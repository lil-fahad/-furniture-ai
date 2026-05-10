"""
Product search routes — IKEA and Alibaba.

GET  /search/ikea?query=sofa&category=sofa&max_results=10
GET  /search/alibaba?query=sofa&category=sofa&max_results=10
POST /search/blueprint-recommend   — combined AI + store search from blueprint analysis
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.models.pydantic_schemas import (
    BlueprintRecommendRequest,
    BlueprintRecommendResponse,
    ProductSearchResponse,
)
from backend.services.ikea_service import get_ikea_service
from backend.services.alibaba_service import get_alibaba_service
from backend.services.rec_service import get_recommender_service
from backend.logging.logger import logger

router = APIRouter(prefix="/search", tags=["search"])

_ikea = get_ikea_service()
_alibaba = get_alibaba_service()
_recommender = get_recommender_service()


@router.get("/ikea", response_model=ProductSearchResponse)
async def search_ikea(
    query: str = Query(..., description="Search keyword"),
    category: Optional[str] = Query(None, description="Filter by category"),
    max_results: int = Query(10, ge=1, le=50),
) -> ProductSearchResponse:
    """Search IKEA products by keyword."""
    try:
        products = _ikea.search(query=query, category=category, max_results=max_results)
        logger.info("IKEA search", extra={"query": query, "count": len(products)})
        return ProductSearchResponse(source="ikea", products=products, total=len(products))
    except Exception as exc:
        logger.exception("IKEA search failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/alibaba", response_model=ProductSearchResponse)
async def search_alibaba(
    query: str = Query(..., description="Search keyword"),
    category: Optional[str] = Query(None, description="Filter by category"),
    max_results: int = Query(10, ge=1, le=50),
) -> ProductSearchResponse:
    """Search Alibaba / AliExpress products by keyword."""
    try:
        products = _alibaba.search(query=query, category=category, max_results=max_results)
        logger.info("Alibaba search", extra={"query": query, "count": len(products)})
        return ProductSearchResponse(source="alibaba", products=products, total=len(products))
    except Exception as exc:
        logger.exception("Alibaba search failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/blueprint-recommend", response_model=BlueprintRecommendResponse)
async def blueprint_recommend(payload: BlueprintRecommendRequest) -> BlueprintRecommendResponse:
    """
    Given a style / budget / room list (from blueprint analysis),
    return AI recommendations + matching products from IKEA and Alibaba.
    """
    try:
        # Build a search query from style + rooms
        room_hint = " ".join(payload.rooms or [])
        query = f"{payload.style} furniture {room_hint}".strip()

        ikea_products = []
        alibaba_products = []

        if "ikea" in payload.sources:
            ikea_products = _ikea.search(query=query, max_results=payload.max_per_source)

        if "alibaba" in payload.sources:
            alibaba_products = _alibaba.search(query=query, max_results=payload.max_per_source)

        # AI recommendations (existing recommender)
        from backend.models.pydantic_schemas import RecommendRequest
        rec_req = RecommendRequest(
            style=payload.style,
            budget=payload.budget,
            rooms=payload.rooms,
        )
        ai_recs = _recommender.recommend(rec_req)

        logger.info(
            "blueprint-recommend",
            extra={
                "ikea": len(ikea_products),
                "alibaba": len(alibaba_products),
                "ai": len(ai_recs),
            },
        )
        return BlueprintRecommendResponse(
            ikea_products=ikea_products,
            alibaba_products=alibaba_products,
            ai_recommendations=ai_recs,
        )
    except Exception as exc:
        logger.exception("blueprint-recommend failed")
        raise HTTPException(status_code=500, detail=str(exc))
