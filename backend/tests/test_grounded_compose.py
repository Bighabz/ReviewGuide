"""Tests for Tier 2.2/2.3 grounded compose: history/profile helpers and the
build_system_prompt slot assembly the grounded blog wiring depends on."""
from app.services.prompts.voice import build_system_prompt
from mcp_server.tools.product_compose import _format_history, _profile_inject


def test_format_history_formats_recent_turns():
    conv = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
        {"role": "user", "content": "c"},
    ]
    out = _format_history(conv, n=2)
    assert "assistant: b" in out
    assert "user: c" in out
    assert "user: a" not in out  # trimmed to the last 2 turns


def test_format_history_empty_returns_none():
    assert _format_history([]) is None
    assert _format_history(None) is None
    assert _format_history([{"role": "user", "content": ""}]) is None


def test_profile_inject_builds_from_prefs():
    prefs = {"categories": {"headphones": 3, "laptops": 1}, "brands": {"Sony": 2}}
    out = _profile_inject(prefs)
    assert out is not None
    assert out.startswith("Returning user who")
    assert "headphones" in out
    assert "Sony" in out


def test_profile_inject_empty_returns_none():
    assert _profile_inject({}) is None
    assert _profile_inject(None) is None
    assert _profile_inject({"categories": {}, "brands": {}}) is None


def test_grounded_prompt_assembly_surfaces_slots():
    """The grounded wiring relies on build_system_prompt surfacing each slot as a
    labelled section; the user message then carries only the query."""
    system = build_system_prompt(
        role_prompt="ROLE TEXT",
        kind="response",
        profile_inject=_profile_inject({"categories": {"headphones": 1}}),
        history=_format_history([{"role": "user", "content": "best earbuds"}]),
        tool_outputs="Product: X | Rating: 4.5/5 (120 reviews)",
    )
    assert "ABOUT THIS USER" in system
    assert "CONVERSATION SO FAR" in system
    assert "RESEARCH FOR THIS TURN" in system
    assert "Product: X" in system
    assert "headphones" in system


def test_ungrounded_prompt_omits_empty_slots():
    """With no profile/history/research, the optional sections are absent."""
    system = build_system_prompt(role_prompt="ROLE TEXT", kind="response")
    assert "ABOUT THIS USER" not in system
    assert "CONVERSATION SO FAR" not in system
    assert "RESEARCH FOR THIS TURN" not in system


def test_profile_inject_surfaces_richer_signal():
    """Tier 5b: use-cases, budget tier, and favored features (already stored by
    preference_service) now reach the profile, not just categories + brands."""
    prefs = {
        "categories": {"headphones": 3},
        "brands": {"Sony": 2},
        "use_cases": {"travel": 2, "gym": 1},
        "budget_ranges": ["under $200", "under $350"],
        "features": ["noise cancelling", "long battery"],
    }
    out = _profile_inject(prefs)
    assert out is not None
    assert "travel" in out                      # use-case surfaced
    assert "under $350" in out                  # most-recent budget surfaced
    assert "noise cancelling" in out            # feature surfaced
