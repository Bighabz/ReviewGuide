"""Smoke tests for the clarifier question-quality eval (Outcome 10).

Run from backend/:  pytest eval/test_clarifier_eval_smoke.py

These tests make zero network calls — they verify case construction, the
deterministic scorer, and (most importantly) that the scorer stays in sync
with the production pack enforcement in clarifier_agent.py.
"""
import os

os.environ.setdefault("ENV", "test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-characters-long")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-password")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-placeholder")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("LOG_ENABLED", "false")

import json  # noqa: E402
from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402

from app.agents.category_question_packs import CATEGORY_QUESTION_PACKS  # noqa: E402
from app.agents.clarifier_agent import ClarifierAgent  # noqa: E402
from eval.clarifier_eval import (  # noqa: E402
    CASES_BY_CATEGORY,
    CHECKS,
    HINT_BUDGET,
    HINT_DEFAULT,
    HINT_MULTI_SELECT,
    MISSING_SLOTS,
    ClarifierCase,
    build_cases,
    load_api_key,
    score_questions,
)


# ---------------------------------------------------------------------------
# Case construction
# ---------------------------------------------------------------------------

def test_cases_cover_every_pack():
    cases = build_cases()
    assert len(cases) == len(CATEGORY_QUESTION_PACKS)
    assert {c.category for c in cases} == set(CATEGORY_QUESTION_PACKS)


def test_cases_are_first_turn_bare_queries():
    """Cases mirror what production's F6 fast path produces for 'best <category>'."""
    for case in build_cases():
        assert case.user_message == f"best {case.category}"
        assert case.missing_slots == MISSING_SLOTS
        # F6 puts the noun in product_name, not category — pack matching inside
        # _generate_followup_questions resolves it from there.
        assert case.current_slots == {"product_name": case.category}
        assert case.pack is CATEGORY_QUESTION_PACKS[case.category]


# ---------------------------------------------------------------------------
# Scorer on synthetic outputs
# ---------------------------------------------------------------------------

def _perfect_output(case: ClarifierCase) -> dict:
    """Build the output production would emit after enforcement, matching the pack."""
    pack = case.pack
    multi = bool(pack["features"].get("multi_select"))
    features_q = {
        "slot": "features",
        "question": pack["features"]["question"],
        "options": list(pack["features"]["options"]),
        "free_text_hint": HINT_MULTI_SELECT if multi else HINT_DEFAULT,
    }
    if multi:
        features_q["type"] = "multi_select"
    return {
        "intro": f"Happy to help you find the right {case.category} — a couple of quick questions.",
        "questions": [
            {
                "slot": "use_case",
                "question": pack["use_case"]["question"],
                "options": list(pack["use_case"]["options"]),
                "free_text_hint": HINT_DEFAULT,
            },
            features_q,
            {
                "slot": "budget",
                "question": "What's your budget?",
                "options": list(pack["budget_brackets"]),
                "free_text_hint": HINT_BUDGET,
            },
        ],
        "closing": "Then I'll pull together a shortlist.",
    }


def test_perfect_output_scores_clean_for_every_pack():
    for case in build_cases():
        score = score_questions(_perfect_output(case), case)
        assert score.all_passed, f"{case.category}: {score.failures}"
        assert score.pass_fraction == 1.0


def test_wrong_order_flagged():
    case = CASES_BY_CATEGORY["laptops"]
    output = _perfect_output(case)
    output["questions"] = [output["questions"][2], output["questions"][0], output["questions"][1]]
    score = score_questions(output, case)
    assert "order_ok" in score.failures
    assert not score.all_passed


def test_missing_slot_flagged():
    case = CASES_BY_CATEGORY["laptops"]
    output = _perfect_output(case)
    output["questions"] = output["questions"][:2]  # drop budget
    score = score_questions(output, case)
    assert "slots_complete" in score.failures
    assert "budget_brackets_ok" in score.failures


def test_generic_brackets_flagged():
    """'Under $50' for laptops is exactly the failure the packs exist to prevent."""
    case = CASES_BY_CATEGORY["laptops"]
    output = _perfect_output(case)
    output["questions"][2]["options"] = ["Under $50", "$50–$100", "$100+"]
    score = score_questions(output, case)
    assert "budget_brackets_ok" in score.failures


def test_wrong_use_case_options_flagged():
    case = CASES_BY_CATEGORY["mattresses"]
    output = _perfect_output(case)
    output["questions"][0]["options"] = ["Gaming", "Work", "Travel"]  # nonsense for mattresses
    score = score_questions(output, case)
    assert "use_case_options_ok" in score.failures


def test_missing_multi_select_flagged():
    """chairs pack says features is multi_select — output without the flag fails."""
    case = CASES_BY_CATEGORY["chairs"]
    assert case.pack["features"]["multi_select"] is True
    output = _perfect_output(case)
    output["questions"][1].pop("type", None)
    output["questions"][1]["free_text_hint"] = HINT_DEFAULT
    score = score_questions(output, case)
    assert "multi_select_ok" in score.failures


def test_spurious_multi_select_flagged():
    """laptops features is single-select — multi_select flag on it fails; and budget
    must never be multi_select."""
    case = CASES_BY_CATEGORY["laptops"]
    assert not case.pack["features"].get("multi_select")
    output = _perfect_output(case)
    output["questions"][1]["type"] = "multi_select"
    score = score_questions(output, case)
    assert "multi_select_ok" in score.failures

    output2 = _perfect_output(case)
    output2["questions"][2]["type"] = "multi_select"
    score2 = score_questions(output2, case)
    assert "multi_select_ok" in score2.failures


def test_fallback_wording_flagged():
    """'What is the use case?' stubs mean the LLM omitted the slot."""
    case = CASES_BY_CATEGORY["phones"]
    output = _perfect_output(case)
    output["questions"][0]["question"] = "What is the use case?"
    score = score_questions(output, case)
    assert "no_fallback_wording" in score.failures


