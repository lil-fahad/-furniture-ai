from pathlib import Path
from typing import List, Optional
import json
import random

from backend.models.pydantic_schemas import FurnitureRecommendation, RecommendRequest
from backend.core.config import get_settings
from backend.logging.logger import logger


class RecommenderService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_path = self.settings.recommender_model_path
        self.catalog_path = Path("datasets/furniture_catalog.json")
        self.catalog = self._load_catalog()
        # Lazy-load DashScope to avoid circular imports
        self._ai = None

    def _get_ai(self):
        if self._ai is None:
            try:
                from backend.services.dashscope_service import get_dashscope_service
                self._ai = get_dashscope_service()
            except Exception:
                self._ai = None
        return self._ai

    def _load_catalog(self) -> List[dict]:
        if self.catalog_path.exists():
            try:
                return json.loads(self.catalog_path.read_text())
            except Exception:
                logger.warning("could not parse catalog, regenerating fallback")
        fallback = [
            {"item_id": "chair-1", "name": "Modern Chair", "category": "chair"},
            {"item_id": "table-1", "name": "Dining Table", "category": "table"},
            {"item_id": "sofa-1", "name": "Cozy Sofa", "category": "sofa"},
            {"item_id": "lamp-1", "name": "Floor Lamp", "category": "lighting"},
        ]
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.write_text(json.dumps(fallback, indent=2))
        return fallback

    def recommend(self, req: RecommendRequest) -> List[FurnitureRecommendation]:
        # Try AI-powered recommendations first
        ai = self._get_ai()
        if ai and ai.is_available:
            try:
                ai_result = ai.recommend_furniture(
                    style=req.style,
                    budget=req.budget,
                    rooms=req.rooms,
                )
                ai_recs = ai_result.get("recommendations", [])
                if ai_recs:
                    recommendations = []
                    for i, item in enumerate(ai_recs[:5]):
                        recommendations.append(
                            FurnitureRecommendation(
                                item_id=f"ai-{req.style}-{i}",
                                name=item.get("name", f"Item {i+1}"),
                                category=item.get("category", "misc"),
                                score=round(0.95 - i * 0.03, 3),
                                metadata={
                                    "style": req.style,
                                    "budget": req.budget,
                                    "source": item.get("source", ""),
                                    "price_range": item.get("price_range", ""),
                                    "reason": item.get("reason", ""),
                                    "ai_powered": True,
                                    "summary": ai_result.get("summary", ""),
                                },
                            )
                        )
                    logger.info("AI recommendations generated", extra={"count": len(recommendations)})
                    return recommendations
            except Exception as exc:
                logger.warning("AI recommendation failed, falling back: %s", exc)

        # Fallback: catalog-based recommendations
        seed = int(sum([ord(c) for c in req.style]))
        random.seed(seed)
        choices = random.sample(self.catalog, k=min(3, len(self.catalog)))
        recommendations = [
            FurnitureRecommendation(
                item_id=item["item_id"],
                name=item["name"],
                category=item.get("category", "misc"),
                score=round(random.uniform(0.7, 0.98), 3),
                metadata={"style": req.style, "budget": req.budget, "ai_powered": False},
            )
            for item in choices
        ]
        logger.info("catalog recommendations generated", extra={"count": len(recommendations)})
        return recommendations


def get_recommender_service() -> RecommenderService:
    return RecommenderService()
