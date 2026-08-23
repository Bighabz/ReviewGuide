"""Tests for api_suite: strict sequencing, user_id threading, the marker
gate (refusal + prove-marker green/red), security probes, dry-run
zero-network, and breach-aborts-remaining. All mocked - no network."""

import json
import types

import pytest

from lib import marker
from runners import _base, api_suite

# The first conversation in every run mints this session (now_fn + rand r1).
FIRST_SESSION = marker.mint_session("2026-08-22T00:00:00Z", "r1")


def _sse(user_id, completeness="full", coverage=None):
    # Real wire shape: event name on the event: line, no type key in the JSON.
    done = {
        "session_id": "s",
        "user_id": user_id,
        "status": "completed",
        "completeness": completeness,
        "response_metadata": {"provider_coverage": coverage or []},
    }
    return [
        "event: status",
        'data: {"text":"reading..."}',
        "",
        "event: content",
        'data: {"token":"hi"}',
        "",
        "event: done",
        "data: " + json.dumps(done),
        "",
    ]


class FakeChat:
    """Mock POST /v1/chat/stream. Appends one row per turn under the
    session; on an UNthreaded turn 2 it re-keys to a UUID (the breach the
    marker guards against)."""

    def __init__(self, completeness="full", coverage=None, preseed=None):
        self.db = dict(preseed or {})
        self.payloads = []
        self.user_id = "u-123"
        self.completeness = completeness
        self.coverage = coverage

    def __call__(self, payload):
        self.payloads.append(dict(payload))
        sid = payload["session_id"]
        if payload.get("user_id") is None and self.db.get(sid):
            sid = "uuid-%d" % len(self.db)  # server re-key -> prefix lost
        uid = payload.get("user_id") or self.user_id
        self.db.setdefault(sid, []).append(
            {"session_id": sid, "user_id": uid, "content": payload.get("message", "")}
        )
        return _sse(uid, self.completeness, self.coverage)


class FakeQuery:
    def __init__(self, db):
        self.db = db

    def __call__(self, kind, params):
        if kind == "rows_for_session":
            return list(self.db.get(params["session_id"], []))
        if kind == "orphan_scan":
            marker_str = params["content_marker"]
            prefix = params["prefix"]
            return [
                r
                for rows in self.db.values()
                for r in rows
                if marker_str in r.get("content", "")
                and not r["session_id"].startswith(prefix)
            ]
        raise AssertionError("unexpected kind %r" % kind)


class FakeHttp:
    def __init__(
        self,
        ready_status=200,
        manifest=None,
        admin_status=401,
        errors_chart_status=None,
        post_status=422,
        acao=None,
    ):
        self.ready_status = ready_status
        self.manifest = manifest if manifest is not None else {"rate_limiting_enabled": False}
        self.admin_status = admin_status
        self.errors_chart_status = errors_chart_status
        self.post_code = post_status
        self.acao = acao
        self.gets = []
        self.posts = []
        self.opts = []

    def get(self, url, timeout_s=30, headers=None):
        self.gets.append(url)
        if url.endswith("/health/ready"):
            return {"status": self.ready_status, "json": {"manifest": self.manifest}, "headers": {}}
        if url.endswith("/v1/admin/metrics/errors/chart") and self.errors_chart_status is not None:
            return {"status": self.errors_chart_status, "json": None, "headers": {}}
        return {"status": self.admin_status, "json": None, "headers": {}}

    def post(self, url, payload, timeout_s=30, headers=None):
        self.posts.append((url, payload))
        return {"status": self.post_code, "json": None}

    def options(self, url, origin, method="POST", timeout_s=30):
        self.opts.append((url, origin))
        return {"status": 400 if self.acao is None else 200, "acao": self.acao}


@pytest.fixture(autouse=True)
def _qa_key(monkeypatch):
    # emit() -> store.record_observation builds headers from this key.
    monkeypatch.setenv("SUPABASE_QA_KEY", "test-key")


def _args(prove_marker=False):
    return types.SimpleNamespace(prove_marker=prove_marker)


def make_ctx(tmp_path, chat=None, query=None, http=None, dry_run=False, gate=True, **over):
    cfg = {
        "prod_backend": "https://backend.example",
        "prod_frontend": "https://front.example",
        "marker_gate_proven": gate,
        "messages_per_turn": 1,
        "per_prompt_usd": 0.02,
        "chat_prompts_per_day": 6,
        "security_probe_interval_s": 0.0,
        "runner_version": "1",
        "dry_run": dry_run,
    }
    cfg.update(over)
    http = http or FakeHttp()
    sleeps = []
    counter = {"n": 0}

    def rand_fn():
        counter["n"] += 1
        return "r%d" % counter["n"]

    ctx = _base.RunnerContext(
        cfg,
        "run-1",
        str(tmp_path),
        dry_run=dry_run,
        store_exec=lambda req: None,
        post_fn=chat,
        query_fn=query,
        http_get=http.get,
        http_post=http.post,
        http_options=http.options,
        now_fn=lambda: "2026-08-22T00:00:00Z",
        rand_fn=rand_fn,
        sleep_fn=lambda s: sleeps.append(s),
    )
    ctx._sleeps = sleeps
    ctx._http = http
    return ctx


