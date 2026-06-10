"""
SmartVape Recommendation Engine
================================
A complete cannabis strain recommendation system built from scratch.

Core Algorithms:
1. Strain Recommendation - Match user preferences to optimal strains
2. Terpene Blending - Calculate optimal terpene profiles from combinations
3. Medical Condition Matching - Map symptoms to therapeutic strains
4. Similarity Scoring - Rank strain relationships
5. Effect Targeting - Connect desired feelings to chemistry

Author: SmartVape Team
Version: 2.0.0
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from collections import Counter
import json
import math


# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

class StrainType(Enum):
    """Cannabis strain classification types."""
    INDICA = "Indica"
    SATIVA = "Sativa"
    HYBRID = "Hybrid"
    UNKNOWN = "Unknown"

    @classmethod
    def from_string(cls, value: str) -> "StrainType":
        """Convert string to StrainType enum."""
        mapping = {
            "indica": cls.INDICA,
            "sativa": cls.SATIVA,
            "hybrid": cls.HYBRID,
        }
        return mapping.get(value.lower().strip(), cls.UNKNOWN)


class Terpene(Enum):
    """Primary terpenes found in cannabis."""
    MYRCENE = "Myrcene"
    LIMONENE = "Limonene"
    CARYOPHYLLENE = "Caryophyllene"
    PINENE = "Pinene"
    LINALOOL = "Linalool"
    OCIMENE = "Ocimene"
    TERPINOLENE = "Terpinolene"

    @property
    def description(self) -> str:
        """Get the aroma/flavor description for this terpene."""
        descriptions = {
            Terpene.MYRCENE: "herbal, earthy, musky",
            Terpene.LIMONENE: "citrus, lemon, orange",
            Terpene.CARYOPHYLLENE: "pepper, spicy, woody",
            Terpene.PINENE: "pine, fresh, forest",
            Terpene.LINALOOL: "floral, lavender, sweet",
            Terpene.OCIMENE: "sweet, herbal, woody",
            Terpene.TERPINOLENE: "herbal, floral, piney",
        }
        return descriptions.get(self, "")

    @property
    def effects(self) -> list[str]:
        """Get the typical effects associated with this terpene."""
        effect_map = {
            Terpene.MYRCENE: ["Relaxed", "Sleepy", "Calm"],
            Terpene.LIMONENE: ["Happy", "Uplifted", "Energetic"],
            Terpene.CARYOPHYLLENE: ["Relaxed", "Calm", "Pain Relief"],
            Terpene.PINENE: ["Alert", "Focused", "Creative"],
            Terpene.LINALOOL: ["Relaxed", "Calm", "Sleepy"],
            Terpene.OCIMENE: ["Uplifted", "Energetic"],
            Terpene.TERPINOLENE: ["Uplifted", "Happy", "Energetic"],
        }
        return effect_map.get(self, [])

    @classmethod
    def from_string(cls, value: str) -> Optional["Terpene"]:
        """Convert string to Terpene enum."""
        if not value:
            return None
        for terpene in cls:
            if terpene.value.lower() == value.lower().strip():
                return terpene
        return None


# Standard feelings/effects in the database
STANDARD_FEELINGS = [
    "Happy", "Relaxed", "Euphoric", "Creative", "Energetic",
    "Giggly", "Sleepy", "Talkative", "Tingly", "Uplifted",
    "Focused", "Hungry", "Aroused", "Calm"
]

# Standard medical conditions
STANDARD_CONDITIONS = [
    "Anxiety", "Pain", "Insomnia", "Stress", "Depression",
    "PTSD", "Migraines", "Inflammation", "Fatigue", "Nausea",
    "Lack of Appetite", "Muscle Spasms", "Cramps", "Headaches",
    "ADD/ADHD", "Bipolar Disorder", "Gastrointestinal Disorder",
    "Eye Pressure", "Glaucoma", "Asthma"
]


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class TerpeneProfile:
    """Represents a strain's terpene composition."""
    dominant: Optional[Terpene] = None
    dominant_description: str = ""
    secondary: list[Terpene] = field(default_factory=list)

    def get_all_terpenes(self) -> list[Terpene]:
        """Get all terpenes (dominant + secondary)."""
        terpenes = []
        if self.dominant:
            terpenes.append(self.dominant)
        terpenes.extend(self.secondary)
        return terpenes

    def overlap_with(self, other: "TerpeneProfile") -> list[Terpene]:
        """Find common terpenes between two profiles."""
        self_terps = set(self.get_all_terpenes())
        other_terps = set(other.get_all_terpenes())
        return list(self_terps & other_terps)

    def similarity_score(self, other: "TerpeneProfile") -> float:
        """Calculate similarity score (0.0 to 1.0) with another profile."""
        self_terps = set(self.get_all_terpenes())
        other_terps = set(other.get_all_terpenes())

        if not self_terps and not other_terps:
            return 1.0
        if not self_terps or not other_terps:
            return 0.0

        intersection = len(self_terps & other_terps)
        union = len(self_terps | other_terps)

        # Jaccard similarity
        base_score = intersection / union

        # Bonus for matching dominant terpene
        if self.dominant and other.dominant and self.dominant == other.dominant:
            base_score = min(1.0, base_score + 0.2)

        return base_score


