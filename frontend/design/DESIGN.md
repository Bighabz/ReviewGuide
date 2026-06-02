# ReviewGuide — design implementation handoff

This document is the **plain-text bridge** between the design canvas (in JSX) and the build phase. It captures the system, every component, every screen, every decision in a form a coding agent can read directly.

If you have the project zip, the JSX files are the source of truth — this doc is a navigable summary.

---

## 1. Files

```
ReviewGuide.html              ← entry point (design canvas)
ReviewGuide-print.html        ← print/PDF version (auto-fires window.print)
app.jsx                       ← composes the canvas
app-print.jsx                 ← composes the print layout
design-canvas.jsx             ← pan/zoom canvas component (starter, do not modify)
lib/
  tokens.js                   ← design tokens (color, font, radius, shadow, CSS injection)
  atoms.jsx                   ← Phone / StatusBar / TabBar / chat bubbles / chip / composer / etc.
  logo.jsx                    ← Wordmark, LogoHero (Discover bubble), HeaderBrand, TransitionalBubble
  foundation.jsx              ← System cards: color identity, type, components, decisions, feedback
  screens-flow.jsx            ← Discover, Chat (empty / fast / quiz)
  screens-results.jsx         ← Results, Product detail
  screens-meta.jsx            ← Loading, Saved, Compare, About-you (MVP empty + populated)
  v2-delta.jsx                ← V2 cards: logo system, rotation spec, transitional bubble, quiz v2
```

---

## 2. Design tokens (lib/tokens.js)

### Color

```
paper      #FAFAF7   primary background — warm off-white
paperHi    #FFFFFF   raised surfaces (bubble fill, sheet)
paperAlt   #F5F4F0   sunken surfaces

ink        #1A1816   primary text — warm near-black
ink2       #6B6560   secondary text
ink3       #9B9590   tertiary / muted

line       #E8E6E1   1px hairlines, dividers
line2      #D4D1CC   slightly stronger borders

terra      #B8543A   primary accent — muted terracotta (WCAG AA at 14pt)
terraSoft  #F4E2D7   12% tint (save fill, verdict cards)
terraInk   #7A3624   hover / pressed terracotta

danger     #9B3A2D   destructive (reset button)
```

### Type

| Face | Use | Weights | Size range |
|---|---|---|---|
| **DM Sans** | UI: chips, buttons, nav, prices, eyebrow labels | 400/500/600/700 | 9–18 |
| **Newsreader** | Blog body, prose specs, long-form AI writing | 400/500/600 | 14–22 |
| **Instrument Serif Italic** | Display: hero greetings, verdict lede, curious follow-up Q, blog section heads, transitional reasoning bubble | 400 italic | 17–64 |
| JetBrains Mono | Annotations, code, technical labels | 400 | 10–12 |

Eyebrow label spec: DM Sans 500/600, **10px**, letter-spacing **0.12–0.14em**, uppercase, color depends on context (terra for active section, ink2 for inactive).

### Radius / shadow

```
radius.sm   6
radius.md   10
radius.lg   14
radius.xl   20
radius.pill 999

shadow.card   0 1px 0 rgba(26,24,22,.04), 0 8px 24px -12px rgba(26,24,22,.10)
shadow.sheet  0 -2px 0 rgba(26,24,22,.03), 0 -10px 30px -16px rgba(26,24,22,.12)
```

---

## 3. Logo system (lib/logo.jsx)

### Wordmark anatomy

Three pieces, baseline-aligned, letter-spacing `-0.025em`, sans:

| Piece | Weight | Color |
|---|---|---|
| `Review` | DM Sans **700** | `#B8543A` |
| `Guide` | DM Sans **500** | `#1A1816` |
| `.Ai` | DM Sans **700** | `#B8543A` |

### Two treatments

**A. Discover hero** (`<LogoHero rotate width={300} />`)
- Single occurrence in the entire product
- Speech-bubble outline, 2.5px terracotta stroke, rounded-rect with downward tail at bottom-center
- Inside: wordmark + tagline "Ask Before You [word]"
- Final word rotates every 2.4s: **Buy → Eat → Fly → Stay → Book → Subscribe**
- Crossfade only (no slide / scale); 4px translateY in/out; ease-in-out
- Word slot reserves width of longest word ("Subscribe") so line never reflows
- Respects `prefers-reduced-motion` (falls back to static "Buy")

