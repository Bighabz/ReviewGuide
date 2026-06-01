"""Tests for compose model routing (OpenRouter vs OpenAI).

Covers the data-backed switch that routes compose calls to Claude Haiku 4.5 via
OpenRouter (bake-off winner) while preserving the OpenAI fallback. The critical
invariant: when OpenRouter compose is active it must pass ``response_format``
THROUGH (json_object), unlike the legacy native-Anthropic path which force-fell
back to OpenAI on JSON mode (model_service.py).

No network: we patch ModelService.generate and inspect how generate_compose
dispatches to it.
"""
from unittest.mock import AsyncMock

from app.core.config import settings
from app.services.model_service import ModelService


async def test_compose_routes_to_openrouter_and_passes_json_through(monkeypatch):
    """Flag on + key present → OpenRouter model, base_url, key, and json_object preserved."""
    monkeypatch.setattr(settings, "USE_OPENROUTER_COMPOSE", True)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(settings, "OPENROUTER_COMPOSE_MODEL", "anthropic/claude-haiku-4.5")

    svc = ModelService()
    svc.generate = AsyncMock(return_value='{"body": "ok"}')

    out = await svc.generate_compose(
        messages=[{"role": "user", "content": "best earbuds under $100"}],
        temperature=0.7,
        max_tokens=700,
        agent_name="blog_article",
        response_format={"type": "json_object"},
    )

    assert out == '{"body": "ok"}'
    kwargs = svc.generate.call_args.kwargs
    assert kwargs["model"] == "anthropic/claude-haiku-4.5"
    assert kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert kwargs["api_key"] == "sk-or-test"
    # The fix: json_object is forwarded, not stripped/force-fallen-back to OpenAI.
    assert kwargs["response_format"] == {"type": "json_object"}


async def test_compose_falls_back_to_openai_when_unkeyed(monkeypatch):
    """Flag on but no OpenRouter key → safe no-op to OpenAI COMPOSER_MODEL."""
    monkeypatch.setattr(settings, "USE_OPENROUTER_COMPOSE", True)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "")
    monkeypatch.setattr(settings, "COMPOSER_MODEL", "gpt-4o-mini")

    svc = ModelService()
    svc.generate = AsyncMock(return_value='{"body": "fallback"}')

    await svc.generate_compose(
        messages=[{"role": "user", "content": "hi"}],
        response_format={"type": "json_object"},
    )

    kwargs = svc.generate.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs.get("base_url") is None
    assert kwargs["response_format"] == {"type": "json_object"}


async def test_compose_flag_off_uses_openai_even_with_key(monkeypatch):
    """Flag off → OpenAI path, even if an OpenRouter key happens to be present."""
    monkeypatch.setattr(settings, "USE_OPENROUTER_COMPOSE", False)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr(settings, "COMPOSER_MODEL", "gpt-4o-mini")

    svc = ModelService()
    svc.generate = AsyncMock(return_value="plain")

    await svc.generate_compose(messages=[{"role": "user", "content": "hi"}])

    kwargs = svc.generate.call_args.kwargs
    assert kwargs["model"] == "gpt-4o-mini"
    assert kwargs.get("base_url") is None


async def test_openrouter_compose_strips_json_code_fence(monkeypatch):
    """Anthropic-via-OpenRouter wraps JSON in a ```json fence even in json_object mode;
    generate_compose must strip it so product_compose's json.loads succeeds.
    (Caught by a live smoke test — the eval's lenient parser had masked it.)"""
    import json

    monkeypatch.setattr(settings, "USE_OPENROUTER_COMPOSE", True)
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "sk-or-test")
    monkeypatch.setattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setattr(settings, "OPENROUTER_COMPOSE_MODEL", "anthropic/claude-haiku-4.5")

    fenced = '```json\n{"body": "The pick is X.", "follow_up_question": "Commute or gym?"}\n```'
    svc = ModelService()
    svc.generate = AsyncMock(return_value=fenced)

    out = await svc.generate_compose(
        messages=[{"role": "user", "content": "earbuds"}],
        response_format={"type": "json_object"},
    )

    assert not out.lstrip().startswith("```")
    parsed = json.loads(out)
    assert parsed["body"] == "The pick is X."
    assert parsed["follow_up_question"] == "Commute or gym?"


def test_strip_json_fence_variants():
    f = ModelService._strip_json_fence
    assert f('{"a": 1}') == '{"a": 1}'
    assert f('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert f('```\n{"a": 1}\n```') == '{"a": 1}'
    assert f('  {"a": 1}  ') == '{"a": 1}'
    assert f('') == ''
