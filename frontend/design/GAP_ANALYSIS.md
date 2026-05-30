# ReviewGuide.ai — Design Blueprint Gap Analysis

**Date:** 2026-05-29  
**Blueprint:** `frontend/design/` (DESIGN.md + `lib/*.jsx`, the 390px design canvas)  
**Compared against:** current Next.js 14 / Tailwind frontend (`frontend/app`, `frontend/components`)  
**Method:** spec→implementation comparison. The blueprint is a self-contained inline-styled canvas (reads `window.RG`), not portable React — so this grades *contracts* (tokens, component shapes, screen structure, motion) against how the live frontend renders. Strict / pixel-exact grading: every measurable deviation is reported.  
**Legend:** ✅ matches spec · ⚠️ PARTIAL (present but off-spec) · ❌ MISSING or WRONG-SHAPE

---

## Executive summary

The frontend does **not** read from the blueprint's token system at all — it has its own parallel palette, and that palette is the *pre-blueprint* identity the design explicitly replaced. This is the root of "it doesn't look anything like the blueprint i gave you":

1. **Wrong primary color, app-wide.** `globals.css` still defines `--primary: #1B4DFF` — the AI-blue DESIGN.md §11.6 says it *replaced* with terracotta. The accent is `#E85D3A`, not the blueprint terra `#B8543A`. User chat bubbles render in **blue** (`Message.tsx:153`), not ink.
2. **Missing editorial typeface.** Newsreader (the entire blog-body face) is never loaded. `layout.tsx` wires only DM Sans + Instrument Serif.
3. **No design tokens in Tailwind.** No `paper`/`ink`/`terra` colors, no `6/10/14/20/999` radius scale. Components hand-roll `rounded-[20px]` etc.
4. **The defining screen is the wrong shape.** Results is a static extraction summary (header + product grid + sources), not the conversational budget-first → TransitionalBubble → editorial blog → carousel flow that is the blueprint's centerpiece.
5. **Four screens are unbuilt.** Saved, Compare, Product Detail, About-You are placeholders or missing routes.
6. **The hero is missing.** The LogoHero rotating-word speech bubble (the single signature moment) does not exist; the wordmark is a raster PNG, not the 3-piece terra/ink anatomy.

Net: the engineering is competent, but it diverged from the blueprint at the identity layer (color + type + tokens) and at the structural layer (Results flow + secondary screens). The fixes are tractable; this report is the punch list, ordered by severity.

---

## 1. Tokens (visual identity) — the root cause

### Color
- [❌] `frontend/app/globals.css:12` — `--primary: #1B4DFF` (indigo-blue). Blueprint replaced this; there is no blue in the design. **WRONG.**
- [❌] `frontend/app/globals.css:18` — `--accent: #E85D3A`. Blueprint accent is terra `#B8543A` (more muted, WCAG-tuned). Wrong hue/value. **WRONG.**
- [⚠️] `frontend/app/globals.css:37` — `--text: #1C1917`. Blueprint ink is `#1A1816`. Close but not exact. **PARTIAL.**
- [⚠️] `frontend/app/globals.css:29-42` — surfaces/borders (`--background #FAFAF7` ✅, `--surface #F5F4F0` ✅, `--border #E7E5E0` vs spec line `#E8E6E1`). Paper tier is right; ink/line tiers drift. **PARTIAL.**
- [❌] `frontend/tailwind.config.ts:16-39` — no `paper`/`paperHi`/`paperAlt`, `ink`/`ink2`/`ink3` (only `ink`→`--text`), `terra`/`terraSoft`/`terraInk` named colors. Blueprint palette is not expressible in Tailwind classes. **MISSING.**
- [❌] No `terraSoft #F4E2D7` / `terraInk #7A3624` anywhere in the live CSS — used by the spec for save fills, verdict cards, hover/pressed. **MISSING.**

### Type
- [✅] `frontend/app/layout.tsx:6` — DM Sans loaded via `next/font` (400/500/600/700). Matches.
- [✅] `frontend/app/layout.tsx:7` — Instrument Serif loaded (normal + italic). Matches.
- [❌] `frontend/app/layout.tsx:3-7` — **Newsreader is NOT loaded.** The blueprint's blog-body / prose-spec face (14–22, weights 400/500/600) is absent. `tailwind.config.ts:14` maps `font-serif` to Instrument, not Newsreader. **MISSING.**
- [❌] `frontend/tailwind.config.ts:11-15` — no `font-display`/Newsreader family token; the three-face system (DM Sans UI / Newsreader body / Instrument display) collapses to two. **MISSING.**
- [⚠️] Eyebrow label spec (DM Sans 500/600, 10px, letter-spacing 0.12–0.14em, uppercase) — no shared utility; `globals.css` lacks an `.rg-eyebrow` equivalent. Eyebrows are ad-hoc per component. **PARTIAL.**

