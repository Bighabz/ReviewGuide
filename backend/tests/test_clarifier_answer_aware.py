"""Outcome 6 PROTOTYPE — answer-aware follow-ups (USE_ANSWER_AWARE_FOLLOWUPS).

Flag-gated sequential clarification: the clarifier asks use_case ALONE first;
once answered, the remaining questions are generated WITH that answer known, so
the features question adapts to it via the packs' features_by_use_case branches
("Gaming" → "What kind of gaming?").

COST: one extra conversation turn. The flag defaults OFF and these tests pin
both sides: flag-off behavior is byte-identical to the single-card flow, and
flag-on produces the sequential adapted flow.
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

from app.agents.category_question_packs import (  # noqa: E402
    CATEGORY_QUESTION_PACKS,
    format_pack_hint,
    get_features_spec,
)
from app.agents.clarifier_agent import ClarifierAgent  # noqa: E402


@pytest.fixture
def agent():
    return ClarifierAgent()


# ---------------------------------------------------------------------------
# Pack branches + helpers
# ---------------------------------------------------------------------------

def test_laptops_pack_has_branch_per_use_case_option():
    """Every laptop use_case option has an adapted features branch, and every
    branch ends with the 'No strong preference' escape hatch."""
    pack = CATEGORY_QUESTION_PACKS["laptops"]
    branches = pack["features_by_use_case"]
    assert set(branches.keys()) == set(pack["use_case"]["options"])
    for spec in branches.values():
        assert spec["options"][-1] == "No strong preference"
        assert spec["question"] != pack["features"]["question"], "branch must actually differ"


def test_headphones_pack_branches_keep_multi_select():
    """Headphones features are multi-select; the branches must stay multi-select."""
    pack = CATEGORY_QUESTION_PACKS["headphones"]
    for spec in pack["features_by_use_case"].values():
        assert spec.get("multi_select") is True


def test_get_features_spec_returns_branch_on_match():
    pack = CATEGORY_QUESTION_PACKS["laptops"]
    spec = get_features_spec(pack, "Gaming")
    assert spec["question"] == "What kind of gaming?"
    # Case-insensitive fallback
    spec2 = get_features_spec(pack, "gaming")
    assert spec2["question"] == "What kind of gaming?"


def test_get_features_spec_falls_back_to_default():
    pack = CATEGORY_QUESTION_PACKS["laptops"]
    # No answer / unknown answer / pack without branches → default features
    assert get_features_spec(pack, None) is pack["features"]
    assert get_features_spec(pack, "Underwater basket weaving") is pack["features"]
    no_branch_pack = CATEGORY_QUESTION_PACKS["tvs"]
    assert get_features_spec(no_branch_pack, "Gaming") is no_branch_pack["features"]


def test_format_pack_hint_uses_branch_when_answer_known():
    pack = CATEGORY_QUESTION_PACKS["laptops"]
    hint_default = format_pack_hint(pack)
    hint_gaming = format_pack_hint(pack, use_case_answer="Gaming")
    assert "What performance level do you need?" in hint_default
    assert "What kind of gaming?" in hint_gaming
    assert "What performance level do you need?" not in hint_gaming
    # use_case and budget sections are identical either way
    assert "What will you mainly use it for?" in hint_gaming
    assert "$1,200+" in hint_gaming


# ---------------------------------------------------------------------------
# Question generation: features question adapts when use_case is known
# ---------------------------------------------------------------------------

GAMING_FEATURES_LLM_RESPONSE = json.dumps({
    "intro": "Got it — gaming laptop it is.",
    "questions": [
        {
            "slot": "features",
            "question": "What kind of gaming?",
            "options": ["AAA / new releases", "Esports / competitive", "Casual & indie", "No strong preference"],
            "free_text_hint": "or describe it",
        },
        {
            "slot": "budget",
            "question": "What's your budget?",
            "options": ["Under $500", "$500–$800", "$800–$1,200", "$1,200+"],
            "free_text_hint": "or type an amount",
        },
    ],
    "closing": "Then I'll find the right machines.",
})


@pytest.mark.asyncio
async def test_features_question_adapts_to_known_use_case(agent):
    """When use_case is already in current_slots, the enforced features question
    comes from the matching branch — even if the LLM returned the generic one."""
    generic_response = json.dumps({
        "intro": "ok",
        "questions": [
            {"slot": "features", "question": "What performance level do you need?",
             "options": ["Just the basics", "Mid-range power"], "free_text_hint": "x"},
            {"slot": "budget", "question": "What's your budget?",
             "options": ["Under $500"], "free_text_hint": "y"},
        ],
        "closing": "",
    })
    agent.generate = AsyncMock(return_value=generic_response)

    result = await agent._generate_followup_questions(
        missing_slots=["features", "budget"],
        current_slots={"product_name": "laptops", "use_case": "Gaming"},
        user_message="best laptops",
        intent="product",
    )

    ft = next(q for q in result["questions"] if q["slot"] == "features")
    assert ft["question"] == "What kind of gaming?"
    assert ft["options"] == ["AAA / new releases", "Esports / competitive", "Casual & indie", "No strong preference"]


@pytest.mark.asyncio
async def test_features_question_unchanged_without_use_case(agent):
    """No use_case known → default pack features question/options (pre-Outcome-6
    behavior, byte-identical)."""
    generic_response = json.dumps({
        "intro": "ok",
        "questions": [
            {"slot": "use_case", "question": "What will you mainly use it for?",
             "options": ["School"], "free_text_hint": "x"},
            {"slot": "features", "question": "My own phrasing of the performance question?",
             "options": ["Fast", "Slow"], "free_text_hint": "x"},
            {"slot": "budget", "question": "What's your budget?",
             "options": ["Under $500"], "free_text_hint": "y"},
        ],
        "closing": "",
    })
    agent.generate = AsyncMock(return_value=generic_response)

    result = await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"product_name": "laptops"},
        user_message="best laptops",
        intent="product",
    )

    ft = next(q for q in result["questions"] if q["slot"] == "features")
    # Options enforced from the DEFAULT spec; the LLM's question text is kept
    # (no branch in play → no text override)
    assert ft["options"] == ["Just the basics", "Mid-range power", "High-end specs", "No strong preference"]
    assert ft["question"] == "My own phrasing of the performance question?"


# ---------------------------------------------------------------------------
# Sequential flow: _handle_new_plan asks use_case alone (flag on)
# ---------------------------------------------------------------------------

def _new_plan_state(message="best laptops"):
    return {
        "user_message": message,
        "sanitized_text": message,
        "intent": "product",
        "slots": {},
        "session_id": "test-session",
        "conversation_history": [{"role": "user", "content": message}],
        "last_search_context": {},
        "plan": {
            "steps": [
                {"id": "step_1", "tools": ["product_search"], "parallel": False},
            ]
        },
        "metadata": {},
    }


@pytest.mark.asyncio
async def test_flag_on_asks_use_case_alone_first(agent, monkeypatch):
    monkeypatch.setattr(agent.settings, "USE_ANSWER_AWARE_FOLLOWUPS", True)

    captured = {}

    async def fake_generate_followups(missing_slots, current_slots, user_message, intent, conversation_history=None, user_preferences=None):
        captured["asked"] = list(missing_slots)
        return {
            "intro": "x",
            "questions": [{"slot": s, "question": f"{s}?"} for s in missing_slots],
            "closing": "",
        }

    saved_halt_state = {}

    async def fake_update_halt(session_id, data):
        saved_halt_state.update(data)

    agent._extract_all_slots_from_conversation = AsyncMock(return_value={})
    agent._generate_followup_questions = fake_generate_followups

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=fake_update_halt):
        result = await agent._handle_new_plan(_new_plan_state(), "test-session")

    # Only use_case asked in the first card...
    assert captured["asked"] == ["use_case"]
    assert [q["slot"] for q in result["followups"]] == ["use_case"]
    # ...but the halt state remembers the FULL plan so the rest gets asked next turn
    assert set(saved_halt_state["missing_required_slots"]) >= {"use_case", "budget"}
    assert result["proceed_to_execution"] is False


@pytest.mark.asyncio
async def test_flag_off_asks_everything_at_once(agent, monkeypatch):
    """Flag off (the default): the single-card flow is untouched."""
    monkeypatch.setattr(agent.settings, "USE_ANSWER_AWARE_FOLLOWUPS", False)

    captured = {}

    async def fake_generate_followups(missing_slots, current_slots, user_message, intent, conversation_history=None, user_preferences=None):
        captured["asked"] = list(missing_slots)
        return {
            "intro": "x",
            "questions": [{"slot": s, "question": f"{s}?"} for s in missing_slots],
            "closing": "",
        }

    agent._extract_all_slots_from_conversation = AsyncMock(return_value={})
    agent._generate_followup_questions = fake_generate_followups

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(_new_plan_state(), "test-session")

    # All three expert questions in one card
    assert set(captured["asked"]) == {"use_case", "features", "budget"}
    assert result["proceed_to_execution"] is False


# ---------------------------------------------------------------------------
# Sequential flow: _handle_user_answer asks the deferred questions
# ---------------------------------------------------------------------------

def _answer_state(message="Gaming"):
    return {
        "user_message": message,
        "sanitized_text": message,
        "intent": "product",
        "session_id": "test-session",
        "conversation_history": [],
        "metadata": {},
    }


def _use_case_only_halt_state():
    """Halt state as _handle_new_plan (flag on) writes it: only use_case asked,
    full slot plan remembered."""
    return {
        "intent": "product",
        "slots": {"product_name": "laptops"},
        "followups": [
            {"slot": "use_case", "question": "What will you mainly use it for?",
             "options": ["Student / everyday", "Gaming", "Creative / video editing", "Business / office"]},
        ],
        "missing_required_slots": ["use_case", "features", "budget"],
        "plan": {"steps": [{"id": "step_1", "tools": ["product_search"], "parallel": False}]},
        "tools_by_required_slot": {},
    }


@pytest.mark.asyncio
async def test_flag_on_use_case_answer_triggers_deferred_questions(agent, monkeypatch):
    """After the use_case answer, the deferred features+budget questions are asked
    — and generated WITH the use_case answer in current_slots (so the features
    question adapts)."""
    monkeypatch.setattr(agent.settings, "USE_ANSWER_AWARE_FOLLOWUPS", True)

    # Extraction finds the use_case from the chip answer
    agent._extract_all_slots_from_answer = AsyncMock(return_value={"use_case": "Gaming"})

    generation_calls = []

    async def fake_generate_followups(missing_slots, current_slots, user_message, intent, conversation_history=None, user_preferences=None):
        generation_calls.append({"asked": list(missing_slots), "slots": dict(current_slots)})
        return {
            "intro": "Gaming — nice.",
            "questions": [{"slot": s, "question": f"{s}?"} for s in missing_slots],
            "closing": "",
        }

    agent._generate_followup_questions = fake_generate_followups

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()), \
         patch("app.agents.clarifier_agent.HaltStateManager.delete_halt_state", new=AsyncMock()):
        result = await agent._handle_user_answer(
            _answer_state("Gaming"), _use_case_only_halt_state(), "test-session"
        )

    # The deferred questions are asked, not skipped
    assert result["proceed_to_execution"] is False
    asked = generation_calls[-1]["asked"]
    assert set(asked) == {"features", "budget"}
    # And generation saw the use_case answer (this is what makes adaptation possible)
    assert generation_calls[-1]["slots"].get("use_case") == "Gaming"


@pytest.mark.asyncio
async def test_flag_on_second_answer_proceeds_to_execution(agent, monkeypatch):
    """Answering the deferred card (features + budget) completes the flow."""
    monkeypatch.setattr(agent.settings, "USE_ANSWER_AWARE_FOLLOWUPS", True)

    halt_state = {
        "intent": "product",
        "slots": {"product_name": "laptops", "use_case": "Gaming"},
        "followups": [
            {"slot": "features", "question": "What kind of gaming?",
             "options": ["AAA / new releases", "Esports / competitive"]},
            {"slot": "budget", "question": "What's your budget?",
             "options": ["$800–$1,200"]},
        ],
        "missing_required_slots": ["features", "budget"],
        "plan": {"steps": [{"id": "step_1", "tools": ["product_search"], "parallel": False}]},
        "tools_by_required_slot": {},
    }

    agent._extract_all_slots_from_answer = AsyncMock(
        return_value={"features": "AAA / new releases", "budget": "$800–$1,200"}
    )

    with patch("app.agents.clarifier_agent.HaltStateManager.delete_halt_state", new=AsyncMock()):
        result = await agent._handle_user_answer(
            _answer_state("AAA / new releases; $800–$1,200"), halt_state, "test-session"
        )

    assert result["proceed_to_execution"] is True
    assert result["slots"]["use_case"] == "Gaming"
    assert result["slots"]["features"] == "AAA / new releases"
    assert result["slots"]["budget"] == "$800–$1,200"


@pytest.mark.asyncio
async def test_flag_off_answer_flow_unchanged(agent, monkeypatch):
    """Flag off: answering all questions proceeds straight to execution — the
    deferred-question branch never runs even if halt state has extra slots."""
    monkeypatch.setattr(agent.settings, "USE_ANSWER_AWARE_FOLLOWUPS", False)

    halt_state = _use_case_only_halt_state()
    agent._extract_all_slots_from_answer = AsyncMock(return_value={"use_case": "Gaming"})
    agent._generate_followup_questions = AsyncMock(
        side_effect=AssertionError("flag off: no question regeneration expected")
    )

    with patch("app.agents.clarifier_agent.HaltStateManager.delete_halt_state", new=AsyncMock()):
        result = await agent._handle_user_answer(
            _answer_state("Gaming"), halt_state, "test-session"
        )

    assert result["proceed_to_execution"] is True


@pytest.mark.asyncio
async def test_flag_on_skip_all_still_bails_out(agent, monkeypatch):
    """Outcome 8's escape hatch beats the answer-aware flow: skip-all on the
    first (use_case-only) card goes straight to results."""
    monkeypatch.setattr(agent.settings, "USE_ANSWER_AWARE_FOLLOWUPS", True)

    agent._extract_all_slots_from_answer = AsyncMock(
        side_effect=AssertionError("skip-all must not extract")
    )
    agent._generate_followup_questions = AsyncMock(
        side_effect=AssertionError("skip-all must not regenerate questions")
    )

    with patch("app.agents.clarifier_agent.HaltStateManager.delete_halt_state", new=AsyncMock()):
        result = await agent._handle_user_answer(
            _answer_state("Just show me the best overall"),
            _use_case_only_halt_state(),
            "test-session",
        )

    assert result["proceed_to_execution"] is True
