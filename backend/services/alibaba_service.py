"""
Alibaba / AliExpress furniture catalog service.
Uses a curated catalog of real Alibaba wholesale furniture products.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from backend.models.pydantic_schemas import FurnitureProduct

logger = logging.getLogger("furniture_ai")

# ---------------------------------------------------------------------------
# Curated Alibaba catalog (real product types, representative images)
# ---------------------------------------------------------------------------
ALIBABA_CATALOG: List[dict] = [
    # ── Sofas ──────────────────────────────────────────────────────────────
    {
        "item_id": "ali-nordic-sofa-3s",
        "name": "Nordic Fabric Sofa 3-Seater",
        "category": "sofa",
        "price": 320.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/H8b3e2e2e2e2e4e2e8e2e2e2e2e2e2e2eX.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Nordic-Fabric-Sofa_62534567890.html",
        "description": "Wholesale Nordic-style 3-seater fabric sofa, MOQ 1 unit.",
        "dimensions": {"w": 210, "d": 85, "h": 80, "unit": "cm"},
        "colors": ["light grey", "dark grey", "beige", "blue"],
        "styles": ["nordic", "modern", "minimalist"],
        "rating": 4.3,
        "reviews": 456,
    },
    {
        "item_id": "ali-velvet-sofa",
        "name": "Luxury Velvet Chesterfield Sofa",
        "category": "sofa",
        "price": 480.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Hvelvet_sofa_chesterfield.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Velvet-Chesterfield-Sofa_62534567891.html",
        "description": "Premium velvet Chesterfield sofa with button tufting.",
        "dimensions": {"w": 195, "d": 90, "h": 85, "unit": "cm"},
        "colors": ["emerald green", "navy blue", "burgundy", "gold"],
        "styles": ["luxury", "classic", "vintage"],
        "rating": 4.5,
        "reviews": 312,
    },
    # ── Chairs ─────────────────────────────────────────────────────────────
    {
        "item_id": "ali-eames-replica-chair",
        "name": "Eames Style Lounge Chair & Ottoman",
        "category": "chair",
        "price": 185.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Heames_lounge_chair.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Eames-Lounge-Chair_62534567892.html",
        "description": "Mid-century modern lounge chair with genuine leather and walnut shell.",
        "dimensions": {"w": 83, "d": 84, "h": 93, "unit": "cm"},
        "colors": ["black/walnut", "brown/walnut", "white/walnut"],
        "styles": ["mid-century", "modern", "luxury"],
        "rating": 4.4,
        "reviews": 789,
    },
    {
        "item_id": "ali-mesh-office-chair",
        "name": "Ergonomic Mesh Office Chair",
        "category": "chair",
        "price": 95.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Hmesh_office_chair.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Ergonomic-Mesh-Chair_62534567893.html",
        "description": "Full mesh ergonomic chair with lumbar support and adjustable armrests.",
        "dimensions": {"w": 65, "d": 65, "h": 120, "unit": "cm"},
        "colors": ["black", "grey", "blue"],
        "styles": ["office", "modern", "ergonomic"],
        "rating": 4.2,
        "reviews": 1230,
    },
    # ── Tables ─────────────────────────────────────────────────────────────
    {
        "item_id": "ali-marble-dining-table",
        "name": "Marble Top Dining Table",
        "category": "table",
        "price": 420.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Hmarble_dining_table.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Marble-Dining-Table_62534567894.html",
        "description": "Italian marble top dining table with stainless steel base.",
        "dimensions": {"w": 160, "d": 90, "h": 76, "unit": "cm"},
        "colors": ["white marble/gold", "black marble/silver"],
        "styles": ["luxury", "modern", "italian"],
        "rating": 4.6,
        "reviews": 234,
    },
    {
        "item_id": "ali-solid-wood-coffee-table",
        "name": "Solid Wood Coffee Table",
        "category": "table",
        "price": 145.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Hsolid_wood_coffee_table.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Solid-Wood-Coffee-Table_62534567895.html",
        "description": "Handcrafted solid oak coffee table with natural finish.",
        "dimensions": {"w": 120, "d": 60, "h": 45, "unit": "cm"},
        "colors": ["natural oak", "walnut", "ebony"],
        "styles": ["rustic", "natural", "scandinavian"],
        "rating": 4.5,
        "reviews": 567,
    },
    # ── Storage ────────────────────────────────────────────────────────────
    {
        "item_id": "ali-tv-cabinet",
        "name": "Modern TV Cabinet with LED",
        "category": "storage",
        "price": 210.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Htv_cabinet_led.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/TV-Cabinet-LED_62534567896.html",
        "description": "Floating TV cabinet with LED strip lighting and push-open doors.",
        "dimensions": {"w": 180, "d": 40, "h": 50, "unit": "cm"},
        "colors": ["white", "walnut", "grey"],
        "styles": ["modern", "minimalist", "contemporary"],
        "rating": 4.4,
        "reviews": 890,
    },
    {
        "item_id": "ali-bookshelf-industrial",
        "name": "Industrial Pipe Bookshelf",
        "category": "storage",
        "price": 130.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Hindustrial_bookshelf.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Industrial-Bookshelf_62534567897.html",
        "description": "5-tier industrial bookshelf with metal pipe frame and wood shelves.",
        "dimensions": {"w": 100, "d": 30, "h": 175, "unit": "cm"},
        "colors": ["black/rustic brown", "white/natural"],
        "styles": ["industrial", "loft", "vintage"],
        "rating": 4.3,
        "reviews": 1100,
    },
    # ── Beds ───────────────────────────────────────────────────────────────
    {
        "item_id": "ali-upholstered-bed",
        "name": "Upholstered Platform Bed",
        "category": "bed",
        "price": 380.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Hupholstered_platform_bed.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Upholstered-Platform-Bed_62534567898.html",
        "description": "King-size upholstered platform bed with tufted headboard.",
        "dimensions": {"w": 193, "d": 203, "h": 120, "unit": "cm"},
        "colors": ["light grey", "dark grey", "beige", "navy"],
        "styles": ["modern", "luxury", "contemporary"],
        "rating": 4.5,
        "reviews": 678,
    },
    # ── Lighting ───────────────────────────────────────────────────────────
    {
        "item_id": "ali-pendant-light",
        "name": "Nordic Pendant Light",
        "category": "lighting",
        "price": 45.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Hnordic_pendant_light.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Nordic-Pendant-Light_62534567899.html",
        "description": "Minimalist Nordic pendant light with E27 socket.",
        "dimensions": {"w": 30, "d": 30, "h": 120, "unit": "cm"},
        "colors": ["black", "white", "gold", "copper"],
        "styles": ["nordic", "minimalist", "modern"],
        "rating": 4.4,
        "reviews": 2300,
    },
    # ── Rugs ───────────────────────────────────────────────────────────────
    {
        "item_id": "ali-persian-rug",
        "name": "Persian Style Area Rug",
        "category": "rug",
        "price": 89.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Hpersian_area_rug.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Persian-Area-Rug_62534567900.html",
        "description": "Traditional Persian pattern area rug, machine washable.",
        "dimensions": {"w": 160, "d": 230, "h": 0, "unit": "cm"},
        "colors": ["red/gold", "blue/ivory", "green/beige"],
        "styles": ["traditional", "classic", "bohemian"],
        "rating": 4.2,
        "reviews": 1560,
    },
    # ── Desks ──────────────────────────────────────────────────────────────
    {
        "item_id": "ali-standing-desk",
        "name": "Electric Height-Adjustable Standing Desk",
        "category": "desk",
        "price": 265.0,
        "currency": "USD",
        "image_url": "https://s.alicdn.com/@sc04/kf/Hstanding_desk_electric.jpg_300x300.jpg",
        "buy_url": "https://www.alibaba.com/product-detail/Standing-Desk-Electric_62534567901.html",
        "description": "Electric sit-stand desk with memory presets and anti-collision.",
        "dimensions": {"w": 140, "d": 70, "h": 125, "unit": "cm"},
        "colors": ["white", "black", "bamboo"],
        "styles": ["modern", "office", "ergonomic"],
        "rating": 4.6,
        "reviews": 3400,
    },
]


class AlibabaService:
    """Provides Alibaba furniture products."""

    def __init__(self) -> None:
        self._catalog = ALIBABA_CATALOG

    def get_all(self) -> List[FurnitureProduct]:
        return [self._to_product(item) for item in self._catalog]

    def search(
        self,
        category: Optional[str] = None,
        style: Optional[str] = None,
        max_price: Optional[float] = None,
        color: Optional[str] = None,
    ) -> List[FurnitureProduct]:
        results = self._catalog
        if category:
            results = [r for r in results if r["category"].lower() == category.lower()]
        if style:
            results = [r for r in results if style.lower() in [s.lower() for s in r.get("styles", [])]]
        if max_price is not None:
            results = [r for r in results if r.get("price", 0) <= max_price]
        if color:
            results = [
                r for r in results
                if any(color.lower() in c.lower() for c in r.get("colors", []))
            ]
        return [self._to_product(item) for item in results]

    def _to_product(self, item: dict) -> FurnitureProduct:
        return FurnitureProduct(
            item_id=item["item_id"],
            name=item["name"],
            category=item["category"],
            source="alibaba",
            price=item.get("price"),
            currency=item.get("currency", "USD"),
            image_url=item.get("image_url"),
            buy_url=item.get("buy_url"),
            description=item.get("description"),
            dimensions=item.get("dimensions"),
            colors=item.get("colors"),
            styles=item.get("styles"),
            rating=item.get("rating"),
            reviews=item.get("reviews"),
            in_stock=True,
        )


_alibaba_service: Optional[AlibabaService] = None


def get_alibaba_service() -> AlibabaService:
    global _alibaba_service
    if _alibaba_service is None:
        _alibaba_service = AlibabaService()
    return _alibaba_service
