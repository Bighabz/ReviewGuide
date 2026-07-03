# QA Round 7 — Findings (2026-06-03)

**Scope:** prod sweep after PRs #92–#98 + `USE_PRODUCT_VERIFICATION` enablement.
**Method:** one continuous 3-search prod session (the rounds-4/5 meta-lesson: every flow tested as a 2nd/3rd search), Playwright-driven, desktop.
**Prod at:** main `806852b`, both Railway + Vercel verified at that SHA.

## Result: ALL PASS — zero P0/P1/P2 findings

| # | Scenario | Result |
|---|---|---|
| 1 | **Comparison mode, 1st search** — `iPhone 15 vs Pixel 8` | ✅ ONE dimension question naming both products; chips = Camera / Battery life / Ecosystem / Price; tapped Camera |
| 2 | **Camera-weighted verdict** | ✅ Opens "On camera, the iPhone 15 Pro is the pick — 5x optical zoom…"; closes "if camera is truly your deciding factor"; 12 camera mentions |
| 3 | **Comparison mode, 2nd search** (meta-lesson) — `Sony WH-1000XM5 vs Bose QuietComfort Ultra` typed into the same session | ✅ NEW question with headphone dimensions (Sound quality / Noise cancelling / Comfort / Price) — zero bleed from the phone comparison |
| 4 | **NC-weighted verdict** | ✅ "The Sony WH-1000XM5 is the pick for noise cancellation…" / "But you said noise cancelling is the deciding factor, so the Sony's ANC advantage is the tiebreaker" |
| 5 | **Editor's pick badge (#93) in comparison flows** | ✅ Present on consensus block |
| 6 | **Refinement chips after comparison results** | ✅ Present (clarify + refine_budget categories) |
| 7 | **F5 regression** — `best blender` as 3rd search after two comparisons | ✅ Full blender expert trio (Smoothies/…, multi-select features, $100–$200/…  brackets), use-case first / budget last, NO inheritance, NO comparison question |
| 8 | **Skip-all (#96) on 3rd search** | ✅ Tap → 5 real blender cards (Vitamix A3500, Breville Super Q, Ninja BN701, Blendtec 725, KitchenAid Pro Line) |
| 9 | Ratings ≤ 5.0 | ✅ 8/8 |
| 10 | Zero Google Shopping buy links | ✅ 0 |
| 11 | Amazon links all tagged `revguide-20` | ✅ 15/15 |
| 12 | No $0.00 / NaN prices | ✅ 0 |
| 13 | Console errors + warnings (whole session) | ✅ 0 / 0 |

## P3 observations (no action taken)

- "Ninja BN701 Professional Plus **Bender**" — typo comes from the source listing title (search data), not our rendering. Could be cleaned by a title-normalization pass; cosmetic.
- The blender flow's skip-all produced results without a budget filter (by design — skip-all = no constraints).

## Not covered this round (carry to Round 8)

- Mobile sweep (375px) of the comparison flow
- Travel / general / greeting regression (unchanged code paths this burst)
- Under-budget badge re-verification (verified in its own ship cycle this session; not re-swept here)
- axe accessibility pass
