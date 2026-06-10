"""
eBay Affiliate Network Provider
Integrates with eBay Partner Network API for product search and affiliate link generation.
Supports mock mode (development) and real Browse API (production).
"""
from app.core.centralized_logger import get_logger
import httpx
import base64
import hashlib
import time
from typing import List, Dict, Any, Optional
from urllib.parse import quote, urlencode
from app.services.affiliate.base import BaseAffiliateProvider, AffiliateProduct
from app.services.affiliate.registry import AffiliateProviderRegistry
from app.core.config import settings

logger = get_logger(__name__)


# eBay-flavored category variations for mock data
EBAY_CATEGORY_VARIATIONS = {
    "laptop": [
        "Intel i7, 16GB, 512GB SSD - Free Shipping",
        "AMD Ryzen 7, 32GB, 1TB SSD - Top Rated Plus",
        "Intel i9, 64GB, 2TB SSD - Fast 'N Free",
        "AMD Ryzen 9, 16GB, 512GB - Certified Refurbished",
        "Intel i5, 8GB, 256GB SSD - Buy It Now",
    ],
    "computer": [
        "Intel i7, 32GB RAM, 1TB SSD Desktop - Free Shipping",
        "AMD Ryzen 9, 64GB RAM, 2TB NVMe Tower",
        "Intel Xeon, 128GB ECC, 4TB Workstation",
        "AMD Threadripper, 256GB RAM - Top Rated Seller",
        "Intel i9, 64GB, 2TB SSD Custom Build",
    ],
    "server": [
        "Dual Xeon, 256GB ECC, 8TB RAID - Tested",
        "AMD EPYC 64-Core, 512GB RAM - Seller Refurbished",
        "Intel Xeon W, 128GB, 4TB NVMe - Free Shipping",
        "GPU Server 4x RTX 4090, 256GB - Buy It Now",
        "Tower Server 64GB RAM, 2TB SSD - Top Rated",
    ],
    "gpu": [
        "RTX 4090 24GB GDDR6X - Free Shipping",
        "RTX 4080 Super 16GB - Top Rated Plus",
        "RTX 3090 Ti 24GB - Certified Refurbished",
        "AMD RX 7900 XTX 24GB - Buy It Now",
        "RTX A6000 48GB Professional - Fast 'N Free",
    ],
    "phone": [
        "128GB Unlocked - Excellent Condition",
        "256GB Factory Sealed - Free Shipping",
        "512GB Unlocked - Top Rated Seller",
        "128GB Certified Refurbished",
        "256GB New in Box - Buy It Now",
    ],
    "headphones": [
        "Noise Cancelling - New Sealed",
        "Wireless Over-Ear - Free Shipping",
        "Studio Quality - Top Rated Plus",
        "Sport Wireless - Certified Refurbished",
        "Premium Edition - Buy It Now",
    ],
    "general": [
        "New - Factory Sealed",
        "New - Open Box",
        "Brand New - Free Shipping",
        "Latest Model - Top Rated Seller",
        "New - Buy It Now",
    ],
}

# eBay base prices (typically 5-10% below Amazon)
EBAY_CATEGORY_BASE_PRICES = {
    "laptop": 849.99,
    "computer": 949.99,
    "server": 1849.99,
    "gpu": 749.99,
    "phone": 649.99,
    "headphones": 229.99,
    "general": 179.99,
}

# Keywords for category detection (shared logic with Amazon)
EBAY_CATEGORY_KEYWORDS = {
    "laptop": ["laptop", "notebook", "macbook", "chromebook", "ultrabook"],
    "computer": ["computer", "desktop", "pc", "workstation", "llm", "llms", "ai server", "hosting"],
    "server": ["server", "rack", "nas", "hosting server"],
    "gpu": ["gpu", "graphics card", "video card", "rtx", "radeon"],
    "phone": ["phone", "iphone", "smartphone", "android", "galaxy", "pixel"],
    "headphones": ["headphone", "earphone", "earbud", "airpod", "earpiece", "headset"],
    "general": [],
}


