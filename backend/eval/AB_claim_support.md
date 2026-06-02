# A/B — Does real review evidence improve claim accuracy? (Tier 5 / A1 validation)

**Date:** 2026-06-02 · **Model:** `anthropic/claude-haiku-4.5` (prod composer) ·
**Judge:** `anthropic/claude-sonnet-4.6` (blind) · **Cases:** `earbuds_under_100`, `need_a_laptop`

Run it yourself:
```bash
# grounded (writer gets the product/review evidence — current prod with A1 on)
python -m eval.voice_eval --models anthropic/claude-haiku-4.5 --cases earbuds_under_100,need_a_laptop
# ungrounded (evidence stripped — writer relies on parametric knowledge, i.e. A1 off)
python -m eval.voice_eval --models anthropic/claude-haiku-4.5 --cases earbuds_under_100,need_a_laptop --ungrounded
```
The `--ungrounded` flag strips the product/review lines from the writer's input but the
judge still scores `claim_support` against the full evidence — so the delta isolates how
much real evidence improves claim accuracy.

## Result

| Arm | Mean judge | claim_support | rank_and_commit | no_glazing |
|-----|-----------:|--------------:|----------------:|-----------:|
| **Grounded** (A1 on) | **4.57** | **5.0** | 5.0 | 5.0 |
| **Ungrounded** (A1 off) | **2.57** | **2.0** | 1.5 | 3.5 |
| **Delta** | **+2.00** | **+3.00** | +3.5 | +1.5 |

## What the judge saw

- **Grounded:** *"Every claim traces directly to the evidence payload — ANC killing subway
  hum, 50-hour battery, JBuds' bass-forward tuning, Nothing Ear (a)'s $119 price — all present
  without fabrication."* (5/5)
- **Ungrounded:** *"The entire body is built around the Soundcore Life P3 and JBL TUNE 125TWS,
  neither of which appears in the evidence; every factual claim is fabricated wholesale, and the
  actual evidence products are completely ignored."* (1/5)

## Takeaway

Without real evidence the composer **invents products that don't exist** and writes confident
specs about them — the exact failure mode Tier 5 targets. Grounding (A1: `review_search` in the
standard plan, now flowing via the SerpApi.com fallback) lifts claim accuracy from 2.0 → 5.0 and
overall voice from 2.6 → 4.6. This is the data justifying A1's ~+8s latency, and why A2
(`USE_PRODUCT_VERIFICATION` — drop products with no real shopping match or reviews) is the
necessary backstop for any name that still slips through. Latency is mitigated by two-speed
routing (Tier 5c), which spends the evidence budget only on considered purchases.

**Recommendation:** keep `USE_REVIEW_GROUNDING` on in prod (already enabled), enable
`USE_PRODUCT_VERIFICATION` to harden against residual hallucinations, and use `USE_TWO_SPEED_COMPOSE`
to hold latency on quick queries.
