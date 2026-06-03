"""
Conversational-expert clarifier: category-aware questions with tappable option
chips, use-case-first / budget-last ordering, and chip-aware slot extraction.

Covers:
- _generate_followup_questions normalizes LLM output (options capped, strings,
  free_text_hint defaulted) and enforces use_case-first / budget-last ordering
- backward compat: questions without options still pass through untouched
- LLM failure falls back to plain per-slot questions (no options)
- _extract_all_slots_from_answer includes offered chip choices in its prompt
- _handle_new_plan adds use_case + budget on substantive product queries,
  ordered use_case first and budget last
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

from app.agents.clarifier_agent import ClarifierAgent  # noqa: E402


@pytest.fixture
def agent():
    return ClarifierAgent()


# ---------------------------------------------------------------------------
# _generate_followup_questions — options + ordering
# ---------------------------------------------------------------------------

LAPTOP_LLM_RESPONSE = json.dumps({
    "intro": "Happy to help you find the right laptop.",
    "questions": [
        {
            "slot": "budget",
            "question": "What's your budget?",
            "options": ["Under $500", "$500–$800", "$800–$1,200", "$1,200+"],
            "free_text_hint": "or type an amount",
        },
        {
            "slot": "use_case",
            "question": "What will you mainly use it for?",
            "options": ["Student / everyday", "Gaming", "Creative / video editing", "Business / office"],
            "free_text_hint": "or describe your own use",
        },
    ],
    "closing": "Then I'll pull together a shortlist.",
})


@pytest.mark.asyncio
async def test_options_pass_through_and_budget_ordered_last(agent):
    """LLM returns budget first; the normalizer must reorder use_case → budget."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    result = await agent._generate_followup_questions(
        missing_slots=["use_case", "budget"],
        current_slots={"category": "laptops"},
        user_message="best laptop",
        intent="product",
    )

    slots_in_order = [q["slot"] for q in result["questions"]]
    assert slots_in_order == ["use_case", "budget"], "use_case must lead, budget must close"

    use_case_q = result["questions"][0]
    assert use_case_q["options"] == ["Student / everyday", "Gaming", "Creative / video editing", "Business / office"]
    # QA5 bug 3: microcopy is deterministic — the LLM's per-category hint is replaced
    assert use_case_q["free_text_hint"] == "or type your own answer"

    budget_q = result["questions"][1]
    assert "Under $500" in budget_q["options"]
    assert "Under $50" not in budget_q["options"], "no generic tiers for laptops"


@pytest.mark.asyncio
async def test_options_normalization_caps_and_defaults(agent):
    """Options are capped at 6 strings; missing free_text_hint gets a default."""
    response = json.dumps({
        "intro": "ok",
        "questions": [
            {
                "slot": "use_case",
                "question": "What for?",
                # 8 options incl. blanks and a number — should cap at 6 non-empty strings
                "options": ["a", "b", "", "c", 4, "d", "e", "f", "g"],
                # no free_text_hint
            },
        ],
        "closing": "",
    })
    agent.generate = AsyncMock(return_value=response)

    result = await agent._generate_followup_questions(
        missing_slots=["use_case"],
        current_slots={},
        # No question pack matches "best widget" — pack enforcement must not
        # replace the LLM options, so the capping logic is what's under test.
        user_message="best widget",
        intent="product",
    )

    q = result["questions"][0]
    assert len(q["options"]) == 6
    assert all(isinstance(o, str) and o for o in q["options"])
    assert q["free_text_hint"] == "or type your own answer"


@pytest.mark.asyncio
async def test_questions_without_options_still_work(agent):
    """Backward compat: a question with no options has no options key (frontend falls back)."""
    response = json.dumps({
        "intro": "ok",
        "questions": [
            {"slot": "destination", "question": "Where are you going?"},
        ],
        "closing": "",
    })
    agent.generate = AsyncMock(return_value=response)

    result = await agent._generate_followup_questions(
        missing_slots=["destination"],
        current_slots={},
        user_message="plan a trip",
        intent="travel",
    )

    q = result["questions"][0]
    assert q == {"slot": "destination", "question": "Where are you going?"}
    assert "options" not in q


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_plain_questions(agent):
    """If the LLM call raises, we still produce one plain question per missing slot."""
    agent.generate = AsyncMock(side_effect=RuntimeError("LLM down"))

    result = await agent._generate_followup_questions(
        missing_slots=["use_case", "budget"],
        current_slots={},
        user_message="best laptop",
        intent="product",
    )

    assert [q["slot"] for q in result["questions"]] == ["use_case", "budget"]
    assert all("options" not in q for q in result["questions"])


@pytest.mark.asyncio
async def test_malformed_question_entries_are_dropped(agent):
    """Entries missing slot/question are dropped, then backfilled from missing_slots."""
    response = json.dumps({
        "intro": "ok",
        "questions": [
            {"question": "No slot here"},          # dropped (no slot)
            {"slot": "budget"},                     # dropped (no question)
            "not even a dict",                      # dropped
        ],
        "closing": "",
    })
    agent.generate = AsyncMock(return_value=response)

    result = await agent._generate_followup_questions(
        missing_slots=["budget"],
        current_slots={},
        user_message="best laptop",
        intent="product",
    )

    assert len(result["questions"]) == 1
    assert result["questions"][0]["slot"] == "budget"
    assert result["questions"][0]["question"]  # backfilled placeholder


