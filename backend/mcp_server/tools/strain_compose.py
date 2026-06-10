"""
Strain Compose Tool — verdict prose + Leafly link-out cards for the cannabis
strain vertical.

Consumes strain_search's results (SmartVape engine data — ours, so no source
attribution problem) and produces the standard compose surface: editor-voiced
assistant_text with a committed pick, a follow_up_question, and
product_review cards whose single link goes OUT to Leafly. ReviewGuide sells
nothing here; the destination site's age gate applies on click-through.
"""

import json
import os
import sys
from typing import Any, Dict, List

from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "strain_compose",
    "intent": "strain",
    "purpose": "Generate the final strain recommendation response with verdict prose and strain cards. Final tool in the strain flow.",
    "tools": {
        "pre": ["strain_search"],
        "post": [],
    },
    "produces": ["assistant_text", "ui_blocks", "citations"],
    "citation_message": "Weighing the tradeoffs…",
    "tool_order": 800,
}

_STRAIN_BLOG_ROLE = """Write a strain recommendation verdict for ReviewGuide.ai.

OUTPUT FORMAT — return a JSON object with these string fields:
{
  "body": "<2-4 short paragraphs of markdown>",
  "follow_up_question": "<exactly one contextual curious question>",
  "top_pick": "<the EXACT strain name of your #1, copied verbatim from the strain list>"
}

RANK AND COMMIT: you are an editor with a take. Name a #1 strain and say WHY
it beats the others for what this user described — lean on the data you're
given (strain type, dominant terpene, effects, what it helps with). The
runner-up is the right pick for a specific different situation, not "also
great".

RULES:
- Ground every claim in the provided strain data — never invent effects,
  potency numbers, or medical outcomes
- No medical advice; effects framing only ("users report", "known for")
- Do NOT include links or images — the cards below your text carry those
- Keep the body under 250 words
- The follow_up_question must reference something specific (a strain, an
  effect tradeoff, the user's stated need) — never a generic offer"""


def _strain_card(strain: Dict[str, Any], rank: int) -> Dict[str, Any]:
    features = []
    if strain.get("strain_type") and strain["strain_type"] != "Unknown":
        features.append(strain["strain_type"])
    if strain.get("dominant_terpene"):
        terp = strain["dominant_terpene"]
        desc = strain.get("terpene_description") or ""
        features.append(f"{terp} dominant" + (f" ({desc})" if desc else ""))

    pros = [{"description": f, "citations": []} for f in strain.get("feelings", [])[:4]]

    helps = strain.get("helps_with", [])
    summary_bits = []
    if strain.get("feelings"):
        summary_bits.append("Known for: " + ", ".join(strain["feelings"][:4]))
    if helps:
        summary_bits.append("Users report help with: " + ", ".join(helps[:4]))

    return {
        "type": "product_review",
        "data": {
            "product_name": strain["name"],
            "image_url": "",
            "rating": "",
            "summary": ". ".join(summary_bits),
            "features": features,
            "pros": pros,
            "cons": [],
            "affiliate_links": [{
                "product_id": f"leafly-{rank}",
                "title": f"{strain['name']} on Leafly",
                "price": 0,
                "currency": "USD",
                "affiliate_link": strain.get("leafly_url", ""),
                "merchant": "Leafly",
                "image_url": "",
                "rating": None,
                "review_count": None,
            }],
            "rank": rank,
        },
    }


def _fallback_body(strains: List[Dict[str, Any]], mode: str) -> str:
    top = strains[0]
    lines = [
        f"**{top['name']}** is the pick here — a {top.get('strain_type', 'hybrid').lower()} "
        f"known for {', '.join(top.get('feelings', ['balanced effects'])[:3])}."
    ]
    if len(strains) > 1:
        alt = strains[1]
        lines.append(
            f"If that's not quite it, **{alt['name']}** leans "
            f"{', '.join(alt.get('feelings', ['different'])[:2])} instead."
        )
    lines.append("Details and availability are on the cards below.")
    return "\n\n".join(lines)


@tool_error_handler(tool_name="strain_compose", error_message="Failed to compose strain response")
async def strain_compose(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the strain verdict response from strain_search results.

    Reads from state:
        - strain_results, strain_mode (from strain_search)
        - user_message, conversation_history

    Returns:
        {"assistant_text", "ui_blocks", "citations", "follow_up_question", "success"}
    """
    from app.core.centralized_logger import get_logger
    from app.core.config import settings
    from app.services.model_service import model_service
    from app.services.prompts.voice import build_system_prompt

    logger = get_logger(__name__)

    strains = state.get("strain_results", []) or []
    mode = state.get("strain_mode", "recommend")
    user_message = state.get("user_message", "")

    if not strains:
        return {
            "assistant_text": (
                "I couldn't match that to anything in the strain library. "
                "Tell me the effect you're after — relaxing, sleep, focus, energy — "
                "or name a strain you've liked, and I'll work from there."
            ),
            "ui_blocks": [],
            "citations": [],
            "success": True,
        }

    # ── One LLM call for the verdict prose ──
    strain_lines = []
    for s in strains:
        strain_lines.append(
            f"Strain: {s['name']} | Type: {s.get('strain_type')} | "
            f"Dominant terpene: {s.get('dominant_terpene')} ({s.get('terpene_description', '')}) | "
            f"Effects: {', '.join(s.get('feelings', []))} | "
            f"Helps with: {', '.join(s.get('helps_with', []))} | "
            f"Match score: {s.get('score')}"
        )
    blog_data = (
        f'User asked: "{user_message}"\n'
        f"Mode: {mode}\n\nStrain data:\n" + "\n".join(strain_lines)
    )

    body = ""
    follow_up = ""
    top_pick = ""
    try:
        raw = await model_service.generate_compose(
            messages=[
                {"role": "system", "content": build_system_prompt(role_prompt=_STRAIN_BLOG_ROLE, kind="response")},
                {"role": "user", "content": blog_data},
            ],
            temperature=0.7,
            max_tokens=600,
            response_format={"type": "json_object"},
            agent_name="strain_composer",
        )
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            body = (parsed.get("body") or "").strip()
            follow_up = (parsed.get("follow_up_question") or "").strip()
            top_pick = (parsed.get("top_pick") or "").strip()
    except Exception as e:
        logger.warning(f"[strain_compose] verdict LLM failed, using deterministic fallback: {e}")

    if not body:
        body = _fallback_body(strains, mode)

    # ── Cards: prose's top pick leads (stable move-to-front, like product_compose) ──
    ordered = list(strains)
    if top_pick:
        idx = next(
            (i for i, s in enumerate(ordered) if s["name"].lower() == top_pick.lower()),
            None,
        )
        if idx is not None and idx > 0:
            ordered.insert(0, ordered.pop(idx))

    ui_blocks = [_strain_card(s, i) for i, s in enumerate(ordered[:5], 1)]

    logger.info(
        f"[strain_compose] mode={mode}, cards={len(ui_blocks)}, "
        f"top_pick={top_pick or ordered[0]['name']!r}, llm_body={bool(top_pick or follow_up)}"
    )

    result = {
        "assistant_text": body,
        "ui_blocks": ui_blocks,
        "citations": [],
        "success": True,
    }
    if follow_up:
        result["follow_up_question"] = follow_up
    return result
