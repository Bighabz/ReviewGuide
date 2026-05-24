"""Unit tests for voice compliance — banned phrases + follow-up specificity.

These are pure regex tests (no Claude calls). CI integration tests that
actually invoke Claude live in a separate file (test_voice_integration.py)
and run a small set of canonical prompts to verify the deployed prompt
produces compliant output.
"""

from app.services.prompts.voice_compliance import (
    BANNED_PHRASES,
    GENERIC_FOLLOW_UPS,
    check_follow_up_specificity,
    check_voice_compliance,
    sanitize_voice,
)


class TestCheckVoiceCompliance:
    def test_empty_string_is_compliant(self):
        assert check_voice_compliance("") == []

    def test_clean_output_is_compliant(self):
        text = (
            "The QC Ultra is the pick for your situation — better ANC for "
            "plane drone and the case actually fits in a personal item."
        )
        assert check_voice_compliance(text) == []

    def test_great_choice_is_flagged(self):
        assert "Great choice!" in check_voice_compliance("Great choice! Here are some picks.")

    def test_case_insensitive_match(self):
        assert "Great choice!" in check_voice_compliance("great choice! Here are picks.")

    def test_excellent_pick_is_flagged(self):
        assert "Excellent pick!" in check_voice_compliance("Excellent pick! The XM5 is solid.")

    def test_as_an_ai_is_flagged(self):
        assert "As an AI" in check_voice_compliance("As an AI, I can't really know your preferences.")

    def test_im_just_a_language_model_is_flagged(self):
        assert "I'm just a language model" in check_voice_compliance(
            "I'm just a language model, so take this with a grain of salt."
        )

    def test_it_really_depends_is_flagged(self):
        assert "It really depends on your needs" in check_voice_compliance(
            "It really depends on your needs and use case."
        )

    def test_take_your_to_the_next_level_is_flagged(self):
        violations = check_voice_compliance("Take your audio to the next level with these.")
        assert "Take your [X] to the next level" in violations

    def test_take_your_time_is_NOT_flagged(self):
        # The split phrase must not false-flag innocent uses of "take your".
        assert check_voice_compliance("Take your time deciding.") == []

    def test_multiple_violations_all_returned(self):
        text = "Great choice! As an AI, I can't really know — it really depends on your needs."
        violations = check_voice_compliance(text)
        assert "Great choice!" in violations
        assert "As an AI" in violations
        assert "It really depends on your needs" in violations

    def test_marketing_verb_unlock_is_flagged(self):
        assert "Unlock" in check_voice_compliance("Unlock new possibilities with the XM5.")

    def test_marketing_verb_elevate_is_flagged(self):
        assert "Elevate" in check_voice_compliance("Elevate your morning commute.")

    def test_marketing_verb_empower_is_flagged(self):
        assert "Empower" in check_voice_compliance("Empower your workflow.")


class TestCheckFollowUpSpecificity:
    def test_contextual_question_passes(self):
        result = check_follow_up_specificity(
            "Want me to factor in glasses fit, or are you contact-lens-only?"
        )
        assert result is None

    def test_anything_else_is_flagged(self):
        assert check_follow_up_specificity("Anything else I can help with?") == "anything else"

    def test_any_other_questions_is_flagged(self):
        assert check_follow_up_specificity("Any other questions?") == "any other questions"

    def test_want_to_dig_deeper_is_flagged(self):
        assert check_follow_up_specificity("Want to dig deeper into the specs?") == "want to dig deeper"

    def test_how_can_i_help_is_flagged(self):
        assert check_follow_up_specificity("How can I help further?") == "how can i help"

    def test_let_me_know_if_is_flagged(self):
        assert check_follow_up_specificity("Let me know if you need anything.") == "let me know if"

    def test_empty_follow_up_returns_none(self):
        # Empty follow-ups are caught by schema validation upstream;
        # this function returns None to signal "not a generic match".
        assert check_follow_up_specificity("") is None
        assert check_follow_up_specificity("   ") is None

    def test_contextual_question_containing_generic_words_passes(self):
        # The generic openers anchor at the start of the trimmed string,
        # so a longer contextual question that happens to contain "let
        # me know" mid-sentence is NOT falsely flagged.
        contextual = "Are you locked into Apple-ecosystem features?"
        assert check_follow_up_specificity(contextual) is None

    def test_leading_whitespace_does_not_bypass_check(self):
        assert check_follow_up_specificity("  Anything else?  ") == "anything else"

    def test_case_insensitivity(self):
        assert check_follow_up_specificity("ANYTHING ELSE?") == "anything else"


