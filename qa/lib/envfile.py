"""Minimal KEY=VALUE .env loader (stdlib only).

Loads qa/.env into os.environ WITHOUT overwriting values already set in
the environment (a real env var wins over the file). Blank lines and
lines beginning with '#' are ignored; an optional leading 'export ' is
stripped; surrounding single/double quotes on the value are removed.

Secret VALUES are never logged - callers get only the list of keys set.
"""

import os

__all__ = ["load_env", "parse_env"]


def parse_env(text):
    """Parse .env text into an ordered list of (key, value) pairs.

    Pure - no environment access. Malformed lines (no '=') are skipped.
    """
    pairs = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        pairs.append((key, value))
    return pairs


def load_env(path, environ=None):
    """Load KEY=VALUE lines from `path` into environ (default os.environ).

    A key already present in environ is left untouched (real env wins).
    Returns the list of keys that were newly set (never the values).
    Missing file is a no-op returning []. Never logs a value.
    """
    if environ is None:
        environ = os.environ
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return []
    set_keys = []
    for key, value in parse_env(text):
        if key in environ:
            continue
        environ[key] = value
        set_keys.append(key)
    return set_keys
