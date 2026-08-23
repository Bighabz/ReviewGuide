import { defineConfig, devices } from '@playwright/test'

/**
 * QA-loop headless checks. Device profiles MIRROR
 * frontend/playwright.config.ts (the source of truth) so there is not a
 * second definition of "desktop"/"mobile" to drift.
 *
 * baseURL comes from BASE_URL (browser_qa passes qa/config.json
 * prod_frontend). Traces + video are OFF: a QA artifact must never carry a
 * captured auth header (secrets rule from the dual-verify).
 */
export default defineConfig({
  testDir: '.',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: 0,
  workers: 1,
  outputDir: process.env.QA_RUN_DIR || './test-results',
  use: {
    baseURL: process.env.BASE_URL || 'https://www.reviewguide.ai',
    trace: 'off',
    video: 'off',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      // iPhone 14 Pro viewport, but forced onto CHROMIUM (setup installs only
      // chromium; the device's default webkit would fail to launch).
      name: 'chromium-mobile',
      use: { ...devices['iPhone 14 Pro'], browserName: 'chromium' },
    },
  ],
})
