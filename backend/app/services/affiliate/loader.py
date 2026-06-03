"""
Affiliate Provider Loader
Auto-discovers provider modules, validates env vars, and registers instances.
"""
import os
import importlib
from typing import List
from pathlib import Path

from app.core.centralized_logger import get_logger
from app.core.config import settings
from .registry import AffiliateProviderRegistry

logger = get_logger(__name__)


def _auto_import_providers() -> None:
    """
    Auto-discover and import all provider modules in the providers directory.
    This triggers their @register decorators without hard-coding imports.
    """
    providers_dir = Path(__file__).parent / "providers"

    if not providers_dir.exists():
        logger.warning(f"Affiliate providers directory not found: {providers_dir}")
        return

    provider_files = [
        f.stem for f in providers_dir.glob("*.py")
        if f.is_file() and f.stem != "__init__"
    ]

    for provider_name in provider_files:
        try:
            module_path = f"app.services.affiliate.providers.{provider_name}"
            importlib.import_module(module_path)
            logger.debug(f"Loaded affiliate provider module: {provider_name}")
        except ImportError as e:
            logger.warning(f"Failed to import affiliate provider {provider_name}: {e}")
        except Exception as e:
            logger.error(f"Error loading affiliate provider {provider_name}: {e}")


def _check_env_vars(required: List[str]) -> bool:
    """Return True if all required env vars are set and non-empty."""
    for var in required:
        if not os.environ.get(var, ""):
            return False
    return True


# Provider-specific factory kwargs, keyed by registry name.
# Each provider has different constructor signatures — this maps
# registry name -> callable returning kwargs dict for instantiation.
_PROVIDER_INIT_MAP = {
    "ebay": lambda: {
        "app_id": settings.EBAY_APP_ID,
        "cert_id": settings.EBAY_CERT_ID,
        "campaign_id": settings.EBAY_CAMPAIGN_ID,
        "custom_id": settings.EBAY_AFFILIATE_CUSTOM_ID,
    },
    "amazon": lambda: {
        "country_code": settings.AMAZON_DEFAULT_COUNTRY,
        "associate_tag": settings.AMAZON_ASSOCIATE_TAG,
    },
    "cj": lambda: {
        "api_key": settings.CJ_API_KEY,
        "website_id": settings.CJ_WEBSITE_ID,
    },
    "serper_shopping": lambda: {
        "skimlinks_publisher_id": settings.SKIMLINKS_PUBLISHER_ID,
        "skimlinks_enabled": settings.SKIMLINKS_API_ENABLED,
    },
}


def setup_affiliate_providers(manager) -> None:
    """
    Auto-import all provider modules, validate env vars, instantiate, and
    register each provider with the given AffiliateManager.
    """
    _auto_import_providers()

    registered = AffiliateProviderRegistry.list_providers()
    logger.info(f"Discovered affiliate provider classes: {registered}")

    all_info = AffiliateProviderRegistry.list_provider_info()

    for name in registered:
        info = all_info[name]
        required = info["required_env_vars"]

        if required and not _check_env_vars(required):
            missing = [v for v in required if not os.environ.get(v, "")]
            logger.warning(
                f"Skipping affiliate provider '{name}': missing required env vars {missing}"
            )
            continue

        provider_class = AffiliateProviderRegistry.get_provider_class(name)
        try:
            init_fn = _PROVIDER_INIT_MAP.get(name)
            if init_fn:
                instance = provider_class(**init_fn())
            else:
                instance = provider_class()

            manager.register_provider(name, instance)
            logger.info(f"Registered affiliate provider: {name}")
        except Exception as e:
            logger.error(f"Failed to instantiate affiliate provider '{name}': {e}")
