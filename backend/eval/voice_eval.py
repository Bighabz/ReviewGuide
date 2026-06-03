"""Voice model bake-off runner.

Same prompt, swap the model: runs the production blog_article prompt against
a matrix of candidate models via OpenRouter, scores every output with the
production voice-compliance checks plus an LLM judge, and writes a ranked
report so the winning model can be chosen from data instead of vibes.

Usage (from backend/):

    python -m eval.voice_eval --dry-run          # assemble prompts, no API calls
    python -m eval.voice_eval                    # full bake-off (needs OPENROUTER_API_KEY)
    python -m eval.voice_eval --models openai/gpt-4o-mini,anthropic/claude-sonnet-4.6
    python -m eval.voice_eval --cases earbuds_under_100 --no-judge

The OPENROUTER_API_KEY is read from the environment (or backend/.env) and is
never logged or written to results files.

This is a dev-only tool: nothing in the live request path imports it.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# Make `app.` imports resolve whether invoked as `python -m eval.voice_eval`
# (from backend/) or as a script from anywhere.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.services.prompts.voice import build_system_prompt  # noqa: E402
from app.services.prompts.voice_compliance import (  # noqa: E402
    check_follow_up_specificity,
    check_voice_compliance,
)

try:  # package import (python -m eval.voice_eval)
    from .fixtures import CASES_BY_ID, GOLDEN_CASES, GoldenCase
    from .judge import (
        DEFAULT_JUDGE_MODEL,
        JUDGE_DIMENSIONS,
        build_judge_messages,
        mean_judge_score,
        parse_judge_response,
    )
except ImportError:  # script import (python eval/voice_eval.py)
    from fixtures import CASES_BY_ID, GOLDEN_CASES, GoldenCase  # type: ignore
    from judge import (  # type: ignore
        DEFAULT_JUDGE_MODEL,
        JUDGE_DIMENSIONS,
        build_judge_messages,
        mean_judge_score,
        parse_judge_response,
    )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
API_KEY_ENV = "OPENROUTER_API_KEY"

# Candidate models (OpenRouter slugs). Edit here or override with --models.
# Unknown slugs are reported and skipped at startup, not fatal.
MODEL_MATRIX: List[str] = [
    "openai/gpt-4o-mini",            # current production floor / control
    "anthropic/claude-sonnet-4.6",   # workhorse candidate
    "anthropic/claude-haiku-4.5",    # the fair retest
    "openai/gpt-oss-120b",           # structured-path candidate
    "deepseek/deepseek-chat",        # cheap-writer candidate
    "google/gemini-2.5-flash",       # cheap-writer candidate
]

# Production call parameters — mirror the blog_article call in
# backend/mcp_server/tools/product_compose.py (model_service.generate_compose).
GENERATION_TEMPERATURE = 0.7
GENERATION_MAX_TOKENS = 700

# Body word cap enforced by the prompt's BODY RULES.
BODY_WORD_CAP = 400

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Concurrent in-flight requests (per OpenRouter key).
MAX_CONCURRENCY = 4


# Copied verbatim from backend/mcp_server/tools/product_compose.py blog_role
# (the blog_article composer call) — keep in sync. test_eval_smoke.py asserts
# this stays identical to the production string.
BLOG_ROLE = """Write a buying guide for ReviewGuide.ai.

OUTPUT FORMAT — return a JSON object with these string fields:
{
  "body": "<3-5 paragraphs of markdown, no per-product headings>",
  "follow_up_question": "<exactly one contextual curious question that references something specific from the body — a product name, a tradeoff just mentioned, or the user's stated situation>",
  "transitional_reasoning": "<OPTIONAL — exactly one short sentence, OR an empty string. See TRANSITIONAL RULES.>",
  "top_pick": "<the EXACT product name of your #1 pick, copied verbatim from the product list — the same product your body names first>"
}

RANK AND COMMIT (load-bearing — read first):

You are an editor with a take, not a balanced surveyor. Every buying guide
has a #1 pick and a #2 pick. Name them, in order, and explain WHY one beats
the other for the default buyer in this category. The runner-up isn't "also
great" — it is the right pick for a specific person whose situation differs
from the default.

