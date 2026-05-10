"""
Unified Furniture Recommendation Service
Combines IKEA and Alibaba catalogs to provide smart recommendations.
"""
from typing import List, Optional
import random

from backend.models.pydantic_schemas import FurnitureRecommendation, RecommendRequest
from backend.services.ikea_service import IKEAService
from backend.services.alibaba_service import AlibabaService
from backend.logging.logger import logger


class RecommenderService:
    """Unified recommender that merges IKEA + Alibaba results."""

    def __init__(self) -> None:
        self.ikea = IKEAService()
        self.alibaba = AlibabaService()
        logger.info("RecommenderService initialized with IKEA + Alibaba")

    def recommend(self, req: RecommendRequest) -> List[FurnitureRecommendation]:
        sources = req.sources or ["ikea", "alibaba"]
        all_results: List[FurnitureRecommendation] = []

        room_type = req.room_type or (req.rooms[0] if req.rooms else None)

        # Gather from IKEA
        if "ikea" in sources:
            ikea_results = self.ikea.search(
                query=req.style,
                style=req.style,
                max_price=req.budget,
                room_type=room_type,
                limit=15,
            )
            all_results.extend(ikea_results)
            logger.info("IKEA results", extra={"count": len(ikea_results)})

        # Gather from Alibaba
        if "alibaba" in sources:
            ali_results = self.alibaba.search(
                query=req.style,
                style=req.style,
                max_price=req.budget,
                room_type=room_type,
                limit=15,
            )
            all_results.extend(ali_results)
            logger.info("Alibaba results", extra={"count": len(ali_results)})

        # Filter by categories if specified
        if req.categories:
            all_results = [r for r in all_results if r.category in req.categories]

        # Filter by color preference
        if req.color_preference:
            color_lower = req.color_preference.lower()
            filtered = [
                r for r in all_results
                if any(
                    color_lower in (c.lower() if c else "")
                    for src in r.sources
                    for c in (src.colors or [])
                )
            ]
            if filtered:
                all_results = filtered

        # Filter by material preference
        if req.material_preference:
            mat_lower = req.material_preference.lower()
            filtered = [
                r for r in all_results
                if any(
                    mat_lower in (m.lower() if m else "")
                    for src in r.sources
                    for m in (src.materials or [])
                )
            ]
            if filtered:
                all_results = filtered

        # Deduplicate by item_id
        seen = set()
        unique_results = []
        for r in all_results:
            if r.item_id not in seen:
                seen.add(r.item_id)
                unique_results.append(r)

        # Sort by score descending
        unique_results.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            "recommendations generated",
            extra={"total": len(unique_results), "sources": sources},
        )
        return unique_results[:20]

    def recommend_for_blueprint(
        self,
        rooms: List[dict],
        style: str = "modern",
        budget: Optional[float] = None,
        sources: Optional[List[str]] = None,
    ) -> List[FurnitureRecommendation]:
        """Recommend furniture based on detected rooms from blueprint analysis."""
        sources = sources or ["ikea", "alibaba"]
        all_results: List[FurnitureRecommendation] = []

        # Map detection labels to room types
        room_type_map = {
            "room": "living_room",
            "bedroom": "bedroom",
            "kitchen": "kitchen",
            "bathroom": "bathroom",
            "dining": "dining_room",
            "office": "office",
            "living": "living_room",
            "living_room": "living_room",
        }

        seen_room_types = set()
        for room in rooms:
            label = room.get("label", "room").lower()
            room_type = room_type_map.get(label, "living_room")
            if room_type in seen_room_types:
                continue
            seen_room_types.add(room_type)

            if "ikea" in sources:
                ikea_results = self.ikea.recommend_for_room(
                    room_type=room_type,
                    style=style,
                    budget=budget,
                    limit=5,
                )
                all_results.extend(ikea_results)

            if "alibaba" in sources:
                ali_results = self.alibaba.recommend_for_room(
                    room_type=room_type,
                    style=style,
                    budget=budget,
                    limit=5,
                )
                all_results.extend(ali_results)

        # Deduplicate
        seen = set()
        unique_results = []
        for r in all_results:
            if r.item_id not in seen:
                seen.add(r.item_id)
                unique_results.append(r)

        unique_results.sort(key=lambda x: x.score, reverse=True)
        return unique_results[:20]


def get_recommender_service() -> RecommenderService:
    return RecommenderService()
