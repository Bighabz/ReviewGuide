"""Centralized prompt construction for ReviewGuide.

VOICE_PROMPT is the single source of truth for ReviewGuide's editor voice.
build_system_prompt() composes a full system prompt from VOICE_PROMPT plus
role-specific instructions, the personality profile inject, history, and
tool outputs.

See tone.md and BACKEND_AGENT_CONTEXT.md for the architectural reasoning.
"""

from .voice import VOICE_PROMPT, build_system_prompt
from .voice_compliance import (
    BANNED_PHRASES,
    GENERIC_FOLLOW_UPS,
    check_voice_compliance,
    check_follow_up_specificity,
)

__all__ = [
    "VOICE_PROMPT",
    "build_system_prompt",
    "BANNED_PHRASES",
    "GENERIC_FOLLOW_UPS",
    "check_voice_compliance",
    "check_follow_up_specificity",
]
