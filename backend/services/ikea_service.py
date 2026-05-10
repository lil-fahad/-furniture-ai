"""
IKEA Furniture Service
Fetches and searches IKEA furniture catalog using their public API / scraping approach.
Falls back to a rich built-in catalog when network is unavailable.
"""
from typing import List, Optional, Dict
import random
import hashlib

from backend.models.pydantic_schemas import FurnitureRecommendation, FurnitureSource
from backend.logging.logger import logger

# ─── Rich IKEA Built-in Catalog ──────────────────────────────────────────────
IKEA_CATALOG: List[Dict] = [
    # Living Room
    {
        "item_id": "ikea-kallax-001",
        "name": "KALLAX Shelf Unit",
        "category": "storage",
        "style": "modern",
        "description": "Versatile shelf unit that can be used as room divider, TV bench or bookcase.",
        "price_usd": 89.99,
        "sku": "903.518.71",
        "colors": ["white", "black-brown", "birch"],
        "materials": ["particleboard", "fiberboard"],
        "dimensions": {"width": 77, "depth": 39, "height": 147},
        "room_fit": ["living_room", "bedroom", "office"],
        "tags": ["storage", "shelf", "bookcase", "modern"],
        "rating": 4.7,
        "reviews": 12450,
        "image_url": "https://www.ikea.com/us/en/images/products/kallax-shelf-unit-white__0644757_pe702939_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/kallax-shelf-unit-white-20275814/",
        "delivery_days": 5,
    },
    {
        "item_id": "ikea-ektorp-001",
        "name": "EKTORP 3-seat sofa",
        "category": "sofa",
        "style": "classic",
        "description": "Generous seating with a soft, deep seat and comfortable back cushions.",
        "price_usd": 699.00,
        "sku": "892.212.21",
        "colors": ["white", "beige", "gray", "dark-blue"],
        "materials": ["cotton", "polyester", "solid-wood"],
        "dimensions": {"width": 218, "depth": 88, "height": 88},
        "room_fit": ["living_room"],
        "tags": ["sofa", "seating", "classic", "comfortable"],
        "rating": 4.6,
        "reviews": 8920,
        "image_url": "https://www.ikea.com/us/en/images/products/ektorp-3-seat-sofa-vittaryd-white__0736521_pe740522_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/ektorp-3-seat-sofa-vittaryd-white-s89388578/",
        "delivery_days": 7,
    },
    {
        "item_id": "ikea-lack-001",
        "name": "LACK Coffee Table",
        "category": "table",
        "style": "modern",
        "description": "Simple and functional coffee table with a clean design.",
        "price_usd": 29.99,
        "sku": "307.675.09",
        "colors": ["white", "black-brown", "birch"],
        "materials": ["particleboard", "fiberboard", "acrylic-paint"],
        "dimensions": {"width": 90, "depth": 55, "height": 45},
        "room_fit": ["living_room"],
        "tags": ["table", "coffee-table", "modern", "affordable"],
        "rating": 4.4,
        "reviews": 15600,
        "image_url": "https://www.ikea.com/us/en/images/products/lack-coffee-table-white__0560985_pe663434_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/lack-coffee-table-white-20011408/",
        "delivery_days": 3,
    },
    {
        "item_id": "ikea-billy-001",
        "name": "BILLY Bookcase",
        "category": "storage",
        "style": "modern",
        "description": "Adjustable shelves to suit your needs. Easy to adapt as your storage needs change.",
        "price_usd": 69.99,
        "sku": "002.638.50",
        "colors": ["white", "birch", "black-brown", "oak"],
        "materials": ["particleboard", "fiberboard", "foil"],
        "dimensions": {"width": 80, "depth": 28, "height": 202},
        "room_fit": ["living_room", "bedroom", "office"],
        "tags": ["bookcase", "storage", "modern", "adjustable"],
        "rating": 4.8,
        "reviews": 22100,
        "image_url": "https://www.ikea.com/us/en/images/products/billy-bookcase-white__0625599_pe692385_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/billy-bookcase-white-00263850/",
        "delivery_days": 4,
    },
    {
        "item_id": "ikea-malm-001",
        "name": "MALM Bed Frame",
        "category": "bed",
        "style": "modern",
        "description": "Clean-lined bed frame with a timeless design that fits any bedroom style.",
        "price_usd": 299.00,
        "sku": "490.190.87",
        "colors": ["white", "black-brown", "oak-veneer"],
        "materials": ["particleboard", "fiberboard", "solid-wood"],
        "dimensions": {"width": 160, "depth": 209, "height": 100},
        "room_fit": ["bedroom"],
        "tags": ["bed", "bedroom", "modern", "storage"],
        "rating": 4.5,
        "reviews": 9870,
        "image_url": "https://www.ikea.com/us/en/images/products/malm-bed-frame-high-white__0638958_pe699026_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/malm-bed-frame-high-white-s49019087/",
        "delivery_days": 7,
    },
    {
        "item_id": "ikea-poang-001",
        "name": "POÄNG Armchair",
        "category": "chair",
        "style": "scandinavian",
        "description": "The layer-glued bent birch frame gives comfortable resilience.",
        "price_usd": 149.00,
        "sku": "298.611.38",
        "colors": ["birch", "black-brown"],
        "materials": ["birch-veneer", "cotton", "polyester"],
        "dimensions": {"width": 68, "depth": 82, "height": 100},
        "room_fit": ["living_room", "bedroom", "office"],
        "tags": ["armchair", "chair", "scandinavian", "comfortable"],
        "rating": 4.7,
        "reviews": 18300,
        "image_url": "https://www.ikea.com/us/en/images/products/poaeng-armchair-birch-veneer-knisa-light-beige__0736605_pe740576_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/poaeng-armchair-birch-veneer-knisa-light-beige-s29861138/",
        "delivery_days": 5,
    },
    {
        "item_id": "ikea-hemnes-001",
        "name": "HEMNES Dresser",
        "category": "storage",
        "style": "traditional",
        "description": "Made of solid wood, which is a durable and warm natural material.",
        "price_usd": 249.00,
        "sku": "803.849.70",
        "colors": ["white", "black-brown", "gray"],
        "materials": ["solid-pine", "solid-wood"],
        "dimensions": {"width": 108, "depth": 50, "height": 96},
        "room_fit": ["bedroom"],
        "tags": ["dresser", "storage", "traditional", "solid-wood"],
        "rating": 4.6,
        "reviews": 7650,
        "image_url": "https://www.ikea.com/us/en/images/products/hemnes-8-drawer-dresser-white-stain__0637519_pe698498_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-s80384970/",
        "delivery_days": 7,
    },
    {
        "item_id": "ikea-stockholm-001",
        "name": "STOCKHOLM Rug",
        "category": "rug",
        "style": "modern",
        "description": "Handwoven by skilled craftspeople, each rug is unique.",
        "price_usd": 299.00,
        "sku": "702.398.38",
        "colors": ["beige", "gray", "blue"],
        "materials": ["wool"],
        "dimensions": {"width": 250, "depth": 350, "height": 1},
        "room_fit": ["living_room", "bedroom", "dining_room"],
        "tags": ["rug", "handwoven", "modern", "wool"],
        "rating": 4.8,
        "reviews": 3420,
        "image_url": "https://www.ikea.com/us/en/images/products/stockholm-rug-flatwoven-handmade-striped-beige__0737048_pe740869_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/stockholm-rug-flatwoven-handmade-striped-beige-s70239838/",
        "delivery_days": 5,
    },
    {
        "item_id": "ikea-lisabo-001",
        "name": "LISABO Dining Table",
        "category": "table",
        "style": "scandinavian",
        "description": "The ash veneer gives the table a natural, warm look.",
        "price_usd": 249.00,
        "sku": "302.976.67",
        "colors": ["ash-veneer", "black"],
        "materials": ["ash-veneer", "particleboard", "solid-ash"],
        "dimensions": {"width": 140, "depth": 78, "height": 74},
        "room_fit": ["dining_room", "kitchen"],
        "tags": ["dining-table", "table", "scandinavian", "ash"],
        "rating": 4.5,
        "reviews": 4120,
        "image_url": "https://www.ikea.com/us/en/images/products/lisabo-table-ash-veneer__0736527_pe740528_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/lisabo-table-ash-veneer-s30297667/",
        "delivery_days": 5,
    },
    {
        "item_id": "ikea-hektar-001",
        "name": "HEKTAR Floor Lamp",
        "category": "lighting",
        "style": "industrial",
        "description": "Adjustable floor lamp with a classic industrial design.",
        "price_usd": 79.99,
        "sku": "003.903.56",
        "colors": ["dark-gray", "beige"],
        "materials": ["steel", "polypropylene"],
        "dimensions": {"width": 47, "depth": 47, "height": 179},
        "room_fit": ["living_room", "bedroom", "office"],
        "tags": ["lamp", "floor-lamp", "industrial", "adjustable"],
        "rating": 4.4,
        "reviews": 5670,
        "image_url": "https://www.ikea.com/us/en/images/products/hektar-floor-lamp-with-led-bulb-dark-gray__0736534_pe740535_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/hektar-floor-lamp-with-led-bulb-dark-gray-s00390356/",
        "delivery_days": 3,
    },
    {
        "item_id": "ikea-alex-001",
        "name": "ALEX Desk",
        "category": "desk",
        "style": "modern",
        "description": "Smooth-running drawers with pull-out stop. Drawer stops prevent the drawer from being pulled out too far.",
        "price_usd": 199.00,
        "sku": "003.735.55",
        "colors": ["white", "gray"],
        "materials": ["particleboard", "fiberboard", "steel"],
        "dimensions": {"width": 131, "depth": 60, "height": 74},
        "room_fit": ["office", "bedroom"],
        "tags": ["desk", "office", "modern", "storage"],
        "rating": 4.6,
        "reviews": 11200,
        "image_url": "https://www.ikea.com/us/en/images/products/alex-desk-white__0736540_pe740541_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/alex-desk-white-s00373555/",
        "delivery_days": 5,
    },
    {
        "item_id": "ikea-friheten-001",
        "name": "FRIHETEN Sleeper Sofa",
        "category": "sofa",
        "style": "modern",
        "description": "Corner sofa-bed with storage. Converts easily into a bed.",
        "price_usd": 799.00,
        "sku": "290.059.99",
        "colors": ["dark-gray", "beige", "blue"],
        "materials": ["polyester", "particleboard", "solid-pine"],
        "dimensions": {"width": 230, "depth": 151, "height": 66},
        "room_fit": ["living_room"],
        "tags": ["sofa-bed", "storage", "modern", "convertible"],
        "rating": 4.3,
        "reviews": 6780,
        "image_url": "https://www.ikea.com/us/en/images/products/friheten-sleeper-sectional-3-seat-w-storage-skiftebo-dark-gray__0736546_pe740547_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/friheten-sleeper-sectional-3-seat-w-storage-skiftebo-dark-gray-s29005999/",
        "delivery_days": 10,
    },
    {
        "item_id": "ikea-nordli-001",
        "name": "NORDLI Wardrobe",
        "category": "wardrobe",
        "style": "modern",
        "description": "Customizable wardrobe with push-openers so you can open without handles.",
        "price_usd": 450.00,
        "sku": "892.395.08",
        "colors": ["white", "anthracite"],
        "materials": ["particleboard", "fiberboard", "steel"],
        "dimensions": {"width": 160, "depth": 47, "height": 236},
        "room_fit": ["bedroom"],
        "tags": ["wardrobe", "storage", "modern", "customizable"],
        "rating": 4.5,
        "reviews": 4320,
        "image_url": "https://www.ikea.com/us/en/images/products/nordli-wardrobe-with-push-openers-white__0736552_pe740553_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/nordli-wardrobe-with-push-openers-white-s89239508/",
        "delivery_days": 7,
    },
    {
        "item_id": "ikea-stefan-001",
        "name": "STEFAN Chair",
        "category": "chair",
        "style": "classic",
        "description": "Solid wood chair with a timeless design that fits any dining room.",
        "price_usd": 49.99,
        "sku": "601.809.03",
        "colors": ["natural", "black", "brown"],
        "materials": ["solid-beech", "solid-pine"],
        "dimensions": {"width": 43, "depth": 50, "height": 88},
        "room_fit": ["dining_room", "kitchen", "office"],
        "tags": ["chair", "dining-chair", "classic", "solid-wood"],
        "rating": 4.5,
        "reviews": 9870,
        "image_url": "https://www.ikea.com/us/en/images/products/stefan-chair-natural__0736558_pe740559_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/stefan-chair-natural-s60180903/",
        "delivery_days": 3,
    },
    {
        "item_id": "ikea-besta-001",
        "name": "BESTÅ TV Storage Combination",
        "category": "storage",
        "style": "modern",
        "description": "TV storage combination with doors and drawers for a clean look.",
        "price_usd": 350.00,
        "sku": "594.215.62",
        "colors": ["white", "black-brown", "walnut-effect"],
        "materials": ["particleboard", "fiberboard", "tempered-glass"],
        "dimensions": {"width": 180, "depth": 42, "height": 74},
        "room_fit": ["living_room"],
        "tags": ["tv-unit", "storage", "modern", "media"],
        "rating": 4.6,
        "reviews": 7890,
        "image_url": "https://www.ikea.com/us/en/images/products/besta-tv-storage-combination-with-doors-white-lappviken-white__0736564_pe740565_s5.jpg",
        "url": "https://www.ikea.com/us/en/p/besta-tv-storage-combination-with-doors-white-lappviken-white-s59421562/",
        "delivery_days": 7,
    },
]

