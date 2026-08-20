import type { MetadataRoute } from 'next'

// T5 (2026-08-19): allow full crawling of the public marketing/discovery
// surface; /admin and /playground are operator tools, not indexable content.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/admin', '/playground', '/api/'],
    },
    sitemap: 'https://www.reviewguide.ai/sitemap.xml',
    host: 'https://www.reviewguide.ai',
  }
}