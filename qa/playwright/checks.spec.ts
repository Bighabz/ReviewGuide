import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import {
  AFFILIATE_TAG,
  makeItems,
  productsHistory,
  clarifierHistory,
  sseProductsDone,
  mockChatStream,
  stubHistory,
  guardAffiliate,
  stubNoise,
  lockdownNetwork,
  savedItem,
} from './helpers'

/**
 * QA-loop Tier A checks. Containment invariants enforced at the Playwright
 * layer, independent of any app behavior:
 *   - lockdownNetwork default-denies every non-reviewguide.ai host (the
 *     affiliate window.open target can never load),
 *   - the chat stream is route-mocked in every /chat test (no real chat),
 *   - the affiliate click POST is captured + fulfilled locally (never a prod
 *     write),
 *   - QA sessions enter via /chat?session=qa-auto-pw-... and content is
 *     restored through a stubbed history response.
 *
 * DELIVERED but unvalidated: these require a first supervised run (npm ci +
 * playwright install) against live prod DOM to confirm selectors.
 */

const RUN = process.env.QA_RUN_ID || 'local'
const qaSession = (n: string) => `qa-auto-pw-${RUN}-${n}`

// Narrow allowlist (#18): only the lockdown's own abort noise + benign chatter.
// A real failed resource (404/500 chunk) is NOT allowlisted and fails A1.
const CONSOLE_ALLOW = [
  /net::ERR_ABORTED/i,
  /net::ERR_FAILED/i,
  /net::ERR_BLOCKED/i,
  /ResizeObserver/i,
  /favicon/i,
]

function watchConsole(page: Page): string[] {
  const errors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return
    const text = msg.text()
    if (CONSOLE_ALLOW.some((re) => re.test(text))) return
    errors.push(text)
  })
  return errors
}

test.beforeEach(async ({ context, page }) => {
  await lockdownNetwork(context)
  await stubNoise(page)
})

test('A1 Discover loads with a clean console', async ({ page }) => {
  const errors = watchConsole(page)
  await page.goto('/')
  await page.waitForLoadState('networkidle')
  expect(errors, `unexpected console errors: ${errors.join(' | ')}`).toHaveLength(0)
})

test('A2 Discover search hands off to /chat and auto-submits', async ({ page }) => {
  await mockChatStream(page, sseProductsDone(qaSession('a2'), makeItems(5)))
  await page.goto('/')
  // Discover hero input renders as <input> with no type attribute -> textbox role.
  const box = page.getByRole('textbox').first()
  await box.fill('best noise cancelling headphones')
  await box.press('Enter')
  await page.waitForURL('**/chat**', { timeout: 15_000 })
  await expect(page.locator(`a[href*="${AFFILIATE_TAG}"]`).first()).toBeVisible({ timeout: 15_000 })
})

test('A3 five product cards render from restored history', async ({ page }) => {
  await stubHistory(page, productsHistory(makeItems(5)))
  await mockChatStream(page, sseProductsDone(qaSession('a3'), makeItems(5)))
  await page.goto(`/chat?session=${qaSession('a3')}`)
  await expect
    .poll(async () => page.locator(`a[href*="${AFFILIATE_TAG}"]`).count(), { timeout: 15_000 })
    .toBeGreaterThanOrEqual(5)
})

test('A4 clarifier chips render and a chip resumes to results', async ({ page }) => {
  await stubHistory(page, clarifierHistory())
  await mockChatStream(page, sseProductsDone(qaSession('a4'), makeItems(5)))
  await page.goto(`/chat?session=${qaSession('a4')}`)
  const chip = page.locator('[data-testid="clarifier-option-chip"]').first()
  await expect(chip).toBeVisible({ timeout: 15_000 })
  await chip.click()
  await expect(page.locator(`a[href*="${AFFILIATE_TAG}"]`).first()).toBeVisible({ timeout: 15_000 })
})

test('A5 affiliate click never reaches prod and keeps the qa-auto marker', async ({ page }) => {
  // lockdownNetwork already blocks the external window.open target; guardAffiliate
  // captures the click POST locally so it never becomes a real prod write.
  const clicks = await guardAffiliate(page)
  await stubHistory(page, productsHistory(makeItems(5)))
  await mockChatStream(page, sseProductsDone(qaSession('a5'), makeItems(5)))
  await page.goto(`/chat?session=${qaSession('a5')}`)

  const cta = page.locator(`a[href*="${AFFILIATE_TAG}"]`).first()
  await expect(cta).toBeVisible({ timeout: 15_000 })
  const href = await cta.getAttribute('href')
  expect(href, 'anchor must be a real affiliate URL').toContain(AFFILIATE_TAG)

  await cta.click()
  await page.waitForTimeout(1000)

  // The click POST fired, was captured locally, and carried the qa-auto marker
  // (the exact regression - UUID wipe destroying the marker - fails this).
  expect(clicks.length, 'affiliate click POST should have fired').toBeGreaterThanOrEqual(1)
  expect(clicks[0], 'click payload must be present').toBeTruthy()
  expect(String(clicks[0].session_id)).toMatch(/^qa-auto-pw-/)
})

test('A6 saved + compare render seeded items', async ({ page, context }) => {
  const items = [
    savedItem('Test Product 1', 101, `https://www.amazon.com/dp/QA1?${AFFILIATE_TAG}`),
    savedItem('Test Product 2', 102, `https://www.amazon.com/dp/QA2?${AFFILIATE_TAG}`),
  ]
  await context.addInitScript(
    ([saved]) => {
      try {
        localStorage.setItem('saved_items', JSON.stringify(saved))
        localStorage.setItem('compare_selection', JSON.stringify((saved as any[]).map((s) => s.id)))
      } catch {
        /* ignore */
      }
    },
    [items] as const,
  )
  await page.goto('/saved')
  await expect(page.getByText(items[0].name).first()).toBeVisible({ timeout: 15_000 })
  await page.goto('/compare')
  await expect(page.getByText(items[0].name).first()).toBeVisible({ timeout: 15_000 })
})

test('A7 mobile chat has no horizontal scroll and 44px touch targets', async ({ page }) => {
  test.skip(test.info().project.name !== 'chromium-mobile', 'mobile-only check')
  await stubHistory(page, clarifierHistory())
  await mockChatStream(page, sseProductsDone(qaSession('a7'), makeItems(5)))
  await page.goto(`/chat?session=${qaSession('a7')}`)
  await page.waitForLoadState('networkidle')

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow, 'no horizontal body scroll').toBeLessThanOrEqual(1)

  const chips = page.locator('[data-testid="clarifier-option-chip"]')
  await expect(chips.first()).toBeVisible({ timeout: 15_000 })
  const count = await chips.count()
  const undersized: string[] = []
  for (let i = 0; i < count; i++) {
    const box = await chips.nth(i).boundingBox()
    if (box && (box.height < 44 || box.width < 44)) {
      undersized.push(`chip ${i}: ${Math.round(box.width)}x${Math.round(box.height)}`)
    }
  }
  expect(undersized, `touch targets under 44px: ${undersized.join(', ')}`).toHaveLength(0)
})
