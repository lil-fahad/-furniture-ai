"""
Furniture catalog endpoint — browse IKEA + Alibaba products.
"""
from typing import List, Optional
from fastapi import APIRouter, Query

from backend.models.pydantic_schemas import FurnitureProduct
from backend.services.ikea_service import get_ikea_service
from backend.services.alibaba_service import get_alibaba_service
from backend.logging.logger import logger

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/products", response_model=List[FurnitureProduct])
async def get_products(
    source: Optional[str] = Query(None, description="ikea | alibaba | all"),
    category: Optional[str] = Query(None),
    style: Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
    color: Optional[str] = Query(None),
) -> List[FurnitureProduct]:
    ikea = get_ikea_service()
    alibaba = get_alibaba_service()

    results: List[FurnitureProduct] = []

    if source in (None, "all", "ikea"):
        results.extend(ikea.search(category=category, style=style, max_price=max_price, color=color))
    if source in (None, "all", "alibaba"):
        results.extend(alibaba.search(category=category, style=style, max_price=max_price, color=color))

    # Sort by rating desc
    results.sort(key=lambda p: (p.rating or 0), reverse=True)
    logger.info("catalog query", extra={"count": len(results), "source": source})
    return results


@router.get("/categories", response_model=List[str])
async def get_categories() -> List[str]:
    return ["sofa", "chair", "table", "storage", "bed", "desk", "lighting", "rug"]


@router.get("/sources", response_model=List[str])
async def get_sources() -> List[str]:
    return ["ikea", "alibaba"]