### Radius / shadow
- [❌] `frontend/tailwind.config.ts:47-49` — only `borderRadius.editorial (0.625rem)`. No `sm 6 / md 10 / lg 14 / xl 20 / pill 999` scale. Components use arbitrary `rounded-[20px]`/`rounded-2xl`. **MISSING.**
- [⚠️] `frontend/tailwind.config.ts:43` — `shadow.card` is `0 1px 3px… , 0 6px 16px…`; blueprint `shadow.card` is `0 1px 0 rgba(26,24,22,.04), 0 8px 24px -12px rgba(26,24,22,.10)`. Different. **PARTIAL.**
- [❌] No `shadow.sheet` equivalent for bottom sheets/composer. **MISSING.**

---

## 2. Atoms (component shapes)

### Chat bubbles
- [❌] `frontend/components/Message.tsx:176` — **AI bubble** `rounded-tl-[4px] tr-[20px] br-[20px] bl-[20px]` squares the **top-left** corner at 20px radius. Spec is `14/14/14/4` → squares the **bottom-left** at 14px. Wrong corner + wrong radius. Border ✅ (`1px var(--border)`), bg should be paperHi. **WRONG-SHAPE.**
- [⚠️] `frontend/components/Message.tsx:153` — **User bubble** `rounded-tl-[20px] tr-[20px] br-[4px] bl-[20px]`, bg `var(--primary)` (= blue), `text-white`. Correct squared corner (bottom-right) but radius 20 vs 14, and bg is **blue not ink `#1A1816`**. **WRONG (color) + PARTIAL (radius).**
- [⚠️] Both bubbles use `max-w-[80%]`/`85%` rather than the spec's fixed 312/280 — acceptable for responsive web, noted for fidelity. **PARTIAL.**

### Suggestion chip
- [❌] `frontend/components/Message.tsx:299` — chip `rounded-[20px]` (pill). Spec is radius **12, rounded-rect NOT pill**, left-aligned, 1px line2 border, paperHi bg (active terraSoft + terra border). No active/accent state. Quiz-path **4px terracotta leading dot** absent. **WRONG-SHAPE.**

### Loading bubble
- [⚠️] `frontend/components/Message.tsx:190-198` — exists (rotating copy from the tone pool ✅), but the dot is `w-1.5 h-1.5` (6px) `bg-[var(--primary)]` (blue) `animate-pulse`. Spec: **8px terracotta dot, breathing 1.6s** (scale 1→1.35, `rg-breath`), rotating copy in **Instrument Serif Italic 18/24 ink2** (currently DM Sans). Right idea, wrong dot size/color/animation and wrong copy font. **PARTIAL.**

### Curious follow-up Q
- [⚠️] `frontend/components/Message.tsx:224-228` — divider is a generic `border-t border-[var(--border)]/60` full-width; spec wants a **24px terra hairline at 0.55 opacity** (`rg-hairline-short`). Follow-up text is DM Sans 15/medium; spec is **Instrument Serif Italic 19/26 ink** on its own line. **PARTIAL (wrong hairline + wrong font).**

### Inline product link
- [❌] No dedicated atom. Prose links use solid hover underline (`Message.tsx` prose styles). Spec: ink-colored text, weight 500, **dotted 1px terracotta underline, 4px offset**, tap scrolls carousel into view. **MISSING.**

### Product card (carousel)
- [⚠️] `frontend/components/ProductCarousel.tsx` / `ResultsProductCard.tsx` — responsive flex/grid card, image `aspect-square` (100%), name in serif (Instrument, not Newsreader 17/22). Spec: fixed **240×~320, image top 75%**, role label DM Sans 10pt 600 small-caps (terra for top pick), **floating 32px terra save pill top-right**, **~50px peek** of next card. Save pill + peek + fixed dims absent. **WRONG-SHAPE.**

### Sticky composer
- [⚠️] `frontend/components/ChatInput.tsx` — inner control `rounded-2xl` (16px), `shadow-sm`. Spec: **radius 28 pill**, 1px line2, **shadow.card**, padding 14/18/22, **cream gradient mask** (`linear-gradient(to top, paper 65%, transparent)`), **36px ink send circle** with paper arrow (current send is `w-9 h-9 rounded-xl` ArrowUp). Mask absent. **PARTIAL.** (Positioning covered in §5.)

