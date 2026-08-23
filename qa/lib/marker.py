"""Marker contract for the QA loop (THE critical piece).

Every synthetic conversation MUST run under a session_id with the
`qa-auto-` prefix so prod containment filters can isolate and prune QA
writes. The known failure mode: the server replaces the session with a
fresh UUID on turn 2+ unless the caller threads the `user_id` assigned
in turn 1's done event back into every subsequent turn - losing the
prefix and bypassing containment.

api_suite MUST run conversations sequentially; one session per
conversation; user_id threaded into every turn after the first.
"""

import json

MARKER_PREFIX = "qa-auto-"


def mint_session(now_iso, rand):
    """Build `qa-auto-{now_iso}-{rand}`.

    Both parts are passed in - never Date.now/random inside (callers
    vary rand per turn/run).
    """
    return "%s%s-%s" % (MARKER_PREFIX, now_iso, rand)


def chat_turn(post_fn, session_id, message, user_id=None):
    """POST one chat turn via the injectable post_fn(payload).

    Parses the SSE stream for the done event (chat.py:958) which carries
    the assigned user_id. Returns (assistant_ok, returned_user_id); the
    caller MUST thread returned_user_id into the next turn or the server
    replaces the session_id with a UUID and the prefix is lost.
    """
    assistant_ok, user_id, _done = chat_turn_full(
        post_fn, session_id, message, user_id
    )
    return assistant_ok, user_id


def chat_turn_full(post_fn, session_id, message, user_id=None):
    """Like chat_turn but also returns the full done event dict, so callers
    can inspect completeness / provider_coverage (provider-honesty check).

    Returns (assistant_ok, returned_user_id, done_event_or_None).
    """
    payload = {"session_id": session_id, "message": message}
    if user_id is not None:
        payload["user_id"] = user_id
    body = post_fn(payload)
    return _parse_stream_full(body)


def _parse_stream(body):
    assistant_ok, user_id, _done = _parse_stream_full(body)
    return assistant_ok, user_id


def _iter_lines(body):
    """Yield individual SSE lines, PRESERVING blank lines (the frame
    separators). Accepts a list of lines, a list of blobs, or one string."""
    if isinstance(body, (list, tuple)):
        for item in body:
            text = "" if item is None else str(item)
            if "\n" in text:
                for line in text.split("\n"):
                    yield line
            else:
                yield text
    else:
        for line in str(body).split("\n"):
            yield line


def _parse_stream_full(body):
    """Parse the backend SSE stream the way frontend/lib/chatApi.ts does.

    The event NAME is on an `event: <name>` line and the JSON is on the
    following `data: <json>` line; the backend's done payload carries NO
    `type` key inside the JSON (chat.py `_sse_event`). A blank line resets
    the current event to the legacy 'data' channel, where the JSON may
    carry its own `type`/`done`/`user_id` keys.

    Returns (assistant_ok, user_id, done_event_or_None).
    """
    done = None
    error = None
    assistant_ok = False
    current_event = None  # None => legacy/data channel
    for raw in _iter_lines(body):
        line = raw.rstrip("\r")
        if line.strip() == "":
            current_event = None  # frame separator resets to legacy channel
            continue
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
            continue
        if not line.startswith("data:"):
            continue
        data = line[len("data:"):].strip()
        if not data:
            continue
        try:
            event = json.loads(data)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        # Effective type: the SSE event name wins; else an inline type/event
        # key (legacy mocks / old backend); else the legacy 'data' channel.
        etype = current_event or event.get("type") or event.get("event") or "data"
        if etype in ("content", "token", "delta"):
            assistant_ok = True
        elif etype == "status":
            pass  # placeholder status line, not real assistant content
        elif etype == "done":
            done = event
            # A clean done is a successful turn - including a clarifier
            # "halted" (the assistant asked a question), which is a valid
            # response, not a failure. Only an explicit error/failed status
            # (or an error event / done.error, handled below) marks failure.
            status = str(event.get("status") or "").lower()
            if status not in ("error", "failed", "failure"):
                assistant_ok = True
        elif etype == "error":
            error = event
        else:
            # legacy 'data' channel: the JSON itself discriminates.
            if event.get("token") or event.get("content"):
                assistant_ok = True
            if event.get("error"):
                error = event
            is_done = event.get("done") is True or event.get("type") == "done"
            if is_done or (done is None and event.get("user_id") is not None):
                done = event
    if error is not None:
        assistant_ok = False
        if done is None:
            done = error
    if isinstance(done, dict) and (done.get("ok") is False or done.get("error")):
        assistant_ok = False
    user_id = done.get("user_id") if isinstance(done, dict) else None
    return assistant_ok, user_id, (done if isinstance(done, dict) else None)


def assert_marker_intact(
    query_fn,
    session_id,
    expected_turns,
    content_marker,
    window_start,
    settle_sleep=None,
    settle_attempts=1,
):
    """Post-run containment proof. Returns (ok, reason).

    The backend persists each turn fire-and-forget AFTER the stream ends
    (chat.py save_turn task), so the row count can lag. `settle_sleep` (a
    zero-arg callable) + `settle_attempts` poll `rows_for_session` until the
    count reaches expected_turns before the checks run - so a timing lag is
    not mistaken for a breach, and (crucially) the orphan scan only runs once
    all our rows are present, never against a half-written state.

    The `conversation_messages` table has NO user_id column (only session_id,
    content, created_at) and the UUID-swap breach re-keys turn 2 under a NEW
    anonymous user, so a user_id-based orphan scan is impossible AND could
    not attribute the leaked rows. Instead the caller embeds `content_marker`
    (the qa-auto session string) into every probe message, so any leaked row
    carries the marker in its content under a non-qa-auto session.

    GREEN requires ALL of:
      (a) count of rows for session_id == expected_turns (a re-key drops
          turn-2 rows out of this session -> count falls short -> breach);
      (b) NEGATIVE scan: ZERO conversation_messages rows whose content
          carries `content_marker` under any non-`qa-auto-%` session_id
          since window_start (a marked orphan = the re-key breach);
      (c) every row for the session carries the `qa-auto-` prefix.
    Any miss -> (False, reason). query_fn(kind, params) is injectable.
    """
    if not content_marker:
        # No marker -> containment is unverifiable; never a passing query.
        return (False, "no content_marker for session %s" % session_id)
    rows = query_fn("rows_for_session", {"session_id": session_id}) or []
    attempt = 1
    while (
        len(rows) != expected_turns
        and settle_sleep is not None
        and attempt < max(1, settle_attempts)
    ):
        settle_sleep()
        rows = query_fn("rows_for_session", {"session_id": session_id}) or []
        attempt += 1
    if len(rows) != expected_turns:
        return (
            False,
            "expected %d rows for %s, found %d (after %d attempt(s))"
            % (expected_turns, session_id, len(rows), attempt),
        )
    for row in rows:
        row_session = (row or {}).get("session_id", "")
        if not row_session.startswith(MARKER_PREFIX):
            return (
                False,
                "row lost marker prefix: session_id=%r" % row_session,
            )
    orphans = (
        query_fn(
            "orphan_scan",
            {
                "content_marker": content_marker,
                "window_start": window_start,
                "prefix": MARKER_PREFIX,
            },
        )
        or []
    )
    if orphans:
        return (
            False,
            "orphan rows carrying marker %s under non-qa-auto sessions: %d"
            % (content_marker, len(orphans)),
        )
    return True, "ok"
