# Frontend Visual Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Elevate ReviewGuide.ai from "functional beta" to polished editorial product — refining design tokens, surfaces, spacing, typography hierarchy, component density, dark mode, micro-interactions, AND generating real product imagery via nano-banana MCP to replace placeholder icons.

**Architecture:** Token-first approach (globals.css + tailwind.config.ts), then image generation (nano-banana MCP → save to public/images/products/), then shell polish, page layouts, component upgrades with real images, and finally Chrome MCP visual QA. Each task ends with lint + test verification.

**Tech Stack:** Next.js 14, Tailwind CSS 3, CSS custom properties, DM Sans + Instrument Serif (Google Fonts), Vitest, nano-banana MCP (Gemini image generation), Chrome MCP (visual QA)

**Protected test contracts** (`frontend/tests/designTokens.test.ts`):
- Must preserve: `--stream-status-size`, `--stream-status-color`, `--stream-content-color`, `--citation-color`
- Must preserve: `.stream-status-text`, `.stream-content-text`, `.citation-text` utility classes
- Must preserve: `.animate-card-enter`, `.animate-pulse`, `.stream-status-text` in `prefers-reduced-motion` block
- Must preserve: `card-enter` animation, `stream`/`stream-out`/`stream-inout` in tailwind.config
- Must preserve: `--gpt-accent`, `--gpt-text`, `--gpt-background` legacy mappings

---

## Affiliate & Product Data Architecture

Understanding how product links and data flow is critical for carousel CTAs, product cards, and results panel.

### Provider Status

| Provider | Status | Tag/Code | Notes |
|----------|--------|----------|-------|
| **Curated Amazon** | LIVE | `revguide-20` | 120+ hardcoded amzn.to links in `curated_amazon_links.py`. `USE_CURATED_LINKS=true` on Railway. **Primary source — always works.** |
| **eBay** | Likely working | — | Needs verification with test call |
| **CJ (Commission Junction)** | Code ready | `cj_provider.py` | Active — products appear when CJ has matches |
| **Impact.com** | Code ready | `impact_provider.py` | Needs credentials/application |
| **Amazon PA-API** | Not approved | — | Application pending |
| **Walmart** | Not applied | Via Impact Radius | Pending application |
| **Best Buy** | Not applied | Via Impact Radius or CJ | If applied through CJ, auto-appears with zero code change |
| **Home Depot** | Not applied | Via Impact Radius | Pending application |
| **Serper Shopping** | Env set | `ENABLE_SERPAPI=true` | On Railway but may not be wired into main search flow |

### Frontend Implications

- **Carousel "Check Price" / "Research" links:** Currently navigate to `/chat?q=<query>&new=1` (research flow, not direct affiliate). This is correct — the carousel drives research, not direct purchases.
- **ResultsProductCard "Check Price" button:** Links to `product.url` (affiliate link from backend) or falls back to Amazon search with `tag=revguide-20`. This fallback is the curated Amazon link system.
- **InlineProductCard / ProductCards:** Same pattern — affiliate URLs from backend response, Amazon tag fallback.
- **Key rule:** All product links MUST include the `revguide-20` Amazon tag when pointing to Amazon. This is already handled in `ResultsProductCard.tsx` line ~37.

### Backend Files (DO NOT MODIFY — reference only)

| File | Purpose |
|------|---------|
| `backend/app/services/affiliate/curated_amazon_links.py` | 120+ hardcoded product → amzn.to link mappings |
| `backend/app/services/affiliate/providers/cj_provider.py` | CJ affiliate link resolution |
| `backend/app/services/affiliate/providers/impact_provider.py` | Impact.com affiliate integration |
| `backend/app/services/affiliate/loader.py` | Loads and chains affiliate providers |
| `backend/app/core/config.py` | Feature flags (USE_CURATED_LINKS, ENABLE_SERPAPI, etc.) |

---

## File Map

### Modified files:
| File | Responsibility |
|------|---------------|
| `frontend/app/globals.css` | Design tokens (colors, shadows, borders, typography tokens) |
| `frontend/tailwind.config.ts` | Tailwind theme extensions mapping to CSS vars |
| `frontend/components/UnifiedTopbar.tsx` | Desktop header/navigation |
| `frontend/components/MobileHeader.tsx` | Mobile header |
| `frontend/components/MobileTabBar.tsx` | Mobile bottom tab bar |
| `frontend/components/Footer.tsx` | Desktop footer |
| `frontend/app/page.tsx` | Homepage layout |
| `frontend/components/discover/ProductCarousel.tsx` | Carousel cards — **upgraded with real product images** |
| `frontend/components/discover/DiscoverSearchBar.tsx` | Search input styling |
| `frontend/components/discover/CategoryChipRow.tsx` | Category chip styling |
| `frontend/components/CategorySidebar.tsx` | Desktop sidebar |
| `frontend/components/ResultsMainPanel.tsx` | Desktop results panel |
| `frontend/components/ResultsProductCard.tsx` | Product card — **fallback images from generated set** |
| `frontend/components/ChatContainer.tsx` | Chat UI (className only) |
| `frontend/components/ChatInput.tsx` | Chat input bar (className only) |
| `frontend/components/Message.tsx` | Message bubble styling (className only) |

