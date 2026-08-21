"""F2 tests: store builds correct immutable payloads (fake executor, no network)."""

import pytest

from lib import store

TEST_KEY = "test-service-key-not-real"


class FakeExecutor:
    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return {"ok": True, "status": 201}


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setenv("SUPABASE_QA_KEY", TEST_KEY)
    return FakeExecutor()


def test_start_run_posts_runs_row(fake):
    store.start_run(fake, "run-2026-08-21-001", "beeep")
    req = fake.requests[0]
    assert req["method"] == "POST"
    assert req["url"].endswith("/rest/v1/runs")
    assert req["json"]["run_id"] == "run-2026-08-21-001"
    assert req["json"]["host"] == "beeep"
    assert req["json"]["status"] == "running"


def test_beat_posts_heartbeat(fake):
    store.beat(fake, "run-1")
    req = fake.requests[0]
    assert req["method"] == "POST"
    assert req["url"].endswith("/rest/v1/heartbeats")
    assert req["json"] == {"run_id": "run-1"}


def test_record_observation_is_immutable_and_versioned(fake):
    store.record_observation(
        fake,
        run_id="run-1",
        fingerprint="abc123",
        dimension="security",
        severity="HIGH",
        summary="rate limit off",
        locus="POST /v1/chat",
        status="OPEN",
        runner_version="1.0.0",
    )
    req = fake.requests[0]
    assert req["method"] == "POST"
    assert req["url"].endswith("/rest/v1/observations")
    payload = req["json"]
    assert payload["run_id"] == "run-1"
    assert payload["fingerprint"] == "abc123"
    assert payload["runner_version"] == "1.0.0"
    assert payload["severity"] == "HIGH"
    # Immutable per-run rows keyed (run_id, fingerprint): insert with
    # ignore-duplicates, never an upsert that overwrites history.
    assert req["query"]["on_conflict"] == "run_id,fingerprint"
    assert "ignore-duplicates" in req["headers"]["Prefer"]


def test_two_runs_same_fingerprint_write_two_rows(fake):
    for run_id in ("run-1", "run-2"):
        store.record_observation(
            fake,
            run_id=run_id,
            fingerprint="abc123",
            dimension="api",
            severity="MED",
            summary="s",
            locus="l",
            status="OPEN",
            runner_version="1.0.0",
        )
    run_ids = [r["json"]["run_id"] for r in fake.requests]
    assert run_ids == ["run-1", "run-2"]


def test_finish_run_patches_counts(fake):
    store.finish_run(fake, "run-1", {"PASS": 9, "FAIL": 1})
    req = fake.requests[0]
    assert req["method"] == "PATCH"
    assert req["url"].endswith("/rest/v1/runs")
    assert req["query"]["run_id"] == "eq.run-1"
    assert req["json"]["status"] == "finished"
    assert req["json"]["counts"] == {"PASS": 9, "FAIL": 1}


def test_uses_browser_user_agent_for_cloudflare(fake):
    store.beat(fake, "run-1")
    ua = fake.requests[0]["headers"]["User-Agent"]
    assert ua.startswith("Mozilla/5.0")


def test_targets_qa_schema(fake):
    store.beat(fake, "run-1")
    headers = fake.requests[0]["headers"]
    assert headers["Accept-Profile"] == "qa"
    assert headers["Content-Profile"] == "qa"


def test_service_key_from_env_and_never_in_payload(fake):
    store.beat(fake, "run-1")
    req = fake.requests[0]
    assert req["headers"]["Authorization"] == "Bearer " + TEST_KEY
    assert req["headers"]["apikey"] == TEST_KEY
    assert TEST_KEY not in repr(req["json"])
    assert TEST_KEY not in req["url"]


def test_missing_service_key_raises(monkeypatch):
    monkeypatch.delenv("SUPABASE_QA_KEY", raising=False)
    with pytest.raises(RuntimeError):
        store.beat(FakeExecutor(), "run-1")