def _findings_from_artifact(tmp_path):
    data = json.loads(open(tmp_path / "api_suite.json", encoding="utf-8").read())
    return data["findings"]


# --- dry run: zero network -----------------------------------------------

def test_dry_run_makes_zero_network(tmp_path):
    # All network seams are guards (not supplied) -> any call raises.
    ctx = _base.RunnerContext(
        {
            "prod_backend": "https://b.example",
            "prod_frontend": "https://f.example",
            "marker_gate_proven": True,
            "dry_run": True,
            "runner_version": "1",
        },
        "run-dry",
        str(tmp_path),
        dry_run=True,
    )
    code = api_suite.run(ctx, _args())
    assert code == _base.EXIT_OK
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "dry-run" for f in findings)


# --- marker gate refusal (REQUIRED test a) -------------------------------

def test_marker_gate_refusal_makes_no_chat_calls(tmp_path):
    chat = FakeChat()
    ctx = make_ctx(tmp_path, chat=chat, query=FakeQuery(chat.db), gate=False)
    code = api_suite.run(ctx, _args())
    assert code == _base.EXIT_OK
    assert chat.payloads == []  # NOT ONE chat turn fired with the gate closed
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "marker-gate-unproven" for f in findings)


# --- prove-marker green + red (REQUIRED test b) --------------------------

def test_count_mismatch_breaches_with_messages_per_turn_2(tmp_path):
    # Prod writes 2 rows/turn; FakeChat writes 1. With messages_per_turn=2 the
    # 2-turn prove convo expects 4 rows but finds 2 -> count mismatch -> breach.
    # (Guards the expected = turns * messages_per_turn math against silent green.)
    chat = FakeChat()
    ctx = make_ctx(tmp_path, chat=chat, query=FakeQuery(chat.db), messages_per_turn=2)
    code = api_suite.run(ctx, _args(prove_marker=True))
    assert code == _base.EXIT_BREACH
    findings = _findings_from_artifact(tmp_path)
    breach = [f for f in findings if f["check"] == "containment-breach"]
    assert breach and "expected 4" in breach[0]["summary"]


def test_prove_marker_green_path(tmp_path):
    chat = FakeChat()
    ctx = make_ctx(tmp_path, chat=chat, query=FakeQuery(chat.db))
    code = api_suite.run(ctx, _args(prove_marker=True))
    assert code == _base.EXIT_OK
    assert len(chat.payloads) == 2  # exactly one 2-turn conversation
    # turn 1 sends no user_id; turn 2 threads the assigned user_id.
    assert chat.payloads[0].get("user_id") is None
    assert chat.payloads[1]["user_id"] == "u-123"


def test_prove_marker_red_path_orphan_exits_breach(tmp_path):
    # A row carrying the session marker under a non-qa-auto session = a leaked
    # (re-keyed) row = breach, even though the qa-auto rows look intact.
    orphan = {"session_id": "legacy-uuid", "user_id": "u-9", "content": "leaked [qa-ref:%s]" % FIRST_SESSION}
    chat = FakeChat(preseed={"legacy-uuid": [orphan]})
    ctx = make_ctx(tmp_path, chat=chat, query=FakeQuery(chat.db))
    code = api_suite.run(ctx, _args(prove_marker=True))
    assert code == _base.EXIT_BREACH
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "containment-breach" for f in findings)


# --- sequencing + threading ----------------------------------------------

def test_conversations_are_strictly_sequential(tmp_path):
    chat = FakeChat()
    ctx = make_ctx(tmp_path, chat=chat, query=FakeQuery(chat.db))
    api_suite.run(ctx, _args())
    # 1 + 2 + 2 turns; each conversation's session_id block is contiguous.
    sessions = [p["session_id"] for p in chat.payloads]
    assert len(sessions) == 5
    # contiguous grouping: collapsing runs of equal ids yields distinct ids.
    collapsed = [s for i, s in enumerate(sessions) if i == 0 or s != sessions[i - 1]]
    assert len(collapsed) == len(set(collapsed)) == 3


def test_user_id_threaded_into_turn_two(tmp_path):
    chat = FakeChat()
    ctx = make_ctx(tmp_path, chat=chat, query=FakeQuery(chat.db))
    api_suite.run(ctx, _args())
    # The cordless conversation is turns index 1 and 2 in payloads.
    assert chat.payloads[1]["session_id"] == chat.payloads[2]["session_id"]
    assert chat.payloads[2]["user_id"] == "u-123"