### New files:
| File | Responsibility |
|------|---------------|
| `frontend/public/images/products/headphones.png` | Generated: Sony WH-1000XM6 product shot |
| `frontend/public/images/products/tokyo.png` | Generated: Tokyo cityscape travel hero |
| `frontend/public/images/products/laptop.png` | Generated: MacBook Air M4 product shot |
| `frontend/public/images/products/vacuum.png` | Generated: Robot vacuum product shot |
| `frontend/public/images/products/shoes.png` | Generated: Running shoes product shot |

---

## Task 1: Refine Design Tokens (globals.css)

**Files:**
- Modify: `frontend/app/globals.css`

**Design rationale:** Sonnet 4.6 identified washed-out surfaces and low contrast. The fix is better surface elevation scale, richer shadows, and a warm neutral scale that isn't sterile.

- [ ] **Step 1: Update light mode `:root` surface tokens**

In `frontend/app/globals.css`, update these values in `:root` (keep all variable NAMES identical):

```css
:root {
  /* Backgrounds: Clearer elevation steps */
  --background: #FAFAF7;       /* was #F7F5F0 — slightly lighter base */
  --surface: #FFFFFF;           /* was #F5F4F0 — true white for cards */
  --surface-hover: #F5F4F0;    /* was #EDECE7 — previous surface becomes hover */
  --surface-elevated: #FFFFFF;  /* keep white */
  --surface-float: rgba(255, 255, 255, 0.95);

  /* Shadows: More perceptible, dual-layer */
  --shadow-sm: 0 1px 3px rgba(28, 25, 23, 0.05), 0 1px 2px rgba(28, 25, 23, 0.03);
  --shadow-md: 0 4px 12px rgba(28, 25, 23, 0.07), 0 2px 4px rgba(28, 25, 23, 0.04);
  --shadow-lg: 0 8px 24px rgba(28, 25, 23, 0.09), 0 4px 8px rgba(28, 25, 23, 0.04);
  --shadow-xl: 0 20px 48px rgba(28, 25, 23, 0.12), 0 8px 16px rgba(28, 25, 23, 0.06);
  --shadow-float: 0 12px 36px rgba(27, 77, 255, 0.10), 0 4px 12px rgba(28, 25, 23, 0.06);

  /* Border: Slightly stronger */
  --border-strong: #D1CEC8;    /* was #D6D3CD */
}
```

All other `:root` values (--primary, --accent, --text, --stream-*, --citation-*, --gpt-*, --card-accent-*) remain UNCHANGED.

- [ ] **Step 2: Update dark mode tokens**

In `[data-theme="dark"]`:

```css
[data-theme="dark"] {
  --background: #0A0C12;
  --surface: #12151E;
  --surface-hover: #1A1E2A;
  --surface-elevated: #1E2232;
  --surface-float: rgba(10, 12, 18, 0.96);

  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.4);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.5), 0 2px 4px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 8px 28px rgba(0, 0, 0, 0.6), 0 4px 8px rgba(0, 0, 0, 0.3);
  --shadow-float: 0 12px 36px rgba(59, 130, 246, 0.15), 0 4px 12px rgba(0, 0, 0, 0.4);

  --border: #1E2538;
  --border-strong: #2D3650;
}
```

- [ ] **Step 3: Improve glass utility and add focus-ring**

Update `.glass`:
```css
.glass {
  backdrop-filter: blur(20px) saturate(1.1);
  -webkit-backdrop-filter: blur(20px) saturate(1.1);
}
```

Add after `.glass`:
```css
.focus-ring {
  outline: none;
}
.focus-ring:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
  border-radius: inherit;
}
```

- [ ] **Step 4: Verify prefers-reduced-motion block is intact**

Confirm `.animate-card-enter`, `.animate-pulse`, `.stream-status-text` are still in the `@media (prefers-reduced-motion: reduce)` block.

- [ ] **Step 5: Run tests**

