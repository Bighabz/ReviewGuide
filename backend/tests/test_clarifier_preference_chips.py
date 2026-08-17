"""DOCTRINE D4 (decided 2026-08-17): preferences are SESSION-scoped.

Outcome 7 — cross-session preference-biased chips ("like last time") — is
REMOVED. This file used to pin the injection; it now pins the inverse
invariant: stored user_preferences never reorder a fresh chat's options and
never tag a question with preference_chip, no matter what they contain.
"""
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

import json  # noqa: E402
from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402

from app.agents.clarifier_agent import ClarifierAgent  # noqa: E402


@pytest.fixture
def agent():
    return ClarifierAgent()


LAPTOP_OPTIONS = ["Student / everyday", "Gaming", "Creative / video editing", "Business / office"]
BUDGET_OPTIONS = ["Under $500", "$500–$800", "$800–$1,200", "$1,200+"]

LAPTOP_LLM_RESPONSE = json.dumps({
    "intro": "Happy to help you find the right laptop.",
    "questions": [
        {
            "slot": "use_case",
            "question": "What will you mainly use it for?",
            "options": LAPTOP_OPTIONS,
            "free_text_hint": "or describe your own use",
        },
        {
            "slot": "budget",
            "question": "What's your budget?",
            "options": BUDGET_OPTIONS,
            "free_text_hint": "or type an amount",
        },
    ],
    "closing": "Then I'll pull together a shortlist.",
})

LAPTOP_ARGS = dict(
    missing_slots=["use_case", "budget"],
    current_slots={"product_name": "laptops"},
    user_message="best laptops",
    intent="product",
)


def _q(result, slot):
    return next(q for q in result["questions"] if q["slot"] == slot)


@pytest.mark.asyncio
async def test_stored_preferences_never_reorder_options(agent):
    """A returning shopper's stored 'Gaming' answer must NOT jump the queue —
    cross-session personalization is scoped out (D4)."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS,
        user_preferences={"use_cases": {"Gaming": 5}, "budget_ranges": ["$500–$800"]},
    )

    assert _q(result, "use_case")["options"] == LAPTOP_OPTIONS
    assert _q(result, "budget")["options"] == BUDGET_OPTIONS


@pytest.mark.asyncio
async def test_no_question_is_ever_tagged_with_preference_chip(agent):
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS,
        user_preferences={
            "use_cases": {"Gaming": 9},
            "budget_ranges": ["Under $500"],
            "features": ["High-end specs"],
        },
    )

    for q in result["questions"]:
        assert "preference_chip" not in q


@pytest.mark.asyncio
async def test_empty_preferences_also_change_nothing(agent):
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS, user_preferences={}
    )

    assert _q(result, "use_case")["options"] == LAPTOP_OPTIONS
    assert all("preference_chip" not in q for q in result["questions"])
