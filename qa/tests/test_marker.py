"""F3 tests: the marker contract - green path and breach (red) paths.

The orphan scan keys on CONTENT (conversation_messages has no user_id
column and the re-key lands under a new user), so probe messages embed the
qa-auto session string and a leaked row is found by that marker. All chat +
DB access is mocked; no network.
"""

import uuid

from lib import marker

# Real backend wire shape: the event NAME is on the `event:` line and the
# done payload carries NO `type` key inside the JSON (chat.py _sse_event).
TURN_STREAM = (
    "event: status\n"
    'data: {"text": "Reading reviews..."}\n'
    "\n"
    "event: content\n"
    'data: {"token": "Hello there"}\n'
    "\n"
    "event: done\n"
    'data: {"session_id": "s", "user_id": "%s", "status": "completed"}\n'
    "\n"
)


class FakeChatEndpoint:
    """Mock of POST /v1/chat/stream.

    turn 1: assigns a user_id.
    turn 2+ WITHOUT user_id: server REPLACES the session_id with a fresh
    UUID (the containment-bypass bug the marker contract guards against).
    Stores each row's content so the content-based orphan scan can run.
    """

    def __init__(self, db):
        self.db = db
        self.payloads = []
        self.user_id = "u-" + uuid.uuid4().hex[:8]

    def __call__(self, payload):
        self.payloads.append(dict(payload))
        session_id = payload["session_id"]
        if payload.get("user_id") is None and self.db.get(session_id):
            session_id = str(uuid.uuid4())  # prefix lost
        row = {
            "session_id": session_id,
            "user_id": payload.get("user_id") or self.user_id,
            "content": payload.get("message", ""),
        }
        self.db.setdefault(session_id, []).append(row)
        return TURN_STREAM % row["user_id"]


class FakeQuery:
    """Mock of the Supabase conversation_messages queries."""

    def __init__(self, db):
        self.db = db

    def __call__(self, kind, params):
        if kind == "rows_for_session":
            return list(self.db.get(params["session_id"], []))
        if kind == "orphan_scan":
            marker_str = params["content_marker"]
            prefix = params["prefix"]
            return [
                row
                for rows in self.db.values()
                for row in rows
                if marker_str in row.get("content", "")
                and not row["session_id"].startswith(prefix)
            ]
        raise AssertionError("unexpected query kind: %r" % kind)


def _marked(session, text):
    return "%s [qa-ref:%s]" % (text, session)


def test_clarifier_halt_done_is_a_successful_turn():
    """A clarifier 'halted' done (assistant asked a question, no content
    tokens) is a valid response, not a failed turn."""
    stream = (
        "event: status\n"
        'data: {"text": "Thinking..."}\n'
        "\n"
        "event: done\n"
        'data: {"session_id": "s", "user_id": "u-1", "status": "halted", "followups": {"questions": []}}\n'
        "\n"
    )
    ok, user_id, done = marker.chat_turn_full(lambda payload: stream, "qa-auto-s", "hi")
    assert ok
    assert user_id == "u-1"
    assert done.get("status") == "halted"


def test_error_status_done_is_a_failed_turn():
    stream = (
        "event: done\n"
        'data: {"session_id": "s", "user_id": "u-1", "status": "error"}\n'
        "\n"
    )
    ok, _user_id, _done = marker.chat_turn_full(lambda payload: stream, "qa-auto-s", "hi")
    assert not ok


def test_mint_session_uses_passed_in_parts_only():
    session = marker.mint_session("20260821T101500Z", "ab12cd")
    assert session == "qa-auto-20260821T101500Z-ab12cd"
    assert session.startswith(marker.MARKER_PREFIX)