**B. Static wordmark** (`<WordmarkStatic size={n} showTagline={bool} />`)
- Every other page, top-center of the header band
- No bubble
- Tagline below in 9pt small-caps DM Sans, `letter-spacing: 0.16em`, color `ink3`
- Static text: "Ask before you buy"
- Drops tagline entirely at the smallest size (14px wordmark)

### Header band (HeaderBrand)

Used on Chat, Results, Product detail, Loading, Saved, Compare, About-you:

```
[ back ←  ]   [ wordmark + context line ]   [ right slot ]
   28px            centered                    28px
```

`context` prop accepts a single line ("Wireless headphones · 4 sources"); when omitted, the small-caps tagline shows instead.

---

## 4. Component library (lib/atoms.jsx + lib/logo.jsx)

### AI bubble

```
maxWidth   312
padding    14px 16px
background paperHi
border     1px line
radius     14px 14px 14px 4px   (asymmetric — left-bottom corner squared)
font       DM Sans 15/22
```

### User bubble

```
maxWidth   280
align      right
padding    12px 16px
background ink
color      paper
radius     14px 14px 4px 14px   (asymmetric — right-bottom corner squared)
font       DM Sans 15/22
```

### Suggestion chip (rounded-rect, NOT capsule)

```
padding    10px 14px
radius     12   ← NOT pill
border     1px line2
background paperHi (active: terraSoft + 1px terra border)
font       DM Sans 14/20 weight 500
align      left   ← NOT center
```

Quiz-path variant: 4px terracotta leading dot. Reads as "tap to reply", not "select-one form".

### Loading bubble

```
shape   AI-bubble identical
content [ 8px terracotta dot, breathing 1.6s ease-in-out infinite ]  +
        Instrument Serif Italic 18/24, ink2, rotating copy every ~2s
```

Rotating copy pool: *"Reading the room…"*, *"Cross-checking the specs…"*, *"Hunting for the catch…"*, *"Sorting the contenders…"*, *"Seeing what others are saying…"*, *"Comparing notes…"*

### Curious follow-up Q (§13 #3)

Inside the AI bubble, at the bottom. Structure:
```
[ blog body ]
[ 24px terracotta hairline, opacity 0.55 ]   <- the rg-hairline-short class
[ Instrument Serif Italic 19/26, ink, on its own line ]
```

### Transitional reasoning bubble (NEW — quiz-path)

```
container  No bubble background
border     1px terracotta on left edge only
padding    4px 0 4px 14px
margin     marginLeft: 8 (8px indent from chat gutter)
maxWidth   ~280
font       Instrument Serif Italic 17/24, ink, letter-spacing -0.005em
voice      ONE sentence, compressed-consensus phrasing
animation  fade-in 200ms; next AI question follows 600ms after settle
```

When: between user reply and next AI question, only when the user's answer changed the shortlist meaningfully. Never on routine confirmations.

### Inline product link (§13 #2)

```
color           ink (matches body)
fontWeight      500
text-decoration underline dotted 1px terracotta
underlineOffset 4px
cursor          pointer
```

On tap: smooth-scroll the carousel container into view (anchored above the composer), then snap to the matching card. ~280ms total, single ease.

### Carousel card (§13 #7)

```
width       240
height      ~320
image       top, 75% of width tall, full bleed
roleLabel   DM Sans 10pt 600 small-caps, terra for "Top pick · for you", ink2 otherwise
name        Newsreader 17/22 weight 500
brand+price DM Sans 12 ink3 / 14 ink 500
save        floating 32px terracotta-pill, top-right
peek        ~50px of next card visible at right edge
```

### Save toggle / Bookmark (§13 #9)

Icon: classic bookmark glyph, fill terracotta when saved.

Tap animation: icon scale 0.9 → 1.05 → 1.0 over 200ms; 1px terracotta ring scales 0.6 → 1.6 and fades over 140ms. **No toast** — the icon flip is the confirmation.

### Sticky composer (§8.6)

```
position    fixed/sticky to viewport bottom
padding     14px 18px 22px
mask        linear-gradient(to top, paper 65%, transparent)
inner pill  paperHi, 1px line2, radius 28, shadow.card
send button 36px ink circle, paper arrow
font        DM Sans 15/22, placeholder ink3
```