@pytest.mark.asyncio
async def test_product_prompt_carries_expert_framing(agent):
    """The product prompt names the category and demands realistic options."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    await agent._generate_followup_questions(
        missing_slots=["use_case", "budget"],
        current_slots={"category": "laptops"},
        user_message="best laptop",
        intent="product",
    )

    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "laptops specialist" in system_prompt
    assert "options" in system_prompt
    assert "budget LAST" in system_prompt


# ---------------------------------------------------------------------------
# _extract_all_slots_from_answer — chip-aware extraction context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extraction_prompt_includes_offered_choices(agent):
    """The slot extractor sees the chips that were offered, so a tapped chip maps cleanly."""
    agent.generate = AsyncMock(return_value=json.dumps({"use_case": "Gaming"}))

    followups = [
        {
            "slot": "use_case",
            "question": "What will you mainly use it for?",
            "options": ["Student / everyday", "Gaming", "Business / office"],
            "free_text_hint": "or describe your own use",
        }
    ]
    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["use_case"],
        user_message="Gaming",
        followups=followups,
    )

    assert extracted == {"use_case": "Gaming"}
    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "offered choices" in system_prompt
    assert "Student / everyday" in system_prompt


@pytest.mark.asyncio
async def test_extraction_without_options_unchanged(agent):
    """Questions without options keep the original extraction context format."""
    agent.generate = AsyncMock(return_value=json.dumps({"destination": "Tokyo"}))

    followups = [{"slot": "destination", "question": "Where are you going?"}]
    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["destination"],
        user_message="Tokyo",
        followups=followups,
    )

    assert extracted == {"destination": "Tokyo"}
    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    # No per-question choice list is rendered when the question has no options.
    # (The generic combined-answer rule may mention choices — that's fine.)
    assert "(offered choices:" not in system_prompt


# ---------------------------------------------------------------------------
# _handle_new_plan — expert-first ordering on substantive product queries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_substantive_product_query_asks_use_case_first_budget_last(agent):
    """'best laptop' (category extracted, nothing else) → ask use_case then budget."""
    state = {
        "plan": {"steps": [{"tools": ["product_search"]}]},
        "slots": {},
        "user_message": "best laptop",
        "sanitized_text": "best laptop",
        "intent": "product",
        "conversation_history": [],
        "last_search_context": {},
        "session_id": "test-session",
    }

    captured = {}

    async def fake_generate_followups(missing_slots, current_slots, user_message, intent, conversation_history=None):
        captured["missing_slots"] = list(missing_slots)
        return {
            "intro": "x",
            "questions": [{"slot": s, "question": f"{s}?"} for s in missing_slots],
            "closing": "",
        }

    # Extraction finds the category but nothing else
    agent._extract_all_slots_from_conversation = AsyncMock(
        return_value={"category": "laptops", "use_case": None, "budget": None}
    )
    agent._generate_followup_questions = fake_generate_followups

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    assert result["proceed_to_execution"] is False
    assert captured["missing_slots"][0] == "use_case", "use_case must be asked first"
    assert captured["missing_slots"][-1] == "budget", "budget must be asked last"


@pytest.mark.asyncio
async def test_non_substantive_query_does_not_inject_questions(agent):
    """A query where no category/product was extracted doesn't get use_case/budget injected."""
    state = {
        "plan": {"steps": [{"tools": ["product_search"]}]},
        "slots": {},
        "user_message": "hmm",
        "sanitized_text": "hmm",
        "intent": "product",
        "conversation_history": [],
        "last_search_context": {},
        "session_id": "test-session",
    }

    agent._extract_all_slots_from_conversation = AsyncMock(return_value={})

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    # No required slots, not substantive → proceed without questions
    assert result["proceed_to_execution"] is True
    assert result["followups"] == []


@pytest.mark.asyncio
async def test_query_with_use_case_and_budget_skips_clarification(agent):
    """'gaming laptop under $1500' — both slots present → no questions, straight to execution."""
    state = {
        "plan": {"steps": [{"tools": ["product_search"]}]},
        "slots": {},
        "user_message": "gaming laptop under $1500",
        "sanitized_text": "gaming laptop under $1500",
        "intent": "product",
        "conversation_history": [],
        "last_search_context": {},
        "session_id": "test-session",
    }

    agent._extract_all_slots_from_conversation = AsyncMock(
        return_value={"category": "laptops", "use_case": "gaming", "budget": "under $1500"}
    )

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    assert result["proceed_to_execution"] is True
    assert result["followups"] == []


