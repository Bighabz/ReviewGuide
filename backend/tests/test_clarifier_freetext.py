"""Free-text answers must fill the slot the clarifier is waiting on.

Audit: asked for a departure city three times after being told "Manchester, UK"
twice. The typed answer was never mapped onto the open slot.
"""
import os

import pytest

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.agents.clarifier_agent import capture_freetext_answer

FOLLOWUPS = [{"slot": "departure_city", "question": "Which city are you flying from?"}]


@pytest.mark.parametrize("message,expected", [
    ("Manchester, UK", "Manchester, UK"),
    ("manchester uk", "manchester uk"),
    ("I'm flying from Manchester", "Manchester"),
    ("From Manchester, UK", "Manchester, UK"),
    ("Manchester", "Manchester"),
])
def test_captures_a_typed_city_answer(message, expected):
    assert capture_freetext_answer(message, "departure_city", FOLLOWUPS) == expected


@pytest.mark.parametrize("message", [
    "Just show me the best overall",
    "Ask me a few more questions",
])
def test_control_phrases_are_not_slot_answers(message):
    # These are backend contracts handled by _is_skip_all / _is_ask_more.
    assert capture_freetext_answer(message, "departure_city", FOLLOWUPS) is None


def test_a_question_is_not_a_slot_answer():
    assert capture_freetext_answer(
        "which reviews support your pick?", "departure_city", FOLLOWUPS) is None


def test_empty_message_is_not_an_answer():
    assert capture_freetext_answer("   ", "departure_city", FOLLOWUPS) is None


def test_closed_slot_is_not_captured():
    assert capture_freetext_answer("Manchester", "budget", FOLLOWUPS) is None
