import type { MetadataRoute } from 'next'

const SITE_URL = 'https://www.reviewguide.ai'

// /admin + /login are the Phase-1 admin surface; /profile + /saved + /compare
// are per-visitor state — none of them belong in a search index.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/admin', '/login', '/profile', '/saved', '/compare'],
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  }
}
