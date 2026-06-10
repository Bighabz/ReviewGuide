"""QA remediation — "Ask me a few more questions" snowball.

Observed in QA (2026-06-10): each ask-more click re-rendered every question from
all previous rounds plus 1-3 new ones (2 → 5 → 8 → 9), generated rephrased
duplicates ("mattress type" vs "material" with identical options), and finally
scraped the bottom of the optional-slot barrel with "What is your gender?" on a
mattress query.

These tests pin the fixed contract:
1. Ask-more presents ONLY the newly generated questions (the prior card is
   still on screen); halt state keeps the full list so extraction still works.
2. The question generator is told what was already asked so it can't rephrase.
3. Ask-more is capped at 2 rounds — the third click proceeds to execution.
4. Demographic slots (gender) are never drawn into ask-more extras.
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


ROUND1_QUESTIONS = [
    {"slot": "features", "question": "How firm do you like your mattress?",
     "options": ["Soft", "Medium", "Firm"]},
    {"slot": "budget", "question": "What's your budget?",
     "options": ["Under $500", "$500-$1,000"]},
]

NEW_QUESTIONS_RESPONSE = {
    "intro": "Happy to dig deeper.",
    "questions": [
        {"slot": "size", "question": "What size do you need?",
         "options": ["Twin", "Queen", "King"], "optional": True},
        {"slot": "material", "question": "Any material preference?",
         "options": ["Memory foam", "Hybrid"], "optional": True},
    ],
    "closing": "",
}


def _halt_state(followups=None, slots=None, rounds=None):
    hs = {
        "followups": list(followups if followups is not None else ROUND1_QUESTIONS),
        "slots": dict(slots or {}),
        "intent": "product",
        "plan": {"steps": [{"id": "step_1", "tools": ["product_search"], "parallel": False}]},
    }
    if rounds is not None:
        hs["ask_more_rounds"] = rounds
    return hs


def _state(message="Ask me a few more questions"):
    return {
        "user_message": message,
        "sanitized_text": message,
        "intent": "product",
        "session_id": "test-session",
        "conversation_history": [{"role": "user", "content": "best mattress"}],
        "metadata": {},
    }


@pytest.mark.asyncio
async def test_ask_more_presents_only_new_questions(agent):
    """The new card shows ONLY the extra questions — prior unanswered ones are
    not re-rendered (their card is still on screen). Halt state keeps the full
    combined list so answers to the old card still extract."""
    agent._generate_followup_questions = AsyncMock(return_value=NEW_QUESTIONS_RESPONSE)
    saved = {}

    async def fake_update(session_id, data):
        saved.update(data)

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=fake_update):
        result = await agent._handle_user_answer(_state(), _halt_state(), "test-session")

    presented = [q["slot"] for q in result["next_question"]["questions"]]
    assert presented == ["size", "material"], (
        f"ask-more must present only NEW questions, got {presented}"
    )
    # Extraction continuity: halt state still tracks old + new
    tracked = [q["slot"] for q in saved["followups"]]
    assert set(tracked) == {"features", "budget", "size", "material"}
    assert result["proceed_to_execution"] is False


@pytest.mark.asyncio
async def test_ask_more_tells_generator_what_was_already_asked(agent):
    """The generator LLM must receive the previously asked question texts so it
    cannot rephrase them into duplicates."""
    agent._generate_followup_questions = AsyncMock(return_value=NEW_QUESTIONS_RESPONSE)

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        await agent._handle_user_answer(_state(), _halt_state(), "test-session")

    kwargs = agent._generate_followup_questions.call_args.kwargs
    already_asked = kwargs.get("already_asked")
    assert already_asked, "generator must be told what was already asked"
    assert "How firm do you like your mattress?" in already_asked
    assert "What's your budget?" in already_asked


@pytest.mark.asyncio
async def test_ask_more_increments_round_counter(agent):
    agent._generate_followup_questions = AsyncMock(return_value=NEW_QUESTIONS_RESPONSE)
    saved = {}

    async def fake_update(session_id, data):
        saved.update(data)

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=fake_update):
        await agent._handle_user_answer(_state(), _halt_state(), "test-session")

    assert saved.get("ask_more_rounds") == 1


@pytest.mark.asyncio
async def test_ask_more_round_cap_proceeds_to_execution(agent):
    """Third click (two rounds already served) stops digging and runs the search
    instead of stalling the turn with ever-deeper questions."""
    agent._generate_followup_questions = AsyncMock(return_value=NEW_QUESTIONS_RESPONSE)
    delete_mock = AsyncMock()

    with patch("app.agents.clarifier_agent.HaltStateManager.delete_halt_state", new=delete_mock), \
         patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        result = await agent._handle_user_answer(
            _state(), _halt_state(rounds=2), "test-session"
        )

    assert result["proceed_to_execution"] is True
    delete_mock.assert_awaited_once()
    agent._generate_followup_questions.assert_not_awaited()


@pytest.mark.asyncio
async def test_ask_more_excludes_demographic_slots(agent):
    """'What is your gender?' must never be drawn into ask-more extras.
    Slots filled so the only remaining optional contract slots are style+gender:
    only style may be asked."""
    agent._generate_followup_questions = AsyncMock(return_value=NEW_QUESTIONS_RESPONSE)
    slots = {
        "product_name": "mattress", "category": "mattresses", "brand": "any",
        "size": "Queen", "color": "white", "material": "foam", "use_case": "sleep",
    }

    with patch("app.agents.clarifier_agent.HaltStateManager.update_halt_state", new=AsyncMock()):
        await agent._handle_user_answer(
            _state(), _halt_state(slots=slots), "test-session"
        )

    asked_slots = agent._generate_followup_questions.call_args.args[0] \
        if agent._generate_followup_questions.call_args.args \
        else agent._generate_followup_questions.call_args.kwargs["missing_slots"]
    assert "gender" not in asked_slots
    assert asked_slots == ["style"]


@pytest.mark.asyncio
async def test_generator_prompt_contains_already_asked_questions(agent):
    """_generate_followup_questions injects the already-asked list into the LLM
    prompt with a do-not-repeat instruction."""
    captured = {}

    async def fake_generate(messages, **kwargs):
        captured["messages"] = messages
        return json.dumps(NEW_QUESTIONS_RESPONSE)

    agent.generate = fake_generate

    await agent._generate_followup_questions(
        missing_slots=["size", "material"],
        current_slots={"category": "mattresses"},
        user_message="Ask me a few more questions",
        intent="product",
        already_asked=["How firm do you like your mattress?", "What's your budget?"],
    )

    system_prompt = captured["messages"][0]["content"]
    assert "How firm do you like your mattress?" in system_prompt
    assert "What's your budget?" in system_prompt
