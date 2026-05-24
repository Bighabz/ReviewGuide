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


# Known review-site source names. Used as a whitelist to anchor citation
# pattern matching so product brand names ("Sony highlights ANC") aren't
# falsely flagged. Add a source here when it surfaces in production output;
# omit ambiguous English words (e.g. "Wired" — adjective collision) to
# stay false-positive safe.
KNOWN_REVIEW_SOURCES: List[str] = [
    "Wirecutter",
    "RTINGS",
    "The Verge",
    "CNET",
    "Tom's Guide",
    "Tom's Hardware",
    "Engadget",
    "TechRadar",
    "PCMag",
    "Consumer Reports",
    "Trusted Reviews",
    "Digital Trends",
    "Android Authority",
    "Mashable",
    "Forbes",
    "GQ",
    "NYT",
    "Ars Technica",
    "Gizmodo",
    "9to5Mac",
    "9to5Google",
    "Reviewed",
]

# Domain substrings for the markdown-link fallback. Matches the domain
# anywhere in the URL (handles both "wirecutter.com" and the path-based
# "nytimes.com/wirecutter" variant). Word-boundary anchored so "rtings"
# matches but "shirtings" doesn't.
REVIEW_SITE_DOMAIN_SUBSTRINGS: List[str] = [
    "wirecutter",
    "rtings",
    "theverge",
    "cnet",
    "tomsguide",
    "tomshardware",
    "engadget",
    "techradar",
    "pcmag",
    "consumerreports",
    "trustedreviews",
    "digitaltrends",
    "androidauthority",
    "mashable",
    "arstechnica",
    "gizmodo",
    "reviewed.com",
]


_SOURCE_ALT = "|".join(re.escape(s) for s in KNOWN_REVIEW_SOURCES)
# Matches a source name in any of three forms: bare ("Wirecutter"),
# bracketed ("[Wirecutter]"), or as the text of a markdown link
# ("[Wirecutter](https://...)"). The optional URL group has no \) inside
# to avoid greedy match across multiple links.
_SOURCE_REF = rf"(?:\[)?(?:{_SOURCE_ALT})(?:\])?(?:\([^)]*\))?"


# Citation patterns. Order matters only for violation reporting — all six
# run against the same input via finditer, then a single sub strips them.
# Trailing whitespace + optional comma is consumed so the strip leaves
# clean surrounding prose ("According to RTINGS, the X is great" →
# "the X is great", not ", the X is great").
_CITATION_PATTERNS: List[Pattern[str]] = [
    re.compile(rf"\baccording to\s+{_SOURCE_REF}\s*,?\s*", re.IGNORECASE),
    re.compile(rf"\bas noted by\s+{_SOURCE_REF}\s*,?\s*", re.IGNORECASE),
    # "Per <SOURCE>" only when followed by a known source name — avoids
    # false-flagging "per the spec sheet" / "per your request".
    re.compile(rf"\bper\s+{_SOURCE_REF}\s*,?\s*", re.IGNORECASE),
    # "Reviewers at/from <SOURCE>"
    re.compile(rf"\breviewers?\s+(?:at|from)\s+{_SOURCE_REF}\s*", re.IGNORECASE),
    # "<SOURCE> (says|highlights|...)" — anchored on the known-source list
    # so brand attributions like "Sony highlights ANC" survive untouched.
    re.compile(
        rf"\b{_SOURCE_REF}\s+"
        r"(?:says|recommends?|advises?|suggests?|highlights?|notes?|praises?|"
        r"criticizes?|commends?|writes?|reports?|finds?|prefers?|favors?)\s+",
        re.IGNORECASE,
    ),
    # "<SOURCE>'s review/verdict/take/recommendation"
    re.compile(
        rf"\b{_SOURCE_REF}'?s?\s+"
        r"(?:review|verdict|take|recommendation|opinion|coverage|guide|writeup)\b",
        re.IGNORECASE,
    ),
    # Generic third-person attribution: "Reviewers/Critics/Experts <verb>".
    # No source-name constraint here — the subject is the attribution
    # itself, so any review-style verb after these subjects is a citation.
    re.compile(
        r"\b(?:reviewers?|critics?|experts?)\s+"
        r"(?:highlight|recommend|note|praise|commend|criticize|advise|suggest|prefer|favor)\w*\s+",
        re.IGNORECASE,
    ),
]