# ---------------------------------------------------------------------------
# Round 2 — features slot rides along; prompt translates slots per category
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_features_rides_along_between_use_case_and_budget(agent):
    """'best laptop' (nothing but category) → three questions ordered
    use_case → features → budget."""
    state = {
        "plan": {"steps": [{"tools": ["product_search"]}]},
        "slots": {},
        "user_message": "best laptop",
        "sanitized_text": "best laptop",
        "intent": "product",
        "conversation_history": [],
        "last_search_context": {},
        "session_id": "test-session",
    }

    captured = {}

    async def fake_generate_followups(missing_slots, current_slots, user_message, intent, conversation_history=None):
        captured["missing_slots"] = list(missing_slots)
        return {
            "intro": "x",
            "questions": [{"slot": s, "question": f"{s}?"} for s in missing_slots],
            "closing": "",
        }

    agent._extract_all_slots_from_conversation = AsyncMock(
        return_value={"category": "laptops", "use_case": None, "features": None, "budget": None}
    )
    agent._generate_followup_questions = fake_generate_followups

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    assert result["proceed_to_execution"] is False
    assert captured["missing_slots"] == ["use_case", "features", "budget"]


@pytest.mark.asyncio
async def test_product_prompt_translates_slots_to_specialist_questions(agent):
    """The prompt teaches slot translation: mattress use_case = 'How do you usually sleep?',
    and the features question carries a 'No strong preference' escape hatch."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"category": "mattresses"},
        user_message="best mattress",
        intent="product",
    )

    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "How do you usually sleep?" in system_prompt, "category-translation examples missing"
    assert "No strong preference" in system_prompt, "features escape-hatch instruction missing"
    assert "mattresses specialist" in system_prompt


# ---------------------------------------------------------------------------
# Multi-select questions — "type": "multi_select" flag
# ---------------------------------------------------------------------------

HEADPHONES_MULTISELECT_RESPONSE = json.dumps({
    "intro": "Let's find your headphones.",
    "questions": [
        {
            "slot": "use_case",
            "question": "Where will you use them most?",
            "options": ["Commute & travel", "Gym & runs", "At a desk"],
            "free_text_hint": "or describe your own use",
            "type": "single_select",
        },
        {
            "slot": "features",
            "question": "Which features matter to you?",
            "options": ["Noise cancelling", "Waterproof", "Wireless", "No strong preference"],
            "free_text_hint": "or type your own",
            "type": "multi_select",
        },
        {
            "slot": "budget",
            "question": "What's your budget?",
            "options": ["Under $100", "$100–$250", "$250+"],
            "free_text_hint": "or type an amount",
        },
    ],
    "closing": "Then I'll pull a shortlist together.",
})


@pytest.mark.asyncio
async def test_multi_select_type_preserved_on_features_question(agent):
    """A question the LLM marks multi_select keeps the flag through normalization."""
    agent.generate = AsyncMock(return_value=HEADPHONES_MULTISELECT_RESPONSE)

    result = await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"category": "headphones"},
        user_message="best headphones",
        intent="product",
    )

    by_slot = {q["slot"]: q for q in result["questions"]}
    assert by_slot["features"].get("type") == "multi_select"


@pytest.mark.asyncio
async def test_single_select_type_stays_implicit(agent):
    """"single_select" (or no type at all) is the default — never emitted as a key."""
    agent.generate = AsyncMock(return_value=HEADPHONES_MULTISELECT_RESPONSE)

    result = await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"category": "headphones"},
        user_message="best headphones",
        intent="product",
    )

    by_slot = {q["slot"]: q for q in result["questions"]}
    assert "type" not in by_slot["use_case"], "single_select must stay implicit"
    assert "type" not in by_slot["budget"], "absent type must stay implicit"


@pytest.mark.asyncio
async def test_multi_select_stripped_from_budget_and_use_case(agent):
    """budget/use_case are always single-answer, even if the LLM marks them multi_select."""
    response = json.dumps({
        "intro": "ok",
        "questions": [
            {
                "slot": "use_case",
                "question": "What for?",
                "options": ["A", "B"],
                "type": "multi_select",  # wrong — must be stripped
            },
            {
                "slot": "budget",
                "question": "How much?",
                "options": ["Under $100", "$100+"],
                "type": "multi_select",  # wrong — must be stripped
            },
        ],
        "closing": "",
    })
    agent.generate = AsyncMock(return_value=response)

    result = await agent._generate_followup_questions(
        missing_slots=["use_case", "budget"],
        current_slots={"category": "headphones"},
        user_message="best headphones",
        intent="product",
    )

    for q in result["questions"]:
        assert "type" not in q, f"multi_select must never survive on {q['slot']}"


@pytest.mark.asyncio
async def test_product_prompt_carries_multi_select_instruction(agent):
    """The product prompt teaches the LLM when to emit multi_select."""
    agent.generate = AsyncMock(return_value=LAPTOP_LLM_RESPONSE)

    await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"category": "headphones"},
        user_message="best headphones",
        intent="product",
    )

    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "multi_select" in system_prompt
    assert "Never make budget or use_case multi-select" in system_prompt


@pytest.mark.asyncio
async def test_extraction_context_labels_multi_select_questions(agent):
    """The slot extractor is told which questions were multi-select, so a combined
    answer ("Noise cancelling, Waterproof") maps to that ONE slot."""
    agent.generate = AsyncMock(
        return_value=json.dumps({"features": "Noise cancelling, Waterproof"})
    )

    followups = [
        {
            "slot": "features",
            "question": "Which features matter to you?",
            "options": ["Noise cancelling", "Waterproof", "Wireless"],
            "free_text_hint": "or type your own",
            "type": "multi_select",
        }
    ]
    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["features"],
        user_message="Noise cancelling, Waterproof",
        followups=followups,
    )

    assert extracted == {"features": "Noise cancelling, Waterproof"}
    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "multi-select" in system_prompt
    assert "ONE slot's value" in system_prompt


@pytest.mark.asyncio
async def test_extraction_context_omits_multi_select_note_for_single_select(agent):
    """Single-select questions don't get the multi-select note in the extraction prompt."""
    agent.generate = AsyncMock(return_value=json.dumps({"use_case": "Gaming"}))

    followups = [
        {
            "slot": "use_case",
            "question": "What will you mainly use it for?",
            "options": ["Student / everyday", "Gaming"],
            "free_text_hint": "or describe your own use",
        }
    ]
    await agent._extract_all_slots_from_answer(
        slot_names=["use_case"],
        user_message="Gaming",
        followups=followups,
    )

    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "multi-select" not in system_prompt


