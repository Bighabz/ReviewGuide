# Next Session Prompt — ReviewGuide.ai Stabilization Continuation

**Written:** 2026-05-19 (supersedes `next-session-prompt-2026-04-22.md`, which was based on a misdiagnosed symptom).
**Last verified commit on `origin/main`:** `84d2999` ("fix(backend): add missing generate_compose / generate_compose_with_streaming").
**Session goal:** Land 4-5 atomic fixes (1 backend, 3-4 frontend) that came out of the 2026-04-21 audit. Stop the affiliate compliance bleed first.
**Expected duration:** 2-4 hours depending on logo restoration scope.
**Note:** Several weeks may have passed between this doc being written and the next session — re-verify reality before assuming any of this is still accurate.

---

## Reference documents (read these first, in this order)

1. **This file** — current plan.
2. [`qa-report-2026-04-21.md`](./qa-report-2026-04-21.md) — manual browser walkthrough findings, confirmed in MCP audit. Drove this plan.
3. [`opus-4.7-audit-report-2026-04-16.md`](./opus-4.7-audit-report-2026-04-16.md) — original principal-engineer audit; P0-P3 inventory and 3-month roadmap.
4. [`sprint-plan-2026-04-21.md`](./sprint-plan-2026-04-21.md) — 3-week sprint plan from prior session.
5. [`next-session-prompt-2026-04-22.md`](./next-session-prompt-2026-04-22.md) — **SUPERSEDED by this doc.** Its premise (`ui_blocks: []`, providers report "unavailable") was wrong: cards DO render, they just have wrong affiliate URLs. Its env-mutation plan (`USE_MOCK_AFFILIATE=true` etc.) would have made things worse and should NOT be executed.
6. Codebase maps in `.planning/codebase/` — STACK / ARCHITECTURE / CONVENTIONS / CONCERNS.

---

## State snapshot (as of 2026-04-21 deep-audit session)

**What's verified live on https://www.reviewguide.ai (from MCP browser audit):**

| Area | State |
|---|---|
| Homepage hero | Renders fine. Static "Ask Before You Buy" blue logo pill (PNG `1815e5dc...png`) top-left. "What are you researching today?" headline. TrendingCards grid below the fold. |
| Homepage chips | Render. Each navigates to `/chat?q=<query>&new=1`. **Several chips fire wrong queries — see Fix 3 below.** |
| Discover nav link | `href="/"` — correct, homepage IS the Discover page. |
| `/discover` typed URL | 404 — needs simple redirect. |
| `/saved` and `/compare` | Both render "coming soon" pages. Nav links work but lead to dead ends. |
| `/chat` page | Loads in ~1s after chip click. LLM stream takes ~25-30s. No hard browser freeze observed — the chat-page useEffect bug is real but does not lock the browser. |
| Headphones query | Returns 5 product cards with **all 5 Amazon links pointing to wrong, unrelated, cheaper products** — confirmed visually. Same positional-zip pattern in two independent sessions. |
| `AnimatedLogo.tsx` | Component exists with full video + audio + sessionStorage gating logic, but is **not imported anywhere**. Orphaned after a refactor. Assets (`animated_logo.mp4`, `Animation_Logo_sound.mp3`, `ezgif-7b66ba24abcfdab0.gif`) all present in `frontend/public/images/`. |

**What's still broken (this session's targets):**

1. Affiliate links point to wrong products (compliance + revenue critical) — root cause diagnosed.
2. `/discover` 404 — trivial fix identified.
3. Category chip queries miscategorized — trivial fix identified.
4. Saved + Compare lead to dead pages — remove from nav until features ship.
5. `/chat` page useEffect loop — real bug, downgraded from P0 to P2 after MCP audit could not reproduce a hard freeze.
6. Animated logo orphaned — restore decision pending (see end of doc).

---

## Prerequisites (run on fresh clone before doing anything else)

> **If this is a brand new machine,** start with [`docs/CLAUDE-CODE-SETUP.md`](../CLAUDE-CODE-SETUP.md) first — it covers MCP setup, plugin install, CLI auth, and contains a separate kickoff prompt for fresh-clone scenarios. Come back here after that.

