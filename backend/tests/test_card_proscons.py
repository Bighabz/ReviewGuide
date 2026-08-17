"""PLAN-3 v2 — grounded pros/cons from the consolidated composer call.

The old evidence path was dead (parallel with its producer) and fabricated
quotes when alive. Pros/cons now ride the consolidated schema, grounded on the
review_data the call already receives."""
import os

import pytest

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from mcp_server.tools.product_compose import (
    _BLOG_SCHEMA_TAIL,
    _CONSOLIDATED_SCHEMA_TAIL,
    _CONSOLIDATED_EXTRA_RULES,
    _consolidated_blog_role,
)


def test_consolidated_schema_declares_pros_cons():
    assert '"pros_cons"' in _CONSOLIDATED_SCHEMA_TAIL


def test_rules_ground_pros_cons_and_forbid_invention():
    lowered = _CONSOLIDATED_EXTRA_RULES.lower()
    assert "pros_cons" in lowered
    assert "review" in lowered           # grounded on review signal
    assert "empty" in lowered            # no grounding -> empty lists
    assert "never" in lowered            # never invent / never quote


def test_transform_still_replaces_the_tail():
    # The extension edits the tail the transform swaps in — the swap must
    # still fire (guards against breaking the .replace anchor).
    fake_role = "ROLE HEAD\n" + _BLOG_SCHEMA_TAIL
    out = _consolidated_blog_role(fake_role)
    assert '"pros_cons"' in out
    assert out.endswith(_CONSOLIDATED_EXTRA_RULES)
