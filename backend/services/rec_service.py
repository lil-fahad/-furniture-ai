"""
Smart furniture recommender that merges IKEA + Alibaba catalogs
and scores products based on style, budget, room type, and color.
"""
from __future__ import annotations

import logging
import math
from typing import List, Optional

from backend.models.pydantic_schemas import (
    FurnitureProduct,
    FurnitureRecommendation,
    RecommendRequest,
)
from backend.services.ikea_service import get_ikea_service
from backend.services.alibaba_service import get_alibaba_service
from backend.services.dashscope_service import get_dashscope_service

logger = logging.getLogger("furniture_ai")

# Style → category priority mapping
STYLE_CATEGORY_WEIGHTS: dict = {
    "modern":       {"sofa": 1.0, "chair": 0.9, "table": 0.9, "storage": 0.8, "lighting": 0.8, "desk": 0.7, "rug": 0.6, "bed": 0.8},
    "scandinavian": {"sofa": 1.0, "chair": 0.9, "table": 0.8, "storage": 0.9, "lighting": 0.7, "rug": 0.8, "bed": 0.7, "desk": 0.6},
    "industrial":   {"storage": 1.0, "desk": 0.9, "chair": 0.8, "lighting": 0.9, "table": 0.7, "sofa": 0.6, "rug": 0.5, "bed": 0.5},
    "luxury":       {"sofa": 1.0, "bed": 1.0, "table": 0.9, "chair": 0.9, "lighting": 0.8, "rug": 0.8, "storage": 0.7, "desk": 0.6},
    "minimalist":   {"sofa": 0.9, "table": 0.9, "storage": 1.0, "chair": 0.8, "desk": 0.9, "lighting": 0.7, "rug": 0.5, "bed": 0.8},
    "classic":      {"sofa": 1.0, "chair": 0.9, "table": 0.9, "rug": 1.0, "storage": 0.8, "lighting": 0.7, "bed": 0.8, "desk": 0.5},
    "office":       {"desk": 1.0, "chair": 1.0, "storage": 0.9, "lighting": 0.8, "table": 0.6, "sofa": 0.4, "rug": 0.3, "bed": 0.0},
}

# Room type → relevant categories
ROOM_CATEGORY_MAP: dict = {
    "living room":  ["sofa", "table", "chair", "lighting", "rug", "storage"],
    "bedroom":      ["bed", "storage", "lighting", "rug", "chair"],
    "office":       ["desk", "chair", "storage", "lighting"],
    "dining room":  ["table", "chair", "lighting", "rug", "storage"],
    "kitchen":      ["table", "chair", "storage", "lighting"],
    "hallway":      ["storage", "lighting", "rug"],
    "room":         ["sofa", "table", "chair", "storage", "lighting"],
}


def _style_score(product: FurnitureProduct, style: str) -> float:
    """Score 0-1 based on how well product matches requested style."""
    if not product.styles:
        return 0.5
    style_lower = style.lower()
    # Direct match
    if style_lower in [s.lower() for s in product.styles]:
        return 1.0
    # Partial / related match
    related = {
        "modern": ["minimalist", "contemporary", "scandinavian"],
        "scandinavian": ["nordic", "minimalist", "natural"],
        "industrial": ["loft", "vintage", "rustic"],
        "luxury": ["italian", "classic", "premium"],
        "minimalist": ["modern", "scandinavian", "contemporary"],
        "classic": ["traditional", "vintage", "luxury"],
    }
    related_styles = related.get(style_lower, [])
    for ps in product.styles:
        if ps.lower() in related_styles:
            return 0.7
    return 0.3


def _budget_score(product: FurnitureProduct, budget: Optional[float]) -> float:
    """Score 0-1 based on budget fit. Products well under budget score higher."""
    if budget is None or product.price is None:
        return 0.8
    if product.price > budget:
        return 0.0
    ratio = product.price / budget
    # Sweet spot: 50-80% of budget
    if 0.5 <= ratio <= 0.8:
        return 1.0
    elif ratio < 0.5:
        return 0.7
    else:
        return 0.9


