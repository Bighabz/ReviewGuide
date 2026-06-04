# Topic hero illustrations

AI-generated, palette-matched hero art for /topic/[slug] pages.
Filenames are <slug>.webp (e.g. running-shoes.webp).

Generate with: GEMINI_API_KEY=... node scripts/gen-topic-heroes.mjs [slug ...]
Missing files fall back to the stock category image (see components/TopicHero.tsx).

After generating a new hero, add its slug to `GENERATED_HERO_SLUGS` in
`lib/generatedHeroes.ts`. TopicHero only requests the generated asset for slugs
listed there — otherwise it renders the stock image directly (no 404).
