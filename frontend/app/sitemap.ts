import type { MetadataRoute } from 'next'
import { categories } from '@/lib/categoryConfig'

const SITE_URL = 'https://www.reviewguide.ai'

// T5 (2026-08-19): sitemap lists the stable public routes + every statically
// known section index (/browse/[category]). Dynamic routes (/topic/[slug],
// /product/[id], /results/[id]) are user/content-generated and omitted.
export default function sitemap(): MetadataRoute.Sitemap {
  const topLevel = ['', '/saved', '/compare', '/affiliate-disclosure', '/login', '/browse', '/privacy', '/terms']
  const entries: MetadataRoute.Sitemap = topLevel.map((path) => ({
    url: `${SITE_URL}${path || '/'}`,
    lastModified: new Date('2026-08-19'),
    changeFrequency: path === '' ? 'daily' : 'weekly',
    priority: path === '' ? 1 : 0.6,
  }))
  for (const cat of categories) {
    entries.push({
      url: `${SITE_URL}/browse/${cat.slug}`,
      lastModified: new Date('2026-08-19'),
      changeFrequency: 'weekly',
      priority: 0.7,
    })
  }
  return entries
}