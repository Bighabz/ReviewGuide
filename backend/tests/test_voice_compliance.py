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
    sanitize_voice_payload,
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


class TestSanitizeVoiceCitations:
    """Pass 0 — citation patterns (review-site links + attribution phrases).

    These exercise the production-incident patterns: "According to RTINGS",
    "Reviewers from Wirecutter", "Reviewers highlight X", markdown links
    to review-site domains. The known-source whitelist is the firewall
    against product-brand false positives.
    """

    def test_according_to_known_source_stripped(self):
        text = "According to RTINGS, the Anker Life P3 has a balanced sound signature."
        cleaned, violations = sanitize_voice(text)
        assert any(v.startswith("citation:") for v in violations)
        assert "RTINGS" not in cleaned
        assert "According to" not in cleaned
        assert "the Anker Life P3" in cleaned

    def test_according_to_markdown_link_stripped(self):
        text = "According to [RTINGS](https://www.rtings.com/), the Anker Life P3 offers value."
        cleaned, violations = sanitize_voice(text)
        assert "RTINGS" not in cleaned
        assert "rtings.com" not in cleaned
        assert "the Anker Life P3 offers value" in cleaned

    def test_reviewers_from_source_stripped(self):
        text = "Reviewers from Wirecutter commend the JBL for its bass."
        cleaned, violations = sanitize_voice(text)
        assert "Wirecutter" not in cleaned
        assert "Reviewers from" not in cleaned
        assert "commend the JBL for its bass" in cleaned

    def test_reviewers_from_markdown_link_stripped(self):
        # Production-incident shape: Reviewers from [Wirecutter](nyt-url).
        text = (
            "Reviewers from [Wirecutter](https://www.nytimes.com/wirecutter) "
            "commend the JBL for its straightforward controls."
        )
        cleaned, violations = sanitize_voice(text)
        assert "Wirecutter" not in cleaned
        assert "nytimes" not in cleaned
        assert "commend the JBL for its straightforward controls" in cleaned

    def test_source_says_pattern_stripped(self):
        text = "Wirecutter highlights its noise cancellation."
        cleaned, violations = sanitize_voice(text)
        assert "Wirecutter highlights" not in cleaned
        # The trailing object survives ("its noise cancellation.").
        assert "noise cancellation" in cleaned

    def test_source_possessive_review_stripped(self):
        text = "CNET's review of the XM5 is glowing."
        cleaned, violations = sanitize_voice(text)
        assert "CNET" not in cleaned
        assert "review" not in cleaned or "of the XM5 is glowing" in cleaned

    def test_generic_reviewers_pattern_stripped(self):
        text = "Reviewers highlight the Anker Life P3 as a top contender."
        cleaned, violations = sanitize_voice(text)
        assert "Reviewers highlight" not in cleaned
        assert "the Anker Life P3 as a top contender" in cleaned

    def test_generic_critics_praise_stripped(self):
        text = "Critics praise the XM5 for its travel-ready case."
        cleaned, violations = sanitize_voice(text)
        assert "Critics praise" not in cleaned
        assert "the XM5 for its travel-ready case" in cleaned

    def test_markdown_link_to_review_domain_stripped(self):
        # Bare review-site link not in a citation phrase context — caught
        # by the markdown-link fallback pass.
        text = "More detail at [the full review](https://www.theverge.com/review/123)."
        cleaned, violations = sanitize_voice(text)
        assert any(v.startswith("review-link:") for v in violations)
        assert "theverge" not in cleaned.lower()
        assert "[the full review]" not in cleaned

    def test_product_brand_attribution_NOT_stripped(self):
        # Sony / JBL / Anker are product brands, not review sources. The
        # known-source whitelist is the firewall: brand attributions must
        # survive the strip pass.
        text = "Sony highlights ANC capability in its marketing materials."
        cleaned, violations = sanitize_voice(text)
        assert "Sony highlights" in cleaned
        assert not any(v.startswith("citation:") for v in violations)

    def test_per_known_source_stripped(self):
        text = "Per CNET, the JBL has solid controls."
        cleaned, violations = sanitize_voice(text)
        assert "CNET" not in cleaned
        assert "the JBL has solid controls" in cleaned

    def test_per_non_source_preserved(self):
        # "Per" is ambiguous — "per the spec" / "per your request" are
        # not citations. The known-source whitelist gates the strip so
        # those forms survive.
        text = "Per the spec sheet, battery life is 8 hours."
        cleaned, violations = sanitize_voice(text)
        assert "Per the spec sheet" in cleaned

    def test_link_to_non_review_domain_preserved(self):
        # Links to merchant pages / brand sites / unknown domains stay.
        text = "Check the price at [Amazon](https://amazon.com/dp/X)."
        cleaned, violations = sanitize_voice(text)
        assert "Amazon" in cleaned
        assert "amazon.com" in cleaned
        assert not any(v.startswith("review-link:") for v in violations)

    def test_production_incident_verbatim_sanitized(self):
        # Reproduction of the PR #6 post-merge regression text. All three
        # named-source citations must be excised while product names and
        # technical content survive.
        text = (
            "Reviewers highlight the Anker Soundcore Life P3 as a top contender "
            "in this category, praised for its active noise cancellation. "
            "According to [RTINGS](https://www.rtings.com/), the Life P3 offers "
            "a balanced sound signature. Reviewers from [Wirecutter](https://www.nytimes.com/wirecutter) "
            "commend the JBL for its straightforward controls."
        )
        cleaned, violations = sanitize_voice(text)
        # At least 3 citation-class violations recorded.
        citation_violations = [
            v for v in violations
            if v.startswith("citation:") or v.startswith("review-link:")
        ]
        assert len(citation_violations) >= 3, (
            f"expected >=3 citation violations, got {len(citation_violations)}: {citation_violations}"
        )
        # All three named sources gone.
        for name in ("RTINGS", "Wirecutter", "rtings", "wirecutter", "nytimes"):
            assert name not in cleaned, f"{name} survived sanitization: {cleaned!r}"
        # Product names preserved.
        assert "Anker Soundcore Life P3" in cleaned
        assert "JBL" in cleaned
        # Substantive content preserved.
        assert "noise cancellation" in cleaned
        assert "balanced sound signature" in cleaned
        assert "straightforward controls" in cleaned

    def test_normalize_whitespace_after_strip(self):
        # The cleanup pass collapses doubled spaces and orphaned commas
        # left behind by previous strips so the shipped prose isn't
        # visibly jagged.
        text = "According to RTINGS,  the Anker is great."
        cleaned, _ = sanitize_voice(text)
        # No doubled space surviving the cleanup.
        assert "  " not in cleaned
        # No orphaned leading comma on the line.
        assert not cleaned.lstrip().startswith(",")


