# Stream blog_article Tokens via SSE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stream blog_article LLM tokens to the browser in real-time (~50ms per token) instead of buffering the entire response (~15s) and dumping it all at once.

**Architecture:** Use LangGraph's `adispatch_custom_event` to emit tokens from within the plan_executor node during blog_article generation. chat.py handles these `on_custom_event` events and yields SSE `content` events immediately. Falls back gracefully to current behavior if custom events aren't available.

**Tech Stack:** LangGraph 1.0.2, langchain-core 1.0.4, ChatAnthropic/ChatOpenAI with `.astream()`, Python asyncio, SSE.

**Spec:** `docs/superpowers/specs/2026-03-26-v3-full-implementation-spec.md` (Section 1)

---

## Root Cause Analysis

The current streaming pipeline has a fundamental timing problem:

```
T=0s    User sends message
T=0.1s  Backend yields "Thinking..." (status SSE event)
        │
        ▼  LangGraph workflow runs as a single coroutine
        │  safety_node → intent_node → plan_executor_node
        │                              │
        │                              ├─ product_search (tool)
        │                              ├─ product_compose (tool)
        │                              │   ├─ concierge LLM ─────┐
        │                              │   ├─ consensus x3 LLM ──┤ asyncio.gather()
        │                              │   ├─ descriptions LLM ──┤ ALL run in parallel
        │                              │   ├─ blog_article LLM ──┤ but ALL must finish
        │                              │   └─ top_pick LLM ──────┘ before node returns
        │                              │
T=12s   plan_executor_node returns ◄───┘
        │
        ▼  on_chain_end fires for plan_executor_node
T=12.1s result_state populated with assistant_text (full blog_article)
        │
        ▼  Post-workflow: rapid 24-char chunking of already-complete text
T=12.2s 20-50 SSE "content" events yielded in milliseconds
        │
        ▼  All tokens arrive at frontend nearly simultaneously
T=12.3s React batches updates → entire response appears at once
```

**The fix:** Stream blog_article tokens AS THEY GENERATE from the LLM, not after the workflow completes.

```
T=0s    User sends message
T=0.1s  Backend yields "Thinking..." (status SSE event)
        │
T=1.5s  blog_article LLM starts generating tokens
        │  ┌─ Token 1 → adispatch_custom_event → astream_events → SSE content
        │  ├─ Token 2 → adispatch_custom_event → astream_events → SSE content
        │  ├─ Token 3 → ...
        │  └─ (user is reading as tokens arrive)
        │
T=8s    blog_article complete, other LLM tasks complete
T=8.1s  plan_executor returns → ui_blocks sent via done event
```

---

## How It Works: adispatch_custom_event

LangGraph supports dispatching custom events from WITHIN a node via `langchain_core.callbacks.manager.adispatch_custom_event`. These events propagate through `graph.astream_events()` immediately (not buffered until node completion).

**Requirements:**
- langchain-core >= 0.2.15 (we have 1.0.4 ✓)
- Code runs within a LangGraph node's async context (plan_executor_node ✓)
- Python contextvars propagation through asyncio.gather tasks (Python 3.7+ ✓)

**Event flow:**
```
product_compose → adispatch_custom_event("stream_token", {"token": "..."})
     │
     ▼  (propagates through LangGraph's runnable context)
astream_events() yields {"event": "on_custom_event", "name": "stream_token", "data": {...}}
     │
     ▼  (consume_events task puts it in event_queue)
chat.py drain loop picks up event → yields SSE content event
     │
     ▼  (SSE travels to browser)
Frontend onToken callback appends to message.content
```

