import type { Page, BrowserContext, Route } from '@playwright/test'

/**
 * Shared builders for the QA-loop checks. Shapes are taken verbatim from the
 * frontend contract:
 *   - SSE framing: `event: X\ndata: {json}\n\n`, stream ends with a blank line
 *     (chatApi.ts:329-348).
 *   - product cards render via VerdictCard from a {type:'products', data:[...]}
 *     ui_block (BlockRegistry.tsx:35-43) - NOT ProductCarousel.
 *   - clarifier chips need message.followups as a NON-array object
 *     (Message.tsx:634, data-testid clarifier-option-chip).
 *   - history restore: GET /v1/chat/history/<id> -> {success, messages:[{role,
 *     content, created_at, message_metadata}]}; ChatContainer spreads
 *     message_metadata onto the message (so ui_blocks/followups live there).
 *     Entering /chat?session=... runs switchToSession() which WIPES a
 *     localStorage seed, so content must come from a stubbed history response.
 */

export const AFFILIATE_TAG = 'tag=revguide-20'
export const BACKEND_HOST = 'backend-production-0ae7.up.railway.app'

export interface Item {
  product_id: string
  title: string
  price: number
  currency: string
  merchant: string
  image_url: string
  affiliate_link: string
  rating: number
  review_count: number
  rank: number
}

export function makeItems(n: number): Item[] {
  const items: Item[] = []
  for (let i = 1; i <= n; i++) {
    items.push({
      product_id: `p${i}`,
      title: `Test Product ${i}`,
      price: 100 + i,
      currency: 'USD',
      merchant: 'Amazon',
      image_url: `https://img.invalid/p${i}.jpg`,
      affiliate_link: `https://www.amazon.com/dp/QA00000${i}?${AFFILIATE_TAG}`,
      rating: 4.5,
      review_count: 1000 + i,
      rank: i,
    })
  }
  return items
}

/**
 * #2 global default-deny: allow only reviewguide.ai (+ subdomains), the
 * backend origin, and localhost; ABORT every other host so a stray affiliate
 * window.open / analytics / external fetch can never leave. Register FIRST so
 * later, more-specific fulfills win (Playwright matches newest route first).
 */
export async function lockdownNetwork(context: BrowserContext): Promise<void> {
  await context.route('**/*', (route: Route) => {
    const url = route.request().url()
    if (url.startsWith('data:') || url.startsWith('blob:')) return route.continue()
    let host = ''
    try {
      host = new URL(url).hostname
    } catch {
      return route.continue()
    }
    const allowed =
      host === 'localhost' ||
      host === '127.0.0.1' ||
      host === BACKEND_HOST ||
      host === 'reviewguide.ai' ||
      host.endsWith('.reviewguide.ai')
    return allowed ? route.continue() : route.abort()
  })
}

/** A correctly-framed SSE stream ending in a `done` carrying a products block. */
export function sseProductsDone(sessionId: string, items: Item[]): string {
  const done = {
    session_id: sessionId,
    status: 'completed',
    intent: 'product',
    ui_blocks: [{ type: 'products', title: 'Top picks', data: items }],
    citations: [],
    followups: null,
    next_suggestions: [],
    completeness: 'full',
    request_id: 'req-mock',
    user_id: 1,
  }
  return (
    'event: status\ndata: {"text":"Reading reviews…"}\n\n' +
    'event: content\ndata: {"token":"Here are the top picks. "}\n\n' +
    'event: done\ndata: ' + JSON.stringify(done) + '\n\n'
  )
}

/** Fulfil a mocked chat stream (never reaches the real backend). */
export async function mockChatStream(page: Page, body: string): Promise<void> {
  await page.route('**/v1/chat/stream', async (route: Route) => {
    if (route.request().method() === 'OPTIONS') {
      return route.fulfill({
        status: 204,
        headers: {
          'access-control-allow-origin': '*',
          'access-control-allow-methods': 'POST, OPTIONS',
          'access-control-allow-headers': '*',
        },
      })
    }
    return route.fulfill({
      status: 200,
      headers: {
        'content-type': 'text/event-stream; charset=utf-8',
        'cache-control': 'no-cache',
        'access-control-allow-origin': '*',
      },
      body,
    })
  })
}

/** Stub GET /v1/chat/history/<id> to restore seeded messages (survives the
 * switchToSession wipe). Each message's ui_blocks/followups go in metadata. */
export async function stubHistory(page: Page, messages: any[]): Promise<void> {
  await page.route('**/v1/chat/history/**', (route: Route) =>
    route.fulfill({
      status: 200,
      headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
      body: JSON.stringify({ success: true, messages }),
    }),
  )
}

export function productsHistory(items: Item[]): any[] {
  return [
    {
      role: 'assistant',
      content: 'Here are the top picks.',
      created_at: '2026-08-22T00:00:00Z',
      message_metadata: { ui_blocks: [{ type: 'products', title: 'Top picks', data: items }] },
    },
  ]
}

export function clarifierHistory(): any[] {
  return [
    {
      role: 'assistant',
      content: 'A couple of quick questions:',
      created_at: '2026-08-22T00:00:00Z',
      message_metadata: {
        followups: {
          intro: 'A couple of quick questions:',
          questions: [
            {
              slot: 'use_case',
              question: 'What will you mainly use it for?',
              options: ['Student / everyday', 'Gaming', 'Creative / video editing'],
              type: 'single_select',
            },
          ],
          closing: "Then I'll pull together a shortlist.",
        },
      },
    },
  ]
}

/**
 * Containment guard: capture the affiliate click POST and fulfil it LOCALLY
 * (never let it reach the real backend - it is a prod write). The external
 * commerce host (window.open target) is already blocked by lockdownNetwork;
 * this also captures the payload for assertions. Returns the capture array.
 */
export async function guardAffiliate(page: Page): Promise<any[]> {
  const captured: any[] = []
  await page.route('**/v1/affiliate/click', async (route: Route) => {
    try {
      captured.push(route.request().postDataJSON())
    } catch {
      captured.push(null)
    }
    return route.fulfill({
      status: 200,
      headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
      body: '{"ok":true}',
    })
  })
  await page.route('**/v1/affiliate/event', (route: Route) =>
    route.fulfill({ status: 200, headers: { 'access-control-allow-origin': '*' }, body: '{}' }),
  )
  return captured
}

/** Silence the render telemetry POST. History is stubbed per-test. */
export async function stubNoise(page: Page): Promise<void> {
  await page.route('**/v1/telemetry/render', (route: Route) =>
    route.fulfill({ status: 200, headers: { 'access-control-allow-origin': '*' }, body: '{}' }),
  )
}

/** Seed the saved/compare localStorage (savedItems.ts). /saved does not
 * switchToSession, so this is not wiped. id must equal slug(name). */
export function savedItem(name: string, price: number, url: string): any {
  return {
    id: name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, ''),
    name,
    price,
    imageUrl: 'https://img.invalid/x.jpg',
    url,
    role: 'Best price',
    savedAt: 1735689600000,
  }
}
