from typing import List
from fastapi import APIRouter, HTTPException

from backend.services.rec_service import get_recommender_service
from backend.models.pydantic_schemas import (
    RecommendRequest,
    RecommendResponse,
    CatalogItem,
    CatalogResponse,
    CategoriesResponse,
)
from backend.logging.logger import logger

router = APIRouter(prefix="/recommend", tags=["recommend"])

rec_service = get_recommender_service()


@router.get("/catalog", response_model=CatalogResponse)
async def list_catalog() -> CatalogResponse:
    items = [CatalogItem(**item) for item in rec_service.get_catalog()]
    return CatalogResponse(items=items)


@router.get("/categories", response_model=CategoriesResponse)
async def list_categories() -> CategoriesResponse:
    return CategoriesResponse(categories=rec_service.get_categories())


@router.post("/furniture", response_model=RecommendResponse)
async def recommend_furniture(payload: RecommendRequest) -> RecommendResponse:
    try:
        recommendations = rec_service.recommend(payload)
        return RecommendResponse(recommendations=recommendations)
    except Exception as exc:
        logger.exception("recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))
