"""
Outcome 4 (conversational engine roadmap): category question packs.

The top ~20 categories each have a curated specialist question set that the
clarifier injects into its question-generation prompt as the authoritative
example. Unlisted categories keep the generic expert framing.

Covers:
- pack schema integrity for all 20 categories
- get_category_pack matching: exact, plural/singular, aliases, compound
  categories, and no-match
- format_pack_hint rendering (questions, options, multi-select flag, brackets)
- clarifier prompt injection: pack categories get the curated set; unlisted
  categories don't
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

from app.agents.category_question_packs import (  # noqa: E402
    CATEGORY_QUESTION_PACKS,
    format_pack_hint,
    get_category_pack,
)
from app.agents.clarifier_agent import ClarifierAgent  # noqa: E402


EXPECTED_CATEGORIES = [
    "laptops", "phones", "tvs", "headphones", "mattresses", "bikes", "monitors",
    "coffee machines", "vacuums", "air purifiers", "strollers", "watches",
    "cameras", "keyboards", "desks", "chairs", "grills", "luggage",
    "running shoes", "tablets",
]


# ---------------------------------------------------------------------------
# Pack data integrity
# ---------------------------------------------------------------------------

def test_all_twenty_categories_have_packs():
    assert sorted(CATEGORY_QUESTION_PACKS.keys()) == sorted(EXPECTED_CATEGORIES)
    assert len(CATEGORY_QUESTION_PACKS) == 20


@pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
def test_pack_schema(category):
    """Every pack has a lead question, a differentiator, and realistic brackets."""
    pack = CATEGORY_QUESTION_PACKS[category]
    # use_case: question + 3-5 options
    assert pack["use_case"]["question"].endswith("?")
    assert 3 <= len(pack["use_case"]["options"]) <= 5
    # features: question + options + explicit multi_select flag,
    # with a "No strong preference"-style escape hatch
    assert pack["features"]["question"].endswith("?")
    assert 3 <= len(pack["features"]["options"]) <= 5
    assert isinstance(pack["features"]["multi_select"], bool)
    assert any(
        "no strong preference" in o.lower() or "not sure" in o.lower() or "it varies" in o.lower()
        for o in pack["features"]["options"]
    ), f"{category} features question needs an escape-hatch option"
    # budget: exactly 4 brackets, all carrying $ amounts
    assert len(pack["budget_brackets"]) == 4
    assert all("$" in b for b in pack["budget_brackets"])
    # aliases exist
    assert pack["aliases"], f"{category} pack needs aliases"


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def test_exact_and_plural_matching():
    assert get_category_pack("laptops") is CATEGORY_QUESTION_PACKS["laptops"]
    assert get_category_pack("laptop") is CATEGORY_QUESTION_PACKS["laptops"]
    assert get_category_pack("Mattress") is CATEGORY_QUESTION_PACKS["mattresses"]
    assert get_category_pack("TVs") is CATEGORY_QUESTION_PACKS["tvs"]
    assert get_category_pack("TV") is CATEGORY_QUESTION_PACKS["tvs"]


def test_alias_matching():
    assert get_category_pack("earbuds") is CATEGORY_QUESTION_PACKS["headphones"]
    assert get_category_pack("smartphone") is CATEGORY_QUESTION_PACKS["phones"]
    assert get_category_pack("iPhone") is CATEGORY_QUESTION_PACKS["phones"]
    assert get_category_pack("suitcase") is CATEGORY_QUESTION_PACKS["luggage"]
    assert get_category_pack("sneakers") is CATEGORY_QUESTION_PACKS["running shoes"]
    assert get_category_pack("office chair") is CATEGORY_QUESTION_PACKS["chairs"]
    assert get_category_pack("espresso machine") is CATEGORY_QUESTION_PACKS["coffee machines"]
    assert get_category_pack("e-bike") is CATEGORY_QUESTION_PACKS["bikes"]
    assert get_category_pack("iPad") is CATEGORY_QUESTION_PACKS["tablets"]
    assert get_category_pack("BBQ") is CATEGORY_QUESTION_PACKS["grills"]


def test_compound_category_matching():
    """Compound categories like 'gaming laptop' must still find their pack."""
    assert get_category_pack("gaming laptop") is CATEGORY_QUESTION_PACKS["laptops"]
    assert get_category_pack("noise cancelling headphones") is CATEGORY_QUESTION_PACKS["headphones"]
    assert get_category_pack("4k smart tv") is CATEGORY_QUESTION_PACKS["tvs"]
    assert get_category_pack("standing desk") is CATEGORY_QUESTION_PACKS["desks"]


def test_no_match_returns_none():
    assert get_category_pack("kayak") is None
    assert get_category_pack("blender") is None
    assert get_category_pack("") is None
    assert get_category_pack(None) is None
    assert get_category_pack(123) is None


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------

def test_format_pack_hint_renders_questions_and_flags():
    hint = format_pack_hint(CATEGORY_QUESTION_PACKS["headphones"])
    assert "Where will you use them most?" in hint
    assert "Noise cancelling" in hint
    assert '"type": "multi_select"' in hint  # headphones features are multi-select
    assert "Under $100" in hint and "$400+" in hint
    assert "CURATED QUESTION SET" in hint


def test_format_pack_hint_single_select_category():
    hint = format_pack_hint(CATEGORY_QUESTION_PACKS["mattresses"])
    assert "How do you usually sleep?" in hint
    assert '"type": "single_select"' in hint  # firmness is single-answer
    assert "$2,000+" in hint


# ---------------------------------------------------------------------------
# Clarifier integration — pack injection into the question-generation prompt
# ---------------------------------------------------------------------------

LLM_RESPONSE = json.dumps({
    "intro": "ok",
    "questions": [
        {"slot": "use_case", "question": "q?", "options": ["a", "b", "c"]},
        {"slot": "features", "question": "q?", "options": ["a", "b", "c"]},
        {"slot": "budget", "question": "q?", "options": ["$1", "$2", "$3"]},
    ],
    "closing": "",
})


@pytest.fixture
def agent():
    return ClarifierAgent()


@pytest.mark.asyncio
async def test_pack_category_injects_curated_set(agent):
    """A pack category's prompt carries the curated questions verbatim."""
    agent.generate = AsyncMock(return_value=LLM_RESPONSE)

    await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"category": "mattresses"},
        user_message="best mattress",
        intent="product",
    )

    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "CURATED QUESTION SET" in system_prompt
    assert "How do you usually sleep?" in system_prompt
    assert "$1,000–$2,000" in system_prompt


