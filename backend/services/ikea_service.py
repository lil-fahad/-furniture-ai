"""
IKEA product search service.

Uses the unofficial IKEA API (ikea.com/api) to search for furniture products.
Falls back to a curated static catalog when the network is unavailable.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote_plus

import httpx

from backend.models.pydantic_schemas import ExternalProduct

logger = logging.getLogger(__name__)

# Country / language codes used in the IKEA API
_IKEA_BASE = "https://sik.search.blue.cdtapps.com"
_COUNTRY = "us"
_LANGUAGE = "en"

# Fallback static catalog (used when network is unavailable)
_FALLBACK_CATALOG: List[dict] = [
    {
        "item_id": "ikea-KALLAX",
        "name": "KALLAX Shelf unit",
        "category": "storage",
        "price": 69.99,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/kallax-shelf-unit-white__0644757_pe702938_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/kallax-shelf-unit-white-00275848/",
        "source": "ikea",
        "description": "Smooth surfaces and clean lines make this shelf unit easy to combine with other furniture.",
    },
    {
        "item_id": "ikea-BILLY",
        "name": "BILLY Bookcase",
        "category": "storage",
        "price": 59.99,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/billy-bookcase-white__0625599_pe692385_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/billy-bookcase-white-00263850/",
        "source": "ikea",
        "description": "Adjustable shelves let you customise your storage as needed.",
    },
    {
        "item_id": "ikea-POANG",
        "name": "POANG Armchair",
        "category": "chair",
        "price": 129.00,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/poaeng-armchair-birch-veneer-knisa-light-beige__0951374_pe800178_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/poaeng-armchair-birch-veneer-knisa-light-beige-s09408182/",
        "source": "ikea",
        "description": "Layer-glued bent birch frame gives this armchair a comfortable resilience.",
    },
    {
        "item_id": "ikea-MALM",
        "name": "MALM Bed frame",
        "category": "bed",
        "price": 249.00,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/malm-bed-frame-high-white__0637598_pe698416_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/malm-bed-frame-high-white-00176552/",
        "source": "ikea",
        "description": "Clean-lined bed frame with a timeless look that fits any bedroom style.",
    },
    {
        "item_id": "ikea-LACK",
        "name": "LACK Coffee table",
        "category": "table",
        "price": 29.99,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/lack-coffee-table-white__0178601_pe334073_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/lack-coffee-table-white-20011408/",
        "source": "ikea",
        "description": "Simple and functional coffee table with a clean design.",
    },
    {
        "item_id": "ikea-EKTORP",
        "name": "EKTORP Sofa",
        "category": "sofa",
        "price": 549.00,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/ektorp-sofa-vittaryd-white__0988178_pe816891_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/ektorp-sofa-vittaryd-white-s09388727/",
        "source": "ikea",
        "description": "Traditional sofa with a relaxed, casual look and generous seating.",
    },
    {
        "item_id": "ikea-HEMNES",
        "name": "HEMNES Dresser",
        "category": "storage",
        "price": 199.00,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/hemnes-chest-of-6-drawers-white-stain__0637607_pe698420_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/hemnes-chest-of-6-drawers-white-stain-30392283/",
        "source": "ikea",
        "description": "Solid wood dresser with six spacious drawers.",
    },
    {
        "item_id": "ikea-STEFAN",
        "name": "STEFAN Chair",
        "category": "chair",
        "price": 39.99,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/stefan-chair-brown-black__0713514_pe729498_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/stefan-chair-brown-black-20213563/",
        "source": "ikea",
        "description": "Solid wood chair with a classic design that suits any room.",
    },
    {
        "item_id": "ikea-BESTA",
        "name": "BESTA TV unit",
        "category": "tv_unit",
        "price": 149.00,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/besta-tv-unit-white__0488231_pe622371_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/besta-tv-unit-white-60245922/",
        "source": "ikea",
        "description": "Versatile TV unit with adjustable shelves and cable management.",
    },
    {
        "item_id": "ikea-NORDLI",
        "name": "NORDLI Wardrobe",
        "category": "wardrobe",
        "price": 349.00,
        "currency": "USD",
        "image_url": "https://www.ikea.com/us/en/images/products/nordli-wardrobe-with-sliding-doors-white__0737416_pe741116_s5.jpg",
        "product_url": "https://www.ikea.com/us/en/p/nordli-wardrobe-with-sliding-doors-white-s79417221/",
        "source": "ikea",
        "description": "Sliding doors save space and give a clean, seamless look.",
    },
]


class IKEAService:
    """Search IKEA products by keyword or category."""

    def __init__(self) -> None:
        self._cache_path = Path("datasets/ikea_cache.json")
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
        """Search IKEA products. Tries live API first, falls back to catalog."""
        try:
            results = self._live_search(query, max_results)
            if results:
                return results
        except Exception as exc:
            logger.warning("IKEA live search failed: %s — using catalog fallback", exc)

        return self._catalog_search(query, category, max_results)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _live_search(self, query: str, max_results: int) -> List[ExternalProduct]:
        """Call the IKEA search API."""
        url = (
            f"{_IKEA_BASE}/{_COUNTRY}/{_LANGUAGE}/search"
            f"?q={quote_plus(query)}&size={max_results}&types=PRODUCT"
        )
        with httpx.Client(timeout=8) as client:
            resp = client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()

        products: List[ExternalProduct] = []
        items = (
            data.get("searchResultPage", {})
            .get("products", {})
            .get("main", {})
            .get("items", [])
        )
        for item in items[:max_results]:
            p = item.get("product", item)
            name = p.get("name", "") + " " + p.get("typeName", "")
            price_info = p.get("priceNumeral") or p.get("price", {})
            price = float(price_info) if isinstance(price_info, (int, float)) else None
            products.append(
                ExternalProduct(
                    item_id=f"ikea-{p.get('id', '')}",
                    name=name.strip(),
                    category=p.get("typeName", "furniture").lower(),
                    price=price,
                    currency="USD",
                    image_url=p.get("mainImageUrl") or p.get("imageUrl"),
                    product_url=f"https://www.ikea.com/us/en/p/{p.get('id', '')}/",
                    source="ikea",
                    description=p.get("contextualImageAlt") or p.get("description"),
                )
            )
        return products

    def _catalog_search(
        self,
        query: str,
        category: Optional[str],
        max_results: int,
    ) -> List[ExternalProduct]:
        """Filter the static catalog by query / category."""
        q = query.lower()
        results = []
        for item in self._catalog:
            if category and item.get("category", "").lower() != category.lower():
                continue
            if q and q not in item["name"].lower() and q not in item.get("description", "").lower() and q not in item.get("category", "").lower():
                continue
            results.append(ExternalProduct(**item))
        # If nothing matched the query, return all (or category-filtered) items
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


def get_ikea_service() -> IKEAService:
    return IKEAService()
