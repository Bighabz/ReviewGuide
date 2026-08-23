"""Tests for the .env loader: real env wins, quotes/comments handled, no
value ever returned."""

from lib import envfile


def test_parse_env_basic():
    text = "A=1\n# comment\n\nB = two \nexport C=three\n"
    pairs = dict(envfile.parse_env(text))
    assert pairs == {"A": "1", "B": "two", "C": "three"}


def test_parse_env_strips_matching_quotes():
    pairs = dict(envfile.parse_env('K="v a l"\nJ=\'x\'\nL="mismatch\'\n'))
    assert pairs["K"] == "v a l"
    assert pairs["J"] == "x"
    assert pairs["L"] == '"mismatch\''  # unmatched quotes left intact


def test_parse_env_skips_malformed_lines():
    assert dict(envfile.parse_env("no_equals_here\n=noname\nOK=1\n")) == {"OK": "1"}


def test_load_env_does_not_overwrite_existing(tmp_path):
    env = {"KEEP": "original"}
    p = tmp_path / ".env"
    p.write_text("KEEP=fromfile\nNEW=added\n", encoding="utf-8")
    set_keys = envfile.load_env(str(p), environ=env)
    assert env["KEEP"] == "original"  # real env wins
    assert env["NEW"] == "added"
    assert set_keys == ["NEW"]  # only newly-set keys returned, never values


def test_load_env_missing_file_is_noop(tmp_path):
    assert envfile.load_env(str(tmp_path / "absent.env"), environ={}) == []
