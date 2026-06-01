/**
 * Group C — Discover topic pool. Locks the invariants the carousel and the
 * /topic/[slug] landing pages depend on, and verifies every referenced image
 * actually exists on disk (so no card renders a broken poster).
 */
import { describe, it, expect } from 'vitest'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { DISCOVER_TOPICS, TOPIC_BODIES, getTopicBySlug } from '@/lib/discoverTopics'

describe('DISCOVER_TOPICS', () => {
  it('is a large pool (>= 40 topics) for fresh rotation each visit', () => {
    expect(DISCOVER_TOPICS.length).toBeGreaterThanOrEqual(40)
  })

  it('has unique, kebab-case slugs', () => {
    const slugs = DISCOVER_TOPICS.map((t) => t.slug)
    expect(new Set(slugs).size).toBe(slugs.length)
    for (const slug of slugs) {
      expect(slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)
    }
  })

  it('every topic has all fields populated', () => {
    for (const t of DISCOVER_TOPICS) {
      for (const key of ['title', 'hook', 'category', 'image', 'query', 'blurb'] as const) {
        expect(t[key].trim().length, `${t.slug}.${key}`).toBeGreaterThan(0)
      }
    }
  })

  it('every referenced image exists under public/', () => {
    for (const t of DISCOVER_TOPICS) {
      expect(t.image.startsWith('/images/'), `${t.slug} image path`).toBe(true)
      const onDisk = join(process.cwd(), 'public', t.image)
      expect(existsSync(onDisk), `missing asset for ${t.slug}: ${t.image}`).toBe(true)
    }
  })

  it('getTopicBySlug resolves known slugs (with body attached) and undefined otherwise', () => {
    const first = DISCOVER_TOPICS[0]
    expect(getTopicBySlug(first.slug)).toEqual({ ...first, body: TOPIC_BODIES[first.slug] })
    expect(getTopicBySlug('definitely-not-a-real-topic')).toBeUndefined()
  })

  it('every topic has a non-trivial blog body (no bodyless blog page)', () => {
    for (const t of DISCOVER_TOPICS) {
      const body = TOPIC_BODIES[t.slug]
      expect(body, `missing body for ${t.slug}`).toBeTruthy()
      expect(body.length, `body too short for ${t.slug}`).toBeGreaterThan(120)
    }
  })
})
