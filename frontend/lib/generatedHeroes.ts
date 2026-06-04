/**
 * Manifest of topic slugs that have a generated, palette-matched hero image at
 * `public/images/topics/hero/<slug>.webp`.
 *
 * TopicHero only requests the generated asset for slugs listed here; everything
 * else renders the stock category image directly. This avoids a guaranteed 404
 * (and broken-image flash) on every topic page for slugs whose AI hero hasn't
 * been generated yet — the generator (`scripts/gen-topic-heroes.mjs`) needs a
 * Gemini key with image-gen quota, so the library fills in incrementally.
 *
 * When you generate a new hero, add its slug here.
 */
export const GENERATED_HERO_SLUGS: ReadonlySet<string> = new Set<string>([
  // e.g. 'running-shoes', once public/images/topics/hero/running-shoes.webp exists
])

export function hasGeneratedHero(slug: string): boolean {
  return GENERATED_HERO_SLUGS.has(slug)
}