# ---------------------------------------------------------------------------
# Duplicate-slot extraction loop (prod 2026-06-02): required slots also listed
# as optional produced duplicate JSON keys in the extractor template; json.loads
# keeps the LAST key, so the real answer was overwritten by null and the
# clarifier re-asked the same questions forever.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extraction_slot_names_are_deduped(agent):
    """_extract_all_slots_from_answer must never put duplicate slot names in its
    prompt template — duplicates become duplicate JSON keys and the answer is lost."""
    captured = {}

    async def fake_generate(**kwargs):
        captured["system"] = kwargs["messages"][0]["content"]
        return json.dumps({"use_case": "Office tasks", "features": None, "budget": None})

    agent.generate = fake_generate

    followups = [
        {"slot": "use_case", "question": "What for?", "options": ["Office tasks", "Gaming"]},
        {"slot": "features", "question": "Which features?", "options": ["Light", "Fast"]},
        {"slot": "budget", "question": "How much?", "options": ["$500", "$1000"]},
    ]
    # Caller passes duplicates (required + optional overlap) — the prod trigger
    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["use_case", "features", "budget", "brand", "budget", "features", "use_case"],
        user_message="You chose: Office tasks",
        followups=followups,
        optional_slots=["brand", "budget", "features", "use_case"],
    )

    # The template line '"<slot>": <value or null>' must appear exactly once per slot
    assert captured["system"].count('"use_case":') == 1, "duplicate use_case key in extractor template"
    assert captured["system"].count('"budget":') == 1, "duplicate budget key in extractor template"
    assert extracted.get("use_case") == "Office tasks"


@pytest.mark.asyncio
async def test_handle_user_answer_dedupes_required_and_optional(agent):
    """_handle_user_answer must not list a required slot as optional too — the
    chip answer must be consumed, not re-asked."""
    halt_state = {
        "intent": "product",
        "slots": {"category": "laptop", "country_code": "US"},
        "followups": [
            {"slot": "use_case", "question": "What will you mainly use the laptop for?",
             "options": ["Schoolwork", "Office tasks", "Creative work"]},
            {"slot": "budget", "question": "What is your budget?",
             "options": ["Under $500", "$500–$800"]},
        ],
        "missing_required_slots": ["use_case", "budget"],
        # product_search's contract lists use_case/budget/features as OPTIONAL too —
        # this overlap is what created the duplicates in prod
        "plan": {"steps": [{"id": "s1", "tools": ["product_search"]}]},
        "tools_by_required_slot": {},
    }
    state = {
        "session_id": "test-session",
        "user_message": "You chose: Office tasks",
        "sanitized_text": "You chose: Office tasks",
        "intent": "product",
        "slots": {},
        "conversation_history": [],
        "last_search_context": {},
        "search_history": [],
    }

    captured = {}

    async def fake_extract(slot_names, user_message, followups, optional_slots=None):
        captured["slot_names"] = list(slot_names)
        # Simulate successful extraction of the answered slot
        return {s: ("Office tasks" if s == "use_case" else None) for s in slot_names}

    agent._extract_all_slots_from_answer = fake_extract
    # Question regeneration for the still-missing budget slot
    agent._generate_followup_questions = AsyncMock(return_value={
        "intro": "x",
        "questions": [{"slot": "budget", "question": "Budget?", "options": ["Under $500"]}],
        "closing": "",
    })

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_user_answer(state, halt_state, "test-session")

    # No duplicates went into extraction
    assert len(captured["slot_names"]) == len(set(captured["slot_names"])), (
        f"duplicate slot names passed to extraction: {captured['slot_names']}"
    )
    # The answer was consumed: use_case filled, only budget still missing
    assert result["slots"]["use_case"] == "Office tasks"
    assert result["missing_required_slots"] == ["budget"]


