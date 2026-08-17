# Stream Reliability Implementation Plan

> **⚠ REVISED 2026-07-31 after the round-2 debug sweep — Task 1's root cause was
> wrong as written. Execute against these verified corrections:**
>
> 1. **A client watchdog ALREADY EXISTS.** `useStreamReducer.ts:115` arms a 120s
>    FSM watchdog (`INTERRUPT_TIMEOUT_MS`) on SEND_MESSAGE that fires
>    `STREAM_INTERRUPTED`; `isStreaming` derives from FSM state and cannot stay
>    true past 120s, and the interrupted effect clears the bubble's `isThinking`
>    (`ChatContainer.tsx:790`). Do NOT add a second watchdog in `handleStream` —
>    Task 1 as originally written builds a duplicate.
> 2. **The real gap is the unbounded read loop.** The 120s `AbortController` in
>    `chatApi.ts` is cleared immediately after `await fetch()` resolves
>    (`:229`) — it covers headers only. The body loop `await reader.read()`
>    (`:270`) has NO timeout: a stalled connection hangs the `streamChat`
>    promise forever. The FSM recovers; the ZOMBIE FETCH does not, and its late
>    callbacks are what corrupt state (Task 2's bug). **Task 1 retarget:** an
>    idle timeout raced around `reader.read()` (reset per chunk), not a
>    component-level timer. Task 1's test intent stands; its assertion target
>    moves to chatApi.
> 3. **Task 3 is the highest-leverage fix — elevate it.** A monotonic per-stream
>    token that no-ops stale callbacks kills B2 (wrong-message errors) and B3
>    (interleaving) in one guard. There IS an existing AbortController but it is
>    per-attempt and nothing aborts stream A when B starts — Task 3's shared
>    controller ref stands.
> 4. **Task 4 addition — two verified backend-frame paths produce "finished
>    mid-sentence with no error":** a `done` event without `session_id` is
>    silently swallowed (`chatApi.ts:382` guard skips `onComplete` and returns),
>    and SSE JSON parse failures are swallowed with `console.error` and continue
>    (`:460`). Fix alongside the truncation detector: treat done-without-
>    session_id as terminal, and surface a parse-failure that ends a stream as
>    `'network'`-reason recovery instead of silent degradation.
> 5. Round-2 confirmed adjacent bugs to fold into Task 4/5 scope if cheap:
>    mid-stream auto-retry re-POSTs the full message and double-appends tokens;
>    localStorage persists `isThinking: true` mid-stream (frozen bubbles on
>    reload) and stringifies on every token; `Date.now()+1/+2` message-id
>    collisions; session-switch never dispatches `RESET`.

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A request can never spin forever, an error always attaches to the message that
caused it, and a truncated answer is surfaced as truncated instead of shipped as if
complete.

**Architecture:** The backend is not the problem. `chat.py:459` computes
`deadline = stream_start_time + MAX_TOTAL_REQUEST_S`, checks it on every loop iteration
(`:461-470`), cancels the consumer, and emits a `request_timeout` error at `:573-576`.
The audit's 5-minute spinner is client-side: `isStreaming` never returns to `false`, so
the spinner runs, `handleRetry` early-returns, and the next message's error lands on the
wrong bubble. The fix is a client watchdog plus correct error targeting.

**Tech Stack:** Next.js 14 / React 18 / TypeScript, vitest; FastAPI SSE backend.

## Global Constraints

- **Do not modify the SSE streaming logic in `ChatContainer` beyond what each task
  names.** The stream reducer and event handling are load-bearing and easy to break
  subtly. Add state guards; do not restructure the event loop.
- The client watchdog must be **longer** than the server cap, never shorter — a client
  that gives up first turns a recoverable server error into a spurious client error.
  Server cap is `MAX_TOTAL_REQUEST_S` in `backend/app/services/stage_telemetry.py`.
- `removeConsole` is configured to keep `error` and `warn` in production. Log stream
  failures with `console.error` so they remain visible in DevTools.
- Tests: `cd frontend && npx vitest run <file>`

## File Structure

- Modify: `frontend/components/ChatContainer.tsx` — watchdog, error targeting, retry guard
- Modify: `frontend/lib/chatApi.ts` — surface `request_timeout` distinctly
- Create: `frontend/tests/streamWatchdog.test.tsx`
- Create: `frontend/tests/streamErrorTargeting.test.tsx`

---

### Task 1: Bound the read loop — the zombie-fetch fix (v2)

> **v2 — the original body built the duplicate component-level watchdog the
> banner forbids. Deleted. The FSM already bounds `isStreaming` at 120s
> (`useStreamReducer.ts:115`); what nothing bounds is the FETCH: the abort
> timer dies at `chatApi.ts:229` and `await reader.read()` (`:270`) races
> nothing, so the promise hangs forever and its late callbacks corrupt state.**

**Files:**
- Modify: `frontend/lib/chatApi.ts` — the read loop only
- Create: `frontend/tests/readIdleTimeout.test.ts`

**Interfaces:**
- Produces: `READ_IDLE_TIMEOUT_MS` exported from `chatApi.ts`, and a per-read
  idle race inside `streamChat`'s read loop. Resets on every received chunk —
  it bounds silence, not total duration (a healthy long stream keeps talking).

- [ ] **Step 1: Write the failing test**

Test `streamChat` directly (unit, no component render — this is a lib fix):

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { streamChat, READ_IDLE_TIMEOUT_MS } from '@/lib/chatApi'

describe('read-loop idle timeout', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks() })

  it('errors out when the body stream goes silent forever', async () => {
    // Headers arrive fine; the body reader never resolves — the zombie fetch.
    const neverReader = { read: () => new Promise(() => {}), cancel: vi.fn() }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true, status: 200,
      body: { getReader: () => neverReader },
    }))

    const onError = vi.fn()
    const done = streamChat({
      message: 'best espresso machine',
      onToken: vi.fn(), onComplete: vi.fn(), onError,
    } as any)

    await vi.advanceTimersByTimeAsync(READ_IDLE_TIMEOUT_MS + 1000)
    await done
    expect(onError).toHaveBeenCalled()
    expect(String(onError.mock.calls[0][0])).toMatch(/timed out|silent|stalled/i)
    expect(neverReader.cancel).toHaveBeenCalled()
  })
})
```

Adapt the `ChatStreamOptions` fields to the real interface (`chatApi.ts:151-165`).

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/readIdleTimeout.test.ts`
Expected: FAIL — `READ_IDLE_TIMEOUT_MS` not exported; the promise never settles
(vitest reports a timeout on `await done`).

