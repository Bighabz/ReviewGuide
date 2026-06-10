"""
Strain Search Tool — cannabis strain vertical (SmartVape engine).

Runs the vendored SmartVape recommendation engine (1054 strains, terpene +
effect profiles) against the user's query. No retailer search, no affiliate
calls — ReviewGuide owns the strain verdict and the compose step links OUT to
Leafly. Three modes:

- comparison: the query names 2+ strains ("sour d vs blue dream")
- similar:    one named strain → it plus its closest matches
- recommend:  effect/condition intent ("strains for sleep") → multi-factor
              recommendation
"""

import os
import re
import sys
from typing import Any, Dict, List

from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "strain_search",
    "intent": "strain",
    "purpose": "Recommend, compare, or find similar cannabis strains from the in-house strain database",
    "tools": {
        "pre": [],
        "post": ["strain_compose"],
    },
    "produces": ["strain_results", "strain_mode"],
    # No required slots — strain queries go straight to results (results-first).
    "optional_slots": ["desired_effects", "strain_type"],
    "slot_types": {
        "desired_effects": {"type": "string", "description": "Desired feelings or conditions (e.g., 'relaxed', 'sleep', 'focus', 'anxiety')"},
        "strain_type": {"type": "string", "description": "Strain type preference: indica, sativa, or hybrid"},
    },
    "citation_message": "Reading the room…",
}

_VS_SPLIT = re.compile(r"\s+(?:vs\.?|versus)\s+", re.IGNORECASE)

# Message vocabulary → engine feelings / conditions (SmartVape standard lists)
_FEELING_HINTS = {
    "relax": "Relaxed", "relaxed": "Relaxed", "chill": "Relaxed", "calm": "Calm",
    "sleep": "Sleepy", "sleepy": "Sleepy", "tired": "Sleepy",
    "focus": "Focused", "focused": "Focused", "productive": "Focused",
    "creative": "Creative", "creativity": "Creative",
    "energy": "Energetic", "energetic": "Energetic", "active": "Energetic",
    "happy": "Happy", "euphoric": "Euphoric", "euphoria": "Euphoric",
    "uplifted": "Uplifted", "uplifting": "Uplifted",
    "social": "Talkative", "talkative": "Talkative", "giggly": "Giggly",
    "hungry": "Hungry", "appetite": "Hungry", "aroused": "Aroused",
}
_CONDITION_HINTS = {
    "sleep": "Insomnia", "insomnia": "Insomnia",
    "anxiety": "Anxiety", "anxious": "Anxiety",
    "pain": "Pain", "aches": "Pain",
    "stress": "Stress", "stressed": "Stress",
    "depression": "Depression", "depressed": "Depression",
    "ptsd": "PTSD", "migraine": "Migraines", "migraines": "Migraines",
    "inflammation": "Inflammation", "fatigue": "Fatigue",
    "nausea": "Nausea",
}


def _strain_to_result(strain, score: float, reasons: List[str]) -> Dict[str, Any]:
    from app.services.smartvape import leafly_url

    d = strain.to_dict()
    # Strip dataset version suffixes ("Blue Dream 1.0") for display
    display_name = re.sub(r"\s+\d+(\.\d+)?$", "", d["name"]).strip() or d["name"]
    return {
        "name": display_name,
        "strain_type": d.get("type", "Unknown"),
        "dominant_terpene": d.get("dominant_terpene"),
        "terpene_description": d.get("terpene_description", ""),
        "feelings": d.get("feelings", []),
        "helps_with": d.get("helps_with", []),
        "score": round(float(score), 2),
        "match_reasons": reasons,
        "leafly_url": leafly_url(display_name),
    }


@tool_error_handler(tool_name="strain_search", error_message="Failed to search strains")
async def strain_search(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve the user's strain query against the SmartVape engine.

    Reads from state:
        - user_message: the query
        - slots: optional desired_effects / strain_type

    Returns:
        {"strain_results": [...], "strain_mode": "comparison|similar|recommend", "success": bool}
    """
    from app.core.centralized_logger import get_logger
    from app.services.smartvape import get_engine

    logger = get_logger(__name__)
    engine = get_engine()

    message = state.get("user_message", "") or ""
    slots = state.get("slots", {}) or {}
    msg_lower = message.lower()

    # Strain type preference (from slots or the message itself)
    strain_type = None
    type_hint = str(slots.get("strain_type", "")).lower() + " " + msg_lower
    for t in ("indica", "sativa", "hybrid"):
        if t in type_hint:
            strain_type = t.capitalize()
            break

    # ── Named strains: vs-sides first (partial names), then anywhere in text ──
    named = []
    seen = set()

    def _add(strain):
        if strain and strain.name not in seen:
            seen.add(strain.name)
            named.append(strain)

    parts = _VS_SPLIT.split(message)
    if len(parts) >= 2:
        for part in parts:
            # Strip lead-in words so "should i get sour d" still resolves
            cleaned = re.sub(
                r"^(?:should i (?:get|go|pick|buy)|best|which is better[,:]?)\s+", "",
                part.strip(), flags=re.IGNORECASE,
            ).strip(" ?!.")
            if cleaned:
                matches = engine.search_strains(cleaned, limit=1)
                if matches:
                    _add(matches[0])
    for token in re.findall(r"[a-z0-9' ]{4,}", msg_lower):
        for strain in engine.search_strains(token.strip(), limit=1):
            if strain.name.lower() in msg_lower:
                _add(strain)

    # ── Effect / condition intent from slots + message vocabulary ──
    words = set(re.findall(r"[a-z']+", msg_lower + " " + str(slots.get("desired_effects", "")).lower()))
    feelings = sorted({v for k, v in _FEELING_HINTS.items() if k in words})
    conditions = sorted({v for k, v in _CONDITION_HINTS.items() if k in words})

    results: List[Dict[str, Any]] = []

    if len(named) >= 2:
        mode = "comparison"
        for strain in named[:4]:
            results.append(_strain_to_result(strain, 1.0, ["Named in your question"]))
        # A couple of alternatives that bridge the compared strains
        for rec in engine.find_similar(named[0].name, limit=3):
            if rec.strain.name not in seen:
                seen.add(rec.strain.name)
                results.append(_strain_to_result(rec.strain, rec.score, ["Close alternative"]))
    elif len(named) == 1:
        mode = "similar"
        results.append(_strain_to_result(named[0], 1.0, ["Named in your question"]))
        for rec in engine.find_similar(named[0].name, limit=5):
            if rec.strain.name not in seen:
                seen.add(rec.strain.name)
                results.append(_strain_to_result(rec.strain, rec.score, rec.match_reasons))
    else:
        mode = "recommend"
        if not feelings and not conditions:
            feelings = ["Happy", "Relaxed"]  # sensible default ask
        recs = engine.advanced_recommend(
            feelings=feelings or None,
            conditions=conditions or None,
            strain_type=strain_type,
            limit=6,
        )
        for rec in recs:
            results.append(_strain_to_result(rec.strain, rec.score, rec.match_reasons))

    logger.info(
        f"[strain_search] mode={mode}, named={[s.name for s in named]}, "
        f"feelings={feelings}, conditions={conditions}, type={strain_type}, "
        f"results={len(results)}"
    )

    return {
        "strain_results": results[:6],
        "strain_mode": mode,
        "success": True,
    }
