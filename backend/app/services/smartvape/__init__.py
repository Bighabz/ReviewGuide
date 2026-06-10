"""SmartVape strain engine — vendored from Habib's smartvape project.

Powers the cannabis strain vertical: 1054 strains with terpene + effect
profiles and a multi-factor recommendation engine (engine.py, vendored
verbatim except a silenced stdout print). ReviewGuide owns the verdict and
links OUT to Leafly for anything transactional — we sell nothing, and the
destination site's age gate applies on click-through.

Public surface:
- get_engine()        — lazy singleton over data/strains.json
- is_strain_query(q)  — deterministic cannabis-query detector (planner hook)
- leafly_url(name)    — guaranteed-valid Leafly search link for a strain
"""
from __future__ import annotations

import os
import re
from functools import lru_cache
from urllib.parse import quote

from .engine import SmartVapeEngine

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "strains.json")

# Unambiguous cannabis vocabulary. Deliberately NOT included: "cbd" (legit
# Amazon-sellable products), "edible"/"gelato"/"wedding cake" (common
# non-cannabis meanings). Strain names handle those cases via the pair rule.
_CANNABIS_KEYWORDS = {
    "cannabis", "marijuana", "marihuana", "weed", "ganja",
    "strain", "strains",
    "indica", "sativa",
    "terpene", "terpenes", "myrcene", "limonene", "caryophyllene",
    "linalool", "pinene", "terpinolene", "ocimene",
    "thc", "dispensary", "dispensaries", "kush", "420",
}

_VS_SPLIT = re.compile(r"\s+(?:vs\.?|versus)\s+", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9']+")


@lru_cache(maxsize=1)
def get_engine() -> SmartVapeEngine:
    """Load the strain database once per process (~1MB JSON, 1054 strains)."""
    return SmartVapeEngine(_DATA_PATH)


def leafly_url(strain_name: str) -> str:
    """Leafly search link — always lands somewhere useful (direct strain-page
    slugs 404 for odd names like 'GG4 1.0'; search never does)."""
    return f"https://www.leafly.com/search?q={quote(str(strain_name).strip())}"


@lru_cache(maxsize=1)
def _strain_name_lexicon() -> frozenset:
    """Lowercased full strain names with version suffixes stripped
    ('Blue Dream 1.0' → 'blue dream'). Single-word generic names that collide
    with everyday products are excluded from detection."""
    generic = {"gelato", "cookies", "sherbert", "sherbet", "runtz", "oreoz", "mimosa", "do-si-dos"}
    names = set()
    for strain in get_engine().strains:
        name = re.sub(r"\s+\d+(\.\d+)?$", "", strain.name.lower()).strip()
        if name and name not in generic and len(name) >= 4:
            names.add(name)
    return frozenset(names)


def _named_strains_in(text: str) -> list:
    """Known strain names appearing in the text on word boundaries."""
    text_l = f" {' '.join(_WORD.findall(text.lower()))} "
    return [n for n in _strain_name_lexicon() if f" {n} " in text_l]


def is_strain_query(message: str) -> bool:
    """Deterministic cannabis-query detector (planner routing hook).

    True when the message either uses unambiguous cannabis vocabulary, names
    two known strains, or is an 'X vs Y' where both sides resolve to strains
    via the engine's partial-name search ('sour d vs blue dream'). A single
    strain-name hit is NOT enough — 'wedding cake stand' is a baking query.
    """
    if not message:
        return False
    msg = message.lower()
    words = set(_WORD.findall(msg))

    if words & _CANNABIS_KEYWORDS:
        return True

    named = _named_strains_in(msg)
    if len(named) >= 2:
        return True

    # "X vs Y" where BOTH sides match strains (partial names allowed)
    parts = _VS_SPLIT.split(message)
    if len(parts) == 2 and named:
        engine = get_engine()
        sides_match = all(
            engine.search_strains(part.strip(), limit=1) for part in parts if part.strip()
        )
        if sides_match:
            return True
    return False
