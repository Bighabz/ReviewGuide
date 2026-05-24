"""Unit tests for VOICE_PROMPT content + build_system_prompt() composition.

Verifies the structural contract: VOICE_PROMPT contains the load-bearing
rules; build_system_prompt() composes layers in the right order; profile
omission for new users does not produce an empty placeholder.
"""

from app.services.prompts.voice import VOICE_PROMPT, build_system_prompt


class TestVoicePromptContent:
    def test_prompt_is_non_empty(self):
        assert VOICE_PROMPT
        assert len(VOICE_PROMPT) > 1000

    def test_prompt_names_reviewguide(self):
        assert "ReviewGuide" in VOICE_PROMPT

    def test_prompt_includes_banned_phrases_section(self):
        assert "BANNED PHRASES" in VOICE_PROMPT

    def test_prompt_includes_banned_patterns_section(self):
        assert "BANNED PATTERNS" in VOICE_PROMPT

    def test_prompt_includes_follow_up_rule(self):
        assert "FOLLOW-UP QUESTION RULE" in VOICE_PROMPT
        assert "EXACTLY ONE" in VOICE_PROMPT

    def test_prompt_includes_all_three_examples(self):
        assert "Example 1" in VOICE_PROMPT
        assert "Example 2" in VOICE_PROMPT
        assert "Example 3" in VOICE_PROMPT

    def test_prompt_uses_reviewguide_label_in_examples(self):
        # "ReviewGuide:" is the assistant label in examples; "AI:" or "You:"
        # would be a regression to the older convention.
        assert "ReviewGuide:" in VOICE_PROMPT

    def test_prompt_includes_no_glazing_rule(self):
        assert "No glazing" in VOICE_PROMPT or "no glazing" in VOICE_PROMPT.lower()

    def test_prompt_includes_rank_dont_trash(self):
        assert "Rank" in VOICE_PROMPT

    def test_prompt_includes_competitor_no_citation(self):
        assert "RTINGS" in VOICE_PROMPT
        assert "Wirecutter" in VOICE_PROMPT


class TestBuildSystemPrompt:
    def test_role_only(self):
        result = build_system_prompt(role_prompt="You compose product review responses.")
        assert VOICE_PROMPT in result
        assert "You compose product review responses." in result
        assert "ROLE" in result
        # No optional sections injected.
        assert "ABOUT THIS USER" not in result
        assert "CONVERSATION SO FAR" not in result
        assert "RESEARCH FOR THIS TURN" not in result

    def test_voice_prompt_comes_first(self):
        result = build_system_prompt(role_prompt="Role text here.")
        # Voice prompt opens; role appears later.
        assert result.startswith(VOICE_PROMPT[:50])

    def test_with_profile_inject(self):
        result = build_system_prompt(
            role_prompt="Composer.",
            profile_inject="Enthusiast — comfortable with technical specs.",
        )
        assert "ABOUT THIS USER" in result
        assert "Enthusiast — comfortable with technical specs." in result

    def test_with_history(self):
        result = build_system_prompt(
            role_prompt="Composer.",
            history="User: best earbuds?\nReviewGuide: under $100?",
        )
        assert "CONVERSATION SO FAR" in result
        assert "best earbuds?" in result

    def test_with_tool_outputs(self):
        result = build_system_prompt(
            role_prompt="Composer.",
            tool_outputs="Top 3 products: A, B, C with specs ...",
        )
        assert "RESEARCH FOR THIS TURN" in result
        assert "Top 3 products" in result

    def test_new_user_no_profile_omits_section(self):
        # Passing None — never an empty string — for new users.
        result = build_system_prompt(role_prompt="Composer.", profile_inject=None)
        assert "ABOUT THIS USER" not in result

    def test_empty_string_profile_omits_section(self):
        # Falsy empty string is treated the same as None.
        result = build_system_prompt(role_prompt="Composer.", profile_inject="")
        assert "ABOUT THIS USER" not in result

    def test_section_ordering(self):
        result = build_system_prompt(
            role_prompt="Role.",
            profile_inject="Profile.",
            history="History.",
            tool_outputs="Tools.",
        )
        # Sections must appear in this order: voice, role, profile, history, tools.
        idx_voice = 0  # opens the prompt
        idx_role = result.index("ROLE")
        idx_profile = result.index("ABOUT THIS USER")
        idx_history = result.index("CONVERSATION SO FAR")
        idx_tools = result.index("RESEARCH FOR THIS TURN")
        assert idx_voice < idx_role < idx_profile < idx_history < idx_tools

    def test_default_kind_is_response(self):
        # Without an explicit kind, the full follow-up rule must be present.
        result = build_system_prompt(role_prompt="Composer.")
        assert "FOLLOW-UP QUESTION RULE" in result
        assert "EXACTLY ONE" in result

    def test_snippet_kind_omits_follow_up_rule(self):
        # Snippet variant must remove the literal follow-up rule heading and
        # the "exactly one" wording so a snippet generator doesn't emit a
        # trailing question that collides with sibling snippets.
        result = build_system_prompt(role_prompt="Composer.", kind="snippet")
        assert "FOLLOW-UP QUESTION RULE" not in result
        assert "EXACTLY ONE" not in result
        # And the replacement marker must be present so the model knows why.
        assert "SNIPPET CONTEXT" in result

    def test_snippet_kind_preserves_banned_phrases(self):
        result = build_system_prompt(role_prompt="Composer.", kind="snippet")
        assert "BANNED PHRASES" in result
        # Spot-check a couple of banned phrases survive the slice.
        assert "Great choice!" in result
        assert "As an AI" in result

    def test_snippet_kind_preserves_examples(self):
        # The examples teach the tone and must remain in both variants.
        result = build_system_prompt(role_prompt="Composer.", kind="snippet")
        assert "Example 1" in result
        assert "Example 2" in result
        assert "Example 3" in result
        assert "EXAMPLES — INTERNALIZE THE VOICE" in result
