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
    payload = {"session_id": session_id, "message": message}
    if user_id is not None:
        payload["user_id"] = user_id
    body = post_fn(payload)
    return _parse_stream(body)


def _parse_stream(body):
    done = None
    assistant_ok = False
    chunks = body if isinstance(body, (list, tuple)) else str(body).splitlines()
    for chunk in chunks:
        for line in str(chunk).splitlines():
            line = line.strip()
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
            event_type = event.get("type") or event.get("event")
            if event_type in ("token", "delta", "content"):
                assistant_ok = True
            if event_type == "done" or done is None:
                done = event
    if isinstance(done, dict) and (done.get("ok") is False or done.get("error")):
        assistant_ok = False
    user_id = done.get("user_id") if isinstance(done, dict) else None
    return assistant_ok, user_id


def assert_marker_intact(query_fn, session_id, expected_turns, user_id, window_start):
    """Post-run containment proof. Returns (ok, reason).

    GREEN requires ALL of:
      (a) count of qa-auto rows for session_id == expected_turns;
      (b) NEGATIVE scan via query_fn finds ZERO conversation_messages
          rows for user_id under any non-`qa-auto-%` session_id since
          window_start (an orphan = containment breach);
      (c) every row for the session carries the `qa-auto-` prefix.
    Any miss -> (False, reason). query_fn(kind, params) is injectable.
    """
    rows = query_fn("rows_for_session", {"session_id": session_id}) or []
    if len(rows) != expected_turns:
        return (
            False,
            "expected %d rows for %s, found %d"
            % (expected_turns, session_id, len(rows)),
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
                "user_id": user_id,
                "window_start": window_start,
                "prefix": MARKER_PREFIX,
            },
        )
        or []
    )
    if orphans:
        return (
            False,
            "orphan rows for user_id %s outside qa-auto- sessions: %d"
            % (user_id, len(orphans)),
        )
    return True, "ok"
