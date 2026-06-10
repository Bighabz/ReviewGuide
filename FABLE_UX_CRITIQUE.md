# ReviewGuide.ai — UX Critique & Redesign Direction
*Fable 5 · June 2026 · branch `fable/ux-prototype`*

---

## Start here

```bash
git checkout fable/ux-prototype
cd frontend && npm run dev
# open http://localhost:3000/playground
```

**Look at these three things first, in order:**

1. **"The Shortlist" (Section 1 of the playground)** — the current chat product cards rendered from
   fixture data, directly above my proposed replacement rendered from *the same fixture data*. This is
   the core of the redesign: one card system, a real winner treatment, scannable verdicts, and a
   terracotta buy button. Flip the **light/dark toggle** in the sticky toolbar — the current cards
   visibly break in dark mode (white image wells, black badges); the proposed ones don't.
2. **The missing-image card** (product #4 in the proposed shortlist) — the serif monogram tile that
   replaces the dancing-cat emoji placeholder. This is the level of detail the brand needs.
3. **"The Front Page" (Section 2)** — the Discover homepage rebuilt as a magazine front page, with the
   category index *on the homepage* for the first time.

Then resize to 375px and tap around — every CTA in the proposal is a ≥44px target.

---

## TL;DR verdict

Your diagnosis is mostly right but it under-claims the problem. The cards aren't just visually
inconsistent — they're **three different products wearing the same logo**, and one of them is showing
users **fabricated data** (more below). The homepage's problem isn't missing imagery — it's that
**ReviewGuide's homepage doesn't know what ReviewGuide is**. And the browse section isn't just badly
dressed — it's **unreachable**: there is no link to `/browse` anywhere in the primary navigation.

The fix is not a restyle. It's one decision applied everywhere: **ReviewGuide is a magazine that
happens to be conversational, not a chatbot that happens to sell things.** Every surface below follows
from that.

---

## Surface 1 — Chat product cards

### Where you're right (verified in code)

- **Component fragmentation is worse than you think.** It's not six near-duplicates — I count **ten**
  components that render "a product you can buy" (`ProductCards`, `ProductCarousel`, `ProductReview`,
  `ComparisonTable`, `AffiliateLinks`, `InlineProductCard`, `ResultsProductCard`, `CuratedProductCard`,
  `PriceComparison`, `ProductRecommendations`), each with its own product interface, its own image
  fallback strategy, its own rating treatment, and its own CTA language. Concretely:
  - **Five different image-failure behaviors:** emoji `FunPlaceholder` (`ProductCarousel`), a gray
    shopping-cart icon (`InlineProductCard`, `ResultsProductCard`), keyword-matched stock fallbacks
    (`ProductReview.tsx:5-26`), literal "No Image" text (`ComparisonTable.tsx:108`), and
    *hide-the-element-entirely* (`ProductCards.tsx:72`).
  - **Four different rating treatments:** raw string `"4.5/5"` (`ProductReview`), hand-built SVG
    half-stars (`ProductCarousel:30-53`), `fill-yellow-400` lucide stars (`ComparisonTable:52`), and
    none at all (`ProductCards` — the *primary* ranked-list card drops `rating` on the floor even
    though the data contract carries it).
  - **Five CTA dialects:** "Check price →" text link, "View on {merchant} →" text link, "Buy on
    Amazon" 12px text link, "Buy on Amazon" filled blue button, "View Deal" filled blue button.
- **Pros/cons as prose** — verified at `ProductCards.tsx:117-133`: pros are `join('. ')`-ed into a
  paragraph. Ironically `ProductReview` already does it right with scannable check/cross lists. That's
  drift, not design.
- **Weak CTAs** — verified. The flagship ranked-list card's only action is a 14px text link
  (`ProductCards.tsx:136-145`). On a site whose *entire revenue model* is that click, the buy action is
  the quietest element on the card.
- **Dark-mode breakage** — verified: `bg-white` image wells (`ProductReview.tsx:91`,
  `ComparisonTable.tsx:99`), `bg-black` rank badge (`ResultsProductCard.tsx:81`), hardcoded
  `text-green-600`/`text-red-500` pros/cons, fixed `#E5A100`/`#D6D3CD` star hexes.
- **`FunPlaceholder` is off-brand** — verified ("Finding purrfect products… 🐱"). Charming in a
  consumer chat toy; wrong for a publication asking to be trusted with a $400 decision.

### Where you're wrong, or I'd push back

1. **"No tier/winner differentiation" is not quite true — the truth is worse.** There are *three
   competing* winner systems: `InlineProductCard` awards 🏆 Top Pick / ⚡ Best Value / ✨ Premium **by
   array position**; `ResultsProductCard` does the same with off-palette goldenrod/violet pills
   (`#B8860B`, `#7C3AED` — violet isn't in your system at all); and `ProductCards` renders
   backend-provided `badges[]` as small italic text. So the winner treatment exists — it's just
   incoherent, position-faked, and invisible where it matters.
2. **`ResultsProductCard` shows users invented numbers.** `POSITION_SCORES = [95, 88, 82, 76, 70]`
   (`ResultsProductCard.tsx:13`) renders a "Score: 95" progress bar that is a function of *list
   position*, not evidence. For a product whose one differentiator is "evidence-based recommendations,"
   a fabricated score is a brand integrity bug, not a styling bug. **Kill it.** Show real `rating` ×
   `review_count`, or show nothing.
3. **Your image-size numbers are off, but the complaint stands.** The wells are 64–96px
   (`w-16`/`w-20`/`w-24`), not 20–24px. Still too small: at 64px a headphone and a blender are the same
   gray smudge. The deeper issue is *composition* — image pinned left as an afterthought thumbnail,
   rather than the image being part of the editorial layout.
4. **A bug you didn't list: dark-mode `dark:` variants are dead code.** Several cards use Tailwind
   `dark:` classes (`ProductCarousel.tsx:183`, `ComparisonTable.tsx:140`), but `tailwind.config.ts` has
   **no `darkMode` setting**, so those variants compile to the `prefers-color-scheme` media query —
   they respond to the *OS* setting, not your `[data-theme]` toggle. Users with OS-dark + app-light (or
   vice versa) get mixed palettes. Either set `darkMode: ['class', '[data-theme="dark"]']` in the
   config or ban `dark:` in components (the codebase convention is CSS vars; I'd ban it).
5. **`ProductCarousel` violates the Rules of Hooks** — `if (!items || items.length === 0) return null`
   *before* `useEffect` (`ProductCarousel.tsx:90-92`). Works by luck until the day items arrive
   streaming-empty-then-full.
6. **A carousel is the wrong container for a ranked recommendation.** Wirecutter does not hide picks
   #2–4 behind a chevron. A vertical ranked list inside the prose *is* the blog format the product
   claims to be. I keep a horizontal rail only as a `rail` variant for "more like this" overflow — never
   for the answer itself.

### My direction: one card system — "The Verdict Card"

One base component, four variants, one product normalizer. (Prototype: `frontend/components/_playground/proposed/VerdictCard.tsx`.)

| Variant | Replaces | Use |
|---|---|---|
| `feature` | nothing (new) | Rank #1 / "Top Pick" — earns a magazine spread |
| `standard` | `ProductCards` rows | Ranks 2–N in the shortlist |
| `compact` | `InlineProductCard` | Ledger rows in flowing prose |
| `rail` | `ProductCarousel` | Horizontal overflow ("also considered") |

Design decisions, stated as decisions:

- **Terracotta = money. Blue = navigation.** The single highest-leverage change. Every buy action is a
  filled `--accent` button ("See price at Amazon ↗", ≥44px tall, full-width on mobile); blue is demoted
  to links and metadata. The founder's favorite color stops being a garnish and becomes the *signature
  interaction* — and revenue clicks become the loudest element on every card. This also gives the
  terracotta a *job*, which is what "use it with more intent" actually means.
- **The rank is typography, not a badge.** A large Instrument Serif numeral (terracotta for #1, ink for
  the rest) set beside the title — the visual language of a magazine ranked list, costs zero chrome.
  Black circle badges deleted.
- **Winner treatment = restraint with one loud moment.** The `feature` card gets: a terracotta top
  rule, an uppercase letterspaced kicker ("TOP PICK — BEST FOR MOST PEOPLE", driven by real `badges[]`
  data, never by array index), a 4:3 image at meaningful size, and an italic serif **verdict line** —
  one sentence, the editor's call. Everything else stays quiet so this reads as *the* pick.
- **Pros/cons become "FOR / AGAINST" ledgers.** Two columns on ≥sm, `+`/`–` typographic glyphs in
  `--success`/`--error`, text in neutral ink, max three each. Scannable in under two seconds.
- **One `Rating` component everywhere.** Stars in `--warning` via tokens, serif numeral, muted count.
  Used identically in every variant; the current four dialects die.
- **The missing-image case is designed, not apologized for.** A serif italic monogram (first letter of
  the product) on `--accent-light` with a hairline ring — looks like a deliberate editorial drop cap,
  works in both themes, replaces both the emoji cat and the shopping-cart icon.
- **The list gets a masthead.** The shortlist opens with a small-caps kicker ("THE SHORTLIST · 5
  CONTENDERS"), a serif title, and an editorial rule; the affiliate disclosure moves into a set-small
  colophon line at the foot. The container itself communicates "curated," before a single card is read.

### Touchstones

1. **Wirecutter's "Our pick" callout** — the structural model for the `feature` variant: boxed,
   labeled, one clear photo, "why it wins" up top, the buy button unmissable. It's the proof that
   editorial authority and conversion CTAs can coexist.
2. **Monocle's retail/ranked spreads** — the typographic model: serif numerals as rank, hairline rules,
   small-caps kickers, generous but disciplined whitespace, product photos in calm neutral wells. This
   is where "editorial luxury" stops being a vibe and becomes a spec.
3. **Financial Times / FT Globetrotter** — the proof that *warm paper + ink + one warm accent* can be a
   complete identity system. FT's pink is to FT what terracotta should be to ReviewGuide: not a color
   in the palette, but the *first thing you recognize*.

---

## Surface 2 — Discover homepage

### Where you're right

- **The structural diagnosis is the correct one** and it's the most important sentence in your brief:
  categories don't exist on the homepage. I'll extend it: **they don't exist in the topbar either.**
  `UnifiedTopbar` links to `/`, `/saved`, `/chat`, `/compare` — never `/browse`. The chip row's "Tech"
  chip doesn't even go to `/browse/electronics`; it fires a canned chat query. The entire browse
  section — ten category pages, ten commissioned hero images — is **orphaned architecture** reachable
  only by URL. This is an IA bug masquerading as a design preference.
- Zero imagery, templated 72px trending rows, personality-free chips, cramped `mt-8` rhythm — all
  verified. Also worth flagging: the discover components are written in **inline `style` objects**
  rather than Tailwind (`TrendingCards.tsx:48-58`), so they're cut off from the token utilities and the
  hover system everything else uses.

### What I'd add

The headline "What are you researching today?" with subline "Expert reviews, real data, zero fluff" is
*chatbot* framing — it asks the user to do work before showing any evidence the product has taste. A
magazine front page asserts an identity first ("Ask before you buy."), then offers the index. Trust is
built by *showing curation*, not by an empty text box.

### My direction: "The Front Page"

(Prototype: Section 2 of `/playground`.)

- **Masthead hero** — small-caps kicker ("INDEPENDENT BUYING ADVICE · RESEARCHED LIVE"), an Instrument
  Serif display headline ("Ask before you buy*, italic terracotta on the load-bearing word*"), the
  search bar promoted to a real input with a terracotta submit button, and three starter-query links
  set as editorial citations underneath. Generous `py` — the hero is allowed to breathe.
- **"The Index"** — the structural fix. All ten categories on the homepage as a numbered
  two-column table of contents: serif numeral, category name, tagline, thumbnail from the *existing*
  `/images/browse/*.jpg` heroes. Routes to `/browse/[slug]`. (Production note: `/browse` also belongs
  in `UnifiedTopbar` — one-line change.)
- **"Today's Briefing"** — trending rebuilt with editorial hierarchy: the lead story as a large image
  card (kicker, serif headline, dek), remaining topics as a numbered dateline list with hairline rules.
  Six identical pill-rows become one front page. Uses the existing `mosaic-*.webp` assets.
- **The chips die.** A horizontal scroll of personality-free pills that secretly fire chat queries is
  three patterns doing one job badly; The Index does that job honestly.

---

## Surface 3 — Category browse pages

### Where you're right

- Hero = `<img>` + black gradient + white text is the most generic move in web design; verified, along
  with the silent-fail fallback (`page.tsx:42-51`) that leaves a ghost gradient and no headline image.
- Popular Questions as a flat 2×2 of identical buttons, verified — no lead question, no hierarchy.
- "Explore Other Categories" as 200px micro-cards, verified — it's a footnote pretending to be a section.

### Corrections

- **The off-palette promo gradient is in `CategoryNav.tsx:55-59`, not `CategorySidebar`** — including
  the undefined `--secondary` var (resolves to *transparent/invalid*, so the gradient renders from
  nothing into `blue-900`). `CategorySidebar` itself is on-palette; its actual problem is that it's a
  12px-type utility list trying to do a magazine's job, and (per Surface 2) almost nobody can reach it.
- The hero overlay also ignores the warm palette — pure `black/70` over the photo, cold and
  off-brand in both themes.

### My direction: "The Section Opener"

(Prototype: Section 3 of `/playground`.)

- **Split hero, not overlay hero.** Left: an ivory panel with the issue-style kicker ("THE GUIDE ·
  Nº 02"), serif display headline, tagline, and the search input. Right: the photo in a frame with a
  terracotta offset rule. The text never sits *on* the photo, so a failed image degrades to a clean
  editorial layout instead of a ghost gradient — and dark mode needs no overlay hacks.
- **"Start here" + the question index.** The first curated query becomes a featured serif
  question-as-pull-quote card with a terracotta rule and an explicit "Ask this →" action; the rest
  become a numbered index list. One door, clearly marked, then the catalog.
- **Other categories as a colophon strip** — slim numbered text links with thumbnails, full-bleed rule
  above, honest about being a footer rather than cosplaying as content cards.

---

## Production integration path (when a direction wins)

The prototype was built to make this cheap:

1. **`VerdictCard` + `normalizeProduct()`** (both in `_playground/proposed/`) are written against the
   exact `ProductCard` contract from `ProductCards.tsx`, including legacy/MCP field merging. Integration
   is a `BlockRegistry.tsx` change only: point `product_cards` at `<VerdictList>`, `inline_product_card`
   at `<VerdictCard variant="compact">`, `carousel`/`products` at `<VerdictCard variant="rail">` — the
   streaming layer (`ChatContainer`, `Message.tsx`) is untouched, exactly as constrained.
2. **Retire by redirect, don't rewrite:** `ProductCards`, `InlineProductCard`, `ResultsProductCard`,
   `ProductCarousel`, and `FunPlaceholder` become thin wrappers (or direct registry swaps) over
   `VerdictCard`; delete after a bake period. `ProductReview` (the citation-rich dossier) keeps its
   structure but adopts the system's `Rating`, image well, and CTA primitives.
3. **Homepage:** `app/page.tsx` swaps to the Front Page sections (`MastheadHero`, `CategoryIndex`,
   `TodaysBriefing` — all in the prototype). Add `/browse` to `UnifiedTopbar`. Zero backend work; all
   data already lives in `categoryConfig.ts` / `trendingTopics.ts`.
4. **Category pages:** replace hero + questions sections in `app/browse/[category]/page.tsx` with
   `SectionOpener` + `QuestionIndex`. Delete `CategoryNav`'s promo card (and the phantom `--secondary`).
5. **Two config fixes regardless of design outcome:** add `darkMode: ['class', '[data-theme="dark"]']`
   to `tailwind.config.ts` (or lint-ban `dark:`), and delete `POSITION_SCORES`.
6. **Token additions (no palette changes):** the prototype adds only utility-level CSS (kicker
   letter-spacing, monogram tile, terracotta rules) in its own scoped file — portable into
   `globals.css` as ~30 lines.

Estimated production effort after sign-off: **2–3 days** for cards (registry swap + bake), **1–2 days**
for homepage + category pages, plus a QA pass on real streamed data.

---

*Things in the prototype the brief didn't ask for, flagged as my own ideas: the terracotta-=-money CTA
rule; killing the fabricated score bar; the verdict line on feature cards; deleting the homepage chip
row; the topbar `/browse` link. I believe in all five, the first two most.*