DO NOT write parallel descriptions where every product gets one paragraph of
praise. That reads like SEO content, not editor judgment.

  BAD (parallel survey — do not write like this):
    "The Anker Soundcore Life P3 is praised for its active noise cancellation
    and customizable sound. The JBL TUNE 125TWS is noted for its deep bass
    and user-friendly controls. Both are solid options under $100."

  GOOD (ranked, with fit-based reasoning):
    "For most people under $100, the Anker Soundcore Life P3 is the pick —
    the ANC actually works on a subway, and the case is small enough to
    pocket. The JBL TUNE 125TWS edges it out only if you want louder bass
    and don't care about noise cancellation. Skip the rest at this price."

BODY RULES:
- Paragraph 1: what the user is looking for and what matters most in this category
- Paragraphs 2-3: name the #1 pick first with WHY, then the #2 pick with WHO IT FITS — speak in your own voice, do not name-check review outlets or "reviewers" as a group
- Paragraph 4: what to skip and why, or one real tradeoff worth knowing about the top pick
- Final paragraph: short verdict — who should buy the #1, who should buy the #2
- DO NOT write per-product ## headings — products render as interactive cards below your text
- DO NOT include product images, prices, or buy links — they render in the cards
- NEVER invent features, specs, or URLs
- NEVER mention personal details unless the user provided them
- Keep the body under 400 words total

