"""QA remediation (audit 2026-07-31) — sourcing-honesty and safety guardrails.

Three critical findings share one root: the composer writes confident claims it
has no data for.

1. Fabricated safety attributes — a nickel-allergy gift request produced "ships
   with nickel-free hardware as standard, which is genuinely rare at this tier"
   about a right-handed guitar the (left-handed) user could not play. Both
   invented. Acting on that answer can cause an allergic reaction.
2. Invented citations — "came from real user reviews... Two users specifically
   mentioned..." review_search returns aggregate signal only (avg_rating,
   total_reviews, site names). No individual review is ever read. Inventing a
   complaint about a named brand is a legal exposure, not just a trust cost.
3. Silent substitution — asked to finish a cordless-stick recommendation, the
   composer recommended a corded upright with no acknowledgement.

Both sections are appended to the role at the CALL SITE only — the blog_role
string is byte-pinned by the eval prod-sync test, same pattern as
_RELEVANCE_GATE_SECTION and the two-speed LENGTH OVERRIDE.
"""
import os

import pytest

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from mcp_server.tools.product_compose import (  # noqa: E402
    _SOURCING_HONESTY_SECTION,
    _SAFETY_ATTRIBUTE_SECTION,
    _RELEVANCE_GATE_SECTION,
    _consolidated_blog_role,
    _with_guardrails,
)

# A stand-in for the local `blog_role` literal (product_compose.py:1723). The real
# one is a function-local string, so tests exercise the composition helper against
# a role containing the schema tail the transforms operate on.
FAKE_ROLE = '''Write a buying guide for ReviewGuide.ai.

OUTPUT FORMAT:
{
  "follow_up_question": "<one question>",
  "top_pick": "<the EXACT product name of your #1 pick, copied verbatim from the product list — the same product your body names first>"
}'''


class TestSourcingHonesty:
    """The composer must not invent attributions or claim retrieval it never did."""

    @pytest.mark.parametrize("phrase", [
        "never attribute",
        "aggregate",
        "have not read any individual review",
    ])
    def test_forbids_attributing_claims_to_people(self, phrase):
        assert phrase in _SOURCING_HONESTY_SECTION.lower()

    def test_names_the_exact_fabrication_pattern_from_the_audit(self):
        # "Two users specifically mentioned..." is the sentence shape that has to die.
        assert "two users" in _SOURCING_HONESTY_SECTION.lower()

    def test_forbids_claiming_to_search_or_cite(self):
        lowered = _SOURCING_HONESTY_SECTION.lower()
        assert "searched the web" in lowered
        assert "sources" in lowered or "links" in lowered

    def test_requires_english_answers(self):
        # A Spanish query produced a refusal written in Spanish, followed by four
        # fluent Spanish paragraphs promising to answer "en inglés".
        lowered = _SOURCING_HONESTY_SECTION.lower()
        assert "english" in lowered
        assert "refusal" in lowered or "do not open with" in lowered


class TestSafetyAttributes:
    """No unverifiable safety-critical claims, no silent substitutions."""

    @pytest.mark.parametrize("term", [
        "nickel-free",
        "hypoallergenic",
        "left-handed",
        "verify",
    ])
    def test_forbids_unverifiable_safety_attributes(self, term):
        assert term in _SAFETY_ATTRIBUTE_SECTION.lower()

    def test_forbids_dressing_up_an_invented_attribute(self):
        # "which is genuinely rare at this tier" is the flourish that made the
        # invented nickel-free claim persuasive.
        assert "rare at this tier" in _SAFETY_ATTRIBUTE_SECTION.lower()

    @pytest.mark.parametrize("phrase", [
        "substitut",
        "acknowledge",
    ])
    def test_forbids_silent_substitution(self, phrase):
        assert phrase in _SAFETY_ATTRIBUTE_SECTION.lower()

    def test_names_the_cordless_case(self):
        assert "cordless" in _SAFETY_ATTRIBUTE_SECTION.lower()


class TestGuardrailComposition:
    """_with_guardrails is the single call-site entry point."""

    def test_appends_both_sections(self):
        extended = _with_guardrails(FAKE_ROLE)
        assert _SOURCING_HONESTY_SECTION in extended
        assert _SAFETY_ATTRIBUTE_SECTION in extended

    def test_preserves_the_original_role_verbatim(self):
        assert _with_guardrails(FAKE_ROLE).startswith(FAKE_ROLE)

    def test_is_idempotent(self):
        once = _with_guardrails(FAKE_ROLE)
        assert _with_guardrails(once) == once

    def test_appends_each_section_exactly_once(self):
        extended = _with_guardrails(FAKE_ROLE)
        assert extended.count(_SOURCING_HONESTY_SECTION) == 1
        assert extended.count(_SAFETY_ATTRIBUTE_SECTION) == 1


class TestBytePinIsPreserved:
    """The eval prod-sync test pins the role transforms byte-for-byte."""

    def test_consolidated_transform_does_not_carry_the_guardrails(self):
        # If the guardrails leaked into _consolidated_blog_role, the eval's
        # CONSOLIDATED_ROLE comparison would break.
        consolidated = _consolidated_blog_role(FAKE_ROLE)
        assert _SOURCING_HONESTY_SECTION not in consolidated
        assert _SAFETY_ATTRIBUTE_SECTION not in consolidated

    def test_guardrails_survive_the_consolidated_transform(self):
        # Applied AFTER the transform, like _RELEVANCE_GATE_SECTION, so the
        # transform's .replace() on the schema tail cannot mangle them.
        role = _with_guardrails(_consolidated_blog_role(FAKE_ROLE))
        assert _SOURCING_HONESTY_SECTION in role
        assert _SAFETY_ATTRIBUTE_SECTION in role

    def test_composes_with_the_relevance_gate(self):
        role = _with_guardrails(FAKE_ROLE + _RELEVANCE_GATE_SECTION)
        assert _RELEVANCE_GATE_SECTION in role
        assert _SOURCING_HONESTY_SECTION in role


