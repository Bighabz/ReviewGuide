"""Clarifier question-quality eval (Outcome 10).

For every category in CATEGORY_QUESTION_PACKS, run the PRODUCTION clarifier
question generation — ``ClarifierAgent._generate_followup_questions``, the real
prompt assembly, LLM call parameters, normalization, and pack enforcement —
against a live LLM, then score the output deterministically against the pack:

  - one question per missing slot (no fallback "What is the use case?" stubs)
  - slot order: use_case first, budget last
  - use_case / features options match the pack exactly
  - multi-select flag matches the pack's features.multi_select
  - budget brackets match the pack
  - deterministic microcopy hints
  - non-generic intro

Usage (from backend/):

    python -m eval.clarifier_eval --dry-run            # assemble prompts, no API calls
    python -m eval.clarifier_eval                      # full eval (needs OPENAI_API_KEY)
    python -m eval.clarifier_eval --categories laptops,phones
    python -m eval.clarifier_eval --ci                 # CI mode: skip cleanly without a key,
                                                       # exit 1 below --threshold pass rate

The OPENAI_API_KEY is read from the environment (or backend/.env) and is never
logged or written to results files. Unlike the voice bake-off (which swaps
models via OpenRouter), this harness measures the production path with the
production model — settings.CLARIFIER_MODEL — because the thing under test is
"what do real users see", not "which model writes best".

This is a dev/CI-signal tool: nothing in the live request path imports it.
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
from typing import Any, Dict, List, Optional

# Make `app.` imports resolve whether invoked as `python -m eval.clarifier_eval`
# (from backend/) or as a script from anywhere.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Settings must initialize to import the agent. These placeholders mirror the
# test-suite pattern (the "test" prefix also keeps gitleaks' generic-api-key
# rule quiet); live runs route LLM calls through a client built from
# load_api_key(), never through these values.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

from app.agents.category_question_packs import CATEGORY_QUESTION_PACKS  # noqa: E402
from app.agents.clarifier_agent import ClarifierAgent  # noqa: E402
from app.core.config import settings  # noqa: E402


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_KEY_ENV = "OPENAI_API_KEY"

# Keys that mean "no real key configured" — the eval skips live calls on these.
PLACEHOLDER_KEYS = {"", "sk-test-placeholder", "test-api-key"}

# The expert-first flow always asks these three, in this order, on a bare
# substantive product query (see clarifier_agent._handle_new_plan).
MISSING_SLOTS = ["use_case", "features", "budget"]

# Deterministic microcopy enforced by _generate_followup_questions normalization.
# test_clarifier_eval_smoke.py::test_production_enforcement_satisfies_scorer
# guards against drift between these copies and clarifier_agent.py.
HINT_MULTI_SELECT = "Select all that apply — or type your own"
HINT_BUDGET = "or type an amount"
HINT_DEFAULT = "or type your own answer"

# Generic intros that mean the LLM response was missing/failed (production fallbacks).
FALLBACK_INTROS = {
    "I need a few more details:",
    "I need a few more details to help you:",
}

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Concurrent in-flight requests.
MAX_CONCURRENCY = 4

# CI pass-rate threshold: fraction of categories that must score clean.
# Pack enforcement is deterministic, so a healthy run is ~100%; the headroom
# absorbs one flaky LLM response (intro quality is the only un-enforced check).
DEFAULT_THRESHOLD = 0.9


# ---------------------------------------------------------------------------
# Cases — one per curated category pack
# ---------------------------------------------------------------------------

@dataclass
class ClarifierCase:
    category: str
    user_message: str
    current_slots: Dict[str, Any]
    missing_slots: List[str]
    pack: Dict[str, Any]


def build_cases() -> List[ClarifierCase]:
    """One case per curated pack: a bare first-turn "best <category>" query.

    current_slots mirrors what production's F6 fast path produces for these
    queries: the noun lands in product_name (not category), and pack matching
    inside _generate_followup_questions resolves it from there.
    """
    cases = []
    for key, pack in CATEGORY_QUESTION_PACKS.items():
        cases.append(ClarifierCase(
            category=key,
            user_message=f"best {key}",
            current_slots={"product_name": key},
            missing_slots=list(MISSING_SLOTS),
            pack=pack,
        ))
    return cases


CASES_BY_CATEGORY: Dict[str, ClarifierCase] = {c.category: c for c in build_cases()}


# ---------------------------------------------------------------------------
# Deterministic scoring against the pack
# ---------------------------------------------------------------------------

CHECKS = [
    "slots_complete",
    "order_ok",
    "use_case_options_ok",
    "features_options_ok",
    "multi_select_ok",
    "budget_brackets_ok",
    "no_fallback_wording",
    "hints_ok",
    "intro_ok",
]


@dataclass
class ClarifierScore:
    category: str
    failures: Dict[str, str] = field(default_factory=dict)  # check name -> reason
    latency_s: float = 0.0
    error: Optional[str] = None
    n_questions: int = 0

    @property
    def all_passed(self) -> bool:
        return self.error is None and not self.failures

    @property
    def pass_fraction(self) -> float:
        if self.error:
            return 0.0
        return (len(CHECKS) - len(self.failures)) / len(CHECKS)


def _first_for_slot(questions: List[dict], slot: str) -> dict:
    for q in questions:
        if q.get("slot") == slot:
            return q
    return {}


def score_questions(result: Dict[str, Any], case: ClarifierCase) -> ClarifierScore:
    """Score one _generate_followup_questions output against the category pack."""
    score = ClarifierScore(category=case.category)
    pack = case.pack
    questions = result.get("questions", []) or []
    score.n_questions = len(questions)
    slots_in_order = [q.get("slot") for q in questions]

    # 1. Exactly one question per missing slot, no extras and no duplicates.
    if sorted(slots_in_order) != sorted(case.missing_slots):
        score.failures["slots_complete"] = (
            f"expected one question each for {case.missing_slots}, got {slots_in_order}"
        )

    # 2. Order: use_case leads, budget closes.
    if slots_in_order:
        if slots_in_order[0] != "use_case" or slots_in_order[-1] != "budget":
            score.failures["order_ok"] = f"order was {slots_in_order} (want use_case first, budget last)"
    else:
        score.failures["order_ok"] = "no questions returned"

    # 3. use_case options match the pack exactly.
    uc = _first_for_slot(questions, "use_case")
    if uc.get("options") != pack["use_case"]["options"]:
        score.failures["use_case_options_ok"] = (
            f"got {uc.get('options')}, pack says {pack['use_case']['options']}"
        )

    # 4. features options match the pack exactly.
    ft = _first_for_slot(questions, "features")
    if ft.get("options") != pack["features"]["options"]:
        score.failures["features_options_ok"] = (
            f"got {ft.get('options')}, pack says {pack['features']['options']}"
        )

    # 5. Multi-select flag matches the pack; use_case/budget are never multi-select.
    want_multi = bool(pack["features"].get("multi_select"))
    got_multi = ft.get("type") == "multi_select"
    problems = []
    if want_multi != got_multi:
        problems.append(f"features multi_select: got {got_multi}, pack says {want_multi}")
    for slot in ("use_case", "budget"):
        if _first_for_slot(questions, slot).get("type") == "multi_select":
            problems.append(f"{slot} must never be multi_select")
    if problems:
        score.failures["multi_select_ok"] = "; ".join(problems)

    # 6. Budget brackets match the pack exactly.
    bq = _first_for_slot(questions, "budget")
    if bq.get("options") != pack["budget_brackets"]:
        score.failures["budget_brackets_ok"] = (
            f"got {bq.get('options')}, pack says {pack['budget_brackets']}"
        )

    # 7. No fallback stubs — "What is the use case?" means the LLM omitted the
    #    slot (or errored) and production back-filled a placeholder question.
    stubs = []
    for q in questions:
        slot = q.get("slot") or ""
        if (q.get("question") or "").strip().lower() == f"what is the {slot.replace('_', ' ')}?":
            stubs.append(slot)
    if stubs:
        score.failures["no_fallback_wording"] = f"fallback stub questions for: {stubs}"

    # 8. Deterministic microcopy hints (only on questions that carry options).
    bad_hints = []
    for q in questions:
        if not q.get("options"):
            continue
        if q.get("type") == "multi_select":
            want = HINT_MULTI_SELECT
        elif q.get("slot") == "budget":
            want = HINT_BUDGET
        else:
            want = HINT_DEFAULT
        if q.get("free_text_hint") != want:
            bad_hints.append(f"{q.get('slot')}: got {q.get('free_text_hint')!r}, want {want!r}")
    if bad_hints:
        score.failures["hints_ok"] = "; ".join(bad_hints)

    # 9. Intro is present and not a production fallback string.
    intro = (result.get("intro") or "").strip()
    if not intro or intro in FALLBACK_INTROS:
        score.failures["intro_ok"] = f"generic/missing intro: {intro!r}"

    return score


# ---------------------------------------------------------------------------
# Generation via the production agent
# ---------------------------------------------------------------------------

def make_client(api_key: str):
    """Plain AsyncOpenAI client. Imported lazily so --dry-run never needs openai."""
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=api_key)


def make_live_generate(client, model_override: Optional[str], record: dict):
    """Build a replacement for BaseAgent.generate that routes to a plain client.

    The production method passes model/temperature/max_tokens/response_format —
    we forward them verbatim so the call is parameter-identical to production,
    minus the model_service plumbing (Langfuse, retries) that needs app infra.
    """

    async def _generate(
        messages: List[dict],
        model: str = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[dict] = None,
        session_id: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        record["model"] = model_override or model
        record["messages"] = messages
        completion = await client.chat.completions.create(
            model=model_override or model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        return completion.choices[0].message.content or ""

    return _generate


def make_capture_generate(record: dict):
    """Dry-run replacement: capture the prompt, never call the network.

    Returns an empty JSON object so production's parser takes its quiet
    fallback path (stub questions, no error logging) — the dry run only
    reports prompt sizes, so that output is discarded.
    """

    async def _generate(messages: List[dict], model: str = None, **kwargs) -> str:
        record["model"] = model
        record["messages"] = messages
        return "{}"

    return _generate


@dataclass
class CaseRun:
    case: ClarifierCase
    score: ClarifierScore
    result: Dict[str, Any] = field(default_factory=dict)
    model: str = ""


async def run_case(client, model_override: Optional[str], case: ClarifierCase, sem: asyncio.Semaphore) -> CaseRun:
    """Run the production question generation for one category and score it."""
    agent = ClarifierAgent()
    record: dict = {}
    agent.generate = make_live_generate(client, model_override, record)

    async with sem:
        start = time.monotonic()
        result = await agent._generate_followup_questions(
            missing_slots=list(case.missing_slots),
            current_slots=dict(case.current_slots),
            user_message=case.user_message,
            intent="product",
        )
        latency = time.monotonic() - start

    score = score_questions(result, case)
    score.latency_s = latency
    return CaseRun(case=case, score=score, result=result, model=record.get("model", ""))


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def render_report(runs: List[CaseRun], model: str, timestamp: str) -> str:
    """Markdown report: summary table + details for any category that failed."""
    n_clean = sum(1 for r in runs if r.score.all_passed)
    latencies = [r.score.latency_s for r in runs if not r.score.error]

    lines = [
        f"# Clarifier question-quality eval — {timestamp}",
        "",
        f"- **Model:** {model}",
        f"- **Categories:** {len(runs)} (from CATEGORY_QUESTION_PACKS)",
        f"- **Clean pass:** {n_clean}/{len(runs)} ({n_clean / len(runs):.0%})" if runs else "- **Clean pass:** n/a",
        f"- **p50 latency:** {statistics.median(latencies):.1f}s" if latencies else "- **p50 latency:** n/a",
        "",
        "## Summary",
        "",
        "| Category | Result | Failed checks | Latency (s) |",
        "|---|---|---|---|",
    ]
    for r in sorted(runs, key=lambda r: (r.score.all_passed, r.case.category)):
        status = "✅ pass" if r.score.all_passed else ("💥 error" if r.score.error else "❌ fail")
        failed = ", ".join(r.score.failures) if r.score.failures else "—"
        lines.append(f"| {r.case.category} | {status} | {failed} | {r.score.latency_s:.1f} |")

    failed_runs = [r for r in runs if not r.score.all_passed]
    if failed_runs:
        lines += ["", "## Failure details"]
        for r in failed_runs:
            lines += ["", f"### {r.case.category}", ""]
            if r.score.error:
                lines.append(f"**ERROR:** `{r.score.error}`")
                continue
            for check, reason in r.score.failures.items():
                lines.append(f"- **{check}**: {reason}")
            lines += [
                "",
                "<details><summary>Generated questions</summary>",
                "",
                "```json",
                json.dumps(r.result, indent=2, ensure_ascii=False),
                "```",
                "",
                "</details>",
            ]

    return "\n".join(lines) + "\n"


def write_csv(runs: List[CaseRun], path: Path) -> None:
    fieldnames = ["category", "all_passed", *CHECKS, "latency_s", "error"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in runs:
            row = {
                "category": r.case.category,
                "all_passed": r.score.all_passed,
                "latency_s": round(r.score.latency_s, 2),
                "error": r.score.error or "",
            }
            for check in CHECKS:
                row[check] = "fail" if check in r.score.failures else ("" if r.score.error else "pass")
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Dry run
# ---------------------------------------------------------------------------

async def dry_run(cases: List[ClarifierCase]) -> None:
    """Assemble every production prompt and print sizes. Zero network calls."""
    print("=== DRY RUN — no API calls ===\n")
    print(f"Categories ({len(cases)}): {', '.join(c.category for c in cases)}")
    print(f"Production model: {settings.CLARIFIER_MODEL} (temperature 0.3, max_tokens {settings.CLARIFIER_MAX_TOKENS})\n")

    for case in cases:
        agent = ClarifierAgent()
        record: dict = {}
        agent.generate = make_capture_generate(record)
        # Production catches the dry-run exception and returns fallback questions;
        # we only need the captured prompt.
        await agent._generate_followup_questions(
            missing_slots=list(case.missing_slots),
            current_slots=dict(case.current_slots),
            user_message=case.user_message,
            intent="product",
        )
        messages = record.get("messages", [])
        system_len = len(messages[0]["content"]) if messages else 0
        print(f"--- {case.category} ---")
        print(f"  system prompt: {system_len:,} chars (includes curated pack hint)")
        print(f"  pack: use_case {len(case.pack['use_case']['options'])} options, "
              f"features {len(case.pack['features']['options'])} options "
              f"(multi_select={bool(case.pack['features'].get('multi_select'))}), "
              f"{len(case.pack['budget_brackets'])} budget brackets")

    print(f"\nPlanned calls for a live run: {len(cases)} (one per category, ~$0.01 total on gpt-4o-mini).")
    print("Dry run complete. Run without --dry-run (with OPENAI_API_KEY set) to execute.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_api_key() -> Optional[str]:
    """Read OPENAI_API_KEY from env (ignoring placeholders), falling back to backend/.env."""
    key = os.environ.get(API_KEY_ENV, "")
    if key and key not in PLACEHOLDER_KEYS:
        return key
    env_file = _BACKEND_DIR / ".env"
    if env_file.exists():
        try:
            from dotenv import dotenv_values

            key = dotenv_values(env_file).get(API_KEY_ENV, "")
        except ImportError:
            key = ""
    return key if key and key not in PLACEHOLDER_KEYS else None


async def run(args: argparse.Namespace) -> int:
    if args.categories:
        unknown = [c for c in args.categories.split(",") if c.strip() not in CASES_BY_CATEGORY]
        if unknown:
            print(f"Unknown categories: {unknown}. Available: {list(CASES_BY_CATEGORY)}")
            return 1
        cases = [CASES_BY_CATEGORY[c.strip()] for c in args.categories.split(",")]
    else:
        cases = build_cases()

    if args.dry_run:
        await dry_run(cases)
        return 0

    api_key = load_api_key()
    if not api_key:
        if args.ci:
            # CI without the secret (e.g. fork PRs): skip cleanly, never fail the job.
            print(f"SKIPPED: {API_KEY_ENV} not configured — clarifier eval needs a live key. Exiting 0.")
            return 0
        print(f"ERROR: {API_KEY_ENV} is not set (env var or backend/.env). Use --dry-run to test without a key.")
        return 1

    model = args.model or settings.CLARIFIER_MODEL
    client = make_client(api_key)
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    print(f"Running clarifier eval: {len(cases)} categories × 1 generation on {model}...")
    runs: List[CaseRun] = list(await asyncio.gather(*[
        run_case(client, args.model, case, sem) for case in cases
    ]))

    # Write results.
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    md_path = RESULTS_DIR / f"{timestamp}_clarifier.md"
    csv_path = RESULTS_DIR / f"{timestamp}_clarifier.csv"
    md_path.write_text(render_report(runs, model, timestamp), encoding="utf-8")
    write_csv(runs, csv_path)

    # Stdout summary.
    n_clean = sum(1 for r in runs if r.score.all_passed)
    pass_rate = n_clean / len(runs) if runs else 0.0
    print(f"\nClean pass: {n_clean}/{len(runs)} categories ({pass_rate:.0%})")
    for r in runs:
        if not r.score.all_passed:
            detail = r.score.error or ", ".join(r.score.failures)
            print(f"  ❌ {r.case.category}: {detail}")
    print(f"\nReport: {md_path}")
    print(f"CSV:    {csv_path}")

    if args.ci and pass_rate < args.threshold:
        print(f"\nFAIL: pass rate {pass_rate:.0%} is below the --threshold {args.threshold:.0%}")
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="ReviewGuide clarifier question-quality eval")
    parser.add_argument("--categories", help=f"Comma-separated pack keys (default: all). Available: {', '.join(CASES_BY_CATEGORY)}")
    parser.add_argument("--model", help="Override the model (default: settings.CLARIFIER_MODEL — production parity)")
    parser.add_argument("--dry-run", action="store_true", help="Assemble prompts without any API calls")
    parser.add_argument("--ci", action="store_true", help="CI mode: skip cleanly when no API key; exit 1 below --threshold")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help=f"CI pass-rate threshold (default {DEFAULT_THRESHOLD})")
    args = parser.parse_args()

    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