### Bookmark / save toggle
- [❌] No bookmark atom on product cards. Spec: classic bookmark glyph, terra fill when saved, tap animation icon **scale 0.9→1.05→1.0 (200ms)** + **1px terra ring scale 0.6→1.6 fade (140ms, `rg-ring`)**, no toast. Neither glyph nor animation present. **MISSING.**

---

## 3. Logo system

- [❌] `frontend/app/page.tsx` (Discover hero) — **LogoHero is missing.** Discover renders a plain serif headline, not the speech-bubble (2.5px terra stroke + downward tail) with rotating word **Buy→Eat→Fly→Stay→Book→Subscribe** every 2.4s. This is the single signature moment of the product. **MISSING.**
- [❌] `frontend/components/UnifiedTopbar.tsx:129-136` / `MobileHeader.tsx:91-99` — **Wordmark is a raster PNG**, not the 3-piece DM Sans anatomy `Review`(700, terra) + `Guide`(500, ink) + `.Ai`(700, terra), -0.025em. Brand text exists only in `alt`. Can't support context lines or sizing. **WRONG-SHAPE.**
- [❌] `frontend/components/UnifiedTopbar.tsx` — **HeaderBrand band missing.** Spec wants `[28px back] [centered wordmark + context] [28px right]` on Chat/Results/Product/Loading/Saved/Compare/About-you. Current uses a generic topbar (search, nav, avatar). No per-screen context line ("Wireless headphones · 4 sources"). **MISSING.**
- [❌] `frontend/components/MobileHeader.tsx` — no WordmarkStatic + 9pt small-caps tagline ("Ask before you buy", 0.16em, ink3). **MISSING.**
- [❌] `frontend/components/AnimatedLogo.tsx` — TransitionalBubble (quiz-path reasoning) not implemented anywhere; word rotation that does exist uses `setInterval` not CSS `@keyframes`. **MISSING / WRONG-SHAPE.**

---

## 4. Screens

### 1. Discover — ⚠️ PARTIAL
- [❌] `frontend/app/page.tsx` — LogoHero rotating bubble missing (see §3). **MISSING.**
- [⚠️] `frontend/components/discover/*` — TRENDING/POPULAR sections exist but eyebrow labels aren't at spec typography (10px DM Sans 0.14em uppercase); POPULAR uses icon-grid cards, not the 64px thumb + Newsreader name + take + price list. **PARTIAL.**
- [❌] "PICK UP WHERE YOU LEFT OFF" recent-chats section not rendered. **MISSING.**

### 2. Chat — empty — ⚠️ PARTIAL
- [⚠️] `frontend/components/ChatContainer.tsx:68-145` — empty state uses a cycling-verb animation instead of the static **"What are you trying to figure out?" Instrument Serif Italic 30/34**. **PARTIAL.**
- [❌] "A FEW PEOPLE ARE ASKING" + 4 pre-rendered full-width starter chips absent on load. **MISSING.**
- [❌] HeaderBrand absent (generic topbar). **MISSING.**

### 3. Chat — fast / loading — ⚠️ PARTIAL
- [⚠️] Loading bubble renders (see §2) but dot/copy off-spec. **PARTIAL.**
- [❌] HeaderBrand + `context="Wireless earbuds"` absent. **MISSING.**

### 4. Chat — quiz — ⚠️ PARTIAL
- [⚠️] `frontend/components/Message.tsx:238-270` — clarifier chips render but lack the 4px terra leading dot and selected/accent state. **PARTIAL.**
- [❌] HeaderBrand absent. **MISSING.**

### 5. Results — ❌ WRONG-SHAPE (the defining screen)
- [❌] `frontend/app/results/[id]/page.tsx` — renders **ResultsHeader + ResultsQuickActions (Share/Save/Refresh) + product grid + Sources list**. This is a static extraction summary, **not** the conversational thread. **WRONG-SHAPE.**
- [❌] Flow ordering verdict: the blueprint's centerpiece — user ask → AI budget question + chips → user budget answer → **TransitionalBubble** → **editorial Blog card** (THE PICK eyebrow → verdict lede Instrument Serif Italic 30/36 → hairline → Newsreader 16/26 body → BlogHeads → follow-up Q) → **THE SHORTLIST carousel** — is **entirely absent**. **MISSING.**
- [❌] No TransitionalBubble; no blog/editorial markup; products are a 3-col grid (`page.tsx:93-104`), not a peek-next carousel. **MISSING / WRONG-SHAPE.**
- [⚠️] A Sources section is present that the spec's Results screen does not have (it folds sourcing into AI voice). **PARTIAL (extra).**
- [❌] HeaderBrand `context="Wireless headphones · 4 sources" right=filter` absent (plain back link). **MISSING.**