**Graceful fallback:** If `adispatch_custom_event` fails (import error, no runnable context, etc.), the function catches the exception and continues. The full text is still returned by the function. chat.py falls back to post-workflow 24-char chunking (current behavior). No user-visible regression.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/app/services/model_service.py` | Add `generate_compose_with_streaming()` method |
| Modify | `backend/mcp_server/tools/product_compose.py` | Use streaming method for blog_article task |
| Modify | `backend/app/api/v1/chat.py` | Handle `on_custom_event` in event drain loop |

---

## Task 1: Add Streaming Compose Method to ModelService

**Files:**
- Modify: `backend/app/services/model_service.py`

The new method `generate_compose_with_streaming()` wraps the compose LLM with `.astream()` and dispatches a custom event per token chunk. If streaming fails for any reason, it falls back to the existing non-streaming `generate_compose()`.

- [ ] **Step 1: Read the file to find insertion point**

Read `backend/app/services/model_service.py` lines 158-270 to see `generate_compose()` and understand the compose model setup.

- [ ] **Step 2: Add the streaming method after generate_compose**

After the `generate_compose` method (which ends around line 266), add:

```python
    async def generate_compose_with_streaming(
            self,
            messages: list[Dict[str, str]],
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            agent_name: Optional[str] = None,
    ) -> str:
        """Generate a compose completion while streaming tokens via LangGraph custom events.

        Uses ``llm.astream()`` to get tokens as they generate, dispatching each
        as a ``stream_token`` custom event via ``adispatch_custom_event``.  If
        streaming or event dispatch fails at any point, falls back to the
        standard non-streaming ``generate_compose()`` path.

        Returns the full generated text (same as ``generate_compose``).
        """
        # Try to import the custom event dispatcher
        try:
            from langchain_core.callbacks.manager import adispatch_custom_event
        except ImportError:
            logger.debug("adispatch_custom_event not available, falling back to non-streaming")
            return await self.generate_compose(
                messages=messages, temperature=temperature,
                max_tokens=max_tokens, agent_name=agent_name,
            )

        # Resolve which LLM to use (same logic as generate_compose)
        use_anthropic = (
            getattr(settings, "USE_ANTHROPIC_COMPOSE", False)
            and getattr(settings, "ANTHROPIC_API_KEY", "")
        )

        try:
            if use_anthropic:
                llm = self.get_compose_model()
            else:
                llm = self._get_llm(
                    model=settings.COMPOSER_MODEL,
                    temperature=temperature,
                )

            lc_messages = self._convert_messages(messages)
            full_text_parts: list[str] = []

            async with self._streaming_semaphore:
                async for chunk in llm.astream(lc_messages):
                    if chunk.content:
                        full_text_parts.append(chunk.content)
                        try:
                            await adispatch_custom_event(
                                "stream_token",
                                {"token": chunk.content},
                            )
                        except Exception:
                            # Custom event dispatch failed — continue collecting text
                            # The full text will still be returned and chunked post-workflow
                            pass

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
```

- [ ] **Step 3: Verify _streaming_semaphore exists**

Check that `self._streaming_semaphore` is initialized in `__init__`. If it doesn't exist, find which semaphore `_stream_response` uses and use the same one. The attribute is `_streaming_semaphore` (defined around the constructor).

If `_streaming_semaphore` doesn't exist but `_sync_semaphore` does, use `_sync_semaphore` instead. Or if neither exists, skip the semaphore:

```python
# If no semaphore attribute exists, replace:
async with self._streaming_semaphore:
# with:
if True:  # no semaphore needed
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/model_service.py
git commit -m "feat: add generate_compose_with_streaming() for real-time token dispatch"
```

---

## Task 2: Use Streaming for blog_article in product_compose

**Files:**
- Modify: `backend/mcp_server/tools/product_compose.py`

Currently blog_article uses `model_service.generate_compose()` which returns the full text after the LLM finishes. Replace with `generate_compose_with_streaming()` for just the blog_article task. All other LLM tasks (concierge, descriptions, consensus, top_pick) keep using the non-streaming path — they're short outputs where streaming isn't valuable.

- [ ] **Step 1: Read lines 715-800 to find the blog_article task setup**

Read `backend/mcp_server/tools/product_compose.py` around lines 715-800. Find where `llm_tasks['blog_article']` is assigned. It looks like:

```python
llm_tasks['blog_article'] = model_service.generate_compose(
    messages=[...],
    temperature=0.7,
    max_tokens=500,
    agent_name="blog_article_composer"
)
```

- [ ] **Step 2: Replace with streaming variant**

Change the blog_article task from:
```python
llm_tasks['blog_article'] = model_service.generate_compose(
    messages=[...],
    temperature=0.7,
    max_tokens=500,
    agent_name="blog_article_composer"
)
```

To:
```python
llm_tasks['blog_article'] = model_service.generate_compose_with_streaming(
    messages=[...],
    temperature=0.7,
    max_tokens=500,
    agent_name="blog_article_composer"
)
```

This is a ONE-LINE change — just swap the method name. The method signature is identical. The function still returns `str`, so `asyncio.gather()` works unchanged. The only difference: during execution, it dispatches `stream_token` custom events.

**IMPORTANT:** Only change this ONE task. Do NOT change concierge, descriptions, consensus, or top_pick — those are short structured outputs where streaming adds no value.

- [ ] **Step 3: Commit**

```bash
git add backend/mcp_server/tools/product_compose.py
git commit -m "feat: use streaming compose for blog_article — tokens dispatch as custom events"
```

---

## Task 3: Handle on_custom_event in chat.py Event Loop

**Files:**
- Modify: `backend/app/api/v1/chat.py`

The event drain loop processes LangGraph events from the queue. Currently it handles `on_chain_start` and `on_chain_end`. Add handling for `on_custom_event` with name `stream_token` — yield SSE `content` events immediately.

- [ ] **Step 1: Read the event processing section**

Read `backend/app/api/v1/chat.py` around lines 440-490. Find the event type routing:

```python
event_type = event.get("event", "")

if event_type == "on_chain_start":
    # log agent status...

elif event_type == "on_chain_end":
    # process stream_chunk_data, set result_state...
