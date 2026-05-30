# ReviewGuide.ai — QA Test Brief (design preview)

**For:** junior dev doing QA
**What you're testing:** the redesigned frontend on the preview build, against the design blueprint in `frontend/design/` (`DESIGN.md`).
**Build / URL:** `https://reviewguide-ai-git-design-bluep-49fb25-habibs-projects-2039317a.vercel.app/`
(this is a per-branch preview; if it 404s, ask for the current preview link).

> **Important — backend caveat.** This preview is the **frontend only**. The live AI backend is still the old version, so the *conversation logic* (asking budget first, the one-line reasoning note, fresh AI write-ups) may NOT fully work yet. Test the **look, layout, navigation, and interactions** — and for anything that needs a real AI answer, note "needs backend" rather than logging it as broken.

---

## Setup (do this first)
1. Always **hard-refresh** before testing: `Ctrl + Shift + R` (Win) / `Cmd + Shift + R` (Mac). The app caches JavaScript, so a normal reload can show a stale version.
2. Test on **both**: desktop Chrome AND a phone (or Chrome DevTools mobile view, iPhone 14/15 size).
3. Also do one pass in an **incognito window** (rules out cache).
4. Compare what you see against `frontend/design/DESIGN.md` (the spec) and the screens in `frontend/design/lib/screens-*.jsx`.

## How to report each issue
Use this format (one per issue), in a shared doc or as GitHub issues:

```
Title: [Screen] short description
URL / page:
Device + browser:
Steps to reproduce:  1) … 2) … 3) …
Expected (per design):
Actual:
Severity: Blocker / Major / Minor / Polish
Screenshot/recording: (attach)
```

**Severity guide:** Blocker = can't use the feature / broken page. Major = wrong behavior or clearly off-design. Minor = small visual/spacing issue. Polish = nitpick.

---

## A. Behavior questions to judge (NOT just bugs)
These are UX calls — give your opinion + what the design implies, don't just pass/fail:

1. **Category chips firing canned queries.** On Discover, tapping a category (e.g. **Outdoor**) jumps straight into a chat pre-loaded with a hardcoded query ("best camping gear for beginners"). Question to evaluate: should tapping a category instead **(a)** drop you into the search box with that category as a starting point you can edit, **(b)** show a category landing/browse view, or **(c)** do nothing until you type? Document the current behavior for every chip and flag which ones feel wrong/presumptuous.
2. **"Popular this week" rows** — same question: tapping a row launches a canned chat. Is that the right action, or should it preview first?
3. **Empty/placeholder states** — do Saved, Compare, and About-You read sensibly when there's no data yet?
4. **Anything that feels "auto-decided for the user"** — note it. The product voice is "ask before you buy," not "assume for you."

---

## B. Screen-by-screen checklist

### 1. Discover (home `/`)
- [ ] Terracotta speech-bubble logo shows, and the last word **rotates** (Buy → Eat → Fly → Stay → Book → Subscribe).
- [ ] Headline "What are you researching?" is in the italic serif font.
- [ ] "TRENDING RIGHT NOW" chips scroll sideways; tapping each one (log where each goes — see A.1).
- [ ] "POPULAR THIS WEEK" is a vertical list (icon tile + title + one-line take + chevron), NOT a grid of pastel circles.
- [ ] Search box: typing a query + Enter starts a chat with YOUR text (not a canned one).
- [ ] Reduced-motion: turn on OS "reduce motion" → the rotating word should stop on "Buy".

### 2. Logo / header / nav
- [ ] Logo is the text wordmark **Review**(terracotta) **Guide**(dark) **.Ai**(terracotta) — NOT an image.
- [ ] No blue anywhere. Accents should be terracotta.
- [ ] Top nav + bottom tab bar (mobile) navigate correctly; active tab is highlighted.

### 3. Chat
- [ ] Your messages = dark bubble, right side. AI = light bubble, left side, with rounded corners (one corner squared).
- [ ] Loading state = a single pulsing terracotta dot + rotating "Reading the room…" style text (NOT three dots, NOT "Thinking…").
- [ ] Suggestion chips are rounded rectangles with a small terracotta dot, left-aligned (NOT pills).
- [ ] Composer (text box) sits at the bottom, pill-shaped, with a dark round send button.
- [ ] *(Needs backend)* Asking about a product should ask budget first, then show a write-up. If the AI answer never comes / errors, mark "needs backend."

### 4. Product cards (in chat results)
- [ ] Card has image on top, a small-caps role label ("Top pick", etc.), title in serif, price, and a **Buy** button.
- [ ] **Save bookmark** (top-right of card): tapping it fills in terracotta with a little ring animation; tapping again un-saves. No popup/toast.
- [ ] A saved item then appears on the **Saved** page.
- [ ] No leftover green/blue accents on the cards.

### 5. Saved (`/saved`)
- [ ] Saved products show in a 2-column grid with the terracotta bookmark filled.
- [ ] Tapping two cards selects them (terracotta check appears) and a "Compare · 2" button enables.
- [ ] Empty state (nothing saved) reads sensibly.

### 6. Compare (`/compare`)
- [ ] With two items selected, shows both side by side + a "THE VERDICT FOR YOU" section + two action buttons.
- [ ] With fewer than two selected, shows the "pick two to compare" prompt.

### 7. Product detail (`/product/...`)
- [ ] Reached by tapping a product name; shows big image, name, price, Buy button, and a "get the full breakdown" prompt.

### 8. About-You (`/profile`, or the You/Profile tab)
- [ ] Shows the "MVP state" banner + "Still getting to know you." + the dashed placeholder cards. (This is intentionally an empty state.)

### 9. Cross-cutting
- [ ] **Responsive:** every screen looks right on phone width (no overflow, no cut-off text, tap targets big enough).
- [ ] **Dark mode** (if there's a toggle): no broken contrast, still terracotta accents.
- [ ] **Console:** open DevTools → Console; report any red errors per page.
- [ ] **Broken links / 404s:** click everything; note anything that dead-ends.

---

## C. What "good" looks like
The whole thing should feel like a **warm editorial magazine** (cream paper, terracotta accents, serif headlines) — not a generic blue SaaS app. If a screen still feels like the "old" blue/grid style, screenshot it and flag it.
</content>
