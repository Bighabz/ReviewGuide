"""Config loader: config.json defaults overlaid with config.local.json."""

import json

from lib import config


def test_load_reads_committed_config():
    cfg = config.load()
    assert cfg["supabase_ref"] == "qvowmjjcotdonezdtvur"
    assert "prod_backend" in cfg


def test_local_override_wins(tmp_path, monkeypatch):
    local = tmp_path / "config.local.json"
    local.write_text(json.dumps({"npx_path": "npx", "enabled_runners": ["api_suite"]}), encoding="utf-8")
    monkeypatch.setenv("QA_CONFIG_LOCAL", str(local))
    cfg = config.load()
    assert cfg["npx_path"] == "npx"  # overridden
    assert cfg["enabled_runners"] == ["api_suite"]  # added
    assert cfg["supabase_ref"] == "qvowmjjcotdonezdtvur"  # base preserved


def test_missing_local_is_fine(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_CONFIG_LOCAL", str(tmp_path / "absent.json"))
    cfg = config.load()
    assert "prod_backend" in cfg
