# Eval Harnesses

Two dev/CI-signal harnesses live here. Nothing in the live request path
imports either of them.

1. **Voice bake-off** (`voice_eval.py`) — compares candidate models on the
   production blog prompt via OpenRouter. See "Voice Model Bake-Off" below.
2. **Clarifier question quality** (`clarifier_eval.py`) — scores the
   production clarifier's generated questions against the curated category
   packs. See "Clarifier Question-Quality Eval" below.

---

# Clarifier Question-Quality Eval (Outcome 10)

For every category in `CATEGORY_QUESTION_PACKS`, runs the **production**
question generation (`ClarifierAgent._generate_followup_questions` — real
prompt assembly, normalization, and pack enforcement) against a live LLM and
scores the output deterministically against the pack.

## Running

From `backend/` (reads `OPENAI_API_KEY` from env or `backend/.env`):

```bash
# Sanity check: assemble all prompts, zero API calls
python -m eval.clarifier_eval --dry-run

# Full eval — one generation per category (~$0.01 total on gpt-4o-mini)
python -m eval.clarifier_eval

# Subset / model override
python -m eval.clarifier_eval --categories laptops,phones,mattresses
python -m eval.clarifier_eval --model gpt-4o

# CI mode: skips cleanly without a key, exits 1 below the pass-rate threshold
python -m eval.clarifier_eval --ci --threshold 0.9
```

Smoke tests (no network):

```bash
pytest eval/test_clarifier_eval_smoke.py
```

## What gets checked (per category)

| Check | Meaning |
|---|---|
| `slots_complete` | One question per missing slot (use_case, features, budget) |
| `order_ok` | use_case leads, budget closes |
| `use_case_options_ok` | Options match the pack exactly |
| `features_options_ok` | Options match the pack exactly |
| `multi_select_ok` | Features multi-select flag matches the pack; use_case/budget never multi-select |
| `budget_brackets_ok` | Budget brackets match the pack (no "Under $50" laptops) |
| `no_fallback_wording` | No "What is the use case?" stubs (means the LLM omitted a slot) |
| `hints_ok` | Deterministic microcopy per question kind |
| `intro_ok` | Intro is contextual, not a production fallback string |

Reports land in `eval/results/<timestamp>_clarifier.md` + `.csv` (gitignored).

## CI

The `clarifier-eval` job in `.github/workflows/voice-integration.yml` runs the
smoke tests plus the live eval as a **non-blocking signal**
(`continue-on-error: true`) — same pattern as the Claude voice job. It skips
cleanly when `OPENAI_API_KEY` isn't configured (fork PRs).

## Keeping it honest

- The scorer's microcopy/ordering expectations are guarded by
  `test_production_enforcement_satisfies_scorer`, which runs the **real**
  production normalization with a mocked sloppy LLM response and asserts the
  scorer passes it clean. If clarifier_agent.py enforcement or the scorer
  drifts, that test fails.
- Generation parameters are production's own (the harness swaps only the
  transport, not the call): `settings.CLARIFIER_MODEL`, temperature 0.3,
  `settings.CLARIFIER_MAX_TOKENS`, JSON object mode.

---

# Voice Model Bake-Off

Same prompt, swap the model. This harness runs the **production** blog_article
prompt (VOICE_PROMPT + `blog_role`) against a matrix of candidate models via
OpenRouter, scores every output, and writes a ranked report — so the model that
writes ReviewGuide's voice gets chosen from data, not vibes.

This is a **dev-only tool**. Nothing in the live request path imports it.

## Setup

One env var, read from the environment or `backend/.env` (never logged, never
written to results):

```bash
OPENROUTER_API_KEY=sk-or-...
```

## Running

From `backend/`:

```bash
# Sanity check: assemble all prompts, estimate cost, make zero API calls
python -m eval.voice_eval --dry-run

# Full bake-off (all models × all cases, then a blind LLM judge pass)
python -m eval.voice_eval

# Subset of models / cases, or skip the judge
python -m eval.voice_eval --models openai/gpt-4o-mini,anthropic/claude-sonnet-4.6
python -m eval.voice_eval --cases earbuds_under_100,airpods_max_pushback
python -m eval.voice_eval --no-judge
```

Smoke tests (no network):

```bash
pytest eval/test_eval_smoke.py
```

## What gets measured

Per (model × case):

1. **Deterministic checks** — the production compliance code, reused directly:
   - `check_voice_compliance` — banned phrases / patterns in the prose
   - `check_follow_up_specificity` — generic follow-up openers
   - JSON-parse success + required fields present
   - Body word count vs the 400-word cap
2. **Blind LLM judge** (default `anthropic/claude-sonnet-4.6`) — scores 1–5 on
   the tone.md dimensions: rank-and-commit, no glazing, ranks-not-trashes,
   follow-up quality, calibrated depth, transitional correctness. The judge
   never sees which model wrote the output.
3. **Latency** — wall-clock per generation.

## Output

`eval/results/<timestamp>.md` — ranked summary table, per-dimension breakdown,
and **all prose samples grouped by case** so outputs can be read side by side.

`eval/results/<timestamp>.csv` — raw scores for spreadsheet analysis.

The `results/` directory is gitignored.

## The cases

Five golden cases drawn from tone.md's canonical examples (`fixtures.py`):

| Case id | Tests |
|---|---|
| `earbuds_under_100` | Fast path; transitional reasoning on a budget constraint |
| `airpods_max_pushback` | The no-glazing test; pushback handling |
| `xm5_vs_qc_looks` | Taste deferral; refuses to fake an opinion |
| `kyoto_hotels_april` | Aspirational long-form prose |
| `need_a_laptop` | Sparse constraints; the follow-up question carries the response |

## Keeping it honest

- `voice_eval.BLOG_ROLE` is a verbatim copy of the production `blog_role` in
  `mcp_server/tools/product_compose.py`. The smoke test
  `test_blog_role_in_sync_with_production` fails if they drift — when it does,
  copy the new production text into `voice_eval.py`.
- Generation parameters (temperature 0.7, max_tokens 700, JSON object mode)
  mirror the production `model_service.generate_compose` call.
- Fixture review snippets carry no review-source names, same as production
  (VOICE_PROMPT forbids citing competitors).

## Adding a model or case

- **Model:** add the OpenRouter slug to `MODEL_MATRIX` in `voice_eval.py` (or
  pass `--models`). Unknown slugs are reported and skipped at startup.
- **Case:** add a `GoldenCase` to `fixtures.py` and register it in
  `GOLDEN_CASES`. Keep `blog_data` in the production format (see the module
  docstring) and give the judge concrete `expectations`.