```bash
cd frontend && npm run lint && npm run test:run
```

Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/globals.css
git commit -m "refine: design tokens — clearer surface elevation, richer shadows, focus-ring utility"
```

---

## Task 2: Update Tailwind Theme Extensions

**Files:**
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Update boxShadow to use token vars**

```typescript
boxShadow: {
  'float': 'var(--shadow-float)',
  'premium': 'var(--gpt-shadow-premium)',
  'card': 'var(--shadow-sm)',
  'card-hover': 'var(--shadow-md)',
  'editorial': 'var(--shadow-md)',
  'elevated': 'var(--shadow-lg)',
},
```

- [ ] **Step 2: Run tests**

```bash
cd frontend && npm run lint && npm run test:run
```

- [ ] **Step 3: Commit**

```bash
git add frontend/tailwind.config.ts
git commit -m "refine: tailwind — token-driven shadows"
```

---

## Task 3: Generate All Site Images (nano-banana MCP)

**Prerequisite:** nano-banana MCP server must be connected (`claude mcp add nanobanana -- npx -y @ycse/nanobanana-mcp` with `GEMINI_API_KEY`). If not available, restart Claude Code first.

**Style guide:** All images use consistent editorial photography style — warm lighting, clean compositions, soft gradient backgrounds that match the site's color tokens. Product shots float with subtle shadows. Travel shots use cinematic golden-hour grading. 16:9 aspect ratio for hero/carousel images, 1:1 square for thumbnails/placeholders.

### Group A: Carousel & Trending Hero Images (5)

Shared between ProductCarousel.tsx and TrendingCards.tsx — same categories, same images.

**Files:**
- Create: `frontend/public/images/products/headphones.png`
- Create: `frontend/public/images/products/tokyo.png`
- Create: `frontend/public/images/products/laptop.png`
- Create: `frontend/public/images/products/vacuum.png`
- Create: `frontend/public/images/products/shoes.png`

- [ ] **Step 1: Create output directories**

```bash
mkdir -p frontend/public/images/products
mkdir -p frontend/public/images/trending
mkdir -p frontend/public/images/categories
mkdir -p frontend/public/images/placeholders
```

- [ ] **Step 2: Generate headphones hero**
- **Prompt:** "Professional product photography of premium over-ear noise-cancelling headphones, Sony WH-1000XM6 style, matte black finish, floating on a soft blue gradient background, studio lighting, clean minimal composition, 16:9 aspect ratio, high-end product catalog style"
- **Output:** `frontend/public/images/products/headphones.png`

- [ ] **Step 3: Generate Tokyo travel hero**
- **Prompt:** "Stunning aerial view of Tokyo skyline at golden hour, Shibuya crossing visible, cherry blossoms in foreground, warm cinematic color grading, travel magazine cover style, 16:9 aspect ratio, editorial photography"
- **Output:** `frontend/public/images/products/tokyo.png`

- [ ] **Step 4: Generate laptop hero**
- **Prompt:** "Professional product photography of a thin silver laptop, MacBook Air M4 style, open at 45 degrees, on a clean mint green gradient background, studio lighting, floating with subtle shadow, product catalog style, 16:9 aspect ratio"
- **Output:** `frontend/public/images/products/laptop.png`

- [ ] **Step 5: Generate robot vacuum hero**
- **Prompt:** "Professional product photography of a modern white robot vacuum cleaner with lidar sensor tower, on a soft purple gradient background, clean studio lighting, floating product shot, 16:9 aspect ratio, high-end catalog style"
- **Output:** `frontend/public/images/products/vacuum.png`

- [ ] **Step 6: Generate running shoes hero**
- **Prompt:** "Professional product photography of modern running shoes, Nike Vaporfly style, neon pink and white colorway, dynamic floating angle, on a warm coral gradient background, studio lighting, 16:9 aspect ratio, athletic catalog style"
- **Output:** `frontend/public/images/products/shoes.png`

### Group B: Trending Card Thumbnail (1 extra)

TrendingCards has 6 topics but carousel only has 5. The 6th ("Smart Home Starter Kit") needs its own image.

- [ ] **Step 7: Generate smart home hero**
- **Prompt:** "Professional product photography of a smart home starter kit — smart speaker, smart bulb, smart plug, and motion sensor — artfully arranged on a soft teal gradient background, studio lighting, floating product composition, 16:9 aspect ratio, editorial catalog style"
- **Output:** `frontend/public/images/products/smart-home.png`

### Group C: Category Placeholder SVGs → Real Images (8)

Referenced by `ImageWithFallback.tsx` as `/placeholders/*.svg` — files currently DON'T EXIST. Replace with real PNG images for a polished look.

- [ ] **Step 8: Generate electronics placeholder**
- **Prompt:** "Minimal flat-lay of consumer electronics — wireless earbuds, smartwatch, tablet, charging cable — arranged on a cool gray gradient, soft studio lighting, 1:1 square, clean editorial style"
- **Output:** `frontend/public/placeholders/electronics.png`

- [ ] **Step 9: Generate travel placeholder**
- **Prompt:** "Minimal flat-lay of travel essentials — passport, sunglasses, boarding pass, camera — arranged on a warm sandy gradient, soft studio lighting, 1:1 square, editorial travel magazine style"
- **Output:** `frontend/public/placeholders/travel.png`

- [ ] **Step 10: Generate gaming placeholder**
- **Prompt:** "Minimal flat-lay of gaming gear — wireless controller, gaming headset, mechanical keyboard — arranged on a dark purple gradient with subtle RGB glow, 1:1 square, editorial style"
- **Output:** `frontend/public/placeholders/gaming.png`

- [ ] **Step 11: Generate home placeholder**
- **Prompt:** "Minimal flat-lay of home essentials — scented candle, linen towel, ceramic mug, plant cutting — arranged on a warm beige gradient, soft natural lighting, 1:1 square, lifestyle editorial style"
- **Output:** `frontend/public/placeholders/home.png`

- [ ] **Step 12: Generate fashion placeholder**
- **Prompt:** "Minimal flat-lay of fashion accessories — leather watch, sunglasses, wallet, sneaker — arranged on a blush pink gradient, soft studio lighting, 1:1 square, fashion editorial style"
- **Output:** `frontend/public/placeholders/fashion.png`

- [ ] **Step 13: Generate beauty placeholder**
- **Prompt:** "Minimal flat-lay of beauty products — serum bottle, moisturizer jar, jade roller, makeup brush — arranged on a soft rose gold gradient, soft studio lighting, 1:1 square, beauty editorial style"
- **Output:** `frontend/public/placeholders/beauty.png`

- [ ] **Step 14: Generate sports placeholder**
- **Prompt:** "Minimal flat-lay of sports gear — running shoe, water bottle, fitness tracker, resistance band — arranged on an energetic coral gradient, soft studio lighting, 1:1 square, athletic editorial style"
- **Output:** `frontend/public/placeholders/sports.png`

- [ ] **Step 15: Generate default placeholder**
- **Prompt:** "Minimal flat-lay of a gift box with ribbon, shopping bag, and product package — arranged on a neutral warm ivory gradient, soft studio lighting, 1:1 square, clean editorial style"
- **Output:** `frontend/public/placeholders/default.png`

### Group D: Product Category Fallback Images (5)

Better fallbacks for `productImages.ts` — replace crude inline SVGs with real product category images used when API returns no image.

- [ ] **Step 16: Generate headphones fallback (square)**
- **Prompt:** "Single pair of premium over-ear headphones on a clean white background, centered, minimal shadow, 1:1 square, product catalog thumbnail style"
- **Output:** `frontend/public/images/products/fallback-headphones.png`

- [ ] **Step 17: Generate laptop fallback (square)**
- **Prompt:** "Single thin silver laptop on a clean white background, centered, lid open, minimal shadow, 1:1 square, product catalog thumbnail style"
- **Output:** `frontend/public/images/products/fallback-laptop.png`

- [ ] **Step 18: Generate kitchen fallback (square)**
- **Prompt:** "Single premium kitchen appliance (stand mixer) on a clean white background, centered, minimal shadow, 1:1 square, product catalog thumbnail style"
- **Output:** `frontend/public/images/products/fallback-kitchen.png`

- [ ] **Step 19: Generate fitness fallback (square)**
- **Prompt:** "Single pair of running shoes on a clean white background, centered, minimal shadow, 1:1 square, product catalog thumbnail style"
- **Output:** `frontend/public/images/products/fallback-fitness.png`

- [ ] **Step 20: Generate default product fallback (square)**
- **Prompt:** "Clean product box package on a white background, centered, minimal shadow, generic retail product, 1:1 square, catalog thumbnail style"
- **Output:** `frontend/public/images/products/fallback-default.png`

### Group E: Travel Card Fallback Images (3)

Replace Lucide icon placeholders in hotel/car/flight cards when API returns no image.

- [ ] **Step 21: Generate hotel fallback**
- **Prompt:** "Modern luxury hotel lobby interior, warm lighting, marble floor, elegant furniture, welcoming atmosphere, 16:9 aspect ratio, travel magazine editorial style"
- **Output:** `frontend/public/images/products/fallback-hotel.png`

- [ ] **Step 22: Generate car rental fallback**
- **Prompt:** "Clean modern rental car (white SUV) parked at a scenic overlook, blue sky, soft lighting, 16:9 aspect ratio, automotive editorial style"
- **Output:** `frontend/public/images/products/fallback-car.png`

- [ ] **Step 23: Generate flight fallback**
- **Prompt:** "Aerial view through airplane window of clouds at sunrise, warm golden light, wing visible, 16:9 aspect ratio, travel editorial photography style"
- **Output:** `frontend/public/images/products/fallback-flight.png`

### Verification & Commit

- [ ] **Step 24: Verify all images exist and check sizes**

```bash
echo "=== Product/Carousel images ==="
ls -la frontend/public/images/products/
echo ""
echo "=== Category placeholders ==="
ls -la frontend/public/placeholders/
echo ""
echo "=== Trending ==="
ls -la frontend/public/images/trending/ 2>/dev/null || echo "(shared with products)"
```

Each image should be under 500KB. Optimize if needed:
```bash
npx sharp-cli -i frontend/public/images/products/*.png -o frontend/public/images/products/ --quality 80
npx sharp-cli -i frontend/public/placeholders/*.png -o frontend/public/placeholders/ --quality 80
```

- [ ] **Step 25: Commit all generated images**

```bash
git add frontend/public/images/ frontend/public/placeholders/
git commit -m "feat: generate 23 editorial images via nano-banana — carousel, trending, placeholders, fallbacks"
```

---

## Task 4: Upgrade ProductCarousel with Real Images

**Files:**
- Modify: `frontend/components/discover/ProductCarousel.tsx`

- [ ] **Step 1: Read current ProductCarousel.tsx**

- [ ] **Step 2: Add image paths to SLIDES data**

Update each slide in the `SLIDES` array to include an `image` field:

```typescript
const SLIDES: ProductSlide[] = [
  {
    id: 'headphones',
    tag: 'TOP PICK',
    tagColor: '#92400E',
    title: 'Best Headphones 2026',
    subtitle: 'Sony WH-1000XM6 leads for noise cancellation',
    score: '9.4',
    scoreLabel: 'Expert Score',
    price: '$348',
    query: 'Best noise-cancelling headphones 2026',
    icon: 'Headphones',
    gradient: 'linear-gradient(135deg, #DBEAFE 0%, #93C5FD 50%, #60A5FA 100%)',
    iconColor: '#2563EB',
    image: '/images/products/headphones.png',
  },
  {
    id: 'tokyo',
    // ... existing fields ...
    image: '/images/products/tokyo.png',
  },
  {
    id: 'laptops',
    // ... existing fields ...
    image: '/images/products/laptop.png',
  },
  {
    id: 'vacuums',
    // ... existing fields ...
    image: '/images/products/vacuum.png',
  },
  {
    id: 'running',
    // ... existing fields ...
    image: '/images/products/shoes.png',
  },
]
```

Add `image: string` to the `ProductSlide` interface.

- [ ] **Step 3: Replace icon hero area with product image**

Find the gradient hero `<div>` (the one with `height: '120px'`). Replace its content:

**Before:** Lucide icon in a glass card
**After:** Product image with gradient overlay

```tsx
{/* Gradient hero area with product image */}
<div
  className="relative flex items-center justify-center overflow-hidden transition-all duration-700"
  style={{ background: slide.gradient, height: '160px' }}
