"""Voice compliance check for generated AI output.

Two enforcement points:

1. check_voice_compliance(text) -> list[str]
   Returns a list of banned phrases found in the text. Used as:
   - Log-and-flag in production (warn + emit to observability; do not
     strip or block the response — silent stripping masks prompt bugs).
   - Block-and-fail in CI integration tests (any non-empty result fails
     the test, catching voice regressions before they ship).

2. check_follow_up_specificity(follow_up: str) -> Optional[str]
   Returns the matched generic pattern if the follow-up question is a
   generic offer rather than a contextual question. Used by schema
   validation before emitting a blog or verdict response.

The canonical banned-phrases list lives here so both the prompt-rendering
side and the compliance-check side reference one source.
"""

from __future__ import annotations

import re
from typing import List, Optional, Pattern


# Canonical literal banned phrases. Mirrors the list in VOICE_PROMPT.
# Tuning happens here; the prompt and the check stay in lockstep.
BANNED_PHRASES: List[str] = [
    "Great choice!",
    "Excellent pick!",
    "You'll love it!",
    "You can't go wrong with",
    "You're going to be so happy with",
    "Great question!",
    "What a great question!",
    "Happy to help!",
    "I'd be glad to",
    "As an AI",
    "I'm just a language model",
    "Ultimately the decision is yours",
    "It really depends on your needs",
    "Everyone's different",
    "Game-changer",
    "Best of the best",
    "Crushing it",
    "Unlock",
    "Elevate",
    "Empower",
    "Experience the",
    "Take your",  # paired with "to the next level" — see _NEXT_LEVEL_PATTERN
]


# Generic follow-up question openers. A follow-up matching any of these
# fails the "exactly one contextual question" rule. Match is case-
# insensitive and anchored at the start of the trimmed string so a
# longer contextual question containing one of these as a substring is
# not falsely flagged.
GENERIC_FOLLOW_UPS: List[str] = [
    "anything else",
    "any other questions",
    "want to dig deeper",
    "how can i help",
    "let me know if",
    "is there anything",
    "do you have any other",
    "feel free to ask",
    "if you have any more",
]


# Compile once at import time.
_BANNED_PATTERNS: List[Pattern[str]] = [
    re.compile(re.escape(phrase), re.IGNORECASE) for phrase in BANNED_PHRASES
]

# Special-case the split phrase "Take your [X] to the next level" so a
# bare "Take your" mention (e.g. "take your time") doesn't false-flag.
_NEXT_LEVEL_PATTERN: Pattern[str] = re.compile(
    r"take your .* to the next level", re.IGNORECASE
)

_GENERIC_FOLLOW_UP_PATTERNS: List[Pattern[str]] = [
    re.compile(r"^\W*" + re.escape(opener), re.IGNORECASE)
    for opener in GENERIC_FOLLOW_UPS
]


def check_voice_compliance(text: str) -> List[str]:
    """Return a list of banned phrases (or pattern matches) found in text.

    Empty list = compliant. Non-empty list = at least one banned phrase or
    banned pattern fired.

    Use in production as log-and-flag (emit a warning to observability;
    do not silently strip — that masks the underlying prompt bug). Use in
    CI integration tests as block-and-fail (any non-empty return fails
    the test).

    Args:
        text: The generated AI output to check.

    Returns:
        List of matched banned phrases / patterns, in document order, with
        duplicates preserved. Returns an empty list if compliant.
    """
    if not text:
        return []

    violations: List[str] = []

    # The "Take your" entry is paired with the next-level pattern.
    # Check the pattern variant first; if it matches, attribute the
    # violation to the "Take your [X] to the next level" form.
    if _NEXT_LEVEL_PATTERN.search(text):
        violations.append("Take your [X] to the next level")

    for phrase, pattern in zip(BANNED_PHRASES, _BANNED_PATTERNS):
        if phrase == "Take your":
            # Handled above with the next-level pattern.
            continue
        if pattern.search(text):
            violations.append(phrase)

    return violations


def check_follow_up_specificity(follow_up: str) -> Optional[str]:
    """Return the matched generic opener if the follow-up is generic.

    Returns None if the follow-up appears contextual (does not begin with
    a known generic opener).

    Used by schema validation before emitting blog or verdict responses.
    A non-None return value means the response is malformed by spec.

    Args:
        follow_up: The follow_up_question string from the response payload.

    Returns:
        The matched generic opener string, or None if the follow-up
        appears contextual.
    """
    if not follow_up or not follow_up.strip():
        return None

    for opener, pattern in zip(GENERIC_FOLLOW_UPS, _GENERIC_FOLLOW_UP_PATTERNS):
        if pattern.match(follow_up):
            return opener

    return None
