"""
Serper Google Shopping Provider (+ optional Skimlinks monetization)

Surfaces REAL prices, product images, and merchant links from Google Shopping
via the existing Serper/SerpApi client. This replaces the `serper_shopping`
bolt-on that previously lived inside the product_affiliate tool — Google
Shopping is now a first-class provider in the registry like Amazon/eBay/CJ.

Monetization (affiliate provider harmony, Step 2):
- When SKIMLINKS_API_ENABLED and SKIMLINKS_PUBLISHER_ID are set, non-Amazon /
  non-eBay merchant URLs are wrapped with the Skimlinks redirect
  (go.skimresources.com) and become monetizable buy links.
- Without Skimlinks credentials the offers pass through unwrapped — they stay
  context-only (price/image backfill in product_compose), exactly the
  pre-refactor behavior. The provider is DORMANT-monetization by default.
- Amazon and eBay domains are never wrapped: those have direct affiliate
  programs (Amazon Associates / eBay EPN) that pay better than a sub-affiliate
  cut, and Skimlinks does not cover Amazon at all.
"""

import asyncio
from typing import List, Optional
from urllib.parse import quote, urlparse

from app.core.centralized_logger import get_logger
from app.core.config import settings
from app.services.affiliate.base import BaseAffiliateProvider, AffiliateProduct
from app.services.affiliate.registry import AffiliateProviderRegistry

logger = get_logger(__name__)

SKIMLINKS_REDIRECT_BASE = "https://go.skimresources.com/"

# Domains with direct affiliate programs — never wrapped with Skimlinks.
EXCLUDED_DOMAINS = (
    "amazon.com",
    "amazon.co.uk",
    "amazon.ca",
    "amazon.de",
    "amazon.fr",
    "amazon.it",
    "amazon.es",
    "amazon.co.jp",
    "amazon.in",
    "amazon.com.au",
    "amzn.to",
    "amzn.com",
    "ebay.com",
    "ebay.co.uk",
    "ebay.ca",
    "ebay.de",
    "ebay.fr",
    "ebay.it",
    "ebay.es",
    "ebay.com.au",
)

# Per-product Google Shopping lookup budget — same as the old bolt-on.
SHOPPING_TIMEOUT_S = 6


def _domain_of(url: str) -> str:
    """Hostname of a URL, lowercased, without a leading www."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _is_excluded_domain(url: str) -> bool:
    """True when the URL belongs to a direct-program merchant (Amazon/eBay)."""
    domain = _domain_of(url)
    if not domain:
        return False
    return any(domain == d or domain.endswith("." + d) for d in EXCLUDED_DOMAINS)


# required_env_vars is intentionally [] — the search gate lives inside
# search_products (settings.ENABLE_SERPAPI and settings.SERPAPI_API_KEY), which
# reads pydantic settings (.env file AND real env vars). The loader's env-var
# check only sees os.environ, which would wrongly skip this provider in local
# .env-file setups; the old bolt-on gated on settings, and behavior must match.
@AffiliateProviderRegistry.register(
    "serper_shopping",
    required_env_vars=[],
    optional_env_vars=["SERPAPI_API_KEY", "SKIMLINKS_PUBLISHER_ID"],
)
class SerperShoppingProvider(BaseAffiliateProvider):
    """
    Google Shopping (via Serper) as an affiliate provider.

    - search_products(query) → at most one real-priced offer per product
      (price, image, merchant, link) from Google Shopping.
    - Skimlinks wrapping of the merchant link when configured (see module
      docstring); raw pass-through otherwise.
    """

    def __init__(
        self,
        skimlinks_publisher_id: str = None,
        skimlinks_enabled: bool = None,
    ):
        self.skimlinks_publisher_id = (
            skimlinks_publisher_id
            if skimlinks_publisher_id is not None
            else settings.SKIMLINKS_PUBLISHER_ID
        )
        self.skimlinks_enabled = (
            skimlinks_enabled
            if skimlinks_enabled is not None
            else settings.SKIMLINKS_API_ENABLED
        )
        # Lazy — the Serper client touches Redis/settings at construction.
        self._client = None

        logger.info(
            f"SerperShopping provider initialized: "
            f"skimlinks={'on' if self._skimlinks_active else 'dormant'}"
        )

    @property
    def _skimlinks_active(self) -> bool:
        return bool(self.skimlinks_enabled and self.skimlinks_publisher_id)

    def _get_client(self):
        if self._client is None:
            from app.services.serpapi.client import SerpAPIClient

            self._client = SerpAPIClient()
        return self._client

    def get_provider_name(self) -> str:
        return "Google Shopping"

    def wrap_with_skimlinks(self, url: str) -> str:
        """Wrap a merchant URL with the Skimlinks redirect when active.

        Returns the URL unchanged when Skimlinks is dormant, the URL is empty,
        the merchant has a direct program (Amazon/eBay), or it's already wrapped.
        """
        if not url or not self._skimlinks_active:
            return url
        if _is_excluded_domain(url):
            return url
        if "skimresources.com" in _domain_of(url):
            return url
        return (
            f"{SKIMLINKS_REDIRECT_BASE}"
            f"?id={self.skimlinks_publisher_id}"
            f"&xs=1"
            f"&url={quote(url, safe='')}"
        )

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 10,
    ) -> List[AffiliateProduct]:
        """One real-priced Google Shopping offer for the product, or []."""
        # Same gate as the old product_affiliate bolt-on — settings-based so it
        # works identically with .env files (local) and real env vars (Railway).
        if not (settings.ENABLE_SERPAPI and settings.SERPAPI_API_KEY):
            return []

        try:
            offer = await asyncio.wait_for(
                self._get_client().search_shopping_offer(query),
                timeout=SHOPPING_TIMEOUT_S,
            )
        except Exception as e:
            logger.warning(
                f"[serper_shopping] Shopping lookup failed for '{query}': {e}"
            )
            return []

        if not offer or not offer.get("price"):
            return []

        raw_url = offer.get("url") or ""
        link = self.wrap_with_skimlinks(raw_url)
        if link != raw_url:
            logger.info(
                f"[serper_shopping] Skimlinks-wrapped offer for '{query}' "
                f"({_domain_of(raw_url)})"
            )

        return [
            AffiliateProduct(
                product_id=f"serper-{abs(hash(query)) % 10**10}",
                title=offer.get("title") or query,
                price=float(offer["price"]),
                currency=offer.get("currency") or "USD",
                affiliate_link=link,
                merchant=offer.get("merchant") or "Online",
                image_url=offer.get("image_url") or "",
                rating=offer.get("rating"),
                review_count=offer.get("review_count"),
                condition="new",
                source_url=raw_url,
            )
        ]

    async def generate_affiliate_link(
        self,
        product_id: str,
        campaign_id: Optional[str] = None,
        tracking_id: Optional[str] = None,
    ) -> str:
        """Links are generated inline during search (Skimlinks wrap); nothing to do."""
        return ""

    async def check_link_health(self, affiliate_link: str) -> bool:
        """Skimlinks redirects resolve at click time — treat non-empty as healthy."""
        return bool(affiliate_link)