class TestBannedPhrasesAndGenericFollowUpsAreNotEmpty:
    def test_banned_phrases_populated(self):
        assert len(BANNED_PHRASES) > 0

    def test_generic_follow_ups_populated(self):
        assert len(GENERIC_FOLLOW_UPS) > 0


class TestSanitizeVoice:
    def test_empty_string_passes_through(self):
        cleaned, violations = sanitize_voice("")
        assert cleaned == ""
        assert violations == []

    def test_clean_text_unchanged(self):
        text = "The Sony XM5 is the right pick for travel — the case fits in a personal item."
        cleaned, violations = sanitize_voice(text)
        assert cleaned == text
        assert violations == []

    def test_banned_phrase_stripped_inline(self):
        text = "Great choice! The XM5 is solid."
        cleaned, violations = sanitize_voice(text)
        assert "Great choice!" in violations
        assert "Great choice!" not in cleaned
        assert "The XM5 is solid." in cleaned

    def test_multiple_banned_phrases_all_stripped(self):
        text = "Great choice! Unlock your audio. As an AI I think you'll love it."
        cleaned, violations = sanitize_voice(text)
        # All matched banned phrases recorded.
        assert "Great choice!" in violations
        assert "Unlock" in violations
        assert "As an AI" in violations
        # None of the matched phrases survive in the cleaned output.
        for phrase in ("Great choice!", "Unlock", "As an AI"):
            assert phrase not in cleaned

    def test_next_level_pattern_stripped(self):
        text = "Take your morning commute to the next level with these earbuds."
        cleaned, violations = sanitize_voice(text)
        assert "Take your [X] to the next level" in violations
        # The "Take your" literal isn't double-counted.
        assert "Take your" not in violations
        assert "morning commute" not in cleaned or "to the next level" not in cleaned

    def test_trailing_generic_followup_paragraph_stripped(self):
        # Mirrors the production regression: trailing "Want to dig deeper?"
        # paragraph followed by bulleted questions. The whole trailing block
        # must be removed.
        text = (
            "The Anker Life P3 fits a tight budget. The JBL TUNE adds louder bass.\n"
            "\n"
            "Want to dig deeper?\n"
            "\n"
            "* Want to compare them head-to-head?\n"
            "* Looking for budget alternatives under $30?\n"
            "* Interested in seeing what real users say?"
        )
        cleaned, violations = sanitize_voice(text)
        assert any(v.startswith("trailing-generic-block:") for v in violations)
        assert "Want to dig deeper?" not in cleaned
        assert "head-to-head" not in cleaned
        # Body content above the trailing block is preserved.
        assert "Anker Life P3" in cleaned
        assert "JBL TUNE" in cleaned

    def test_trailing_generic_single_question_stripped(self):
        # Single trailing question form (no bullets).
        text = "The XM5 is the right pick for travel.\n\nAnything else?"
        cleaned, violations = sanitize_voice(text)
        assert any(v.startswith("trailing-generic-block:") for v in violations)
        assert "Anything else?" not in cleaned
        assert "The XM5 is the right pick for travel." in cleaned

    def test_contextual_trailing_question_preserved(self):
        # A genuinely contextual final question (the desired voice) must
        # survive the strip pass.
        text = (
            "The QC Ultra edges out the XM5 on plane drone, and the case "
            "fits in a personal item.\n"
            "\n"
            "Where are you flying first?"
        )
        cleaned, violations = sanitize_voice(text)
        assert violations == []
        assert "Where are you flying first?" in cleaned

    def test_pathological_all_generic_returns_original(self):
        # If sanitization would yield empty text (e.g. the entire response
        # was a banned phrase), return the original with violations logged.
        text = "Great choice!"
        cleaned, violations = sanitize_voice(text)
        assert "Great choice!" in violations
        # Original preserved rather than shipping empty text.
        assert cleaned == text

    def test_generic_block_far_from_end_not_stripped(self):
        # The trailing-block detector only looks at the last 5 paragraphs.
        # A "Want to dig deeper?" buried 10 paragraphs back stays put —
        # this is intentional; the strip pass is for trailing artifacts,
        # not for content auditing.
        paragraphs = ["Want to dig deeper?"] + [f"Paragraph {i}." for i in range(10)]
        text = "\n\n".join(paragraphs)
        cleaned, violations = sanitize_voice(text)
        # No trailing-generic-block violation because it's not in the tail.
        assert not any(v.startswith("trailing-generic-block:") for v in violations)
        assert "Want to dig deeper?" in cleaned
