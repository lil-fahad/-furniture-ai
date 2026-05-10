"""
Furniture Search API
Search across IKEA and Alibaba catalogs by query, category, style, price range, etc.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from backend.services.ikea_service import get_ikea_service
from backend.services.alibaba_service import get_alibaba_service
from backend.models.pydantic_schemas import (
    SearchRequest,
    SearchResponse,
    FurnitureRecommendation,
)
from backend.logging.logger import logger

router = APIRouter(prefix="/search", tags=["search"])

ikea_service = get_ikea_service()
alibaba_service = get_alibaba_service()


@router.post("/furniture", response_model=SearchResponse)
async def search_furniture(payload: SearchRequest) -> SearchResponse:
    """
    Search furniture across IKEA and/or Alibaba catalogs.

    - **query**: Free-text search (name, description, tags)
    - **source**: Filter by source: `ikea`, `alibaba`, or omit for both
    - **category**: Filter by category (sofa, bed, table, chair, storage, lighting, rug, desk, wardrobe, decor)
    - **min_price** / **max_price**: Price range in USD
    - **style**: Style preference (modern, classic, scandinavian, industrial, minimalist, traditional, bohemian)
    - **limit**: Max results to return (default 20)
    """
    try:
        results: List[FurnitureRecommendation] = []
        sources_searched = []

        search_source = payload.source  # "ikea" | "alibaba" | None

        if search_source in (None, "ikea"):
            ikea_results = ikea_service.search(
                query=payload.query,
                category=payload.category,
                style=payload.style,
                max_price=payload.max_price,
                min_price=payload.min_price,
                limit=payload.limit,
            )
            results.extend(ikea_results)
            sources_searched.append("ikea")
            logger.info("IKEA search results", extra={"count": len(ikea_results)})

        if search_source in (None, "alibaba"):
            ali_results = alibaba_service.search(
                query=payload.query,
                category=payload.category,
                style=payload.style,
                max_price=payload.max_price,
                min_price=payload.min_price,
                limit=payload.limit,
            )
            results.extend(ali_results)
            sources_searched.append("alibaba")
            logger.info("Alibaba search results", extra={"count": len(ali_results)})

        # Deduplicate by item_id
        seen = set()
        unique_results = []
        for r in results:
            if r.item_id not in seen:
                seen.add(r.item_id)
                unique_results.append(r)

        # Sort by score descending
        unique_results.sort(key=lambda x: x.score, reverse=True)
        unique_results = unique_results[: payload.limit]

        logger.info(
            "search completed",
            extra={"query": payload.query, "total": len(unique_results)},
        )

        return SearchResponse(
            results=unique_results,
            total=len(unique_results),
            query=payload.query,
            source=payload.source,
        )

    except Exception as exc:
        logger.exception("search failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/furniture", response_model=SearchResponse)
async def search_furniture_get(
    q: str = Query(..., description="Search query"),
    source: Optional[str] = Query(None, description="ikea | alibaba | (omit for both)"),
    category: Optional[str] = Query(None, description="Furniture category"),
    min_price: Optional[float] = Query(None, description="Minimum price in USD"),
    max_price: Optional[float] = Query(None, description="Maximum price in USD"),
    style: Optional[str] = Query(None, description="Style preference"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
) -> SearchResponse:
    """
    GET version of furniture search — convenient for quick queries.

    Example: `/search/furniture?q=sofa&source=ikea&max_price=500&style=modern`
    """
    payload = SearchRequest(
        query=q,
        source=source,
        category=category,
        min_price=min_price,
        max_price=max_price,
        style=style,
        limit=limit,
    )
    return await search_furniture(payload)
