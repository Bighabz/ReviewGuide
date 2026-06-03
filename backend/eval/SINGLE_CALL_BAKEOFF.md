# Single-call consolidation bake-off — Sonnet 4.6 vs Haiku 4.5 vs gpt-4o-mini

**Date:** 2026-06-03 · **Judge:** `anthropic/claude-sonnet-4.6` (blind) · **Cases:** all 5 golden cases
**Question:** which model should write the consolidated single compose call (Tier 3: blog + consensus + descriptions in ONE request), measured at the consolidated call's real output size?

Run it yourself:
```bash
# Consolidated single-call workload (max_tokens 1400)
python -m eval.voice_eval --consolidated --models anthropic/claude-sonnet-4.6,anthropic/claude-haiku-4.5,openai/gpt-4o-mini
# Today's blog-only workload (max_tokens 700) — the baseline
python -m eval.voice_eval --models anthropic/claude-sonnet-4.6,anthropic/claude-haiku-4.5,openai/gpt-4o-mini
```

## Results — consolidated workload (blog + consensus + descriptions, one call)

| Model | Mean judge | p50 latency | Cost/resp | Output tokens | JSON parse | Voice violations |
|---|---:|---:|---:|---:|---:|---:|
| **Sonnet 4.6** | **4.71** | 26.2s | $0.0251 | 1024 | **4/5** ⚠️ | 2 |
| **Haiku 4.5** | **4.46** | 12.0s | $0.0079 | 924 | 5/5 | 0 |
| gpt-4o-mini | 2.83 | 11.6s | $0.0008 | 644 | 5/5 | 0 |

## Results — today's blog-only workload (baseline, same day)

| Model | Mean judge | p50 latency | Cost/resp | Output tokens | JSON parse | Voice violations |
|---|---:|---:|---:|---:|---:|---:|
| **Sonnet 4.6** | **4.77** | 15.0s | $0.0173 | 563 | 5/5 | 0 |
| **Haiku 4.5** | **4.51** | 6.2s | $0.0053 | 458 | 5/5 | 1 |
| gpt-4o-mini | 2.40 | 5.2s | $0.0006 | 388 | 5/5 | 0 |

## Judge dimension breakdown (consolidated workload)

| Model | rank_and_commit | no_glazing | ranks_not_trashes | follow_up_quality | calibrated_depth | transitional_correctness | claim_support |
|---|---|---|---|---|---|---|---|
| Sonnet 4.6 | 5.00 | 5.00 | 5.00 | 4.25 | 5.00 | 3.75 | 5.00 |
| Haiku 4.5 | 4.60 | 4.80 | 4.60 | 4.20 | 4.20 | 4.40 | 4.40 |
| gpt-4o-mini | 2.60 | 2.20 | 3.60 | 1.80 | 2.40 | 3.00 | 4.20 |

## Key findings

1. **Consolidation itself is viable on both Claude models.** Quality drop from folding
   consensus + descriptions into the blog call is negligible: Sonnet −0.06, Haiku −0.05.
   Both models returned complete consensus (top-3) and descriptions (every product)
   objects in every parseable output.

2. **Sonnet wins quality in both modes** (+0.25 over Haiku consolidated, +0.26 baseline).
   Where it wins: perfect rank_and_commit / no_glazing / claim_support. Where it loses:
   transitional_correctness (3.75 vs Haiku's 4.40 — it over-emits the transitional
   sentence) and it leaked 2 banned phrases ("Unlock", "Experience the") on the Kyoto case.

3. **Sonnet has a JSON reliability problem via OpenRouter.** 1/5 consolidated outputs was
   unparseable: it wrapped the JSON in markdown fences AND left an unescaped `"` inside a
   string (`MacBook Air M4 13".`). Anthropic models have no native json_object mode —
   OpenRouter just passes the instruction through. Haiku was 10/10 parse-clean across both
   runs. **Step 4 (prose/JSON decouple) eliminates this risk class entirely**; until then,
   Sonnet in production would need a retry-on-parse-failure path.

4. **The latency/cost tradeoff is stark:**
   - Haiku consolidated: 12.0s, $0.0079 — vs today's Haiku fan-out (blog + 3×consensus +
     descriptions + voice pass ≈ $0.015, ~11-12s wall-clock incl. the voice-pass round-trip):
     **consolidation halves cost at equal latency and equal quality (4.46 vs 4.51).**
   - Sonnet consolidated: 26.2s, $0.0251 — **+14s slower and 3.2× the cost** of Haiku
     consolidated, for +0.25 judge quality.

5. **gpt-4o-mini is disqualified as the prose writer** (2.83/2.40 — parallel-survey prose,
   generic follow-ups, glazing). It remains fine as the CI fallback path.

## Cost at volume (consolidated, per 1,000 responses)

| Model | Cost / 1k responses |
|---|---:|
| Sonnet 4.6 | ~$25.10 |
| Haiku 4.5 | ~$7.90 |
| gpt-4o-mini | ~$0.80 |

## Recommendation

Proceed with Tier 3 consolidation regardless of model choice — it's quality-neutral and
cost-positive. Model choice is a product call:

- **Haiku 4.5** (keep current): equal quality to today's prod, half the cost, no latency
  regression, 100% parse reliability.
- **Sonnet 4.6** (upgrade): +0.25 judge quality (visibly better prose commitment), but
  +14s per response, 3.2× cost, and requires the Step-4 decouple (or a retry path) to be
  parse-safe.

Raw reports: `eval/results/2026-06-03_092310.{md,csv}` (consolidated),
`eval/results/2026-06-03_092433.{md,csv}` (baseline) — gitignored, kept locally.
