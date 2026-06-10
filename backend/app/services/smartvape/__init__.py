"""SmartVape strain engine — vendored from Habib's smartvape project.

Powers the cannabis strain vertical: 1054 strains with terpene + effect
profiles and a multi-factor recommendation engine (engine.py, vendored
verbatim except a silenced stdout print). ReviewGuide owns the verdict and
links OUT to Leafly for anything transactional — we sell nothing, and the
destination site's age gate applies on click-through.

Routing is AI-driven: the intent classifier owns strain detection (the
"strain" intent category) and strain_search asks an LLM to parse the query —
there is deliberately NO keyword detector here (Habib, 2026-06-10).

Public surface:
- get_engine()   — lazy singleton over data/strains.json
- leafly_url(n)  — guaranteed-valid Leafly search link (fallback when Serper
                   enrichment is off or finds no strain page)
"""
from __future__ import annotations

import os
from functools import lru_cache
from urllib.parse import quote

from .engine import SmartVapeEngine

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "strains.json")


@lru_cache(maxsize=1)
def get_engine() -> SmartVapeEngine:
    """Load the strain database once per process (~1MB JSON, 1054 strains)."""
    return SmartVapeEngine(_DATA_PATH)


def leafly_url(strain_name: str) -> str:
    """Leafly search link — always lands somewhere useful (direct strain-page
    slugs 404 for odd names; search never does). Serper enrichment upgrades
    this to the real strain page when available."""
    return f"https://www.leafly.com/search?q={quote(str(strain_name).strip())}"
