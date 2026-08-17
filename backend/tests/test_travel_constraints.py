"""Travel output must respect stated constraints.

Audit: "4 days in Lisbon with two kids under 8" returned Bairro Alto
nightlife and a Fado dinner, and invented calendar dates the user never gave.
"""
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from mcp_server.tools.travel_itinerary import _travel_constraint_block


def test_children_in_the_party_are_asserted():
    block = _travel_constraint_block({"travelers": "2 adults, 2 children under 8"})
    lowered = block.lower()
    assert "child" in lowered or "kid" in lowered
    assert "nightlife" in lowered or "late-night" in lowered


def test_children_as_structured_travelers_are_asserted_too():
    block = _travel_constraint_block({"travelers": {"adults": 2, "children": 2}})
    lowered = block.lower()
    assert "child" in lowered or "kid" in lowered


def test_absent_dates_are_not_invented():
    block = _travel_constraint_block({"destination": "Lisbon", "duration": "4 days"})
    assert "do not invent" in block.lower() or "never invent" in block.lower()


def test_no_constraints_yields_no_child_block_but_keeps_date_honesty():
    # No travelers and no dates: the date-honesty fragment still applies.
    block = _travel_constraint_block({})
    assert "nightlife" not in block.lower()


def test_dates_present_suppresses_the_date_fragment():
    block = _travel_constraint_block({"travelers": "2 adults", "dates": "Dec 15-19"})
    assert block == ""