def _detect_ebay_category(query: str, category_hint: Optional[str] = None) -> str:
    """Detect product category from query keywords or category hint."""
    if category_hint:
        hint_lower = category_hint.lower()
        for cat in EBAY_CATEGORY_KEYWORDS:
            if cat in hint_lower:
                return cat

    query_lower = query.lower()
    for cat, keywords in EBAY_CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in query_lower:
                return cat

    return "general"


# eBay marketplace IDs by country code
EBAY_MARKETPLACES: Dict[str, str] = {
    "US": "EBAY_US",
    "GB": "EBAY_GB",
    "UK": "EBAY_GB",
    "DE": "EBAY_DE",
    "FR": "EBAY_FR",
    "IT": "EBAY_IT",
    "ES": "EBAY_ES",
    "AU": "EBAY_AU",
    "CA": "EBAY_CA",
    "IE": "EBAY_IE",
    "NL": "EBAY_NL",
    "BE": "EBAY_BE",
    "AT": "EBAY_AT",
    "CH": "EBAY_CH",
    "PL": "EBAY_PL",
    "IN": "EBAY_IN",
    "SG": "EBAY_SG",
    "HK": "EBAY_HK",
    "MY": "EBAY_MY",
    "PH": "EBAY_PH",
}

# eBay domain URLs by country code (for affiliate links)
EBAY_DOMAINS: Dict[str, str] = {
    "US": "ebay.com",
    "GB": "ebay.co.uk",
    "UK": "ebay.co.uk",
    "DE": "ebay.de",
    "FR": "ebay.fr",
    "IT": "ebay.it",
    "ES": "ebay.es",
    "AU": "ebay.com.au",
    "CA": "ebay.ca",
    "IE": "ebay.ie",
    "NL": "ebay.nl",
    "BE": "ebay.be",
    "AT": "ebay.at",
    "CH": "ebay.ch",
    "PL": "ebay.pl",
    "IN": "ebay.in",
    "SG": "ebay.com.sg",
    "HK": "ebay.com.hk",
    "MY": "ebay.com.my",
    "PH": "ebay.ph",
}