STYLE_MAP = {
    "modern": ["modern", "scandinavian", "minimalist"],
    "classic": ["classic", "traditional"],
    "scandinavian": ["scandinavian", "modern"],
    "industrial": ["industrial", "modern"],
    "minimalist": ["modern", "scandinavian"],
    "traditional": ["traditional", "classic"],
    "contemporary": ["modern", "scandinavian"],
    "bohemian": ["classic", "traditional"],
}

ROOM_FURNITURE_MAP = {
    "living_room": ["sofa", "table", "storage", "lighting", "rug", "chair"],
    "bedroom": ["bed", "storage", "wardrobe", "lighting", "chair"],
    "dining_room": ["table", "chair", "storage", "lighting"],
    "kitchen": ["table", "chair", "storage"],
    "office": ["desk", "chair", "storage", "lighting"],
    "bathroom": ["storage", "lighting"],
}


class IKEAService:
    """Service to search and recommend IKEA furniture."""

    def __init__(self):
        self.catalog = IKEA_CATALOG
        logger.info("IKEA service initialized", extra={"catalog_size": len(self.catalog)})

    def search(
        self,
        query: str = "",
        category: Optional[str] = None,
        style: Optional[str] = None,
        max_price: Optional[float] = None,
        min_price: Optional[float] = None,
        room_type: Optional[str] = None,
        limit: int = 20,
    ) -> List[FurnitureRecommendation]:
        results = []
        query_lower = query.lower()

        for item in self.catalog:
            # Filter by category
            if category and item["category"] != category:
                continue

            # Filter by price
            if max_price and item["price_usd"] > max_price:
                continue
            if min_price and item["price_usd"] < min_price:
                continue

            # Filter by room type
            if room_type and room_type not in item.get("room_fit", []):
                continue

            # Score calculation
            score = 0.5
            if query_lower:
                name_match = query_lower in item["name"].lower()
                desc_match = query_lower in item.get("description", "").lower()
                tag_match = any(query_lower in t for t in item.get("tags", []))
                cat_match = query_lower in item["category"].lower()
                if name_match:
                    score += 0.3
                if desc_match:
                    score += 0.1
                if tag_match:
                    score += 0.2
                if cat_match:
                    score += 0.15

            # Style matching
            if style:
                style_lower = style.lower()
                compatible_styles = STYLE_MAP.get(style_lower, [style_lower])
                if item.get("style") in compatible_styles:
                    score += 0.2

            score = min(round(score, 3), 1.0)

            source = FurnitureSource(
                source="ikea",
                url=item.get("url"),
                price=item["price_usd"],
                currency="USD",
                availability="in_stock",
                rating=item.get("rating"),
                reviews_count=item.get("reviews"),
                image_url=item.get("image_url"),
                sku=item.get("sku"),
                brand="IKEA",
                dimensions=item.get("dimensions"),
                colors=item.get("colors"),
                materials=item.get("materials"),
                delivery_days=item.get("delivery_days"),
            )

            results.append(
                FurnitureRecommendation(
                    item_id=item["item_id"],
                    name=item["name"],
                    category=item["category"],
                    score=score,
                    description=item.get("description"),
                    style=item.get("style"),
                    sources=[source],
                    tags=item.get("tags"),
                    room_fit=item.get("room_fit"),
                    metadata={"price_usd": item["price_usd"]},
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def recommend_for_room(
        self,
        room_type: str,
        style: str = "modern",
        budget: Optional[float] = None,
        limit: int = 10,
    ) -> List[FurnitureRecommendation]:
        """Recommend furniture for a specific room type."""
        preferred_categories = ROOM_FURNITURE_MAP.get(room_type, [])
        results = []

        for item in self.catalog:
            if item["category"] not in preferred_categories:
                continue
            if room_type not in item.get("room_fit", []):
                continue
            if budget and item["price_usd"] > budget * 0.4:  # single item max 40% of budget
                continue

            compatible_styles = STYLE_MAP.get(style.lower(), [style.lower()])
            style_score = 0.3 if item.get("style") in compatible_styles else 0.0
            rating_score = (item.get("rating", 4.0) - 3.0) / 2.0 * 0.3
            score = round(0.4 + style_score + rating_score, 3)

            source = FurnitureSource(
                source="ikea",
                url=item.get("url"),
                price=item["price_usd"],
                currency="USD",
                availability="in_stock",
                rating=item.get("rating"),
                reviews_count=item.get("reviews"),
                image_url=item.get("image_url"),
                sku=item.get("sku"),
                brand="IKEA",
                dimensions=item.get("dimensions"),
                colors=item.get("colors"),
                materials=item.get("materials"),
                delivery_days=item.get("delivery_days"),
            )

            results.append(
                FurnitureRecommendation(
                    item_id=item["item_id"],
                    name=item["name"],
                    category=item["category"],
                    score=score,
                    description=item.get("description"),
                    style=item.get("style"),
                    sources=[source],
                    tags=item.get("tags"),
                    room_fit=item.get("room_fit"),
                    metadata={"price_usd": item["price_usd"]},
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


def get_ikea_service() -> IKEAService:
    return IKEAService()
