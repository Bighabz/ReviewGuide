"""
Affiliate Click Tracking API

Provides endpoint to track affiliate link clicks for analytics.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.centralized_logger import get_logger
from app.core.database import get_db
from app.core.dependencies import check_rate_limit
from app.models.affiliate_click import AffiliateClick

logger = get_logger(__name__)
router = APIRouter()


class ClickRequest(BaseModel):
    """Affiliate click tracking request"""
    provider: str = Field(..., max_length=100, description="Affiliate provider name")
    product_name: Optional[str] = Field(None, max_length=500, description="Product name")
    category: Optional[str] = Field(None, max_length=100, description="Product category")
    url: str = Field(..., max_length=2048, description="Affiliate URL clicked")
    session_id: Optional[str] = Field(None, max_length=255, description="User session ID")


class ClickResponse(BaseModel):
    """Affiliate click tracking response"""
    tracked: bool


class EventRequest(BaseModel):
    """General UI event tracking request"""
    event: str = Field(..., max_length=100, description="Event name")
    payload: dict = Field(default_factory=dict, description="Event payload")


@router.post("/event", dependencies=[Depends(check_rate_limit)])
async def track_event(
    request: EventRequest,
    db: AsyncSession = Depends(get_db),
):
    """Track a named UI event (e.g., suggestion_click). Logs for now; no DB write required."""
    # Strip CR/LF so a crafted event/payload can't forge extra log lines (log injection).
    safe_event = request.event.replace("\r", " ").replace("\n", " ")[:100]
    safe_payload = str(request.payload).replace("\r", " ").replace("\n", " ")[:500]
    logger.info(f"[affiliate] event={safe_event} payload={safe_payload}")
    return {"status": "ok"}


@router.post("/click", response_model=ClickResponse, dependencies=[Depends(check_rate_limit)])
async def track_click(request: ClickRequest, db: AsyncSession = Depends(get_db)):
    """Track an affiliate link click"""
    try:
        click = AffiliateClick(
            session_id=request.session_id,
            provider=request.provider,
            product_name=request.product_name,
            category=request.category,
            url=request.url,
        )
        db.add(click)
        await db.commit()
        logger.info(f"Tracked affiliate click: {request.provider} - {request.product_name}")
        return ClickResponse(tracked=True)
    except Exception as e:
        logger.error(f"Failed to track affiliate click: {e}")
        await db.rollback()
        return ClickResponse(tracked=False)


class CJSearchRequest(BaseModel):
    keywords: str
    advertiser_ids: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    limit: int = 10


class CJProductResponse(BaseModel):
    title: str
    price: float
    currency: str
    buy_url: str
    merchant: str
    image_url: Optional[str] = None
    product_id: str = ""


class CJSearchResponse(BaseModel):
    results: List[CJProductResponse]
    count: int


@router.post("/cj/search", response_model=CJSearchResponse, dependencies=[Depends(check_rate_limit)])
async def cj_search(req: CJSearchRequest):
    """Search CJ product catalog"""
    from app.services.affiliate.manager import affiliate_manager

    provider = affiliate_manager.get_provider("cj")
    if not provider:
        return CJSearchResponse(results=[], count=0)

    products = await provider.search_products(
        query=req.keywords,
        min_price=req.min_price,
        max_price=req.max_price,
        limit=req.limit,
        advertiser_ids=req.advertiser_ids,
    )

    results = [
        CJProductResponse(
            title=p.title,
            price=p.price,
            currency=p.currency,
            buy_url=p.affiliate_link,
            merchant=p.merchant,
            image_url=p.image_url,
            product_id=p.product_id,
        )
        for p in products
    ]

    return CJSearchResponse(results=results, count=len(results))
