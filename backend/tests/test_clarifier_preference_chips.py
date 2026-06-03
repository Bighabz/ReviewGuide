"""Outcome 7 — preference-biased clarifier chips ("like last time").

product_compose stores the user's answers after every completed search
(PR #76, preference_service). When the clarifier generates questions for a
returning user, a stored past answer that is ALREADY one of a question's
options moves to the front and the question is tagged with preference_chip
so the frontend renders "(like last time)" on it.

Safety property: preferences are global (not per category), so option
membership is the gate — a mattress answer can never surface on a laptop
question because it isn't one of the laptop options.
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


# The LLM's (pack-conformant) laptop questions — what production generates for
# "best laptops" before preference biasing runs.
LAPTOP_LLM_RESPONSE = json.dumps({
    "intro": "Happy to help you find the right laptop.",
    "questions": [
        {
            "slot": "use_case",
            "question": "What will you mainly use it for?",
            "options": ["Student / everyday", "Gaming", "Creative / video editing", "Business / office"],
            "free_text_hint": "or describe your own use",
        },
        {
            "slot": "features",
            "question": "What performance level do you need?",
            "options": ["Just the basics", "Mid-range power", "High-end specs", "No strong preference"],
            "free_text_hint": "or describe what you need",
        },
        {
            "slot": "budget",
            "question": "What's your budget?",
            "options": ["Under $500", "$500–$800", "$800–$1,200", "$1,200+"],
            "free_text_hint": "or type an amount",
        },
    ],
    "closing": "Then I'll pull together a shortlist.",
})

LAPTOP_ARGS = dict(
    missing_slots=["use_case", "features", "budget"],
    current_slots={"product_name": "laptops"},
    user_message="best laptops",
    intent="product",
)


def _q(result, slot):
    return next(q for q in result["questions"] if q["slot"] == slot)


# ---------------------------------------------------------------------------
# The headline behavior
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stored_use_case_moves_to_front_with_preference_chip(agent):
    """A returning laptop shopper who answered 'Gaming' before sees Gaming as
    the FIRST chip, tagged as their past answer."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS,
        user_preferences={"use_cases": {"Gaming": 2}},
    )

    uc = _q(result, "use_case")
    assert uc["options"][0] == "Gaming"
    assert uc["preference_chip"] == "Gaming"
    # All original options still present, just reordered
    assert sorted(uc["options"]) == sorted(
        ["Student / everyday", "Gaming", "Creative / video editing", "Business / office"]
    )


@pytest.mark.asyncio
async def test_stored_budget_bracket_moves_to_front(agent):
    """budget_ranges are stored newest-first — the most recent matching bracket
    leads the budget options."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS,
        user_preferences={"budget_ranges": ["$500–$800", "Under $100"]},
    )

    bq = _q(result, "budget")
    assert bq["options"][0] == "$500–$800"
    assert bq["preference_chip"] == "$500–$800"


@pytest.mark.asyncio
async def test_most_used_use_case_wins(agent):
    """Counts decide: the use case answered most often leads."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS,
        user_preferences={"use_cases": {"Business / office": 1, "Gaming": 5}},
    )

    uc = _q(result, "use_case")
    assert uc["options"][0] == "Gaming"
    assert uc["preference_chip"] == "Gaming"


@pytest.mark.asyncio
async def test_features_preference_biasing(agent):
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS,
        user_preferences={"features": ["High-end specs"]},
    )

    ft = _q(result, "features")
    assert ft["options"][0] == "High-end specs"
    assert ft["preference_chip"] == "High-end specs"


# ---------------------------------------------------------------------------
# Safety: cross-category answers never leak
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_category_preference_never_leaks(agent):
    """A stored mattress answer ('Side sleeper') is not a laptop option — the
    laptop questions must be completely untouched."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS,
        user_preferences={
            "use_cases": {"Side sleeper": 4},          # from a mattress search
            "budget_ranges": ["$1,000–$2,000"],        # mattress brackets ≠ laptop brackets
            "features": ["Firm"],
        },
    )

    uc = _q(result, "use_case")
    assert uc["options"][0] == "Student / everyday", "laptop options must stay in pack order"
    assert "preference_chip" not in uc
    assert "Side sleeper" not in uc["options"]

    bq = _q(result, "budget")
    assert "preference_chip" not in bq
    assert "$1,000–$2,000" not in bq["options"]


@pytest.mark.asyncio
async def test_no_preferences_changes_nothing(agent):
    """First-time users (no stored preferences): byte-identical behavior."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    baseline = await agent._generate_followup_questions(**LAPTOP_ARGS)

    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)
    with_empty = await agent._generate_followup_questions(
        **LAPTOP_ARGS, user_preferences={}
    )

    assert baseline == with_empty
    for q in with_empty["questions"]:
        assert "preference_chip" not in q


@pytest.mark.asyncio
async def test_preference_biasing_works_with_pack_enforcement(agent):
    """Pack enforcement replaces sloppy LLM options with the pack's; preference
    biasing then reorders the ENFORCED options. Both must compose correctly."""
    sloppy = json.dumps({
        "intro": "Let me help with laptops.",
        "questions": [
            {"slot": "use_case", "question": "What will you mainly use it for?",
             "options": ["School", "Play"], "free_text_hint": "..."},
            {"slot": "features", "question": "What performance level do you need?",
             "options": ["Fast"], "free_text_hint": "..."},
            {"slot": "budget", "question": "What's your budget?",
             "options": ["$10"], "free_text_hint": "..."},
        ],
        "closing": "ok",
    })
    agent.generate = AsyncMock(return_value=sloppy)

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS,
        user_preferences={"use_cases": {"Gaming": 3}},
    )

    uc = _q(result, "use_case")
    # Pack options enforced AND Gaming (a pack option) moved to front
    assert uc["options"][0] == "Gaming"
    assert set(uc["options"]) == {
        "Student / everyday", "Gaming", "Creative / video editing", "Business / office"
    }
    assert uc["preference_chip"] == "Gaming"


@pytest.mark.asyncio
async def test_questions_without_options_are_skipped(agent):
    """LLM-failure fallback questions carry no options — preference biasing must
    not crash on or alter them."""
    agent.generate = AsyncMock(side_effect=RuntimeError("API down"))

    result = await agent._generate_followup_questions(
        **LAPTOP_ARGS,
        user_preferences={"use_cases": {"Gaming": 2}},
    )

    # Fallback stubs, no options, no preference_chip, no crash
    for q in result["questions"]:
        assert "options" not in q or not q.get("options")
        assert "preference_chip" not in q
