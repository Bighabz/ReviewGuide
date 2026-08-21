"""F3 tests: the marker contract - green path and breach (red) path.

All chat + DB access is mocked; no network.
"""

import uuid

from lib import marker

TURN_STREAM = (
    'data: {"type": "token", "content": "Hello"}\n'
    'data: {"type": "token", "content": " there"}\n'
    'data: {"type": "done", "user_id": "%s"}\n'
)


class FakeChatEndpoint:
    """Mock of POST /v1/chat/stream.

    turn 1: assigns a user_id.
    turn 2+ WITHOUT user_id: server REPLACES the session_id with a fresh
    UUID (the containment-bypass bug the marker contract guards against).
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
            return [
                row
                for rows in self.db.values()
                for row in rows
                if row["user_id"] == params["user_id"]
                and not row["session_id"].startswith(params["prefix"])
            ]
        raise AssertionError("unexpected query kind: %r" % kind)


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

    ok1, user_id = marker.chat_turn(chat, session, "hi")
    assert ok1 and user_id
    ok2, _ = marker.chat_turn(chat, session, "follow up", user_id=user_id)
    assert ok2

    # user_id was threaded into turn 2.
    assert chat.payloads[1]["user_id"] == user_id
    # Both turns stayed under the qa-auto session.
    assert set(db.keys()) == {session}

    ok, reason = marker.assert_marker_intact(
        query, session, expected_turns=2, user_id=user_id, window_start=window_start
    )
    assert ok, reason
    assert reason == "ok"


def test_marker_breach_detected_when_user_id_not_threaded_red_path():
    """RED PATH: turn 2 omits user_id, server re-keys the turn under a bare
    UUID, and assert_marker_intact MUST catch it - including via the
    negative orphan scan (rows for the user outside qa-auto-* sessions)."""
    db = {}
    chat = FakeChatEndpoint(db)
    query = FakeQuery(db)
    session = marker.mint_session("20260821T101500Z", "ab12cd")
    window_start = "2026-08-21T10:15:00Z"

    ok1, user_id = marker.chat_turn(chat, session, "hi")
    assert ok1 and user_id
    # BUG: caller fails to thread user_id into turn 2.
    ok2, _ = marker.chat_turn(chat, session, "follow up")
    assert ok2

    # The server replaced the session with a UUID: the prefix is gone.
    orphan_sessions = [sid for sid in db.keys() if sid != session]
    assert len(orphan_sessions) == 1
    uuid.UUID(orphan_sessions[0])  # really a UUID
    assert not orphan_sessions[0].startswith(marker.MARKER_PREFIX)

    ok, reason = marker.assert_marker_intact(
        query, session, expected_turns=2, user_id=user_id, window_start=window_start
    )
    assert not ok
    assert "expected 2" in reason  # count check fired (turn-2 row landed outside the session)
    assert session in reason


def test_missing_rows_fails_count_check():
    query = FakeQuery({})
    ok, reason = marker.assert_marker_intact(
        query,
        "qa-auto-20260821T101500Z-ab12cd",
        expected_turns=2,
        user_id="u-1",
        window_start="2026-08-21T10:15:00Z",
    )
    assert not ok
    assert "expected 2" in reason


def test_row_without_prefix_fails_even_with_clean_orphan_scan():
    session = "qa-auto-20260821T101500Z-ab12cd"
    db = {
        session: [
            {"session_id": session, "user_id": "u-1"},
            {"session_id": "plain-session", "user_id": "u-1"},
        ]
    }

    class RiggedQuery(FakeQuery):
        def __call__(self, kind, params):
            if kind == "rows_for_session":
                return db[session]
            return super().__call__(kind, params)

    ok, reason = marker.assert_marker_intact(
        RiggedQuery(db),
        session,
        expected_turns=2,
        user_id="u-1",
        window_start="2026-08-21T10:15:00Z",
    )
    assert not ok
    assert "prefix" in reason


def test_marker_breach_detected_by_negative_orphan_scan_red_path():
    """RED PATH (negative-orphan-scan): the qa-auto session itself kept the
    full expected row count, but a scan for user_id rows under non-qa-auto
    sessions since window_start finds an orphan -> containment breach."""
    session = marker.mint_session("20260821T101500Z", "ab12cd")
    user_id = "u-orphan"
    orphan_session = str(uuid.uuid4())
    db = {
        session: [
            {"session_id": session, "user_id": user_id},
            {"session_id": session, "user_id": user_id},
        ],
        orphan_session: [{"session_id": orphan_session, "user_id": user_id}],
    }
    assert not orphan_session.startswith(marker.MARKER_PREFIX)

    ok, reason = marker.assert_marker_intact(
        FakeQuery(db),
        session,
        expected_turns=2,
        user_id=user_id,
        window_start="2026-08-21T10:15:00Z",
    )
    assert not ok
    assert "orphan" in reason  # negative-orphan-scan path fired
    assert user_id in reason

