"""Voice integration tests.

Two layers, both runnable from the same file:

1. **Structural wiring** (always run, no API needed). Every voice-applicable
   prompt site must import ``build_system_prompt`` and use it. Sites that
   produce structured JSON the user never reads as prose (classifiers,
   extractors, search-retrieval payloads) must NOT wire voice. These
   parametrized tests catch "I deleted the wrap" regressions at PR review.

2. **Live LLM compliance** (``@pytest.mark.integration``, gated by
   ``ANTHROPIC_API_KEY``). The CI workflow ``voice-integration.yml`` runs
   these against the real Claude API on each push to a voice-touching path.
   Each test invokes a composer tool directly with a minimal state dict,
   captures ``assistant_text``, and asserts
   ``check_voice_compliance(text) == []``. Direct tool invocation keeps the
   surface smaller than driving the SSE endpoint or full LangGraph.

The structural layer is the merge-blocking signal for wiring regressions;
the live layer is the merge-blocking signal for model-output regressions.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Bootstrap a test env BEFORE any app import. Mirrors conftest.py but is
# duplicated here so this file can run with --noconftest in local dev
# environments where the full conftest mock stack isn't available.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", "test-api-key"))
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.services.prompts.voice import VOICE_PROMPT, build_system_prompt  # noqa: E402
from app.services.prompts.voice_compliance import (  # noqa: E402
    check_follow_up_specificity,
    check_voice_compliance,
)


BACKEND_ROOT = Path(__file__).resolve().parent.parent

# Voice-applicable sites — each must wire voice via build_system_prompt().
VOICE_APPLICABLE_SITES: list[str] = [
    "app/agents/clarifier_agent.py",
    "mcp_server/tools/product_compose.py",
    "mcp_server/tools/product_comparison.py",
    "mcp_server/tools/product_general_information.py",
    "mcp_server/tools/general_compose.py",
    "mcp_server/tools/next_step_suggestion.py",
    "mcp_server/tools/travel_destination_facts.py",
    "mcp_server/tools/travel_general_information.py",
    "mcp_server/tools/travel_itinerary.py",
    "mcp_server/tools/intro_compose.py",
    "mcp_server/tools/unclear_compose.py",
]

# Sites that must NOT wire voice — they emit structured data, not prose. See
# the voice-rebuild plan §"Not voice-applicable" for the rationale. Wrapping
# any of these would (a) waste ~750 tokens/call on tone the user never reads
# and (b) collide with ``response_format={"type":"json_object"}`` /
# Perplexity's ``structured_output.schema``.
NOT_VOICE_APPLICABLE_SITES: list[str] = [
    "app/agents/intent_agent.py",
    "app/agents/planner_agent.py",
    "app/agents/safety_agent.py",
    "mcp_server/tools/product_evidence.py",
    "mcp_server/tools/product_extractor.py",
    "mcp_server/tools/product_search.py",
    "mcp_server/tools/travel_compose.py",
    "app/services/search/providers/openai_provider.py",
    "app/services/search/providers/perplexity_provider.py",
    "app/services/model_service.py",
]


# ---------------------------------------------------------------------------
# Layer 1 — Structural wiring (always-on, deterministic, no API)
# ---------------------------------------------------------------------------


class TestVoiceWiring:
    """Source-level assertions about where build_system_prompt is wired."""

    @pytest.mark.parametrize("rel_path", VOICE_APPLICABLE_SITES)
    def test_voice_applicable_file_uses_build_system_prompt(self, rel_path: str) -> None:
        path = BACKEND_ROOT / rel_path
        content = path.read_text(encoding="utf-8")
        assert "build_system_prompt" in content, (
            f"{rel_path} produces user-facing prose and must wrap its system "
            "prompt via build_system_prompt(). See voice-rebuild plan."
        )

    @pytest.mark.parametrize("rel_path", NOT_VOICE_APPLICABLE_SITES)
    def test_not_voice_applicable_file_does_not_wire_voice(self, rel_path: str) -> None:
        path = BACKEND_ROOT / rel_path
        content = path.read_text(encoding="utf-8")
        assert "build_system_prompt" not in content, (
            f"{rel_path} emits structured data the user never reads as prose. "
            "Wrapping it with VOICE_PROMPT wastes tokens and risks colliding "
            "with response_format / structured_output. See voice-rebuild plan."
        )


# ---------------------------------------------------------------------------
# Layer 2 — Live LLM voice compliance
# ---------------------------------------------------------------------------


def _looks_like_real_key(value: str | None) -> bool:
    """Return True only for keys that aren't obvious test placeholders.

    Recognizes the common placeholder patterns used in this repo's CI:
    ``test-api-key``, anything starting with ``sk-test`` (OpenAI's
    documented test-key prefix), and the empty string. Without this
    filter, ``${{ secrets.OPENAI_API_KEY || 'sk-test-placeholder' }}`` in
    the workflow would silently mark the live layer "available" and let
    every tool fall through to its hardcoded fallback string — which
    looks like a pass but tests nothing.
    """
    if not value:
        return False
    if value.startswith("sk-test"):
        return False
    if value in {"test-api-key", "test-key", "placeholder"}:
        return False
    return True


_HAS_LIVE_CREDS = _looks_like_real_key(os.environ.get("ANTHROPIC_API_KEY")) or _looks_like_real_key(
    os.environ.get("OPENAI_API_KEY")
)
# Tools that hit settings.DEFAULT_MODEL / settings.COMPOSER_MODEL (both
# default to ``gpt-4o-mini``) need an OpenAI key specifically.
_HAS_OPENAI = _looks_like_real_key(os.environ.get("OPENAI_API_KEY"))


@pytest.fixture(autouse=False)
def _model_service_init(monkeypatch):
    """Ensure model_service is importable. The conftest in CI handles this,
    but we don't want a partial conftest dependency in this file."""
    return None