```bash
# 1. Auth
gh auth status                                              # log in if needed
railway login                                               # browser-based
railway link --project reviewguide-backend                  # if not already linked
railway service                                             # confirm backend service selected

# 2. Install
cd backend && pip install -r requirements.txt && cd ..
cd frontend && npm install && cd ..

# 3. Sanity check the live backend is up
curl -sS -o /dev/null -w "%{http_code}\n" \
  https://backend-production-0ae7.up.railway.app/health
# expect: 200

# 4. Re-snapshot Railway env vars to a LOCAL (not committed) file before mutating anything
mkdir -p ~/railway-env-backups
TS=$(date +%Y%m%d-%H%M%S)
railway variables --json > ~/railway-env-backups/backend-production-$TS.json
railway variables --kv   > ~/railway-env-backups/backend-production-$TS.env
echo "Snapshot: ~/railway-env-backups/backend-production-$TS.*"
```

**Do NOT commit the env-var snapshots — they contain secrets.** Keep them in a directory outside the repo (the example above uses `~/railway-env-backups/`). Add that path to your shell history so you can restore if a mutation breaks production:

```bash
# Example rollback (only run if you mutated and need to revert):
railway variable delete VAR_NAME            # for each var you set that was previously unset
# or
railway variable set VAR_NAME=<old-value>   # if it had a previous value (read from the .env snapshot)
```

---

## Fix plan (priority order)

### 🔴 Fix 1 — Positional-zip affiliate mismapping (P0, ship alone)

**File:** `backend/mcp_server/tools/product_affiliate.py:171-203` (inside the Amazon branch of `search_provider`).

**Bug:** LLM returns ordered product list `[Sony XM5, Bose 700, AirPods Max, …]`. Code zips that list against `curated_amazon_links[]` by index. So whatever order the LLM picks, slot N always gets curated entry N — guaranteeing mismatch when the orders differ. Two independent live sessions confirmed: slot 5 always returns the Bose QC link regardless of which product the LLM chose for slot 5.

**Why this is urgent:** Advertised product X with affiliate link to product Y (and often a wrong price too) is a compliance/legal risk under Amazon Associates ToS and FTC affiliate disclosure rules. Earning commissions on the wrong product is worse than earning nothing.

**Why the prior session's env mutation would have made this worse:**
- Setting `USE_MOCK_AFFILIATE=true` routes through `MockAffiliateProvider` (`backend/app/services/affiliate/manager.py:143-147`), generating generic mock products — obscures the real bug.
- Setting `AMAZON_ASSOCIATE_TAGS=US:revguide-20` doesn't help curated `amzn.to` links — those don't carry query params; the associate tag is resolved server-side by Amazon based on the account that minted the short link.

**Before editing, verify:**
1. Read `_fuzzy_product_match` (cited at `product_compose.py:499-513` and again in `product_affiliate.py`) — confirm threshold convention (higher = stricter, or lower = stricter?). Don't pick a number blindly.
2. Spot-check `backend/app/services/affiliate/curated_amazon_links.py` for the "noise cancelling headphones" category — does the curated list contain ANY entries for premium brands the LLM commonly returns (Sony WH-1000XM5, Apple AirPods Max, Sennheiser Momentum, Jabra Elite 85h, Bose 700)? If not, fuzzy matching can't invent what isn't there — most cards will fall through.
3. Read `backend/app/services/affiliate/registry.py` and `providers/amazon_provider.py` to understand the fallback chain so the "no curated match → fall through" branch goes somewhere useful.

**The change (sketch):**

```python
# OLD (buggy positional zip):
for i, product_name in enumerate(products_to_search):
    if i < len(curated_amazon_links):
        curated = curated_amazon_links[i]
        # ... append wrong link ...

# NEW (product-name fuzzy match with fall-through):
for product_name in products_to_search:
    matched = next(
        (c for c in curated_amazon_links
         if _fuzzy_product_match(
             product_name.lower(),
             c.get("title", "").lower(),
             threshold=<verify-then-pick>)),
        None,
    )
    if not matched:
        # Skip curated; live provider (PA-API or SerpAPI) fills in below.
        continue
    curated = matched
    # ... append correct link ...
```

**User-approved scope:** A1 (skip unmatched products immediately) plus A2 (fall through to live PA-API / SerpAPI for unmatched products where the env is configured). A1 stops the compliance bleed today; A2 expands coverage as a follow-up.

**Verification:**

