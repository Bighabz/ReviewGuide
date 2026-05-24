"""
Product Comparison Tool

Generates HTML comparison table using LLM based on product names.
Runs after product_extractor, before product_normalize/affiliate.
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
    "name": "product_comparison",
    "intent": "product",
    "purpose": "Compare products side-by-side",
    "tools": {
        "pre": ["product_extractor"],  # Needs product_names from extractor
        # "post": ["product_evidence"]  # Compose is auto-added at end of intent
        "post": ["product_normalize"]  # Compose is auto-added at end of intent
    },
    "produces": ["comparison_html", "comparison_data"],
    "citation_message": "Generating product comparison..."
}


@tool_error_handler(tool_name="product_comparison", error_message="Failed to compare products")
async def product_comparison(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate HTML comparison table using LLM.

    Reads from state:
        - product_names: List of product names from extractor

    Writes to state:
        - comparison_html: HTML table for browser display
        - comparison_data: Structured comparison data

    Returns:
        {
            "comparison_html": str,
            "comparison_data": {...},
            "success": bool
        }
    """
    from app.core.centralized_logger import get_logger
    from app.services.model_service import model_service
    from app.core.config import settings
    from app.utils.date_utils import get_current_date_str

    logger = get_logger(__name__)

    try:
        # Read product names from extractor
        product_names = state.get("product_names", [])

        if not product_names or len(product_names) < 2:
            logger.info(f"[product_comparison] Not enough products to compare: {product_names}")
            return {
                "comparison_html": None,
                "comparison_data": None,
                "success": True
            }

        logger.info(f"[product_comparison] Generating comparison for: {product_names}")

        # Generate HTML comparison using LLM
        comparison_prompt = f"""Generate a detailed HTML comparison table for these products:

Products: {json.dumps(product_names)}

Identify the product category and include 8-10 key specifications that matter most for comparing these products, plus estimated price range.

Requirements:
1. Return ONLY valid HTML (no markdown, no ```html blocks)
2. Use inline CSS for modern, clean styling
3. Design guidelines:
   - Use a card-style container with rounded corners (border-radius: 16px)
   - Header row: gradient background (#667eea to #764ba2), white text, sticky
   - Product columns: equal width, centered text
   - Spec rows: alternating backgrounds (#ffffff and #f8fafc)
   - Spec labels: left-aligned, font-weight 600, color #374151
   - Values: centered, color #1f2937
   - Highlight better specs with subtle green background (#ecfdf5) or checkmark
   - Add subtle shadows and borders for depth
   - Padding: 16px for cells
   - Font: system-ui, -apple-system, sans-serif
4. Include a verdict/summary section at the bottom with:
   - Background: #f0f9ff (light blue)
   - Brief recommendation for each product (who should buy it)

Use this exact structure:
<div style="font-family: system-ui, -apple-system, sans-serif; max-width: 100%; overflow-x: auto;">
  <table style="width: 100%; border-collapse: separate; border-spacing: 0; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);">
    <thead>
      <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
        <th style="padding: 16px 20px; text-align: left; color: white; font-weight: 600; font-size: 14px; text-transform: uppercase; letter-spacing: 0.05em;">Feature</th>
        <th style="padding: 16px 20px; text-align: center; color: white; font-weight: 600; font-size: 15px;">Product 1</th>
        <th style="padding: 16px 20px; text-align: center; color: white; font-weight: 600; font-size: 15px;">Product 2</th>
      </tr>
    </thead>
    <tbody>
      <tr style="background: #ffffff;">
        <td style="padding: 14px 20px; font-weight: 600; color: #374151; border-bottom: 1px solid #e5e7eb;">Display</td>
        <td style="padding: 14px 20px; text-align: center; color: #1f2937; border-bottom: 1px solid #e5e7eb;">...</td>
        <td style="padding: 14px 20px; text-align: center; color: #1f2937; border-bottom: 1px solid #e5e7eb;">...</td>
      </tr>
      <!-- alternate row backgrounds between #ffffff and #f8fafc -->
    </tbody>
  </table>
  <div style="margin-top: 16px; padding: 16px 20px; background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); border-radius: 12px; border-left: 4px solid #0ea5e9;">
    <div style="font-weight: 600; color: #0369a1; margin-bottom: 8px; font-size: 15px;">💡 Verdict</div>
    <p style="margin: 0; color: #1e40af; font-size: 14px; line-height: 1.6;">...</p>
  </div>
</div>

Return ONLY the HTML, nothing else."""

        from app.services.prompts.voice import build_system_prompt
        comparison_system_prefix = (
            f"Today's date is {get_current_date_str()}.\n"
            "If discussing specific products or models that may have been released after your training "
            "cutoff, briefly acknowledge that you may not have the most current specifications or pricing.\n\n"
        )
        comparison_role = comparison_system_prefix + (
            "Generate an accurate, well-formatted HTML comparison table for the "
            "given products. Return only valid HTML with inline CSS — no prose "
            "preamble, no markdown. The verdict paragraph inside the HTML should "
            "be opinionated and specific, not glazing."
        )
        html_response = await model_service.generate(
            messages=[
                {"role": "system", "content": build_system_prompt(role_prompt=comparison_role, kind="snippet")},
                {"role": "user", "content": comparison_prompt}
            ],
            model=settings.COMPOSER_MODEL,
            temperature=0.3,
            max_tokens=3000,
            agent_name="product_comparison"
        )

        # Clean up response - remove any markdown wrappers
        comparison_html = html_response.strip()
        if comparison_html.startswith("```html"):
            comparison_html = comparison_html[7:]
        if comparison_html.startswith("```"):
            comparison_html = comparison_html[3:]
        if comparison_html.endswith("```"):
            comparison_html = comparison_html[:-3]
        comparison_html = comparison_html.strip()

        # Build comparison data structure
        comparison_data = {
            "products": product_names,
            "html": comparison_html,
            "type": "spec_comparison"
        }

        logger.info(f"[product_comparison] Generated HTML comparison ({len(comparison_html)} chars) for {len(product_names)} products")

        return {
            "comparison_html": comparison_html,
            "comparison_data": comparison_data,
            "success": True
        }

    except Exception as e:
        logger.error(f"[product_comparison] Error: {e}", exc_info=True)
        return {
            "comparison_html": None,
            "comparison_data": None,
            "error": str(e),
            "success": False
        }
