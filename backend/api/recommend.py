from fastapi import APIRouter, HTTPException

from backend.services.rec_service import get_recommender_service
from backend.services.ai_service import get_ai_service
from backend.models.pydantic_schemas import (
    RecommendRequest,
    RecommendResponse,
    FurnitureRecommendation,
)
from backend.logging.logger import logger

router = APIRouter(prefix="/recommend", tags=["recommend"])

rec_service = get_recommender_service()
ai_service = get_ai_service()


@router.post("/furniture", response_model=RecommendResponse)
async def recommend_furniture(payload: RecommendRequest) -> RecommendResponse:
    try:
        # Base recommendations from the catalog (always available as fallback)
        base_recommendations = rec_service.recommend(payload)

        # Attempt AI-enhanced ranking/enrichment via Qwen
        ai_items = ai_service.enhance_furniture_recommendations(
            style=payload.style,
            budget=payload.budget,
            rooms=payload.rooms,
            base_catalog=rec_service.catalog,
        )

        if ai_items:
            # Merge AI results: use AI score/reason, fall back to base data for missing fields
            base_map = {r.item_id: r for r in base_recommendations}
            enriched: list[FurnitureRecommendation] = []
            for item in ai_items:
                base = base_map.get(item.get("item_id"))
                enriched.append(
                    FurnitureRecommendation(
                        item_id=item.get("item_id", "unknown"),
                        name=item.get("name", base.name if base else "Unknown"),
                        category=item.get("category", base.category if base else "misc"),
                        score=float(item.get("score", base.score if base else 0.8)),
                        metadata={
                            "style": payload.style,
                            "budget": payload.budget,
                            "ai_reason": item.get("ai_reason", ""),
                            "ai_enhanced": True,
                        },
                    )
                )
            logger.info("recommend: returning AI-enhanced results", extra={"count": len(enriched)})
            return RecommendResponse(recommendations=enriched)

        # AI unavailable or returned no results — use base recommendations
        logger.info("recommend: returning base recommendations", extra={"count": len(base_recommendations)})
        return RecommendResponse(recommendations=base_recommendations)

    except Exception as exc:
        logger.exception("recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))
