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


def sanitize_voice(text: str) -> tuple[str, list[str]]:
    """Strip voice violations from generated text. Returns (cleaned, violations).

    This is the active SSE-exit gate, called once per response just before
    streaming. Three sanitization passes, applied in order:

    1. Literal banned phrases (`BANNED_PHRASES`): every match replaced
       with an empty string. Sentence-level — a banned phrase mid-paragraph
       leaves the surrounding prose intact (possibly with minor
       grammatical artifacts; acceptable tradeoff vs. shipping the bad
       voice or stalling for a retry).
    2. The split phrase "Take your [X] to the next level" via the
       precompiled `_NEXT_LEVEL_PATTERN`.
    3. Trailing generic follow-up blocks: if a paragraph within the last
       five starts with a generic opener (anything `check_follow_up_specificity`
       would flag), strip from that paragraph to the end of the text.
       Catches the "Want to dig deeper?" + bulleted-questions block that
       gpt-4o-mini reproduces from training-data priors despite explicit
       prompt instructions to avoid it.

    Returns:
        ``(cleaned_text, violations)`` where ``violations`` is the list of
        matched phrases / opener slugs (with ``trailing-generic-block:``
        prefix for case 3). Empty list = no sanitization applied.

    Callers should log every non-empty ``violations`` return to
    observability so the underlying prompt regression surfaces. Do NOT
    log-and-pass-through the original text — silent pass-through masks
    the moat erosion this gate exists to prevent.

    If sanitization would yield empty text (pathological case where the
    entire response was bad voice), the function returns the ORIGINAL
    text with violations recorded. The caller can then decide whether
    to ship the original (with the log alarm) or surface an error to
    the user. Returning empty text is never the right answer.
    """
    if not text:
        return text, []

    violations: list[str] = []
    cleaned = text

    # Pass 1 — literal banned phrases.
    for phrase, pattern in zip(BANNED_PHRASES, _BANNED_PATTERNS):
        if phrase == "Take your":
            # Handled by the next-level pattern in pass 2.
            continue
        if pattern.search(cleaned):
            violations.append(phrase)
            cleaned = pattern.sub("", cleaned)

    # Pass 2 — split phrase "Take your [X] to the next level".
    if _NEXT_LEVEL_PATTERN.search(cleaned):
        violations.append("Take your [X] to the next level")
        cleaned = _NEXT_LEVEL_PATTERN.sub("", cleaned)

    # Pass 3 — trailing generic follow-up block.
    cleaned, stripped_opener = _strip_trailing_generic_block(cleaned)
    if stripped_opener is not None:
        violations.append(f"trailing-generic-block:{stripped_opener}")

    # Pathological case — empty result. Better to ship the original with
    # the alarm than serve a blank response.
    if violations and not cleaned.strip():
        return text, violations

    return cleaned, violations


def _strip_trailing_generic_block(text: str) -> tuple[str, Optional[str]]:
    """Walk backwards through the last five paragraphs; if any starts with
    a generic follow-up opener, strip from that paragraph to end of text.

    A "paragraph" here is a blank-line-separated block (markdown convention).
    Catches both:

    - Single trailing question: ``...body.\n\nWant to dig deeper?``
    - Question + bulleted continuation: ``...body.\n\nWant to dig deeper?\n\n* a\n* b\n* c``

    Returns:
        ``(cleaned_text, matched_opener)``. ``matched_opener`` is None if
        no generic block was found at the tail.
    """
    if not text or not text.strip():
        return text, None

    paragraphs = text.split("\n\n")
    # Walk backwards through the last five paragraphs (look-back window).
    start_idx = max(0, len(paragraphs) - 5)
    for i in range(start_idx, len(paragraphs)):
        first_line = paragraphs[i].strip().split("\n", 1)[0].strip()
        generic = check_follow_up_specificity(first_line)
        if generic is not None:
            cleaned = "\n\n".join(paragraphs[:i]).rstrip()
            return cleaned, generic

    return text, None