@AffiliateProviderRegistry.register(
    "ebay",
    required_env_vars=[],
    optional_env_vars=["EBAY_APP_ID", "EBAY_CERT_ID", "EBAY_CAMPAIGN_ID"],
)
class EbayAffiliateProvider(BaseAffiliateProvider):
    """
    eBay Partner Network (EPN) Integration

    Features:
    - OAuth token generation from App ID + Cert ID
    - Product search via eBay Browse API
    - Affiliate link generation with campaign tracking
    - Link health monitoring
    - Category-based filtering
    - Price range filtering
    """

    def __init__(
        self,
        app_id: str = None,
        cert_id: str = None,
        campaign_id: str = None,
        custom_id: str = None,
        timeout: int = 10,
    ):
        """
        Initialize eBay affiliate provider

        Args:
            app_id: eBay Application ID
            cert_id: eBay Cert ID (Client Secret)
            campaign_id: eBay Partner Network Campaign ID
            custom_id: Custom tracking ID for additional tracking
            timeout: Request timeout in seconds
        """
        self.app_id = app_id or settings.EBAY_APP_ID
        self.cert_id = cert_id or settings.EBAY_CERT_ID
        self.campaign_id = campaign_id or settings.EBAY_CAMPAIGN_ID
        self.custom_id = custom_id or settings.EBAY_AFFILIATE_CUSTOM_ID
        self.timeout = timeout
        self.oauth_token = None  # Will be generated on demand
        self.token_expires_at = 0  # Unix timestamp when token expires
        self.api_enabled = bool(self.app_id and self.cert_id)

        # eBay API endpoints
        self.base_url = "https://api.ebay.com"
        self.oauth_url = f"{self.base_url}/identity/v1/oauth2/token"
        self.browse_api = f"{self.base_url}/buy/browse/v1"

        # Client for HTTP requests
        self.client = httpx.AsyncClient(timeout=self.timeout)

        if not self.api_enabled:
            logger.info(
                "eBay API credentials not configured — running in mock mode. "
                "Set EBAY_APP_ID and EBAY_CERT_ID to enable real API."
            )

        if not self.campaign_id:
            logger.warning(
                "eBay Campaign ID not configured. "
                "Affiliate tracking will not be active. "
                "Set EBAY_CAMPAIGN_ID in environment."
            )

        logger.info(
            f"eBay provider initialized: api_enabled={self.api_enabled}"
        )

    def get_provider_name(self) -> str:
        """Return provider name"""
        return "eBay"

    def _invalidate_token(self):
        """Clear cached OAuth token so the next call fetches a fresh one."""
        self.oauth_token = None
        self.token_expires_at = 0

    async def _get_oauth_token(self) -> str:
        """
        Generate OAuth token from App ID and Cert ID

        Uses client_credentials flow with Basic Auth
        Token is valid for ~2 hours (7200 seconds)
        Refreshes automatically 5 minutes before expiry.

        Returns:
            OAuth access token
        """
        # Return cached token if still valid (with 5-minute buffer)
        if self.oauth_token and time.time() < (self.token_expires_at - 300):
            return self.oauth_token

        try:
            # Create Basic Auth header: base64(app_id:cert_id)
            credentials = f"{self.app_id}:{self.cert_id}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {encoded_credentials}"
            }

            data = {
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope"
            }

            logger.info("Requesting new eBay OAuth token")
            response = await self.client.post(
                self.oauth_url,
                headers=headers,
                data=data
            )

            if response.status_code != 200:
                logger.error(f"eBay OAuth error: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get eBay OAuth token: {response.status_code}")

            token_data = response.json()
            self.oauth_token = token_data["access_token"]
            # eBay tokens typically expire in 7200 seconds (2 hours)
            expires_in = token_data.get("expires_in", 7200)
            self.token_expires_at = time.time() + expires_in
            logger.info(f"Successfully obtained eBay OAuth token (expires in {expires_in}s)")
            return self.oauth_token

        except Exception as e:
            self._invalidate_token()
            logger.error(f"Failed to get eBay OAuth token: {str(e)}", exc_info=True)
            raise

    async def search_products(
        self,
        query: str,
        category: Optional[str] = None,
        brand: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        limit: int = 10,
        country_code: Optional[str] = None,
    ) -> List[AffiliateProduct]:
        """
        Search for products on eBay

        Uses eBay Browse API to search for products with filters

        Args:
            query: Search query
            category: Optional category filter
            brand: Optional brand filter
            min_price: Minimum price
            max_price: Maximum price
            limit: Maximum results
            country_code: ISO country code for regional eBay marketplace (e.g., "US", "GB", "DE")
        """
        # Determine marketplace based on country code
        effective_country = (country_code or settings.AMAZON_DEFAULT_COUNTRY).upper()
        marketplace_id = EBAY_MARKETPLACES.get(effective_country, "EBAY_US")

        # Use mock data when API credentials are not configured
        if not self.api_enabled:
            return await self._search_mock_data(
                query, category, brand, min_price, max_price, limit, effective_country
            )

        logger.info("=" * 80)
        logger.info("EBAY SEARCH - INPUT PARAMETERS:")
        logger.info(f"  Query: '{query}'")
        logger.info(f"  Category: {category}")
        logger.info(f"  Brand: {brand}")
        logger.info(f"  Min Price: ${min_price}")
        logger.info(f"  Max Price: ${max_price}")
        logger.info(f"  Limit: {limit}")
        logger.info(f"  Country: {effective_country}")
        logger.info(f"  Marketplace ID: {marketplace_id}")

        try:
            # Get OAuth token
            token = await self._get_oauth_token()

            # Build search query with filters
            search_query = self._build_search_query(
                query, category, brand, min_price, max_price
            )

            # Build filters
            filters = self._build_filters(category, min_price, max_price)

            logger.info(f"  Final Search Query: '{search_query}'")
            logger.info(f"  Final Filters: '{filters}'")

            # Make API request
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-EBAY-C-MARKETPLACE-ID": marketplace_id,  # Dynamic marketplace based on country
            }

            params = {
                "q": search_query,
                "limit": min(limit, settings.EBAY_MAX_RESULTS),  # Use configured max results
                "filter": filters,
            }

            url = f"{self.browse_api}/item_summary/search"
            logger.info(f"  eBay API URL: {url}")
            logger.info(f"  Request params: {params}")
            response = await self.client.get(url, headers=headers, params=params)

            if response.status_code == 401:
                # Token expired — refresh and retry once
                logger.warning("eBay API returned 401 — refreshing OAuth token and retrying")
                self._invalidate_token()
                token = await self._get_oauth_token()
                headers["Authorization"] = f"Bearer {token}"
                response = await self.client.get(url, headers=headers, params=params)

            if response.status_code != 200:
                logger.error(
                    f"eBay API error: {response.status_code} - {response.text}"
                )
                return []

            data = response.json()
            items = data.get("itemSummaries", [])

            logger.info(f"EBAY SEARCH - API RESPONSE:")
            logger.info(f"  Status Code: {response.status_code}")
            logger.info(f"  Total Results: {len(items)}")

            # Log first 3 items for debugging
            for idx, item in enumerate(items[:3], 1):
                logger.info(f"  Result #{idx}:")
                logger.info(f"    Title: {item.get('title', 'N/A')}")
                logger.info(f"    Item ID: {item.get('itemId', 'N/A')}")
                logger.info(f"    Price: {item.get('price', {}).get('value', 'N/A')} {item.get('price', {}).get('currency', '')}")
                logger.info(f"    Image: {item.get('image')}")
                logger.info(f"    ThumbnailImages: {item.get('thumbnailImages')}")

            if len(items) > 3:
                logger.info(f"  ... and {len(items) - 3} more results")
            logger.info("=" * 80)

            # Convert to AffiliateProduct objects
            products = []
            for item in items:
                try:
                    product = self._parse_ebay_item(item, country_code=effective_country)
                    if product:
                        products.append(product)
                except Exception as e:
                    logger.warning(f"Failed to parse eBay item: {e}")
                    continue

            logger.info(f"eBay: Successfully parsed {len(products)} products")
            return products

        except httpx.TimeoutException:
            logger.error("eBay API request timeout")
            return []
        except Exception as e:
            logger.error(f"eBay search error: {e}", exc_info=True)
            return []

    async def _search_mock_data(
        self,
        query: str,
        category: Optional[str],
        brand: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
        limit: int,
        country_code: str,
    ) -> List[AffiliateProduct]:
        """Return mock products for development - generates eBay-flavored results"""
        import random

        # Deterministic generation based on query
        query_hash = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
        random.seed(query_hash + 7)  # Offset from Amazon so results differ

        detected_category = _detect_ebay_category(query, category)
        variations = EBAY_CATEGORY_VARIATIONS.get(detected_category, EBAY_CATEGORY_VARIATIONS["general"])
        base_price = EBAY_CATEGORY_BASE_PRICES.get(detected_category, 179.99)

        seller_names = ["tech_deals_usa", "electronics_hub", "best_value_store", "top_rated_seller", "warehouse_direct"]

        results = []
        for i in range(min(limit, 5)):
            # Price variance: +/- 25% from base
            price_offset = ((query_hash + i * 17) % 50 - 25) / 100.0
            price = round(base_price * (1.0 + price_offset), 2)
            shipping = round(random.uniform(0, 12.99), 2) if i % 3 != 0 else 0.0
            seller = seller_names[(query_hash + i) % len(seller_names)]

            item_id = f"v1|EBMOCK{query_hash % 1000000:06d}{i}|0"

            # Generate affiliate link
            affiliate_link = self._generate_affiliate_url(item_id, country_code=country_code)

            # First result = exact query, rest = query + eBay-style variation
            if i == 0:
                title = query
            else:
                variation = variations[i % len(variations)]
                title = f"{query} - {variation}"

            results.append(AffiliateProduct(
                product_id=item_id,
                title=title,
                price=price,
                currency="USD",
                affiliate_link=affiliate_link,
                # User-facing label: just "eBay" — seller usernames ("lin-866576")
                # leaked into card merchant labels and titles.
                merchant="eBay",
                image_url=f"https://placehold.co/400x400/e8e8e8/333333?text={query.replace(' ', '+')}",
                rating=None,  # eBay Browse API doesn't return ratings
                review_count=None,
                condition="New",
                shipping_cost=shipping,
                availability=True,
                source_url=affiliate_link,
            ))

        logger.info(f"eBay mock: generated {len(results)} {detected_category} products for '{query}'")
        return results

    def _build_search_query(
        self,
        query: str,
        category: Optional[str],
        brand: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
    ) -> str:
        """Build eBay search query with filters"""
        # Use the full query as-is (should be the full product title from Perplexity)
        # Don't manipulate or add category/negative keywords - let the full title do the work
        if query:
            return query

        # Fallback: if no query, use category
        if category:
            return category

        return ""

    def _build_filters(
        self,
        category: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
    ) -> str:
        """Build eBay filter string"""
        filters = []

        # Price filters
        if min_price is not None:
            filters.append(f"price:[{min_price}..],priceCurrency:USD")
        if max_price is not None:
            filters.append(f"price:[..{max_price}],priceCurrency:USD")

        # Only new items
        filters.append("conditions:{NEW}")

        # Only buy-it-now (not auctions)
        filters.append("buyingOptions:{FIXED_PRICE}")

        # Removed hardcoded category ID filter - let the full product title handle specificity

        return "|".join(filters) if filters else ""

    def _parse_ebay_item(self, item: Dict[str, Any], country_code: str = "US") -> Optional[AffiliateProduct]:
        """Parse eBay item into AffiliateProduct"""
        try:
            item_id = item.get("itemId")
            title = item.get("title", "")

            # Price
            price_obj = item.get("price", {})
            price = float(price_obj.get("value", 0))
            currency = price_obj.get("currency", "USD")

            # Image - try multiple fields
            image_url = None
            if item.get("image") and item["image"].get("imageUrl"):
                image_url = item["image"]["imageUrl"]
            elif item.get("thumbnailImages") and len(item["thumbnailImages"]) > 0:
                image_url = item["thumbnailImages"][0].get("imageUrl")
            elif item.get("additionalImages") and len(item["additionalImages"]) > 0:
                image_url = item["additionalImages"][0].get("imageUrl")

            # Log if no image found for debugging
            if not image_url:
                logger.warning(f"No image URL found for item {item_id} - '{title[:50]}...'")

            # Generate affiliate link with EPN tracking (country-specific)
            affiliate_link = self._generate_affiliate_url(item_id, country_code=country_code)

            # Fallback to itemWebUrl if item_id parsing failed
            if not affiliate_link:
                affiliate_link = item.get("itemWebUrl", "")

            # Additional details
            condition = item.get("condition", "New")
            seller = item.get("seller", {}).get("username", "eBay")

            # Shipping
            shipping_cost = None
            shipping_options = item.get("shippingOptions", [])
            if shipping_options and shipping_options[0].get("shippingCost"):
                shipping_obj = shipping_options[0]["shippingCost"]
                shipping_cost = float(shipping_obj.get("value", 0))

            # Source URL (same as affiliate_link in this case)
            source_url = affiliate_link

            return AffiliateProduct(
                product_id=item_id,
                title=title,
                price=price,
                currency=currency,
                affiliate_link=affiliate_link,
                # User-facing label: just "eBay" — seller usernames ("lin-866576")
                # leaked into card merchant labels and titles.
                merchant="eBay",
                image_url=image_url,
                rating=None,  # eBay doesn't provide ratings in Browse API
                review_count=None,
                condition=condition,
                shipping_cost=shipping_cost,
                availability=True,
                source_url=source_url,
            )

        except (KeyError, ValueError) as e:
            logger.warning(f"Failed to parse eBay item: {e}")
            return None

    def _generate_affiliate_url(self, product_id: str, custom_id: str = None, country_code: str = "US") -> str:
        """
        Generate eBay affiliate link with EPN tracking parameters

        Args:
            product_id: eBay item ID (may be in format "v1|legacyId|...")
            custom_id: Optional custom tracking ID (overrides instance custom_id)
            country_code: ISO country code for regional eBay domain

        Returns:
            eBay product URL with affiliate tracking parameters
        """
        # Extract legacy item ID from Browse API format
        legacy_item_id = product_id
        if "|" in product_id:
            parts = product_id.split("|")
            if len(parts) >= 2:
                legacy_item_id = parts[1]

        # Get country-specific domain
        domain = EBAY_DOMAINS.get(country_code.upper(), "ebay.com")

        # Build base URL
        base_url = f"https://www.{domain}/itm/{legacy_item_id}"

        # Add EPN tracking parameters if campaign ID is configured
        logger.debug(f"Generating affiliate URL - campaign_id: {self.campaign_id}")
        if self.campaign_id:
            # EPN tracking parameters per https://developer.ebay.com/api-docs/buy/static/ref-epn-link.html
            params = {
                "mkcid": settings.EBAY_MKCID,       # Channel ID (1=EPN)
                "mkrid": settings.EBAY_MKRID,       # Rotation ID (marketplace)
                "campid": self.campaign_id,         # Campaign ID
                "toolid": settings.EBAY_TOOLID,     # Tool ID (10001=default)
                "mkevt": settings.EBAY_MKEVT        # Event type (1=Click)
            }

            # Add custom tracking ID if provided
            tracking_custom_id = custom_id or self.custom_id
            if tracking_custom_id:
                params["customid"] = tracking_custom_id

            # Build query string
            query_string = urlencode(params)
            affiliate_url = f"{base_url}?{query_string}"
            logger.info(f"Generated eBay affiliate link: {affiliate_url}")
            return affiliate_url

        # Return direct link if no campaign ID configured
        logger.warning(f"No campaign ID configured, returning direct link: {base_url}")
        return base_url

    async def generate_affiliate_link(
        self,
        product_id: str,
        campaign_id: Optional[str] = None,
        tracking_id: Optional[str] = None,
    ) -> str:
        """
        Generate eBay product link with affiliate tracking

        Args:
            product_id: eBay item ID (may be in format "v1|legacyId|...")
            campaign_id: Optional override for campaign ID (not used, set via env)
            tracking_id: Optional custom tracking ID for this specific link

        Returns:
            eBay affiliate link with tracking parameters
        """
        return self._generate_affiliate_url(product_id, custom_id=tracking_id)

    async def check_link_health(self, affiliate_link: str) -> bool:
        """
        Check if an eBay affiliate link is still valid

        Makes a HEAD request to check if the link returns 200
        """
        try:
            response = await self.client.head(
                affiliate_link,
                follow_redirects=True,
                timeout=5,
            )
            is_healthy = response.status_code == 200
            logger.debug(
                f"eBay link health check: {affiliate_link[:50]}... = {is_healthy}"
            )
            return is_healthy

        except Exception as e:
            logger.warning(f"eBay link health check failed: {e}")
            return False

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# Export
__all__ = ["EbayAffiliateProvider"]