@dataclass
class EffectProfile:
    """Represents a strain's effects and medical benefits."""
    feelings: list[str] = field(default_factory=list)
    helps_with: list[str] = field(default_factory=list)

    # Percentage scores for each feeling (0.0 to 1.0)
    feeling_scores: dict[str, float] = field(default_factory=dict)
    condition_scores: dict[str, float] = field(default_factory=dict)

    def has_feeling(self, feeling: str) -> bool:
        """Check if strain produces a specific feeling."""
        return feeling.lower() in [f.lower() for f in self.feelings]

    def helps_condition(self, condition: str) -> bool:
        """Check if strain helps with a specific condition."""
        return condition.lower() in [c.lower() for c in self.helps_with]

    def feeling_match_score(self, desired_feelings: list[str]) -> float:
        """Calculate how well this strain matches desired feelings."""
        if not desired_feelings:
            return 1.0

        matches = sum(1 for f in desired_feelings if self.has_feeling(f))
        return matches / len(desired_feelings)

    def condition_match_score(self, conditions: list[str]) -> float:
        """Calculate how well this strain helps with specified conditions."""
        if not conditions:
            return 1.0

        matches = sum(1 for c in conditions if self.helps_condition(c))
        return matches / len(conditions)


@dataclass
class Strain:
    """Represents a cannabis strain with all its properties."""
    name: str
    strain_type: StrainType
    terpene_profile: TerpeneProfile
    effect_profile: EffectProfile

    # Optional metadata
    popularity_score: float = 0.5  # 0.0 to 1.0

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Strain):
            return self.name == other.name
        return False

    def similarity_to(self, other: "Strain") -> float:
        """Calculate overall similarity score to another strain."""
        # Terpene similarity (40% weight)
        terpene_sim = self.terpene_profile.similarity_score(other.terpene_profile)

        # Effect similarity (35% weight) - Jaccard on feelings
        self_feelings = set(self.effect_profile.feelings)
        other_feelings = set(other.effect_profile.feelings)
        if self_feelings or other_feelings:
            effect_sim = len(self_feelings & other_feelings) / len(self_feelings | other_feelings)
        else:
            effect_sim = 0.5

        # Type similarity (25% weight)
        if self.strain_type == other.strain_type:
            type_sim = 1.0
        elif StrainType.HYBRID in (self.strain_type, other.strain_type):
            type_sim = 0.5
        else:
            type_sim = 0.0

        return (terpene_sim * 0.40) + (effect_sim * 0.35) + (type_sim * 0.25)

    def to_dict(self) -> dict:
        """Convert strain to dictionary representation."""
        return {
            "name": self.name,
            "type": self.strain_type.value,
            "dominant_terpene": self.terpene_profile.dominant.value if self.terpene_profile.dominant else None,
            "terpene_description": self.terpene_profile.dominant_description,
            "secondary_terpenes": [t.value for t in self.terpene_profile.secondary],
            "feelings": self.effect_profile.feelings,
            "helps_with": self.effect_profile.helps_with,
        }


# =============================================================================
# DATA PARSER
# =============================================================================