# ---------------------------------------------------------------------------
# QA Round 4 — F6: bare "best X" queries skip the extraction LLM call
# ---------------------------------------------------------------------------
# The extraction call costs 3-8s and was pushing the clarifier past its hard
# stage budget; the timeout fallback then silently skipped clarification.
# Bare category queries extract product_name heuristically instead.

def _new_plan_state(message: str, history=None):
    return {
        "plan": {"steps": [{"tools": ["product_search"]}]},
        "slots": {},
        "user_message": message,
        "sanitized_text": message,
        "intent": "product",
        "conversation_history": history or [],
        "last_search_context": {},
        "session_id": "test-session",
    }


@pytest.mark.asyncio
async def test_bare_best_x_query_skips_extraction_llm_call(agent):
    """'best mattress' → product_name extracted heuristically, NO extraction LLM call,
    and the expert questions still get injected (substantive query)."""
    state = _new_plan_state("best mattress")

    extraction_mock = AsyncMock(return_value={})
    agent._extract_all_slots_from_conversation = extraction_mock

    captured = {}

    async def fake_generate_followups(missing_slots, current_slots, user_message, intent, conversation_history=None):
        captured["missing_slots"] = list(missing_slots)
        captured["current_slots"] = dict(current_slots)
        return {
            "intro": "x",
            "questions": [{"slot": s, "question": f"{s}?"} for s in missing_slots],
            "closing": "",
        }

    agent._generate_followup_questions = fake_generate_followups

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    extraction_mock.assert_not_called()
    assert captured["current_slots"].get("product_name") == "mattress"
    # The expert flow still fires — questions are asked, not skipped
    assert result["proceed_to_execution"] is False
    assert "use_case" in captured["missing_slots"]
    assert "budget" in captured["missing_slots"]


@pytest.mark.asyncio
async def test_query_with_qualifier_still_uses_llm_extraction(agent):
    """'best mattress for side sleepers' has extractable content → LLM extraction runs."""
    state = _new_plan_state("best mattress for side sleepers")

    extraction_mock = AsyncMock(return_value={"product_name": "mattress", "use_case": "side sleepers"})
    agent._extract_all_slots_from_conversation = extraction_mock
    agent._generate_followup_questions = AsyncMock(return_value={"intro": "", "questions": [], "closing": ""})

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        await agent._handle_new_plan(state, "test-session")

    extraction_mock.assert_called_once()


@pytest.mark.asyncio
async def test_query_with_budget_number_still_uses_llm_extraction(agent):
    """'best laptop under $800' contains a number → LLM extraction runs (budget needs parsing)."""
    state = _new_plan_state("best laptop under $800")

    extraction_mock = AsyncMock(return_value={"product_name": "laptop", "budget": "under $800"})
    agent._extract_all_slots_from_conversation = extraction_mock
    agent._generate_followup_questions = AsyncMock(return_value={"intro": "", "questions": [], "closing": ""})

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        await agent._handle_new_plan(state, "test-session")

    extraction_mock.assert_called_once()


@pytest.mark.asyncio
async def test_non_superlative_query_still_uses_llm_extraction(agent):
    """'hmm' doesn't match the fast path → LLM extraction runs → not substantive → proceed."""
    state = _new_plan_state("hmm")

    extraction_mock = AsyncMock(return_value={})
    agent._extract_all_slots_from_conversation = extraction_mock

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    extraction_mock.assert_called_once()
    assert result["proceed_to_execution"] is True


@pytest.mark.asyncio
async def test_fast_path_skipped_with_conversation_history(agent):
    """A 'best X' query mid-conversation still uses LLM extraction (history may hold answers)."""
    history = [
        {"role": "user", "content": "best coffee machine"},
        {"role": "assistant", "content": "..."},
        {"role": "user", "content": "best espresso machine"},
    ]
    state = _new_plan_state("best espresso machine", history=history)

    extraction_mock = AsyncMock(return_value={})
    agent._extract_all_slots_from_conversation = extraction_mock

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        await agent._handle_new_plan(state, "test-session")

    extraction_mock.assert_called_once()


def test_clarifier_stage_budget_accommodates_two_llm_calls():
    """F6 regression: the clarifier hard budget must be ≥ 15s — two sequential LLM calls
    (extraction + question generation) routinely take 8-12s, and the timeout fallback
    silently skips clarification."""
    from app.services.stage_telemetry import STAGE_BUDGETS
    soft, hard = STAGE_BUDGETS["clarifier"]
    assert hard >= 15.0, (
        f"Clarifier hard budget is {hard}s - the timeout fallback skips clarification "
        "entirely, so this must cover two sequential LLM calls (QA Round 4 F6)"
    )


