"""Never re-ask a slot the user already filled; honour changes to it.

Audit: the budget was given in the opening message ($400) and asked for again
two turns later; "budget dropped to $700 and Apple is now allowed" produced
the same pick with no acknowledgement.
"""
import os

import pytest

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.agents.clarifier_agent import merge_constraint_updates


def test_budget_from_the_opening_message_is_captured():
    slots = merge_constraint_updates("cordless vacuum for pet hair under $400", {})
    assert slots.get("budget") == "under $400"


def test_a_lowered_budget_replaces_the_old_one():
    slots = merge_constraint_updates("budget dropped to $700", {"budget": "under $1200"})
    assert "700" in slots["budget"]
    assert "1200" not in slots["budget"]


def test_removing_a_brand_exclusion_clears_it():
    slots = merge_constraint_updates("Apple is now allowed",
                                     {"excluded_brands": ["Apple"]})
    assert "Apple" not in slots.get("excluded_brands", [])


def test_unrelated_message_leaves_slots_untouched():
    before = {"budget": "under $400", "category": "vacuum"}
    assert merge_constraint_updates("which one is quietest?", dict(before)) == before


def test_bare_price_mention_never_overwrites_an_existing_budget():
    # Binding validation catch: prices inside follow-up QUESTIONS must not
    # silently replace slots.budget — replacement requires a budget verb.
    before = {"budget": "under $400"}
    after = merge_constraint_updates(
        "does the $300 model come in black?", dict(before))
    assert after["budget"] == "under $400"


def test_bare_price_still_captures_when_no_budget_exists():
    slots = merge_constraint_updates("something around $300 to $400", {})
    assert slots.get("budget")