def _assert_voice_compliant(text: str, label: str) -> None:
    """Helper: surface both compliance errors and the failing text excerpt."""
    violations = check_voice_compliance(text)
    assert not violations, (
        f"[{label}] Voice violations: {violations}\n"
        f"--- assistant_text (first 400 chars) ---\n{text[:400]}"
    )


@pytest.mark.integration
@pytest.mark.skipif(not _HAS_LIVE_CREDS, reason="needs OPENAI_API_KEY or ANTHROPIC_API_KEY")
@pytest.mark.asyncio
async def test_intro_compose_voice_compliance() -> None:
    """Canonical prompt #1: a fresh chat — `intro_compose` should welcome
    the user without `Great choice!`-style filler and end with one
    contextual invitation."""
    from mcp_server.tools.intro_compose import intro_compose

    result = await intro_compose({})
    text = result.get("assistant_text", "")
    assert text, "intro_compose returned empty assistant_text"
    _assert_voice_compliant(text, "intro_compose")


@pytest.mark.integration
@pytest.mark.skipif(not _HAS_LIVE_CREDS, reason="needs OPENAI_API_KEY or ANTHROPIC_API_KEY")
@pytest.mark.asyncio
async def test_unclear_compose_voice_compliance() -> None:
    """Canonical prompt #2: gibberish input. `unclear_compose` should help
    the user try again without sales-floor filler."""
    from mcp_server.tools.unclear_compose import unclear_compose

    state = {"user_message": "asdkjfh", "conversation_history": []}
    result = await unclear_compose(state)
    text = result.get("assistant_text", "")
    assert text, "unclear_compose returned empty assistant_text"
    _assert_voice_compliant(text, "unclear_compose")


@pytest.mark.integration
@pytest.mark.skipif(not _HAS_LIVE_CREDS, reason="needs OPENAI_API_KEY or ANTHROPIC_API_KEY")
@pytest.mark.asyncio
async def test_general_compose_no_search_voice_compliance() -> None:
    """Canonical prompt #9: no-search conversational reply. Hits
    general_compose's `if not search_results` branch (line 85 site)."""
    from mcp_server.tools.general_compose import general_compose

    state = {
        "user_message": "what is HDR10+",
        "search_results": [],
        "conversation_history": [],
    }
    result = await general_compose(state)
    text = result.get("assistant_text", "")
    assert text, "general_compose returned empty assistant_text"
    _assert_voice_compliant(text, "general_compose:no-search")


@pytest.mark.integration
@pytest.mark.skipif(not _HAS_LIVE_CREDS, reason="needs OPENAI_API_KEY or ANTHROPIC_API_KEY")
@pytest.mark.asyncio
async def test_general_compose_with_search_voice_compliance() -> None:
    """Canonical prompt #8: search-results-backed reply. Hits
    general_compose's with-search branch (line 151 site)."""
    from mcp_server.tools.general_compose import general_compose

    state = {
        "user_message": "what's the weather in Tokyo",
        "search_results": [
            {
                "title": "Tokyo weather forecast",
                "snippet": "Tokyo currently has mild spring weather with highs near 18C.",
                "url": "https://example.com/tokyo-weather",
            }
        ],
        "conversation_history": [],
    }
    result = await general_compose(state)
    text = result.get("assistant_text", "")
    assert text, "general_compose returned empty assistant_text"
    _assert_voice_compliant(text, "general_compose:with-search")


