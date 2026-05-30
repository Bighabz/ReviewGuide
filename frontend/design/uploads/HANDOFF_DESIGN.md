# ReviewGuide — Design handoff (logo + Discover update)

Fresh session. This is a **delta brief**, not a full design pass. The first design pass is done and locked — see `reviewdesign1.pdf` for the system (color, type, ten screens). This handoff covers the changes that came out of a stakeholder review after that pass.

---

## Read first

In this order:

1. **`tone.md`** — voice & personality. Gospel. Two new sections were just added (see "What changed" below).
2. **`reviewguide-spec.md`** — full design spec. §11.7 (Logo & wordmark) is new. §7.10 is now marked MVP-placeholder.
3. **`reviewdesign1.pdf`** — the locked first design pass. Everything in it stands except where this brief overrides.

---

## What's already locked (don't re-litigate)

The design system from `reviewdesign1.pdf`:

- **Colors:** Terracotta `#B8543A` on Cream `#FAFAF7`, Ink `#1A1816`. Full system in §00 of the PDF.
- **Type:** Instrument Serif Italic (display) · Newsreader 16/26 (blog body) · DM Sans (UI).
- **Components:** chat bubbles, suggestion chips (rounded-rect, dot-led, asymmetric), inline product link (dotted terracotta underline, 4px offset), carousel card (240×320, role label small-caps, image-top 75%), save toggle (fill + ring expand), sticky composer (cream gradient mask). All defined in PDF §00.
- **All ten screens** as rendered in PDF §01–§07.
- **Decisions log** (PDF §07): each of the spec's ten §13 open questions has been answered with reasoning. Don't re-open them.

This handoff is **additive** to all of the above.

---

## What changed

### 1. The logo is coming back

The stakeholder wants the existing **"ReviewGuide.Ai"** wordmark restored, in the new color system. The existing logo is sans-serif with a speech-bubble container and a rotating tagline word ("Ask Before You [Eat / Fly / Subscribe / …]"). The recolor maps:

| Element | Was | Now |
|---|---|---|
| "Review" + ".Ai" | Saturated cyan `#22B8E6` | Terracotta `#B8543A` |
| "Guide" | Dark navy `#1A2E5B` | Ink `#1A1816` |
| Bubble stroke | Cyan | Terracotta |
| Background | White | Cream `#FAFAF7` |

Wordmark structure stays identical: **Review** + **Guide** (different weight) + **.Ai**, with the bubble outline and downward-pointing tail.

### 2. Two treatments

**A. Discover hero (full bubble + rotating word):**
- Full speech bubble outline, large, centered at the top of the Discover screen
- Wordmark inside the bubble
- Below the wordmark inside the bubble, the tagline: **"Ask Before You [word]"** with the final word rotating every ~2.4s through: **Buy → Eat → Fly → Stay → Book → Subscribe**
- This is the only place the bubble outline appears in the entire product

**B. Every other page (small static wordmark):**
- Same wordmark, scaled down, top-left of the page header
- **No bubble outline**
- Tagline is static: **"Ask before you buy"** (no rotation)

### 3. Discover hero composition update

The serif greeting *"What are you researching?"* stays — but **smaller, below the bubble logo, where it always was**. The composition is now:

```
[ full bubble logo with rotating tagline word ]
       What are you researching?      ← serif italic, smaller than current hero size
       [ composer input ]
       Trending right now…
       Popular this week…
       Pick up where you left off…
```

Both the bubble and the greeting are visible. The bubble is the hero element; the greeting is the editorial voice underneath it.

### 4. Tagline becomes the brand line

*"Ask before you buy"* is now the product's positioning sentence and shows up wherever the wordmark does. This is documented in spec §1.

### 5. Personality profile — MVP placeholder

The §7.10 "About you" screen stays in the IA but is **static for MVP**. It renders the empty-state copy (*"Still getting to know you. Ask a few things and this fills in."*) and reserves the route, but the underlying personality-memory system (Honcho) is deferred to post-MVP. The full §7.10 spec describes the post-MVP target, not the v1 build.

