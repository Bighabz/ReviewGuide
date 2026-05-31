"""
Review Search Client (Serper.dev)

Runs parallel searches across Serper.dev endpoints to find real product reviews
from trusted sources (Wirecutter, RTINGS, Reddit, YouTube, Tom's Guide, etc.).

Temporary swap from SerpAPI to Serper while SerpAPI credits refill.
Same interface (ReviewBundle, ReviewSource, SerpAPIClient) so the rest of the
codebase doesn't need changes.

Features:
- Parallel search (Google + Google Shopping + Reddit)
- Redis caching with 24h TTL
- Graceful degradation on failure
- Source authority scoring
"""

import asyncio
import hashlib
import json
import math
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.centralized_logger import get_logger

logger = get_logger(__name__)

# Trusted source authority scores (higher = more authoritative)
TRUSTED_SOURCES: Dict[str, float] = {
    "wirecutter.com": 0.95,
    "nytimes.com": 0.95,  # Wirecutter is part of NYT
    "rtings.com": 0.93,
    "tomsguide.com": 0.88,
    "techradar.com": 0.85,
    "cnet.com": 0.85,
    "theverge.com": 0.83,
    "pcmag.com": 0.82,
    "soundguys.com": 0.80,
    "reddit.com": 0.78,
    "youtube.com": 0.75,
    "amazon.com": 0.70,
    "bestbuy.com": 0.68,
    "walmart.com": 0.65,
    "target.com": 0.63,
}

# Editorial sites for Google search
EDITORIAL_SITES = [
    "wirecutter.com",
    "rtings.com",
    "tomsguide.com",
    "techradar.com",
    "cnet.com",
    "theverge.com",
    "pcmag.com",
    "soundguys.com",
]


@dataclass
class ReviewSource:
    """A single review source for a product."""
    site_name: str
    url: str
    title: str
    snippet: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    favicon_url: Optional[str] = None
    authority_score: float = 0.5
    date: Optional[str] = None


@dataclass
class ReviewBundle:
    """Aggregated review data for a single product."""
    product_name: str
    sources: List[ReviewSource] = field(default_factory=list)
    avg_rating: float = 0.0
    total_reviews: int = 0
    consensus: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_name": self.product_name,
            "sources": [asdict(s) for s in self.sources],
            "avg_rating": self.avg_rating,
            "total_reviews": self.total_reviews,
            "consensus": self.consensus,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewBundle":
        sources = [ReviewSource(**s) for s in data.get("sources", [])]
        return cls(
            product_name=data.get("product_name", ""),
            sources=sources,
            avg_rating=data.get("avg_rating", 0.0),
            total_reviews=data.get("total_reviews", 0),
            consensus=data.get("consensus", ""),
        )


def _get_authority_score(url: str) -> float:
    """Get authority score for a URL based on its domain."""
    for domain, score in TRUSTED_SOURCES.items():
        if domain in url:
            return score
    return 0.4  # Default for unknown sources


def _extract_site_name(url: str) -> str:
    """Extract human-readable site name from URL."""
    domain_names = {
        "wirecutter.com": "Wirecutter",
        "nytimes.com": "Wirecutter",
        "rtings.com": "RTINGS",
        "tomsguide.com": "Tom's Guide",
        "techradar.com": "TechRadar",
        "cnet.com": "CNET",
        "theverge.com": "The Verge",
        "pcmag.com": "PCMag",
        "soundguys.com": "SoundGuys",
        "reddit.com": "Reddit",
        "youtube.com": "YouTube",
        "amazon.com": "Amazon",
        "bestbuy.com": "Best Buy",
        "walmart.com": "Walmart",
        "target.com": "Target",
    }
    for domain, name in domain_names.items():
        if domain in url:
            return name
    # Fallback: extract domain
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "").split(".")[0].title()
    except Exception:
        return "Web"


