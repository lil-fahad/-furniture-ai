from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List, Optional

from backend.core.config import get_settings
from backend.logger import logger
from backend.models.pydantic_schemas import FurnitureRecommendation, RecommendRequest

DEFAULT_CATALOG = [
    {"item_id": "chair-1", "name": "Modern Chair", "category": "chair"},
    {"item_id": "table-1", "name": "Dining Table", "category": "table"},
    {"item_id": "sofa-1", "name": "Cozy Sofa", "category": "sofa"},
    {"item_id": "lamp-1", "name": "Floor Lamp", "category": "lighting"},
]


class RecommenderService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_path = self.settings.recommender_model_path
        self.catalog_path = Path("datasets/furniture_catalog.json")
        self.catalog = self._load_catalog()

    def _load_catalog(self) -> List[dict]:
        if self.catalog_path.exists():
            try:
                data = json.loads(self.catalog_path.read_text())
                if isinstance(data, list) and data:
                    return data
            except Exception:
                logger.warning("could not parse catalog, regenerating fallback")
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.write_text(json.dumps(DEFAULT_CATALOG, indent=2))
        return list(DEFAULT_CATALOG)

    def recommend(self, req: RecommendRequest) -> List[FurnitureRecommendation]:
        seed = sum(ord(c) for c in (req.style or "default")) or 1
        rng = random.Random(seed)
        k = min(3, len(self.catalog))
        choices = rng.sample(self.catalog, k=k)
        return [
            FurnitureRecommendation(
                item_id=item["item_id"],
                name=item["name"],
                category=item.get("category", "misc"),
                score=round(rng.uniform(0.7, 0.98), 3),
                metadata={"style": req.style, "budget": req.budget},
            )
            for item in choices
        ]


_service: RecommenderService | None = None


def get_recommender_service() -> RecommenderService:
    global _service
    if _service is None:
        _service = RecommenderService()
    return _service
