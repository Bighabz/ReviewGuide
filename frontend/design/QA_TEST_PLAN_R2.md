# ReviewGuide.ai — QA Brief, Round 2 (LIVE production)

**For:** junior dev doing QA
**What changed since round 1:** the redesign is now **merged and live in production**, and the **backend is deployed too** — so this round we test the *real conversation flow* (budget-first question → reasoning note → write-up), re-verify the round-1 fixes, and finally cover **mobile** (which round 1 couldn't).
**URL:** `https://reviewguide.ai` (the real site, not a preview).

## Setup
1. **Hard-refresh** first: `Ctrl/Cmd + Shift + R`. Do one pass in **incognito** too.
2. Test on **desktop Chrome** AND a **real phone** (round 1 couldn't verify mobile — this is a priority now).
3. Reporting format (one per issue):
   ```
   Title: [Screen] short description
   URL / page · Device + browser
   Steps: 1) … 2) … 3) …
   Expected: …   Actual: …
   Severity: Blocker / Major / Minor / Polish
   Screenshot/recording
   ```
4. Spec to compare against: `frontend/design/DESIGN.md`.

---

## STEP 0 — Confirm the backend actually deployed (do this first)
Ask the chat: **"best wireless earbuds"** (just that, no budget).
- ✅ **Expected (new backend live):** it asks a **budget question first** (e.g. "what's the rough budget?") with tappable options, BEFORE giving picks.
- ❌ If it jumps straight to product picks with no budget question → the new backend is NOT live yet. **Stop and report this immediately** (it means the deploy didn't swap); the conversation-flow tests below won't be valid until it's fixed.

---

## A. The conversation flow (NEW — the main event)
Run a full product research conversation and check each beat:
1. **Budget-first** — on a non-trivial product ask, the AI asks budget before recommending. The budget options are tappable chips (rounded rectangles, small terracotta dot, left-aligned — NOT pills).
2. **Transitional note** — after you answer the budget, is there a short one-line italic aside (e.g. "$X puts the mid-tier on the table — that changes the pick…") *before* the write-up? Note: this only shows when your answer actually changes the recommendation, so it may not appear every time — log when it does/doesn't.
3. **Editorial write-up** — the answer reads like a short magazine piece: a "THE PICK" label, a serif verdict line, body copy in the serif font — NOT a wall of plain text or a bare list.
4. **The shortlist** — product cards appear below the write-up: image on top, a role label ("Top pick"), serif name, price, a **Buy** button, and a **save bookmark** (top-right).
5. **Follow-up** — a single curious follow-up question at the end of the write-up, on its own line.
6. **Ask a second question** in the same chat — does the *previous* write-up collapse down to a short line (with a "Show the full take" link) while the new one stays full-size?
- Judgement call: does the whole exchange feel like it's *asking and reasoning with you* (the "ask before you buy" voice), or does anything still feel auto-decided?

## B. Re-verify the Round-1 fixes (regression check)
- [ ] **Chat empty screen** — opens with "What are you trying to figure out?" in serif. **No blue logo / no glitchy video.** (This was the big round-1 bug.)
- [ ] **Save flow works end-to-end:** tap a card's bookmark → it fills terracotta → go to **Saved** → the item is there → tap two saved items → "Compare · 2" enables → Compare shows them side by side.
- [ ] **Product name is clickable** → opens the product detail page.
- [ ] **Discover chips/rows are editable, not auto-fired:** tap "Outdoor" (or any category) → it should drop you into the chat with editable text in the box that you press Enter to send — it should NOT instantly send a canned query.
- [ ] **Discover layout:** "TRENDING RIGHT NOW" chips + "POPULAR THIS WEEK" vertical list with terracotta icons (no pastel circle grid).
- [ ] **Send button** in the composer is a visible circle (not invisible).
- [ ] **No blue anywhere**; pros/cons in write-ups use "+ / —" not green/red.

## C. Mobile (priority — round 1 couldn't test this)
On a real phone:
- [ ] Every screen fits — no horizontal scroll, no cut-off text, tap targets usable.
- [ ] Bottom tab bar (Discover / Saved / Ask / Compare / You) shows and navigates.
- [ ] The sticky composer stays at the bottom and isn't hidden by the keyboard awkwardly.
- [ ] Discover, chat, cards, Saved all look right at phone width.

## D. Cross-cutting
- [ ] **Reduce motion:** turn on your OS "reduce motion" setting → the rotating word in the Discover bubble should stop on "Buy" (round 1 couldn't test this).
- [ ] **Console:** open DevTools → Console; report red errors per page. (The 401 history errors from round 1 — check if they're gone now that backend is live.)
- [ ] **Dark mode** (toggle in nav): terracotta preserved, good contrast, no blue.
- [ ] **Broken links / 404s:** click everything.

## E. What "good" looks like
Warm editorial magazine — cream paper, terracotta accents, serif headlines, a chat that *asks before it assumes*. Flag anything that still feels like a generic blue SaaS app or that decides for the user.

---
*Report back grouped by section. Severity guide: Blocker = broken/unusable · Major = wrong behavior or clearly off-design · Minor = small visual issue · Polish = nitpick.*