```

- [ ] **Step 2: Add on_custom_event handler**

After the `on_chain_end` block and before the drain loop continues, add:

```python
                elif event_type == "on_custom_event":
                    custom_name = event.get("name", "")
                    if custom_name == "stream_token":
                        custom_data = event.get("data", {})
                        token = custom_data.get("token", "") if isinstance(custom_data, dict) else ""
                        if token:
                            if not data_already_streamed:
                                # First token: clear the "Thinking..." / skeleton state
                                yield _sse_event("artifact", {"clear": True})
                                logger.info("🔄 First streaming token received — cleared placeholder")
                            data_already_streamed = True
                            yield _sse_event("content", {"token": token})
```

**Key behaviors:**
- On the FIRST token, sends `{"clear": True}` artifact event to clear the "Thinking..." indicator
- Sets `data_already_streamed = True` so post-workflow text chunking (lines 615-620) is skipped
- Each subsequent token yields an SSE `content` event immediately
- The frontend's `onToken(token, false)` handler appends to `message.content` and clears `isThinking`

- [ ] **Step 3: Verify the clear signal doesn't conflict**

After the drain loop exits (around line 590-610), verify that when `data_already_streamed` is True:

1. Line 595: `if ui_blocks and ... and not data_already_streamed:` → FALSE (skips ui_blocks+clear combo)
2. Line 605: `elif not data_already_streamed:` → FALSE (skips standalone clear)
3. Line 609: `else:` → enters this branch (skips clear, logs "data already streamed")
4. Line 613: `should_stream_text = not is_halted and response_text and not data_already_streamed` → FALSE (skips post-workflow chunking)

This is correct. The ui_blocks will be sent in the `done` event (around line 700+) since `ui_blocks_sent_early` is False. The frontend processes them without clearing content.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/chat.py
git commit -m "feat: handle on_custom_event stream_token in SSE loop — real-time token delivery"
```

---

## Task 4: Verify and Deploy

- [ ] **Step 1: Review all changes**

Verify the three files have clean, minimal diffs:

```bash
git diff main -- backend/app/services/model_service.py
git diff main -- backend/mcp_server/tools/product_compose.py
git diff main -- backend/app/api/v1/chat.py
```

- [ ] **Step 2: Check Python syntax**

```bash
cd backend && python -c "
import ast
for f in ['app/services/model_service.py', 'mcp_server/tools/product_compose.py', 'app/api/v1/chat.py']:
    ast.parse(open(f).read())
    print(f'{f}: OK')
"
```

- [ ] **Step 3: Deploy to Railway**

Push the branch and deploy to Railway. The streaming changes are backward-compatible:
- If `adispatch_custom_event` works → tokens stream in real-time
- If it doesn't → falls back to current post-workflow chunking
- No frontend changes needed — the existing `onToken(token, false)` handler already works

- [ ] **Step 4: Test in browser**

Send a product query (e.g., "Best noise-cancelling headphones"). Observe:
- Tokens should start appearing within 2-3 seconds (after search completes, compose starts)
- Text should flow incrementally, not dump all at once
- Product cards should appear after the text finishes
- The streaming cursor (blinking line) should show during streaming

If tokens still dump all at once, check Railway logs for:
- `"adispatch_custom_event not available"` → import path wrong
- `"Streaming compose failed"` → LLM streaming error
- `"First streaming token received"` → tokens are being dispatched (frontend issue if they still batch)

---

## Dependency Graph

```
Task 1 (model_service) ──→ Task 2 (product_compose uses new method)
                        ──→ Task 3 (chat.py handles events from new method)
Task 2 + Task 3 ──→ Task 4 (verify & deploy)
```

Tasks 2 and 3 are independent of each other (Task 2 changes what emits events, Task 3 changes what handles events). But both depend on Task 1 which creates the new method.

---

## Fallback Behavior Matrix

| adispatch_custom_event available? | LLM .astream() works? | chat.py handles on_custom_event? | Result |
|---|---|---|---|
| ✅ Yes | ✅ Yes | ✅ Yes | **Real-time streaming** — tokens appear as generated |
| ❌ No (import fails) | N/A | N/A | Falls back to `generate_compose()` → post-workflow chunking |
| ✅ Yes | ❌ No (LLM error) | ✅ Yes | Falls back to `generate_compose()` → post-workflow chunking |
| ✅ Yes | ✅ Yes | ❌ No (event ignored) | Custom events dispatched but unhandled; text still in result_state → post-workflow chunking |
| ✅ Yes | ✅ Yes | ✅ Yes, but context lost | `adispatch_custom_event` silently fails; text still collected → post-workflow chunking |

**Every failure path degrades to the current behavior.** No regression possible.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `adispatch_custom_event` import path wrong | Low | None — fallback | try/except with fallback |
| RunnableConfig contextvar not propagated through asyncio.gather | Medium | None — fallback | try/except around each dispatch |
| LLM `.astream()` not supported for compose model | Very Low | None — fallback | Catch exception, fall back |
| Token ordering issues (interleaved with other events) | Low | Low — minor visual glitch | Only blog_article streams; other tasks return structured data |
| First `clear` event arrives too early/late | Low | Minor — thinking indicator flickers | Clear fires on first token, which is the natural transition point |
| Railway deploy breaks other functionality | Very Low | High | Changes are additive only — no existing code paths modified |
