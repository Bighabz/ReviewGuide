"""Smoke tests for the voice bake-off harness.

Run from backend/:  pytest eval/test_eval_smoke.py

These tests make zero network calls — they verify that prompt assembly,
deterministic scoring, and the prod-sync invariant all hold.
"""

import json
import re
from pathlib import Path

from eval.fixtures import GOLDEN_CASES, CASES_BY_ID
from eval.judge import JUDGE_DIMENSIONS, build_judge_messages, parse_judge_response, mean_judge_score
from eval.voice_eval import (
    BLOG_ROLE,
    CONSOLIDATED_MAX_TOKENS,
    CONSOLIDATED_ROLE,
    GENERATION_MAX_TOKENS,
    assemble_messages,
    compute_cost,
    count_case_products,
    deterministic_checks,
    parse_output,
)

_BACKEND_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Prod-sync invariant
# ---------------------------------------------------------------------------

def test_blog_role_in_sync_with_production():
    """BLOG_ROLE must stay byte-identical to the blog_role string in product_compose.py.

    If this fails, someone edited the production prompt — copy the new text
    into voice_eval.BLOG_ROLE so the bake-off keeps measuring the real prompt.
    """
    source = (_BACKEND_DIR / "mcp_server" / "tools" / "product_compose.py").read_text(encoding="utf-8")
    match = re.search(r'blog_role = """(.*?)"""', source, re.DOTALL)
    assert match, "Could not find blog_role triple-quoted string in product_compose.py"
    assert match.group(1) == BLOG_ROLE, (
        "BLOG_ROLE has drifted from production blog_role in product_compose.py — "
        "copy the production text into eval/voice_eval.py"
    )


def test_prompt_assembly_contains_voice_and_role():
    """The assembled system prompt must layer VOICE_PROMPT first, then the role."""
    from app.services.prompts.voice import VOICE_PROMPT

    for case in GOLDEN_CASES:
        messages = assemble_messages(case)
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        system = messages[0]["content"]
        # Voice comes first, role second — same layering as production.
        assert system.startswith(VOICE_PROMPT[:50])
        assert "RANK AND COMMIT" in system
        assert messages[1]["content"] == case.blog_data


# ---------------------------------------------------------------------------
# Fixtures sanity
# ---------------------------------------------------------------------------

def test_fixtures_are_well_formed():
    assert len(GOLDEN_CASES) == 5
    assert len(CASES_BY_ID) == 5
    for case in GOLDEN_CASES:
        # blog_data mirrors production format: first line quotes the user.
        assert case.blog_data.startswith(f'User asked: "{case.user_message}"')
        # Every case ships product data for the model to synthesize.
        product_lines = [line for line in case.blog_data.splitlines() if line.startswith("Product:")]
        assert len(product_lines) >= 2, f"{case.id} needs at least 2 products"
        assert case.expectations, f"{case.id} needs judge expectations"


def test_fixture_review_snippets_have_no_source_attribution():
    """Production strips review-source names before the LLM sees excerpts —
    fixtures must do the same or models get unfairly tempted to cite."""
    from app.services.prompts.voice_compliance import KNOWN_REVIEW_SOURCES

    for case in GOLDEN_CASES:
        for source_name in KNOWN_REVIEW_SOURCES:
            assert source_name.lower() not in case.blog_data.lower(), (
                f"{case.id} blog_data mentions review source {source_name!r}"
            )


# ---------------------------------------------------------------------------
# Deterministic scoring
# ---------------------------------------------------------------------------

KNOWN_BAD_OUTPUT = json.dumps({
    "body": (
        "Great choice! The Anker Soundcore Life P3 is praised for its active noise "
        "cancellation and customizable sound. The JBL TUNE 125TWS is noted for its "
        "deep bass. Both are solid options that will unlock your listening experience "
        "and take your music to the next level. Ultimately the decision is yours."
    ),
    "follow_up_question": "Anything else I can help you with?",
    "transitional_reasoning": "",
})