```bash
curl -sSN --max-time 60 -H 'Content-Type: application/json' \
  -d '{"message":"best noise cancelling headphones","session_id":null}' \
  https://backend-production-0ae7.up.railway.app/v1/chat/stream \
  -o /tmp/rg_test.sse

# Sanity:
grep -c '"ui_blocks": \[\]' /tmp/rg_test.sse    # expect 0
grep -c 'amzn.to/' /tmp/rg_test.sse              # expect ≥1

# The real check: extract each card's title + affiliate URL and confirm they correspond.
# (Manual: open the chat in a browser, click through each Amazon link, confirm destination
# product matches the card title.) The "tag=revguide-20" assertion from the prior handoff
# CANNOT be used here — curated amzn.to short links don't carry the tag parameter.
```

Repeat for at least 2 more categories (travel, laptops) to confirm the fix is global, not isolated.

---

### 🟡 Fix 2 — `/discover` 404 redirect (P1, trivial)

**Create:** `frontend/app/discover/page.tsx`

```tsx
import { redirect } from 'next/navigation'

export default function DiscoverRedirect() {
  redirect('/')
}
```

**Why:** Nav link is correct (`href="/"`, since homepage IS the Discover page — confirmed via `frontend/app/page.tsx` exporting `DiscoverPage()`, plus `/browse` already redirects to `/`). The only bug is that users who type `/discover` manually get the 404 editorial page. This redirect closes that gap.

**Effort:** 2 minutes.

---

### 🟡 Fix 3 — Category chip query mappings (P1, ~5 min)

**File:** `frontend/components/discover/CategoryChipRow.tsx:10-19`

**Current mappings (broken):**
```typescript
{ label: 'Tech',     query: 'Best noise-cancelling headphones' },  // ← should be tech
{ label: 'Kitchen',  query: 'Best robot vacuums for pet hair'   }, // ← vacuums aren't kitchen
{ label: 'Fitness',  query: 'Best hiking boots for beginners'   }, // ← duplicates Outdoor
{ label: 'Outdoor',  query: 'Best hiking boots for beginners'   }, // ← duplicates Fitness
```

**Recommended (verify each maps to a reasonable curated category in `curated_amazon_links.py` or returns sensible products):**
```typescript
{ label: 'Tech',     query: 'Best laptops for productivity' },
{ label: 'Kitchen',  query: 'Best kitchen appliances 2026' },
{ label: 'Fitness',  query: 'Best running shoes 2026' },
{ label: 'Outdoor',  query: 'Best camping gear for beginners' },
```

Leave Popular / Travel / Home / Fashion as-is (they map reasonably).

---

### 🟡 Fix 4 — Remove Saved + Compare from nav (P1, ~5 min)

**Files:**
- `frontend/components/UnifiedTopbar.tsx:151-158` — remove the Saved link block
- `frontend/components/UnifiedTopbar.tsx:169-176` — remove the Compare link block
- `frontend/app/saved/page.tsx` — delete (coming-soon placeholder)
- `frontend/app/compare/page.tsx` — delete

**Why:** User-approved choice. Both lead to dead-end "coming soon" pages with no advance signal. Removing entirely is simpler than adding a Soon badge or feature-flag infrastructure, and git history preserves the pattern for restoration when the features actually ship.

---

### 🟢 Fix 5 — `/chat` useEffect loop (P2, ~15 min including verification)

**File:** `frontend/app/chat/page.tsx:25-83`

**Bug:** `useEffect` has deps `[searchParams, router]` and internally calls `router.replace('/chat', { scroll: false })` (lines ~54 and ~74) to clean up query params after processing. The replace mutates `searchParams`, which re-triggers the effect. Loop.

**Why downgraded from P0 to P2:** MCP browser audit (2026-04-21) clicked the Tech chip and the page loaded in ~1s, streamed response in ~25-30s, no browser hang. The QA report's "freeze" was most likely perceived slowness during a long LLM stream amplified by the effect re-running, not an actual lock-up.

**The fix is NOT just `deps=[]`** (an earlier subagent suggested this). In Next.js App Router, `router.push('/chat?q=B')` from `/chat?q=A` updates `searchParams` without remounting — so empty deps would break the second-chip-click flow.

**Better fix:** Keep the deps, gate the `router.replace` behind a "did we actually process a new query" check using the existing `processedQueryRef` (line 23). After processing, set the ref; on re-entry, the existing guard at line 33 (`processedQueryRef.current !== query`) short-circuits the effect body so the replace doesn't fire again.

**Verification:** Click a category chip, watch chat-page perf with React DevTools profiler — useEffect should run twice max (initial mount + after router.replace), not unbounded.

---

### 🔵 Logo restoration — open question, needs user input before doing anything

