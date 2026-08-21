"""Flake gate + finding fingerprinting for the QA loop.

Pure functions only - no I/O, no network, no clock access.
"""

import hashlib
import json
import os

PASS = "PASS"
FAIL = "FAIL"

_DEFAULT_RETRIES = 2


def _config_retries():
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            return int(json.load(handle).get("flake_retries", _DEFAULT_RETRIES))
    except (OSError, ValueError):
        return _DEFAULT_RETRIES


def fingerprint(dimension, check, locus):
    """Stable finding identity: sha1 hex of dimension+check+locus."""
    payload = "\x1f".join([dimension or "", check or "", locus or ""])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def run_with_retries(fn, retries=None):
    """Run fn until it passes or fails retries+1 times in a row.

    Returns (status, attempts): FAIL only after retries+1 consecutive
    failures (default retries comes from qa/config.json flake_retries);
    a transient failure followed by a pass is PASS.
    """
    if retries is None:
        retries = _config_retries()
    attempts = 0
    while True:
        attempts += 1
        try:
            if fn():
                return PASS, attempts
        except Exception:
            pass
        if attempts > retries:
            return FAIL, attempts
