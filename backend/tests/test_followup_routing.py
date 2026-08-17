"""Questions about the previous answer must be answered, not re-clarified.

Audit: "which reviews support your pick?" produced another budget/brand
questionnaire. A message arriving while a halt exists was treated as a slot
answer or a fresh search — never as a question about the previous answer.
"""
import os

import pytest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.agents.clarifier_agent import is_followup_question

CONTEXT = {"category": "air purifier",
           "product_names": ["GermGuardian AC4825", "Levoit Core 300"]}


@pytest.mark.parametrize("message", [
    "what CADR and filter type should I look for, and does the GermGuardian meet it?",
    "which reviews support your pick?",
    "where did you get the Emma claim?",
    "why did you pick that one over the Levoit?",
    "is the GermGuardian quiet enough for a bedroom?",
])
def test_recognises_follow_up_questions(message):
    assert is_followup_question(message, CONTEXT) is True


@pytest.mark.parametrize("message", [
    "best espresso machine under $500",
    "cordless vacuum for pet hair",
    "Manchester, UK",
    "under $300",
])
def test_new_searches_and_slot_answers_are_not_follow_ups(message):
    assert is_followup_question(message, CONTEXT) is False


def test_no_prior_context_means_no_follow_up():
    assert is_followup_question("which reviews support your pick?", {}) is False


# ---------------------------------------------------------------------------
# Resume-branch routing: T1×T3 composition (binding validation rule) —
# capture runs FIRST; a message that plausibly fills the one open slot is
# never rerouted. A follow-up question routes to intent and clears the halt.
# ---------------------------------------------------------------------------

from app.services.langgraph import workflow as wf

ALLOW = {
    "policy_status": "allow", "sanitized_text": "", "redaction_map": {},
    "health_advisory": False,
}


def _halt(followups, slots=None, **extra):
    return {"intent": "product", "slots": slots or {"category": "air purifier"},
            "followups": followups, "plan": None, **extra}


async def _resume(user_message, halt, state_extra=None):
    fake_exec = AsyncMock(return_value={**ALLOW, "sanitized_text": user_message})
    delete_mock = AsyncMock()
    with patch.object(wf.safety_agent_instance, "execute", fake_exec), \
         patch("app.services.halt_state_manager.HaltStateManager.check_halt_exists",
               AsyncMock(return_value=True)), \
         patch("app.services.halt_state_manager.HaltStateManager.load_halt_state",
               AsyncMock(return_value=halt)), \
         patch("app.services.halt_state_manager.HaltStateManager.delete_halt_state",
               delete_mock):
        update = await wf.safety_node({
            "session_id": "s1",
            "user_message": user_message,
            "conversation_history": [],
            **(state_extra or {}),
        })
    return update, delete_mock


@pytest.mark.asyncio
async def test_followup_question_routes_to_intent_and_clears_the_halt():
    halt = _halt([{"slot": "budget", "question": "Budget?"}],
                 last_search_context=CONTEXT)
    update, delete_mock = await _resume("which reviews support your pick?", halt)

    assert update["next_agent"] == "intent"
    assert update.get("followups") == []
    delete_mock.assert_awaited()


@pytest.mark.asyncio
async def test_plausible_slot_answer_is_never_rerouted():
    # One open slot + a message that fills it -> clarifier, even though the
    # category word appears (T1 wins over T3 by mandated order).
    halt = _halt([{"slot": "budget", "question": "Budget?"}],
                 last_search_context=CONTEXT)
    update, delete_mock = await _resume("under $300", halt)

    assert update["next_agent"] == "clarifier"
    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_followup_detection_falls_back_to_halt_slots_for_context():
    # Clarification halts don't reliably carry last_search_context — the
    # category in the halt's own slots must serve as fallback context.
    halt = _halt([{"slot": "budget", "question": "Budget?"}])
    update, delete_mock = await _resume(
        "is an air purifier worth it for allergies?", halt)

    assert update["next_agent"] == "intent"
    delete_mock.assert_awaited()
