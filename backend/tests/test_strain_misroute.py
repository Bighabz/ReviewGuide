"""Prod incident 2026-07-21 (session 96e11c6f): a Whoop-vs-Apple-Watch
question was intent-classified 'strain', the extractor correctly found zero
cannabis signal, and the pipeline recommended GG4 anyway.

Three stacked failures; each fix here is independent:
1. zero-signal extraction aborts instead of broad-recommending (strain_search)
2. a verdict refusal is FINAL — the fallback may not resurrect the pick
   (strain_compose; DOCTRINE D5 axis three: protective gates fail closed)
3. zero-evidence veto on the strain intent (intent_agent; the AI still owns
   detection — the veto fires only when NO cannabis evidence exists anywhere)
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

from app.core.config import settings
from mcp_server.tools.strain_search import strain_search

UNCLE_QUERY = ("Health only, but is the whoop worth it, does it do more than "
               "the apple watch for health")

EMPTY_EXTRACTION = '{"named_strains": [], "feelings": [], "conditions": [], "strain_type": null}'


@pytest.fixture(autouse=True)
def _no_serper(monkeypatch):
    monkeypatch.setattr(settings, "ENABLE_SERPAPI", False)


# ---------------------------------------------------------------------------
# Task 1 — zero cannabis signal aborts the strain plan
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_signal_aborts_instead_of_recommending():
    with patch("app.services.model_service.model_service.generate",
               new=AsyncMock(return_value=EMPTY_EXTRACTION)):
        result = await strain_search({"user_message": UNCLE_QUERY, "slots": {}})
    assert result.get("strain_misroute") is True
    assert result.get("strain_results") in ([], None)


@pytest.mark.asyncio
async def test_empty_extraction_with_cannabis_words_still_recommends():
    """'what should I smoke to relax' can extract empty (vocab clamp) but the
    message IS a cannabis ask — broad recommend stays correct there."""
    with patch("app.services.model_service.model_service.generate",
               new=AsyncMock(return_value=EMPTY_EXTRACTION)):
        result = await strain_search({
            "user_message": "what weed should I smoke to relax", "slots": {}})
    assert result.get("strain_misroute") is not True
    assert result.get("strain_results")


# ---------------------------------------------------------------------------
# Task 2 — a verdict refusal is final
# ---------------------------------------------------------------------------

from mcp_server.tools.strain_compose import strain_compose


@pytest.mark.asyncio
async def test_misroute_flag_yields_honest_redirect_not_cards():
    result = await strain_compose({
        "user_message": UNCLE_QUERY,
        "strain_results": [],
        "strain_misroute": True,
    })
    text = (result.get("assistant_text") or "").lower()
    assert "gg4" not in text
    assert result.get("ui_blocks") in ([], None)
    # It redirects to the actual question instead of answering with cannabis.
    assert "question" in text or "back" in text or "?" in text


@pytest.mark.asyncio
async def test_verdict_refusal_is_not_replaced_by_fallback():
    """The prod incident's third failure: the verdict LLM refused the
    mismatch and the deterministic fallback overrode it with GG4."""
    refusal = ("I need to stop here and be direct: you asked about health "
               "tracking devices, but the strain data is cannabis.")
    with patch("app.services.model_service.model_service.generate_compose",
               new=AsyncMock(return_value=refusal)):
        result = await strain_compose({
            "user_message": UNCLE_QUERY,
            "strain_results": [{"name": "GG4", "type": "hybrid",
                                "effects": ["Relaxed", "Happy", "Euphoric"]}],
        })
    text = (result.get("assistant_text") or "")
    assert "GG4" not in text  # fallback must not resurrect the pick


# ---------------------------------------------------------------------------
# Task 3 — evidence veto on the strain intent (narrow, AI-first preserved)
# ---------------------------------------------------------------------------

from app.agents.intent_agent import veto_strain_intent


def test_vetoes_strain_on_zero_evidence():
    history = [
        {"role": "user", "content": "What's the difference between an apple watch and whoop"},
        {"role": "assistant", "content": "The Apple Watch and Whoop serve different purposes…"},
    ]
    assert veto_strain_intent(UNCLE_QUERY, history) is True


def test_no_veto_when_message_has_cannabis_terms():
    assert veto_strain_intent("sour d vs blue dream", []) is False


def test_no_veto_when_history_is_a_strain_conversation():
    history = [{"role": "user", "content": "best sativa strains for focus"},
               {"role": "assistant", "content": "Durban Poison is the pick…"}]
    assert veto_strain_intent("what about something more relaxing", history) is False