KNOWN_GOOD_OUTPUT = json.dumps({
    "body": (
        "Under $100, the pick is the Soundcore Liberty 4 NC. The ANC actually works "
        "on a subway, the app has a real EQ, and 50 hours of total battery means the "
        "chunky case earns its size. The JLab JBuds ANC 3 is the pick instead if your "
        "budget is closer to $60 and most of your listening happens at the gym — the "
        "bass-forward tuning suits workouts better than commutes.\n\n"
        "Skip the Nothing Ear (a) for this budget: they're good earbuds, but at $119 "
        "you're paying $20 over budget mostly for the design.\n\n"
        "Verdict: Liberty 4 NC for commuters and office workers, JBuds ANC 3 if the "
        "gym is the main venue and $60 is the real ceiling."
    ),
    "follow_up_question": "Are these mostly for the commute, or do workouts factor in too?",
    "transitional_reasoning": "Under $100, value beats flagship features, so the pick leans practical.",
})


def test_known_bad_output_flags_violations():
    parsed = parse_output(KNOWN_BAD_OUTPUT)
    checks = deterministic_checks(parsed)

    assert checks.json_ok
    assert not checks.missing_fields
    # "Great choice!", "Unlock", "Take your [X] to the next level", "Ultimately the decision is yours"
    assert len(checks.voice_violations) >= 3
    assert "Great choice!" in checks.voice_violations
    assert checks.generic_follow_up is not None  # "Anything else..." is generic


def test_known_good_output_passes():
    parsed = parse_output(KNOWN_GOOD_OUTPUT)
    checks = deterministic_checks(parsed)

    assert checks.json_ok
    assert not checks.missing_fields
    assert checks.voice_violations == []
    assert checks.generic_follow_up is None
    assert not checks.over_word_cap


def test_unparseable_output_fails_json_check():
    checks = deterministic_checks(parse_output("I'm sorry, I can't produce JSON right now."))
    assert not checks.json_ok
    assert checks.missing_fields == ["body", "follow_up_question", "transitional_reasoning"]


def test_markdown_fenced_json_is_tolerated():
    fenced = f"```json\n{KNOWN_GOOD_OUTPUT}\n```"
    parsed = parse_output(fenced)
    assert parsed is not None
    assert "body" in parsed


# ---------------------------------------------------------------------------
# Judge plumbing
# ---------------------------------------------------------------------------

def test_judge_messages_are_blind_and_complete():
    case = CASES_BY_ID["earbuds_under_100"]
    output = json.loads(KNOWN_GOOD_OUTPUT)
    messages = build_judge_messages(case, output)

    combined = messages[0]["content"] + messages[1]["content"]
    # Blind: no model slugs anywhere in the judge prompt.
    assert "gpt-4o" not in combined
    assert "claude" not in combined.lower()
    # Complete: every dimension and the candidate's text are present.
    for dim in JUDGE_DIMENSIONS:
        assert dim in combined
    assert output["body"] in combined
    assert output["follow_up_question"] in combined


def test_judge_scores_claim_support_against_evidence():
    """The claim_support dimension (Tier 5 / A1) must be scored, and the judge
    must be shown the evidence payload so it can actually verify the claims."""
    case = CASES_BY_ID["earbuds_under_100"]
    output = json.loads(KNOWN_GOOD_OUTPUT)
    messages = build_judge_messages(case, output)
    combined = messages[0]["content"] + messages[1]["content"]

    # The new dimension is in the rubric...
    assert "claim_support" in JUDGE_DIMENSIONS
    assert "claim_support" in combined
    # ...and the writer's evidence is shown so claim_support is verifiable.
    assert case.blog_data in messages[1]["content"]

    # The judge response must carry a claim_support score (parse iterates the rubric).
    fake_response = json.dumps({
        "scores": {dim: {"score": 4, "rationale": "fine"} for dim in JUDGE_DIMENSIONS}
    })
    scores = parse_judge_response(fake_response)
    assert scores is not None
    assert "claim_support" in scores


# ---------------------------------------------------------------------------
# Consolidated single-call mode (Tier 3 prototype)
# ---------------------------------------------------------------------------