Placeholder strings: "Reply with anything", "Push back, narrow down, ask follow-up…", "Type anything… or tap above"

### Tab bar (bottom nav)

5 tabs: Discover · Saved · **Ask** (center, primary) · Compare · You. Active = ink + 600; inactive = ink3 + 500. Primary tab = 44px ink pill.

---

## 5. Screens (10)

### 7.1 Discover

```
[ status bar ]
[ centered LogoHero — bubble with rotating word, width 300 ]
What are you researching?            ← Instrument Serif Italic 28/32
[ prompt input — 14px padding, soft border, breathing cursor bar ]
TRENDING RIGHT NOW                   ← eyebrow
[ horizontal scrolling chips with category tag (Audio/Travel/Tech/…) ]
POPULAR THIS WEEK · see all
[ vertical list: 64px thumb + name (Newsreader) + take (DM Sans) + price ]
PICK UP WHERE YOU LEFT OFF
[ recent chat cards: topic, last AI line italic, timestamp ]
[ tab bar ]
```

### 7.2 Chat — empty

```
[ HeaderBrand back ]
What are you trying to figure out?   ← Instrument Serif Italic 30/34
A category, a budget, a vibe — anything works.
A FEW PEOPLE ARE ASKING
[ 4 full-width starter chips ]
[ sticky composer "Type anything… or tap above" ]
```

### 7.3 Chat — fast path (loading)

```
[ HeaderBrand back context="Wireless earbuds" right=overflow-dots ]
[ user bubble ]
[ loading bubble — breathing dot + rotating italic copy ]
[ composer, disabled ]
```

### 7.4 Chat — quiz path

```
[ HeaderBrand back context="A new laptop" ]
[ user bubble: "I need a new laptop." ]
[ AI bubble: clarifying intro ]
[ user bubble: use case ]
[ AI bubble: "Got it. 1 of 3 · what's the rough budget?"
  + 4 vertical chips with leading dot, one accent (selected) ]
[ "or just type if none of these quite fit." — ink3 12pt ]
[ composer ]
```

### 7.5 Results (the densest screen)

Critical ordering — **budget-first, then transitional reasoning, then blog**:

```
[ HeaderBrand back context="Wireless headphones · 4 sources" right=filter ]
[ user bubble: original ask ]
[ AI bubble: "Happy to narrow this. Before I do — what's the rough budget?"
  + 4 chips with leading dot ]
[ user bubble: budget answer ]
[ TransitionalBubble: "$X puts the [tier] on the table — that changes the pick for…" ]
[ Blog card — full-width within the chat gutter, 18px border-radius, paperHi
   THE PICK                                    ← terra eyebrow
   For [situation] — the [product].            ← Instrument Serif Italic 30/36 verdict lede
   ─────────────────────────────────           ← full-width hairline
   [ Newsreader 16/26 body — 1-2 paragraphs ]
   If you want the [other one] instead         ← BlogHead, Newsreader 18 weight 600
   [ Newsreader 16/26 body ]
   The budget pick that's genuinely good       ← BlogHead
   [ Newsreader 16/26 body ]
   ─────────────────────────────────
   [ 24px terra hairline ]
   [ Curious follow-up Q — Instrument Serif Italic 19/26 ]
]
THE SHORTLIST · 4 PICKS
[ horizontal carousel — 4 ProductCards, peek at right edge ]
[ sticky composer "Push back, narrow down, ask follow-up…" ]
```

### 7.6 Product detail

```
[ HeaderBrand back right=saved-toggle ]
[ Hero image — 320h, 18px radius, 4 dots indicator at bottom ]
TOP PICK · BEST ALL-ROUNDER FOR YOUR SITUATION  ← terra eyebrow
Product Name                          ← Newsreader 26/32 weight 600
Brand · Form factor · Wireless        ← ink2 13
[ Price (Newsreader 24 weight 600)  |  Buy at [retailer] (ink pill button) ]
WHY IT'S YOUR PICK
[ Newsreader 16/26 — AI's take, 1 paragraph ]
WHAT MATTERS HERE
[ 5 prose spec rows — 64px label column DM Sans 12 weight 600, value Newsreader 15/22 ]
HONEST NOTES
[ pros (+, terra) and cons (—, ink2) — Newsreader 15/22 ]
```