# ---------------------------------------------------------------------------
# QA Round 5 (external bugs 2+3) — pack data and microcopy are deterministic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pack_multi_select_enforced_even_when_llm_drops_it(agent):
    """Office chairs' features question is multi_select in the pack; the LLM dropping
    the flag must not make it single-select (external QA bug 2)."""
    response = json.dumps({
        "intro": "ok",
        "questions": [
            {
                "slot": "features",
                "question": "Which features matter to you?",
                # LLM echoed the question but DROPPED the multi_select type + reworded options
                "options": ["Lumbar support", "Headrest", "Armrests"],
            },
        ],
        "closing": "",
    })
    agent.generate = AsyncMock(return_value=response)

    result = await agent._generate_followup_questions(
        missing_slots=["features"],
        current_slots={"category": "office chair"},
        user_message="best office chair",
        intent="product",
    )

    q = result["questions"][0]
    # Pack enforcement: chairs pack says multi_select=True and defines the options
    assert q.get("type") == "multi_select"
    from app.agents.category_question_packs import CATEGORY_QUESTION_PACKS
    assert q["options"] == CATEGORY_QUESTION_PACKS["chairs"]["features"]["options"]
    # Deterministic microcopy for multi-select
    assert q["free_text_hint"] == "Select all that apply — or type your own"


@pytest.mark.asyncio
async def test_pack_single_select_enforced_when_llm_invents_multi(agent):
    """Laptops' performance question is single-select in the pack; the LLM marking it
    multi_select must be stripped."""
    response = json.dumps({
        "intro": "ok",
        "questions": [
            {
                "slot": "features",
                "question": "What performance level do you need?",
                "options": ["Just the basics", "Mid-range power"],
                "type": "multi_select",  # LLM invented this — pack says False
            },
        ],
        "closing": "",
    })
    agent.generate = AsyncMock(return_value=response)

    result = await agent._generate_followup_questions(
        missing_slots=["features"],
        current_slots={"category": "laptops"},
        user_message="best laptop",
        intent="product",
    )

    q = result["questions"][0]
    assert q.get("type") is None, "laptop features must stay single-select per the pack"
    assert q["free_text_hint"] == "or type your own answer"


@pytest.mark.asyncio
async def test_budget_microcopy_and_brackets_enforced_from_pack(agent):
    """Budget question: pack brackets + 'or type an amount' hint, regardless of LLM output."""
    response = json.dumps({
        "intro": "ok",
        "questions": [
            {
                "slot": "budget",
                "question": "What's your budget range?",
                "options": ["Cheap", "Mid", "Expensive"],  # LLM ignored the pack brackets
                "free_text_hint": "or specify other amount",
            },
        ],
        "closing": "",
    })
    agent.generate = AsyncMock(return_value=response)

    result = await agent._generate_followup_questions(
        missing_slots=["budget"],
        current_slots={"category": "headphones"},
        user_message="best headphones",
        intent="product",
    )

    q = result["questions"][0]
    from app.agents.category_question_packs import CATEGORY_QUESTION_PACKS
    assert q["options"] == CATEGORY_QUESTION_PACKS["headphones"]["budget_brackets"]
    assert q["free_text_hint"] == "or type an amount"


@pytest.mark.asyncio
async def test_extraction_prompt_handles_combined_card_answer(agent):
    """The extraction prompt documents the combined multi-question answer format the
    form-style card sends ('use case; features; budget')."""
    agent.generate = AsyncMock(return_value=json.dumps({
        "use_case": "Road running", "features": "Max cushion", "budget": "$80–$130",
    }))

    followups = [
        {"slot": "use_case", "question": "What kind of running?", "options": ["Road running", "Trail running"]},
        {"slot": "features", "question": "What feel?", "options": ["Max cushion", "Stability"], "type": "multi_select"},
        {"slot": "budget", "question": "Budget?", "options": ["Under $80", "$80–$130"]},
    ]
    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["use_case", "features", "budget"],
        user_message="Road running; Max cushion; $80–$130",
        followups=followups,
    )

    assert extracted["use_case"] == "Road running"
    assert extracted["budget"] == "$80–$130"
    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "SEVERAL questions in ONE message" in system_prompt


# ---------------------------------------------------------------------------
# QA Round 5 — F5: cross-category slot bleed
# ---------------------------------------------------------------------------
# Prior conversation/search context may only satisfy clarifier slots when it's
# about the SAME category. Before this fix, "best blender" after a running-shoes
# search inherited running-shoe answers and never asked blender questions.

from app.agents.clarifier_agent import _query_relates_to_context  # noqa: E402

COFFEE_CONTEXT = {
    "category": "coffee machine",
    "product_type": "coffee machine",
    "product_names": ["Hamilton Beach 49980A 2-Way Brewer", "Cuisinart DGB-900BC Grind & Brew"],
    "budget": "under $100",
    "use_case": "espresso drinks",
    "features": "built-in grinder",
    "top_prices": {"Hamilton Beach 49980A 2-Way Brewer": 39.99},
}

COFFEE_HISTORY = [
    {"role": "user", "content": "best coffee machine"},
    {"role": "assistant", "content": "Let's narrow down..."},
    {"role": "user", "content": "I mostly make espresso drinks at home"},
    {"role": "assistant", "content": "What's your budget?"},
    {"role": "user", "content": "Under $100"},
    {"role": "assistant", "content": "Here are the picks..."},
]


