# Next Session Plan — Mobile QA + Fixes + v4.0

## Step 1: Set Up Mobile Testing (FIRST THING)

Before touching any code:

1. Open `https://www.reviewguide.ai/` in Chrome MCP tab
2. Press F12 to open DevTools
3. Press Ctrl+Shift+M to toggle device toolbar
4. Select **iPhone 14 Pro** from device dropdown
5. Screenshot — this is the real mobile viewport

Do the same for `/chat` page.

## Step 2: Mobile QA Pass (Discover Page)

With DevTools device emulation active on `/`:
- [ ] Mosaic hero: only 4 center tiles visible?
- [ ] Headline readable?
- [ ] Search bar visible WITHOUT scrolling?
- [ ] Category chips: horizontally scrollable?
- [ ] Carousel: images load, swipeable?
- [ ] No horizontal scrollbar?
- [ ] Bottom tab bar visible?

Fix anything broken before moving on.

## Step 3: Mobile QA Pass (Chat Page)

Navigate to `/chat` in device emulation. Send a test query like "best headphones":
- [ ] Sent message visible after sending (not scrolled off screen)?
- [ ] Loading dots appear?
- [ ] Blog text streams in?
- [ ] TopPickBlock: image ABOVE text (stacked, not side-by-side)?
- [ ] TopPickBlock: CTA button not cut off?
- [ ] ProductReview cards: 64px images, tighter padding?
- [ ] "Where to Buy" links: single column (not 3-col)?
- [ ] Prices readable, not truncated?
- [ ] No horizontal overflow?
- [ ] Chat input always visible at bottom?

Fix anything broken before moving on.

## Step 4: Every Mentioned Product Gets a Card

**Backend change in `product_compose.py`:**

After the blog article is generated, extract product names from the blog text. For each product mentioned that doesn't already have a `product_review` UI block, create a card with:
- Product name from the blog text
- Amazon search URL as affiliate link (`amazon.com/s?k={name}&tag=revguide-20`)
- No image (or placeholder)
- No price ("Check price →")

This ensures every product the LLM mentions is clickable and monetized.

**Files to modify:**
- `backend/mcp_server/tools/product_compose.py` — after blog article, extract names, generate fallback cards

## Step 5: v4.0 Affiliate Overhaul (if time permits)

### 5a. eBay Campaign ID
- Get real campaign ID from Mike
- Update on Railway: `EBAY_CAMPAIGN_ID=<real_id>`
- Test an eBay link and verify tracking params

### 5b. Activate CJ on Railway
- Set `CJ_API_ENABLED=true`, `CJ_API_KEY`, `CJ_WEBSITE_ID` on Railway
- Verify CJ results appear in product searches

### 5c. Expedia Integration
- Get Expedia affiliate credentials
- Configure in Railway env vars
- Test travel query returns Expedia links

## Step 6: Final QA

Run through `docs/superpowers/plans/2026-04-01-full-ui-qa.md` checklist on:
- [ ] Desktop (1440px)
- [ ] Mobile via DevTools device emulation (iPhone 14 Pro)
- [ ] Sign off both columns