def test_two_turn_convo_threading_user_id_stays_intact_green():
    db = {}
    chat = FakeChatEndpoint(db)
    query = FakeQuery(db)
    session = marker.mint_session("20260821T101500Z", "ab12cd")
    window_start = "2026-08-21T10:15:00Z"

    ok1, user_id = marker.chat_turn(chat, session, _marked(session, "hi"))
    assert ok1 and user_id
    ok2, _ = marker.chat_turn(chat, session, _marked(session, "follow up"), user_id=user_id)
    assert ok2

    assert chat.payloads[1]["user_id"] == user_id
    assert set(db.keys()) == {session}

    ok, reason = marker.assert_marker_intact(
        query, session, expected_turns=2, content_marker=session, window_start=window_start
    )
    assert ok, reason
    assert reason == "ok"


def test_marker_breach_detected_when_user_id_not_threaded_red_path():
    """RED PATH: turn 2 omits user_id, server re-keys the turn under a bare
    UUID, so the qa-auto session is missing turn 2's row -> count check
    fails AND the marked orphan row is found by the negative scan."""
    db = {}
    chat = FakeChatEndpoint(db)
    query = FakeQuery(db)
    session = marker.mint_session("20260821T101500Z", "ab12cd")
    window_start = "2026-08-21T10:15:00Z"

    ok1, user_id = marker.chat_turn(chat, session, _marked(session, "hi"))
    assert ok1 and user_id
    # BUG: caller fails to thread user_id into turn 2.
    ok2, _ = marker.chat_turn(chat, session, _marked(session, "follow up"))
    assert ok2

    orphan_sessions = [sid for sid in db.keys() if sid != session]
    assert len(orphan_sessions) == 1
    uuid.UUID(orphan_sessions[0])
    assert not orphan_sessions[0].startswith(marker.MARKER_PREFIX)

    ok, reason = marker.assert_marker_intact(
        query, session, expected_turns=2, content_marker=session, window_start=window_start
    )
    assert not ok
    assert "expected 2" in reason
    assert session in reason


def test_missing_rows_fails_count_check():
    query = FakeQuery({})
    session = "qa-auto-20260821T101500Z-ab12cd"
    ok, reason = marker.assert_marker_intact(
        query, session, expected_turns=2, content_marker=session, window_start="2026-08-21T10:15:00Z"
    )
    assert not ok
    assert "expected 2" in reason


def test_row_without_prefix_fails_even_with_clean_orphan_scan():
    session = "qa-auto-20260821T101500Z-ab12cd"
    db = {
        session: [
            {"session_id": session, "content": _marked(session, "a")},
            {"session_id": "plain-session", "content": "no marker here"},
        ]
    }

    class RiggedQuery(FakeQuery):
        def __call__(self, kind, params):
            if kind == "rows_for_session":
                return db[session]
            return super().__call__(kind, params)

    ok, reason = marker.assert_marker_intact(
        RiggedQuery(db), session, expected_turns=2, content_marker=session, window_start="2026-08-21T10:15:00Z"
    )
    assert not ok
    assert "prefix" in reason


def test_marker_breach_detected_by_negative_orphan_scan_red_path():
    """RED PATH (negative-orphan-scan): the qa-auto session kept its full
    expected row count, but a marked row leaked under a non-qa-auto session
    since window_start -> containment breach caught by content scan."""
    session = marker.mint_session("20260821T101500Z", "ab12cd")
    orphan_session = str(uuid.uuid4())
    db = {
        session: [
            {"session_id": session, "content": _marked(session, "hi")},
            {"session_id": session, "content": _marked(session, "again")},
        ],
        orphan_session: [{"session_id": orphan_session, "content": _marked(session, "leaked")}],
    }
    assert not orphan_session.startswith(marker.MARKER_PREFIX)

    ok, reason = marker.assert_marker_intact(
        FakeQuery(db), session, expected_turns=2, content_marker=session, window_start="2026-08-21T10:15:00Z"
    )
    assert not ok
    assert "orphan" in reason
    assert session in reason


def test_no_content_marker_is_red():
    """Defense-in-depth (#14): a missing marker can never be a green pass."""
    ok, reason = marker.assert_marker_intact(
        FakeQuery({}), "qa-auto-x", expected_turns=2, content_marker="", window_start="w"
    )
    assert not ok
    assert "content_marker" in reason
