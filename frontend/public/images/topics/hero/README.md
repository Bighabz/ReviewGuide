# Topic hero illustrations

AI-generated, palette-matched hero art for /topic/[slug] pages.
Filenames are <slug>.webp (e.g. running-shoes.webp).

Generate with: GEMINI_API_KEY=... node scripts/gen-topic-heroes.mjs [slug ...]
Missing files fall back to the stock category image (see components/TopicHero.tsx).