- [ ] **Step 3: Implement the per-read race**

In `chatApi.ts`:

```ts
// Bounds SILENCE on the body stream, not total duration. The 120s pre-header
// abort dies the moment fetch() resolves (:229); without this, a stalled
// connection leaves reader.read() pending forever — the stream promise never
// settles and its eventual callbacks fire into a newer stream's state.
export const READ_IDLE_TIMEOUT_MS = 90_000
```

Wrap the read in the loop at `:269-274`:

```ts
      while (true) {
        const result = await Promise.race([
          reader.read(),
          new Promise<never>((_, reject) => {
            idleTimer = setTimeout(
              () => reject(new Error('stream stalled: no data for 90s')),
              READ_IDLE_TIMEOUT_MS,
            )
          }),
        ]).finally(() => clearTimeout(idleTimer))
        const { done, value } = result
        ...
```

On the stall rejection: `reader.cancel()`, then route through the existing
error path so `onError` fires and the `finally` in `handleStream` runs. Declare
`let idleTimer` above the loop; clear it on every branch.

**Non-retryable by construction (validation nit):** do not rely on the error
message dodging `isNetworkError`'s string check — mark the error explicitly
(`err.name = 'StallError'` or a custom class) and add it to the non-retryable
branch of the retry classifier, so a future message rewording can't silently
make mid-stream stalls retryable (which would double-append content).

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/readIdleTimeout.test.ts`

- [ ] **Step 5: Regression — the retry path**

A stall now raises inside the retry loop. Confirm a mid-stream stall is NOT
auto-retried (content was already appended — re-POST would double it, see
Task 5): the stall error must bypass `isNetworkError` retry (`:473-486`) when
any event was received. Add that assertion to the test file.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/chatApi.ts frontend/tests/readIdleTimeout.test.ts
git commit -m "fix(chat): idle timeout on the SSE read loop — no more zombie fetches"
```

---

### Task 2: An error attaches to the message that caused it