>
  {/* Product image */}
  <img
    src={slide.image}
    alt={slide.title}
    className="absolute inset-0 w-full h-full object-cover opacity-90 transition-transform duration-500 group-hover:scale-105"
    loading="lazy"
  />
  {/* Gradient overlay for text readability */}
  <div
    className="absolute inset-0"
    style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.3) 0%, transparent 60%)' }}
  />

  {/* Tag badge */}
  <div className="absolute top-3 left-3 z-10">
    <span className="px-2 py-0.5 rounded-md text-[9px] font-bold tracking-wider text-white"
      style={{ background: slide.tagColor }}>
      {slide.tag}
    </span>
  </div>

  {/* Score badge */}
  <div className="absolute top-3 right-3 z-10 flex items-center gap-1 px-2 py-1 rounded-lg backdrop-blur-sm"
    style={{ background: 'rgba(255,255,255,0.85)' }}>
    <Star size={10} fill={slide.iconColor} color={slide.iconColor} />
    <span className="text-xs font-bold" style={{ color: slide.iconColor }}>{slide.score}</span>
  </div>
</div>
```

Note: increase height from `120px` to `160px` for better image display.

- [ ] **Step 4: Adjust info area for tighter mobile fit**

The card now has a taller hero (160px). To keep single-screen fit on mobile, tighten the info area padding:

```tsx
<div className="px-4 py-2.5">
```

(was `py-3`)

- [ ] **Step 5: Remove Lucide icon imports no longer needed**

Remove unused icon imports from the component if the icon-in-glass-card rendering code is fully replaced. Keep `ChevronLeft`, `ChevronRight`, `Star`, `ArrowRight`. Remove individual product icons (`Headphones`, `Plane`, etc.) and the `iconMap` if no longer used.

- [ ] **Step 6: Run tests and commit carousel**

```bash
cd frontend && npm run lint && npm run test:run
git add frontend/components/discover/ProductCarousel.tsx
git commit -m "feat: carousel with real product images — replaces icon placeholders"
```

---

## Task 4b: Wire Up Trending Cards with Real Images

**Files:**
- Modify: `frontend/lib/trendingTopics.ts`
- Modify: `frontend/components/discover/TrendingCards.tsx`

- [ ] **Step 1: Add image field to TrendingTopic interface**

In `frontend/lib/trendingTopics.ts`, add `image: string` to the interface and add image paths to each topic:

```typescript
export interface TrendingTopic {
  id: string
  title: string
  subtitle: string
  query: string
  icon: string
  iconBg: string
  iconColor: string
  image: string  // NEW — path to generated image
}
```

Map each topic to its generated image:
- `headphones-2026` → `/images/products/headphones.png`
- `tokyo-travel` → `/images/products/tokyo.png`
- `laptops-students` → `/images/products/laptop.png`
- `robot-vacuums` → `/images/products/vacuum.png`
- `running-shoes` → `/images/products/shoes.png`
- `smart-home-starter` → `/images/products/smart-home.png`

- [ ] **Step 2: Replace icon square with image thumbnail in TrendingCards.tsx**

Replace the 48x48 icon square `<div>` with an image thumbnail:

```tsx
{/* Image thumbnail — 48x48, rounded 12px */}
<div
  aria-hidden="true"
  className="overflow-hidden"
  style={{
    width: '48px',
    height: '48px',
    borderRadius: '12px',
    flexShrink: 0,
  }}