### 7.7 Loading detail

Standalone screen showing the loading state in context — same as Chat fast-path mid-loading.

### 7.8 Saved

```
[ HeaderBrand context="Things you bookmarked" ]
Saved on this device · 6 items        |  [ Compare · 2 ] pill (terra)
[ 2-column grid of cards:
  - 110h image + 28px circular save badge top-right (filled terra)
  - 22px terra check badge top-left when in compare-selection
  - role label (DM Sans 9pt small-caps)
  - name (Newsreader 15/20)
  - price (DM Sans 12 weight 500)
  - 1px terra border when selected, line border otherwise
]
[ tab bar ]
```

### 7.9 Compare two

```
[ HeaderBrand back context="Comparing two" ]
[ 2-column header cards: image + brand + name + price ]
THE VERDICT FOR YOU                    ← terraInk eyebrow on terraSoft background
[ verdict paragraph, Newsreader 17/24 weight 500 ]
WHAT MATTERS FOR YOU
[ stacked rows — each row: category label (full width, eyebrow), then 2 columns of
  Newsreader 14/20 text with a 4px leading dot in terracotta for the winner side ]
[ Buy [loser] (outline) | Go with the [winner] → (ink pill, 1.6x wider) ]
```

### 7.10 About you (MVP empty state)

```
[ HeaderBrand back=false ]
[ Banner: terraSoft bg, terra dot, "MVP state. Populated personality profile
  deferred post-MVP — route reserved, empty-state only." ]
ABOUT YOU                              ← eyebrow
Still getting to know you.             ← Instrument Serif Italic 38/42
[ paragraph: explanation of what fills in — Newsreader 17/26 ink2 ]
[ Editorial CTA card: 38px ink circle + arrow, "Ask your first thing"
  + "One real question is enough to start." ]
WHAT LIVES HERE, EVENTUALLY            ← eyebrow
[ 3 greyed-out dashed-border placeholders, opacity 0.42 ]
"Filled in by your conversations · never by a form." — ink3 11
[ tab bar ]
```

**About you · populated (POST-MVP reference only, in `ProfileScreenFull`):** keeps the magazine-letter aesthetic; not in v1 build.

---

## 6. Decisions log (the §13 open questions, settled)

| # | Decision |
|---|---|
| 1 | Loading: 1× breathing terracotta dot + rotating italic copy. No tri-dots. |
| 2 | Inline product link: dotted terracotta underline, 4px offset, ink-colored text. |
| 3 | Curious follow-up Q: own line inside AI bubble, 24px terra hairline above, Instrument Serif Italic 19/26. |
| 4 | Suggestion chip: rounded-rect 12px, leading dot at quiz time, left-aligned text. |
| 5 | Typography: Instrument Serif Italic (display) + Newsreader (blog body) + DM Sans (UI). |
| 6 | Discover: editorial vertical rhythm with sections labeled by small-caps eyebrows. |
| 7 | Carousel card: 240×~320, image-top 75%, role small-caps + name (Newsreader 17). |
| 8 | About-you: magazine "letter from the AI" aesthetic, not a settings list. (MVP build: empty state only.) |
| 9 | Save toggle: fill + expanding ring (140ms), no toast. |
| 10 | Color identity: terracotta `#B8543A` on cream `#FAFAF7`, ink `#1A1816`. |

---

## 7. Interaction notes for build

- **Sticky composer**: must always sit at viewport bottom. Cream gradient mask (paper 65% → transparent) covers the buffer below the carousel, never the cards themselves.
- **Carousel peek-of-next + composer collision**: add 96px+ of post-carousel buffer in document flow.
- **Loading → blog transition**: fade out loading bubble (200ms), then render blog top-down with section-staggered opacity (3 × 100ms steps). No height animation.
- **Prior-blog handling on second-turn**: when the user replies after a blog, collapse the prior blog to a 1-line verdict lede with the carousel preserved as a thin scroll-strip; tap to re-expand. Only the live blog is full-size.
- **Tagline rotation**: CSS `@keyframes` (not setInterval) so iOS low-power mode pauses correctly. Single animation, `animation-iteration-count: 1`, advance the word in JS at `animationend`, then restart the animation.

---

