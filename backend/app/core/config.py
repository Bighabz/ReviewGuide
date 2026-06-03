"""
Application Configuration
Loads settings from environment variables
"""
import json
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = Field(default="ReviewGuide.ai", description="Application name")
    ENV: str = Field(default="development", description="Environment (development, staging, production)")
    DEBUG: bool = Field(default=True, description="Enable debug mode")
    SECRET_KEY: str = Field(..., min_length=32, description="Secret key for JWT and encryption")
    API_V1_PREFIX: str = Field(default="/v1", description="API version prefix")
    # Infra/deploy token sometimes present in the environment (Railway CLI/MCP).
    # Declared but unused so it doesn't trip extra=forbid and crash startup/tests.
    RAILWAY_TOKEN: str = Field(default="", description="Railway deploy token (infra only; unused by the app)")
    TIMEZONE: str = Field(default="Asia/Bangkok", description="Application timezone (UTC+7)")

    # CORS - stored as str to avoid pydantic-settings JSON parsing issues with env vars
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000,http://localhost:3001,http://localhost:3002,http://127.0.0.1:3000,http://127.0.0.1:3001",
        description="Allowed CORS origins (comma-separated string or JSON array)"
    )
    CORS_ORIGIN_REGEX: str = Field(
        default="",
        description="Regex pattern for additional allowed CORS origins (e.g. Vercel preview deployments)"
    )

    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, list):
            return ",".join(v)
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS string into a list. Handles JSON arrays and comma-separated strings."""
        v = self.CORS_ORIGINS.strip()
        if v.startswith("["):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                pass
        return [origin.strip().strip('"').strip("'") for origin in v.split(",") if origin.strip()]

    # Admin Credentials
    ADMIN_USERNAME: str = Field(default="admin", description="Admin username")
    ADMIN_PASSWORD: str = Field(..., min_length=8, description="Admin password")

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")
    DB_POOL_SIZE: int = Field(default=10, description="Database connection pool size per worker (reduced from 50 — Postgres default max_connections=100 was exhausted at 2+ workers)")
    DB_MAX_OVERFLOW: int = Field(default=5, description="Database connection pool max overflow per worker (reduced from 50)")
    DB_POOL_RECYCLE: int = Field(default=3600, description="Database connection recycle time in seconds")
    DB_CONNECT_TIMEOUT: int = Field(default=10, description="Database connection timeout in seconds")

    # Redis
    REDIS_URL: str = Field(..., description="Redis connection string")
    REDIS_MAX_CONNECTIONS: int = Field(default=50, description="Redis connection pool max connections")
    REDIS_RETRY_MAX_ATTEMPTS: int = Field(default=3, description="Redis retry max attempts")
    REDIS_SOCKET_CONNECT_TIMEOUT: int = Field(default=5, description="Redis socket connect timeout in seconds")
    REDIS_HEALTH_CHECK_INTERVAL: int = Field(default=30, description="Redis health check interval in seconds")
    REDIS_RETRY_BACKOFF_BASE: float = Field(default=0.1, description="Redis retry exponential backoff base delay in seconds")
    ENABLE_SEARCH_CACHE: bool = Field(default=True, description="Enable/disable search results caching")

    # MCP Dynamic Workflow
    USE_MCP_PLANNER: bool = Field(
        default=False,
        description="Enable MCP-based dynamic planner (true) or use traditional LangGraph workflow (false)"
    )

    # Product Search Configuration
    MAX_PRODUCTS_RETURN: int = Field(
        default=5,
        description="Maximum number of products to return from search"
    )

    # Conversation History
    USE_REDIS_FOR_HISTORY: bool = Field(
        default=True,
        description="Use Redis cache for history (true) or load directly from PostgreSQL (false)"
    )
    MAX_HISTORY_MESSAGES: int = Field(
        default=30,
        description="Maximum number of recent messages to load and send to LLM for context"
    )
    MAX_USER_HISTORY_FOR_SLOT_EXTRACTION: int = Field(
        default=5,
        description="Maximum number of user messages from history to include when extracting slots in clarifier agent"
    )

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="Enable rate limiting for chat endpoint"
    )
    TRUSTED_PROXY_CIDRS: List[str] = Field(
        default_factory=list,
        description="CIDR ranges of trusted reverse proxies (e.g. ['10.0.0.0/8']). "
                    "X-Forwarded-For is only trusted from these IPs."
    )

    @validator("TRUSTED_PROXY_CIDRS", pre=True)
    def parse_trusted_proxy_cidrs(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"TRUSTED_PROXY_CIDRS looks like JSON but failed to parse: {exc}"
                    ) from exc
            if v:
                return [cidr.strip() for cidr in v.split(",") if cidr.strip()]
        return []

    RATE_LIMIT_GUEST_REQUESTS: int = Field(
        default=20,
        description="Max requests per time window for guest users"
    )
    RATE_LIMIT_GUEST_WINDOW: int = Field(
        default=60,
        description="Time window in seconds for guest rate limit (default: 1 minute)"
    )
    RATE_LIMIT_AUTH_REQUESTS: int = Field(
        default=100,
        description="Max requests per time window for authenticated users"
    )
    RATE_LIMIT_AUTH_WINDOW: int = Field(
        default=60,
        description="Time window in seconds for authenticated rate limit (default: 1 minute)"
    )

    # ============================================
    # TIERED ROUTING CONFIGURATION
    # ============================================

    # Feature flags for high-risk APIs
    ENABLE_SERPAPI: bool = Field(
        default=False,
        description="Enable SerpApi for review search"
    )
    SERPAPI_API_KEY: str = Field(default="", description="SerpAPI key for review search")
    SERPAPI_MAX_SOURCES: int = Field(default=8, description="Max review sources per product")
    SERPAPI_CACHE_TTL: int = Field(default=86400, description="Redis cache TTL in seconds (24h)")
    SERPAPI_TIMEOUT: float = Field(default=15.0, description="SerpAPI request timeout")

    # Cross-provider failover: the primary review/shopping provider is Serper.dev
    # (google.serper.dev). When it errors or runs out of credits, fail over to
    # SerpApi.com (a DIFFERENT service — different endpoint/auth/schema), adapted
    # back into Serper's response shape. Default off → zero behavior change until a
    # SerpApi.com key is set and the flag is flipped in prod.
    SERPAPI_FALLBACK_ENABLED: bool = Field(default=False, description="On Serper.dev error/credit-exhaustion, fail over to SerpApi.com")
    SERPAPI_COM_API_KEY: str = Field(default="", description="SerpApi.com API key (fallback provider; different service from Serper.dev)")
    SERPAPI_COM_API_KEY_2: str = Field(default="", description="Second SerpApi.com key — tried when the first is credit-exhausted/erroring (chained fallback)")
    ENABLE_REDDIT_API: bool = Field(
        default=False,
        description="Enable Reddit API (Tier 3) - Requires commercial license and user consent"
    )
    ENABLE_YOUTUBE_TRANSCRIPTS: bool = Field(
        default=True,
        description="Enable YouTube transcript extraction (Tier 2)"
    )

    # Tier escalation settings
    MAX_AUTO_TIER: int = Field(
        default=2,
        ge=1,
        le=4,
        description="Highest tier to auto-escalate to without user consent (1-4)"
    )
    PARALLEL_API_TIMEOUT_MS: int = Field(
        default=5000,
        ge=1000,
        le=30000,
        description="Timeout per API call in milliseconds"
    )

    # Cost tracking
    LOG_API_COSTS: bool = Field(
        default=True,
        description="Track API usage costs in api_usage_logs table"
    )

    # Circuit breaker settings
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of failures before opening circuit"
    )
    CIRCUIT_BREAKER_RESET_TIMEOUT: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Seconds before attempting to close circuit"
    )

    # LLM Providers
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key")
    DEFAULT_MODEL: str = Field(default="gpt-4o-mini", description="Default LLM model to use")
    LITELLM_LOG_LEVEL: str = Field(default="INFO", description="LiteLLM logging level")

    # Agent-specific Models (override DEFAULT_MODEL for specific agents)
    PLANNER_MODEL: str = Field(default="gpt-4o-mini", description="Model for planner agent")
    INTENT_MODEL: str = Field(default="gpt-4o-mini", description="Model for intent classification agent")
    CLARIFIER_MODEL: str = Field(default="gpt-4o-mini", description="Model for clarifier agent")
    COMPOSER_MODEL: str = Field(default="gpt-4o-mini", description="Model for composer agents (OpenAI fallback when OpenRouter compose is off/unkeyed)")
    PRODUCT_SEARCH_MODEL: str = Field(default="gpt-4o-mini", description="Model for product search")

    # OpenRouter compose routing. Data-backed: in the voice bake-off (backend/eval),
    # Claude Haiku 4.5 won on BOTH quality (#1) and latency (~6.8s p50, faster than
    # gpt-4o-mini's ~9s) and handled json_object cleanly via OpenRouter. Routes ALL
    # compose calls through OpenRouter's OpenAI-compatible endpoint. Gated on the key:
    # where OPENROUTER_API_KEY is unset (e.g. an env without it) this no-ops and
    # compose falls back to COMPOSER_MODEL on OpenAI — so the switch is safe by default.
    USE_OPENROUTER_COMPOSE: bool = Field(default=True, description="Route compose calls to OpenRouter (OPENROUTER_COMPOSE_MODEL) instead of OpenAI COMPOSER_MODEL")
    OPENROUTER_COMPOSE_MODEL: str = Field(default="anthropic/claude-haiku-4.5", description="OpenRouter model slug for compose calls (bake-off winner)")
    OPENROUTER_API_KEY: str = Field(default="", description="OpenRouter API key (OpenAI-compatible endpoint)")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1", description="OpenRouter base URL")

    # Tier 2.2/2.3 grounding: route product facts through build_system_prompt's
    # tool_outputs slot and inject conversation history + a user-preference
    # profile into the blog compose call, instead of cramming everything into the
    # user message. Default off; flip on after the eval A/B confirms it helps.
    USE_GROUNDED_COMPOSE: bool = Field(default=False, description="Ground the blog compose call via tool_outputs/history/profile slots")

    # Tier 5 / A1 evidence grounding: insert review_search into the STANDARD
    # product plan (recommendation/comparison) so the composer writes from real
    # review data (editorial path) instead of invented product names + parametric
    # knowledge (concierge path). review_search self-gates on ENABLE_SERPAPI, so
    # this no-ops gracefully where SerpAPI is off. Default off — the ~+8s latency
    # is opt-in and A/B-able; flip on in prod once the eval confirms the accuracy gain.
    USE_REVIEW_GROUNDING: bool = Field(default=False, description="Insert review_search into the standard product plan so real review evidence reaches the composer (editorial path). Self-gates on ENABLE_SERPAPI; ~+8s latency.")

    # Tier 5 / A2 anti-hallucination: drop products that have NEITHER a real
    # shopping match (priced offer with a non-placeholder image) NOR real review
    # evidence — i.e. likely invented product names from the LLM search — so the
    # composer never writes about non-existent products. Keeps ≥2 verified products
    # so sparse results still render. Default off.
    USE_PRODUCT_VERIFICATION: bool = Field(default=False, description="Drop products with no real shopping match and no review evidence (anti-hallucination) before compose")

    # Tier 5 / C two-speed routing: vary blog-compose depth by query complexity
    # (re-derived in compose via the cheap heuristic classifier — no GraphState
    # passthrough). Utility queries (factoid/comparison) get terser, faster, cheaper
    # prose; considered purchases (deep_research) get room for the tradeoffs that
    # matter; recommendations keep the standard 400-word default. Default off.
    USE_TWO_SPEED_COMPOSE: bool = Field(default=False, description="Vary blog compose depth (word cap + max_tokens) by query complexity tier")

    # Tier 3 compose redesign (Option B): a draft→revise voice pass. After the blog
    # article is generated, run ONE more LLM call that polishes the assembled body
    # for maximum voice adherence (rank-and-commit, no glaze, position-by-fit)
    # without inventing facts. Adds ~one compose round-trip of latency; graceful
    # fallback to the draft on any failure. Default off.
    USE_VOICE_PASS: bool = Field(default=False, description="Run a draft→revise voice pass over the assembled blog body (Tier 3)")

    # Tier 3a compose consolidation: fold the per-product review consensus (top 3)
    # and the card descriptions into the single blog_article call's JSON schema,
    # deleting the separate consensus:* and descriptions LLM calls (5-6 round-trips
    # → 1). The blog writer already has every product's reviews/ratings in its
    # input, so it writes consensus + descriptions from the same evidence. Bake-off
    # (eval/SINGLE_CALL_BAKEOFF.md) showed this is quality-neutral on Haiku 4.5.
    # Graceful: if a consensus/description entry is missing, the template/empty
    # fallback fills it. Default off.
    USE_CONSOLIDATED_COMPOSE: bool = Field(default=False, description="Fold review consensus + descriptions into the single blog compose call (Tier 3a)")

    # Outcome 6 PROTOTYPE (conversational engine): answer-aware follow-ups.
    # The clarifier asks use_case ALONE first; once answered, the features
    # question is generated with knowledge of that answer, so it can adapt
    # ("Gaming" → "What kind of gaming?") via the packs' features_by_use_case
    # branches. COST: one extra conversation turn per search (two clarifier
    # cards instead of one) — measure on prod before any default-on decision.
    # Default off; the single-card flow is unchanged while off.
    USE_ANSWER_AWARE_FOLLOWUPS: bool = Field(default=False, description="Outcome 6 prototype: sequential clarification — use_case first, then an answer-adapted features question (doubles turns)")

    # Agent-specific Max Tokens
    PLANNER_MAX_TOKENS: int = Field(default=2000, description="Max tokens for planner agent")
    INTENT_MAX_TOKENS: int = Field(default=50, description="Max tokens for intent agent")
    CLARIFIER_MAX_TOKENS: int = Field(default=1200, description="Max tokens for clarifier agent (raised from 800 — questions now carry per-category option chips, which roughly doubles the JSON size)")
    COMPOSER_MAX_TOKENS: int = Field(default=1500, description="Max tokens for composer agents (raised from 80 — was truncating JSON output and causing Pydantic parse failures in product_compose)")
    PRODUCT_SEARCH_MAX_TOKENS: int = Field(default=500, description="Max tokens for product search")

    # Search Provider Configuration
    SEARCH_PROVIDER: str = Field(default="perplexity", description="Search provider to use")

    # OpenAI Search Provider
    OPENAI_SEARCH_BASE_URL: str = Field(default="https://api.openai.com/v1", description="OpenAI base URL")
    OPENAI_SEARCH_TIMEOUT: float = Field(default=30.0, description="OpenAI timeout in seconds")
    OPENAI_PRODUCT_DOMAINS: str = Field(default="amazon.com,ebay.com,walmart.com", description="Comma-separated list of domains for product search")
    OPENAI_SERVICE_DOMAINS: str = Field(default="g2.com,capterra.com,trustpilot.com", description="Comma-separated list of domains for service search")
    OPENAI_TRAVEL_DOMAINS: str = Field(default="tripadvisor.com,lonelyplanet.com,booking.com", description="Comma-separated list of domains for travel search")

    # Perplexity Search Provider
    PERPLEXITY_API_KEY: str = Field(default="", description="Perplexity API key")
    PERPLEXITY_BASE_URL: str = Field(default="https://api.perplexity.ai", description="Perplexity base URL")
    PERPLEXITY_MODEL: str = Field(default="sonar", description="Perplexity model")
    PERPLEXITY_TIMEOUT: float = Field(default=30.0, description="Perplexity timeout in seconds")
    PERPLEXITY_PRODUCT_DOMAINS: str = Field(default="ebay.com", description="Comma-separated list of domains for product search")
    PERPLEXITY_SERVICE_DOMAINS: str = Field(default="g2.com,capterra.com,trustpilot.com", description="Comma-separated list of domains for service search")
    PERPLEXITY_TRAVEL_DOMAINS: str = Field(default="tripadvisor.com,lonelyplanet.com", description="Comma-separated list of domains for travel search")

    @validator("PERPLEXITY_PRODUCT_DOMAINS", "PERPLEXITY_SERVICE_DOMAINS", "PERPLEXITY_TRAVEL_DOMAINS", "OPENAI_PRODUCT_DOMAINS", "OPENAI_SERVICE_DOMAINS", "OPENAI_TRAVEL_DOMAINS", pre=True)
    def parse_domain_list(cls, v):
        if isinstance(v, str):
            return v
        return v

    # Search Query Generation
    ENABLE_LLM_SEARCH_QUERY: bool = Field(
        default=False,
        description="Enable LLM-based search query generation. If False, simple slot concatenation is used."
    )
    SEARCH_QUERY_PRODUCT_SUFFIX: str = Field(
        default="no articles, blogs, news, reviews, shop. search only purchasable products with title, price, url",
        description="Suffix to append to product search queries when ENABLE_LLM_SEARCH_QUERY is False"
    )

    # eBay Partner Network
    EBAY_APP_ID: str = Field(default="", description="eBay App ID")
    EBAY_CERT_ID: str = Field(default="", description="eBay Cert ID (Client Secret)")
    EBAY_CAMPAIGN_ID: str = Field(default="", description="eBay Partner Network Campaign ID")
    EBAY_AFFILIATE_CUSTOM_ID: str = Field(default="", description="eBay custom tracking ID (optional)")
    EBAY_MKCID: str = Field(default="1", description="eBay marketing channel ID (1=EPN, 7=Site Email, 8=Marketing Email)")
    EBAY_MKRID: str = Field(default="711-53200-19255-0", description="eBay rotation ID for US marketplace")
    EBAY_TOOLID: str = Field(default="10001", description="eBay tool ID (10001=default)")
    EBAY_MKEVT: str = Field(default="1", description="eBay marketing event (1=Click, 2=Impression)")
    MAX_AFFILIATE_OFFERS_PER_PRODUCT: int = Field(default=3, description="Maximum number of affiliate offers to fetch per product")
    USE_MOCK_AFFILIATE: bool = Field(default=True, description="Use mock affiliate provider")

    # Amazon Associates / Product Advertising API
    AMAZON_API_ENABLED: bool = Field(default=False, description="Enable real Amazon PA-API (requires API credentials)")
    AMAZON_ACCESS_KEY: str = Field(default="", description="Amazon PA-API Access Key")
    AMAZON_SECRET_KEY: str = Field(default="", description="Amazon PA-API Secret Key")
    AMAZON_ASSOCIATE_TAG: str = Field(default="", description="Amazon Associate Tag (e.g., yoursite-20)")
    AMAZON_ASSOCIATE_TAGS: str = Field(
        default="US:,UK:,DE:,FR:,JP:,CA:,AU:",
        description="Comma-separated country:tag pairs for regional affiliate tags"
    )
    AMAZON_DEFAULT_COUNTRY: str = Field(default="US", description="Default country code for Amazon links")

    # Walmart Affiliate (placeholder — not yet implemented)
    WALMART_API_ENABLED: bool = Field(default=False, description="Enable Walmart affiliate API")
    WALMART_API_KEY: str = Field(default="", description="Walmart Affiliate API key")
    WALMART_AFFILIATE_ID: str = Field(default="", description="Walmart Impact Radius affiliate ID")

    # Best Buy Affiliate (placeholder — not yet implemented)
    BESTBUY_API_ENABLED: bool = Field(default=False, description="Enable Best Buy affiliate API")
    BESTBUY_API_KEY: str = Field(default="", description="Best Buy Affiliate API key")
    BESTBUY_AFFILIATE_ID: str = Field(default="", description="Best Buy affiliate tracking ID")

    # Target Affiliate (placeholder — not yet implemented)
    TARGET_API_ENABLED: bool = Field(default=False, description="Enable Target affiliate API")
    TARGET_API_KEY: str = Field(default="", description="Target Affiliate API key")
    TARGET_AFFILIATE_ID: str = Field(default="", description="Target Impact Radius affiliate ID")

    # Commission Junction (CJ) Affiliate
    CJ_API_ENABLED: bool = Field(default=False, description="Enable CJ Product Search API")
    CJ_API_KEY: str = Field(default="", description="CJ personal access token (Bearer token)")
    CJ_WEBSITE_ID: str = Field(default="", description="CJ publisher website ID (PID)")
    CJ_ADVERTISER_IDS: str = Field(
        default="joined",
        description="CJ advertiser IDs: 'joined' for all, or comma-separated CIDs"
    )
    CJ_API_TIMEOUT: float = Field(default=10.0, description="CJ API request timeout in seconds")
    CJ_CACHE_TTL: int = Field(default=28800, description="CJ search cache TTL in seconds (8 hours)")
    CJ_MAX_RESULTS: int = Field(default=20, description="Max CJ products per search request")

    # Skimlinks (sub-affiliate network — wraps non-Amazon/non-eBay merchant URLs
    # from Google Shopping into monetizable go.skimresources.com redirects).
    # DORMANT until both are set: the SerperShoppingProvider passes raw URLs
    # through unchanged when disabled, exactly the pre-Skimlinks behavior.
    SKIMLINKS_API_ENABLED: bool = Field(default=False, description="Enable Skimlinks wrapping of Google Shopping merchant URLs")
    SKIMLINKS_PUBLISHER_ID: str = Field(default="", description="Skimlinks publisher site ID (format 12345X6789, from accounts.skimlinks.com/sites)")

    # IP Geolocation
    IPINFO_TOKEN: str = Field(default="", description="IPInfo.io API token for IP geolocation")

    # Affiliate Links Display Configuration
    SHOW_AFFILIATE_LINKS_PER_PRODUCT: bool = Field(
        default=False,
        description="Include detailed affiliate links per product in responses (multiple sellers)"
    )

    # Travel APIs (Hotels & Flights)
    USE_MOCK_TRAVEL: bool = Field(default=True, description="Use mock travel providers (legacy)")
    TRAVEL_HOTEL_PROVIDERS: str = Field(default="mock", description="Comma-separated list of hotel providers")
    TRAVEL_FLIGHT_PROVIDERS: str = Field(default="mock", description="Comma-separated list of flight providers")
    BOOKING_API_KEY: str = Field(default="", description="Booking.com API key")
    BOOKING_AFFILIATE_ID: str = Field(default="", description="Booking.com affiliate ID")
    EXPEDIA_API_KEY: str = Field(default="", description="Expedia API key")
    SKYSCANNER_API_KEY: str = Field(default="", description="Skyscanner API key")
    AMADEUS_API_KEY: str = Field(default="", description="Amadeus API key")
    AMADEUS_API_SECRET: str = Field(default="", description="Amadeus API secret")
    VIATOR_AFFILIATE_ID: str = Field(default="", description="Viator affiliate ID for activity search links")

    # Travel Cache Configuration
    ENABLE_TRAVEL_CACHE: bool = Field(default=True, description="Enable Redis caching for travel searches")
    TRAVEL_CACHE_TTL: int = Field(default=3600, description="Travel cache TTL in seconds (default: 1 hour)")

    # Airport Code Cache Configuration
    ENABLE_AIRPORT_CACHE: bool = Field(default=True, description="Enable database caching for city -> airport code lookups")
    AIRPORT_CACHE_EXPIRY_DAYS: int = Field(default=180, description="Airport cache expiration in days (default: 6 months)")

    # Link Health Monitoring
    ENABLE_LINK_HEALTH_CHECKER: bool = Field(
        default=True,
        description="Enable automatic link health monitoring in background"
    )
    LINK_HEALTH_CHECK_INTERVAL_HOURS: int = Field(
        default=6,
        description="Interval in hours between automatic link health checks"
    )
    LINK_HEALTH_CHECK_TIMEOUT: int = Field(
        default=10,
        description="Timeout in seconds for each link health check request"
    )
    LINK_HEALTH_CHECK_MAX_CONCURRENT: int = Field(
        default=10,
        description="Maximum number of concurrent link health checks"
    )

    # Logging Configuration
    LOG_ENABLED: bool = Field(default=True, description="Enable/disable all logging in the application")
    LOG_LEVEL: str = Field(default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    LOG_FORMAT: str = Field(default="colored", description="Log format: json or colored")

    # Config Encryption
    CONFIG_ENCRYPTION_KEY: str = Field(default="", description="Master encryption key for sensitive config values in database (Fernet key)")

    # Observability
    SENTRY_DSN: str = Field(default="", description="Sentry DSN for error monitoring (added 2026-04-21 — empty = disabled)")
    LANGFUSE_PUBLIC_KEY: str = Field(default="", description="Langfuse public key")
    LANGFUSE_SECRET_KEY: str = Field(default="", description="Langfuse secret key")
    LANGFUSE_HOST: str = Field(default="https://cloud.langfuse.com", description="Langfuse host URL")
    LANGFUSE_OTLP_ENDPOINT: str = Field(default="/api/public/otel", description="Langfuse OTLP endpoint path")
    ENABLE_TRACING: bool = Field(default=True, description="Enable tracing")
    ENABLE_OPENTELEMETRY_EXPORT: bool = Field(default=True, description="Enable OpenTelemetry OTLP export to Langfuse")

    # OTEL Batch Processor Configuration
    OTEL_BATCH_SCHEDULE_DELAY_MILLIS: int = Field(default=5000, description="Delay between batch exports (ms)")
    OTEL_BATCH_MAX_QUEUE_SIZE: int = Field(default=2048, description="Maximum queue size for spans")
    OTEL_BATCH_MAX_EXPORT_BATCH_SIZE: int = Field(default=512, description="Maximum batch size for export")
    OTEL_BATCH_EXPORT_TIMEOUT_MILLIS: int = Field(default=30000, description="Timeout for export (ms)")

    # Additional Rate Limiting
    RATE_LIMIT_PER_IP: int = Field(default=100, description="Rate limit per IP address")
    RATE_LIMIT_PER_SESSION: int = Field(default=20, description="Rate limit per session")

    # Anonymous User Configuration
    ANONYMOUS_EMAIL_DOMAIN: str = Field(
        default="@reviewguide.ai",
        description="Email domain for anonymous users"
    )
    ANONYMOUS_EMAIL_PREFIX: str = Field(
        default="anonymous_",
        description="Email prefix for anonymous users"
    )
    ANONYMOUS_EMAIL_RANDOM_LENGTH: int = Field(
        default=16,
        description="Number of random characters in anonymous email"
    )

    # JWT
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    JWT_EXPIRATION_HOURS: int = Field(default=24, description="JWT expiration in hours")

    # Application Server
    APP_HOST: str = Field(default="0.0.0.0", description="Application host")
    APP_PORT: int = Field(default=8000, description="Application port")

    # Provider Result Limits
    EBAY_MAX_RESULTS: int = Field(default=50, description="Maximum eBay search results")
    AMADEUS_MAX_HOTEL_RESULTS: int = Field(default=50, description="Maximum Amadeus hotel results")
    AMADEUS_MAX_HOTELS_PER_REQUEST: int = Field(default=5, description="Maximum hotels per Amadeus API request")
    AMADEUS_MAX_HOTELS_TO_RETURN: int = Field(default=10, description="Maximum hotels to return in response")
    AMADEUS_MAX_FLIGHT_RESULTS: int = Field(default=10, description="Maximum Amadeus flight results")
    BOOKING_MAX_RESULTS: int = Field(default=10, description="Maximum Booking.com results")
    SKYSCANNER_MAX_RESULTS: int = Field(default=10, description="Maximum Skyscanner results")

    # Provider Timeouts and Delays
    SKYSCANNER_POLLING_DELAY: int = Field(default=2, description="Skyscanner polling delay in seconds")
    CHAT_EVENT_QUEUE_TIMEOUT: float = Field(default=0.1, description="Chat event queue timeout in seconds")
    CHAT_STREAM_SLEEP_DELAY: float = Field(default=0.01, description="Chat stream sleep delay in seconds")

    # Cache TTLs
    HALT_STATE_TTL: int = Field(default=3600, description="Halt state cache TTL in seconds")
    CHAT_HISTORY_CACHE_TTL: int = Field(default=3600, description="Chat history cache TTL in seconds")

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()


async def load_config_overrides_from_db():
    """
    Load configuration overrides using ConfigCache snapshot approach.

    Priority: Redis snapshot → Database → .env

    Single Redis operation loads entire config snapshot (Magento 2 style).
    If snapshot doesn't exist, builds from DB and caches for next time.

    This should be called on application startup to load database configs to settings.
    """
    from app.services.config_cache import get_config_cache
    from app.core.centralized_logger import get_logger

    logger = get_logger(__name__)

    try:
        # Get config cache instance
        config_cache = get_config_cache()

        # Invalidate stale Redis snapshot on startup so it rebuilds
        # from current env vars + DB (prevents stale values across deploys)
        await config_cache.invalidate_all(rebuild=False)

        # Load all configs from snapshot (Redis → DB → .env)
        config_dict = await config_cache.load_all()

        # Apply to settings instance
        overrides_applied = 0
        for key, value in config_dict.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
                overrides_applied += 1

        logger.info(f"[Config] Applied {overrides_applied} config values from snapshot")

    except Exception as e:
        logger.error(f"[Config] Failed to load config overrides: {e}", exc_info=True)
        # Don't fail startup if config loading fails
        pass