def _get_favicon_url(url: str) -> str:
    """Get favicon URL for a site using Google's favicon service."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split("/")[0]
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
    except Exception:
        return ""


def _cache_key(product_name: str, category: str) -> str:
    """Generate Redis cache key for a product search."""
    raw = f"{product_name.lower().strip()}:{category.lower().strip()}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"serpapi:{h}"


class SerpAPIClient:
    """Client for searching product reviews via Serper.dev (drop-in for SerpAPI)."""

    def __init__(self):
        from app.core.config import settings
        self.api_key = settings.SERPAPI_API_KEY
        self.max_sources = settings.SERPAPI_MAX_SOURCES
        self.cache_ttl = settings.SERPAPI_CACHE_TTL
        self.timeout = settings.SERPAPI_TIMEOUT

    async def search_reviews(
        self,
        product_name: str,
        category: str = "",
    ) -> ReviewBundle:
        """
        Search for real product reviews from trusted sources.

        Runs 3 parallel Serper searches:
        1. Google Search: editorial review sites
        2. Google Search: Reddit discussions
        3. Google Shopping: ratings and review counts
        """
        # Check cache first
        cached = await self._get_cached(product_name, category)
        if cached:
            logger.info(f"[serper] Cache hit for '{product_name}'")
            return cached

        logger.info(f"[serper] Searching reviews for '{product_name}' (category: {category or 'general'})")

        try:
            # Run parallel searches
            editorial_task = self._search_editorial(product_name, category)
            reddit_task = self._search_reddit(product_name, category)
            shopping_task = self._search_shopping(product_name)

            results = await asyncio.gather(
                editorial_task, reddit_task, shopping_task,
                return_exceptions=True,
            )

            # Merge results
            all_sources: List[ReviewSource] = []
            shopping_data: Dict[str, Any] = {}

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    search_names = ["editorial", "reddit", "shopping"]
                    logger.warning(f"[serper] {search_names[i]} search failed: {result}")
                    continue
                if i < 2:
                    all_sources.extend(result)
                else:
                    shopping_data = result

            # Deduplicate by URL
            seen_urls = set()
            unique_sources = []
            for source in all_sources:
                if source.url not in seen_urls:
                    seen_urls.add(source.url)
                    unique_sources.append(source)

            # Sort by authority score (highest first)
            unique_sources.sort(key=lambda s: s.authority_score, reverse=True)

            # Limit to max sources
            unique_sources = unique_sources[:self.max_sources]

            # Aggregate ratings
            ratings = [s.rating for s in unique_sources if s.rating and s.rating > 0]
            if shopping_data.get("rating"):
                ratings.append(shopping_data["rating"])

            avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else 0.0

            total_reviews = sum(
                s.review_count for s in unique_sources if s.review_count
            )
            if shopping_data.get("review_count"):
                total_reviews += shopping_data["review_count"]

            bundle = ReviewBundle(
                product_name=product_name,
                sources=unique_sources,
                avg_rating=avg_rating,
                total_reviews=total_reviews,
                consensus="",
            )

            # Cache result
            await self._set_cached(product_name, category, bundle)

            logger.info(
                f"[serper] Found {len(unique_sources)} sources for '{product_name}' "
                f"(avg_rating={avg_rating}, total_reviews={total_reviews})"
            )
            return bundle

        except Exception as e:
            logger.error(f"[serper] Search failed for '{product_name}': {e}", exc_info=True)
            return ReviewBundle(product_name=product_name)

    async def _search_editorial(self, product_name: str, category: str) -> List[ReviewSource]:
        """Search editorial review sites via Google."""
        site_filter = " OR ".join(f"site:{site}" for site in EDITORIAL_SITES)
        query = f"{product_name} review {site_filter}"
        if category:
            query = f"{product_name} {category} review {site_filter}"

        results = await self._serper_search(query, num=10)
        return self._parse_organic_results(results)

    async def _search_reddit(self, product_name: str, category: str) -> List[ReviewSource]:
        """Search Reddit discussions via Google."""
        query = f"{product_name} review site:reddit.com"
        if category:
            query = f"{product_name} {category} review site:reddit.com"

        results = await self._serper_search(query, num=10)
        return self._parse_organic_results(results)

    async def _search_shopping(self, product_name: str) -> Dict[str, Any]:
        """Search Google Shopping for ratings and review counts."""
        try:
            results = await self._serper_shopping(product_name)
            shopping = results.get("shopping", [])

            if not shopping:
                return {}

            # Find best match
            best = shopping[0]
            rating = None
            review_count = None

            if best.get("rating"):
                try:
                    rating = float(best["rating"])
                except (ValueError, TypeError):
                    pass
            if best.get("ratingCount"):
                try:
                    review_count = int(str(best["ratingCount"]).replace(",", ""))
                except (ValueError, TypeError):
                    pass

            return {
                "rating": rating,
                "review_count": review_count,
                "price": best.get("price"),
                "source": best.get("source"),
            }

        except Exception as e:
            logger.warning(f"[serper] Shopping search failed: {e}")
            return {}

    @staticmethod
    def _parse_price(price: Any) -> Optional[float]:
        """Parse a Serper shopping price (e.g. "$278.00", "1,299", 49.99) into a float.
        Returns None when no positive numeric price can be determined."""
        if price is None:
            return None
        if isinstance(price, (int, float)):
            return float(price) if price > 0 else None
        if isinstance(price, str):
            import re
            cleaned = re.sub(r"[^\d.]", "", price)
            try:
                val = float(cleaned)
                return val if val > 0 else None
            except ValueError:
                return None
        return None

    async def search_shopping_offer(self, product_name: str) -> Optional[Dict[str, Any]]:
        """Fetch a single REAL Google Shopping offer for a product via Serper.

        Returns a normalized offer dict with a real price, product image, merchant,
        and buy-link — or None when no priced result is found.

        Used by product_affiliate to surface real prices/images on product cards:
        the affiliate providers run in mock mode (Amazon price=0 without PA-API,
        eBay placeholder images), so this is currently the only real-price source.
        Results are cached in Redis (same TTL as review bundles).
        """
        cached = await self._get_cached_shopping(product_name)
        if cached is not None:
            # {} is a sentinel for "looked up, no priced result" — avoids re-querying.
            return cached or None

        try:
            results = await self._serper_shopping(product_name)
            shopping = results.get("shopping", [])

            offer: Optional[Dict[str, Any]] = None
            for item in shopping:
                price = self._parse_price(item.get("price"))
                if price is None:
                    continue

                rating = None
                review_count = None
                if item.get("rating"):
                    try:
                        rating = float(item["rating"])
                    except (ValueError, TypeError):
                        pass
                if item.get("ratingCount"):
                    try:
                        review_count = int(str(item["ratingCount"]).replace(",", ""))
                    except (ValueError, TypeError):
                        pass

                offer = {
                    "price": price,
                    "currency": "USD",
                    "merchant": item.get("source") or "",
                    "url": item.get("link") or "",
                    "image_url": item.get("imageUrl") or "",
                    "title": item.get("title") or product_name,
                    "rating": rating,
                    "review_count": review_count,
                }
                break

            await self._set_cached_shopping(product_name, offer or {})
            return offer

        except Exception as e:
            logger.warning(f"[serper] Shopping offer lookup failed for '{product_name}': {e}")
            return None

    async def _serper_search(self, query: str, num: int = 10) -> Dict[str, Any]:
        """Execute a Google search via Serper.dev."""
        return await self._serper_request(
            "https://google.serper.dev/search",
            {"q": query, "num": num},
        )

    async def _serper_shopping(self, query: str) -> Dict[str, Any]:
        """Execute a Google Shopping search via Serper.dev."""
        return await self._serper_request(
            "https://google.serper.dev/shopping",
            {"q": query, "num": 5},
        )

    async def _serper_request(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make async POST request to Serper.dev."""
        import httpx

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            return response.json()

    def _parse_organic_results(self, results: Dict[str, Any]) -> List[ReviewSource]:
        """Parse Serper organic results into ReviewSource objects."""
        sources = []
        organic = results.get("organic", [])

        for item in organic:
            url = item.get("link", "")
            if not url:
                continue

            source = ReviewSource(
                site_name=_extract_site_name(url),
                url=url,
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                rating=None,
                review_count=None,
                favicon_url=_get_favicon_url(url),
                authority_score=_get_authority_score(url),
                date=item.get("date"),
            )
            sources.append(source)

        return sources

    async def _get_cached(self, product_name: str, category: str) -> Optional[ReviewBundle]:
        """Get cached review bundle from Redis."""
        try:
            from app.core.redis_client import redis_get_with_retry
            key = _cache_key(product_name, category)
            data = await redis_get_with_retry(key)
            if data:
                return ReviewBundle.from_dict(json.loads(data))
        except Exception as e:
            logger.warning(f"[serper] Cache read failed: {e}")
        return None

    async def _set_cached(self, product_name: str, category: str, bundle: ReviewBundle) -> None:
        """Cache review bundle in Redis."""
        try:
            from app.core.redis_client import redis_set_with_retry
            key = _cache_key(product_name, category)
            data = json.dumps(bundle.to_dict())
            await redis_set_with_retry(key, data, ex=self.cache_ttl)
        except Exception as e:
            logger.warning(f"[serper] Cache write failed: {e}")

    @staticmethod
    def _shopping_cache_key(product_name: str) -> str:
        """Redis cache key for a Google Shopping offer lookup."""
        h = hashlib.sha256(product_name.lower().strip().encode()).hexdigest()[:16]
        return f"serper_shop:{h}"

    async def _get_cached_shopping(self, product_name: str) -> Optional[Dict[str, Any]]:
        """Get a cached shopping offer from Redis. Returns None on cache miss,
        or the cached dict ({} sentinel = looked-up-but-no-priced-result)."""
        try:
            from app.core.redis_client import redis_get_with_retry
            data = await redis_get_with_retry(self._shopping_cache_key(product_name))
            if data is not None:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"[serper] Shopping cache read failed: {e}")
        return None

    async def _set_cached_shopping(self, product_name: str, offer: Dict[str, Any]) -> None:
        """Cache a shopping offer ({} when none found) in Redis."""
        try:
            from app.core.redis_client import redis_set_with_retry
            await redis_set_with_retry(
                self._shopping_cache_key(product_name),
                json.dumps(offer),
                ex=self.cache_ttl,
            )
        except Exception as e:
            logger.warning(f"[serper] Shopping cache write failed: {e}")
