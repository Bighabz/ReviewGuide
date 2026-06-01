"""LLM-judge rubric for the voice model bake-off.

This module only builds judge prompts and parses judge responses — all
network I/O lives in voice_eval.py so there is exactly one client.

The judge scores blind: it never sees which model produced an output, so
brand bias can't leak into the scores.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .fixtures import GoldenCase


# Default judge model (OpenRouter slug). Overridable via --judge-model.
DEFAULT_JUDGE_MODEL = "anthropic/claude-sonnet-4.6"


# Scoring dimensions, in report order. Keys are CSV column names.
JUDGE_DIMENSIONS: Dict[str, str] = {
    "rank_and_commit": (
        "Commits to a ranked #1 and #2 pick with a reason WHY the #1 wins for the "
        "default buyer — versus a parallel survey where every product gets equal praise. "
        "(For pure-taste questions where ranking would be wrong, score 5 if it correctly "
        "declines to rank.)"
    ),
    "no_glazing": (
        "No empty affirmation, no reflexive agreement, no 'great choice!' energy. "
        "Agreement only where it is earned by the substance."
    ),
    "ranks_not_trashes": (
        "Nothing is called 'bad' — alternatives are positioned by who they fit. "
        "Real downsides are surfaced honestly, without manufactured balance."
    ),
    "follow_up_quality": (
        "The follow_up_question is exactly one question, references something specific "
        "from the body or the user's situation, and opens the next turn. Generic offers "
        "('anything else?') score 1."
    ),
    "calibrated_depth": (
        "Depth matches the user's apparent expertise and the purchase weight. No "
        "condescension, no fact-dump, no padding."
    ),
    "transitional_correctness": (
        "The transitional_reasoning field follows its rules: emitted as exactly one "
        "compressed sentence when the conversation carries a real constraint (budget, "
        "use case, must-have); an empty string when there is no constraint to frame. "
        "Never restates the question, never lists options."
    ),
}


# tone.md "Quick-reference rules card" (tone.md:336) — embedded so the judge
# scores against the same gospel the prompt was written from.
RULES_CARD = """\
1. Opinionated about fit, not about products.
2. Rank, don't trash.
3. No glazing. No empty affirmation.
4. Earn agreement when it's earned.
5. Every response ends with a curious question.
6. Strong opinions on substance, humility on taste.
7. Learn the user; don't learn to agree with them.
8. No source citations. Synthesize.
9. Loading copy is curious and ambiguous."""


def build_judge_messages(case: "GoldenCase", output: dict) -> List[dict]:
    """Build the (system, user) messages for one judge call.

    Args:
        case: The golden case the output was generated for.
        output: The candidate's parsed JSON output. Expected keys: ``body``,
            ``follow_up_question``, ``transitional_reasoning``. Missing keys
            are shown to the judge as "(MISSING)" so structural failures cost
            score instead of crashing the judge.

    Returns:
        Messages list ready for an OpenAI-compatible chat completion call.
    """
    dimensions_block = "\n".join(
        f"- {key}: {desc}" for key, desc in JUDGE_DIMENSIONS.items()
    )
    expectations_block = "\n".join(f"- {e}" for e in case.expectations)

    if case.expects_transitional is True:
        transitional_note = "For this case, transitional_reasoning SHOULD be emitted (the query carries a real constraint)."
    elif case.expects_transitional is False:
        transitional_note = "For this case, transitional_reasoning should be an EMPTY string (no real constraint to frame)."
    else:
        transitional_note = "For this case, either emitting or omitting transitional_reasoning can be correct — judge the execution."

    system = f"""You are an exacting editorial reviewer for ReviewGuide.ai, a product
recommendation service whose entire moat is its voice: a senior product
editor who commits to picks, never glazes, ranks by fit, and ends every
response with one curious, specific question.

The voice rules card:

{RULES_CARD}

You will be shown one anonymous candidate response (you do not know which
model wrote it). Score it 1-5 on each dimension below. Be harsh: 5 means
"could ship as-is", 3 means "competent but generic", 1 means "violates the
rule outright". Do not give credit for length or politeness.

Dimensions:

{dimensions_block}

Return ONLY a JSON object of this exact shape (no markdown fences):

{{
  "scores": {{
    "<dimension_key>": {{"score": <1-5 integer>, "rationale": "<one sentence>"}},
    ...one entry per dimension...
  }}
}}"""

    body = output.get("body") or "(MISSING)"
    follow_up = output.get("follow_up_question")
    follow_up = follow_up if follow_up is not None else "(MISSING)"
    transitional = output.get("transitional_reasoning")
    transitional = transitional if transitional is not None else "(MISSING)"

    user = f"""## The user's query

{case.user_message}

## What a strong response must do for this case

{expectations_block}

{transitional_note}

## Candidate response

### body
{body}

### follow_up_question
{follow_up}

### transitional_reasoning
{transitional!r}

Score every dimension. Return only the JSON object."""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def parse_judge_response(text: str) -> Optional[Dict[str, dict]]:
    """Parse the judge's JSON response into ``{dimension: {score, rationale}}``.

    Returns None if the response can't be parsed or is structurally wrong —
    callers record that as a judge failure rather than crashing the run.
    """
    try:
        # Tolerate accidental markdown fences.
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[len("json"):]
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, IndexError):
        return None

    scores = parsed.get("scores")
    if not isinstance(scores, dict):
        return None

    result: Dict[str, dict] = {}
    for key in JUDGE_DIMENSIONS:
        entry = scores.get(key)
        if not isinstance(entry, dict) or not isinstance(entry.get("score"), (int, float)):
            return None
        score = max(1, min(5, int(entry["score"])))
        result[key] = {"score": score, "rationale": str(entry.get("rationale", ""))}
    return result


def mean_judge_score(scores: Dict[str, dict]) -> float:
    """Mean across all dimensions, for the ranked summary table."""
    return sum(s["score"] for s in scores.values()) / len(scores)