class TestSanitizeVoiceNumericMarkers:
    """Tests for the A.1 numeric citation marker pattern.

    general_compose.py used to instruct the LLM to emit ``[1]``, ``[2]``
    markers. The instruction was removed in A.1, but the regex pattern
    is defense-in-depth for models that emit the markers from training
    priors anyway.
    """

    def test_numeric_marker_after_word_is_stripped(self):
        text = "The Bose is the pick for travel [1]."
        cleaned, violations = sanitize_voice(text)
        assert "[1]" not in cleaned
        # The strip should leave clean prose, not a dangling space + period.
        assert "Bose" in cleaned and cleaned.rstrip().endswith(".")
        assert violations  # the violation list should be non-empty

    def test_multiple_numeric_markers_stripped(self):
        text = "Good for travel [1] and excellent for calls [2]."
        cleaned, _ = sanitize_voice(text)
        assert "[1]" not in cleaned and "[2]" not in cleaned
        assert "travel" in cleaned and "calls" in cleaned

    def test_double_digit_marker_stripped(self):
        text = "Comfort is the standout [12]."
        cleaned, _ = sanitize_voice(text)
        assert "[12]" not in cleaned

    def test_code_like_bracket_is_not_stripped(self):
        # No space between identifier and bracket — pattern's preceding
        # whitespace anchor ensures this doesn't get falsely consumed.
        text = "Use arr[0] to access the first element."
        cleaned, violations = sanitize_voice(text)
        assert "arr[0]" in cleaned
        # No violation should be reported for the code snippet.
        assert not any("citation:" in v for v in violations)

    def test_bracket_at_sentence_start_is_not_stripped(self):
        # No preceding word char + space, so the pattern doesn't fire.
        # This avoids stripping things like list markers in markdown.
        text = "[1] is the top pick."
        cleaned, _ = sanitize_voice(text)
        assert "[1]" in cleaned


