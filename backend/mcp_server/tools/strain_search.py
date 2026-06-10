"""
Strain Search Tool — cannabis strain vertical (SmartVape engine, AI-parsed).

The query is understood by an LLM (named strains, desired feelings,
conditions, strain type — abbreviations like "sour d" resolved by the model),
then the vendored SmartVape engine (1054 strains, terpene + effect profiles)
does the ranking. Live Leafly strain-page URLs and snippets come from Serper
(the existing SERPAPI pipeline — no Leafly API key needed); when Serper is
off or finds nothing, cards fall back to Leafly search links.

Three modes:
- comparison: the query names 2+ strains ("sour d vs blue dream")
- similar:    one named strain → it plus its closest matches
- recommend:  effect/condition intent ("strains for sleep")
"""

import asyncio
import json
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


async def _extract_query_params(message: str, slots: Dict[str, Any]) -> Dict[str, Any]:
    """LLM-parse the strain query. The model resolves abbreviations and slang
    ("sour d" → "Sour Diesel", "gdp" → "Granddaddy Purple") and maps the
    user's ask onto the engine's standard feelings/conditions vocabulary."""
    from app.core.config import settings
    from app.services.model_service import model_service
    from app.services.smartvape.engine import STANDARD_FEELINGS, STANDARD_CONDITIONS

    system_prompt = f"""You parse cannabis strain queries for a recommendation engine. Extract what the user is asking for.

Return ONLY valid JSON:
{{
  "named_strains": ["<full canonical strain names the user referenced — resolve abbreviations and slang, e.g. 'sour d' → 'Sour Diesel', 'gdp' → 'Granddaddy Purple', 'gg4' → 'GG4'>"],
  "feelings": ["<desired feelings, ONLY from: {', '.join(STANDARD_FEELINGS)}>"],
  "conditions": ["<conditions to help with, ONLY from: {', '.join(STANDARD_CONDITIONS)}>"],
  "strain_type": "<'Indica', 'Sativa', 'Hybrid', or null if no preference stated>"
}}

Rules:
- named_strains: only strains the user EXPLICITLY referenced; empty list if none
- Map intent words onto the allowed vocabulary ("can't sleep" → feelings ["Sleepy"], conditions ["Insomnia"]; "for focus at work" → ["Focused"])
- "indica vs sativa" is a TYPE question, not named strains — leave named_strains empty
- Empty lists are fine; never invent"""

    extra = str(slots.get("desired_effects", "") or "")
    user_prompt = f'Query: "{message}"' + (f"\nStated preferences: {extra}" if extra else "")

    raw = await model_service.generate(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=settings.PRODUCT_SEARCH_MODEL,
        temperature=0.1,
        max_tokens=300,
        response_format={"type": "json_object"},
        agent_name="strain_query_parser",
    )
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("strain extraction returned non-dict")

    # Clamp the model's answer to the engine's vocabulary (case-insensitive)
    feelings_ok = {f.lower(): f for f in STANDARD_FEELINGS}
    conditions_ok = {c.lower(): c for c in STANDARD_CONDITIONS}
    return {
        "named_strains": [str(n).strip() for n in parsed.get("named_strains") or [] if str(n).strip()],
        "feelings": [feelings_ok[f.lower()] for f in parsed.get("feelings") or [] if str(f).lower() in feelings_ok],
        "conditions": [conditions_ok[c.lower()] for c in parsed.get("conditions") or [] if str(c).lower() in conditions_ok],
        "strain_type": parsed.get("strain_type") if parsed.get("strain_type") in ("Indica", "Sativa", "Hybrid") else None,
    }


async def _enrich_via_serper(results: List[Dict[str, Any]], logger) -> None:
    """Upgrade Leafly search links to real strain-page URLs + live snippets via
    Serper (in place, top 3, best-effort — failures keep the fallback link)."""
    from app.core.config import settings

    if not getattr(settings, "ENABLE_SERPAPI", False) or not getattr(settings, "SERPAPI_API_KEY", ""):
        logger.info("[strain_search] Serper disabled — keeping Leafly search-link fallbacks")
        return

    from app.services.serpapi.client import SerpAPIClient

    client = SerpAPIClient()
    targets = results[:3]
    infos = await asyncio.gather(
        *(client.search_strain_info(r["name"]) for r in targets),
        return_exceptions=True,
    )
    upgraded = 0
    for r, info in zip(targets, infos):
        if isinstance(info, dict) and info.get("url"):
            r["leafly_url"] = info["url"]
            if info.get("snippet"):
                r["leafly_snippet"] = info["snippet"]
            upgraded += 1
        elif isinstance(info, Exception):
            logger.warning(f"[strain_search] Serper enrichment failed for '{r['name']}': {info}")
    logger.info(f"[strain_search] Serper enrichment: {upgraded}/{len(targets)} strain pages resolved")


@tool_error_handler(tool_name="strain_search", error_message="Failed to search strains")
async def strain_search(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve the user's strain query: LLM extraction → SmartVape engine ranking
    → Serper Leafly enrichment.

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

    # ── AI query understanding (graceful default when the LLM is down) ──
    try:
        params = await _extract_query_params(message, slots)
    except Exception as e:
        logger.warning(f"[strain_search] extraction LLM failed ({e}) — defaulting to broad recommend")
        params = {"named_strains": [], "feelings": ["Happy", "Relaxed"], "conditions": [], "strain_type": None}

    strain_type = params["strain_type"]
    slot_type = str(slots.get("strain_type", "")).capitalize()
    if not strain_type and slot_type in ("Indica", "Sativa", "Hybrid"):
        strain_type = slot_type

    # Resolve the LLM's canonical names against the database (partial match)
    named = []
    seen = set()
    for name in params["named_strains"]:
        matches = engine.search_strains(name, limit=1)
        if matches and matches[0].name not in seen:
            seen.add(matches[0].name)
            named.append(matches[0])

    feelings = params["feelings"]
    conditions = params["conditions"]
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

    results = results[:6]
    await _enrich_via_serper(results, logger)

    logger.info(
        f"[strain_search] mode={mode}, named={[s.name for s in named]}, "
        f"feelings={feelings}, conditions={conditions}, type={strain_type}, "
        f"results={len(results)}"
    )

    return {
        "strain_results": results,
        "strain_mode": mode,
        "success": True,
    }