def test_consolidated_role_extends_blog_role_without_modifying_it():
    """CONSOLIDATED_ROLE must carry the new schema fields + rules sections, and
    must be a real extension of BLOG_ROLE (the .replace() actually fired) —
    while BLOG_ROLE itself stays untouched (the prod-sync pin covers that)."""
    # New fields are in the consolidated schema...
    assert '"consensus"' in CONSOLIDATED_ROLE
    assert '"descriptions"' in CONSOLIDATED_ROLE
    assert "CONSENSUS RULES" in CONSOLIDATED_ROLE
    assert "DESCRIPTIONS RULES" in CONSOLIDATED_ROLE
    # ...but NOT in the production blog role.
    assert '"consensus"' not in BLOG_ROLE
    assert "CONSENSUS RULES" not in BLOG_ROLE
    # The schema tail replacement fired (top_pick is followed by the new fields,
    # not by the closing brace).
    assert '"top_pick": "<the EXACT product name of your #1 pick, copied verbatim from the product list — the same product your body names first>",' in CONSOLIDATED_ROLE
    # Everything load-bearing from BLOG_ROLE survives in the consolidated role.
    for section in ["RANK AND COMMIT", "BODY RULES", "FOLLOW-UP RULES", "TRANSITIONAL RULES"]:
        assert section in CONSOLIDATED_ROLE
    # Bigger output budget.
    assert CONSOLIDATED_MAX_TOKENS > GENERATION_MAX_TOKENS


def test_consolidated_role_in_sync_with_production():
    """The eval's CONSOLIDATED_ROLE must equal what production builds via
    _consolidated_blog_role(blog_role). product_compose owns the canonical
    transform; this pins the bake-off to it (sibling of the BLOG_ROLE pin)."""
    from mcp_server.tools.product_compose import (
        _consolidated_blog_role,
        _BLOG_SCHEMA_TAIL as PROD_SCHEMA_TAIL,
    )

    # Production's schema-tail constant must actually occur in the production
    # blog_role, or the .replace() is a silent no-op and the new fields vanish.
    source = (_BACKEND_DIR / "mcp_server" / "tools" / "product_compose.py").read_text(encoding="utf-8")
    match = re.search(r'blog_role = """(.*?)"""', source, re.DOTALL)
    assert match, "Could not find blog_role in product_compose.py"
    assert PROD_SCHEMA_TAIL in match.group(1), (
        "_BLOG_SCHEMA_TAIL no longer occurs in production blog_role — the "
        "consolidated .replace() would be a no-op. Update _BLOG_SCHEMA_TAIL."
    )

    # And the eval's consolidated role must be byte-identical to production's.
    assert _consolidated_blog_role(BLOG_ROLE) == CONSOLIDATED_ROLE, (
        "CONSOLIDATED_ROLE has drifted from production's _consolidated_blog_role "
        "transform — update eval/voice_eval.py to match product_compose.py."
    )


def test_consolidated_assembly_uses_consolidated_role():
    case = CASES_BY_ID["earbuds_under_100"]
    normal = assemble_messages(case)
    consolidated = assemble_messages(case, consolidated=True)
    assert "CONSENSUS RULES" not in normal[0]["content"]
    assert "CONSENSUS RULES" in consolidated[0]["content"]
    # User payload identical in both modes — only the role changes.
    assert normal[1]["content"] == consolidated[1]["content"]


def test_count_case_products():
    assert count_case_products(CASES_BY_ID["earbuds_under_100"]) == 4
    assert count_case_products(CASES_BY_ID["xm5_vs_qc_looks"]) == 2


KNOWN_GOOD_CONSOLIDATED_OUTPUT = json.dumps({
    **json.loads(KNOWN_GOOD_OUTPUT),
    "top_pick": "Soundcore Liberty 4 NC",
    "consensus": {
        "Soundcore Liberty 4 NC": "Reviewers consistently praise the ANC and battery life. The case is chunky. Best for commuters who want flagship features under $100.",
        "JLab JBuds ANC 3": "Praised for punchy bass and gym fit. ANC lets voices through. Best for budget gym-goers.",
        "Nothing Ear (a)": "Praised for design and clean sound. Over the $100 budget. Best for design-conscious buyers.",
    },
    "descriptions": {
        "Soundcore Liberty 4 NC": "Effective ANC, 50-hour battery, and real app EQ make it the standout commuter pick under $100.",
        "JLab JBuds ANC 3": "Bass-forward earbuds built for workouts, with decent ANC at a sixty-dollar price.",
        "Nothing Ear (a)": "Transparent design and balanced sound for buyers who care how their earbuds look.",
        "EarFun Air Pro 4": "aptX Lossless and multipoint connectivity at an unexpectedly low price for spec-focused listeners.",
    },
})