# Fallback: any remaining markdown link whose URL contains a known
# review-site domain. Runs after the phrase patterns so a citation
# clause containing a markdown link gets caught as a single citation
# violation (not double-counted as both citation + review-link).
_REVIEW_SITE_DOMAINS_REGEX = "|".join(REVIEW_SITE_DOMAIN_SUBSTRINGS)
_REVIEW_SITE_LINK: Pattern[str] = re.compile(
    rf"\[([^\]]+)\]\(https?://[^)]*\b(?:{_REVIEW_SITE_DOMAINS_REGEX})\b[^)]*\)",
    re.IGNORECASE,
)


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
    streaming. Five sanitization passes, applied in order:

    0. Citation patterns (``_CITATION_PATTERNS``): "According to <SOURCE>",
       "Reviewers from <SOURCE>", "<SOURCE> highlights", etc., plus
       markdown links to known review-site domains. Source names are
       anchored to a known-source whitelist so product brand names
       ("Sony highlights ANC") survive untouched. Runs first so a citation
       clause containing other banned tokens gets counted as one citation
       violation rather than double-counted.
    1. Literal banned phrases (``BANNED_PHRASES``): every match replaced
       with an empty string. Sentence-level — a banned phrase mid-paragraph
       leaves the surrounding prose intact (possibly with minor
       grammatical artifacts; acceptable tradeoff vs. shipping the bad
       voice or stalling for a retry).
    2. The split phrase "Take your [X] to the next level" via the
       precompiled ``_NEXT_LEVEL_PATTERN``.
    3. Trailing generic follow-up blocks: if a paragraph within the last
       five starts with a generic opener (anything ``check_follow_up_specificity``
       would flag), strip from that paragraph to the end of the text.
       Catches the "Want to dig deeper?" + bulleted-questions block that
       gpt-4o-mini reproduces from training-data priors despite explicit
       prompt instructions to avoid it.
    4. Whitespace normalization: collapse doubled horizontal whitespace,
       remove orphaned commas left behind by previous passes, collapse
       runs of 3+ newlines back to paragraph breaks.

    Returns:
        ``(cleaned_text, violations)`` where ``violations`` is the list of
        matched phrases / opener slugs. Prefixes: ``citation:`` for phrase
        citations, ``review-link:`` for markdown-link citations,
        ``trailing-generic-block:`` for case 3. Empty list = no
        sanitization applied.

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

    # Pass 0 — citation patterns (review-site links + attribution phrases).
    cleaned = _strip_citations(cleaned, violations)

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

    # Pass 4 — whitespace cleanup so previous strip passes don't leave
    # doubled spaces or orphaned commas / colons mid-sentence.
    if violations:
        cleaned = _normalize_whitespace(cleaned)

    # Pathological case — empty result. Better to ship the original with
    # the alarm than serve a blank response.
    if violations and not cleaned.strip():
        return text, violations

    return cleaned, violations


def _strip_citations(text: str, violations: List[str]) -> str:
    """Strip citation patterns (Pass 0 of sanitize_voice).

    Records violations with ``citation:`` prefix for phrase patterns and
    ``review-link:`` prefix for markdown-link patterns so callers can
    distinguish them in logs without re-running the regex.

    Order: phrase patterns first (catches "According to [Wirecutter](url)"
    as a whole citation), then the markdown-link fallback for any review
    link still present (e.g. a bare "Check the [full review](theverge.com)"
    link not in a citation phrase).
    """
    cleaned = text

    for pattern in _CITATION_PATTERNS:
        for match in pattern.finditer(cleaned):
            snippet = re.sub(r"\s+", " ", match.group(0)).strip()[:60]
            violations.append(f"citation:{snippet}")
        cleaned = pattern.sub("", cleaned)

    for match in _REVIEW_SITE_LINK.finditer(cleaned):
        violations.append(f"review-link:{match.group(1)[:40]}")
    cleaned = _REVIEW_SITE_LINK.sub("", cleaned)

    return cleaned


def _normalize_whitespace(text: str) -> str:
    """Cleanup after regex-based strip passes.

    - Collapses repeated horizontal whitespace (preserves newlines).
    - Fixes orphaned punctuation (" ," → ",", " ." → ".").
    - Strips orphaned leading commas / colons / semicolons on each line
      (artifact of "According to X, the Y" → ", the Y" after strip).
    - Collapses runs of 3+ newlines to two (preserves paragraph breaks).
    """
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r"(?m)^[,;:]\s*", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


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
