"""F1 tests: flake gate + fingerprint stability."""

import hashlib

from lib import flake


def test_fingerprint_is_sha1_hex():
    fp = flake.fingerprint("security", "rate_limit", "POST /v1/chat")
    assert fp == hashlib.sha1(
        "security\x1frate_limit\x1fPOST /v1/chat".encode("utf-8")
    ).hexdigest()
    assert len(fp) == 40
    int(fp, 16)  # valid hex


def test_fingerprint_stable_across_calls():
    first = flake.fingerprint("api", "chat_done", "done event")
    second = flake.fingerprint("api", "chat_done", "done event")
    assert first == second


def test_fingerprint_distinct_per_finding():
    base = flake.fingerprint("api", "chat_done", "done event")
    assert base != flake.fingerprint("browser", "chat_done", "done event")
    assert base != flake.fingerprint("api", "chat_error", "done event")
    assert base != flake.fingerprint("api", "chat_done", "stream event")


def test_gate_fails_only_after_retries_plus_one_consecutive_failures():
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        return False

    status, attempts = flake.run_with_retries(always_fails, retries=2)
    assert status == flake.FAIL
    assert attempts == 3  # retries + 1
    assert calls["n"] == 3


def test_gate_passes_on_transient_failure():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        return calls["n"] >= 3  # fail, fail, pass

    status, attempts = flake.run_with_retries(flaky, retries=2)
    assert status == flake.PASS
    assert attempts == 3


def test_gate_passes_first_try():
    status, attempts = flake.run_with_retries(lambda: True, retries=2)
    assert status == flake.PASS
    assert attempts == 1


def test_gate_counts_exceptions_as_failures():
    calls = {"n": 0}

    def raises_then_passes():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return True

    status, attempts = flake.run_with_retries(raises_then_passes, retries=2)
    assert status == flake.PASS
    assert attempts == 2


def test_gate_default_retries_come_from_config():
    calls = {"n": 0}

    def always_fails():
        calls["n"] += 1
        return False

    status, attempts = flake.run_with_retries(always_fails)
    assert status == flake.FAIL
    # qa/config.json pins flake_retries=2 -> 3 consecutive attempts.
    assert attempts == 3
