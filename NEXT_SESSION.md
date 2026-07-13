# NEXT SESSION — Launch Focus (updated 2026-07-03)

**Read this first.** The product is feature-complete and prod-stable. The ONLY goal now is the soft launch.
Do not pick up feature handoffs (`docs/handoffs/`) until every open item below is closed.

**Launch decisions (Habib, 2026-07-03):** soft launch (public link, iterate fast) · affiliate revenue must work day 1 · PR #122 (v0 redesign) PARKED · search-credit funding deferred (free SerpApi failover carries prod — accepted risk).

## 1) Blockers needing HABIB (agent applies each value as it arrives)

| # | Item | Why | How |
|---|------|-----|-----|
| 1 | **eBay EPN campaign ID** | Prod `EBAY_CAMPAIGN_ID=1234567890` is a placeholder → every eBay affiliate link earns **$0**. THE day-1-revenue blocker. | partner.ebay.com → Campaigns → copy `campid`, paste in chat. Agent sets it + live-verifies a prod card link carries it. |
| 2 | **Rate-limit go-ahead** | `RATE_LIMIT_ENABLED=false` in prod (dogfooding override). Flip attempt on 2026-07-03 was blocked by permissions — needs live say-so. | Habib runs `railway variables --service backend --set "RATE_LIMIT_ENABLED=true"` (triggers redeploy) or tells the agent "flip it". Verify: 21 rapid chat requests from one IP → 21st gets HTTP 429. |
| 3 | **Merge PR #123** | robots.txt + sitemap.xml + Vercel Analytics (draft, CI-green). Vercel auto-deploys on merge. | github.com/Bighabz/ReviewGuide/pull/123 |
| 4 | **Sentry DSNs** | Sentry fully wired in code, DSNs unset → zero error visibility at launch. | Create Sentry project (Next.js + Python), paste both DSNs. Agent sets `NEXT_PUBLIC_SENTRY_DSN` (Vercel) + `SENTRY_DSN` (Railway). |
| 5 | **Rotate exposed keys** | OpenRouter + 2× SerpApi keys appeared in past chat transcripts. | Mint replacements, paste in chat. Agent sets on Railway (never echoes), verifies search+compose still work. |
| 6 | **`OPENAI_API_KEY` GH secret** | CI eval gates skip silently without it. | `gh secret set OPENAI_API_KEY --repo Bighabz/ReviewGuide` (or paste; agent sets via stdin). |
| 7 | *(optional)* Skimlinks publisher ID | Extra affiliate coverage; code is dormant-ready. | Set `SKIMLINKS_PUBLISHER_ID` + `SKIMLINKS_API_ENABLED=true` on Railway — zero code. |

## 2) Agent work once values land

1. Set the env vars above (Railway via `railway variables --service backend --set`; Vercel via dashboard or `vercel env`).
2. **Launch smoke test** (prod, Playwright + curl): fresh chat → clarifier → results with real prices → eBay link contains the real campid → OG share unfurl → `/robots.txt` + `/sitemap.xml` 200 → Sentry test event received → rate-limit 429 fires → travel query renders hotel/flight/itinerary blocks.
3. Update `project_launch_checklist` memory + this file: flip items to DONE.

## 3) Current state (so you don't rediscover it)

- **main** = deployed prod; verify any merge via `/health` `.version` (see CLAUDE.md → Production Reality).
- **PR #123** `launch/seo-analytics` — draft, ready, awaiting merge (item 3).
- **PR #122** `feat/v0-redesign` — PARKED by decision; the main checkout sits on this branch; v0 inputs archived in `archive/v0-handoff/`.
- **Travel: WORKS, verified E2E in prod 2026-07-03.** Keyless by design — affiliate-tagged Expedia PLP deep links + LLM itinerary (details: CLAUDE.md → Production Reality → Travel). Post-launch upgrades if wanted: real inventory via Amadeus/Booking/Skyscanner keys; fix clarifier asking departure city on hotel-only queries.
- **Rate limiting** defaults ON in code; prod override is the only thing keeping it off.
- **Auth is admin-only BY DESIGN** — guest chat is the product; no public accounts planned for launch.

## 4) Parked (do NOT work on these until launch is done)

PR #122 v0 redesign · compose Step 7 (decoupled streaming, `USE_DECOUPLED_COMPOSE`) · conversational Outcomes 5–8 (`docs/handoffs/CONVERSATIONAL_ENGINE_HANDOFF_V2.md`) · QA Round 8 polish items (`docs/handoffs/QA_ROUND8_HANDOFF.md`) · cookie-consent banner · load testing · travel inventory keys · Serper credit funding.

## 5) Post-launch queue (first things after launch day)

1. QA_ROUND8 polish batch (stale retry stub, truncated chip, comparison one-side cards, `--ink-3` contrast).
2. Compose decouple+streaming are BUILT but OFF (PRs #112/#113) — enabling is a flag flip (`USE_DECOUPLED_COMPOSE`, streaming flag) + prod verification.
3. Search-credit decision (Serper ~$50 top-up vs SerpApi $75/mo) before real traffic scales.
4. Travel clarifier quirk + travel inventory decision.
5. Re-evaluate PR #122 redesign.

## Housekeeping notes (2026-07-03 hardening pass)

- Local branch `fix-provider-coverage` holds one unmerged commit (`7db3801`, affiliate_products passthrough + ~200 lines of tests). The fix itself was **superseded** by the merged price-pipeline PRs (main already propagates `affiliate_products`), but the tests may be worth salvaging into a small PR. Its worktree was removed; the branch was kept.
- Branches `design/blueprint-implementation` and `feat/dreambeans-principles` have unmerged tips (old prototypes whose shipped versions went in via other PRs) — safe to delete after a quick `git log main..<branch>` sanity check.

## Security note (2026-07-03 hardening pass)

`users.txt` (a `username,password-hash` artifact) was removed from tracking but **remains in git history** — if `ben`'s password is weak/reused, rotate it. History scrub (filter-repo) deliberately skipped: repo is private and rewriting shared history breaks clones; revisit only if the repo ever goes public.