>
  <img
    src={topic.image}
    alt=""
    className="w-full h-full object-cover"
    loading="lazy"
  />
</div>
```

Keep the icon imports as fallback — if image fails to load, show icon. Or remove icon imports entirely if images are committed to the repo (they're static assets, not API-dependent).

- [ ] **Step 3: Run tests and commit**

```bash
cd frontend && npm run lint && npm run test:run
git add frontend/lib/trendingTopics.ts frontend/components/discover/TrendingCards.tsx
git commit -m "feat: trending cards with real images — replaces Lucide icon squares"
```

---

## Task 4c: Wire Up Category Placeholders & Product Fallbacks

**Files:**
- Modify: `frontend/components/ui/ImageWithFallback.tsx`
- Modify: `frontend/lib/productImages.ts`
- Modify: `frontend/components/HotelCards.tsx`
- Modify: `frontend/components/FlightCards.tsx`
- Modify: `frontend/components/CarRentalCard.tsx`

- [ ] **Step 1: Update ImageWithFallback.tsx placeholder paths**

Change `.svg` extensions to `.png` in the CATEGORY_PLACEHOLDERS map:

```typescript
const CATEGORY_PLACEHOLDERS: Record<string, string> = {
  electronics: '/placeholders/electronics.png',
  travel: '/placeholders/travel.png',
  gaming: '/placeholders/gaming.png',
  home: '/placeholders/home.png',
  fashion: '/placeholders/fashion.png',
  beauty: '/placeholders/beauty.png',
  sports: '/placeholders/sports.png',
  default: '/placeholders/default.png',
}
```

- [ ] **Step 2: Update productImages.ts with real fallback images**

Replace inline SVG data URIs with real image paths and expand the category detection:

```typescript
const CATEGORY_PLACEHOLDERS: Record<string, string> = {
  headphones: '/images/products/fallback-headphones.png',
  laptop: '/images/products/fallback-laptop.png',
  kitchen: '/images/products/fallback-kitchen.png',
  fitness: '/images/products/fallback-fitness.png',
  default: '/images/products/fallback-default.png',
}

