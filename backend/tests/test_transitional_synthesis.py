"""
E2 (deterministic): _synthesize_transitional frames the pick from a parsed
budget / use-case when the LLM declines to emit transitional_reasoning, and
stays empty for bare unconstrained queries.
"""
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from mcp_server.tools.product_compose import _synthesize_transitional  # noqa: E402


def test_budget_in_message_frames_with_top_pick():
    out = _synthesize_transitional("best wireless earbuds under $100", None, "Sony WF-C700N")
    assert out
    assert "$100" in out
    assert "Sony WF-C700N" in out


def test_budget_slot_takes_precedence():
    out = _synthesize_transitional("best earbuds", {"budget": 150}, "Anker P3")
    assert "$150" in out and "Anker P3" in out


def test_budget_without_a_pick_still_frames():
    out = _synthesize_transitional("best 4k tv under $700", None, "")
    assert "$700" in out
    assert "value picks lead" in out


def test_use_case_slot_frames_when_no_budget():
    out = _synthesize_transitional("best headphones", {"use_case": "travel"}, "Bose QC Ultra")
    assert "travel" in out and "Bose QC Ultra" in out


def test_no_constraint_returns_empty():
    assert _synthesize_transitional("best wireless earbuds", None, "Sony") == ""
    assert _synthesize_transitional("best wireless earbuds", {}, "Sony") == ""


def test_garbage_budget_is_ignored():
    # No parseable budget and no use-case → empty (no false positive).
    assert _synthesize_transitional("which earbuds are good", {"category": "audio"}, "Sony") == ""
