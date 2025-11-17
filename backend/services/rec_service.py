from pathlib import Path
from typing import List
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
        seed = int(sum([ord(c) for c in req.style]))
        random.seed(seed)
        choices = random.sample(self.catalog, k=min(3, len(self.catalog)))
        recommendations = [
            FurnitureRecommendation(
                item_id=item["item_id"],
                name=item["name"],
                category=item.get("category", "misc"),
                score=round(random.uniform(0.7, 0.98), 3),
                metadata={"style": req.style, "budget": req.budget},
            )
            for item in choices
        ]
        logger.info("recommendations generated", extra={"count": len(recommendations)})
        return recommendations


def get_recommender_service() -> RecommenderService:
    return RecommenderService()
