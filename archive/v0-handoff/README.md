# v0 handoff — carousel + Discover redesign

Two self-contained components to iterate on in [v0.dev](https://v0.dev). Each renders instantly (sample data + colors baked in, no imports from this repo). You judge the look; I wire the result back into the real app.

## Files
- **`carousel.v0.tsx`** — the in-chat product-results carousel + review card (shows after a product search).
- **`discover.v0.tsx`** — the Discover/home page (hero + "Popular this week" grid).

## How to use
1. Go to v0.dev → new chat.
2. Paste the **entire contents** of one file.
3. Prompt v0, e.g.:
   > "This is my current [product carousel / discover page]. Keep the warm terracotta-on-cream palette and the fonts. Make it look way better and more premium on **both mobile and desktop**. [your specific wants]."
4. Iterate visually until *you* like it. Then copy the final component back to me (paste the code, or just a screenshot).

## Hard constraints (tell v0 to keep these)
**Carousel:** keep the terracotta palette; it must show a ranked list (a clear #1 "top pick"), each card needs the product image, rating, a short summary, and the "Where to buy" price tiles.

**Discover:** **keep** the `ReviewGuide.Ai` wordmark, the search bar, and the palette. The "Popular this week" topic grid is the main thing to redesign.

## Palette (don't let v0 drift)
| token | value | use |
|---|---|---|
| terracotta | `#B8543A` | primary accent |
| terra soft | `#F4E2D7` | tints/fills |
| terra ink | `#7A3624` | hover/pressed |
| paper | `#FAFAF7` | background |
| paper-hi | `#FFFFFF` | raised cards |
| paper-alt | `#F5F4F0` | sunken surfaces |
| ink | `#1A1816` | primary text |
| ink-2 | `#6B6560` | secondary text |
| ink-3 / muted | `#9B9590` | muted text |
| line | `#E8E6E1` | borders/dividers |
| **no blue** | — | the brand has no blue |

## Fonts
- **DM Sans** — UI / sans
- **Newsreader** — serif body (product summaries, topic titles)
- **Instrument Serif** *(italic)* — display ("What are you researching?")

(The files fall back gracefully if v0 hasn't loaded these — but ask v0 to add them from Google Fonts for an accurate look.)

## What I do with the result
When you hand back the v0 output, I integrate it into the real app — real product/topic data, the `sendSuggestion`/clarifier wiring, design tokens (swap the inlined hexes back to the CSS vars), save/affiliate links, tests, and deploy. The sample data and inlined colors here are scaffolding; the real wiring is my side.

## Note
This `v0-handoff/` folder is scratch — it's not imported by the app and can be deleted once the redesign lands.
```
```