@pytest.mark.asyncio
async def test_pack_matches_via_alias_in_clarifier(agent):
    """Category arrives as an alias ('earbuds') — the headphones pack is used."""
    agent.generate = AsyncMock(return_value=LLM_RESPONSE)

    await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"category": "earbuds"},
        user_message="best earbuds",
        intent="product",
    )

    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "CURATED QUESTION SET" in system_prompt
    assert "Where will you use them most?" in system_prompt


@pytest.mark.asyncio
async def test_unlisted_category_keeps_generic_framing(agent):
    """A category without a pack ('kayak') gets the generic expert prompt only."""
    agent.generate = AsyncMock(return_value=LLM_RESPONSE)

    await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"category": "kayak"},
        user_message="best kayak",
        intent="product",
    )

    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "CURATED QUESTION SET" not in system_prompt
    # Generic expert framing still present
    assert "kayak specialist" in system_prompt


@pytest.mark.asyncio
async def test_travel_intent_never_gets_packs(agent):
    """Packs are a product-intent concept — travel prompts are untouched."""
    agent.generate = AsyncMock(return_value=LLM_RESPONSE)

    await agent._generate_followup_questions(
        missing_slots=["destination"],
        current_slots={"category": "laptops"},  # even with a matching category present
        user_message="plan a trip",
        intent="travel",
    )

    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "CURATED QUESTION SET" not in system_prompt
