"""Tests for browser_qa: command/env building, JSON-report -> findings,
and dry-run skip. The subprocess runner is faked - npx never runs."""

import json

import pytest

from runners import _base, browser_qa


@pytest.fixture(autouse=True)
def _qa_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_QA_KEY", "test-key")


def _cfg(**over):
    cfg = {
        "prod_frontend": "https://front.example",
        "npx_path": "npx",
        "browser_timeout_s": 123,
        "runner_version": "1",
        "dry_run": False,
    }
    cfg.update(over)
    return cfg


def _ctx(tmp_path, run_subprocess, dry_run=False, **over):
    return _base.RunnerContext(
        _cfg(dry_run=dry_run, **over),
        "run-b",
        str(tmp_path),
        dry_run=dry_run,
        store_exec=lambda req: None,
        run_subprocess=run_subprocess,
    )


def _artifact(tmp_path):
    return json.loads(open(tmp_path / "browser_qa.json", encoding="utf-8").read())


def test_dry_run_skips_subprocess(tmp_path):
    def boom(*a, **k):
        raise AssertionError("subprocess must not run in dry_run")

    ctx = _ctx(tmp_path, boom, dry_run=True)
    code = browser_qa.run(ctx, None)
    assert code == _base.EXIT_OK
    assert any(f["check"] == "dry-run" for f in _artifact(tmp_path)["findings"])


def test_builds_command_and_env(tmp_path):
    seen = {}

    def fake(cmd, cwd=None, env=None, timeout=None):
        seen["cmd"] = cmd
        seen["cwd"] = cwd
        seen["env"] = env
        seen["timeout"] = timeout
        return {"returncode": 0, "stdout": json.dumps({"suites": []}), "stderr": ""}

    ctx = _ctx(tmp_path, fake)
    browser_qa.run(ctx, None)
    assert seen["cmd"] == ["npx", "playwright", "test", "--reporter=json"]
    assert seen["timeout"] == 123
    assert seen["env"]["BASE_URL"] == "https://front.example"
    assert seen["env"]["QA_RUN_ID"] == "run-b"
    assert "QA_RUN_DIR" in seen["env"]


def test_failed_specs_become_findings(tmp_path):
    report = {
        "suites": [
            {
                "title": "checks",
                "specs": [
                    {"title": "A3 five cards", "ok": False},
                    {"title": "A1 discover", "ok": True},
                ],
                "suites": [
                    {"title": "nested", "specs": [{"title": "A7 mobile", "ok": False}]}
                ],
            }
        ]
    }

    def fake(cmd, cwd=None, env=None, timeout=None):
        return {"returncode": 1, "stdout": json.dumps(report), "stderr": ""}

    ctx = _ctx(tmp_path, fake)
    code = browser_qa.run(ctx, None)
    assert code == _base.EXIT_OK
    checks = [f["locus"] for f in _artifact(tmp_path)["findings"] if f["check"] == "spec-failed"]
    assert set(checks) == {"A3 five cards", "A7 mobile"}


def test_unparseable_report_with_failure_is_a_finding(tmp_path):
    def fake(cmd, cwd=None, env=None, timeout=None):
        return {"returncode": 2, "stdout": "not json at all", "stderr": "boom"}

    ctx = _ctx(tmp_path, fake)
    browser_qa.run(ctx, None)
    assert any(f["check"] == "playwright-nonzero-exit" for f in _artifact(tmp_path)["findings"])


def test_parseable_report_but_nonzero_exit_is_a_finding(tmp_path):
    # No per-spec failure, but a non-zero exit (config error / zero tests) must
    # NOT pass as green just because the JSON parsed (#17).
    report = {"suites": [{"title": "s", "specs": [{"title": "A1", "ok": True}]}], "errors": [{"message": "config"}]}

    def fake(cmd, cwd=None, env=None, timeout=None):
        return {"returncode": 1, "stdout": json.dumps(report), "stderr": ""}

    ctx = _ctx(tmp_path, fake)
    browser_qa.run(ctx, None)
    assert any(f["check"] == "playwright-nonzero-exit" for f in _artifact(tmp_path)["findings"])


def test_report_artifact_is_redacted(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_QA_KEY", "SECRET-KEY-XYZ")

    def fake(cmd, cwd=None, env=None, timeout=None):
        # A spec logged a secret into stdout; it must not reach the artifact.
        return {"returncode": 0, "stdout": '{"suites": [], "leak": "SECRET-KEY-XYZ"}', "stderr": ""}

    ctx = _ctx(tmp_path, fake)
    browser_qa.run(ctx, None)
    text = open(tmp_path / "playwright-report.json", encoding="utf-8").read()
    assert "SECRET-KEY-XYZ" not in text
    assert "[redacted]" in text


def test_subprocess_env_excludes_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPABASE_QA_KEY", "SECRET-KEY-XYZ")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "BOT-TOK")
    seen = {}

    def fake(cmd, cwd=None, env=None, timeout=None):
        seen["env"] = env
        return {"returncode": 0, "stdout": json.dumps({"suites": []}), "stderr": ""}

    ctx = _ctx(tmp_path, fake)
    browser_qa.run(ctx, None)
    assert "SUPABASE_QA_KEY" not in seen["env"]
    assert "TELEGRAM_BOT_TOKEN" not in seen["env"]


def test_subprocess_error_is_unavailable_finding(tmp_path):
    def fake(cmd, cwd=None, env=None, timeout=None):
        raise OSError("npx not found")

    ctx = _ctx(tmp_path, fake)
    code = browser_qa.run(ctx, None)
    assert code == _base.EXIT_OK
    assert any(f["check"] == "playwright-unavailable" for f in _artifact(tmp_path)["findings"])