function detectCategory(name: string): string {
  const lower = name.toLowerCase()
  if (lower.match(/headphone|earbud|speaker|audio|airpod|bose|sony wh|jabra/)) return 'headphones'
  if (lower.match(/laptop|macbook|chromebook|notebook|computer/)) return 'laptop'
  if (lower.match(/blender|mixer|air fryer|coffee|toaster|oven|cookware|kitchen/)) return 'kitchen'
  if (lower.match(/shoe|sneaker|running|treadmill|yoga|fitness|gym|weight/)) return 'fitness'
  return 'default'
}
```

Update `isPlaceholderImage()` to detect both old SVG and new PNG fallbacks:
```typescript
export function isPlaceholderImage(url: string): boolean {
  return url.startsWith('data:image/svg+xml') || url.startsWith('/images/products/fallback-')
}
```

- [ ] **Step 3: Add fallback images to HotelCards.tsx**

Replace the HotelIcon fallback with the generated hotel image:
```tsx
// When no thumbnail_url:
<img src="/images/products/fallback-hotel.png" alt="Hotel" className="w-full h-full object-cover" />
```

- [ ] **Step 4: Add fallback images to FlightCards.tsx and CarRentalCard.tsx**

For flight PLPLink cards, add a small flight image:
```tsx
<img src="/images/products/fallback-flight.png" alt="" className="w-12 h-12 rounded object-cover" />
```

For car rental cards:
```tsx
<img src="/images/products/fallback-car.png" alt="" className="w-12 h-12 rounded object-cover" />
```

- [ ] **Step 5: Run tests and commit**

```bash
cd frontend && npm run lint && npm run test:run
git add frontend/components/ui/ImageWithFallback.tsx frontend/lib/productImages.ts \
  frontend/components/HotelCards.tsx frontend/components/FlightCards.tsx \
  frontend/components/CarRentalCard.tsx
