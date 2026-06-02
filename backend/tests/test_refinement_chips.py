"""
Outcome 2 (conversational engine roadmap): post-results refinement chips.

After a product shortlist renders, the user can refine it in one tap:
  "Show cheaper options"  → budget ceiling below the cheapest shown price
  "More premium picks"    → budget floor above the priciest shown price
  "Only <brand>"          → brand slot pinned
  "Different use case"    → re-asks ONLY the use_case question

Covers:
- next_step_suggestion._build_refinement_suggestions (deterministic chips from context)
- next_step_suggestion returns the chips for product intent without an LLM call
- clarifier _detect_refinement_action / _apply_refinement_action helpers
- clarifier execute(): refinement → adjusted slots → proceed_to_execution (no re-asking)
- clarifier execute(): "Different use case" → halts with ONLY the use_case question
- clarifier topic guard: a short NEW-topic query ("best mattress" after laptops)
  must NOT inherit the stale context
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
from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402

from app.agents.clarifier_agent import (  # noqa: E402
    ClarifierAgent,
    _apply_refinement_action,
    _detect_refinement_action,
)
from mcp_server.tools.next_step_suggestion import (  # noqa: E402
    _build_refinement_suggestions,
    next_step_suggestion,
)


HEADPHONES_CONTEXT = {
    "category": "headphones",
    "product_type": "",
    "product_names": ["Sony WH-1000XM5", "Bose QuietComfort 45", "Apple AirPods Max"],
    "budget": "under $200",
    "brand": None,
    "features": "Noise cancelling, Wireless",
    "use_case": "travel",
    "top_prices": {
        "Sony WH-1000XM5": 149.99,
        "Bose QuietComfort 45": 169.00,
        "Apple AirPods Max": 159.00,
    },
    "avg_rating": {},
    "query": "best wireless headphones for travel",
}


# ---------------------------------------------------------------------------
# next_step_suggestion — deterministic refinement chips
# ---------------------------------------------------------------------------

def test_refinement_suggestions_built_from_context():
    state = {"last_search_context": HEADPHONES_CONTEXT}
    chips = _build_refinement_suggestions(state)

    questions = [c["question"] for c in chips]
    assert "Show cheaper options" in questions
    assert "More premium picks" in questions
    assert "Only Sony" in questions, f"brand chip missing: {questions}"
    assert "Different use case" in questions
    # Every chip carries a category for the frontend's RFC §2.4 sort
    assert all(c.get("category") for c in chips)


def test_refinement_suggestions_empty_without_context():
    assert _build_refinement_suggestions({}) == []
    assert _build_refinement_suggestions({"last_search_context": {}}) == []


def test_refinement_brand_chip_skipped_for_non_brand_names():
    """A product name starting with a digit must not produce a brand chip."""
    ctx = dict(HEADPHONES_CONTEXT)
    ctx["product_names"] = ["1MORE SonoFlow"]
    chips = _build_refinement_suggestions({"last_search_context": ctx})
    questions = [c["question"] for c in chips]
    assert not any(q.startswith("Only ") for q in questions)
    # The other chips still render
    assert "Show cheaper options" in questions


@pytest.mark.asyncio
async def test_next_step_suggestion_returns_chips_without_llm_for_product():
    """When product results were just shown, the deterministic chips ARE the
    suggestions — no LLM call is made."""
    state = {
        "intent": "product",
        "user_message": "best wireless headphones for travel",
        "assistant_text": "Here is the shortlist.",
        "slots": {"category": "headphones"},
        "ui_blocks": [],
        "last_search_context": HEADPHONES_CONTEXT,
        "conversation_history": [],
    }

    with patch("mcp_server.tools.next_step_suggestion.model_service") as mock_svc:
        mock_svc.generate = AsyncMock(return_value="{}")
        result = await next_step_suggestion(state)

    assert result["success"] is True
    questions = [s["question"] for s in result["next_suggestions"]]
    assert "Show cheaper options" in questions
    mock_svc.generate.assert_not_called()


@pytest.mark.asyncio
async def test_next_step_suggestion_falls_back_to_llm_without_context():
    """No product context (general/travel/intro or empty search) → existing LLM path."""
    state = {
        "intent": "product",
        "user_message": "best headphones",
        "assistant_text": "Here you go.",
        "slots": {},
        "ui_blocks": [],
        "last_search_context": {},
        "conversation_history": [],
    }
    llm_response = json.dumps({
        "next_suggestions": [
            {"id": "s1", "question": "Want a budget set?", "category": "refine_budget", "confidence": 0.8}
        ]
    })

    with patch("mcp_server.tools.next_step_suggestion.model_service") as mock_svc:
        mock_svc.generate = AsyncMock(return_value=llm_response)
        result = await next_step_suggestion(state)

    assert result["success"] is True
    mock_svc.generate.assert_called_once()
    assert result["next_suggestions"][0]["question"] == "Want a budget set?"


# ---------------------------------------------------------------------------
# Clarifier helpers — detection + slot adjustment
# ---------------------------------------------------------------------------

def test_detect_refinement_action_with_and_without_prefix():
    assert _detect_refinement_action("You chose: Show cheaper options") == "cheaper"
    assert _detect_refinement_action("show cheaper options") == "cheaper"
    assert _detect_refinement_action("You chose: More premium picks") == "premium"
    assert _detect_refinement_action("You chose: Different use case") == "different_use_case"
    assert _detect_refinement_action("You chose: Only Sony") == "brand:sony"
    assert _detect_refinement_action("Only Bose") == "brand:bose"


def test_detect_refinement_action_ignores_normal_messages():
    assert _detect_refinement_action("best laptop under $1000") is None
    assert _detect_refinement_action("You chose: Gaming") is None
    assert _detect_refinement_action("You chose: Noise cancelling, Wireless") is None
    assert _detect_refinement_action("tell me more about the Sony") is None
    assert _detect_refinement_action("") is None


def test_apply_refinement_cheaper_sets_ceiling_below_cheapest_shown():
    slots = {"category": "headphones", "use_case": "travel"}
    adjusted = _apply_refinement_action("cheaper", slots, HEADPHONES_CONTEXT)
    # Cheapest shown = $149.99 → ceiling = 80% of that = $119
    assert adjusted["budget"] == "under $119"
    # Other slots untouched
    assert adjusted["category"] == "headphones"
    assert adjusted["use_case"] == "travel"


def test_apply_refinement_premium_sets_floor_above_priciest_shown():
    slots = {"category": "headphones"}
    adjusted = _apply_refinement_action("premium", slots, HEADPHONES_CONTEXT)
    # Priciest shown = $169 → floor = 120% = $202
    assert adjusted["budget"] == "over $202"


def test_apply_refinement_brand_pins_brand_slot():
    slots = {"category": "headphones", "budget": "under $200"}
    adjusted = _apply_refinement_action("brand:sony", slots, HEADPHONES_CONTEXT)
    assert adjusted["brand"] == "Sony"
    assert adjusted["budget"] == "under $200"  # untouched


def test_apply_refinement_cheaper_without_prices_keeps_slots():
    ctx = dict(HEADPHONES_CONTEXT)
    ctx["top_prices"] = {}
    slots = {"category": "headphones", "budget": "under $200"}
    adjusted = _apply_refinement_action("cheaper", slots, ctx)
    assert adjusted == slots  # no price signal → unchanged (re-run is harmless)


# ---------------------------------------------------------------------------
# Clarifier execute() — end-to-end refinement handling
# ---------------------------------------------------------------------------

@pytest.fixture
def agent():
    return ClarifierAgent()


def _refinement_state(message: str, context: dict = None):
    return {
        "session_id": "test-session",
        "user_message": message,
        "sanitized_text": message,
        "intent": "product",
        "slots": {},
        "plan": {"steps": [{"id": "s1", "tools": ["product_search"]}]},
        "conversation_history": [],
        "last_search_context": context if context is not None else dict(HEADPHONES_CONTEXT),
        "search_history": [],
    }


@pytest.mark.asyncio
async def test_cheaper_chip_proceeds_with_lowered_budget(agent):
    """Tapping 'Show cheaper options' re-runs the search with a lower budget —
    no questions asked."""
    state = _refinement_state("You chose: Show cheaper options")

    with patch("app.agents.clarifier_agent.HaltStateManager.get_halt_state", new=AsyncMock(return_value=None)):
        result = await agent.execute(state)

    assert result["proceed_to_execution"] is True
    assert result["followups"] == []
    assert result["slots"]["budget"] == "under $119"
    # Inherited slots — answered questions are not lost
    assert result["slots"]["category"] == "headphones"
    assert result["slots"]["use_case"] == "travel"


@pytest.mark.asyncio
async def test_brand_chip_proceeds_with_brand_slot(agent):
    state = _refinement_state("You chose: Only Sony")

    with patch("app.agents.clarifier_agent.HaltStateManager.get_halt_state", new=AsyncMock(return_value=None)):
        result = await agent.execute(state)

    assert result["proceed_to_execution"] is True
    assert result["slots"]["brand"] == "Sony"
    assert result["slots"]["category"] == "headphones"


@pytest.mark.asyncio
async def test_premium_chip_proceeds_with_raised_floor(agent):
    state = _refinement_state("More premium picks")  # typed form, no prefix

    with patch("app.agents.clarifier_agent.HaltStateManager.get_halt_state", new=AsyncMock(return_value=None)):
        result = await agent.execute(state)

    assert result["proceed_to_execution"] is True
    assert result["slots"]["budget"] == "over $202"


@pytest.mark.asyncio
async def test_different_use_case_chip_reasks_only_use_case(agent):
    """'Different use case' halts with ONLY the use_case question; budget/features
    stay answered (inherited)."""
    state = _refinement_state("You chose: Different use case")

    followup_response = json.dumps({
        "intro": "Sure — what will you use them for instead?",
        "questions": [{
            "slot": "use_case",
            "question": "Where will you use them most?",
            "options": ["Commute & travel", "Gym & runs", "At a desk", "Studio"],
            "free_text_hint": "or describe your own use",
        }],
        "closing": "I'll rebuild the shortlist around that.",
    })
    agent.generate = AsyncMock(return_value=followup_response)

    with patch("app.agents.clarifier_agent.HaltStateManager.get_halt_state", new=AsyncMock(return_value=None)), \
         patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()) as mock_save:
        result = await agent.execute(state)

    assert result["proceed_to_execution"] is False
    assert result["missing_required_slots"] == ["use_case"]
    assert len(result["followups"]) == 1
    assert result["followups"][0]["slot"] == "use_case"
    # use_case was cleared; everything else stays answered
    assert "use_case" not in result["slots"]
    assert result["slots"]["budget"] == "under $200"
    assert result["slots"]["features"] == "Noise cancelling, Wireless"
    # Halt state saved so the answer resumes correctly
    mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_refinement_ignored_without_search_context(agent):
    """A refinement-looking message with NO previous search context goes through
    the normal clarification flow (nothing to refine)."""
    state = _refinement_state("Show cheaper options", context={})
    # Normal flow: extraction + question generation hit the LLM — mock them
    agent._extract_all_slots_from_conversation = AsyncMock(return_value={})

    with patch("app.agents.clarifier_agent.HaltStateManager.get_halt_state", new=AsyncMock(return_value=None)), \
         patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent.execute(state)

    # No context → not handled as a refinement (proceeds or clarifies via normal path,
    # but never crashes and never inherits phantom slots)
    assert result.get("slots", {}).get("budget") != "under $119"


# ---------------------------------------------------------------------------
# Topic guard — persisted context must not hijack genuinely new queries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_new_category_query_does_not_inherit_stale_context(agent):
    """'best mattress' right after a laptop search is a NEW query — it must not
    skip clarification with inherited laptop slots."""
    laptop_context = {
        "category": "laptops",
        "product_type": "",
        "product_names": ["Dell XPS 13", "MacBook Air M3"],
        "budget": "under $1200",
        "use_case": "student",
        "features": "lightweight",
        "top_prices": {"Dell XPS 13": 999.0},
    }
    state = _refinement_state("best mattress", context=laptop_context)

    captured = {}

    async def fake_handle_new_plan(st, session_id):
        captured["called"] = True
        return {"slots": {}, "followups": [], "missing_required_slots": [], "proceed_to_execution": False}

    agent._handle_new_plan = fake_handle_new_plan

    with patch("app.agents.clarifier_agent.HaltStateManager.get_halt_state", new=AsyncMock(return_value=None)):
        result = await agent.execute(state)

    assert captured.get("called") is True, (
        "A short new-category query must fall through to _handle_new_plan (normal "
        "clarification), not be swallowed by the follow-up/inheritance branch."
    )
    assert result["proceed_to_execution"] is False


@pytest.mark.asyncio
async def test_same_category_short_query_still_inherits(agent):
    """'best laptop' after a laptop search IS a follow-up — inheritance applies."""
    laptop_context = {
        "category": "laptops",
        "product_type": "",
        "product_names": ["Dell XPS 13"],
        "budget": "under $1200",
        "use_case": "student",
        "features": None,
        "top_prices": {"Dell XPS 13": 999.0},
    }
    state = _refinement_state("best laptop", context=laptop_context)

    with patch("app.agents.clarifier_agent.HaltStateManager.get_halt_state", new=AsyncMock(return_value=None)):
        result = await agent.execute(state)

    assert result["proceed_to_execution"] is True
    assert result["slots"]["category"] == "laptops"
    assert result["slots"]["budget"] == "under $1200"


@pytest.mark.asyncio
async def test_anaphoric_follow_up_still_works(agent):
    """'cheapest one' (reference signal) keeps the existing follow-up behavior."""
    state = _refinement_state("cheapest one")

    with patch("app.agents.clarifier_agent.HaltStateManager.get_halt_state", new=AsyncMock(return_value=None)):
        result = await agent.execute(state)

    assert result["proceed_to_execution"] is True
    assert result["slots"]["category"] == "headphones"


# ---------------------------------------------------------------------------
# QA Round 4 — F0: pending questions take priority over follow-up shortcuts
# ---------------------------------------------------------------------------
# When the previous turn asked clarifier questions, the user's next message IS
# the answer. It must reach _handle_user_answer even when last_search_context
# exists (2nd+ search in a session) and the message is short enough to look
# like a "follow-up query" to the inheritance shortcut.

MATTRESS_PENDING_HALT_STATE = {
    "intent": "product",
    "slots": {},
    "followups": [
        {"slot": "use_case", "question": "How do you usually sleep?",
         "options": ["Side sleeper", "Back sleeper", "Stomach sleeper", "It varies"]},
        {"slot": "features", "question": "How firm do you like your mattress?",
         "options": ["Soft", "Medium", "Firm"]},
        {"slot": "budget", "question": "What's your budget for a mattress?",
         "options": ["Under $500", "$500–$1,000", "$1,000–$2,000", "$2,000+"]},
    ],
    "missing_required_slots": ["use_case", "features", "budget"],
    "plan": {"steps": [{"id": "s1", "tools": ["product_search"]}]},
    "tools_by_required_slot": {},
}

MATTRESS_CONTEXT = {
    "category": "mattress",
    "product_type": "mattress",
    "product_names": ["Nectar Sleep Premier", "Casper Original", "DreamCloud Luxury"],
    "budget": "under $1500",
    "brand": None,
    "features": "memory foam",
    "use_case": "side sleeper",
    "top_prices": {"Nectar Sleep Premier": 899.0},
    "avg_rating": {},
    "query": "best mattress",
}


@pytest.mark.asyncio
async def test_chip_answer_with_pending_questions_goes_to_extraction(agent):
    """F0 regression: 'You chose: Side sleeper' while 3 questions are pending must be
    treated as an ANSWER (extraction + re-ask remaining), never as a follow-up query
    that skips clarification — even with same-category search context present."""
    state = _refinement_state("You chose: Side sleeper", context=dict(MATTRESS_CONTEXT))

    captured = {}

    async def fake_handle_user_answer(st, halt_state, session_id):
        captured["called"] = True
        captured["halt_state"] = halt_state
        return {
            "slots": {"use_case": "Side sleeper"},
            "followups": MATTRESS_PENDING_HALT_STATE["followups"][1:],
            "missing_required_slots": ["features", "budget"],
            "proceed_to_execution": False,
        }

    agent._handle_user_answer = fake_handle_user_answer

    with patch(
        "app.agents.clarifier_agent.HaltStateManager.get_halt_state",
        new=AsyncMock(return_value=dict(MATTRESS_PENDING_HALT_STATE)),
    ):
        result = await agent.execute(state)

    assert captured.get("called") is True, (
        "A chip answer with pending followups must go to _handle_user_answer — the "
        "follow-up/inheritance shortcut hijacked it (QA Round 4 F0)."
    )
    assert result["proceed_to_execution"] is False
    assert result["missing_required_slots"] == ["features", "budget"]


@pytest.mark.asyncio
async def test_budget_chip_answer_with_pending_questions_not_hijacked(agent):
    """F0 regression: budget chips ('You chose: $100–$250' — 3 tokens) are also short
    enough for the follow-up rule; with pending questions they must go to extraction."""
    state = _refinement_state("You chose: $500–$1,000", context=dict(MATTRESS_CONTEXT))

    captured = {}

    async def fake_handle_user_answer(st, halt_state, session_id):
        captured["called"] = True
        return {
            "slots": {"budget": "$500–$1,000"},
            "followups": [],
            "missing_required_slots": [],
            "proceed_to_execution": True,
        }

    agent._handle_user_answer = fake_handle_user_answer

    with patch(
        "app.agents.clarifier_agent.HaltStateManager.get_halt_state",
        new=AsyncMock(return_value=dict(MATTRESS_PENDING_HALT_STATE)),
    ):
        result = await agent.execute(state)

    assert captured.get("called") is True
    assert result["proceed_to_execution"] is True
    assert result["slots"]["budget"] == "$500–$1,000"


@pytest.mark.asyncio
async def test_refinement_chip_with_no_pending_questions_still_refines(agent):
    """Refinement chips arrive AFTER results (no pending questions) — the refinement
    path must still work when the halt state is context-only (followups: [])."""
    state = _refinement_state("You chose: Show cheaper options")

    context_only_halt_state = {
        "intent": "product",
        "slots": {},
        "followups": [],  # context-only halt state (saved after a completed search)
        "plan": None,
    }

    with patch(
        "app.agents.clarifier_agent.HaltStateManager.get_halt_state",
        new=AsyncMock(return_value=context_only_halt_state),
    ):
        result = await agent.execute(state)

    assert result["proceed_to_execution"] is True
    assert result["followups"] == []
    assert result["slots"]["budget"] == "under $119"


@pytest.mark.asyncio
async def test_intro_intent_still_skips_before_halt_state(agent):
    """Intro/unclear intents skip the clarifier entirely — even with pending questions."""
    state = _refinement_state("hi", context={})
    state["intent"] = "intro"

    halt_lookup = AsyncMock(return_value=dict(MATTRESS_PENDING_HALT_STATE))
    with patch("app.agents.clarifier_agent.HaltStateManager.get_halt_state", new=halt_lookup):
        result = await agent.execute(state)

    assert result["proceed_to_execution"] is True
    halt_lookup.assert_not_called()