def test_consolidated_checks_pass_on_complete_output():
    parsed = parse_output(KNOWN_GOOD_CONSOLIDATED_OUTPUT)
    checks = deterministic_checks(parsed, consolidated=True, n_products=4)

    assert checks.json_ok
    assert not checks.missing_fields
    assert checks.consensus_count == 3
    assert checks.consensus_complete is True
    assert checks.descriptions_count == 4
    assert checks.descriptions_complete is True


def test_consolidated_checks_flag_missing_and_incomplete_fields():
    # Blog-only output run through consolidated checks → consensus/descriptions missing.
    parsed = parse_output(KNOWN_GOOD_OUTPUT)
    checks = deterministic_checks(parsed, consolidated=True, n_products=4)
    assert "consensus" in checks.missing_fields
    assert "descriptions" in checks.missing_fields
    assert checks.consensus_complete is False
    assert checks.descriptions_complete is False

    # Output with too few entries → incomplete, not missing.
    partial = json.loads(KNOWN_GOOD_CONSOLIDATED_OUTPUT)
    partial["consensus"] = {"Soundcore Liberty 4 NC": "Good."}
    partial["descriptions"] = {"Soundcore Liberty 4 NC": "Good earbuds."}
    checks = deterministic_checks(partial, consolidated=True, n_products=4)
    assert not checks.missing_fields
    assert checks.consensus_complete is False
    assert checks.descriptions_complete is False


def test_consolidated_checks_do_not_affect_normal_mode():
    parsed = parse_output(KNOWN_GOOD_OUTPUT)
    checks = deterministic_checks(parsed)
    assert checks.consensus_count is None
    assert checks.consensus_complete is None
    assert checks.descriptions_count is None
    assert checks.descriptions_complete is None


def test_consolidated_checks_catch_banned_phrases_in_new_fields():
    bad = json.loads(KNOWN_GOOD_CONSOLIDATED_OUTPUT)
    bad["consensus"]["Soundcore Liberty 4 NC"] = "Great choice! Reviewers love it."
    checks = deterministic_checks(bad, consolidated=True, n_products=4)
    assert "Great choice!" in checks.voice_violations


# ---------------------------------------------------------------------------
# Cost computation
# ---------------------------------------------------------------------------

def test_compute_cost():
    pricing = {"test/model": {"prompt": 0.000003, "completion": 0.000015}}
    # 1000 prompt + 500 completion tokens → 0.003 + 0.0075 = 0.0105
    assert abs(compute_cost(pricing, "test/model", 1000, 500) - 0.0105) < 1e-9
    # Unknown model or missing usage → None, not a crash.
    assert compute_cost(pricing, "other/model", 1000, 500) is None
    assert compute_cost(pricing, "test/model", None, 500) is None
    assert compute_cost({}, "test/model", 1000, 500) is None


def test_judge_response_parsing_round_trip():
    fake_response = json.dumps({
        "scores": {dim: {"score": 4, "rationale": "fine"} for dim in JUDGE_DIMENSIONS}
    })
    scores = parse_judge_response(fake_response)
    assert scores is not None
    assert mean_judge_score(scores) == 4.0

    # Out-of-range scores are clamped, not rejected.
    fake_response_clamped = json.dumps({
        "scores": {dim: {"score": 9, "rationale": ""} for dim in JUDGE_DIMENSIONS}
    })
    assert mean_judge_score(parse_judge_response(fake_response_clamped)) == 5.0

    # Garbage is rejected, not crashed on.
    assert parse_judge_response("not json at all") is None
    assert parse_judge_response(json.dumps({"scores": {"only_one": {"score": 3}}})) is None