class TestSanitizeVoicePayload:
    """Tests for the A.1 dict/list-aware payload helper.

    The string-only ``sanitize_voice`` gate at ``chat.py:549`` would
    crash if ``result_state['assistant_text']`` arrived as a dict from
    the clarifier-halt path. ``sanitize_voice_payload`` recurses into
    dicts and lists so the gate handles both shapes.
    """

    def test_string_input_matches_sanitize_voice(self):
        text = "According to RTINGS, the Bose is great."
        cleaned, violations = sanitize_voice_payload(text)
        # Same shape and outcome as plain sanitize_voice.
        plain_cleaned, plain_violations = sanitize_voice(text)
        assert cleaned == plain_cleaned
        assert violations == plain_violations

    def test_dict_input_recurses_into_string_values(self):
        # Mirrors the clarifier halt payload shape.
        payload = {
            "intro": "According to RTINGS, the Bose is great.",
            "questions": ["What's your budget?", "Glasses-friendly fit?"],
        }
        cleaned, violations = sanitize_voice_payload(payload)
        assert isinstance(cleaned, dict)
        assert "RTINGS" not in cleaned["intro"]
        assert "Bose" in cleaned["intro"]
        # Untouched leaves stay verbatim.
        assert cleaned["questions"] == payload["questions"]
        # Violation paths are namespaced so the log can pinpoint the leaf.
        assert any(v.startswith("intro:") for v in violations)

    def test_list_input_recurses_into_string_elements(self):
        payload = ["Clean string.", "Per Wirecutter, the Sonos is great."]
        cleaned, violations = sanitize_voice_payload(payload)
        assert isinstance(cleaned, list)
        assert cleaned[0] == "Clean string."
        assert "Wirecutter" not in cleaned[1]
        assert any(v.startswith("[1]:") for v in violations)

    def test_nested_dict_with_list_recurses(self):
        payload = {
            "intro": "Hi there.",
            "followups": [
                "What's your budget?",
                "According to TechRadar, the XM5 has great sound.",
            ],
        }
        cleaned, violations = sanitize_voice_payload(payload)
        assert "TechRadar" not in cleaned["followups"][1]
        # The nested path "followups:[1]:..." is preserved.
        assert any("followups:" in v and "[1]:" in v for v in violations)

    def test_non_text_leaves_pass_through(self):
        payload = {
            "intro": "Plain.",
            "count": 3,
            "active": True,
            "ratio": 0.5,
            "nothing": None,
        }
        cleaned, violations = sanitize_voice_payload(payload)
        assert cleaned == payload
        assert violations == []

    def test_empty_dict_returns_empty(self):
        cleaned, violations = sanitize_voice_payload({})
        assert cleaned == {}
        assert violations == []

    def test_compliant_dict_returns_unchanged(self):
        payload = {
            "intro": "Got it. A few questions:",
            "questions": ["What's your budget?", "Glasses-friendly fit?"],
        }
        cleaned, violations = sanitize_voice_payload(payload)
        assert cleaned == payload
        assert violations == []
