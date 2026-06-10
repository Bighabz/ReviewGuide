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

# SerpApi.com fallback endpoint (a different provider from Serper.dev — used only
# when Serper.dev errors/runs out of credits and failover is configured).
SERPAPI_COM_URL = "https://serpapi.com/search.json"

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
        # Cross-provider failover (Serper.dev primary → SerpApi.com on error/credit-exhaustion).
        # SerpApi.com keys are tried in order: the second covers the first running dry
        # (free-tier accounts cap at 250 searches/mo, so chaining extends headroom).
        self.fallback_enabled = settings.SERPAPI_FALLBACK_ENABLED
        self.serpapi_com_keys = [
            k for k in (settings.SERPAPI_COM_API_KEY, settings.SERPAPI_COM_API_KEY_2) if k
        ]

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
            had_provider_error = False

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    search_names = ["editorial", "reddit", "shopping"]
                    logger.warning(f"[serper] {search_names[i]} search failed: {result}")
                    had_provider_error = True
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

            # Normalize mixed scales before averaging: editorial sites rate /10
            # (RTINGS "8.5"), shopping rates /5. Without this, the average can
            # exceed 5 and downstream star displays break.
            normalized_ratings = [r / 2 if r > 5 else r for r in ratings]
            avg_rating = round(sum(normalized_ratings) / len(normalized_ratings), 1) if normalized_ratings else 0.0

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

            # Cache result — but NEVER cache an empty bundle that resulted from a
            # provider error (e.g. Serper.dev out of credits with no fallback). The
            # 24h TTL would otherwise mask the fix for a full day per product. A
            # genuinely-empty result (searches succeeded, just no reviews) is still
            # cached to avoid re-querying obscure products.
            if unique_sources or not had_provider_error:
                await self._set_cached(product_name, category, bundle)
            else:
                logger.warning(
                    f"[serper] Not caching empty bundle for '{product_name}' — provider error "
                    "(avoiding 24h cache poisoning)"
                )

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

    async def search_strain_info(self, strain_name: str) -> Optional[Dict[str, Any]]:
        """Resolve a cannabis strain's real Leafly page + live snippet via a
        site-scoped Google search (strain vertical — no Leafly API key needed).

        Returns {"url", "snippet", "title"} from the first leafly.com organic
        hit, or None. Tone note: this is sourcing plumbing — the snippet feeds
        the composer's context, never a user-visible citation.
        """
        try:
            data = await self._serper_search(f"{strain_name} cannabis strain site:leafly.com", num=3)
        except Exception:
            return None

        for item in data.get("organic", []) or []:
            link = item.get("link", "") or ""
            if "leafly.com" in link:
                return {
                    "url": link,
                    "snippet": item.get("snippet", "") or "",
                    "title": item.get("title", "") or "",
                }
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

                # D2 (perf): Serper's Google Shopping `imageUrl` is frequently a
                # base64 `data:image/webp;...` URI (~7–9KB each), which bloats the
                # SSE payload by ~130–240KB per product response. Keep only real
                # http(s) images; when empty, downstream picks another offer's
                # image (live-eBay https) or the frontend's themed fallback.
                raw_image = item.get("imageUrl") or ""
                image_url = raw_image if raw_image.startswith("http") else ""

                offer = {
                    "price": price,
                    "currency": "USD",
                    "merchant": item.get("source") or "",
                    "url": item.get("link") or "",
                    "image_url": image_url,
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
        """Execute a Google search via Serper.dev, failing over to SerpApi.com on error."""
        try:
            return await self._serper_request(
                "https://google.serper.dev/search",
                {"q": query, "num": num},
            )
        except Exception as e:
            self._log_provider_failure(e)
            if self._should_failover(e):
                return await self._serpapi_com_search(query, num)
            raise

    async def _serper_shopping(self, query: str) -> Dict[str, Any]:
        """Execute a Google Shopping search via Serper.dev, failing over to SerpApi.com on error."""
        try:
            return await self._serper_request(
                "https://google.serper.dev/shopping",
                {"q": query, "num": 5},
            )
        except Exception as e:
            self._log_provider_failure(e)
            if self._should_failover(e):
                return await self._serpapi_com_shopping(query)
            raise

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

    # ------------------------------------------------------------------
    # Cross-provider failover (Serper.dev → SerpApi.com)
    # ------------------------------------------------------------------

    @staticmethod
    def _is_credit_exhaustion(exc: Exception) -> bool:
        """True if exc is a Serper.dev 400 'Not enough credits' response."""
        import httpx

        if not isinstance(exc, httpx.HTTPStatusError) or exc.response is None:
            return False
        if exc.response.status_code != 400:
            return False
        try:
            body = exc.response.text or ""
        except Exception:
            body = ""
        return "credit" in body.lower()

    def _log_provider_failure(self, exc: Exception) -> None:
        """Loudly surface a primary-provider failure so it can't degrade silently.

        Credit-exhaustion is the one we keep hitting (account runs dry → reviews and
        prices quietly fall back to empty), so it gets an unmissable WARNING whether or
        not failover is configured.
        """
        if self._is_credit_exhaustion(exc):
            logger.warning(
                "[serper] OUT OF CREDITS on Serper.dev — review/price evidence degraded. "
                "%s", "Failing over to SerpApi.com." if (self.fallback_enabled and self.serpapi_com_keys)
                else "No SerpApi.com fallback configured (SERPAPI_FALLBACK_ENABLED / SERPAPI_COM_API_KEY)."
            )
        else:
            logger.warning(f"[serper] Serper.dev request failed: {type(exc).__name__}: {exc}")

    def _should_failover(self, exc: Exception) -> bool:
        """Fail over to SerpApi.com only when configured AND the error is a provider
        error worth retrying elsewhere (HTTP status — credits/auth/rate-limit — or a
        network/timeout error). Non-provider bugs re-raise unchanged."""
        if not (self.fallback_enabled and self.serpapi_com_keys):
            return False
        import httpx

        return isinstance(exc, (httpx.HTTPStatusError, httpx.RequestError))

    async def _serpapi_com_search(self, query: str, num: int = 10) -> Dict[str, Any]:
        """Google search via SerpApi.com, mapped into Serper.dev's organic shape."""
        data = await self._serpapi_com_request({"engine": "google", "q": query, "num": num})
        organic = [
            {
                "link": item.get("link", ""),
                "title": item.get("title", ""),
                "snippet": item.get("snippet", ""),
                "date": item.get("date"),
            }
            for item in data.get("organic_results", [])
        ]
        logger.info(f"[serpapi.com] search returned {len(organic)} organic results for '{query}'")
        return {"organic": organic}

    async def _serpapi_com_shopping(self, query: str) -> Dict[str, Any]:
        """Google Shopping via SerpApi.com, mapped into Serper.dev's shopping shape
        (so _search_shopping / search_shopping_offer parse it unchanged)."""
        data = await self._serpapi_com_request({"engine": "google_shopping", "q": query})
        shopping = []
        for item in data.get("shopping_results", []):
            # SerpApi.com gives price as "$278.00" (price) and/or 278.0 (extracted_price);
            # _parse_price handles either, so pass whichever is present.
            price = item.get("price")
            if price is None:
                price = item.get("extracted_price")
            shopping.append({
                "title": item.get("title", ""),
                "price": price,
                "rating": item.get("rating"),
                "ratingCount": item.get("reviews"),
                "source": item.get("source", ""),
                "link": item.get("product_link") or item.get("link", ""),
                "imageUrl": item.get("thumbnail", ""),
            })
        logger.info(f"[serpapi.com] shopping returned {len(shopping)} results for '{query}'")
        return {"shopping": shopping}

    async def _serpapi_com_request(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make async GET request to SerpApi.com, trying each configured key in
        order. A key that errors or is out of credits falls through to the next;
        only when every key fails does this raise (→ graceful empty upstream)."""
        import httpx

        last_exc: Exception = RuntimeError("No SerpApi.com keys configured")
        total = len(self.serpapi_com_keys)
        for idx, key in enumerate(self.serpapi_com_keys):
            try:
                full_params = {**params, "api_key": key}
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(SERPAPI_COM_URL, params=full_params)
                    response.raise_for_status()
                    data = response.json()
                # SerpApi.com signals failures (bad key, exhausted plan) via an "error"
                # body with HTTP 200 — treat it as a failure so we try the next key.
                if isinstance(data, dict) and data.get("error"):
                    raise RuntimeError(f"SerpApi.com error: {data['error']}")
                return data
            except (httpx.HTTPStatusError, httpx.RequestError, RuntimeError) as e:
                last_exc = e
                if idx + 1 < total:
                    logger.warning(f"[serpapi.com] key #{idx + 1}/{total} failed ({type(e).__name__}); trying next key")
                else:
                    logger.warning(f"[serpapi.com] all {total} key(s) exhausted ({type(e).__name__})")
        raise last_exc

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