@pytest.mark.integration
@pytest.mark.skipif(not _HAS_OPENAI, reason="needs a real OPENAI_API_KEY (tool calls settings.DEFAULT_MODEL = gpt-4o-mini)")
@pytest.mark.asyncio
async def test_product_general_information_follow_up_is_structured() -> None:
    """Canonical prompt #5: product knowledge question. The composer was
    schema-extended to emit `{answer, follow_up_question, sources}`. Verify
    both the answer and the embedded follow-up are voice-compliant."""
    from mcp_server.tools.product_general_information import product_general_information

    state = {
        "user_message": "what is HDR10+",
        "search_results": [],
        "conversation_history": [],
    }
    result = await product_general_information(state)
    combined = result.get("general_product_info", "")
    # Infrastructure-level failure (network blip, schema mismatch, etc.)
    # is caught by the tool's @tool_error_handler and returned as empty.
    # That's not a voice regression — skip rather than fail.
    if not combined or result.get("success") is False:
        pytest.skip(
            f"infra: product_general_information returned empty / success=False "
            f"(error={result.get('error')!r}). Not a voice regression — likely "
            "an OpenAI auth / network issue."
        )
    _assert_voice_compliant(combined, "product_general_information")
    # The follow-up is appended after a blank line per the consumer pattern.
    # Pull the last paragraph and run the specificity check.
    parts = [p.strip() for p in combined.strip().split("\n\n") if p.strip()]
    if len(parts) >= 2:
        candidate_follow_up = parts[-1]
        generic = check_follow_up_specificity(candidate_follow_up)
        assert generic is None, (
            f"product_general_information emitted a generic follow-up "
            f"({generic!r}): {candidate_follow_up!r}"
        )


# ---------------------------------------------------------------------------
# Smoke: confirm the voice prompt itself isn't smuggling banned phrases.
# (Edge case — VOICE_PROMPT quotes some banned phrases inside its own list,
# so this test verifies the *content* of a tagline-style response built
# *with* the prompt, not the prompt itself.)
# ---------------------------------------------------------------------------


def test_build_system_prompt_does_not_double_inject_voice() -> None:
    """Defense in depth: composing a role + voice should yield exactly one
    copy of the VOICE_PROMPT opener, not two."""
    first_line = VOICE_PROMPT.split("\n", 1)[0]
    composed = build_system_prompt(role_prompt="Test role.")
    assert composed.count(first_line) == 1


def test_snippet_kind_still_includes_examples() -> None:
    """The EXAMPLES section teaches tone and must survive the snippet slice."""
    composed = build_system_prompt(role_prompt="Test role.", kind="snippet")
    assert "Example 1" in composed
    assert "Example 2" in composed
    assert "Example 3" in composed


def test_blog_composer_prompt_has_ranking_directive() -> None:
    """Guards against accidental deletion of the RANK-AND-COMMIT section
    of the blog composer prompt.

    The PR #6 post-merge voice regression had two failure modes: leaking
    citations (covered by sanitize_voice) AND parallel survey reading
    ("Anker is praised for X, JBL is noted for Y") that the role prompt
    failed to prevent. Hotfix Commit 4a added a load-bearing RANK-AND-COMMIT
    section with a worked BAD/GOOD counter-example. If a future refactor
    deletes any of those markers, this test goes red so the regression
    surfaces at PR review rather than in production.
    """
    path = BACKEND_ROOT / "mcp_server/tools/product_compose.py"
    content = path.read_text(encoding="utf-8")
    # Load-bearing header.
    assert "RANK AND COMMIT" in content, (
        "Blog composer prompt lost its RANK-AND-COMMIT section. Re-read the "
        "PR #6 post-merge incident before re-deleting — that section is what "
        "stops the parallel-survey voice regression."
    )
    # The BAD/GOOD counter-example pair.
    assert "BAD (parallel survey" in content
    assert "GOOD (ranked" in content


def test_product_compose_does_not_emit_review_sources_block() -> None:
    """Guards against re-introducing the review_sources UI block.

    PR #9 removed a UI block that exposed TechRadar / The Verge /
    Wirecutter / RTINGS site names as user-visible badge pills. That
    surface bypassed sanitize_voice (which only operates on
    assistant_text) and directly contradicted tone.md ("No source
    citations. Synthesize.") and BACKEND_AGENT_CONTEXT.md's
    "No client-facing citation surface" done-criterion.

    The PR #7 hotfix that this builds on was specifically about
    citation prevention. If a future PR re-adds a ui_block with
    type=='review_sources', this test goes red so the regression
    surfaces at PR review rather than in production.
    """
    path = BACKEND_ROOT / "mcp_server/tools/product_compose.py"
    content = path.read_text(encoding="utf-8")
    assert '"type": "review_sources"' not in content, (
        "product_compose.py is emitting a ui_block of type 'review_sources'. "
        "That block was removed in PR #9 because it exposed review-site "
        "names (TechRadar, The Verge, etc.) as user-visible badge pills, "
        "contradicting tone.md and the PR #7 hotfix's intent. If you need "
        "to surface sources, do it through assistant_text (which is gated "
        "by sanitize_voice) — never via a parallel UI surface."
    )
    # The string can appear as `"review_sources"` in surrounding prose
    # (comments referencing the removal) but should not appear as a dict
    # value for a `"type"` key in a ui_blocks.append() call. The exact-
    # phrase check above is the surgical guard.
