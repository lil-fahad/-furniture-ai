from fastapi import APIRouter, HTTPException

from backend.services.rec_service import get_recommender_service
from backend.models.pydantic_schemas import RecommendRequest, RecommendResponse
from backend.logging.logger import logger

router = APIRouter(prefix="/recommend", tags=["recommend"])

rec_service = get_recommender_service()


@router.post("/furniture", response_model=RecommendResponse)
async def recommend_furniture(payload: RecommendRequest) -> RecommendResponse:
    try:
        recommendations = rec_service.recommend(payload)
        return RecommendResponse(recommendations=recommendations)
    except Exception as exc:
        logger.exception("recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))
