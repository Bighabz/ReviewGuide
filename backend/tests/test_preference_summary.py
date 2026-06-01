"""
B-phase 3: _preference_summary derives a small list of interest keywords (top
categories/brands/use-cases) from accumulated user preferences for biasing the
chat starter. Keys only (no counts), deduped, capped, empty on no data.
"""
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.api.v1.chat import _preference_summary  # noqa: E402


def test_empty_or_none_returns_empty():
    assert _preference_summary(None) == []
    assert _preference_summary({}) == []
    assert _preference_summary("nope") == []


def test_top_categories_brands_usecases_by_count():
    prefs = {
        "categories": {"audio": 5, "travel": 2, "kitchen": 1, "fitness": 1},
        "brands": {"sony": 3, "bose": 1},
        "use_cases": {"gym": 2},
    }
    out = _preference_summary(prefs)
    # categories top-3 by count, then brands, then use_cases
    assert out[:3] == ["audio", "travel", "kitchen"]
    assert "sony" in out and "gym" in out
    # keys only — no counts leak
    assert all(isinstance(t, str) for t in out)
    assert len(out) <= 6


def test_dedupes_case_insensitively():
    prefs = {"categories": {"Audio": 2}, "brands": {"audio": 1}}
    out = _preference_summary(prefs)
    assert sum(1 for t in out if t.lower() == "audio") == 1


def test_ignores_non_dict_buckets():
    assert _preference_summary({"categories": ["audio"], "budget_ranges": ["under $100"]}) == []