FOLLOW-UP RULES:
- Exactly one question, returned in the follow_up_question field
- Must reference something specific from the body (a product, a tradeoff, the user's situation)
- Must NOT be a generic offer ("Anything else?", "Want to dig deeper?", "How can I help?")
- Must NOT be a bulleted list of multiple questions — just one single question

TRANSITIONAL RULES (transitional_reasoning field):
- This is a single, compressed-consensus sentence shown BEFORE the guide as a brief
  aside that frames HOW the user's key constraint shapes the pick. Emit it whenever the
  conversation carries a meaningful constraint — a budget, a use case, a must-have, or a
  deal-breaker — that drives which products lead the ranking. This INCLUDES the first
  turn when the query itself names such a constraint (e.g. "under $100", "for small
  ears", "best for travel", "quiet for an office").
- ALSO emit it when the user's latest message added or changed a constraint that flips
  the ranking from a prior shortlist.
- Voice (one sentence, no preamble, no generic filler):
    "$X puts the [tier] on the table — that changes the pick for [situation]."
    "Once comfort matters more than ANC, the order flips."
    "Under $100, value beats flagship features, so the pick leans practical."
- Return an EMPTY STRING "" ONLY when there is no real constraint to frame: bare
  greetings, intros, or vague "what's good?" queries with no budget / use case /
  must-have. When the query carries a genuine constraint, prefer to frame it rather
  than skip it.
- Never restate the question back; never list options; never exceed one sentence."""


# ---------------------------------------------------------------------------
# Consolidated single-call mode (Tier 3 prototype)
# ---------------------------------------------------------------------------
# Production today fans out one blog_article call + up to 3 review-consensus
# calls + one descriptions call per response. The consolidation plan (Tier 3a)
# folds all of that into the blog call's JSON schema. This mode measures
# whether a candidate model can carry that full single-call workload — bigger
# output, more fields — without the prose quality dropping.
#
# BLOG_ROLE itself is never modified: it stays byte-identical to production
# (test_blog_role_in_sync_with_production). The consolidated role is BLOG_ROLE
# with an extended OUTPUT FORMAT plus two extra rules sections that mirror the
# production consensus_role and desc_system prompts in product_compose.py.

_BLOG_SCHEMA_TAIL = '''  "top_pick": "<the EXACT product name of your #1 pick, copied verbatim from the product list — the same product your body names first>"
}'''

_CONSOLIDATED_SCHEMA_TAIL = '''  "top_pick": "<the EXACT product name of your #1 pick, copied verbatim from the product list — the same product your body names first>",
  "consensus": {"<product name>": "<3-5 sentence review consensus summary>", "...": "..."},
  "descriptions": {"<product name>": "<15-25 word factual description>", "...": "..."}
}'''

_CONSOLIDATED_EXTRA_RULES = """

CONSENSUS RULES (consensus field):
- One entry for EACH of the top 3 products in your ranking (all products if fewer than 3)
- Keys are the EXACT product names copied verbatim from the product list
- Each value: a 3-5 sentence summary covering (1) what reviewers consistently praise,
  (2) any notable criticisms or caveats, and (3) who this product is best suited for,
  ending with a sentence describing the ideal buyer
- Do NOT describe your process or mention how many sources were searched

DESCRIPTIONS RULES (descriptions field):
- One entry for EVERY product in the product list
- Keys are the EXACT product names copied verbatim from the product list
- Each value: a factual 15-25 word description — key features, best use case, who it's ideal for
- NEVER invent or assume personal details; write objectively about the product's strengths
- Vary the descriptions — don't repeat the same sentence pattern"""

CONSOLIDATED_ROLE = BLOG_ROLE.replace(_BLOG_SCHEMA_TAIL, _CONSOLIDATED_SCHEMA_TAIL) + _CONSOLIDATED_EXTRA_RULES

# Output budget for the consolidated call (handoff: blog 700 → ~1400 consolidated).
CONSOLIDATED_MAX_TOKENS = 1400


def count_case_products(case: GoldenCase) -> int:
    """Number of products in a case's blog_data payload."""
    return sum(1 for line in case.blog_data.splitlines() if line.startswith("Product:"))


# ---------------------------------------------------------------------------
# Prompt assembly (faithful to production)
# ---------------------------------------------------------------------------

def assemble_messages(case: GoldenCase, ungrounded: bool = False, consolidated: bool = False) -> List[dict]:
    """Build the (system, user) messages production sends for blog_article.

    When ``ungrounded`` is True, the product/review evidence is stripped from the
    user message — only the "User asked: ..." line remains — so the writer must
    rely on parametric knowledge. The judge still scores claim_support against the
    full evidence (case.blog_data), so the grounded-vs-ungrounded delta on that
    dimension measures how much real evidence improves claim accuracy (A1's premise).

    When ``consolidated`` is True, the role prompt is the Tier-3 single-call
    prototype (blog + consensus + descriptions in one response).
    """
    user_content = case.blog_data
    if ungrounded:
        user_content = case.blog_data.splitlines()[0]  # just the 'User asked: "..."' line
    role = CONSOLIDATED_ROLE if consolidated else BLOG_ROLE
    return [
        {"role": "system", "content": build_system_prompt(role_prompt=role, kind="response")},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Deterministic scoring (reuses production compliance code)
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = ["body", "follow_up_question", "transitional_reasoning"]


@dataclass
class DeterministicResult:
    json_ok: bool
    missing_fields: List[str] = field(default_factory=list)
    voice_violations: List[str] = field(default_factory=list)
    generic_follow_up: Optional[str] = None
    body_word_count: int = 0
    over_word_cap: bool = False
    # Consolidated-mode structure checks (None = mode not active)
    consensus_count: Optional[int] = None
    consensus_complete: Optional[bool] = None
    descriptions_count: Optional[int] = None
    descriptions_complete: Optional[bool] = None


def parse_output(raw_text: str) -> Optional[dict]:
    """Parse the model's raw completion into the blog JSON payload."""
    cleaned = raw_text.strip()
    # Tolerate markdown fences — production json_object mode forbids them, but
    # some models emit them anyway and we want to score the prose, not the fence.
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[len("json"):]
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def deterministic_checks(
    parsed: Optional[dict],
    consolidated: bool = False,
    n_products: int = 0,
) -> DeterministicResult:
    """Run the production compliance checks against one parsed output.

    In consolidated mode the output must additionally carry well-formed
    ``consensus`` (one entry per top-3 product) and ``descriptions`` (one entry
    per product) objects — the structural contract Tier 3a will rely on.
    """
    required = list(REQUIRED_FIELDS) + (["consensus", "descriptions"] if consolidated else [])
    if parsed is None:
        return DeterministicResult(json_ok=False, missing_fields=required)

    missing = [f for f in required if f not in parsed]
    body = parsed.get("body") or ""
    follow_up = parsed.get("follow_up_question") or ""
    transitional = parsed.get("transitional_reasoning") or ""

    violations = check_voice_compliance(body)
    violations += check_voice_compliance(follow_up)
    violations += check_voice_compliance(transitional)

    word_count = len(body.split())

    result = DeterministicResult(
        json_ok=True,
        missing_fields=missing,
        voice_violations=violations,
        generic_follow_up=check_follow_up_specificity(follow_up),
        body_word_count=word_count,
        over_word_cap=word_count > BODY_WORD_CAP,
    )

    if consolidated:
        consensus = parsed.get("consensus")
        descriptions = parsed.get("descriptions")

        consensus_entries = (
            [v for v in consensus.values() if isinstance(v, str) and v.strip()]
            if isinstance(consensus, dict) else []
        )
        description_entries = (
            [v for v in descriptions.values() if isinstance(v, str) and v.strip()]
            if isinstance(descriptions, dict) else []
        )
        # Voice compliance applies to the new prose surfaces too.
        for text in consensus_entries + description_entries:
            result.voice_violations += check_voice_compliance(text)

        result.consensus_count = len(consensus_entries)
        result.consensus_complete = len(consensus_entries) >= min(3, n_products) if n_products else bool(consensus_entries)
        result.descriptions_count = len(description_entries)
        result.descriptions_complete = len(description_entries) >= n_products if n_products else bool(description_entries)

    return result


# ---------------------------------------------------------------------------
# Generation + judging
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    model: str
    case_id: str
    raw_text: str = ""
    parsed: Optional[dict] = None
    latency_s: float = 0.0
    error: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    checks: DeterministicResult = field(default_factory=lambda: DeterministicResult(json_ok=False))
    judge_scores: Optional[dict] = None
    judge_error: Optional[str] = None
    # Token usage + cost (generation call only; judge overhead is not the model's cost)
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    cost_usd: Optional[float] = None

    @property
    def mean_judge(self) -> Optional[float]:
        return mean_judge_score(self.judge_scores) if self.judge_scores else None


def make_client(api_key: str):
    """Create the OpenRouter client. Imported lazily so --dry-run never needs openai."""
    from openai import AsyncOpenAI

    return AsyncOpenAI(base_url=OPENROUTER_BASE_URL, api_key=api_key)


async def validate_models(models: List[str], api_key: str) -> tuple:
    """Check candidate slugs against OpenRouter's model list and fetch pricing.

    Returns (valid_models, pricing) where pricing maps slug ->
    {"prompt": $/token, "completion": $/token}. Unknown slugs are reported and
    dropped. If the listing call itself fails (network policy, transient error)
    all slugs are kept, pricing comes back empty, and a warning is printed —
    validation is best-effort, not a gate.
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=20.0) as http:
            resp = await http.get(
                f"{OPENROUTER_BASE_URL}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            listing = {m["id"]: m for m in resp.json().get("data", [])}
    except Exception as exc:  # noqa: BLE001 — best-effort validation
        print(f"[warn] Could not validate model slugs against OpenRouter ({type(exc).__name__}); proceeding with all.")
        return models, {}

    valid = [m for m in models if m in listing]
    for m in models:
        if m not in listing:
            print(f"[warn] Model slug not found on OpenRouter, skipping: {m}")

    pricing = {}
    for m in valid:
        p = listing[m].get("pricing") or {}
        try:
            pricing[m] = {
                "prompt": float(p.get("prompt", 0)),
                "completion": float(p.get("completion", 0)),
            }
        except (TypeError, ValueError):
            pass  # pricing missing/non-numeric → cost shows as — for this model
    return valid, pricing


def compute_cost(pricing: dict, model: str, prompt_tokens: Optional[int], completion_tokens: Optional[int]) -> Optional[float]:
    """Dollar cost of one generation, from OpenRouter per-token pricing."""
    rates = pricing.get(model)
    if not rates or prompt_tokens is None or completion_tokens is None:
        return None
    return prompt_tokens * rates["prompt"] + completion_tokens * rates["completion"]


async def call_chat(
    client,
    model: str,
    messages: List[dict],
    json_mode: bool = True,
    max_tokens: int = GENERATION_MAX_TOKENS,
) -> tuple:
    """One chat completion with production parameters. Returns (text, usage)."""
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=GENERATION_TEMPERATURE,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    completion = await client.chat.completions.create(**kwargs)
    return completion.choices[0].message.content or "", getattr(completion, "usage", None)


async def generate_one(
    client,
    model: str,
    case: GoldenCase,
    sem: asyncio.Semaphore,
    ungrounded: bool = False,
    consolidated: bool = False,
    max_tokens: int = GENERATION_MAX_TOKENS,
    pricing: Optional[dict] = None,
) -> CaseResult:
    """Generate one (model × case) output and run deterministic checks."""
    result = CaseResult(model=model, case_id=case.id)
    messages = assemble_messages(case, ungrounded=ungrounded, consolidated=consolidated)
    usage = None

    async with sem:
        start = time.monotonic()
        try:
            result.raw_text, usage = await call_chat(client, model, messages, json_mode=True, max_tokens=max_tokens)
        except Exception as first_exc:  # noqa: BLE001
            # Some models reject response_format; retry once without it so the
            # prose can still be compared (the deviation is recorded).
            try:
                result.raw_text, usage = await call_chat(client, model, messages, json_mode=False, max_tokens=max_tokens)
                result.notes.append("retried without response_format (model rejected json_object mode)")
            except Exception as second_exc:  # noqa: BLE001
                result.error = f"{type(first_exc).__name__}: {first_exc} | retry: {type(second_exc).__name__}: {second_exc}"
                result.latency_s = time.monotonic() - start
                return result
        result.latency_s = time.monotonic() - start

    if usage is not None:
        result.prompt_tokens = getattr(usage, "prompt_tokens", None)
        result.completion_tokens = getattr(usage, "completion_tokens", None)
        result.cost_usd = compute_cost(pricing or {}, model, result.prompt_tokens, result.completion_tokens)

    result.parsed = parse_output(result.raw_text)
    result.checks = deterministic_checks(result.parsed, consolidated=consolidated, n_products=count_case_products(case))
    return result


async def judge_one(client, judge_model: str, case: GoldenCase, result: CaseResult, sem: asyncio.Semaphore) -> None:
    """Judge one generated output (mutates result). Skipped if generation failed."""
    if result.error or result.parsed is None:
        result.judge_error = "skipped (generation failed or unparseable)"
        return

    messages = build_judge_messages(case, result.parsed)
    async with sem:
        try:
            raw, _ = await call_chat(client, judge_model, messages, json_mode=True)
        except Exception as exc:  # noqa: BLE001
            result.judge_error = f"{type(exc).__name__}: {exc}"
            return

    scores = parse_judge_response(raw)
    if scores is None:
        result.judge_error = "judge response unparseable"
    else:
        result.judge_scores = scores


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _fmt(value, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def render_report(
    results: List[CaseResult],
    models: List[str],
    cases: List[GoldenCase],
    judge_model: Optional[str],
    timestamp: str,
    consolidated: bool = False,
    max_tokens: int = GENERATION_MAX_TOKENS,
) -> str:
    """Render the ranked markdown report."""
    by_model = {m: [r for r in results if r.model == m] for m in models}

    # Ranked summary rows
    rows = []
    for model, rs in by_model.items():
        judged = [r.mean_judge for r in rs if r.mean_judge is not None]
        latencies = [r.latency_s for r in rs if not r.error]
        costs = [r.cost_usd for r in rs if r.cost_usd is not None]
        out_tokens = [r.completion_tokens for r in rs if r.completion_tokens is not None]
        rows.append({
            "model": model,
            "mean_judge": statistics.mean(judged) if judged else None,
            "violations": sum(len(r.checks.voice_violations) for r in rs),
            "generic_follow_ups": sum(1 for r in rs if r.checks.generic_follow_up),
            "json_failures": sum(1 for r in rs if not r.checks.json_ok),
            "over_word_cap": sum(1 for r in rs if r.checks.over_word_cap),
            "errors": sum(1 for r in rs if r.error),
            "p50_latency": statistics.median(latencies) if latencies else None,
            "mean_cost": statistics.mean(costs) if costs else None,
            "mean_out_tokens": statistics.mean(out_tokens) if out_tokens else None,
            "consensus_incomplete": sum(1 for r in rs if r.checks.consensus_complete is False),
            "descriptions_incomplete": sum(1 for r in rs if r.checks.descriptions_complete is False),
        })
    # Sort: judged models by score desc, unjudged last
    rows.sort(key=lambda r: (r["mean_judge"] is None, -(r["mean_judge"] or 0)))

    mode_str = "CONSOLIDATED single-call (blog + consensus + descriptions)" if consolidated else "blog-only (production today)"
    lines = [
        f"# Voice bake-off — {timestamp}",
        "",
        f"- **Mode:** {mode_str}",
        f"- **Models:** {', '.join(models)}",
        f"- **Cases:** {', '.join(c.id for c in cases)}",
        f"- **Judge:** {judge_model or 'disabled (--no-judge)'}",
        f"- **Generation params:** temperature={GENERATION_TEMPERATURE}, max_tokens={max_tokens}, json_object mode",
        "",
        "## Ranked summary",
        "",
    ]
    header = (
        "| Rank | Model | Mean judge (1-5) | Voice violations | Generic follow-ups | JSON failures "
        "| Over word cap | Errors | p50 latency (s) | Mean cost ($/resp) | Mean output tokens |"
    )
    separator = "|---|---|---|---|---|---|---|---|---|---|---|"
    if consolidated:
        header += " Incomplete consensus | Incomplete descriptions |"
        separator += "---|---|"
    lines += [header, separator]
    for i, row in enumerate(rows, 1):
        cells = (
            f"| {i} | {row['model']} | {_fmt(row['mean_judge'])} | {row['violations']} | "
            f"{row['generic_follow_ups']} | {row['json_failures']} | {row['over_word_cap']} | "
            f"{row['errors']} | {_fmt(row['p50_latency'])} | {_fmt(row['mean_cost'], 5)} | "
            f"{_fmt(row['mean_out_tokens'], 0)} |"
        )
        if consolidated:
            cells += f" {row['consensus_incomplete']} | {row['descriptions_incomplete']} |"
        lines.append(cells)

    # Per-dimension breakdown (only if judging ran)
    if any(r.judge_scores for r in results):
        lines += [
            "",
            "## Judge dimension breakdown (mean per model)",
            "",
            "| Model | " + " | ".join(JUDGE_DIMENSIONS) + " |",
            "|---|" + "---|" * len(JUDGE_DIMENSIONS),
        ]
        for model in models:
            rs = [r for r in by_model[model] if r.judge_scores]
            if not rs:
                continue
            cells = []
            for dim in JUDGE_DIMENSIONS:
                cells.append(_fmt(statistics.mean(r.judge_scores[dim]["score"] for r in rs)))
            lines.append(f"| {model} | " + " | ".join(cells) + " |")

    # Full samples, grouped by case so prose can be read side by side
    lines += ["", "## Samples by case"]
    for case in cases:
        lines += [
            "",
            f"### {case.name}",
            "",
            f"> **User:** {case.user_message}",
        ]
        for result in (r for r in results if r.case_id == case.id):
            judge_str = f"judge {_fmt(result.mean_judge)}" if result.mean_judge is not None else "unjudged"
            lines += ["", f"#### {result.model} ({judge_str}, {result.latency_s:.1f}s)", ""]

            if result.error:
                lines.append(f"**GENERATION FAILED:** `{result.error}`")
                continue
            if result.parsed is None:
                lines += ["**UNPARSEABLE OUTPUT (raw):**", "", "```", result.raw_text, "```"]
                continue

            transitional = result.parsed.get("transitional_reasoning") or ""
            if transitional:
                lines.append(f"*{transitional}*\n")
            lines.append(result.parsed.get("body") or "(empty body)")
            follow_up = result.parsed.get("follow_up_question") or "(no follow-up)"
            lines += ["", f"**Follow-up:** {follow_up}"]

            # Consolidated-mode extras: consensus + descriptions, collapsed.
            consensus = result.parsed.get("consensus")
            descriptions = result.parsed.get("descriptions")
            if isinstance(consensus, dict) and consensus:
                lines += ["", "<details><summary>Consensus entries</summary>", ""]
                for pname, text in consensus.items():
                    lines.append(f"- **{pname}**: {text}")
                lines += ["", "</details>"]
            if isinstance(descriptions, dict) and descriptions:
                lines += ["", "<details><summary>Descriptions</summary>", ""]
                for pname, text in descriptions.items():
                    lines.append(f"- **{pname}**: {text}")
                lines += ["", "</details>"]

            flags = []
            if result.checks.voice_violations:
                flags.append(f"banned phrases: {result.checks.voice_violations}")
            if result.checks.generic_follow_up:
                flags.append(f"generic follow-up opener: {result.checks.generic_follow_up!r}")
            if result.checks.missing_fields:
                flags.append(f"missing fields: {result.checks.missing_fields}")
            if result.checks.over_word_cap:
                flags.append(f"body over {BODY_WORD_CAP} words ({result.checks.body_word_count})")
            if result.checks.consensus_complete is False:
                flags.append(f"incomplete consensus ({result.checks.consensus_count} entries)")
            if result.checks.descriptions_complete is False:
                flags.append(f"incomplete descriptions ({result.checks.descriptions_count} entries)")
            if result.notes:
                flags += result.notes
            if flags:
                lines += ["", "⚠️ " + " · ".join(flags)]
            if result.judge_scores:
                lines += ["", "<details><summary>Judge rationale</summary>", ""]
                for dim, entry in result.judge_scores.items():
                    lines.append(f"- **{dim}** {entry['score']}/5 — {entry['rationale']}")
                lines += ["", "</details>"]
            if result.judge_error:
                lines += ["", f"*Judge error: {result.judge_error}*"]

    return "\n".join(lines) + "\n"


def write_csv(results: List[CaseResult], path: Path) -> None:
    """Write raw per-(model × case) scores."""
    fieldnames = [
        "model", "case_id", "json_ok", "missing_fields", "voice_violations",
        "generic_follow_up", "body_word_count", "over_word_cap", "latency_s",
        "prompt_tokens", "completion_tokens", "cost_usd",
        "consensus_count", "descriptions_count",
        "error", "notes", *JUDGE_DIMENSIONS, "mean_judge",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {
                "model": r.model,
                "case_id": r.case_id,
                "json_ok": r.checks.json_ok,
                "missing_fields": ";".join(r.checks.missing_fields),
                "voice_violations": ";".join(r.checks.voice_violations),
                "generic_follow_up": r.checks.generic_follow_up or "",
                "body_word_count": r.checks.body_word_count,
                "over_word_cap": r.checks.over_word_cap,
                "latency_s": round(r.latency_s, 2),
                "prompt_tokens": r.prompt_tokens if r.prompt_tokens is not None else "",
                "completion_tokens": r.completion_tokens if r.completion_tokens is not None else "",
                "cost_usd": f"{r.cost_usd:.6f}" if r.cost_usd is not None else "",
                "consensus_count": r.checks.consensus_count if r.checks.consensus_count is not None else "",
                "descriptions_count": r.checks.descriptions_count if r.checks.descriptions_count is not None else "",
                "error": r.error or "",
                "notes": ";".join(r.notes),
                "mean_judge": _fmt(r.mean_judge) if r.mean_judge is not None else "",
            }
            for dim in JUDGE_DIMENSIONS:
                row[dim] = r.judge_scores[dim]["score"] if r.judge_scores else ""
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Cost guard + dry run
# ---------------------------------------------------------------------------

def estimate_and_print_cost(n_models: int, n_cases: int, with_judge: bool) -> None:
    gen_calls = n_models * n_cases
    judge_calls = gen_calls if with_judge else 0
    # Rough: ~2.5k input + 0.7k output tokens per gen; ~1.5k + 0.4k per judge.
    # Even if every call ran on Sonnet pricing (~$3/M in, $15/M out) the total
    # stays well under a dollar at this volume.
    print(f"Planned calls: {gen_calls} generations + {judge_calls} judge calls = {gen_calls + judge_calls} total")
    print("Estimated spend: well under $1 for the default matrix (worst case ~$0.50 if every call ran at Sonnet pricing).")


def dry_run(models: List[str], cases: List[GoldenCase], with_judge: bool, consolidated: bool = False) -> None:
    """Assemble every prompt and print a summary. Zero network calls, no key needed."""
    print("=== DRY RUN — no API calls ===\n")
    if consolidated:
        print("Mode: CONSOLIDATED single-call (blog + consensus + descriptions)\n")
    print(f"Models ({len(models)}): {', '.join(models)}")
    print(f"Cases ({len(cases)}): {', '.join(c.id for c in cases)}\n")

    for case in cases:
        messages = assemble_messages(case, consolidated=consolidated)
        system_len = len(messages[0]["content"])
        user_len = len(messages[1]["content"])
        print(f"--- {case.id} ---")
        print(f"  system prompt: {system_len:,} chars (VOICE_PROMPT + ROLE + blog_role)")
        n_products = sum(1 for line in case.blog_data.splitlines() if line.startswith("Product:"))
        print(f"  user message:  {user_len:,} chars (blog_data, {n_products} products)")
        print(f"  user message preview: {case.blog_data.splitlines()[0]}")
        if with_judge:
            judge_messages = build_judge_messages(case, {
                "body": "(placeholder)", "follow_up_question": "(placeholder)", "transitional_reasoning": "",
            })
            print(f"  judge prompt:  {len(judge_messages[0]['content']) + len(judge_messages[1]['content']):,} chars")
        print()

    estimate_and_print_cost(len(models), len(cases), with_judge)
    print("\nDry run complete. Run without --dry-run (with OPENROUTER_API_KEY set) to execute.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_api_key() -> Optional[str]:
    """Read OPENROUTER_API_KEY from env, falling back to backend/.env."""
    key = os.environ.get(API_KEY_ENV)
    if key:
        return key
    env_file = _BACKEND_DIR / ".env"
    if env_file.exists():
        try:
            from dotenv import dotenv_values

            key = dotenv_values(env_file).get(API_KEY_ENV)
        except ImportError:
            pass
    return key or None


async def run(args: argparse.Namespace) -> int:
    models = [m.strip() for m in args.models.split(",")] if args.models else list(MODEL_MATRIX)
    if args.cases:
        unknown = [c for c in args.cases.split(",") if c.strip() not in CASES_BY_ID]
        if unknown:
            print(f"Unknown case ids: {unknown}. Available: {list(CASES_BY_ID)}")
            return 1
        cases = [CASES_BY_ID[c.strip()] for c in args.cases.split(",")]
    else:
        cases = list(GOLDEN_CASES)

    with_judge = not args.no_judge
    consolidated = bool(getattr(args, "consolidated", False))
    max_tokens = args.max_tokens or (CONSOLIDATED_MAX_TOKENS if consolidated else GENERATION_MAX_TOKENS)

    if args.dry_run:
        dry_run(models, cases, with_judge, consolidated=consolidated)
        return 0

    api_key = load_api_key()
    if not api_key:
        print(f"ERROR: {API_KEY_ENV} is not set (env var or backend/.env). Use --dry-run to test without a key.")
        return 1

    client = make_client(api_key)
    models, pricing = await validate_models(models, api_key)
    if not models:
        print("ERROR: no valid models to run.")
        return 1

    estimate_and_print_cost(len(models), len(cases), with_judge)
    if consolidated:
        print(f"Mode: CONSOLIDATED single-call, max_tokens={max_tokens}")
    print()

    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    # Generate all (model × case) outputs concurrently.
    gen_tasks = [
        generate_one(
            client, model, case, sem,
            ungrounded=args.ungrounded,
            consolidated=consolidated,
            max_tokens=max_tokens,
            pricing=pricing,
        )
        for model in models for case in cases
    ]
    print(f"Generating {len(gen_tasks)} outputs across {len(models)} models...")
    results: List[CaseResult] = list(await asyncio.gather(*gen_tasks))

    failed = [r for r in results if r.error]
    if failed:
        print(f"[warn] {len(failed)} generations failed (recorded in report).")

    # Judge pass.
    judge_model = args.judge_model if with_judge else None
    if with_judge:
        cases_by_id = {c.id: c for c in cases}
        judge_tasks = [judge_one(client, judge_model, cases_by_id[r.case_id], r, sem) for r in results]
        print(f"Judging {len(judge_tasks)} outputs with {judge_model} (blind)...")
        await asyncio.gather(*judge_tasks)

    # Write results.
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    md_path = RESULTS_DIR / f"{timestamp}.md"
    csv_path = RESULTS_DIR / f"{timestamp}.csv"

    md_path.write_text(
        render_report(results, models, cases, judge_model, timestamp, consolidated=consolidated, max_tokens=max_tokens),
        encoding="utf-8",
    )
    write_csv(results, csv_path)

    print(f"\nReport: {md_path}")
    print(f"CSV:    {csv_path}")

    # Print the ranked summary to stdout too.
    judged = [(m, [r.mean_judge for r in results if r.model == m and r.mean_judge is not None]) for m in models]
    ranked = sorted(
        ((m, statistics.mean(scores)) for m, scores in judged if scores),
        key=lambda x: -x[1],
    )
    if ranked:
        print("\nRanking (mean judge score):")
        for i, (model, score) in enumerate(ranked, 1):
            print(f"  {i}. {model}: {score:.2f}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="ReviewGuide voice model bake-off")
    parser.add_argument("--models", help="Comma-separated OpenRouter slugs (default: built-in matrix)")
    parser.add_argument("--cases", help=f"Comma-separated case ids (default: all). Available: {', '.join(CASES_BY_ID)}")
    parser.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL, help=f"Judge model slug (default: {DEFAULT_JUDGE_MODEL})")
    parser.add_argument("--no-judge", action="store_true", help="Deterministic checks only, skip the LLM judge")
    parser.add_argument("--dry-run", action="store_true", help="Assemble prompts and estimate cost without any API calls")
    parser.add_argument("--ungrounded", action="store_true", help="Strip product/review evidence from the writer's input (parametric-only) — for the grounded-vs-ungrounded claim_support A/B")
    parser.add_argument("--consolidated", action="store_true", help="Tier-3 single-call mode: the role also asks for per-product consensus + descriptions (bigger output, default max_tokens 1400)")
    parser.add_argument("--max-tokens", type=int, default=None, help="Override generation max_tokens (default: 700, or 1400 with --consolidated)")
    args = parser.parse_args()

    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