### 6. Product detail — ❌ MISSING
- [❌] No `/product[s]/[id]` route exists; ProductDetailScreen lives only in the design canvas. Entire screen (hero 320h + 4 dots, eyebrow, Newsreader name, price + Buy pill, WHY/WHAT MATTERS/HONEST NOTES) absent. **MISSING.**

### 7. Loading detail — ⚠️ PARTIAL
- [⚠️] Exists only as an in-message transient state, not the standalone framed screen; HeaderBrand absent. **PARTIAL.**

### 8. Saved — ❌ MISSING
- [❌] `frontend/app/saved/page.tsx:23` — "This feature is coming soon" placeholder (36 lines). None of the 2-col grid / terra save badge / compare-select system. **MISSING.**

### 9. Compare — ❌ MISSING
- [❌] `frontend/app/compare/page.tsx:23` — "coming soon" placeholder (36 lines). `ComparisonTable.tsx` exists but is never imported here. No THE VERDICT FOR YOU / WHAT MATTERS FOR YOU / winner-dot / dual CTA. **MISSING.**

### 10. About-you (MVP empty) — ❌ MISSING
- [❌] No `/profile` or `/about-you` route. `MobileTabBar` "You/Profile" tab routes to `null`. ProfileScreen lives only in the canvas. MVP banner, "Still getting to know you." hero, editorial CTA, 3 dashed placeholders — all absent. **MISSING.**

---

## 5. Interaction / motion polish

- [❌] `frontend/components/ChatContainer.tsx:870` — composer is `className="sticky bottom-0"` (sticky within scroll container), spec requires **true viewport-fixed**. **WRONG-SHAPE.**
- [❌] Composer **cream gradient mask** (`linear-gradient(to top, paper 65% → transparent)`) not implemented. **MISSING.**
- [❌] `frontend/components/ProductCarousel.tsx` — post-carousel buffer ~24px (`mb-6`); spec requires **96px+** so the fixed composer never collides with cards/peek. **MISSING.**
- [❌] **Loading→blog transition** (200ms fade-out, then blog top-down with 3×100ms staggered opacity) — content renders instantly. **MISSING.**
- [❌] **Prior-blog collapse** on second-turn reply (1-line verdict lede + thin carousel scroll-strip, tap to re-expand) — not implemented. **MISSING.**
- [❌] `frontend/components/ChatContainer.tsx:109` — word rotation uses **`setInterval`**; spec mandates CSS `@keyframes` + `animationend` (iOS low-power pauses correctly). **WRONG-SHAPE.**
- [⚠️] `frontend/components/Message.tsx:192` — loading uses `animate-pulse` (opacity, 2s); spec `rg-breath` (scale 1→1.35, 1.6s) defined in `tokens.js:84-88` but not wired into the live build. **PARTIAL.**
- [❌] Bookmark `rg-ring` animation (`tokens.js:91-94`) not used; no save animation in the frontend. **MISSING.**
- [⚠️] `frontend/app/globals.css:430-437` — `prefers-reduced-motion` covers `animate-pulse`/card-enter but the LogoHero reduced-motion fallback (static "Buy") is moot since LogoHero doesn't exist. **PARTIAL.**

---

## Severity-ordered punch list (the fix order, for a later session)

1. **Identity tokens** — repoint `--primary`/`--accent` to terra `#B8543A`, correct ink/line tiers, add `paper/ink/terra` + radius scale to Tailwind, **load Newsreader**. Fixes the app-wide "wrong color, wrong type" complaint at the source. (§1)
2. **Bubbles & loading atom** — ink user bubble (not blue), correct asymmetric corners at radius 14, terra breathing loading dot + Instrument Serif copy. (§2)
3. **Logo system** — build Wordmark (3-piece), HeaderBrand band, and the Discover LogoHero rotating bubble. (§3)
4. **Results flow** — rebuild as the conversational budget-first → TransitionalBubble → editorial blog → carousel sequence (the centerpiece). (§4.5)
5. **Carousel, composer, chips** — fixed-dim cards + save pill + peek; fixed composer + gradient mask + 96px buffer; rounded-rect left-aligned chips with leading dot. (§2, §5)
6. **Secondary screens** — Saved, Compare, Product Detail, About-You from placeholder/missing to spec. (§4.6, 4.8–4.10)
7. **Motion polish** — loading→blog stagger, prior-blog collapse, `@keyframes` rotation, bookmark ring. (§5)

*No code was changed in producing this report.*