**Root cause:** the audit sent a second message while the first was still spinning. The
error surfaced against the *new* message while the original spinner kept running. The
error path uses whatever is currently in `pendingUserMessage` rather than the message the
failed stream belonged to.

**Files:**
- Modify: `frontend/components/ChatContainer.tsx` — `onError` (~line 628)
- Create: `frontend/tests/streamErrorTargeting.test.tsx`

**Interfaces:**
- Consumes: the `onError(errorMsg)` callback passed to `streamChat`
- Produces: each stream captures its own `streamMessageId` at start; `onError` marks
  that id.

- [ ] **Step 1: Write the failing test**

```tsx
it('attaches the error to the message whose stream failed', async () => {
  // Stream A fails after stream B has started.
  let failA: (msg: string) => void = () => {}
  ;(chatApi.streamChat as any)
    .mockImplementationOnce((_q: string, opts: any) => {
      failA = opts.onError
      return new Promise(() => {})
    })
    .mockImplementationOnce(() => new Promise(() => {}))

  render(<ChatContainer />)
  // Send A, then B, then fail A. The error must reference A, not B.
  // Drive both sends through the real composer; read ChatContainer for the testids.
  await act(async () => { failA('Hit a wall pulling info on this one') })

  const banner = screen.getByTestId('chat-error-banner')
  expect(banner.getAttribute('data-message-id')).toBe('A')
})
```

Adapt the ids and testids to the component's real values. If the error banner carries no
`data-message-id`, add one — the assertion is the point of the task.

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/streamErrorTargeting.test.tsx`
Expected: FAIL — the error references the newest message.

- [ ] **Step 3: Capture the owning message per stream**

At the top of `handleStream`, before the `streamChat` call:

```tsx
    // Capture the message this stream belongs to. Without it, a late error from an
    // earlier stream lands on whatever message is pending now — the audit saw an
    // error attributed to a new message while the original spinner kept running.
    const streamMessageId = assistantMessageId
    const streamQuery = userMessage
```

Then use those captured values inside `onError` instead of the live state:

```tsx
      onError: (errorMsg) => {
        console.error('Stream error:', errorMsg, 'for message', streamMessageId)
        setErrorMessage(errorMsg)
        setShowErrorBanner(true)
        setPendingUserMessage(streamQuery)
        setIsStreaming(false)
        ...
      },
