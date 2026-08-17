"""QA remediation (audit 2026-07-31) — medical guardrail fires too late.

The audit's finding: "an air purifier to cure my 6-year-old's asthma so she can
stop using her inhaler" was accepted without comment and went straight to
collecting room size and budget. The final-answer composer DOES push back
correctly — it told the user an air purifier won't cure asthma or replace an
inhaler — but a user who abandons at the clarifier never reaches it. They get
purchase questions and no correction.

SafetyAgent classifies against OpenAI moderation only (violence, self-harm,
sexual/minors, hate/threatening), so a medical query is policy_status="allow"
with nothing downstream knowing it needs a caveat.

This is NOT a refusal path. An air purifier for a home with asthma is legitimate
commerce. The flag makes the clarifier lead with a caveat instead of a budget
question; it must never block the sale.
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

from app.agents.safety_agent import SafetyAgent, detect_health_advisory  # noqa: E402

MEDICAL_QUERY = ("I need an air purifier to cure my 6-year-old's asthma so she can "
                 "stop using her inhaler")


class TestDetector:
    """Narrow by design: a treatment claim, not a comfort or fit preference."""

    @pytest.mark.parametrize("text", [
        MEDICAL_QUERY,
        "mattress that will fix my chronic lower back pain",
        "supplement to replace my blood pressure medication",
        "does this treat my eczema",
        "air purifier to cure asthma",
        "something to get off my anxiety medication",
    ])
    def test_flags_treatment_claims(self, text):
        assert detect_health_advisory(text) is True

    @pytest.mark.parametrize("text", [
        "best espresso machine under $500",
        "cordless vacuum for pet hair",
        "running shoes for flat feet",
        "air purifier for a dusty apartment",
        "chair for long work days",
        "mattress for a side sleeper",
        "left-handed beginner guitar for someone with a nickel allergy",
        "replacement filters for my vacuum",
    ])
    def test_does_not_flag_ordinary_shopping(self, text):
        # A false positive puts a medical caveat on ordinary commerce, which is
        # its own kind of broken. Comfort and fit are not treatment claims.
        assert detect_health_advisory(text) is False

    @pytest.mark.parametrize("text", ["", "   ", None])
    def test_handles_empty_input(self, text):
        assert detect_health_advisory(text) is False


class TestSafetyAgentIntegration:
    """The flag has to leave the agent, or nothing downstream can act on it."""

    @staticmethod
    def _agent():
        return SafetyAgent(openai_api_key="test-key")

    @staticmethod
    def _clean_moderation():
        return AsyncMock(return_value={"flagged": False, "categories": []})

    @pytest.mark.asyncio
    async def test_medical_query_is_not_blocked(self):
        # Legitimate commerce. This must stay true forever.
        agent = self._agent()
        with patch.object(agent, "_moderate_content", self._clean_moderation()):
            result = await agent.execute({
                "session_id": "s1", "user_message": MEDICAL_QUERY,
            })
        assert result["policy_status"] != "block"

    @pytest.mark.asyncio
    async def test_medical_query_sets_the_flag(self):
        agent = self._agent()
        with patch.object(agent, "_moderate_content", self._clean_moderation()):
            result = await agent.execute({
                "session_id": "s1", "user_message": MEDICAL_QUERY,
            })
        assert result["health_advisory"] is True

    @pytest.mark.asyncio
    async def test_ordinary_query_leaves_the_flag_false(self):
        agent = self._agent()
        with patch.object(agent, "_moderate_content", self._clean_moderation()):
            result = await agent.execute({
                "session_id": "s1", "user_message": "best espresso machine under $500",
            })
        assert result["health_advisory"] is False

    @pytest.mark.asyncio
    async def test_flag_is_present_even_on_the_error_path(self):
        # execute() catches exceptions and fails open (safety_agent.py:49-56).
        # The key must still exist or downstream .get() calls diverge by path.
        agent = self._agent()
        with patch.object(agent, "_execute_safety_checks",
                          AsyncMock(side_effect=RuntimeError("boom"))):
            result = await agent.execute({
                "session_id": "s1", "user_message": MEDICAL_QUERY,
            })
        assert result["policy_status"] == "allow"
        assert "health_advisory" in result


# ---------------------------------------------------------------------------
# Graph wiring — LangGraph only merges what a node RETURNS. A field present in
# the agent result but missing from the node's update dict is silently dropped
# at the node boundary (the follow_up_question bug, workflow.py:420-428).
# ---------------------------------------------------------------------------

class TestGraphWiring:

    @pytest.mark.asyncio
    async def test_safety_node_returns_the_flag(self):
        from app.services.langgraph import workflow as wf

        fake = AsyncMock(return_value={
            "policy_status": "allow",
            "sanitized_text": MEDICAL_QUERY,
            "redaction_map": {},
            "health_advisory": True,
        })
        with patch.object(wf.safety_agent_instance, "execute", fake):
            update = await wf.safety_node({
                "session_id": "", "user_message": MEDICAL_QUERY,
                "conversation_history": [],
            })
        assert update["health_advisory"] is True

    @pytest.mark.asyncio
    async def test_safety_node_timeout_fallback_carries_the_key(self):
        # The RFC §1.1 fallback dict must define every channel the happy path
        # does, or a timed-out turn diverges from a normal one.
        from app.services.langgraph import workflow as wf

        fake = AsyncMock(return_value={
            "policy_status": "allow", "sanitized_text": "x",
            "redaction_map": {}, "health_advisory": False,
        })
        with patch.object(wf.safety_agent_instance, "execute", fake):
            update = await wf.safety_node({
                "session_id": "", "user_message": "best espresso machine",
                "conversation_history": [],
            })
        assert "health_advisory" in update

    def test_graph_state_declares_the_channel(self):
        from app.schemas.graph_state import GraphState
        assert "health_advisory" in GraphState.__annotations__

    def test_chat_initial_state_defines_a_default(self):
        # Adding a GraphState field without a default in chat.py's initial_state
        # crashes LangGraph channels at runtime. This has bitten before.
        import pathlib
        src = pathlib.Path("app/api/v1/chat.py").read_text(encoding="utf-8")
        assert '"health_advisory"' in src


# ---------------------------------------------------------------------------
# The caveat itself. next_question is STRUCTURED data (followups_data, a dict
# with an "intro" and a "questions" list) — not a string. The caveat prepends
# to the intro; anything else corrupts the frontend payload.
# ---------------------------------------------------------------------------

from app.agents.clarifier_agent import HEALTH_CAVEAT, apply_health_caveat  # noqa: E402


def _followups(intro="I need a few more details to help you:"):
    return {
        "intro": intro,
        "questions": [
            {"slot": "room_size", "question": "How big is the room?",
             "options": ["Small", "Medium", "Large"]},
            {"slot": "budget", "question": "What's your budget?",
             "options": ["Under $100", "$100-$200"]},
        ],
    }


class TestHealthCaveat:

    def test_caveat_leads_the_intro(self):
        out = apply_health_caveat(_followups(), True)
        assert out["intro"].startswith(HEALTH_CAVEAT)

    def test_original_intro_is_preserved_after_the_caveat(self):
        out = apply_health_caveat(_followups("How big is the room?"), True)
        assert "How big is the room?" in out["intro"]

    def test_questions_are_untouched(self):
        original = _followups()
        out = apply_health_caveat(original, True)
        assert out["questions"] == original["questions"]

    def test_no_caveat_when_flag_is_false(self):
        out = apply_health_caveat(_followups(), False)
        assert HEALTH_CAVEAT not in out["intro"]

    def test_is_idempotent(self):
        once = apply_health_caveat(_followups(), True)
        twice = apply_health_caveat(once, True)
        assert twice["intro"].count(HEALTH_CAVEAT) == 1

    def test_handles_a_missing_intro(self):
        out = apply_health_caveat({"questions": []}, True)
        assert HEALTH_CAVEAT in out["intro"]

    def test_non_dict_payload_passes_through(self):
        assert apply_health_caveat(None, True) is None
        assert apply_health_caveat("a string", True) == "a string"

    def test_caveat_refuses_medical_advice_without_refusing_the_sale(self):
        lowered = HEALTH_CAVEAT.lower()
        assert "doctor" in lowered
        # It must still offer to help — this is legitimate commerce.
        assert "help" in lowered or "comfortable" in lowered


class TestCaveatReachesTheClarifierNode:

    @pytest.mark.asyncio
    async def test_clarifier_node_applies_the_caveat(self):
        from app.services.langgraph import workflow as wf

        fake = AsyncMock(return_value={
            "slots": {}, "followups": [{"slot": "room_size"}],
            "next_question": _followups(), "proceed_to_execution": False,
        })
        with patch.object(wf.clarifier_agent_instance, "execute", fake):
            update = await wf.clarifier_node({
                "session_id": "s1", "user_message": MEDICAL_QUERY,
                "health_advisory": True, "slots": {}, "plan": {"steps": []},
            })
        assert HEALTH_CAVEAT in update["assistant_text"]["intro"]

    @pytest.mark.asyncio
    async def test_clarifier_node_leaves_ordinary_queries_alone(self):
        from app.services.langgraph import workflow as wf

        fake = AsyncMock(return_value={
            "slots": {}, "followups": [{"slot": "budget"}],
            "next_question": _followups(), "proceed_to_execution": False,
        })
        with patch.object(wf.clarifier_agent_instance, "execute", fake):
            update = await wf.clarifier_node({
                "session_id": "s1", "user_message": "best espresso machine",
                "health_advisory": False, "slots": {}, "plan": {"steps": []},
            })
        assert HEALTH_CAVEAT not in update["assistant_text"]["intro"]
