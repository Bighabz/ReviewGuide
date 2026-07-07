import type { MetadataRoute } from 'next'

const SITE_URL = 'https://www.reviewguide.ai'

// Static, public routes only. /chat and /results/[id] are session-driven and
// /topic/[slug] has no enumerable slug source yet — add them here if that changes.
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${SITE_URL}/`, changeFrequency: 'daily', priority: 1 },
    { url: `${SITE_URL}/affiliate-disclosure`, changeFrequency: 'yearly', priority: 0.3 },
    { url: `${SITE_URL}/privacy`, changeFrequency: 'yearly', priority: 0.3 },
    { url: `${SITE_URL}/terms`, changeFrequency: 'yearly', priority: 0.3 },
  ]
}