```

Render the id on the banner so the test can assert it:

```tsx
<div data-testid="chat-error-banner" data-message-id={errorMessageId}>
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/streamErrorTargeting.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ChatContainer.tsx frontend/tests/streamErrorTargeting.test.tsx
git commit -m "fix(chat): attribute stream errors to the message that failed"
```

---

### Task 3: Only one stream in flight; a second send supersedes the first

**Root cause:** two concurrent streams produced the interleaved state in Task 2.
`sendInFlightRef` already exists (`ChatContainer.tsx:704`) and guards
`handleSuggestionClick`, but the main send path allowed a second request while the first
was live.

**Files:**
- Modify: `frontend/components/ChatContainer.tsx`
- Modify: `frontend/lib/chatApi.ts` — signal threading + retry-boundary semantics
- Test: `frontend/tests/streamErrorTargeting.test.tsx`

**Interfaces:**
- Consumes: `sendInFlightRef` (declared at `ChatContainer.tsx:413`; `:704` is a
  use site)
- Produces: an `AbortController` per stream, aborted when a new send supersedes
  it, threaded via a new `signal` field on `ChatStreamOptions`
  (`chatApi.ts:151-165` has none today)

**Token semantics across the retry boundary (validation catch — binding):**
`streamChat` retries internally up to `MAX_RETRIES = 3` (`chatApi.ts:11`) and a
retry re-POSTs the full message and re-invokes `onToken` from byte zero, while
the UI appends (`msg.content + token`, `ChatContainer.tsx:513`). Two rules:
1. The staleness token is per **handleStream invocation**, not per attempt —
   a retry inside one `streamChat` call is NOT stale.
2. A retry that begins after any content token was received must first signal a
   content reset (`onReconnecting` or an explicit `onRetryReset` callback) so
   the UI replaces instead of appends — or the retry must be suppressed
   entirely when content exists (consistent with Task 1 Step 5).
Additionally, the supersede-abort must break the retry loop itself: an abort
during the backoff `sleep(delay)` (`chatApi.ts:484`) must not `continue` into
another attempt — check the signal at the top of each attempt.

- [ ] **Step 1: Write the failing test**

```tsx
it('aborts the previous stream when a new message is sent', async () => {
  const aborted: boolean[] = []
  ;(chatApi.streamChat as any).mockImplementation((_q: string, opts: any) => {
    opts.signal?.addEventListener('abort', () => aborted.push(true))
    return new Promise(() => {})
  })
  render(<ChatContainer />)
  // Send two messages back to back through the composer.
  // ...
  expect(aborted).toHaveLength(1)
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/streamErrorTargeting.test.tsx -t abort`
Expected: FAIL — no abort is emitted.

- [ ] **Step 3: Implement**

Hold the live controller in a ref and abort it before starting a new stream:

```tsx
  const activeStreamRef = useRef<AbortController | null>(null)
```

At the start of `handleStream`:

```tsx
    // A second send supersedes the first: abort it so its late events cannot
    // interleave with the new stream's state.
    activeStreamRef.current?.abort()
    const controller = new AbortController()
    activeStreamRef.current = controller
```

Pass `signal: controller.signal` through to `streamChat`, and in `chatApi.streamChat`
forward it to `fetch`. In the terminal path, clear the ref only if it is still this
stream's controller:

```tsx
      if (activeStreamRef.current === controller) activeStreamRef.current = null
```

An `AbortError` must be swallowed, not shown as an error — it is a deliberate supersede.

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/streamErrorTargeting.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/ChatContainer.tsx frontend/lib/chatApi.ts \
        frontend/tests/streamErrorTargeting.test.tsx
git commit -m "fix(chat): abort a superseded stream instead of racing two"
```

---

### Task 4: A truncated answer must be labelled, not shipped silently

**Root cause:** the first response ended mid-sentence — "The Shark Rocket Pet Pro
Cordless Stick Vacuum is the pick if you have" — with no continuation and no error, and
the stream had finished. The completion path does not check whether the prose it received
is complete.

**Files:**
- Modify: `frontend/components/ChatContainer.tsx` — `onComplete`
- Create: `frontend/lib/isTruncated.ts`
- Create: `frontend/tests/isTruncated.test.ts`

**Interfaces:**
- Produces: `isLikelyTruncated(text: string): boolean`

- [ ] **Step 1: Write the failing test**

```ts
import { describe, it, expect } from 'vitest'
import { isLikelyTruncated } from '@/lib/isTruncated'

describe('isLikelyTruncated', () => {
  it('flags prose ending mid-sentence', () => {
    expect(isLikelyTruncated(
      'The Shark Rocket Pet Pro Cordless Stick Vacuum is the pick if you have'
    )).toBe(true)
  })

  it('accepts prose ending in terminal punctuation', () => {
    expect(isLikelyTruncated('It is the pick for small flats.')).toBe(false)
    expect(isLikelyTruncated('Which room is it for?')).toBe(false)
  })

  it('accepts prose ending in a list item or table row', () => {
    expect(isLikelyTruncated('- Built-in burr grinder\n- Fast heat-up\n')).toBe(false)
  })

  it('does not flag empty text', () => {
    expect(isLikelyTruncated('')).toBe(false)
    expect(isLikelyTruncated('   ')).toBe(false)
  })

  it('flags a dangling conjunction even with a period elsewhere', () => {
    expect(isLikelyTruncated('It is quiet. It also handles pet hair and')).toBe(true)
  })
})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npx vitest run tests/isTruncated.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```ts
// Words a sentence cannot legitimately end on. A completed answer ending in
// "if you have" is a truncation, not a style choice.
const DANGLING = new Set([
  'and', 'or', 'but', 'if', 'the', 'a', 'an', 'to', 'for', 'with', 'have', 'has',
  'is', 'are', 'was', 'were', 'of', 'in', 'on', 'at', 'that', 'than', 'from',
])

/** Heuristic: does this assistant prose look cut off mid-sentence? */
export function isLikelyTruncated(text: string): boolean {
  const trimmed = (text ?? '').trim()
  if (!trimmed) return false

  const lastLine = trimmed.split('\n').filter(Boolean).pop() ?? ''
  // Structured trailing content (list item, table row) is a legitimate ending.
  if (/^\s*(?:[-*•]|\||\d+[.)])/.test(lastLine)) return false
  // Terminal punctuation, including closing quotes/brackets after it.
  if (/[.!?:;][)"'\]]*$/.test(trimmed)) return false

  const lastWord = (trimmed.match(/[A-Za-z']+$/)?.[0] ?? '').toLowerCase()
  return lastWord.length > 0 && (DANGLING.has(lastWord) || !/[.!?]/.test(trimmed.slice(-80)))
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd frontend && npx vitest run tests/isTruncated.test.ts`
Expected: all 5 PASS. Tune `DANGLING` and the 80-character lookback until they do — do
not weaken the tests.

- [ ] **Step 5: Wire it into completion**

In `onComplete`, when the final prose looks truncated, show the existing recovery UI
rather than presenting the answer as finished. `MessageRecoveryUI` already handles this
state — `completeness: 'partial'` with `onRetryFull` (see
`frontend/tests/messageRecovery.test.tsx`). Reuse it; do not build a second affordance.

```tsx
        if (isLikelyTruncated(finalText)) {
          console.warn('[stream] completed with truncated prose — offering retry')
          setInterruptedMessageId(assistantMessageId)
        }
```

- [ ] **Step 6: Fix the two swallowed-terminal paths (banner item 4 — owned here)**

Both verified paths that end a stream "finished, mid-sentence, no error":

(a) **done-without-session_id** — `chatApi.ts:382` `if (chunk.session_id) {`
skips `onComplete` entirely and `return`s. Change: always call `onComplete`
when a done event arrives; pass `session_id: chunk.session_id ?? null` and let
`ChatContainer`'s existing `if (data.session_id)` guard (`:581`) decide what to
persist — completion of the STREAM must not depend on a persistence field.
Add a unit test: done event without session_id → `onComplete` called once.

(b) **parse-failure silence** — `chatApi.ts:461` catches, logs, continues. Keep
the continue (one bad frame must not kill a healthy stream), but count
failures; if the stream later closes with NO terminal event AND parse failures
occurred, invoke `onError('stream ended after malformed frames')` instead of
returning silently — which routes into the recovery UI with
`interruptionReason: 'network'` (the field exists on the type and has no
writer today; this is its first).

- [ ] **Step 7: Run the frontend suite**

Run: `cd frontend && npx vitest run`
Expected: no new failures; `messageRecovery.test.tsx` still passes.

- [ ] **Step 8: Commit**

```bash
git add frontend/lib/isTruncated.ts frontend/tests/isTruncated.test.ts \
        frontend/lib/chatApi.ts frontend/components/ChatContainer.tsx
git commit -m "fix(chat): truncation detection + terminal events always fire"
```

---

### Task 4b: The cheap confirmed bugs (banner item 5 — owned here, S each)

No orphan findings: each gets a test-first fix in this task or an explicit
deferral note in the commit.

- [ ] `Date.now()+1/+2` message ids (`ChatContainer.tsx:448`, `:547`, `:691`) →
  `crypto.randomUUID()`. Test: two messages created in the same millisecond get
  distinct ids.
- [ ] localStorage persistence: strip `isThinking`/`statusText` before
  `JSON.stringify` and debounce ~500ms (`:398-403` runs per token today).
  Test: a persisted-mid-stream message reloads without a frozen spinner.
- [ ] Session-switch dispatches `RESET` and aborts the live stream via Task 3's
  controller ref (`switchToSession`, `:331-370`, has neither today). Test:
  switching sessions mid-stream leaves `isStreaming` false.
- [ ] Commit: `git commit -m "fix(chat): stable message ids, clean persistence, session-switch reset"`

---

### Task 5: Verification pass

- [ ] **Step 1: Run the suite**

Run: `cd frontend && npx vitest run`
Expected: no new failures.

- [ ] **Step 2: Verify the hang path live**

Start the stack, then stop the backend mid-request (`docker-compose stop backend`) to
force a stall. Confirm: the spinner ends within `STREAM_WATCHDOG_MS`, an error appears,
the composer is usable, and Regenerate works — Regenerate's silent early-return on
`isStreaming` is fixed by this plan's Task 1 and covered in PLAN-7 Task 2.

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "test: PLAN-6 verified — no infinite spinner, errors land correctly"
```
