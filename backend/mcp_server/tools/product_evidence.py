"""
Product Evidence Tool

Analyzes product reviews to extract pros, cons, and evidence.
Uses ModelService directly for LLM calls.
"""

import sys
import os
import json
from typing import Dict, Any, List
from app.core.error_manager import tool_error_handler

# Add backend to path (portable path)
backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Tool contract for planner
TOOL_CONTRACT = {
    "name": "product_evidence",
    "intent": "product",
    "purpose": "Analyzes customer reviews and expert opinions to extract structured insights about products. This tool gathers evidence-based information including pros, cons, common complaints, standout features, durability concerns, and overall sentiment. Use this when user wants to understand product quality, reliability, or user experiences before making a purchase decision.",
    "tools": {
        "pre": [],  # Needs product_names from search
        "post": ["product_normalize"]  # Compose is auto-added at end of intent
    },
    "produces": ["review_aspects"],
    "citation_message": "Pulling the receipts…",
    "is_default": True
}


@tool_error_handler(tool_name="product_evidence", error_message="Failed to get product evidence")
async def product_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze product reviews to extract evidence-based insights.

    Reads from state:
        - product_names: List of product names

    Writes to state:
        - review_aspects: Product analysis with pros/cons/ratings
        - evidence_citations: Source citations
        - confidence_score: Confidence in the analysis

    Returns:
        {
            "review_aspects": [...],
            "evidence_citations": [str],
            "confidence_score": float,
            "success": bool
        }
    """
    # Import here to avoid settings validation at module load
    from app.core.centralized_logger import get_logger
    from app.services.model_service import model_service
    from app.core.config import settings

    logger = get_logger(__name__)

    try:
        # Read from state
        product_names = state.get("product_names", [])

        logger.info(f"[product_evidence] Analyzing {len(product_names)} products")

        if not product_names:
            return {
                "review_aspects": [],
                "evidence_citations": [],
                "confidence_score": 0.0,
                "success": True
            }

        # Build context from product names
        products_list = "\n".join([f"{i+1}. {name}" for i, name in enumerate(product_names[:10])])

        # Build prompt for evidence extraction
        prompt = f"""Analyze these products and provide pros/cons based on known information:

{products_list}

For each product, provide:
1. **Pros** (positive aspects mentioned)
2. **Cons** (negative aspects or limitations mentioned)
3. **Overall impression** (rating 1-5)
4. **Evidence snippets** (direct quotes supporting your analysis)

Return ONLY valid JSON in this format:
{{
  "products": [
    {{
      "product_name": "Product Name",
      "pros": ["pro1", "pro2"],
      "cons": ["con1", "con2"],
      "rating": 4.5,
      "evidence": ["quote1", "quote2"]
    }}
  ]
}}
"""

        # Callbacks are automatically inherited from LangGraph context
        # Call LLM
        response = await model_service.generate(
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at analyzing product reviews and extracting evidence-based insights. Be objective and cite specific information."
                },
                {"role": "user", "content": prompt}
            ],
            model=settings.DEFAULT_MODEL,
            temperature=0.3,
            response_format={"type": "json_object"},
            agent_name="product_evidence"
        )

        # Parse response
        data = json.loads(response)
        product_list = data.get("products", [])

        # Format as review_aspects
        review_aspects = []
        evidence_citations = []

        for item in product_list:
            review_aspects.append({
                "product": item.get("product_name", "Unknown"),
                "pros": item.get("pros", []),
                "cons": item.get("cons", []),
                "rating": item.get("rating", 0.0),
                "evidence_snippets": item.get("evidence", [])
            })

            # Add citations
            for evidence in item.get("evidence", []):
                if evidence not in evidence_citations:
                    evidence_citations.append(evidence)

        # Calculate confidence based on amount of evidence
        confidence_score = min(1.0, len(evidence_citations) / 10)  # Max at 10 evidence pieces

        logger.info(f"[product_evidence] Extracted {len(review_aspects)} product analyses")

        return {
            "review_aspects": review_aspects,
            "evidence_citations": evidence_citations[:5],  # Limit citations
            "confidence_score": confidence_score,
            "success": True
        }

    except Exception as e:
        logger.error(f"[product_evidence] Error: {e}", exc_info=True)
        return {
            "review_aspects": [],
            "evidence_citations": [],
            "confidence_score": 0.0,
            "error": str(e),
            "success": False
        }