## 8. Voice anchors (from tone.md)

Use these phrasings freely in any AI-voice copy. They're the substitute for citations:

- *"The biggest praises are…"*
- *"The most common complaint is…"*
- *"What owners keep mentioning is…"*
- *"What matters after six months is…"*
- *"The tradeoff nobody talks about is…"*
- *"Where people get frustrated is…"*
- *"The thing that surprises most buyers is…"*

Confidence framing: *"This is the easy call."* / *"Two options are very close. Here's the tradeoff."* / *"You're overthinking this one — the gap is smaller than the price difference suggests."*

Rule: **clarification follows the specialist flow — use case first, budget last.** On any
non-trivial purchase the AI asks what a knowledgeable salesperson in that department would
ask, in this order: (1) **use case** translated for the category ("How do you usually
sleep?" for mattresses, "What kind of riding will you do?" for bikes), (2) the category's
most **differentiating feature** (firmness, terrain, performance level — multi-select chips
when several answers can apply, always with a "No strong preference" escape), and
(3) **budget last**, with category-realistic brackets — never generic tiers. Every question
renders tappable chips with a free-text affordance underneath. After results land, a row of
slot-aware refinement chips ("Show cheaper options" / "Only [brand]" / "More premium picks" /
"Different use case") lets the user reshape the shortlist in one tap without being re-asked
anything. (Supersedes the earlier budget-first rule; implemented in PRs #62/#64/#69/#77.)

---

## 9. What's out of scope for MVP

- Auth / sign-in screens
- Notifications, sharing, virality surfaces
- Influencer-facing pages
- SMS / text-notification surfaces
- Populated About-you (deferred post-MVP)

---

## 10. Where to find each thing in the source

| You want… | Read… |
|---|---|
| Color/font tokens | `lib/tokens.js` |
| AI / user bubble | `lib/atoms.jsx` → `AIBubble`, `UserBubble` |
| Loading bubble | `lib/atoms.jsx` → `LoadingBubble` |
| Follow-up Q | `lib/atoms.jsx` → `FollowUpQ` |
| Suggestion chip | `lib/atoms.jsx` → `Chip` |
| Composer | `lib/atoms.jsx` → `Composer` |
| Carousel card | `lib/atoms.jsx` → `ProductCard` |
| Bookmark toggle | `lib/atoms.jsx` → `Bookmark` |
| Wordmark | `lib/logo.jsx` → `Wordmark`, `WordmarkStatic` |
| Discover bubble logo | `lib/logo.jsx` → `LogoHero` |
| Header band | `lib/logo.jsx` → `HeaderBrand` |
| Transitional reasoning bubble | `lib/logo.jsx` → `TransitionalBubble` |
| Discover screen | `lib/screens-flow.jsx` → `DiscoverScreen` |
| Chat screens | `lib/screens-flow.jsx` → `ChatEmptyScreen`, `ChatFastScreen`, `ChatQuizScreen` |
| Results screen (with budget-first + reasoning) | `lib/screens-results.jsx` → `ResultsScreen` |
| Product detail | `lib/screens-results.jsx` → `ProductDetailScreen` |
| Loading screen | `lib/screens-meta.jsx` → `LoadingScreen` |
| Saved | `lib/screens-meta.jsx` → `SavedScreen` |
| Compare | `lib/screens-meta.jsx` → `CompareScreen` |
| About-you MVP empty | `lib/screens-meta.jsx` → `ProfileScreen` |
| About-you populated (post-MVP ref) | `lib/screens-meta.jsx` → `ProfileScreenFull` |
| Logo system card | `lib/v2-delta.jsx` → `LogoSystemCard` |
| Rotation spec card | `lib/v2-delta.jsx` → `RotationSpecCard` |
| Transitional bubble doc card | `lib/v2-delta.jsx` → `TransitionalBubbleCard` |
| Quiz v2 with reasoning bubble | `lib/v2-delta.jsx` → `ChatQuizV2Screen` |
| Color identity card | `lib/foundation.jsx` → `ColorIdentityCard` |
| Type card | `lib/foundation.jsx` → `TypeCard` |
| Decisions log | `lib/foundation.jsx` → `DecisionsCard` |
| Spec feedback | `lib/foundation.jsx` → `SpecFeedbackCard` |

End.
