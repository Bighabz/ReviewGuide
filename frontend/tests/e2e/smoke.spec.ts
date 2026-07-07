/**
 * End-to-end smoke tests.
 *
 * Run against a deployed preview or local stack:
 *   BASE_URL=https://www.reviewguide.ai npx playwright test tests/e2e/smoke.spec.ts
 *
 * These are blocking post-deploy checks — they should cover the user journeys
 * whose regressions would lose revenue. Keep the set small and fast; deeper
 * UX tests belong in unit/integration suites.
 *
 * Added 2026-04-21 as part of the stabilization sprint. Requires:
 *   npm i -D @playwright/test
 *   npx playwright install chromium
 */

import { test, expect } from '@playwright/test'

const BASE_URL = process.env.BASE_URL || 'https://www.reviewguide.ai'

test.describe('smoke', () => {
  test.beforeEach(async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
  })

  test('homepage renders hero + trending cards visible above footer at 1440x900', async ({ page }) => {
    await page.goto(BASE_URL)
    await expect(page.locator('h1')).toContainText(/researching/i)

    // Hero search input should be in view.
    const heroInput = page.getByPlaceholder(/Ask anything/i).first()
    await expect(heroInput).toBeVisible()
    const box = await heroInput.boundingBox()
    expect(box).not.toBeNull()
    if (box) expect(box.bottom).toBeLessThan(900) // not hidden off-screen

    // Trending research card(s) should be visible and NOT overlapping the footer.
    const card = page.getByText(/Best Headphones|Tokyo Travel|Top Laptops/).first()
    await expect(card).toBeVisible()
    const cardBox = await card.boundingBox()
    const footer = page.locator('footer').first()
    const footerBox = await footer.boundingBox()
    if (cardBox && footerBox) {
      expect(cardBox.bottom).toBeLessThanOrEqual(footerBox.top + 2) // ≤ footer top (1–2px slop)
    }
  })

  test('/chat?new=1 shows welcome screen AND chat input in viewport at 1440x900', async ({ page }) => {
    await page.goto(`${BASE_URL}/chat?new=1`)
    // Welcome headline.
    await expect(page.getByText(/Smart shopping|What can I help|How can I help/i).first()).toBeVisible()
    // Chat textarea must be visible and fit within viewport.
    const ta = page.locator('textarea[placeholder*="Ask anything"]').first()
    await expect(ta).toBeVisible()
    const box = await ta.boundingBox()
    expect(box).not.toBeNull()
    if (box) expect(box.bottom).toBeLessThan(900) // guards against P0-2 regression
  })

  test('product query returns ≥3 product cards with working affiliate link', async ({ page }) => {
    await page.goto(`${BASE_URL}/chat?new=1`)
    await page.locator('textarea[placeholder*="Ask anything"]').first().fill('best wireless earbuds under $100')
    await page.keyboard.press('Enter')

    // Wait for at least one product card to render. Give the stream up to 30s.
    await expect(page.locator('[data-testid*="product-card"], [class*="product-card"]').first()).toBeVisible({ timeout: 30_000 })
    const count = await page.locator('[data-testid*="product-card"], [class*="product-card"]').count()
    expect(count).toBeGreaterThanOrEqual(3)

    // At least one Amazon link must carry tag=revguide-20 (revenue guardrail).
    const hrefs = await page.locator('a[href*="amazon"]').evaluateAll((els) =>
      els.map((e) => (e as HTMLAnchorElement).href),
    )
    const tagged = hrefs.filter((h) => /[?&]tag=revguide-20(\b|$)/.test(h))
    expect(tagged.length).toBeGreaterThan(0)

    // Fallback string must NOT appear.
    await expect(page.getByText(/error while formatting the response/i)).toHaveCount(0)

    // Revenue guardrails (2026-07 launch hardening):
    // 1. Prices must be real — at least one card shows a non-zero dollar price.
    const priceTexts = await page.locator('text=/\\$\\d/').allTextContents()
    const realPrices = priceTexts.filter((t) => !/\$0(\.0+)?(\s|$)/.test(t))
    expect(realPrices.length).toBeGreaterThan(0)

    // 2. eBay links must not carry the placeholder campaign ID (earns $0).
    const ebayHrefs = await page.locator('a[href*="ebay"]').evaluateAll((els) =>
      els.map((e) => (e as HTMLAnchorElement).href),
    )
    for (const h of ebayHrefs) expect(h).not.toContain('campid=1234567890')

    // 3. Link-injection guard: every link in the results must be http(s) —
    //    provider/LLM data must never produce javascript:/data: hrefs.
    const allHrefs = await page.locator('main a[href]').evaluateAll((els) =>
      els.map((e) => (e as HTMLAnchorElement).href),
    )
    for (const h of allHrefs) expect(h).toMatch(/^https?:/)
  })

  test('travel query completes within 30s — no indefinite hang', async ({ page }) => {
    await page.goto(`${BASE_URL}/chat?new=1`)
    await page.locator('textarea[placeholder*="Ask anything"]').first().fill('plan a 5-day trip to Tokyo')
    await page.keyboard.press('Enter')

    // Either a clarifier question OR hotel/flight cards should appear within 30s.
    const done = page.locator('text=/clarif|Which city|Hotel|Flight|Tokyo|Travel Tips/i').first()
    await expect(done).toBeVisible({ timeout: 30_000 })
  })

  test('/browse/nonexistent renders the custom editorial 404, not the Next.js default', async ({ page }) => {
    const response = await page.goto(`${BASE_URL}/browse/nonexistent-slug-xyz`)
    expect(response?.status()).toBe(404)

    // Custom 404 should either show our editorial copy or a back-to-home CTA.
    // The Next.js default is literally "404" + "This page could not be found." — we
    // assert the page is NOT exactly that.
    const body = await page.locator('body').textContent()
    const isDefaultOnly =
      body?.trim().includes('404') &&
      body?.trim().includes('This page could not be found') &&
      !(body.match(/home|Discover|Ask|ReviewGuide/i))
    expect(isDefaultOnly).toBeFalsy()
  })
})