class DataParser:
    """Parses the raw JSON data into structured Strain objects."""

    @staticmethod
    def parse_json_file(filepath: str) -> list[Strain]:
        """Load and parse the JSON data file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        return DataParser.parse_sheet_data(raw_data.get("Sheet1", []))

    @staticmethod
    def parse_sheet_data(rows: list[dict]) -> list[Strain]:
        """
        Parse the flattened row format into Strain objects.

        The data format has multiple rows per strain:
        - First row of a strain has: Name, Type, Dominant Terpene, Description
        - Subsequent rows have: additional Feelings and Helps With values
        """
        strains: dict[str, Strain] = {}

        # Skip header/metadata rows (first 4 rows typically)
        data_rows = rows[4:] if len(rows) > 4 else rows

        current_strain_name = None

        for row in data_rows:
            # Extract fields using the column mapping
            strain_name = str(row.get("TOTAL", "")).strip()
            strain_type_str = str(row.get("1054", "")).strip()
            feeling = str(row.get("Indica", "")).strip()
            helps_with = str(row.get("Sativa", "")).strip()
            dominant_terpene_str = str(row.get("Hybrid", "")).strip()
            terpene_desc = str(row.get("400", "")).strip()

            # Skip empty rows
            if not strain_name:
                continue

            # Check if this is a new strain or continuation
            if strain_name != current_strain_name:
                current_strain_name = strain_name

                # Create new strain if we haven't seen it
                if strain_name not in strains:
                    # Parse strain type
                    strain_type = StrainType.from_string(strain_type_str)

                    # Parse dominant terpene
                    dominant_terpene = Terpene.from_string(dominant_terpene_str)

                    # Create the strain
                    strains[strain_name] = Strain(
                        name=strain_name,
                        strain_type=strain_type,
                        terpene_profile=TerpeneProfile(
                            dominant=dominant_terpene,
                            dominant_description=terpene_desc,
                            secondary=[]
                        ),
                        effect_profile=EffectProfile(
                            feelings=[],
                            helps_with=[],
                            feeling_scores={},
                            condition_scores={}
                        )
                    )

            # Add feeling and condition to the current strain
            strain = strains.get(strain_name)
            if strain:
                if feeling and feeling not in strain.effect_profile.feelings:
                    strain.effect_profile.feelings.append(feeling)
                    # Try to extract score from percentage columns
                    try:
                        score = float(row.get("275", 0.5))
                        strain.effect_profile.feeling_scores[feeling] = score
                    except (ValueError, TypeError):
                        strain.effect_profile.feeling_scores[feeling] = 0.5

                if helps_with and helps_with not in strain.effect_profile.helps_with:
                    strain.effect_profile.helps_with.append(helps_with)
                    try:
                        score = float(row.get("172", 0.5))
                        strain.effect_profile.condition_scores[helps_with] = score
                    except (ValueError, TypeError):
                        strain.effect_profile.condition_scores[helps_with] = 0.5

        return list(strains.values())


# =============================================================================
# RECOMMENDATION ENGINE
# =============================================================================

@dataclass
class RecommendationResult:
    """Result from a recommendation query."""
    strain: Strain
    score: float
    match_reasons: list[str] = field(default_factory=list)

    def __lt__(self, other):
        return self.score < other.score


@dataclass
class BlendResult:
    """Result from a blending calculation."""
    strains: list[Strain]
    terpene_blend: dict[str, float]  # Terpene name -> percentage
    combined_effects: list[str]
    combined_conditions: list[str]
    compatibility_score: float


class RecommendationEngine:
    """
    Core recommendation engine for strain matching and blending.

    Algorithms:
    1. find_strains_by_feeling - Match desired feelings to strains
    2. find_strains_by_condition - Match medical conditions to strains
    3. find_similar_strains - Find strains similar to a given strain
    4. calculate_blend - Calculate optimal blend from multiple strains
    5. recommend - Multi-factor recommendation with weighted scoring
    """

    def __init__(self, strains: list[Strain]):
        self.strains = strains
        self._build_indexes()

    def _build_indexes(self):
        """Build lookup indexes for fast querying."""
        # Index by strain type
        self.by_type: dict[StrainType, list[Strain]] = {}
        for strain in self.strains:
            if strain.strain_type not in self.by_type:
                self.by_type[strain.strain_type] = []
            self.by_type[strain.strain_type].append(strain)

        # Index by dominant terpene
        self.by_terpene: dict[Terpene, list[Strain]] = {}
        for strain in self.strains:
            if strain.terpene_profile.dominant:
                terp = strain.terpene_profile.dominant
                if terp not in self.by_terpene:
                    self.by_terpene[terp] = []
                self.by_terpene[terp].append(strain)

        # Index by feeling
        self.by_feeling: dict[str, list[Strain]] = {}
        for strain in self.strains:
            for feeling in strain.effect_profile.feelings:
                feeling_lower = feeling.lower()
                if feeling_lower not in self.by_feeling:
                    self.by_feeling[feeling_lower] = []
                self.by_feeling[feeling_lower].append(strain)

        # Index by condition
        self.by_condition: dict[str, list[Strain]] = {}
        for strain in self.strains:
            for condition in strain.effect_profile.helps_with:
                condition_lower = condition.lower()
                if condition_lower not in self.by_condition:
                    self.by_condition[condition_lower] = []
                self.by_condition[condition_lower].append(strain)

        # Index by name for fast lookup
        self.by_name: dict[str, Strain] = {s.name.lower(): s for s in self.strains}

    def get_strain(self, name: str) -> Optional[Strain]:
        """Get a strain by name (case-insensitive)."""
        return self.by_name.get(name.lower())

    # -------------------------------------------------------------------------
    # ALGORITHM 1: Find Strains by Feeling
    # -------------------------------------------------------------------------

    def find_strains_by_feeling(
        self,
        feelings: list[str],
        strain_type: Optional[StrainType] = None,
        limit: int = 10
    ) -> list[RecommendationResult]:
        """
        Find strains that produce the specified feelings.

        Algorithm:
        1. For each feeling, get candidate strains from index
        2. Score each strain by: (matched feelings / total requested)
        3. Optionally filter by strain type
        4. Sort by score and return top N
        """
        if not feelings:
            return []

        # Get candidate strains
        candidates: Counter[Strain] = Counter()
        for feeling in feelings:
            feeling_lower = feeling.lower()
            for strain in self.by_feeling.get(feeling_lower, []):
                candidates[strain] += 1

        # Score and filter
        results = []
        for strain, match_count in candidates.items():
            # Filter by type if specified
            if strain_type and strain.strain_type != strain_type:
                continue

            # Calculate score
            base_score = match_count / len(feelings)

            # Bonus for feeling intensity scores
            intensity_bonus = 0
            for feeling in feelings:
                score = strain.effect_profile.feeling_scores.get(feeling, 0)
                intensity_bonus += score * 0.1

            final_score = min(1.0, base_score + intensity_bonus)

            # Build match reasons
            matched = [f for f in feelings if strain.effect_profile.has_feeling(f)]
            reasons = [f"Produces: {', '.join(matched)}"]
            if strain.terpene_profile.dominant:
                reasons.append(f"Dominant terpene: {strain.terpene_profile.dominant.value}")

            results.append(RecommendationResult(
                strain=strain,
                score=final_score,
                match_reasons=reasons
            ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    # -------------------------------------------------------------------------
    # ALGORITHM 2: Find Strains by Medical Condition
    # -------------------------------------------------------------------------

    def find_strains_by_condition(
        self,
        conditions: list[str],
        strain_type: Optional[StrainType] = None,
        limit: int = 10
    ) -> list[RecommendationResult]:
        """
        Find strains that help with specified medical conditions.

        Algorithm:
        1. For each condition, get candidate strains from index
        2. Score by: (matched conditions / total requested) * condition_score
        3. Apply strain type filter if specified
        4. Sort and return top N
        """
        if not conditions:
            return []

        candidates: Counter[Strain] = Counter()
        for condition in conditions:
            condition_lower = condition.lower()
            for strain in self.by_condition.get(condition_lower, []):
                candidates[strain] += 1

        results = []
        for strain, match_count in candidates.items():
            if strain_type and strain.strain_type != strain_type:
                continue

            # Base score from match count
            base_score = match_count / len(conditions)

            # Weighted bonus from condition effectiveness scores
            effectiveness_bonus = 0
            for condition in conditions:
                score = strain.effect_profile.condition_scores.get(condition, 0)
                effectiveness_bonus += score * 0.15

            final_score = min(1.0, base_score + effectiveness_bonus)

            matched = [c for c in conditions if strain.effect_profile.helps_condition(c)]
            reasons = [f"Helps with: {', '.join(matched)}"]

            results.append(RecommendationResult(
                strain=strain,
                score=final_score,
                match_reasons=reasons
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    # -------------------------------------------------------------------------
    # ALGORITHM 3: Find Similar Strains
    # -------------------------------------------------------------------------

    def find_similar_strains(
        self,
        strain: Strain | str,
        limit: int = 10,
        exclude_self: bool = True
    ) -> list[RecommendationResult]:
        """
        Find strains similar to the given strain.

        Algorithm:
        1. Get the target strain's profile
        2. Calculate similarity score with all other strains using:
           - Terpene profile similarity (Jaccard + dominant bonus)
           - Effect profile similarity (Jaccard on feelings)
           - Type compatibility score
        3. Combine with weights: 40% terpene, 35% effect, 25% type
        """
        # Resolve strain if given as string
        if isinstance(strain, str):
            target = self.get_strain(strain)
            if not target:
                return []
        else:
            target = strain

        results = []
        for candidate in self.strains:
            if exclude_self and candidate.name == target.name:
                continue

            similarity = target.similarity_to(candidate)

            # Build reasons
            reasons = []
            common_terps = target.terpene_profile.overlap_with(candidate.terpene_profile)
            if common_terps:
                reasons.append(f"Shared terpenes: {', '.join(t.value for t in common_terps)}")

            common_feelings = set(target.effect_profile.feelings) & set(candidate.effect_profile.feelings)
            if common_feelings:
                reasons.append(f"Shared effects: {', '.join(list(common_feelings)[:3])}")

            if target.strain_type == candidate.strain_type:
                reasons.append(f"Same type: {target.strain_type.value}")

            results.append(RecommendationResult(
                strain=candidate,
                score=similarity,
                match_reasons=reasons
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    # -------------------------------------------------------------------------
    # ALGORITHM 4: Calculate Blend
    # -------------------------------------------------------------------------

    def calculate_blend(self, strains: list[Strain | str]) -> BlendResult:
        """
        Calculate the optimal blend profile from multiple strains.

        Algorithm:
        1. Collect all terpenes from input strains
        2. Weight terpenes: dominant = 2x, secondary = 1x
        3. Calculate percentage contribution of each terpene
        4. Combine effect profiles (union of all effects)
        5. Calculate blend compatibility score
        """
        # Resolve strain names to objects
        resolved_strains = []
        for s in strains:
            if isinstance(s, str):
                strain = self.get_strain(s)
                if strain:
                    resolved_strains.append(strain)
            else:
                resolved_strains.append(s)

        if not resolved_strains:
            return BlendResult(
                strains=[],
                terpene_blend={},
                combined_effects=[],
                combined_conditions=[],
                compatibility_score=0.0
            )

        # Count terpenes with weighting
        terpene_weights: Counter[str] = Counter()
        for strain in resolved_strains:
            # Dominant terpene gets 2x weight
            if strain.terpene_profile.dominant:
                terpene_weights[strain.terpene_profile.dominant.value] += 2
            # Secondary terpenes get 1x weight
            for terp in strain.terpene_profile.secondary:
                terpene_weights[terp.value] += 1

        # Convert to percentages
        total_weight = sum(terpene_weights.values())
        terpene_blend = {}
        if total_weight > 0:
            for terp, weight in terpene_weights.items():
                terpene_blend[terp] = round(weight / total_weight * 100, 1)

        # Combine effects (union)
        all_feelings: set[str] = set()
        all_conditions: set[str] = set()
        for strain in resolved_strains:
            all_feelings.update(strain.effect_profile.feelings)
            all_conditions.update(strain.effect_profile.helps_with)

        # Calculate compatibility score
        # Based on pairwise similarity between all strains
        if len(resolved_strains) >= 2:
            similarities = []
            for i, s1 in enumerate(resolved_strains):
                for s2 in resolved_strains[i+1:]:
                    similarities.append(s1.similarity_to(s2))
            compatibility_score = sum(similarities) / len(similarities) if similarities else 1.0
        else:
            compatibility_score = 1.0

        return BlendResult(
            strains=resolved_strains,
            terpene_blend=terpene_blend,
            combined_effects=sorted(all_feelings),
            combined_conditions=sorted(all_conditions),
            compatibility_score=round(compatibility_score, 3)
        )

    # -------------------------------------------------------------------------
    # ALGORITHM 5: Multi-Factor Recommendation
    # -------------------------------------------------------------------------

    def recommend(
        self,
        feelings: Optional[list[str]] = None,
        conditions: Optional[list[str]] = None,
        preferred_terpenes: Optional[list[str]] = None,
        strain_type: Optional[StrainType] = None,
        avoid_feelings: Optional[list[str]] = None,
        limit: int = 10,
        weights: Optional[dict[str, float]] = None
    ) -> list[RecommendationResult]:
        """
        Advanced multi-factor recommendation with customizable weights.

        Algorithm:
        1. Score each strain on multiple dimensions:
           - Feeling match (default 35%)
           - Condition match (default 35%)
           - Terpene preference (default 20%)
           - Type preference (default 10%)
        2. Apply negative scoring for avoided feelings
        3. Combine weighted scores
        4. Sort and return top N

        Parameters:
        -----------
        feelings : list[str], optional
            Desired effects/feelings
        conditions : list[str], optional
            Medical conditions to address
        preferred_terpenes : list[str], optional
            Preferred terpene names
        strain_type : StrainType, optional
            Preferred strain type (or None for all)
        avoid_feelings : list[str], optional
            Effects to avoid (e.g., "Sleepy" if need to stay alert)
        limit : int
            Maximum results to return
        weights : dict[str, float], optional
            Custom weights for scoring dimensions
            Keys: "feelings", "conditions", "terpenes", "type"
        """
        # Default weights
        w = weights or {
            "feelings": 0.35,
            "conditions": 0.35,
            "terpenes": 0.20,
            "type": 0.10
        }

        results = []

        for strain in self.strains:
            score = 0.0
            reasons = []

            # 1. Feeling match score
            if feelings:
                feeling_score = strain.effect_profile.feeling_match_score(feelings)
                score += feeling_score * w.get("feelings", 0.35)
                if feeling_score > 0:
                    matched = [f for f in feelings if strain.effect_profile.has_feeling(f)]
                    if matched:
                        reasons.append(f"Feelings: {', '.join(matched)}")
            else:
                # No feeling preference, give neutral score
                score += 0.5 * w.get("feelings", 0.35)

            # 2. Condition match score
            if conditions:
                condition_score = strain.effect_profile.condition_match_score(conditions)
                score += condition_score * w.get("conditions", 0.35)
                if condition_score > 0:
                    matched = [c for c in conditions if strain.effect_profile.helps_condition(c)]
                    if matched:
                        reasons.append(f"Helps: {', '.join(matched)}")
            else:
                score += 0.5 * w.get("conditions", 0.35)

            # 3. Terpene preference score
            if preferred_terpenes:
                strain_terps = [t.value.lower() for t in strain.terpene_profile.get_all_terpenes()]
                pref_terps = [t.lower() for t in preferred_terpenes]
                matches = sum(1 for t in pref_terps if t in strain_terps)
                terpene_score = matches / len(preferred_terpenes) if preferred_terpenes else 0
                score += terpene_score * w.get("terpenes", 0.20)
                if strain.terpene_profile.dominant:
                    reasons.append(f"Terpene: {strain.terpene_profile.dominant.value}")
            else:
                score += 0.5 * w.get("terpenes", 0.20)

            # 4. Type preference score
            if strain_type:
                if strain.strain_type == strain_type:
                    type_score = 1.0
                elif strain.strain_type == StrainType.HYBRID:
                    type_score = 0.5  # Hybrids are partial match
                else:
                    type_score = 0.0
                score += type_score * w.get("type", 0.10)
            else:
                score += 0.5 * w.get("type", 0.10)

            # 5. Penalty for avoided feelings
            if avoid_feelings:
                for avoid in avoid_feelings:
                    if strain.effect_profile.has_feeling(avoid):
                        score -= 0.2  # Penalty per avoided feeling
                        reasons.append(f"Warning: may cause {avoid}")

            # Clamp score to [0, 1]
            score = max(0.0, min(1.0, score))

            results.append(RecommendationResult(
                strain=strain,
                score=score,
                match_reasons=reasons
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    # -------------------------------------------------------------------------
    # ALGORITHM 6: Terpene-to-Effect Analysis
    # -------------------------------------------------------------------------

    def analyze_terpene_effects(self, terpene: Terpene | str) -> dict:
        """
        Analyze what effects are most commonly associated with a terpene.

        Algorithm:
        1. Find all strains with this terpene as dominant
        2. Count frequency of each feeling across those strains
        3. Count frequency of each condition across those strains
        4. Return sorted analysis
        """
        # Resolve terpene
        if isinstance(terpene, str):
            terpene_obj = Terpene.from_string(terpene)
            if not terpene_obj:
                return {"error": f"Unknown terpene: {terpene}"}
        else:
            terpene_obj = terpene

        strains = self.by_terpene.get(terpene_obj, [])

        feeling_counts: Counter[str] = Counter()
        condition_counts: Counter[str] = Counter()

        for strain in strains:
            for feeling in strain.effect_profile.feelings:
                feeling_counts[feeling] += 1
            for condition in strain.effect_profile.helps_with:
                condition_counts[condition] += 1

        total = len(strains) if strains else 1

        return {
            "terpene": terpene_obj.value,
            "description": terpene_obj.description,
            "strain_count": len(strains),
            "top_feelings": [
                {"feeling": f, "frequency": round(c / total * 100, 1)}
                for f, c in feeling_counts.most_common(5)
            ],
            "top_conditions": [
                {"condition": c, "frequency": round(cnt / total * 100, 1)}
                for c, cnt in condition_counts.most_common(5)
            ]
        }

    # -------------------------------------------------------------------------
    # ALGORITHM 7: Effect-to-Terpene Mapping
    # -------------------------------------------------------------------------

    def find_terpenes_for_effect(self, feeling: str) -> dict:
        """
        Find which terpenes are most associated with a desired effect.

        Algorithm:
        1. Find all strains that produce this feeling
        2. Count frequency of each dominant terpene
        3. Return ranked terpene recommendations
        """
        feeling_lower = feeling.lower()
        strains = self.by_feeling.get(feeling_lower, [])

        terpene_counts: Counter[str] = Counter()
        for strain in strains:
            if strain.terpene_profile.dominant:
                terpene_counts[strain.terpene_profile.dominant.value] += 1

        total = len(strains) if strains else 1

        recommendations = []
        for terp_name, count in terpene_counts.most_common():
            terp = Terpene.from_string(terp_name)
            recommendations.append({
                "terpene": terp_name,
                "description": terp.description if terp else "",
                "frequency": round(count / total * 100, 1),
                "strain_count": count
            })

        return {
            "target_feeling": feeling,
            "total_strains_with_feeling": len(strains),
            "recommended_terpenes": recommendations
        }

    # -------------------------------------------------------------------------
    # STATISTICS AND ANALYTICS
    # -------------------------------------------------------------------------

    def get_statistics(self) -> dict:
        """Get database statistics."""
        type_counts = {t.value: len(strains) for t, strains in self.by_type.items()}
        terpene_counts = {t.value: len(strains) for t, strains in self.by_terpene.items()}

        all_feelings = set()
        all_conditions = set()
        for strain in self.strains:
            all_feelings.update(strain.effect_profile.feelings)
            all_conditions.update(strain.effect_profile.helps_with)

        return {
            "total_strains": len(self.strains),
            "by_type": type_counts,
            "by_dominant_terpene": terpene_counts,
            "unique_feelings": sorted(all_feelings),
            "unique_conditions": sorted(all_conditions),
            "feeling_count": len(all_feelings),
            "condition_count": len(all_conditions)
        }


# =============================================================================
# SMART VAPE ENGINE (Main Interface)
# =============================================================================

class SmartVapeEngine:
    """
    Main interface for the SmartVape recommendation system.

    This class provides a high-level API for all recommendation features.
    """

    def __init__(self, data_path: Optional[str] = None):
        """
        Initialize the SmartVape engine.

        Parameters:
        -----------
        data_path : str, optional
            Path to the JSON data file. If not provided, must call load_data().
        """
        self.strains: list[Strain] = []
        self.engine: Optional[RecommendationEngine] = None

        if data_path:
            self.load_data(data_path)

    def load_data(self, filepath: str):
        """Load strain data from JSON file."""
        self.strains = DataParser.parse_json_file(filepath)
        self.engine = RecommendationEngine(self.strains)
        # Vendored change (ReviewGuide): stdout print silenced for server use
        import logging
        logging.getLogger(__name__).info(f"[smartvape] Loaded {len(self.strains)} strains")

    def load_strains(self, strains: list[Strain]):
        """Load strains directly from a list."""
        self.strains = strains
        self.engine = RecommendationEngine(strains)

    def _ensure_loaded(self):
        """Ensure data is loaded."""
        if not self.engine:
            raise RuntimeError("No data loaded. Call load_data() first.")

    # -------------------------------------------------------------------------
    # User-Facing API Methods
    # -------------------------------------------------------------------------

    def get_strain(self, name: str) -> Optional[Strain]:
        """Get a strain by name."""
        self._ensure_loaded()
        return self.engine.get_strain(name)

    def search_strains(self, query: str, limit: int = 10) -> list[Strain]:
        """Search for strains by partial name match."""
        self._ensure_loaded()
        query_lower = query.lower()
        matches = [s for s in self.strains if query_lower in s.name.lower()]
        return matches[:limit]

    def recommend_by_mood(
        self,
        moods: list[str],
        strain_type: Optional[str] = None,
        limit: int = 10
    ) -> list[RecommendationResult]:
        """
        Get strain recommendations based on desired mood/feelings.

        Example:
            engine.recommend_by_mood(["Happy", "Relaxed"], strain_type="Indica")
        """
        self._ensure_loaded()
        type_enum = StrainType.from_string(strain_type) if strain_type else None
        return self.engine.find_strains_by_feeling(moods, type_enum, limit)

    def recommend_by_condition(
        self,
        conditions: list[str],
        strain_type: Optional[str] = None,
        limit: int = 10
    ) -> list[RecommendationResult]:
        """
        Get strain recommendations for medical conditions.

        Example:
            engine.recommend_by_condition(["Anxiety", "Insomnia"])
        """
        self._ensure_loaded()
        type_enum = StrainType.from_string(strain_type) if strain_type else None
        return self.engine.find_strains_by_condition(conditions, type_enum, limit)

    def find_similar(
        self,
        strain_name: str,
        limit: int = 10
    ) -> list[RecommendationResult]:
        """
        Find strains similar to a given strain.

        Example:
            engine.find_similar("Blue Dream")
        """
        self._ensure_loaded()
        return self.engine.find_similar_strains(strain_name, limit)

    def create_blend(self, strain_names: list[str]) -> BlendResult:
        """
        Create a blend profile from multiple strains.

        Example:
            engine.create_blend(["GG4", "Wedding Cake", "Blue Dream"])
        """
        self._ensure_loaded()
        return self.engine.calculate_blend(strain_names)

    def advanced_recommend(
        self,
        feelings: Optional[list[str]] = None,
        conditions: Optional[list[str]] = None,
        terpenes: Optional[list[str]] = None,
        strain_type: Optional[str] = None,
        avoid: Optional[list[str]] = None,
        limit: int = 10
    ) -> list[RecommendationResult]:
        """
        Advanced multi-factor recommendation.

        Example:
            engine.advanced_recommend(
                feelings=["Happy", "Creative"],
                conditions=["Anxiety"],
                terpenes=["Limonene"],
                strain_type="Sativa",
                avoid=["Sleepy"]
            )
        """
        self._ensure_loaded()
        type_enum = StrainType.from_string(strain_type) if strain_type else None
        return self.engine.recommend(
            feelings=feelings,
            conditions=conditions,
            preferred_terpenes=terpenes,
            strain_type=type_enum,
            avoid_feelings=avoid,
            limit=limit
        )

    def analyze_terpene(self, terpene_name: str) -> dict:
        """
        Analyze effects associated with a terpene.

        Example:
            engine.analyze_terpene("Myrcene")
        """
        self._ensure_loaded()
        return self.engine.analyze_terpene_effects(terpene_name)

    def terpenes_for_effect(self, effect: str) -> dict:
        """
        Find best terpenes for a desired effect.

        Example:
            engine.terpenes_for_effect("Relaxed")
        """
        self._ensure_loaded()
        return self.engine.find_terpenes_for_effect(effect)

    def get_stats(self) -> dict:
        """Get database statistics."""
        self._ensure_loaded()
        return self.engine.get_statistics()

    def list_all_feelings(self) -> list[str]:
        """Get list of all unique feelings in the database."""
        self._ensure_loaded()
        feelings = set()
        for strain in self.strains:
            feelings.update(strain.effect_profile.feelings)
        return sorted(feelings)

    def list_all_conditions(self) -> list[str]:
        """Get list of all unique conditions in the database."""
        self._ensure_loaded()
        conditions = set()
        for strain in self.strains:
            conditions.update(strain.effect_profile.helps_with)
        return sorted(conditions)

    def list_all_terpenes(self) -> list[str]:
        """Get list of all terpene names."""
        return [t.value for t in Terpene]


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    import os

    # Initialize engine
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(script_dir, "json_tool.json")

    print("=" * 60)
    print("SmartVape Recommendation Engine v2.0")
    print("=" * 60)

    # Load data
    engine = SmartVapeEngine(data_path)

    # Display statistics
    stats = engine.get_stats()
    print(f"\nDatabase Statistics:")
    print(f"  Total Strains: {stats['total_strains']}")
    print(f"  By Type: {stats['by_type']}")
    print(f"  Unique Feelings: {stats['feeling_count']}")
    print(f"  Unique Conditions: {stats['condition_count']}")

    # Example 1: Recommend by mood
    print("\n" + "-" * 60)
    print("EXAMPLE 1: Recommend strains for 'Happy' and 'Relaxed' mood")
    print("-" * 60)
    results = engine.recommend_by_mood(["Happy", "Relaxed"], limit=5)
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.strain.name} ({r.strain.strain_type.value})")
        print(f"     Score: {r.score:.2f} | {', '.join(r.match_reasons)}")

    # Example 2: Recommend by condition
    print("\n" + "-" * 60)
    print("EXAMPLE 2: Recommend strains for Anxiety and Stress")
    print("-" * 60)
    results = engine.recommend_by_condition(["Anxiety", "Stress"], limit=5)
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.strain.name} ({r.strain.strain_type.value})")
        print(f"     Score: {r.score:.2f} | {', '.join(r.match_reasons)}")

    # Example 3: Find similar strains
    print("\n" + "-" * 60)
    print("EXAMPLE 3: Find strains similar to 'Blue Dream'")
    print("-" * 60)
    results = engine.find_similar("Blue Dream", limit=5)
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.strain.name} (Similarity: {r.score:.2f})")
        print(f"     {', '.join(r.match_reasons)}")

    # Example 4: Create a blend
    print("\n" + "-" * 60)
    print("EXAMPLE 4: Create blend from GG4, Wedding Cake, Runtz")
    print("-" * 60)
    blend = engine.create_blend(["GG4", "Wedding Cake", "Runtz"])
    print(f"  Terpene Profile: {blend.terpene_blend}")
    print(f"  Combined Effects: {', '.join(blend.combined_effects[:5])}...")
    print(f"  Compatibility Score: {blend.compatibility_score}")

    # Example 5: Analyze terpene
    print("\n" + "-" * 60)
    print("EXAMPLE 5: Analyze Myrcene effects")
    print("-" * 60)
    analysis = engine.analyze_terpene("Myrcene")
    print(f"  Strains with Myrcene: {analysis['strain_count']}")
    print(f"  Top Feelings: {[f['feeling'] for f in analysis['top_feelings'][:3]]}")
    print(f"  Top Conditions: {[c['condition'] for c in analysis['top_conditions'][:3]]}")

    # Example 6: Advanced recommendation
    print("\n" + "-" * 60)
    print("EXAMPLE 6: Advanced search - Creative Sativa, no Sleepy")
    print("-" * 60)
    results = engine.advanced_recommend(
        feelings=["Creative", "Energetic"],
        strain_type="Sativa",
        avoid=["Sleepy"],
        limit=5
    )
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.strain.name} - Score: {r.score:.2f}")

    print("\n" + "=" * 60)
    print("Engine ready for use!")
    print("=" * 60)