You can deprioritize visual exploration of the populated state of this screen for now — the placeholder treatment from PDF §06 (the populated mockup) becomes a post-MVP reference. For MVP, only the empty-state version of the screen is needed.

---

## What's new in tone.md (relevant to microcopy decisions in your mockups)

Two new sections were added that you should pull from for any new microcopy:

### "Synthesized authority phrasings"

The product's no-citations rule now has concrete substitute phrasings. Use these freely in any AI-voice copy you produce:

- *"The biggest praises are…"*
- *"The most common complaint is…"*
- *"What owners keep mentioning is…"*
- *"What matters after six months is…"*
- *"The tradeoff nobody talks about is…"*
- *"Where people get frustrated is…"*
- *"The thing that surprises most buyers is…"*

Plus a confidence-framing set: *"This is the easy call." / "Two options are very close. Here's the tradeoff." / "You're overthinking this one — the gap is smaller than the price difference suggests."*

### "Ask before suggesting" + "Asking is the product's intelligence signal"

Two related additions to the quiz-path voice:

- **Budget is the default first question** on any non-trivial purchase. Asking budget first lets every subsequent suggestion be grounded; asking it later feels like sales-then-walkback.
- **Transitional reasoning bubbles**: between quiz turns, when a user's answer triggers a real inference, the AI surfaces it briefly before the next question. *"Got it — glasses changes the shortlist. The clamp matters more than the spec sheet on this one. One more question:"* This is the "whoa, it gets me" moment.

If you do a quiz-path refresh, the transitional reasoning bubble is a new component worth visualizing. It's not a question, not a final blog — it's an intermediate AI bubble that shows reasoning between turns.

---

## What you're being asked to produce

In rough priority order:

1. **The recolored logo, both treatments.** Vector wordmark + bubble, in terracotta/ink on cream. Two versions: full-bubble-with-rotating-word for Discover, small-static-wordmark for every other page. Exported as SVGs for the build.
2. **Updated Discover screen** showing the new composition: bubble at top, serif greeting underneath at smaller size, then the existing trending / popular / recent sections from PDF §02.
3. **Updated page-header treatment** showing the small wordmark top-left on at least Chat, Results, Saved, and About-you. This replaces whatever header treatment is in PDF §03–§07 for those screens.
4. **Tagline rotation behavior spec** — a short note on the animation curve, timing, and word list. The current call is ~2.4s per word, simple opacity crossfade.
5. **Quiz-path transitional reasoning bubble** — new component. Visualize how it differs from a normal AI bubble (more parenthetical, perhaps lighter weight or shorter, sitting between a user's answer and the next AI question).

---

## What you're NOT being asked to do

- Re-open any §13 open question that was answered in PDF §07
- Redesign any screen wholesale — this is a delta on top of the locked pass
- Explore the populated state of the About-you screen (deferred to post-MVP)
- Design notifications, sharing, or virality surfaces (explicitly out of scope for MVP)
- Design influencer-facing pages (out of scope for MVP)
- Design SMS / text-notification surfaces (out of scope for MVP)

---

## How to engage

- The first design pass is **strong**. Honor the system; don't drift.
- The logo is the one place in the product that nods to chatbot visual vocabulary (the bubble). It exists once, on Discover. Don't sprinkle bubble shapes elsewhere — that breaks the editorial register.
- The rotating word is half the personality of the original logo. Keep it on Discover; never elsewhere.
- For the small static wordmark, the absence of the bubble is what makes it work — it reads as a wordmark, not as an AI-app logo.
- If you spot a conflict between this brief and the locked PDF, this brief wins — but flag it.

---

## Reference files

- `tone.md` (updated)
- `reviewguide-spec.md` (updated)
- `reviewdesign1.pdf` (locked first pass)
- `animated_logo.mp4` (the original logo with the rotating word, for animation reference)
