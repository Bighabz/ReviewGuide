"""Tests for the Increment-3 local runners (unit_suite, deps_audit,
lighthouse, data_integrity). All subprocess/network seams faked."""

import json

import pytest

from runners import _base, data_integrity, deps_audit, lighthouse, unit_suite


@pytest.fixture(autouse=True)
def _qa_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_QA_KEY", "test-key")


def _ctx(tmp_path, cfg, **seams):
    base = {"runner_version": "1", "dry_run": False}
    base.update(cfg)
    return _base.RunnerContext(
        base, "run-i3", str(tmp_path), dry_run=False, store_exec=lambda r: None, **seams
    )


def _findings(tmp_path, name):
    return json.loads(open(tmp_path / ("%s.json" % name), encoding="utf-8").read())["findings"]


# --- unit_suite ----------------------------------------------------------

def test_unit_suite_flags_failed_suite(tmp_path):
    calls = []

    def fake(argv, cwd=None, env=None, timeout=None):
        calls.append(argv)
        return {"returncode": 1 if "pytest" in " ".join(argv) else 0, "stdout": "", "stderr": "boom"}

    cfg = {"unit_suite_cmds": [["backend-pytest", ["x", "pytest"], None], ["lint", ["y"], "frontend"]]}
    ctx = _ctx(tmp_path, cfg, run_subprocess=fake)
    unit_suite.run(ctx, None)
    checks = [f for f in _findings(tmp_path, "unit_suite") if f["check"] == "suite-failed"]
    assert len(checks) == 1 and checks[0]["locus"] == "backend-pytest"


# --- deps_audit ----------------------------------------------------------

def test_deps_audit_flags_over_baseline(tmp_path):
    report = {"metadata": {"vulnerabilities": {"high": 10, "critical": 2, "moderate": 5}}}

    def fake(argv, cwd=None, env=None, timeout=None):
        return {"returncode": 1, "stdout": json.dumps(report), "stderr": ""}

    ctx = _ctx(tmp_path, {"deps_accepted_high": 8}, run_subprocess=fake)
    deps_audit.run(ctx, None)
    assert any(f["check"] == "high-vulns-over-baseline" for f in _findings(tmp_path, "deps_audit"))


def test_deps_audit_under_baseline_is_info(tmp_path):
    report = {"metadata": {"vulnerabilities": {"high": 3, "critical": 0}}}

    def fake(argv, cwd=None, env=None, timeout=None):
        return {"returncode": 1, "stdout": json.dumps(report), "stderr": ""}

    ctx = _ctx(tmp_path, {"deps_accepted_high": 8}, run_subprocess=fake)
    deps_audit.run(ctx, None)
    checks = [f["check"] for f in _findings(tmp_path, "deps_audit")]
    assert "audit-counts" in checks and "high-vulns-over-baseline" not in checks


# --- lighthouse ----------------------------------------------------------

def test_lighthouse_flags_low_score(tmp_path):
    report = {
        "categories": {
            "performance": {"score": 0.5},
            "accessibility": {"score": 0.98},
            "best-practices": {"score": 1.0},
            "seo": {"score": 1.0},
        },
        "audits": {
            "cumulative-layout-shift": {"numericValue": 0.0},
            "largest-contentful-paint": {"numericValue": 1200},
        },
    }

    def fake(argv, cwd=None, env=None, timeout=None):
        return {"returncode": 0, "stdout": json.dumps(report), "stderr": ""}

    ctx = _ctx(tmp_path, {"prod_frontend": "https://f.example"}, run_subprocess=fake)
    lighthouse.run(ctx, None)
    checks = [f["check"] for f in _findings(tmp_path, "lighthouse")]
    assert "low-score:performance" in checks


def test_lighthouse_crash_is_low_not_fatal(tmp_path):
    def fake(argv, cwd=None, env=None, timeout=None):
        raise OSError("no lighthouse")

    ctx = _ctx(tmp_path, {"prod_frontend": "https://f.example"}, run_subprocess=fake)
    code = lighthouse.run(ctx, None)
    assert code == _base.EXIT_OK
    assert any(f["check"] == "unavailable" for f in _findings(tmp_path, "lighthouse"))


# --- data_integrity ------------------------------------------------------

def test_data_integrity_reconciles_and_flags_sweeper(tmp_path):
    def fake_public_get(path, query, timeout=30):
        if "conversation_messages" in path:
            return [{"id": 1, "session_id": "qa-auto-x"}, {"id": 2, "session_id": "qa-auto-x"}]
        if "affiliate_clicks" in path:
            return [{"id": 9, "session_id": "qa-auto-x"}]
        if "kv_cache" in path:
            return [{"key": "stale-1"}]
        return []

    ctx = _ctx(
        tmp_path,
        {"prune_warn_rows": 2000},
        public_get=fake_public_get,
        now_fn=lambda: "2026-08-22T00:00:00Z",
    )
    data_integrity.run(ctx, None)
    findings = _findings(tmp_path, "data_integrity")
    assert any(f["check"] == "sweeper-lag" for f in findings)
    manifest = json.loads(open(tmp_path / "qa-writes-manifest.json", encoding="utf-8").read())
    assert manifest["conversation_messages"] == [1, 2]
    assert manifest["affiliate_clicks"] == [9]


def test_data_integrity_dry_run_skips(tmp_path):
    ctx = _base.RunnerContext(
        {"runner_version": "1", "dry_run": True}, "run-i3", str(tmp_path), dry_run=True
    )
    code = data_integrity.run(ctx, None)
    assert code == _base.EXIT_OK
    assert any(f["check"] == "dry-run" for f in _findings(tmp_path, "data_integrity"))