git commit -m "feat: wire up generated fallback images — replaces all SVG/icon placeholders"
```

---

## Task 5: Polish Desktop Shell (UnifiedTopbar)

**Files:**
- Modify: `frontend/components/UnifiedTopbar.tsx`

- [ ] **Step 1: Read current file**

- [ ] **Step 2: Improve scroll blur transition**

Change header transition from `transition-all` to `transition-[box-shadow,background-color]` for performance. Set scrolled opacity to `bg-[var(--background)]/90`.

- [ ] **Step 3: Add focus-ring to all interactive elements**

Add `focus-ring` class to: logo Link, each nav Link, all icon buttons (history, new chat, theme toggle, palette, avatar).

- [ ] **Step 4: Add shadow to active nav tab**

Change active nav state from `'text-[var(--text)] bg-[var(--surface)]'` to `'text-[var(--text)] bg-[var(--surface)] shadow-card'`.

- [ ] **Step 5: Run tests and commit**

```bash
cd frontend && npm run lint && npm run test:run
git add frontend/components/UnifiedTopbar.tsx
git commit -m "polish: desktop topbar — glass blur, focus rings, active tab shadow"
```

---

## Task 6: Polish Mobile Shell (MobileHeader + MobileTabBar)

**Files:**
- Modify: `frontend/components/MobileHeader.tsx`
- Modify: `frontend/components/MobileTabBar.tsx`

- [ ] **Step 1: Read both files**

- [ ] **Step 2: MobileHeader — add glass blur on discover routes**

Add `backdropFilter` and `WebkitBackdropFilter` to the header style: `'blur(20px) saturate(1.1)'`.

- [ ] **Step 3: MobileHeader — add focus-ring to all buttons**

Add `focus-ring` class to back button, share button, logo link, avatar button.

- [ ] **Step 4: MobileTabBar — replace hardcoded #9B9B9B**

Change inactive tab color from `'#9B9B9B'` to `'var(--text-muted)'`. Remove fallback hex from active: `'var(--primary)'`.

- [ ] **Step 5: MobileTabBar — add top shadow**

Add `boxShadow: '0 -4px 16px rgba(0,0,0,0.04)'` to the nav style.

- [ ] **Step 6: Add focus-ring to all tab links and settings button**

- [ ] **Step 7: Run tests and commit**

```bash
cd frontend && npm run lint && npm run test:run
git add frontend/components/MobileHeader.tsx frontend/components/MobileTabBar.tsx
git commit -m "polish: mobile shell — glass blur, token colors, tab shadow, focus rings"
```

---

## Task 7: Polish Homepage Layout

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Add fade-up animation to hero heading**

Add `animate-fade-up` class to the `<h1>`.

- [ ] **Step 2: Improve subtitle**

Change from `className="text-sm text-center mt-2 max-w-md"` to `className="text-sm sm:text-[15px] text-center mt-3 max-w-md leading-relaxed"`.

- [ ] **Step 3: Run tests and commit**

```bash
cd frontend && npm run lint && npm run test:run
git add frontend/app/page.tsx
git commit -m "polish: homepage — fade-up hero, refined subtitle"
```

---

## Task 8: Polish Discover Components (Search, Chips)

**Files:**
- Modify: `frontend/components/discover/DiscoverSearchBar.tsx`
- Modify: `frontend/components/discover/CategoryChipRow.tsx`

- [ ] **Step 1: DiscoverSearchBar — token shadows + focus-within glow**

Replace inline `boxShadow` with `var(--shadow-sm)`. Add `focus-within:shadow-float focus-within:border-[var(--primary)] transition-all` to the form className.

- [ ] **Step 2: CategoryChipRow — add focus-ring to chips**

Add `focus-ring` class to each chip `<button>`.

- [ ] **Step 3: Run tests and commit**

```bash
cd frontend && npm run lint && npm run test:run
git add frontend/components/discover/DiscoverSearchBar.tsx frontend/components/discover/CategoryChipRow.tsx
git commit -m "polish: search bar focus glow, chip focus rings"
```

---

## Task 9: Polish Results & Chat Components

**Files:**
- Modify: `frontend/components/ResultsMainPanel.tsx`
- Modify: `frontend/components/ResultsProductCard.tsx`
- Modify: `frontend/components/ChatInput.tsx`

- [ ] **Step 1: ResultsMainPanel — source link hover**

Add `transition-colors hover:text-[var(--primary)]` to source links.

- [ ] **Step 2: ResultsProductCard — hover lift + fallback image**

Add `transition-all duration-200 hover:shadow-card-hover hover:-translate-y-0.5` to the card container.

Update the placeholder/fallback image logic: when no product image is available, the card already falls back to a generic icon. This is acceptable — the nano-banana generated images are for the carousel, not dynamic API results.

- [ ] **Step 3: ChatInput — focus glow + send button feedback**

Add `focus:ring-2 focus:ring-[var(--primary)]/20 focus:border-[var(--primary)]/40 transition-all` to the text input.

Add `active:scale-95 transition-transform` to the send button.

- [ ] **Step 4: Run tests and commit**

```bash
cd frontend && npm run lint && npm run test:run
git add frontend/components/ResultsMainPanel.tsx frontend/components/ResultsProductCard.tsx frontend/components/ChatInput.tsx
git commit -m "polish: results hover effects, chat input focus glow, send button feedback"
```

---

## Task 10: Consistency Sweep

**Files:**
- Various (grep-driven)

- [ ] **Step 1: Grep for hardcoded colors**

```bash
cd frontend && grep -rn '#[0-9A-Fa-f]\{6\}' components/ --include='*.tsx' | grep -v node_modules | grep -v .test. | head -40
```

Replace hardcoded grays/blues/whites with `var(--*)` tokens. Skip intentional brand colors (carousel gradients, source dots).

- [ ] **Step 2: Grep for inline rgba shadows**

```bash
grep -rn 'rgba(' components/ --include='*.tsx' | grep -v node_modules | grep -v .test. | head -20
```

Replace inline shadow rgba with `var(--shadow-*)` where applicable.

- [ ] **Step 3: Run final tests**

```bash
cd frontend && npm run lint && npm run test:run
```

- [ ] **Step 4: Commit**

```bash
git add -A frontend/components/
git commit -m "sweep: replace hardcoded colors and shadows with tokens"
```

---

## Task 11: Visual QA via Chrome MCP

**Files:** None (read-only verification)

- [ ] **Step 1: Mobile homepage (390x844)**

Navigate to `https://www.reviewguide.ai`, resize to 390x844, screenshot. Verify:
- Header with glass blur
- Hero fade-up animation played
- Carousel shows **real product image** (not icon placeholder)
- Search bar has visible border and focus-within glow works
- Tab bar has top shadow, uses token colors