def test_query_relates_to_context_helper():
    """Unit coverage for the category-relatedness check."""
    # Cross-category: no word overlap → not related
    assert _query_relates_to_context("best office chair", COFFEE_CONTEXT) is False
    assert _query_relates_to_context("best blender", COFFEE_CONTEXT) is False
    # Same-ish category: "machine" overlaps → related
    assert _query_relates_to_context("best espresso machine", COFFEE_CONTEXT) is True
    # Indeterminate cases count as related (pre-F5 behavior preserved)
    assert _query_relates_to_context("best blender", {}) is True
    assert _query_relates_to_context("", COFFEE_CONTEXT) is True


@pytest.mark.asyncio
async def test_cross_category_bare_query_asks_questions_despite_context(agent):
    """F5 regression: 'best office chair' in a coffee-machine session must ask CHAIR
    questions — the coffee budget/use_case must not suppress them. The bare query
    also rides the F6 fast path (no extraction LLM call needed)."""
    state = _new_plan_state("best office chair", history=list(COFFEE_HISTORY))
    state["last_search_context"] = dict(COFFEE_CONTEXT)

    extraction_mock = AsyncMock(return_value={})
    agent._extract_all_slots_from_conversation = extraction_mock

    captured = {}

    async def fake_generate_followups(missing_slots, current_slots, user_message, intent, conversation_history=None):
        captured["missing_slots"] = list(missing_slots)
        captured["current_slots"] = dict(current_slots)
        return {
            "intro": "x",
            "questions": [{"slot": s, "question": f"{s}?"} for s in missing_slots],
            "closing": "",
        }

    agent._generate_followup_questions = fake_generate_followups

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    # Questions ARE asked — the coffee context did not satisfy them
    assert result["proceed_to_execution"] is False
    assert "use_case" in captured["missing_slots"]
    assert "budget" in captured["missing_slots"]
    # Bare cross-category query rides the fast path (no LLM extraction call)
    extraction_mock.assert_not_called()
    assert captured["current_slots"].get("product_name") == "office chair"


@pytest.mark.asyncio
async def test_cross_category_qualified_query_extracts_from_message_only(agent):
    """'best standing desk for small apartments' (not bare → LLM extraction) in a coffee
    session: the extraction must receive an EMPTY history so coffee answers can't bleed."""
    state = _new_plan_state("best standing desk for small apartments", history=list(COFFEE_HISTORY))
    state["last_search_context"] = dict(COFFEE_CONTEXT)

    extraction_mock = AsyncMock(return_value={"product_name": "standing desk"})
    agent._extract_all_slots_from_conversation = extraction_mock
    agent._generate_followup_questions = AsyncMock(
        return_value={"intro": "", "questions": [{"slot": "use_case", "question": "u?"}], "closing": ""}
    )

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    extraction_mock.assert_called_once()
    assert extraction_mock.call_args.kwargs["conversation_history"] == [], (
        "cross-category extraction must not see the prior conversation"
    )
    # And questions get asked (coffee context did not satisfy them)
    assert result["proceed_to_execution"] is False


@pytest.mark.asyncio
async def test_same_category_query_still_inherits_context(agent):
    """'best espresso machine with milk frother' in a coffee session: context relates →
    history IS passed to extraction and the coffee budget/use_case satisfy the expert
    checks (no re-asking)."""
    state = _new_plan_state("best espresso machine with milk frother", history=list(COFFEE_HISTORY))
    state["last_search_context"] = dict(COFFEE_CONTEXT)

    extraction_mock = AsyncMock(return_value={"product_name": "espresso machine"})
    agent._extract_all_slots_from_conversation = extraction_mock

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    # History passed through — same category, inheritance is legitimate
    extraction_mock.assert_called_once()
    assert extraction_mock.call_args.kwargs["conversation_history"] == COFFEE_HISTORY
    # Coffee budget/use_case satisfy the checks → no questions re-asked
    assert result["proceed_to_execution"] is True
    assert result["followups"] == []


@pytest.mark.asyncio
async def test_fresh_session_unaffected_by_f5_gates(agent):
    """No prior context → all F5 gates are no-ops (fast path + expert flow unchanged)."""
    state = _new_plan_state("best mattress")

    extraction_mock = AsyncMock(return_value={})
    agent._extract_all_slots_from_conversation = extraction_mock

    captured = {}

    async def fake_generate_followups(missing_slots, current_slots, user_message, intent, conversation_history=None):
        captured["missing_slots"] = list(missing_slots)
        return {
            "intro": "x",
            "questions": [{"slot": s, "question": f"{s}?"} for s in missing_slots],
            "closing": "",
        }

    agent._generate_followup_questions = fake_generate_followups

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_new_plan(state, "test-session")

    assert result["proceed_to_execution"] is False
    assert "use_case" in captured["missing_slots"]
    extraction_mock.assert_not_called()  # F6 fast path


# ---------------------------------------------------------------------------
# F2 (QA Round 6) — budget ranges must survive slot extraction
# ---------------------------------------------------------------------------

from app.agents.clarifier_agent import _find_budget_phrase  # noqa: E402

