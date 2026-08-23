"""Config loader: config.json overlaid with config.local.json (gitignored).

config.json holds the committed defaults (Windows/beeep). A machine-specific
config.local.json (e.g. Linux paths on the VPS) shallow-overrides those keys
so `git pull` never clobbers per-host settings. QA_CONFIG_LOCAL can point at
an explicit override file.
"""

import json
import os

_DIR = os.path.dirname(__file__)


def _path(name):
    return os.path.join(_DIR, "..", name)


def load():
    with open(_path("config.json"), "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    local = os.environ.get("QA_CONFIG_LOCAL") or _path("config.local.json")
    try:
        with open(local, "r", encoding="utf-8") as fh:
            cfg.update(json.load(fh))
    except (OSError, ValueError):
        pass
    return cfg
