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
