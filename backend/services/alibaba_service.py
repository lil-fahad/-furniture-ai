"""
Alibaba / AliExpress product search service.

Uses the AliExpress DS API (affiliate/data feed) when credentials are present.
Falls back to a curated static catalog otherwise.

Environment variables (optional):
  ALIBABA_APP_KEY    – AliExpress affiliate app key
  ALIBABA_APP_SECRET – AliExpress affiliate app secret
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote_plus, urlencode

import httpx

from backend.models.pydantic_schemas import ExternalProduct

logger = logging.getLogger(__name__)

_ALIEXPRESS_API = "https://api-sg.aliexpress.com/sync"

_FALLBACK_CATALOG: List[dict] = [
    {
        "item_id": "ali-sofa-001",
        "name": "Modern Fabric Sofa 3-Seater",
        "category": "sofa",
        "price": 320.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S1234567890/Modern-Fabric-Sofa.jpg",
        "product_url": "https://www.aliexpress.com/item/1005001234567890.html",
        "source": "alibaba",
        "description": "Comfortable 3-seater sofa with high-density foam cushions and durable fabric.",
    },
    {
        "item_id": "ali-dining-table-001",
        "name": "Solid Wood Dining Table 6-Person",
        "category": "table",
        "price": 450.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S2345678901/Solid-Wood-Dining-Table.jpg",
        "product_url": "https://www.aliexpress.com/item/1005002345678901.html",
        "source": "alibaba",
        "description": "Solid oak dining table with natural finish, seats 6 comfortably.",
    },
    {
        "item_id": "ali-bed-frame-001",
        "name": "King Size Platform Bed Frame",
        "category": "bed",
        "price": 280.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S3456789012/King-Size-Bed-Frame.jpg",
        "product_url": "https://www.aliexpress.com/item/1005003456789012.html",
        "source": "alibaba",
        "description": "Minimalist platform bed frame with wooden slats, no box spring needed.",
    },
    {
        "item_id": "ali-wardrobe-001",
        "name": "Sliding Door Wardrobe 3-Door",
        "category": "wardrobe",
        "price": 380.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S4567890123/Sliding-Door-Wardrobe.jpg",
        "product_url": "https://www.aliexpress.com/item/1005004567890123.html",
        "source": "alibaba",
        "description": "Space-saving 3-door sliding wardrobe with mirror and internal shelves.",
    },
    {
        "item_id": "ali-office-chair-001",
        "name": "Ergonomic Mesh Office Chair",
        "category": "chair",
        "price": 120.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S5678901234/Ergonomic-Mesh-Chair.jpg",
        "product_url": "https://www.aliexpress.com/item/1005005678901234.html",
        "source": "alibaba",
        "description": "Breathable mesh back, adjustable lumbar support, 360° swivel.",
    },
    {
        "item_id": "ali-bookshelf-001",
        "name": "Industrial Style Bookshelf 5-Tier",
        "category": "storage",
        "price": 95.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S6789012345/Industrial-Bookshelf.jpg",
        "product_url": "https://www.aliexpress.com/item/1005006789012345.html",
        "source": "alibaba",
        "description": "Metal frame with wooden shelves, industrial loft style.",
    },
    {
        "item_id": "ali-coffee-table-001",
        "name": "Marble Top Coffee Table",
        "category": "table",
        "price": 175.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S7890123456/Marble-Coffee-Table.jpg",
        "product_url": "https://www.aliexpress.com/item/1005007890123456.html",
        "source": "alibaba",
        "description": "Luxury marble top with gold metal legs, modern living room centerpiece.",
    },
    {
        "item_id": "ali-tv-stand-001",
        "name": "Floating TV Stand Wall Mount",
        "category": "tv_unit",
        "price": 85.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S8901234567/Floating-TV-Stand.jpg",
        "product_url": "https://www.aliexpress.com/item/1005008901234567.html",
        "source": "alibaba",
        "description": "Wall-mounted TV stand with cable management and storage compartments.",
    },
    {
        "item_id": "ali-dresser-001",
        "name": "6-Drawer Chest of Drawers",
        "category": "storage",
        "price": 145.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S9012345678/Chest-of-Drawers.jpg",
        "product_url": "https://www.aliexpress.com/item/1005009012345678.html",
        "source": "alibaba",
        "description": "Solid wood chest with 6 smooth-gliding drawers and metal handles.",
    },
    {
        "item_id": "ali-armchair-001",
        "name": "Velvet Accent Armchair",
        "category": "chair",
        "price": 160.00,
        "currency": "USD",
        "image_url": "https://ae01.alicdn.com/kf/S0123456789/Velvet-Armchair.jpg",
        "product_url": "https://www.aliexpress.com/item/1005000123456789.html",
        "source": "alibaba",
        "description": "Luxurious velvet upholstery with solid wood legs, perfect accent chair.",
    },
]


class AlibabaService:
    """Search Alibaba / AliExpress products by keyword or category."""

    def __init__(self) -> None:
        self._app_key = os.getenv("ALIBABA_APP_KEY", "")
        self._app_secret = os.getenv("ALIBABA_APP_SECRET", "")
        self._cache_path = Path("datasets/alibaba_cache.json")
        self._catalog = self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        max_results: int = 10,
    ) -> List[ExternalProduct]:
        """Search Alibaba products. Tries live API first, falls back to catalog."""
        if self._app_key and self._app_secret:
            try:
                results = self._live_search(query, max_results)
                if results:
                    return results
            except Exception as exc:
                logger.warning("Alibaba live search failed: %s — using catalog fallback", exc)

        return self._catalog_search(query, category, max_results)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _sign(self, params: dict) -> str:
        """Generate HMAC-SHA256 signature for AliExpress API."""
        sorted_params = sorted(params.items())
        sign_string = self._app_secret + "".join(f"{k}{v}" for k, v in sorted_params) + self._app_secret
        return hmac.new(
            self._app_secret.encode("utf-8"),
            sign_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()

    def _live_search(self, query: str, max_results: int) -> List[ExternalProduct]:
        """Call the AliExpress DS API."""
        params = {
            "method": "aliexpress.affiliate.product.query",
            "app_key": self._app_key,
            "timestamp": str(int(time.time() * 1000)),
            "sign_method": "hmac-sha256",
            "keywords": query,
            "page_size": str(min(max_results, 50)),
            "page_no": "1",
            "fields": "product_id,product_title,product_main_image_url,target_sale_price,target_sale_price_currency,product_detail_url,second_level_category_name",
        }
        params["sign"] = self._sign(params)

        with httpx.Client(timeout=10) as client:
            resp = client.post(_ALIEXPRESS_API, data=params)
            resp.raise_for_status()
            data = resp.json()

        products: List[ExternalProduct] = []
        items = (
            data.get("aliexpress_affiliate_product_query_response", {})
            .get("resp_result", {})
            .get("result", {})
            .get("products", {})
            .get("product", [])
        )
        for p in items[:max_results]:
            products.append(
                ExternalProduct(
                    item_id=f"ali-{p.get('product_id', '')}",
                    name=p.get("product_title", ""),
                    category=p.get("second_level_category_name", "furniture").lower(),
                    price=float(p.get("target_sale_price", 0) or 0) or None,
                    currency=p.get("target_sale_price_currency", "USD"),
                    image_url=p.get("product_main_image_url"),
                    product_url=p.get("product_detail_url"),
                    source="alibaba",
                    description=None,
                )
            )
        return products

    def _catalog_search(
        self,
        query: str,
        category: Optional[str],
        max_results: int,
    ) -> List[ExternalProduct]:
        q = query.lower()
        results = []
        for item in self._catalog:
            if category and item.get("category", "").lower() != category.lower():
                continue
            if q and q not in item["name"].lower() and q not in item.get("description", "").lower() and q not in item.get("category", "").lower():
                continue
            results.append(ExternalProduct(**item))
        if not results:
            for item in self._catalog:
                if category and item.get("category", "").lower() != category.lower():
                    continue
                results.append(ExternalProduct(**item))
        return results[:max_results]

    def _load_cache(self) -> List[dict]:
        if self._cache_path.exists():
            try:
                return json.loads(self._cache_path.read_text())
            except Exception:
                pass
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(_FALLBACK_CATALOG, indent=2))
        return _FALLBACK_CATALOG


def get_alibaba_service() -> AlibabaService:
    return AlibabaService()
