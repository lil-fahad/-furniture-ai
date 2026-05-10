"""
Furniture Recommendation API
Smart recommendations based on style, budget, room type, or detected blueprint rooms.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional

from backend.services.rec_service import get_recommender_service
from backend.services.yolo_service import get_yolo_service
from backend.models.pydantic_schemas import (
    RecommendRequest,
    RecommendResponse,
    FurnitureRecommendation,
)
from backend.logging.logger import logger

router = APIRouter(prefix="/recommend", tags=["recommend"])

rec_service = get_recommender_service()
yolo_service = get_yolo_service()


@router.post("/furniture", response_model=RecommendResponse)
async def recommend_furniture(payload: RecommendRequest) -> RecommendResponse:
    """
    Get furniture recommendations based on style, budget, and room preferences.

    - **style**: Design style (modern, classic, scandinavian, industrial, minimalist, traditional, bohemian)
    - **budget**: Total budget in USD (optional)
    - **room_type**: Target room (living_room, bedroom, kitchen, dining_room, bathroom, office)
    - **rooms**: List of room types to furnish
    - **sources**: Which catalogs to search: ["ikea", "alibaba"] (default: both)
    - **color_preference**: Preferred color (e.g. "white", "gray", "beige")
    - **material_preference**: Preferred material (e.g. "wood", "velvet", "metal")
    - **categories**: Filter by furniture categories
    """
    try:
        recommendations = rec_service.recommend(payload)
        sources_searched = payload.sources or ["ikea", "alibaba"]
        return RecommendResponse(
            recommendations=recommendations,
            total=len(recommendations),
            sources_searched=sources_searched,
        )
    except Exception as exc:
        logger.exception("recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/blueprint", response_model=RecommendResponse)
async def recommend_from_blueprint(
    file: UploadFile = File(...),
    style: str = "modern",
    budget: Optional[float] = None,
    sources: str = "ikea,alibaba",
) -> RecommendResponse:
    """
    Upload a floor plan image and get furniture recommendations for each detected room.

    The API will:
    1. Analyze the blueprint to detect rooms
    2. Identify room types (living room, bedroom, kitchen, etc.)
    3. Return tailored furniture recommendations for each room

    - **file**: Floor plan / blueprint image (PNG, JPG, PDF)
    - **style**: Design style preference (default: modern)
    - **budget**: Total budget in USD (optional)
    - **sources**: Comma-separated catalog sources: ikea,alibaba (default: both)
    """
    try:
        sources_list = [s.strip() for s in sources.split(",") if s.strip()]

        # Step 1: Analyze blueprint
        detections, _ = yolo_service.analyze(file)
        logger.info("blueprint analyzed for recommendations", extra={"rooms": len(detections)})

        if not detections:
            raise HTTPException(status_code=422, detail="No rooms detected in the blueprint image")

        # Step 2: Get recommendations per room
        rooms_raw = [
            {
                "label": d.room_type or d.label,
                "room_type": d.room_type or d.label,
                "area_sqm": d.area_sqm,
            }
            for d in detections
        ]

        recommendations = rec_service.recommend_for_blueprint(
            rooms=rooms_raw,
            style=style,
            budget=budget,
            sources=sources_list,
        )

        logger.info(
            "blueprint recommendations generated",
            extra={"rooms": len(detections), "items": len(recommendations)},
        )

        return RecommendResponse(
            recommendations=recommendations,
            total=len(recommendations),
            sources_searched=sources_list,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("blueprint recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/room", response_model=RecommendResponse)
async def recommend_for_room(
    room_type: str,
    style: str = "modern",
    budget: Optional[float] = None,
    sources: str = "ikea,alibaba",
) -> RecommendResponse:
    """
    Get furniture recommendations for a specific room type.

    - **room_type**: living_room | bedroom | kitchen | dining_room | bathroom | office
    - **style**: Design style (modern, classic, scandinavian, industrial, minimalist, traditional, bohemian)
    - **budget**: Budget in USD (optional)
    - **sources**: Comma-separated: ikea,alibaba (default: both)
    """
    try:
        sources_list = [s.strip() for s in sources.split(",") if s.strip()]

        payload = RecommendRequest(
            style=style,
            budget=budget,
            room_type=room_type,
            sources=sources_list,
        )
        recommendations = rec_service.recommend(payload)

        return RecommendResponse(
            recommendations=recommendations,
            total=len(recommendations),
            sources_searched=sources_list,
        )
    except Exception as exc:
        logger.exception("room recommendation failed")
        raise HTTPException(status_code=500, detail=str(exc))
