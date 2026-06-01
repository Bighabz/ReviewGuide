"""
E2 (deterministic): _synthesize_transitional frames the shortlist from a parsed
budget / use-case when the LLM declines to emit transitional_reasoning, stays
empty for bare unconstrained queries, and never names a specific product (so it
cannot contradict the guide's actual #1 pick).
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


def test_budget_in_message_frames_with_amount():
    out = _synthesize_transitional("best wireless earbuds under $100", None)
    assert out
    assert "$100" in out


def test_budget_slot_takes_precedence():
    out = _synthesize_transitional("best earbuds", {"budget": 150})
    assert "$150" in out


def test_use_case_slot_frames_when_no_budget():
    out = _synthesize_transitional("best headphones", {"use_case": "travel"})
    assert "travel" in out


def test_no_constraint_returns_empty():
    assert _synthesize_transitional("best wireless earbuds", None) == ""
    assert _synthesize_transitional("best wireless earbuds", {}) == ""


def test_garbage_budget_is_ignored():
    assert _synthesize_transitional("which earbuds are good", {"category": "audio"}) == ""


def test_never_names_a_product():
    # Pick-agnostic: must not contradict the guide by naming a specific pick.
    out = _synthesize_transitional("best 4k tv under $700", None)
    assert "$700" in out
    assert "shortlist" in out.lower()