BUDGET_FOLLOWUPS = [
    {
        "slot": "budget",
        "question": "What's your budget for these running shoes?",
        "options": ["Under $80", "$80–$130", "$130–$180", "$180+"],
        "free_text_hint": "or type an amount",
    }
]


def test_find_budget_phrase_shapes():
    """The literal-phrase finder preserves every budget shape _parse_budget understands."""
    assert _find_budget_phrase("$80–$130") == "$80–$130"
    assert _find_budget_phrase("You chose: $80–$130") == "$80–$130"
    assert _find_budget_phrase("100-200") == "100-200"
    assert _find_budget_phrase("100 to 200") == "100 to 200"
    assert _find_budget_phrase("$1,200+") == "$1,200+"
    assert _find_budget_phrase("under $500 please") == "under $500"
    assert _find_budget_phrase("somewhere around $150") == "around $150"
    # No budget phrase → empty (bare numbers are NOT a range/qualifier)
    assert _find_budget_phrase("my budget is 100 dollars") == ""
    assert _find_budget_phrase("Gaming") == ""
    assert _find_budget_phrase("") == ""
    assert _find_budget_phrase(None) == ""


def test_find_budget_phrase_prefers_dollar_and_last_in_combined_answers():
    """A combined card answer can contain non-budget number ranges (battery hours).
    The finder must pick the dollar-denominated / right-most phrase — budget is
    always the last question on the card."""
    combined = "4–8 hours; Lumbar support, Breathable mesh; $150–$350"
    assert _find_budget_phrase(combined) == "$150–$350"
    # No dollar signs anywhere → right-most range still wins
    assert _find_budget_phrase("4-8 hours; lumbar; 150-350") == "150-350"


@pytest.mark.asyncio
async def test_extraction_keeps_budget_range_string(agent):
    """When the extractor LLM behaves, the range string passes through untouched."""
    agent.generate = AsyncMock(return_value=json.dumps({"budget": "$80–$130"}))

    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["budget"],
        user_message="$80–$130",
        followups=BUDGET_FOLLOWUPS,
    )

    assert extracted == {"budget": "$80–$130"}


@pytest.mark.asyncio
async def test_extraction_guard_restores_collapsed_budget_range(agent):
    """THE F2 prod bug: the extractor collapsed "$80–$130" to the number 100, which
    reads as a ceiling downstream and erases the floor. The deterministic guard
    must restore the literal phrase from the user's answer."""
    agent.generate = AsyncMock(return_value=json.dumps({"budget": 100}))

    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["budget"],
        user_message="$80–$130",
        followups=BUDGET_FOLLOWUPS,
    )

    assert extracted == {"budget": "$80–$130"}, (
        "a collapsed numeric budget must be replaced by the literal range the user gave"
    )


@pytest.mark.asyncio
async def test_extraction_guard_restores_range_in_combined_card_answer(agent):
    """Same guard, multi-question card format: the budget is the last segment."""
    agent.generate = AsyncMock(return_value=json.dumps({
        "use_case": "Long-distance running",
        "features": "Max cushion",
        "budget": "130",
    }))

    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["use_case", "features", "budget"],
        user_message="Long-distance running; Max cushion; $80–$130",
        followups=BUDGET_FOLLOWUPS,
    )

    assert extracted["budget"] == "$80–$130"
    assert extracted["use_case"] == "Long-distance running"


@pytest.mark.asyncio
async def test_extraction_guard_does_not_fire_on_legit_qualifiers(agent):
    """LLM answers that already carry the shape ("under $80") are kept as-is."""
    agent.generate = AsyncMock(return_value=json.dumps({"budget": "under $80"}))

    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["budget"],
        user_message="Under $80",
        followups=BUDGET_FOLLOWUPS,
    )

    assert extracted == {"budget": "under $80"}


@pytest.mark.asyncio
async def test_extraction_guard_keeps_bare_number_when_user_gave_no_range(agent):
    """A user who really typed a bare number keeps it (treated as a ceiling)."""
    agent.generate = AsyncMock(return_value=json.dumps({"budget": 100}))

    extracted = await agent._extract_all_slots_from_answer(
        slot_names=["budget"],
        user_message="100 dollars max",
        followups=BUDGET_FOLLOWUPS,
    )

    assert extracted == {"budget": 100}


@pytest.mark.asyncio
async def test_extraction_prompt_says_budget_is_a_string(agent):
    """Both extraction prompts must instruct: budget keeps its range/qualifier
    shape as a STRING, and budget is NOT in the return-as-number list."""
    agent.generate = AsyncMock(return_value=json.dumps({"budget": "$80–$130"}))

    await agent._extract_all_slots_from_answer(
        slot_names=["budget"],
        user_message="$80–$130",
        followups=BUDGET_FOLLOWUPS,
    )

    system_prompt = agent.generate.call_args.kwargs["messages"][0]["content"]
    assert "NEVER collapse a range" in system_prompt
    assert "For numbers (duration_days, adults, children): return as number" in system_prompt
    assert "children, budget): return as number" not in system_prompt
