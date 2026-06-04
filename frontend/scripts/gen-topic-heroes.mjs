// Offline generator for Dreambeans-style topic hero illustrations.
//
// Produces palette-matched AI hero art for /topic/[slug] pages and writes it to
// public/images/topics/hero/<slug>.webp, where <TopicHero> picks it up
// automatically (falling back to the stock image when absent).
//
// Requires a Gemini API key WITH image-generation quota:
//   GEMINI_API_KEY=...  node scripts/gen-topic-heroes.mjs [slug ...]
//
// Pass one or more slugs to generate a subset; omit to generate all topics.
// Deps: `sharp` (already a project dependency) for PNG->webp. Node 18+ (global fetch).

import { readFile, mkdir } from 'node:fs/promises'
import { dirname, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT_DIR = resolve(__dirname, '../public/images/topics/hero')
const MODEL = 'gemini-2.5-flash-image' // image-capable Gemini model
const KEY = process.env.GEMINI_API_KEY

if (!KEY) {
  console.error('Set GEMINI_API_KEY (with image-gen quota) and re-run.')
  process.exit(1)
}

// Minimal slug→subject map. Extend as needed; unlisted slugs use a generic line.
const SUBJECTS = {
  'running-shoes': 'a single sleek running shoe mid-stride on a winding trail at dawn, gentle motion lines',
  'espresso-machines': 'a home espresso machine pulling a shot into a small cup on a kitchen counter, soft steam rising',
  'tokyo-guide': 'a narrow neon-lit Tokyo alley at night with paper lanterns, reimagined in warm terracotta tones',
  'noise-cancelling-headphones': 'a pair of over-ear headphones, abstract sound waves dissolving into calm silence around them',
}

const palette =
  'warm terracotta-and-cream palette: terracotta #B8543A as the dominant accent, ' +
  'soft cream #FAFAF7 background, deep charcoal #1A1816 for fine detail. ' +
  'Minimal flat-shaded vector style with a subtle paper-grain texture. ' +
  'Calm, sophisticated, editorial mood. Centered composition with generous ' +
  'negative space toward the bottom for a text overlay. Absolutely no text, no ' +
  'words, no letters. Wide 3:2 landscape aspect ratio.'

function promptFor(slug, title) {
  const subject = SUBJECTS[slug] || `an evocative editorial scene representing "${title}"`
  return `Editorial magazine illustration in a ${palette} Subject: ${subject}.`
}

async function genOne(slug, title) {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${KEY}`
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: promptFor(slug, title) }] }],
      generationConfig: { responseModalities: ['IMAGE'] },
    }),
  })
  if (!res.ok) throw new Error(`${slug}: ${res.status} ${await res.text()}`)
  const json = await res.json()
  const part = json?.candidates?.[0]?.content?.parts?.find((p) => p.inlineData?.data)
  if (!part) throw new Error(`${slug}: no image in response`)
  const png = Buffer.from(part.inlineData.data, 'base64')
  // Guard: slugs feed a filesystem path. Today they're repo-controlled, but a
  // future CMS/data change must never let `../` escape the hero directory.
  if (!/^[a-z0-9-]+$/.test(slug)) throw new Error(`${slug}: invalid slug (expected [a-z0-9-])`)
  const out = resolve(OUT_DIR, `${slug}.webp`)
  if (!out.startsWith(OUT_DIR + sep)) throw new Error(`${slug}: resolved path escapes ${OUT_DIR}`)
  await sharp(png).resize(1200, 800, { fit: 'cover' }).webp({ quality: 82 }).toFile(out)
  console.log(`✓ ${slug} → ${out}`)
}

// Load the topic list. Fast path: a TS-aware runtime (tsx, or `node` with type
// stripping) can import the module directly. Fallback: plain `node` can't load
// a .ts module, so read the source and extract the {slug, title} pairs we need
// — keeps the documented `node scripts/gen-topic-heroes.mjs` command working
// with zero extra dependencies.
const TOPICS_TS = resolve(__dirname, '../lib/discoverTopics.ts')
async function loadTopics() {
  try {
    const mod = await import('../lib/discoverTopics.ts')
    if (Array.isArray(mod?.DISCOVER_TOPICS)) return mod.DISCOVER_TOPICS
  } catch { /* plain node — fall through to text parse */ }
  const src = await readFile(TOPICS_TS, 'utf8')
  const topics = []
  // Each topic is an object literal with `slug: '…'` and `title: '…'` fields.
  const re = /\bslug:\s*'([^']+)'[\s\S]*?\btitle:\s*'([^']+)'/g
  for (let m; (m = re.exec(src)); ) topics.push({ slug: m[1], title: m[2] })
  return topics
}

const DISCOVER_TOPICS = await loadTopics()
if (!DISCOVER_TOPICS.length) {
  console.error(`Could not load topics from ${TOPICS_TS}.`)
  process.exit(1)
}

const want = process.argv.slice(2)
const topics = want.length ? DISCOVER_TOPICS.filter((t) => want.includes(t.slug)) : DISCOVER_TOPICS

await mkdir(OUT_DIR, { recursive: true })
for (const t of topics) {
  try {
    await genOne(t.slug, t.title)
    await new Promise((r) => setTimeout(r, 1500)) // be gentle on rate limits
  } catch (e) {
    console.error(`✗ ${e.message}`)
  }
}