def _room_score(product: FurnitureProduct, rooms: Optional[List[str]]) -> float:
    """Score based on how relevant the product category is for the given rooms."""
    if not rooms:
        return 0.8
    best = 0.0
    for room in rooms:
        room_lower = room.lower()
        relevant_cats = ROOM_CATEGORY_MAP.get(room_lower, ROOM_CATEGORY_MAP["room"])
        if product.category.lower() in relevant_cats:
            idx = relevant_cats.index(product.category.lower())
            score = 1.0 - (idx * 0.1)
            best = max(best, score)
    return best if best > 0 else 0.3


def _category_weight(product: FurnitureProduct, style: str) -> float:
    weights = STYLE_CATEGORY_WEIGHTS.get(style.lower(), {})
    return weights.get(product.category.lower(), 0.5)


def _rating_score(product: FurnitureProduct) -> float:
    if product.rating is None:
        return 0.7
    return (product.rating - 1.0) / 4.0  # normalize 1-5 → 0-1


def _compute_score(
    product: FurnitureProduct,
    style: str,
    budget: Optional[float],
    rooms: Optional[List[str]],
) -> float:
    s = _style_score(product, style)
    b = _budget_score(product, budget)
    r = _room_score(product, rooms)
    c = _category_weight(product, style)
    rt = _rating_score(product)
    # Weighted combination
    score = 0.30 * s + 0.25 * b + 0.20 * r + 0.15 * c + 0.10 * rt
    return round(min(score, 1.0), 3)


def _build_reason(product: FurnitureProduct, style: str, budget: Optional[float]) -> str:
    parts = []
    if product.styles and style.lower() in [s.lower() for s in product.styles]:
        parts.append(f"matches your {style} style")
    if budget and product.price and product.price <= budget:
        parts.append(f"fits your ${budget:.0f} budget at ${product.price:.0f}")
    if product.rating and product.rating >= 4.5:
        parts.append(f"highly rated ({product.rating}/5)")
    if product.source == "ikea":
        parts.append("available at IKEA")
    elif product.source == "alibaba":
        parts.append("available on Alibaba")
    return "; ".join(parts) if parts else "recommended based on your preferences"


class RecommenderService:
    def __init__(self) -> None:
        self.ikea = get_ikea_service()
        self.alibaba = get_alibaba_service()
        self.ai = get_dashscope_service()

    def recommend(self, req: RecommendRequest) -> List[FurnitureRecommendation]:
        sources = req.preferred_sources or ["ikea", "alibaba"]

        all_products: List[FurnitureProduct] = []
        if "ikea" in sources:
            all_products.extend(self.ikea.get_all())
        if "alibaba" in sources:
            all_products.extend(self.alibaba.get_all())

        # Score every product
        scored = []
        for product in all_products:
            score = _compute_score(product, req.style, req.budget, req.rooms)
            if score > 0:
                scored.append((score, product))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate by category — take top 2 per category for variety
        seen_categories: dict = {}
        results: List[FurnitureRecommendation] = []
        for score, product in scored:
            cat = product.category
            count = seen_categories.get(cat, 0)
            if count < 2:
                seen_categories[cat] = count + 1

                # Use Qwen AI for a personalised reason; fall back to rule-based
                try:
                    reason = self.ai.generate_recommendation_reason(
                        product_name=product.name,
                        product_category=product.category,
                        product_styles=product.styles or [],
                        product_price=product.price,
                        user_style=req.style,
                        user_budget=req.budget,
                        user_rooms=req.rooms,
                        score=score,
                    )
                except Exception:
                    reason = _build_reason(product, req.style, req.budget)

                rec = FurnitureRecommendation(
                    product=product,
                    score=score,
                    reason=reason,
                    item_id=product.item_id,
                    name=product.name,
                    category=product.category,
                    metadata={
                        "style": req.style,
                        "budget": req.budget,
                        "source": product.source,
                        "ai_reason": True,
                    },
                )
                results.append(rec)
            if len(results) >= 12:
                break

        logger.info("recommendations generated", extra={"count": len(results), "sources": sources})
        return results


def get_recommender_service() -> RecommenderService:
    return RecommenderService()
