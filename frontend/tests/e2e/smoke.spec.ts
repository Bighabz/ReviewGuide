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
  })

  test('travel query completes within 30s — no indefinite hang', async ({ page }) => {
    await page.goto(`${BASE_URL}/chat?new=1`)
    await page.locator('textarea[placeholder*="Ask anything"]').first().fill('plan a 5-day trip to Tokyo')
    await page.keyboard.press('Enter')

    // Either a clarifier question OR hotel/flight cards should appear within 30s.
    const done = page.locator('text=/clarif|Which city|Hotel|Flight|Tokyo|Travel Tips/i').first()
    await expect(done).toBeVisible({ timeout: 30_000 })
  })

  test('last line of a long answer clears the composer at 1440px and 390px', async ({ page }) => {
    // PLAN-7 T7 (QA audit: "text clipped behind composer"). The defect does
    // NOT reproduce in the current layout — measured 2026-08-17: the last
    // message bottom clears the composer top by 43px (desktop) / 28px (390px)
    // at full scroll. This pins that geometry so it stays true.
    const seed = [
      { id: 'u1', role: 'user', content: 'best espresso machine under $500', timestamp: 1735689600000 },
      {
        id: 'a1',
        role: 'assistant',
        content:
          'Long verdict. ' +
          Array.from({ length: 60 }, (_, i) => `Sentence ${i + 1} carries real content.`).join(' ') +
          ' FINAL LINE MARKER.',
        timestamp: 1735689601000,
      },
    ]
    await page.goto(BASE_URL)
    await page.evaluate((messages) => {
      localStorage.setItem('chat_messages', JSON.stringify(messages))
      localStorage.setItem('chat_session_id', '11111111-2222-4333-8444-555555555555')
    }, seed)

    for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport)
      await page.goto(`${BASE_URL}/chat`)
      await page.waitForSelector('[id^="message-"]')
      const overlap = await page.evaluate(() => {
        const msgs = document.querySelectorAll('[id^="message-"]')
        const last = msgs[msgs.length - 1] as HTMLElement
        const composer = document.getElementById('chat-input-wrapper')
        const scroller = last?.closest('.overflow-y-auto') as HTMLElement | null
        if (!last || !composer || !scroller) return { error: true }
        scroller.scrollTop = scroller.scrollHeight
        const lastBottom = last.getBoundingClientRect().bottom
        const composerTop = composer.getBoundingClientRect().top
        return { error: false, overlapPx: Math.max(0, lastBottom - composerTop) }
      })
      expect(overlap.error).toBeFalsy()
      expect(overlap.overlapPx).toBe(0)
    }
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

  test('no horizontal body scroll on a seeded product answer at 390px', async ({ page }) => {
    // PLAN-10 T3: the response surface (cards, badges, ledger rows, chips)
    // must scroll wide content inside its own containers, never the body.
    const seed = [
      { id: 'u1', role: 'user', content: 'best robot vacuums for pet hair', timestamp: 1735689600000 },
      {
        id: 'a1', role: 'assistant', timestamp: 1735689601000,
        content: 'The iRobot Roomba j7+ is the pick for pet hair households.',
        ui_blocks: [{
          type: 'product_review',
          data: {
            product_name: 'iRobot Roomba j7+ Self-Emptying Robot Vacuum Extended Name',
            rating: '4.4/5',
            summary: 'Smart navigation and reliable pet-hair pickup across carpet and hardwood floors.',
            image_url: 'https://img.example/roomba.jpg',
            features: ['Best Overall'],
            pros: [{ description: 'Obstacle avoidance that actually works' }],
            cons: [{ description: 'Bags cost money over time' }],
            rank: 1,
            affiliate_links: [
              { product_id: 'a', title: 'Amazon - Roomba', price: 398.55, currency: 'USD', affiliate_link: 'https://amazon.example/r', merchant: 'Amazon', condition_label: null, price_source: 'native', over_budget: true },
              { product_id: 'b', title: 'eBay - Roomba', price: 156.55, currency: 'USD', affiliate_link: 'https://ebay.example/r', merchant: 'eBay', condition_label: 'Open box', price_source: 'native', below_budget_floor: true },
            ],
          },
        }],
        next_suggestions: [
          { id: 's1', question: 'Which one handles long-haired shedding breeds best over hardwood?' },
        ],
      },
    ]
    await page.goto(BASE_URL)
    await page.evaluate((messages) => {
      localStorage.setItem('chat_messages', JSON.stringify(messages))
      localStorage.setItem('chat_session_id', '11111111-2222-4333-8444-555555555555')
    }, seed)
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto(`${BASE_URL}/chat`)
    await page.waitForSelector('[id^="message-"]')
    const widths = await page.evaluate(() => ({
      body: document.body.scrollWidth,
      viewport: window.innerWidth,
    }))
    expect(widths.body).toBeLessThanOrEqual(widths.viewport + 1)
  })
