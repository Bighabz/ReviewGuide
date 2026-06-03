"""
Model Service with LangChain ChatOpenAI Integration
Provides model routing and generation. All observability is handled by Langfuse CallbackHandler.
"""
from app.core.centralized_logger import get_logger
import asyncio
import hashlib
import json
from typing import Optional, Dict, AsyncGenerator
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models.chat_models import BaseChatModel
from app.core.config import settings
from app.core.colored_logging import get_colored_logger

logger = get_logger(__name__)
colored_logger = get_colored_logger(__name__)

# Known model context window sizes (used to normalize max_tokens in cache keys)
_MODEL_DEFAULTS: dict[str, int] = {
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gpt-4-turbo": 128000,
    "gpt-4": 8192,
    "gpt-3.5-turbo": 16385,
}
_DEFAULT_MAX_TOKENS = 128000  # fallback for unknown models


class ModelService:
    """Service for LLM interactions. All observability handled by Langfuse CallbackHandler."""

    # Type annotations only — no default assignment at class level.
    # asyncio.Semaphore must not be instantiated at import time (before an
    # event loop exists).  Each instance owns its own semaphores; because
    # the application uses a single global ``model_service`` singleton the
    # concurrency limits are still effectively process-wide.
    _streaming_semaphore: asyncio.Semaphore
    _sync_semaphore: asyncio.Semaphore

    def __init__(self):
        self._llm_cache: dict = {}
        # Separate semaphores for streaming vs non-streaming to prevent
        # head-of-line blocking.  Created here (not at class level) so that
        # no Semaphore is instantiated before an event loop is running.
        self._streaming_semaphore = asyncio.Semaphore(10)   # max 10 concurrent streaming calls
        self._sync_semaphore = asyncio.Semaphore(25)        # max 25 concurrent non-streaming calls

    @property
    def _api_key_fingerprint(self) -> str:
        """Return first 8 hex chars of SHA-256 of the current API key.

        Embedding this in the cache key ensures that rotating the API key
        forces all cached ChatOpenAI instances (which hold the old key) to
        be evicted and recreated with the new credential.
        """
        api_key = getattr(settings, 'OPENAI_API_KEY', '') or ''
        return hashlib.sha256(api_key.encode()).hexdigest()[:8]

    @staticmethod
    def _canonical_key(
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        json_mode: bool,
        stream: bool,
        api_key_fingerprint: str,
        base_url: Optional[str] = None,
    ) -> tuple:
        """Build a normalized cache key that avoids spurious misses.

        Normalizations applied:
        - ``max_tokens``: if the caller passes ``None`` *or* the model's own
          default context length, both collapse to ``None`` — same instance.
        - ``temperature``: rounded to one decimal place so ``0.7`` and ``0.70``
          resolve to the same bucket.
        - ``api_key_fingerprint``: invalidates the entry on key rotation.
        """
        model_default = _MODEL_DEFAULTS.get(model, _DEFAULT_MAX_TOKENS)
        effective_max = max_tokens if (max_tokens is not None and max_tokens > 0 and max_tokens < model_default) else None
        effective_temp = round(temperature, 1)
        return (model, effective_temp, effective_max, json_mode, stream, api_key_fingerprint, base_url)

    @staticmethod
    def _strip_json_fence(text: str) -> str:
        """Strip a markdown code fence (```json … ```) wrapping a JSON payload.

        Anthropic models served via OpenRouter emit a fenced block even when
        ``response_format={"type": "json_object"}`` is requested (OpenRouter
        cannot enforce OpenAI-style JSON mode on them). product_compose calls
        ``json.loads`` on the compose output, so the fence must be removed or the
        blog/descriptions/top_pick parse fails and falls back to raw text.
        """
        if not text:
            return text
        s = text.strip()
        if not s.startswith("```"):
            return s
        nl = s.find("\n")
        s = s[nl + 1:] if nl != -1 else s.lstrip("`")
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
        return s.strip()

    def _get_llm(
        self,
        model: str,
        temperature: float,
        max_tokens: Optional[int],
        json_mode: bool,
        stream: bool,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> ChatOpenAI:
        """Get or create a cached ChatOpenAI instance.

        Instances are cached by a canonical key (model, temperature, max_tokens,
        json_mode, stream, api_key_fingerprint, base_url) so HTTP connections are
        reused via the underlying httpx.AsyncClient.

        ``base_url`` + ``api_key`` let a caller target an OpenAI-compatible endpoint
        other than OpenAI (e.g. OpenRouter for compose). When omitted, the default
        OpenAI credentials are used. The fingerprint is derived from the *effective*
        key so rotating either credential evicts the right cached instances.
        """
        effective_key = api_key or settings.OPENAI_API_KEY
        # Default (OpenAI) path uses the _api_key_fingerprint property so existing
        # cache-rotation behaviour and tests are preserved; an explicit api_key
        # override (e.g. OpenRouter) fingerprints that key instead.
        fingerprint = (
            hashlib.sha256(api_key.encode()).hexdigest()[:8]
            if api_key
            else self._api_key_fingerprint
        )
        cache_key = self._canonical_key(model, temperature, max_tokens, json_mode, stream, fingerprint, base_url)
        if cache_key not in self._llm_cache:
            kwargs: dict = {
                "model": model,
                "openai_api_key": effective_key,
                "streaming": stream,
                "request_timeout": 12,    # Hard cap: no single LLM call waits > 12s
                "max_retries": 1,         # One retry on transient failure (12s × 2 = 24s worst case, fits 15s tool timeout on first attempt)
            }
            if base_url:
                kwargs["openai_api_base"] = base_url
            # o3 models don't support temperature parameter
            if not model.startswith("o3"):
                kwargs["temperature"] = temperature
            if max_tokens:
                kwargs["max_tokens"] = max_tokens
            if json_mode:
                kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
            self._llm_cache[cache_key] = ChatOpenAI(**kwargs)
            logger.info(f"[model_service] Created new ChatOpenAI instance (cache size: {len(self._llm_cache)})")
        return self._llm_cache[cache_key]

    # ------------------------------------------------------------------
    # Compose methods (ported 2026-04-21 from v3 commits 6cde1a6 + a4013da).
    # These MUST exist because product_compose.py lines 621/657/717/839/888
    # call model_service.generate_compose() and generate_compose_with_streaming().
    # The callsites landed in v2-with-swipe (4a544d7, 4cb253a, b30e861) but
    # the methods themselves were on v3-full-implementation and never cherry-
    # picked — producing AttributeError at runtime on every product query.
    # ------------------------------------------------------------------

    def get_compose_model(self) -> BaseChatModel:
        """Return the LLM instance for compose operations.

        When ``USE_ANTHROPIC_COMPOSE`` is enabled and an Anthropic API key is
        configured, returns a ``ChatAnthropic`` (Claude Haiku 4.5) instance.
        Otherwise falls back to the existing ``ChatOpenAI`` path using
        ``COMPOSER_MODEL``.
        """
        if getattr(settings, "USE_ANTHROPIC_COMPOSE", False) and getattr(settings, "ANTHROPIC_API_KEY", ""):
            cache_key = ("anthropic_compose", getattr(settings, "FAST_ROUTER_MODEL", "claude-haiku-4-5-20251001"))
            if cache_key not in self._llm_cache:
                from langchain_anthropic import ChatAnthropic
                self._llm_cache[cache_key] = ChatAnthropic(
                    model=getattr(settings, "FAST_ROUTER_MODEL", "claude-haiku-4-5-20251001"),
                    anthropic_api_key=settings.ANTHROPIC_API_KEY,
                    max_tokens=4096,
                    temperature=0.7,
                    streaming=True,
                )
                logger.info(f"[model_service] Created ChatAnthropic compose instance (cache size: {len(self._llm_cache)})")
            return self._llm_cache[cache_key]
        # Fall back to existing ChatOpenAI with COMPOSER_MODEL
        return self._get_llm(
            model=settings.COMPOSER_MODEL,
            temperature=0.7,
            max_tokens=None,
            json_mode=False,
            stream=False,
        )

    async def generate_compose(
            self,
            messages: list[Dict[str, str]],
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            agent_name: Optional[str] = None,
            session_id: Optional[str] = None,
            response_format: Optional[Dict[str, str]] = None,
            callbacks: Optional[list] = None,
    ) -> str:
        """Generate a completion using the compose model (Anthropic or OpenAI).

        Mirrors ``generate()``. When ``USE_ANTHROPIC_COMPOSE`` is off (default),
        delegates to ``generate()`` with ``COMPOSER_MODEL`` — i.e. the original
        OpenAI path. This keeps the call sites in product_compose / general_compose
        working whether or not the Anthropic flag is set.
        """
        # OpenRouter compose route (data-backed: Haiku 4.5 won the voice bake-off on
        # quality + latency and handles json_object cleanly via OpenRouter). Takes
        # precedence over the native-Anthropic path and, unlike it, passes
        # response_format through. No-ops when unkeyed → OpenAI fallback below.
        use_openrouter = (
            getattr(settings, "USE_OPENROUTER_COMPOSE", False)
            and getattr(settings, "OPENROUTER_API_KEY", "")
        )
        if use_openrouter:
            model_name = getattr(settings, "OPENROUTER_COMPOSE_MODEL", "anthropic/claude-haiku-4.5")
            content = await self.generate(
                messages=messages,
                model=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                agent_name=agent_name,
                session_id=session_id,
                response_format=response_format,
                callbacks=callbacks,
                base_url=settings.OPENROUTER_BASE_URL,
                api_key=settings.OPENROUTER_API_KEY,
            )
            # OpenRouter-served Anthropic models wrap JSON in a ```json fence even
            # in json_object mode; strip it so downstream json.loads succeeds.
            if response_format and response_format.get("type") == "json_object":
                content = self._strip_json_fence(content)
            logger.info(json.dumps({
                "event": "model_call", "agent": agent_name or "unknown",
                "model": model_name, "session_id": session_id, "provider": "openrouter",
            }))
            return content

        use_anthropic = (
            getattr(settings, "USE_ANTHROPIC_COMPOSE", False)
            and getattr(settings, "ANTHROPIC_API_KEY", "")
        )
        # Flag off, or JSON-mode requested (Anthropic doesn't support OpenAI's
        # response_format the same way) → use existing OpenAI generate().
        if not use_anthropic or (response_format and response_format.get("type") == "json_object"):
            return await self.generate(
                messages=messages,
                model=settings.COMPOSER_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                agent_name=agent_name,
                session_id=session_id,
                response_format=response_format,
                callbacks=callbacks,
            )

        try:
            llm = self.get_compose_model()
            lc_messages = self._convert_messages(messages)
            model_name = getattr(settings, "FAST_ROUTER_MODEL", "claude-haiku-4-5-20251001")
            async with self._sync_semaphore:
                if callbacks:
                    response = await llm.ainvoke(lc_messages, config={"callbacks": callbacks})
                else:
                    response = await llm.ainvoke(lc_messages)
            content = response.content
            logger.info(json.dumps({
                "event": "model_call", "agent": agent_name or "unknown",
                "model": model_name, "session_id": session_id, "provider": "anthropic",
            }))
            return content
        except Exception as e:
            logger.error(json.dumps({
                "event": "model_error", "agent": agent_name or "unknown",
                "model": getattr(settings, "FAST_ROUTER_MODEL", "?"),
                "error": str(e), "session_id": session_id, "provider": "anthropic",
            }))
            raise

    async def generate_compose_with_streaming(
            self,
            messages: list[Dict[str, str]],
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            agent_name: Optional[str] = None,
    ) -> str:
        """Generate a compose completion while streaming tokens via LangGraph custom events.

        Uses ``llm.astream()`` for incremental tokens dispatched as ``stream_token``
        custom events. Falls back to ``generate_compose()`` if streaming setup fails.
        """
        try:
            from langchain_core.callbacks.manager import adispatch_custom_event
        except ImportError:
            logger.debug("adispatch_custom_event not available, falling back to non-streaming")
            return await self.generate_compose(
                messages=messages, temperature=temperature,
                max_tokens=max_tokens, agent_name=agent_name,
            )
        use_openrouter = (
            getattr(settings, "USE_OPENROUTER_COMPOSE", False)
            and getattr(settings, "OPENROUTER_API_KEY", "")
        )
        use_anthropic = (
            getattr(settings, "USE_ANTHROPIC_COMPOSE", False)
            and getattr(settings, "ANTHROPIC_API_KEY", "")
        )
        try:
            if use_openrouter:
                llm = self._get_llm(
                    model=settings.OPENROUTER_COMPOSE_MODEL,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=False,
                    stream=True,
                    base_url=settings.OPENROUTER_BASE_URL,
                    api_key=settings.OPENROUTER_API_KEY,
                )
            elif use_anthropic:
                llm = self.get_compose_model()
            else:
                llm = self._get_llm(model=settings.COMPOSER_MODEL, temperature=temperature)
            lc_messages = self._convert_messages(messages)
            full_text_parts: list[str] = []
            # Tier 2.1: in the decoupled format the prose body comes first, then a
            # `<data>` tail with the structured JSON. Only the prose should reach
            # the user as streamed tokens — stop dispatching once the tail marker
            # appears (the full text, tail included, is still returned for parsing).
            _DATA_MARKER = "<data>"
            _emitted_len = 0  # chars of (prose) already dispatched
            _tail_started = False

            async def _emit(content: str) -> None:
                nonlocal _emitted_len, _tail_started
                full_text_parts.append(content)
                if _tail_started:
                    return
                joined = "".join(full_text_parts)
                marker = joined.find(_DATA_MARKER)
                # Dispatch only up to the marker (or all of it so far if no marker yet).
                if marker != -1:
                    visible_end = marker
                else:
                    # No full marker yet — but the marker can split across chunks
                    # (e.g. "...<dat" then "a>..."). Hold back any trailing suffix
                    # that is a prefix of the marker so a partial "<data" never
                    # leaks to the user; it resolves once more text arrives.
                    visible_end = len(joined)
                    for k in range(min(len(_DATA_MARKER) - 1, len(joined)), 0, -1):
                        if joined.endswith(_DATA_MARKER[:k]):
                            visible_end = len(joined) - k
                            break
                if visible_end > _emitted_len:
                    delta = joined[_emitted_len:visible_end]
                    if delta:
                        try:
                            await adispatch_custom_event("stream_token", {"token": delta})
                        except Exception:
                            pass
                    _emitted_len = visible_end
                if marker != -1:
                    _tail_started = True  # stop emitting; tail is structured data

            # Semaphore name varies across versions — guard if attribute missing.
            _sema = getattr(self, "_streaming_semaphore", None) or getattr(self, "_sync_semaphore", None)
            if _sema is not None:
                async with _sema:
                    async for chunk in llm.astream(lc_messages):
                        if chunk.content:
                            await _emit(chunk.content)
            else:
                async for chunk in llm.astream(lc_messages):
                    if chunk.content:
                        await _emit(chunk.content)
            result = "".join(full_text_parts)
            if agent_name:
                logger.info(f"[{agent_name}] Streamed {len(result)} chars ({len(full_text_parts)} chunks)")
            return result
        except Exception as e:
            logger.warning(f"Streaming compose failed ({e}), falling back to non-streaming")
            return await self.generate_compose(
                messages=messages, temperature=temperature,
                max_tokens=max_tokens, agent_name=agent_name,
            )

    def invalidate_cache(self, reason: str = "manual") -> int:
        """Clear all cached LLM instances.

        Returns:
            Number of instances that were evicted.
        """
        count = len(self._llm_cache)
        self._llm_cache.clear()
        logger.info(f"[model_service] Cache invalidated: {count} instances cleared, reason={reason}")
        return count

    def _convert_messages(self, messages: list[Dict[str, str]]):
        """Convert dict messages to LangChain message objects"""
        converted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                converted.append(SystemMessage(content=content))
            elif role == "assistant":
                converted.append(AIMessage(content=content))
            else:  # user or any other role
                converted.append(HumanMessage(content=content))

        return converted

    async def generate(
            self,
            messages: list[Dict[str, str]],
            model: str = None,
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            stream: bool = False,
            agent_name: Optional[str] = None,
            session_id: Optional[str] = None,
            response_format: Optional[Dict[str, str]] = None,
            callbacks: Optional[list] = None,
            base_url: Optional[str] = None,
            api_key: Optional[str] = None,
    ) -> str | AsyncGenerator[str, None]:
        """
        Generate completion with unified Langfuse tracing via callbacks.

        Langfuse tracing is handled automatically via the callbacks parameter.
        The langfuse_handler from chat.py is passed through LangGraph context,
        ensuring all LLM calls (from agents and tools) are traced in a single unified trace.

        Streaming calls acquire ``_streaming_semaphore`` (limit 10 concurrent).
        Non-streaming calls acquire ``_sync_semaphore`` (limit 25 concurrent).

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier (defaults to settings.DEFAULT_MODEL)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            agent_name: Name of the calling agent (for tracking)
            session_id: Session ID (for tracking)
            response_format: Response format (e.g., {"type": "json_object"})
            callbacks: LangChain callbacks (contains langfuse_handler for unified tracing)

        Returns:
            Generated text or async generator for streaming
        """
        try:
            # Use DEFAULT_MODEL from settings if model not specified
            if model is None:
                model = settings.DEFAULT_MODEL

            # Convert messages to LangChain format
            lc_messages = self._convert_messages(messages)

            # Get cached LLM instance (enables HTTP connection pooling)
            json_mode = bool(response_format and response_format.get("type") == "json_object")
            llm = self._get_llm(model, temperature, max_tokens, json_mode, stream, base_url=base_url, api_key=api_key)

            # Log API input (YELLOW)
            colored_logger.api_input(
                {
                    "model": model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "messages": [{"role": m.type, "content": m.content[:100] + "..." if len(m.content) > 100 else m.content} for m in lc_messages]
                },
                endpoint=f"OpenAI Chat ({model})",
                agent=agent_name or "unknown"
            )

            # Langfuse tracing is now handled automatically via callbacks
            # No need to manually create Langfuse client since we're in the same process
            # The langfuse_handler from chat.py will capture all LLM calls via callbacks
            logger.debug(f"[model_service] {agent_name or 'unknown'}: callbacks={len(callbacks) if callbacks else 0}")

            if stream:
                return self._stream_response(
                    llm, lc_messages, model, agent_name, session_id
                )
            else:
                # Acquire the non-streaming concurrency semaphore before calling the API
                async with self._sync_semaphore:
                    # Make API call with callbacks (langfuse_handler will capture automatically)
                    if callbacks:
                        response = await llm.ainvoke(lc_messages, config={"callbacks": callbacks})
                    else:
                        # If no callbacks provided, call without config (will still be traced if in LangGraph context)
                        response = await llm.ainvoke(lc_messages)

                # Extract content
                content = response.content

                # Log API output (YELLOW) - token/cost details available in Langfuse
                colored_logger.api_output(
                    {
                        "content_preview": content[:200] + "..." if len(content) > 200 else content,
                    },
                    endpoint=f"OpenAI Chat ({model})",
                    agent=agent_name or "unknown"
                )

                # Structured JSON logging
                logger.info(
                    json.dumps({
                        "event": "model_call",
                        "agent": agent_name or "unknown",
                        "model": model,
                        "session_id": session_id,
                    })
                )

                return content

        except Exception as e:
            logger.error(
                json.dumps({
                    "event": "model_error",
                    "agent": agent_name or "unknown",
                    "model": model,
                    "error": str(e),
                    "session_id": session_id,
                })
            )
            raise

    async def _stream_response(
            self,
            llm: ChatOpenAI,
            messages,
            model: str,
            agent_name: Optional[str] = None,
            session_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens. Token/cost tracking handled by Langfuse CallbackHandler.

        Acquires ``_streaming_semaphore`` for the full duration of the stream to
        cap concurrent open HTTP/SSE connections.
        """
        async with self._streaming_semaphore:
            try:
                # Langfuse CallbackHandler is inherited from LangGraph context automatically
                async for chunk in llm.astream(messages):
                    if chunk.content:
                        yield chunk.content

                logger.info(
                    json.dumps({
                        "event": "model_stream_complete",
                        "agent": agent_name or "unknown",
                        "model": model,
                        "session_id": session_id,
                    })
                )

            except Exception as e:
                logger.error(
                    json.dumps({
                        "event": "streaming_error",
                        "agent": agent_name or "unknown",
                        "model": model,
                        "error": str(e),
                        "session_id": session_id,
                    })
                )
                raise


# Global instance
model_service = ModelService()
