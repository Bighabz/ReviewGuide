"""Tests for the runner protocol: finding/fingerprint, emit (artifact +
immutable store writes), secret redaction, exit codes, main() crash guard."""

import json

import pytest

from runners import _base


def test_finding_has_stable_fingerprint_and_fields():
    f1 = _base.finding("security", "admin-200", "/v1/admin/config", "high", "boom")
    f2 = _base.finding("security", "admin-200", "/v1/admin/config", "high", "different summary")
    assert f1["fingerprint"] == f2["fingerprint"]  # identity is dim+check+locus
    assert f1["dimension"] == "security"
    assert f1["status"] == "OPEN"
    other = _base.finding("security", "admin-200", "/v1/admin/users", "high", "x")
    assert other["fingerprint"] != f1["fingerprint"]


def test_finding_rejects_bad_severity():
    with pytest.raises(ValueError):
        _base.finding("d", "c", "l", "catastrophic", "s")


def test_redact_scrubs_all_secrets():
    text = "key=SEKRET and token=BOTTOK end"
    assert _base.redact(text, ["SEKRET", "BOTTOK"]) == "key=[redacted] and token=[redacted] end"


def _dry_ctx(tmp_path, config=None):
    cfg = {"runner_version": "9", "dry_run": True}
    if config:
        cfg.update(config)
    return _base.RunnerContext(cfg, "run-x", str(tmp_path), dry_run=True)


def test_emit_dry_run_writes_artifact_and_skips_store(tmp_path):
    ctx = _dry_ctx(tmp_path)
    findings = [_base.finding("api", "c", "l", "info", "hi")]
    # store_exec is the network guard: if emit called it in dry_run, this
    # would raise.
    path = _base.emit(ctx, "myrunner", findings)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["runner"] == "myrunner"
    assert data["runner_version"] == "9"
    assert data["findings"][0]["summary"] == "hi"


def test_emit_redacts_secret_in_artifact(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_QA_KEY", "SUPER-SECRET-KEY")
    ctx = _dry_ctx(tmp_path)
    findings = [_base.finding("api", "c", "l", "info", "leaked SUPER-SECRET-KEY here")]
    path = _base.emit(ctx, "r", findings)
    text = open(path, encoding="utf-8").read()
    assert "SUPER-SECRET-KEY" not in text
    assert "[redacted]" in text


def test_emit_non_dry_writes_one_observation_per_finding(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_QA_KEY", "k")
    calls = []
    ctx = _base.RunnerContext(
        {"runner_version": "3", "dry_run": False},
        "run-y",
        str(tmp_path),
        dry_run=False,
        store_exec=lambda req: calls.append(req),
    )
    findings = [
        _base.finding("api", "c1", "l1", "high", "a"),
        _base.finding("api", "c2", "l2", "low", "b"),
    ]
    _base.emit(ctx, "r", findings)
    assert len(calls) == 2
    assert all(c["url"].endswith("/rest/v1/observations") for c in calls)
    assert all(c["json"]["runner_version"] == "3" for c in calls)


def test_main_returns_crash_on_exception(tmp_path):
    def boom(_ctx, _args):
        raise RuntimeError("kaboom")

    code = _base.main("t", boom, argv=["--run-id", "r", "--artifacts-dir", str(tmp_path)])
    assert code == _base.EXIT_CRASH


def test_main_passes_through_exit_code(tmp_path):
    def ok(_ctx, _args):
        return _base.EXIT_OK

    code = _base.main("t", ok, argv=["--run-id", "r", "--artifacts-dir", str(tmp_path)])
    assert code == _base.EXIT_OK
