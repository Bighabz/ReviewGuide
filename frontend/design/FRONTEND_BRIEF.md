# ReviewGuide.ai — Front-End Brief & Implementation Plan (authoritative)

> Durable, committed copy of the session handoff. `.continue-here.md` may be reverted by concurrent agents — **THIS file is the source of truth.** Last updated 2026-05-31.

## Authorization (user, 2026-05-31)
**Autonomous merge + deploy to production is AUTHORIZED — no per-change review.** Proceed implement → test → PR → merge → deploy → verify without waiting for approval. Be autonomous, not reckless — standing gates that REMAIN:
1. Base each change on the latest `main` (`git fetch origin main` first).
2. **CI must be green before merging** — never merge red CI.
3. **Verify each deploy after it lands** (Railway MCP `list_deployments` / behavioral canary on `/v1/chat/stream` / the prod Playwright re-scan) and report the result.
4. **STOP and report** (don't force) if: CI fails, a deploy fails, verification fails, or a change is destructive/irreversible beyond a normal app deploy (data loss, secret exposure, deleting prod resources, schema-destructive migrations).
5. Don't bypass hooks or branch protection; don't skip signing.

## Current state
Live on production (reviewguide.ai). Recently SHIPPED:
- **Real prices** via Serper Google Shopping + live-eBay fallback — PRs #31/#33 (main `30e750f`). Cards/Saved/Compare show real prices (was $0).
- **QA Round 3 + a11y** — PR #35 (main `a07e49f`): `/results/[id]` hydration fix, Compare float, budget-ceiling, mobile tap targets, favicon, nav/profile contrast. Prod-verified.

**Desktop view = CLEAN** (verified 1904px, dpr 1): full chat flow streamed fine — 0 console errors/hydration, all 65 requests 200 (incl. `/v1/chat/stream` POST), product cards render correctly. The two REAL reproducible front-end bugs are **mobile-only** (Notes 1 & 2). The Note 5 "renderer freeze" was a **DevTools mobile-emulation artifact** (dpr 3.5 CPU-heavy), did NOT reproduce on real desktop — downgraded to "spot-check on a real phone."
**Non-issue:** hero "Ask Before You **Eat**" is INTENTIONAL — the Discover hero is the animated WebP (`DiscoverHeroLogo.tsx`) whose animation cycles the rotating tagline (Buy→Eat→Fly→Stay→Book→Subscribe, per `frontend/design/uploads/reviewguide-spec.md:715`). Static surfaces (`Brand.tsx WordmarkStatic`, `layout.tsx` title) say "Buy". No action.

## Design tokens (REUSE — NO blue anywhere)
Defined in `frontend/app/globals.css` (:root + [data-theme=dark]):
- accent `--terra #b8543a`; hover `--terra-ink #7a3624`; soft wash `--terra-soft #f4e2d7`
- bg `--paper #fafaf7`; alt `--paper-alt #f5f4f0`; elevated `--paper-hi #fff`; card-accent tints `#fff8f0 / #fafaf7 / #f5f4f0 / #f4e2d7`
- text `--ink #1a1816`; `--text-secondary/--ink-2 #6b6560` (AA-passing); `--text-muted/--ink-3 #9b9590` (FAILS AA on paper — decorative only)
- borders `--line #e8e6e1` / `--line-2 #d4d1cc`; shadows `--shadow-card/md/lg/xl/float`; status success `#2b5337` / warning `#c08a2e` / error `#9b3a2d`
- ⚠️ `frontend/lib/trendingTopics.ts` has legacy `iconBg`/`iconColor` BLUE pastels (`#EFF6FF`/`#3B82F6`), currently unused — do NOT resurrect them.

## Work queue (value × low-risk)

### GROUP A — Mobile layout fixes (quick, frontend-only)
- **A1 — chat title truncates on mobile.** `frontend/components/MobileHeader.tsx:56` title `<div className="text-sm font-medium truncate">` (text = `useChatStatus().sessionTitle`; parent :54 `flex-1 text-center px-2 min-w-0`). UnifiedTopbar (desktop) shows no title → mobile-only. FIX: `truncate` → `line-clamp-2 sm:truncate`. (Message bubble is fine — `whitespace-pre-wrap`.)
- **A2 — product card crushed on mobile.** `frontend/components/ProductReview.tsx`: row `flex gap-4` (:129) → fixed image `w-24 h-24` (:131) → text col `flex-1 min-w-0` (:139) → inner `flex items-start justify-between gap-2` (:140) → title `<h3 rg-serif hover:underline>` (:148) crushed to ~47px. NO responsive prefixes. FIX: :129 → `flex flex-col sm:flex-row gap-4`; :131 → `w-16 h-16 sm:w-24 sm:h-24`; text col → `w-full sm:flex-1 sm:min-w-0`. **Confirmed mobile-only** (desktop renders cleanly). Also check `ProductCarousel.tsx` `ProductImage` stacks.

### GROUP B — Dynamic + personalized chat starter content
`frontend/components/ChatContainer.tsx`: greeting "What are you trying to figure out?" (:778); 3 chips array (:793); chip click (:796-799) = `setInput(s)` + `handleSendMessage(s)` (AUTO-SENDS).
- **MIRROR `frontend/components/HeroSubline.tsx`** — rotates subtext from a `HERO_SUBLINES` array: SSR renders index 0, client picks random on mount → no hydration mismatch. Use this exact pattern (do NOT `Math.random()` during render).
- Phase 1 (cold-start): curated pool of greeting + chip-set variants, randomized per load.
- Phase 2 (personalize): bias from `frontend/lib/recentSearches.ts` (localStorage, written ChatContainer.tsx:561), `frontend/lib/savedItems.ts`, and backend `backend/app/services/preference_service.py` (per-user `User.preferences` JSON: brands/categories/budget_ranges/features/use_cases). Cold = random; warm = weighted to user's categories/brands.

### GROUP C — Discover "Popular this week" → Netflix-style carousel (the big build)
Current: `frontend/components/discover/TrendingCards.tsx` renders 6 text cards from `frontend/lib/trendingTopics.ts` (`{id,title,subtitle,query,icon,iconBg,iconColor}`); click (:41) → `/chat?draft=<query>&new=1`.
**USER DECISION (2026-05-31):** entertaining, image-rich, horizontally-swiping Netflix title-picker carousel. **Pool of ~40–50 topics, fresh rotated subset each visit. REMOVE click-to-preload.** Card click → **dedicated topic landing page** (new route `frontend/app/topic/[slug]/page.tsx` — curated editorial intro + CTA into research). Exciting copy. Terracotta tokens only (card bg = card-accent tints / `--terra-soft`, `--shadow-float`, gradient overlays).
- **Images (reuse):** `public/images/browse/*.jpg` (10 photos), `public/images/categories/cat-*.webp` (15 — prefer webp; the `.png` siblings are ~1MB each, see D4), `public/images/products/mosaic-*.webp`, `public/images/travel/hero-*.webp`.
- **Rotation w/o hydration bugs:** SSR deterministic subset, shuffle client-side in `useEffect`/mount (HeroSubline pattern). No `Math.random()`/`Date.now()` in render.
- New topics data module (40–50 entries: slug, title, hook copy, image, category, research query, editorial blurb). The landing page (not the carousel) is where the "into research" CTA enters chat with the query — carousel stays browse-only.
- Keep/refresh `data-testid="trending-card"` and any test expectations.

### GROUP D — Performance hygiene (NOT urgent — freeze was an emulation artifact)
- **D1** `frontend/public/images/animated_logo.webp` = **2.26 MB**, loads every Discover visit (`DiscoverHeroLogo.tsx`). Regenerate smaller/shorter-loop, lazy-load, or static-first-then-swap. (reduced-motion already → 33KB PNG.)
- **D2** chat Serper product images are **base64 `data:image/webp` data-URIs** at runtime (~7–9KB each → ~130–240KB/SSE; confirmed live — a static read claimed "URLs," trust the runtime). In `backend/app/services/serpapi/client.py::search_shopping_offer`, skip `data:` URIs / keep only `http(s)` (cards fall back to eBay https image) to slim the payload.
- **D3** `ChatContainer.tsx:116` 2.5s `setInterval` (verb cycle); `Message.tsx:82` 60s per-message timestamp interval. Minor; pause offscreen/streaming.
- **D4** ~13 MB unused `public/images/categories/cat-*.png` (rendered nowhere) — consume in Group C (webp) or remove.

### GROUP E — Backend / data
- **E1 Product Detail (`/product/[id]`) is placeholder.** `frontend/app/product/[id]/page.tsx` reads `sessionStorage('active_product')`/`savedItems` (name/price/imageUrl/url/role only); "Why it's your pick" (lines 108-119) is HARD-CODED, button restarts chat. No specs/pros-cons/honest-notes, no product-detail API. To make real: persist/expose the per-product analysis product_compose already has (review summary, pros/cons, sources, editorial label) via an endpoint or richer handoff payload, then render real sections. Significant backend+frontend.
- **E2 `transitional_reasoning` rarely emitted** — frontend wired (TransitionalBubble) through all 5 GraphState layers, but the composer seldom produces it. Prompt-tune the product_compose LLM prompts. See memory `project_graphstate_passthrough_layers`.

### GROUP F — Housekeeping / infra
- **F1 `/health` version = "unknown".** `backend/app/api/v1/health.py::_running_version()` reads `RAILWAY_GIT_COMMIT_SHA` then `GIT_SHA` then "unknown". Root cause: the deploy workflow uses Railway CLI (`railway up`/redeploy) which does NOT inject `RAILWAY_GIT_COMMIT_SHA` (only native GitHub integration does), and Docker isn't passed a `GIT_SHA` build-arg. FIX: pass the commit SHA from the workflow. ⚠️ Likely IN-FLIGHT on `fix/voice-gate-harden` / `chore/railway-autodeploy` — coordinate.
- **F2** `git rm --cached` + `.gitignore` the 2.23 MB `frontend/design/ReviewGuide standalone.html`.
- **F3** `.claude/settings.json` has the `.env`-edit block hook (verify it blocks); add prettier auto-format hook via `/update-config` (confirm prettier present).
- **F4** `/login` `<video>` not mounting (admin-only, low priority).

## Decisions made
- Note 4 → dedicated `/topic/[slug]` landing pages; ~40–50 topic pool, rotate per visit; remove preload; Netflix carousel; terracotta only.
- a11y = surgical token repoint (not global bump); budget = offer-level enforcement only.
- Starter content phased: cold-start random pool → personalization layer (reuse preference_service + recentSearches + savedItems).

## Gotchas
- **Hydration:** no `Math.random()`/`Date.now()`/`new Date()` in render — mirror `HeroSubline.tsx`. This caused the `/results/[id]` #418/#423 cluster (fixed via mount guard).
- **`next/og` ImageResponse breaks the Windows build** (`@vercel/og` Invalid-URL on Windows font paths) — use a static favicon (`app/icon.png` + `app/favicon.ico` already added). ffmpeg drawtext on Windows: copy the font into cwd, reference by bare filename.
- Tests = **vitest** (`cd frontend && npm run test`), not jest; `npm run lint` may prompt interactively (pre-existing) — rely on `npm run build` for type/lint gating. Backend pytest needs `RAILWAY_TOKEN` unset.
- **Railway MCP token expires mid-session** → `! railway login` + `/mcp` reconnect. `/health` can't confirm SHA (F1) — verify via Railway MCP `list_deployments` or a behavioral canary (anonymous `POST /v1/chat/stream`; `current_user` is Optional).
- **CONCURRENCY:** many active branches — `fix-provider-coverage`/`worktree-fix-provider-coverage` (affiliate_products passthrough), `chore/railway-autodeploy` (Railway Dockerfile + CI deploy), `fix/voice-gate-harden` (/health SHA + voice). Base PRs on latest `main`; check these before touching F1 or price/passthrough code.
- Three product cards (CLAUDE.md Component Map): chat = ProductReview.tsx / ProductCarousel.tsx, /results = ResultsProductCard.tsx.

## Verification
- Frontend: `cd frontend && npm run build` (gates types/lint) + `npm run test` (vitest, 256 baseline). Local prod check: `PORT=3100 npm run start` then Playwright via `NODE_PATH=".../frontend/node_modules" node <script>`. Mobile checks at 412×915 + 390×844.
- a11y: compute WCAG ratio in a Playwright eval (no axe installed) — ≥4.5:1 text; tap targets ≥40px.
- Backend: `RAILWAY_TOKEN= python -m pytest -q` (444 baseline). Live canary vs `backend-production-0ae7.up.railway.app`.
- Reusable Playwright harness from the QA sessions: `C:\Users\habib\AppData\Local\Temp\rg_qa\` (verify_prod.js, taptargets.js, verify_hydration.js).

## Suggested sequence
A (mobile fixes, quick win) → B (dynamic starter) → C (carousel + topic pages — own multi-PR effort) → D (perf hygiene) → E (Product Detail backend). F2 anytime; coordinate F1 with in-flight branches.