**Current state (verified in browser):**
- Static "Ask Before You Buy" blue PNG logo pill renders top-left of nav — the user already has this.
- `AnimatedLogo.tsx` exists with full video + audio + sessionStorage-once playback logic, but is not imported anywhere.
- Video, audio, GIF, and PNG assets all present in `frontend/public/images/`.
- "Ask before you buy / book travel" as visible UI tagline text: **zero matches in any branch or commit in repo history.** The only "Ask Before You Buy" is in the `<title>` metadata and inside the static logo pill itself.

**Three interpretations of "add back my logo the ask before you buy book travel etc the gif one" — ask user to pick:**

1. **Restore the animated video logo in place of the static PNG** — import `AnimatedLogo` in `UnifiedTopbar.tsx` (find where the current static `<img src="/images/1815e5dc...png">` lives) and replace with `<AnimatedLogo />`. The component already gates playback with `sessionStorage` so it plays once per session and shows the static logo on subsequent navigations. Effort: ~10 min.
2. **Add a homepage hero tagline strip** ("Ask before you buy · Book travel · Compare reviews · …") as a rotating or static block near the headline. Requires writing a new component since no such hero exists in any branch's git history. Effort: ~30 min.
3. **Both** — animated logo in nav + tagline hero on homepage. Effort: ~45 min.

---

## Out of scope (backlog — do not pull in)

- `product_compose.py` refactor (1400 LOC → composable units) — XL, do as own focused PR
- Saved + Compare feature builds — XL each, blocked on product spec
- Profile page (currently hidden)
- Next.js 15 migration
- Python `requirements.lock` via `uv pip compile`
- Sentry re-add (verify compat first per prior handoff §3a)
- Tiered router activation (prior handoff §4a)
- Skimlinks + Serper Shopping provider restoration (prior handoff §4b)
- `ChatContainer.test.tsx.skip` un-skip
- `kishan_frontend/` deletion — local-only, gitignored, user's call

---

## What is NOT in git (you will need to recreate on a fresh clone)

| Item | Where it was | What to do |
|---|---|---|
| Railway env-var snapshots | `C:\Users\habib\railway-env-backups\backend-production-*.{txt,json,env}` (machine-local on prior dev box) | Re-snapshot on your machine before mutating any env. See Prerequisites above. |
| Env-mutation rollback script | Same dir | Not needed unless you mutate — and per Fix 1 reasoning you should NOT execute the prior session's env mutation. |
| Conversation memory from prior sessions | `~/.claude/projects/<project-hash>/memory/` (local per-machine) | Not portable to new machine. This doc captures the load-bearing facts. |
| `cc.txt` (QA report) | `C:\Users\habib\Desktop\cap\cc.txt` | Already ported to `docs/audits/qa-report-2026-04-21.md` in this commit. |

---

## Execution order

1. **Fix 1 alone** — atomic commit, deploy, manual click-through verification on prod. This stops compliance bleed.
2. **Fixes 2 + 3 + 4** — bundle into one frontend PR. All small diffs, all low risk.
3. **Fix 5** — separate commit after deciding how much time to spend.
4. **Logo restoration** — only after the user picks option 1 / 2 / 3 above.

---

## Rollback plan

All fixes are atomic commits on top of `84d2999`. To revert:

```bash
git revert <commit-sha>
```

Pre-sprint state on `origin/main` is `84d2999`, which is healthy enough to serve the site (with all the bugs above still live). If a backend fix breaks production, Railway's previous deploy can be promoted back via `railway redeploy` after rolling back the commit.

---

## Kickoff prompt (paste this to start the next session)

> Continue the ReviewGuide stabilization work. Read these docs in order: `docs/audits/next-session-prompt-2026-05-19.md` (this is the current handoff — supersedes the 2026-04-22 version), `docs/audits/qa-report-2026-04-21.md`, `docs/audits/opus-4.7-audit-report-2026-04-16.md`. Then run the Prerequisites section (re-snapshot Railway env, npm install, sanity-check `/health`). Start with Fix 1 (positional-zip affiliate mismapping in `backend/mcp_server/tools/product_affiliate.py:174-175`) — but before changing code, read `_fuzzy_product_match` to confirm the threshold convention, and spot-check `curated_amazon_links.py` to see whether premium-brand headphone entries even exist. Use TaskCreate to track. Last known good commit on main: `84d2999`. Verify it's still the head before assuming anything.

---

*Written 2026-05-19. Reality may have drifted by the time you read this — verify against `git log -5 origin/main` before trusting state claims.*