# ---------------------------------------------------------------------------
# Integration — the guardrails must actually reach the model's role prompt.
# Constants that exist but are never wired in protect nobody.
# ---------------------------------------------------------------------------
import json  # noqa: E402
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

from app.core.config import settings  # noqa: E402
from mcp_server.tools.product_compose import product_compose  # noqa: E402


def _offer(name, price, slug):
    return {
        "title": name, "price": price, "currency": "USD",
        "url": f"https://www.amazon.com/dp/{slug}?tag=revguide-20",
        "merchant": "Amazon",
        "image_url": f"https://img.example.com/{slug}.jpg",
        "source": "amazon",
    }


def _state():
    return {
        "user_message": "left-handed beginner guitar, nickel allergy, under $150",
        "intent": "product",
        "slots": {"category": "guitars", "budget": "under $150"},
        "normalized_products": [{"name": "Ibanez GRX70QA", "price": 149, "url": "https://e.com/i"}],
        "affiliate_products": {
            "amazon": [{"product_name": "Ibanez GRX70QA",
                        "offers": [_offer("Ibanez GRX70QA", 149, "ibanez")]}],
        },
        "review_data": {}, "comparison_html": None, "comparison_data": None,
        "general_product_info": "", "conversation_history": [],
        "last_search_context": {}, "search_history": [],
    }


def _capturing_service(captured):
    fake = MagicMock()

    async def _generate_compose(*args, **kwargs):
        captured.append(kwargs)
        if kwargs.get("agent_name") == "blog_article_composer":
            return json.dumps({
                "body": "The Ibanez GRX70QA is the pick.",
                "follow_up_question": "Is this a first guitar?",
                "transitional_reasoning": "",
                "top_pick": "Ibanez GRX70QA",
            })
        return "x"

    fake.generate_compose = AsyncMock(side_effect=_generate_compose)
    return fake


def _role_text(kwargs):
    """Pull the role prompt out of whichever call shape product_compose used."""
    if kwargs.get("role_prompt"):
        return kwargs["role_prompt"]
    return "\n".join(
        m.get("content", "") for m in (kwargs.get("messages") or [])
        if m.get("role") == "system"
    )


@pytest.mark.asyncio
async def test_guardrails_reach_the_composer_role(monkeypatch):
    """Both sections must be present in the role the composer actually sends."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", False)
    for flag in ("USE_DECOUPLED_COMPOSE", "USE_COMPOSE_STREAMING",
                 "USE_GROUNDED_COMPOSE", "USE_VOICE_PASS"):
        monkeypatch.setattr(settings, flag, False, raising=False)

    captured = []
    with patch("app.services.model_service.model_service", _capturing_service(captured)):
        await product_compose(_state())

    roles = [_role_text(k) for k in captured
             if k.get("agent_name") == "blog_article_composer"]
    assert roles, "composer was never called"
    assert any("SOURCING HONESTY" in r for r in roles), "sourcing guardrail never reached the model"
    assert any("SAFETY-CRITICAL ATTRIBUTES" in r for r in roles), "safety guardrail never reached the model"


@pytest.mark.asyncio
async def test_guardrails_reach_the_role_in_consolidated_mode(monkeypatch):
    """Consolidated mode rewrites the schema tail — the guardrails must survive it."""
    monkeypatch.setattr(settings, "USE_CONSOLIDATED_COMPOSE", True)
    for flag in ("USE_DECOUPLED_COMPOSE", "USE_COMPOSE_STREAMING",
                 "USE_GROUNDED_COMPOSE", "USE_VOICE_PASS"):
        monkeypatch.setattr(settings, flag, False, raising=False)

    captured = []
    with patch("app.services.model_service.model_service", _capturing_service(captured)):
        await product_compose(_state())

    roles = [_role_text(k) for k in captured
             if k.get("agent_name") == "blog_article_composer"]
    assert roles, "composer was never called"
    assert any("SOURCING HONESTY" in r for r in roles)
    assert any("SAFETY-CRITICAL ATTRIBUTES" in r for r in roles)


# ---------------------------------------------------------------------------
# Status labels must not claim retrieval either. A tool that generates from the
# model's own knowledge cannot say it pulled receipts — the user reads that
# label, then asks for the sources it implied.
#
# NOT included: general_search, which genuinely retrieves via
# search_manager.search(), and review_search, which genuinely queries SerpAPI
# for rating aggregates. Their labels are honest and stay as they are.
# ---------------------------------------------------------------------------

RETRIEVAL_CLAIM_WORDS = ["receipt", "searching the web", "reading reviews"]

# Tools whose output comes from model knowledge, not from a retrieval call.
GENERATIVE_ONLY_TOOLS = [
    ("product_evidence", "mcp_server.tools.product_evidence"),
    ("product_search", "mcp_server.tools.product_search"),
    ("product_compose", "mcp_server.tools.product_compose"),
    ("product_ranking", "mcp_server.tools.product_ranking"),
]


@pytest.mark.parametrize("tool_name,module_path", GENERATIVE_ONLY_TOOLS)
def test_generative_tools_do_not_claim_retrieval(tool_name, module_path):
    import importlib

    module = importlib.import_module(module_path)
    message = module.TOOL_CONTRACT.get("citation_message", "").lower()
    for claim in RETRIEVAL_CLAIM_WORDS:
        assert claim not in message, (
            f"{tool_name} status label {message!r} claims {claim!r}, "
            "but the tool performs no retrieval"
        )
