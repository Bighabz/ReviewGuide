"""
Admin API Endpoints

Provides REST endpoints for admin dashboard:
- Config management (CRUD for core_config table)
- Metrics (request volume, errors, business metrics, top queries)
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import os
import pytz
from collections import defaultdict
from langfuse import Langfuse

from app.core.database import get_db
from app.core.centralized_logger import get_logger
from app.core.config import settings
from app.core.dependencies import check_rate_limit
from app.services.config_service import ConfigService
from app.api.v1.admin_auth import get_current_admin_user

logger = get_logger(__name__)
router = APIRouter(tags=["admin"])

# Get timezone from config
APP_TIMEZONE = pytz.timezone(settings.TIMEZONE)

# Initialize Langfuse client for fetching traces
langfuse_client = Langfuse(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST
)

# Cache for Langfuse error data to avoid hitting rate limits
# Cache expires after 2 minutes (120 seconds)
_langfuse_error_cache = {
    "data": None,
    "timestamp": None,
    "ttl": 120  # seconds
}


# ===== Pydantic Models =====

class ConfigItem(BaseModel):
    id: Optional[int] = None
    key: str
    value: str
    source: str  # 'db' or 'env'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConfigUpdate(BaseModel):
    value: str


class MetricsResponse(BaseModel):
    request_volume: Dict[str, Any]
    error_rate: Dict[str, Any]
    business_metrics: Dict[str, Any]
    top_queries: Dict[str, Any]


# ===== Config Endpoints =====

@router.get("/config", response_model=List[ConfigItem])
async def list_configs(
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_user),
):
    """
    List all configuration items from both database and .env

    Returns configs from core_config table merged with .env defaults
    Sensitive values (API keys, secrets, passwords) are masked with *********
    """
    try:
        service = ConfigService(db)
        return await service.list_all_configs()
    except Exception as e:
        logger.error(f"[admin] Error listing configs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list configs: {str(e)}")


@router.get("/config/{config_id}", response_model=ConfigItem)
async def get_config(
    config_id: int,
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_user),
):
    """Get a single config item by ID (sensitive values masked with *********)"""
    try:
        service = ConfigService(db)
        config = await service.get_config_by_id(config_id)

        if not config:
            raise HTTPException(status_code=404, detail="Config not found")

        return config

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[admin] Error getting config {config_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/config/{config_id}", response_model=ConfigItem)
async def update_config(
    config_id: int,
    update: ConfigUpdate,
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_user),
):
    """Update a config value (updates DB, Redis cache, and in-memory settings)"""
    try:
        service = ConfigService(db)
        return await service.update_config(config_id, update.value)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"[admin] Error updating config {config_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")


@router.delete("/config/{config_id}")
async def delete_config(
    config_id: int,
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_user),
):
    """Delete a config (deletes from DB and Redis, reverts to .env default)"""
    try:
        service = ConfigService(db)
        await service.delete_config(config_id)
        return {"message": "Config deleted, reverted to .env default"}

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"[admin] Error deleting config {config_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete config: {str(e)}")


@router.post("/config", response_model=ConfigItem)
async def create_config(
    config: ConfigItem,
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_user),
):
    """Create a new config override (saves to DB, Redis cache, and in-memory settings)"""
    try:
        service = ConfigService(db)
        return await service.create_config(config.key, config.value)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        await db.rollback()
        logger.error(f"[admin] Error creating config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create config: {str(e)}")


@router.post("/config/clear-cache")
async def clear_config_cache(
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_user),
):
    """Invalidate config cache snapshot and rebuild (cache warming)"""
    try:
        service = ConfigService(db)
        success = await service.clear_cache()

        if success:
            return {
                "message": "Config cache cleared and rebuilt successfully",
                "success": True
            }
        else:
            return {
                "message": "Redis not available, cache not cleared",
                "success": False
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[admin] Error clearing config cache: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear config cache")


# ===== Helper Functions =====

def fetch_langfuse_errors(hours: int = 24) -> List[Dict]:
    """
    Fetch error observations from Langfuse for the specified time range.

    Note: Langfuse tracks errors at the observation level (spans, generations, events),
    not at the trace level. We fetch traces and then check their observations for ERROR level.

    Uses a 2-minute cache to avoid hitting Langfuse rate limits.

    Args:
        hours: Number of hours to look back (default: 24)

    Returns:
        List of error observations with timestamp and error details
    """
    try:
        # Check cache first to avoid hitting rate limits
        now = datetime.utcnow()
        if (_langfuse_error_cache["data"] is not None and
            _langfuse_error_cache["timestamp"] is not None):

            cache_age = (now - _langfuse_error_cache["timestamp"]).total_seconds()
            if cache_age < _langfuse_error_cache["ttl"]:
                logger.info(f"[admin] Using cached Langfuse error data (age: {cache_age:.1f}s)")
                return _langfuse_error_cache["data"]

        logger.info(f"[admin] Fetching fresh Langfuse traces from last {hours} hours")

        # Fetch traces from Langfuse using the correct API
        # Use langfuse_client.api.trace.list() to get traces
        # Note: Langfuse API has a maximum limit of 100 traces per request
        traces_response = langfuse_client.api.trace.list(limit=100)

        error_observations = []

        # Check if traces_response has data
        if not hasattr(traces_response, 'data'):
            logger.warning(f"[admin] Langfuse response has no 'data' attribute: {type(traces_response)}")
            return []

        logger.info(f"[admin] Found {len(traces_response.data)} traces to analyze")

        # Calculate time range for filtering
        # Make from_timestamp timezone-aware (UTC) to match Langfuse timestamps
        from_timestamp = datetime.utcnow().replace(tzinfo=pytz.UTC) - timedelta(hours=hours)

        # Iterate through traces and check their observations for ERROR level
        for trace in traces_response.data:
            trace_id = trace.id if hasattr(trace, 'id') else None
            trace_timestamp = trace.timestamp if hasattr(trace, 'timestamp') else None

            if not trace_id:
                continue

            # Skip traces older than our time range
            if trace_timestamp and trace_timestamp < from_timestamp:
                continue

            # Fetch full trace details to get observations
            try:
                trace_details = langfuse_client.api.trace.get(trace_id)

                # Check if trace has observations
                if hasattr(trace_details, 'observations') and trace_details.observations:
                    for obs in trace_details.observations:
                        # Check if observation has ERROR level
                        # The level is an enum: ObservationLevel.ERROR
                        if hasattr(obs, 'level') and str(obs.level) == 'ObservationLevel.ERROR':
                            obs_timestamp = obs.start_time if hasattr(obs, 'start_time') else trace_timestamp
                            error_observations.append({
                                'timestamp': obs_timestamp,
                                'status_message': getattr(obs, 'status_message', 'Unknown error'),
                                'trace_id': trace_id,
                                'observation_id': obs.id if hasattr(obs, 'id') else None
                            })
            except Exception as trace_error:
                logger.warning(f"[admin] Error fetching trace details for {trace_id}: {str(trace_error)}")
                continue

        logger.info(f"[admin] Found {len(error_observations)} error observations")

        # Update cache with fresh data
        _langfuse_error_cache["data"] = error_observations
        _langfuse_error_cache["timestamp"] = now

        return error_observations

    except Exception as e:
        logger.error(f"[admin] Error fetching Langfuse traces: {str(e)}", exc_info=True)
        # Return cached data if available, even if expired, when API fails
        if _langfuse_error_cache["data"] is not None:
            logger.warning("[admin] Returning stale cached data due to API error")
            return _langfuse_error_cache["data"]
        return []


# ===== Metrics Endpoints =====

@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_user),
):
    """
    Get all dashboard metrics:
    - Request volume (1 hour, 24 hours, requests per minute)
    - Error rate (24h count, percentage, top errors)
    - Business metrics (CTR, impressions, cost per query)
    - Top queries (most popular, most expensive)
    """
    try:
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(days=1)

        # Request Volume (only count user messages)
        result_1h = await db.execute(
            text("SELECT COUNT(*) FROM conversation_messages WHERE created_at >= :time AND role = 'user'"),
            {"time": one_hour_ago}
        )
        requests_1h = result_1h.fetchone()[0] or 0

        result_24h = await db.execute(
            text("SELECT COUNT(*) FROM conversation_messages WHERE created_at >= :time AND role = 'user'"),
            {"time": one_day_ago}
        )
        requests_24h = result_24h.fetchone()[0] or 0

        # Requests per minute (last hour)
        rpm = round(requests_1h / 60, 2) if requests_1h > 0 else 0

        # Error Count - Fetch from Langfuse (last 24 hours)
        error_traces = fetch_langfuse_errors(hours=24)
        errors_24h = len(error_traces)

        # Get top error messages (group by status_message)
        error_counts = defaultdict(int)
        for error in error_traces:
            msg = error.get('status_message', 'Unknown error')
            error_counts[msg] += 1

        # Sort and get top 5 errors
        top_errors = [
            {"message": msg, "count": count}
            for msg, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        ]

        # Business Metrics
        # These would come from your affiliate tracking tables
        # For now, returning mock structure - implement based on your actual tables
        affiliate_ctr = 0.0
        travel_ctr = 0.0
        travel_impressions = 0
        cost_per_query = 0.0

        # Top Queries
        # Get most popular queries
        try:
            result_popular = await db.execute(
                text("""
                SELECT content, COUNT(*) as count
                FROM conversation_messages
                WHERE role = 'user' AND created_at >= :time
                GROUP BY content
                ORDER BY count DESC
                LIMIT 10
                """),
                {"time": one_day_ago}
            )
            popular_queries = [{"query": row[0], "count": row[1]} for row in result_popular.fetchall()]
        except:
            popular_queries = []

        # Most expensive queries (mock - would need cost tracking)
        expensive_queries = []

        return {
            "request_volume": {
                "requests_1h": requests_1h,
                "requests_24h": requests_24h,
                "rpm": rpm,
                "chart_data": []  # Will be populated by frontend from conversation_messages
            },
            "error_rate": {
                "errors_24h": errors_24h,
                "top_errors": top_errors
            },
            "business_metrics": {
                "affiliate_ctr": affiliate_ctr,
                "travel_ctr": travel_ctr,
                "travel_impressions": travel_impressions,
                "cost_per_query": cost_per_query
            },
            "top_queries": {
                "popular": popular_queries,
                "expensive": expensive_queries
            }
        }

    except Exception as e:
        logger.error(f"[admin] Error fetching metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch metrics: {str(e)}")


@router.get("/metrics/chart")
async def get_chart_data(
    timeframe: str = "1h",  # '1h' or '24h'
    db: Session = Depends(get_db),
    _admin: dict = Depends(get_current_admin_user),
):
    """
    Get time-series data for charts
    Returns requests per minute over the specified timeframe
    """
    try:
        now = datetime.utcnow()

        if timeframe == "1h":
            start_time = now - timedelta(hours=1)
            interval = "minute"
        else:  # 24h
            start_time = now - timedelta(days=1)
            interval = "hour"

        # Get request counts grouped by time interval (only user messages)
        result = await db.execute(
            text(f"""
            SELECT
                DATE_TRUNC('{interval}', created_at) as time_bucket,
                COUNT(*) as count
            FROM conversation_messages
            WHERE created_at >= :start_time AND role = 'user'
            GROUP BY time_bucket
            ORDER BY time_bucket
            """),
            {"start_time": start_time}
        )

        # Convert UTC times to configured timezone (UTC+7)
        data_points = [
            {
                "time": pytz.utc.localize(row[0]).astimezone(APP_TIMEZONE).isoformat(),
                "count": row[1]
            }
            for row in result.fetchall()
        ]

        return {"data": data_points, "timeframe": timeframe}

    except Exception as e:
        logger.error(f"[admin] Error fetching chart data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch chart data: {str(e)}")


@router.get("/metrics/errors/chart")
async def get_error_chart_data(
    timeframe: str = "24h",  # '1h' or '24h'
    db: Session = Depends(get_db)
):
    """
    Get time-series data for error rate chart
    Returns error counts over the specified timeframe from Langfuse
    """
    try:
        now = datetime.utcnow()

        if timeframe == "1h":
            hours = 1
            interval = "minute"
        else:  # 24h
            hours = 24
            interval = "hour"

        # Fetch error traces from Langfuse
        error_traces = fetch_langfuse_errors(hours=hours)

        # Group errors by time bucket
        time_buckets = defaultdict(int)

        for error in error_traces:
            # Get timestamp from error trace
            error_time = error.get('timestamp')
            if error_time:
                # Convert to datetime if it's a string
                if isinstance(error_time, str):
                    error_time = datetime.fromisoformat(error_time.replace('Z', '+00:00'))

                # Truncate to hour or minute based on interval
                if interval == "hour":
                    bucket = error_time.replace(minute=0, second=0, microsecond=0)
                else:  # minute
                    bucket = error_time.replace(second=0, microsecond=0)

                # Convert to UTC if it has timezone info
                if error_time.tzinfo:
                    bucket = bucket.replace(tzinfo=pytz.utc)
                else:
                    bucket = pytz.utc.localize(bucket)

                time_buckets[bucket] += 1

        # Convert to sorted list of data points with timezone conversion
        data_points = [
            {
                "time": bucket.astimezone(APP_TIMEZONE).isoformat(),
                "count": count
            }
            for bucket, count in sorted(time_buckets.items())
        ]

        return {"data": data_points, "timeframe": timeframe}

    except Exception as e:
        logger.error(f"[admin] Error fetching error chart data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch error chart data: {str(e)}")


# ===== Internal Model Cache Endpoint =====

@router.post("/internal/model-cache/invalidate")
async def invalidate_model_cache(
    reason: str = Query(default="manual", max_length=120),
    admin: dict = Depends(get_current_admin_user),
    _rate_limit: None = Depends(check_rate_limit),
):
    """
    Invalidate the LLM instance cache on the model service.

    Useful after rotating the OpenAI API key so stale ChatOpenAI instances
    (which embed the old key) are evicted and recreated on the next request.

    Requires admin Bearer token.

    Returns:
        {"cleared": N, "reason": "..."}
    """
    from app.services.model_service import model_service
    cleared = model_service.invalidate_cache(reason=reason)
    return {"cleared": cleared, "reason": reason}
