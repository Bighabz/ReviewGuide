# QA-loop Playwright checks (Tier A)

Headless browser checks that reproduce the manual sweep **without** any real
chat call or real outbound affiliate traffic. Containment is enforced at the
Playwright layer, not by trusting app behavior:

- **`lockdownNetwork`** default-denies every host except `*.reviewguide.ai`,
  the backend origin, and localhost — so the affiliate `window.open` target
  can never load and no external fetch escapes.
- the chat stream is **route-mocked** from `helpers.ts` builders in every
  `/chat` test (no request reaches the backend),
- the affiliate click POST is **captured then fulfilled locally** (never a real
  prod write), and its `session_id` is asserted to keep the `qa-auto-pw-`
  marker,
- QA sessions enter via `/chat?session=qa-auto-pw-...` and rendered content is
  restored through a **stubbed `/v1/chat/history/<id>`** response (entering a
  session runs `switchToSession()`, which wipes any localStorage seed — so
  content must come from the history stub, not localStorage).

> Status: DELIVERED but unvalidated. Selectors and the history-restore shape
> must be confirmed on a first supervised run against live prod DOM.

## One-time setup (per machine / per task account)

```
cd qa/playwright
npm ci                       # installs @playwright/test 1.50.0
npx playwright install chromium
```

Both projects (`chromium-desktop`, `chromium-mobile`) run on **chromium** — the
mobile project uses the iPhone 14 Pro viewport but overrides `browserName` to
chromium, so only the chromium browser needs installing.

For the scheduled-task account, pin the browser cache so the task never
downloads at run time:

```
setx PLAYWRIGHT_BROWSERS_PATH "C:\Users\habib\AppData\Local\ms-playwright"
```

## Run

```
BASE_URL=https://www.reviewguide.ai npx playwright test
```

`browser_qa.py` invokes this with `--reporter=json` and maps failures to
findings. `QA_RUN_DIR` sets the output dir; traces/video are OFF by policy so
no auth header is ever captured into an artifact.