- [ ] **Step 2: Desktop homepage (1280x800)**

Resize to 1280x800, screenshot. Verify:
- Topbar blur-on-scroll, active tab shadow
- Carousel card shows full product image with gradient overlay
- Prev/next arrows visible
- Sidebar renders

- [ ] **Step 3: Mobile chat (/chat at 390x844)**

Navigate to `/chat`, screenshot. Verify:
- Chat input visible above tab bar
- Input focus glow works (click input, screenshot)
- Send button has press feedback
- Header bg is white

- [ ] **Step 4: Desktop chat (/chat at 1280x800)**

Screenshot. Verify:
- Split-pane renders
- Results panel sources have hover effect
- Product cards (if present) have hover lift

- [ ] **Step 5: Dark mode check**

Toggle dark mode. Screenshot mobile + desktop homepage. Verify:
- Deep navy backgrounds (#0A0C12)
- Text contrast meets AA
- Carousel images still look good on dark bg
- No white flashes or broken surfaces

- [ ] **Step 6: Compile results and commit**

```bash
git commit --allow-empty -m "qa: visual verification complete — all surfaces, real images, dark mode checked"
```

---

## Summary

| Task | Category | Key Change | Status |
|------|----------|-----------|--------|
| 1 | Tokens | Surface elevation, shadows, borders, focus-ring utility | DONE |
| 2 | Tailwind | Token-driven shadow mappings | DONE |
| 3 | **Images** | **Generate 23 images via nano-banana MCP — carousel, trending, placeholders, fallbacks** | TODO |
| 4 | **Carousel** | **Replace icon placeholders with real product photos** | TODO |
| 4b | **Trending** | **Replace Lucide icon squares with real image thumbnails** | TODO |
| 4c | **Fallbacks** | **Wire up category placeholders, product/hotel/flight/car fallbacks** | TODO |
| 5 | Shell | Desktop topbar — glass blur, focus rings, active shadow | DONE |
| 6 | Shell | Mobile header/tabbar — blur, token colors, shadow | DONE |
| 7 | Homepage | Hero animation, subtitle refinement | DONE |
| 8 | Discover | Search focus glow, chip focus rings | DONE |
| 9 | Components | Results hover, chat input glow, send feedback | DONE |
| 10 | Sweep | Replace hardcoded colors with tokens | DONE |
| 11 | **Visual QA** | **Chrome MCP screenshots — verify everything including images** | TODO |

### What stays unchanged
- DM Sans + Instrument Serif fonts
- All navigation routes and behavior
- data-theme / data-accent system
- All streaming, chat, and API behavior
- All test contracts (stream/citation tokens, legacy --gpt-* vars)
- Message.tsx render functions and ui_blocks logic