# --- provider honesty -----------------------------------------------------

class RecordingPost:
    """A chat endpoint whose done event carries NO user_id."""

    def __init__(self):
        self.payloads = []

    def __call__(self, payload):
        self.payloads.append(dict(payload))
        return [
            "event: content",
            'data: {"token":"hi"}',
            "",
            "event: done",
            'data: {"status":"completed"}',
            "",
        ]


def test_turn1_no_user_id_refuses_turn2(tmp_path):
    # If turn 1 yields no user_id, sending turn 2 would detonate the UUID-swap.
    # The runner must refuse turn 2 and breach instead (#5).
    post = RecordingPost()
    ctx = make_ctx(tmp_path, chat=post, query=FakeQuery({}))
    code = api_suite.run(ctx, _args(prove_marker=True))
    assert code == _base.EXIT_BREACH
    assert len(post.payloads) == 1  # turn 2 was NOT sent
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "turn-no-user-id" for f in findings)


def test_conversation_error_becomes_breach_not_crash(tmp_path):
    # A raising query_fn (PostgREST 400, etc.) must yield EXIT_BREACH with a
    # finding, never EXIT_CRASH that loses all findings (#3).
    def raising_query(kind, params):
        raise RuntimeError("pg 400")

    chat = FakeChat()
    ctx = make_ctx(tmp_path, chat=chat, query=raising_query)
    code = api_suite.run(ctx, _args())
    assert code == _base.EXIT_BREACH
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "conversation-error" for f in findings)


def test_hidden_degradation_flagged(tmp_path):
    chat = FakeChat(completeness="full", coverage=[{"provider": "cj", "status": "error"}])
    ctx = make_ctx(tmp_path, chat=chat, query=FakeQuery(chat.db))
    api_suite.run(ctx, _args())
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "hidden-degradation" for f in findings)


# --- security probes ------------------------------------------------------

def test_admin_200_is_high_finding(tmp_path):
    http = FakeHttp(errors_chart_status=200)
    ctx = make_ctx(tmp_path, chat=FakeChat(), query=FakeQuery({}), http=http, gate=False)
    api_suite.run(ctx, _args())
    findings = _findings_from_artifact(tmp_path)
    hit = [f for f in findings if f["check"] == "admin-unauthenticated-200"]
    assert hit and hit[0]["severity"] == "high"
    assert hit[0]["locus"] == "/v1/admin/metrics/errors/chart"


def test_cors_reflection_is_high(tmp_path):
    http = FakeHttp(acao=api_suite.EVIL_ORIGIN)
    ctx = make_ctx(tmp_path, chat=FakeChat(), query=FakeQuery({}), http=http, gate=False)
    api_suite.run(ctx, _args())
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "cors-origin-reflected" and f["severity"] == "high" for f in findings)


def test_oversized_message_not_422_flagged(tmp_path):
    http = FakeHttp(post_status=200)
    ctx = make_ctx(tmp_path, chat=FakeChat(), query=FakeQuery({}), http=http, gate=False)
    api_suite.run(ctx, _args())
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "oversized-not-rejected" for f in findings)


def test_probes_spaced_by_configured_interval(tmp_path):
    ctx = make_ctx(
        tmp_path,
        chat=FakeChat(),
        query=FakeQuery({}),
        gate=False,
        security_probe_interval_s=1.5,
    )
    api_suite.run(ctx, _args())
    # 4 admin + 1 oversized POST + 1 CORS OPTIONS = 6 spaced probes.
    assert ctx._sleeps == [1.5] * 6


def test_probes_skipped_when_not_ready(tmp_path):
    http = FakeHttp(ready_status=503)
    ctx = make_ctx(tmp_path, chat=FakeChat(), query=FakeQuery({}), http=http, gate=False)
    api_suite.run(ctx, _args())
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "not-ready" for f in findings)
    assert http.posts == [] and http.opts == []


# --- breach aborts remaining ---------------------------------------------

def test_breach_aborts_remaining_conversations(tmp_path):
    # A leaked row carrying the first conversation's session marker triggers a
    # breach on conversation 1, which must abort the rest.
    orphan = {"session_id": "leak-uuid", "user_id": "u-9", "content": "x [qa-ref:%s]" % FIRST_SESSION}
    chat = FakeChat(preseed={"leak-uuid": [orphan]})
    ctx = make_ctx(tmp_path, chat=chat, query=FakeQuery(chat.db))
    code = api_suite.run(ctx, _args())
    assert code == _base.EXIT_BREACH
    # Only the FIRST conversation (espresso, 1 turn) ran before the abort.
    assert len(chat.payloads) == 1
    findings = _findings_from_artifact(tmp_path)
    assert any(f["check"] == "run-aborted-on-breach" for f in findings)