def test_wrong_hint_flagged():
    case = CASES_BY_CATEGORY["laptops"]
    output = _perfect_output(case)
    output["questions"][2]["free_text_hint"] = "tell me your budget"
    score = score_questions(output, case)
    assert "hints_ok" in score.failures


def test_generic_intro_flagged():
    case = CASES_BY_CATEGORY["laptops"]
    output = _perfect_output(case)
    output["intro"] = "I need a few more details:"
    score = score_questions(output, case)
    assert "intro_ok" in score.failures

    output["intro"] = ""
    score = score_questions(output, case)
    assert "intro_ok" in score.failures


def test_empty_output_fails_everything_relevant():
    case = CASES_BY_CATEGORY["laptops"]
    score = score_questions({"intro": "", "questions": [], "closing": ""}, case)
    assert not score.all_passed
    for check in ("slots_complete", "order_ok", "use_case_options_ok",
                  "features_options_ok", "budget_brackets_ok", "intro_ok"):
        assert check in score.failures, f"expected {check} to fail on empty output"


def test_checks_list_matches_scorer():
    """Every failure key the scorer can emit is declared in CHECKS (report/CSV columns)."""
    case = CASES_BY_CATEGORY["chairs"]
    # Construct a maximally-wrong output to exercise every failure path.
    output = {
        "intro": "I need a few more details:",
        "questions": [
            {"slot": "budget", "question": "What is the budget?",
             "options": ["Under $1"], "free_text_hint": "x", "type": "multi_select"},
            {"slot": "use_case", "question": "What is the use case?",
             "options": ["?"], "free_text_hint": "y", "type": "multi_select"},
        ],
        "closing": "",
    }
    score = score_questions(output, case)
    assert set(score.failures) <= set(CHECKS)
    assert len(score.failures) >= 7


# ---------------------------------------------------------------------------
# Scorer ↔ production-enforcement sync (the drift guard)
# ---------------------------------------------------------------------------

SLOPPY_LLM_RESPONSES = {
    # Wrong order, wrong options, missing multi-select flag, off-script hints —
    # production enforcement must fix ALL of this, and the scorer must agree.
    "chairs": json.dumps({
        "intro": "Let me ask a few quick questions about office chairs.",
        "questions": [
            {"slot": "budget", "question": "What's your budget for the chair?",
             "options": ["Under $50", "$50+"], "free_text_hint": "how much?"},
            {"slot": "use_case", "question": "How long are you sitting per day?",
             "options": ["A while", "All day"], "free_text_hint": "whatever"},
            {"slot": "features", "question": "Which features matter to you?",
             "options": ["Wheels", "Armrests"], "free_text_hint": "hmm"},
        ],
        "closing": "Then I'll find the right chairs for you.",
    }),
    "laptops": json.dumps({
        "intro": "Happy to help with laptops — three quick questions.",
        "questions": [
            {"slot": "use_case", "question": "What will you mainly use it for?",
             "options": ["School", "Games"], "free_text_hint": "or describe it",
             "type": "multi_select"},  # spurious — laptops features/use_case are single-select
            {"slot": "features", "question": "What performance level do you need?",
             "options": ["Fast", "Faster"], "free_text_hint": "or say more"},
            {"slot": "budget", "question": "What's your price range?",
             "options": ["$1", "$2"], "free_text_hint": "or type one"},
        ],
        "closing": "I'll build your shortlist.",
    }),
}


@pytest.mark.asyncio
@pytest.mark.parametrize("category", list(SLOPPY_LLM_RESPONSES))
async def test_production_enforcement_satisfies_scorer(category):
    """Run the REAL _generate_followup_questions with a mocked sloppy LLM response.

    Production pack enforcement (options, multi-select, brackets, hints, ordering)
    must produce output the scorer passes clean. If this fails, either the
    enforcement in clarifier_agent.py regressed, or the scorer's expectations
    (microcopy strings, ordering rules) drifted from production — fix whichever
    side moved.
    """
    agent = ClarifierAgent()
    agent.generate = AsyncMock(return_value=SLOPPY_LLM_RESPONSES[category])

    result = await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"product_name": category},
        user_message=f"best {category}",
        intent="product",
    )

    case = CASES_BY_CATEGORY[category]
    score = score_questions(result, case)
    assert score.all_passed, (
        f"Production enforcement output failed the scorer for {category}: {score.failures}. "
        "Scorer and clarifier_agent.py normalization have drifted."
    )


@pytest.mark.asyncio
async def test_llm_failure_shows_up_as_check_failures():
    """When the LLM call fails, production falls back to stub questions —
    the scorer must flag that as failures, not pass it silently."""
    agent = ClarifierAgent()
    agent.generate = AsyncMock(side_effect=RuntimeError("simulated API failure"))

    result = await agent._generate_followup_questions(
        missing_slots=["use_case", "features", "budget"],
        current_slots={"product_name": "laptops"},
        user_message="best laptops",
        intent="product",
    )

    score = score_questions(result, CASES_BY_CATEGORY["laptops"])
    assert not score.all_passed
    assert "no_fallback_wording" in score.failures


# ---------------------------------------------------------------------------
# API-key handling
# ---------------------------------------------------------------------------

def test_placeholder_key_is_not_a_real_key(monkeypatch):
    """CI fork-PR safety: the test placeholder must never count as a usable key."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-placeholder")
    # Point the .env fallback away from any real backend/.env on the dev machine.
    import eval.clarifier_eval as ce
    monkeypatch.setattr(ce, "_BACKEND_DIR", ce.RESULTS_DIR)  # results/ has no .env
    assert load_api_key() is None
