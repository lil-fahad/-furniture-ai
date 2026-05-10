"""
Furniture Catalog API
Browse the full furniture catalog, get item details, filter by category/source.
"""
from fastapi import APIRouter, HTTPException, Query, Path
from typing import Optional, List

from backend.services.ikea_service import get_ikea_service, IKEA_CATALOG
from backend.services.alibaba_service import get_alibaba_service, ALIBABA_CATALOG
from backend.models.pydantic_schemas import FurnitureRecommendation, FurnitureSource
from backend.logging.logger import logger

router = APIRouter(prefix="/catalog", tags=["catalog"])

ikea_service = get_ikea_service()
alibaba_service = get_alibaba_service()

# ─── Combined catalog lookup ──────────────────────────────────────────────────
_ALL_ITEMS = {item["item_id"]: ("ikea", item) for item in IKEA_CATALOG}
_ALL_ITEMS.update({item["item_id"]: ("alibaba", item) for item in ALIBABA_CATALOG})


def _build_recommendation(source_name: str, item: dict) -> FurnitureRecommendation:
    """Build a FurnitureRecommendation from a raw catalog item."""
    source = FurnitureSource(
        source=source_name,
        url=item.get("url"),
        price=item["price_usd"],
        currency="USD",
        availability="in_stock" if source_name == "ikea" else "available",
        rating=item.get("rating"),
        reviews_count=item.get("reviews"),
        image_url=item.get("image_url"),
        sku=item.get("sku") or item.get("item_id"),
        brand="IKEA" if source_name == "ikea" else item.get("supplier"),
        dimensions=item.get("dimensions"),
        colors=item.get("colors"),
        materials=item.get("materials"),
        delivery_days=item.get("delivery_days"),
    )
    meta = {"price_usd": item["price_usd"]}
    if source_name == "alibaba":
        meta["supplier"] = item.get("supplier")
        meta["moq"] = item.get("moq", 1)

    return FurnitureRecommendation(
        item_id=item["item_id"],
        name=item["name"],
        category=item["category"],
        score=round((item.get("rating", 4.0) - 3.0) / 2.0 * 0.5 + 0.5, 3),
        description=item.get("description"),
        style=item.get("style"),
        sources=[source],
        tags=item.get("tags"),
        room_fit=item.get("room_fit"),
        metadata=meta,
    )


class CatalogResponse:
    pass


from pydantic import BaseModel


class CatalogListResponse(BaseModel):
    items: List[FurnitureRecommendation]
    total: int
    source: Optional[str] = None
    category: Optional[str] = None
    page: int = 1
    page_size: int = 20


@router.get("/items", response_model=CatalogListResponse)
async def list_catalog(
    source: Optional[str] = Query(None, description="ikea | alibaba | (omit for both)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    room_type: Optional[str] = Query(None, description="Filter by room type"),
    style: Optional[str] = Query(None, description="Filter by style"),
    min_price: Optional[float] = Query(None, description="Minimum price USD"),
    max_price: Optional[float] = Query(None, description="Maximum price USD"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> CatalogListResponse:
    """
    Browse the full furniture catalog with optional filters.

    Returns paginated results from IKEA, Alibaba, or both.
    """
    try:
        all_items: List[FurnitureRecommendation] = []

        sources_to_search = []
        if source in (None, "ikea"):
            sources_to_search.append(("ikea", IKEA_CATALOG))
        if source in (None, "alibaba"):
            sources_to_search.append(("alibaba", ALIBABA_CATALOG))

        for src_name, catalog in sources_to_search:
            for item in catalog:
                # Apply filters
                if category and item.get("category") != category:
                    continue
                if room_type and room_type not in item.get("room_fit", []):
                    continue
                if style and item.get("style") != style:
                    continue
                if min_price and item["price_usd"] < min_price:
                    continue
                if max_price and item["price_usd"] > max_price:
                    continue

                all_items.append(_build_recommendation(src_name, item))

        # Sort by score (rating-based) descending
        all_items.sort(key=lambda x: x.score, reverse=True)

        total = len(all_items)
        start = (page - 1) * page_size
        end = start + page_size
        page_items = all_items[start:end]

        logger.info("catalog listed", extra={"total": total, "page": page})

        return CatalogListResponse(
            items=page_items,
            total=total,
            source=source,
            category=category,
            page=page,
            page_size=page_size,
        )

    except Exception as exc:
        logger.exception("catalog list failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/items/{item_id}", response_model=FurnitureRecommendation)
async def get_item(
    item_id: str = Path(..., description="Furniture item ID (e.g. ikea-kallax-001)"),
) -> FurnitureRecommendation:
    """
    Get full details for a specific furniture item by ID.

    Example IDs: `ikea-kallax-001`, `ali-sofa-l001`, `ikea-malm-001`
    """
    entry = _ALL_ITEMS.get(item_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Item '{item_id}' not found")

    source_name, item = entry
    result = _build_recommendation(source_name, item)
    logger.info("item fetched", extra={"item_id": item_id})
    return result


@router.get("/categories", response_model=dict)
async def list_categories() -> dict:
    """
    List all available furniture categories and their item counts.
    """
    categories: dict = {}
    for src_name, catalog in [("ikea", IKEA_CATALOG), ("alibaba", ALIBABA_CATALOG)]:
        for item in catalog:
            cat = item.get("category", "other")
            if cat not in categories:
                categories[cat] = {"total": 0, "ikea": 0, "alibaba": 0}
            categories[cat]["total"] += 1
            categories[cat][src_name] += 1

    return {"categories": categories, "total_categories": len(categories)}


@router.get("/styles", response_model=dict)
async def list_styles() -> dict:
    """
    List all available furniture styles and their item counts.
    """
    styles: dict = {}
    for src_name, catalog in [("ikea", IKEA_CATALOG), ("alibaba", ALIBABA_CATALOG)]:
        for item in catalog:
            style = item.get("style", "other")
            if style not in styles:
                styles[style] = {"total": 0, "ikea": 0, "alibaba": 0}
            styles[style]["total"] += 1
            styles[style][src_name] += 1

    return {"styles": styles, "total_styles": len(styles)}
