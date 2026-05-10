"""
Alibaba / AliExpress Furniture Service
Searches Alibaba/AliExpress furniture catalog.
Uses Alibaba Cloud AI (DashScope / Qwen) API for intelligent recommendations,
with a rich built-in catalog as fallback.
"""
from typing import List, Optional, Dict, Any
import random
import json
import logging

from backend.models.pydantic_schemas import FurnitureRecommendation, FurnitureSource
from backend.logging.logger import logger
from backend.core.config import get_settings

# ─── Rich Alibaba Built-in Catalog ───────────────────────────────────────────
ALIBABA_CATALOG: List[Dict] = [
    {
        "item_id": "ali-sofa-l001",
        "name": "Nordic Minimalist L-Shape Sofa",
        "category": "sofa",
        "style": "modern",
        "description": "High-quality fabric L-shaped sofa with solid wood legs. Perfect for modern living rooms.",
        "price_usd": 420.00,
        "min_order": 1,
        "supplier": "Guangzhou Comfort Furniture Co.",
        "colors": ["light-gray", "dark-gray", "beige", "blue"],
        "materials": ["linen-fabric", "solid-wood", "high-density-foam"],
        "dimensions": {"width": 260, "depth": 160, "height": 85},
        "room_fit": ["living_room"],
        "tags": ["sofa", "l-shape", "nordic", "modern", "fabric"],
        "rating": 4.6,
        "reviews": 2340,
        "image_url": "https://sc04.alicdn.com/kf/H1234567890/nordic-sofa.jpg",
        "url": "https://www.alibaba.com/product-detail/Nordic-Minimalist-L-Shape-Sofa_1234567890.html",
        "delivery_days": 25,
        "moq": 1,
    },
    {
        "item_id": "ali-bed-001",
        "name": "Modern Upholstered Platform Bed",
        "category": "bed",
        "style": "modern",
        "description": "Luxury upholstered platform bed with LED headboard. King/Queen sizes available.",
        "price_usd": 380.00,
        "min_order": 1,
        "supplier": "Foshan Dream Furniture Factory",
        "colors": ["white", "gray", "beige", "black"],
        "materials": ["velvet", "solid-wood", "MDF"],
        "dimensions": {"width": 180, "depth": 210, "height": 120},
        "room_fit": ["bedroom"],
        "tags": ["bed", "platform-bed", "LED", "luxury", "upholstered"],
        "rating": 4.7,
        "reviews": 1890,
        "image_url": "https://sc04.alicdn.com/kf/H1234567891/platform-bed.jpg",
        "url": "https://www.alibaba.com/product-detail/Modern-Upholstered-Platform-Bed_1234567891.html",
        "delivery_days": 30,
        "moq": 1,
    },
    {
        "item_id": "ali-dining-001",
        "name": "Marble Top Dining Table Set",
        "category": "table",
        "style": "modern",
        "description": "Elegant marble top dining table with 6 chairs. Stainless steel base.",
        "price_usd": 650.00,
        "min_order": 1,
        "supplier": "Shenzhen Elite Furniture Co.",
        "colors": ["white-marble", "black-marble", "gold"],
        "materials": ["marble", "stainless-steel", "leather"],
        "dimensions": {"width": 180, "depth": 90, "height": 76},
        "room_fit": ["dining_room"],
        "tags": ["dining-table", "marble", "luxury", "set", "modern"],
        "rating": 4.8,
        "reviews": 987,
        "image_url": "https://sc04.alicdn.com/kf/H1234567892/marble-dining.jpg",
        "url": "https://www.alibaba.com/product-detail/Marble-Top-Dining-Table-Set_1234567892.html",
        "delivery_days": 35,
        "moq": 1,
    },
    {
        "item_id": "ali-wardrobe-001",
        "name": "Sliding Door Wardrobe with Mirror",
        "category": "wardrobe",
        "style": "modern",
        "description": "Space-saving sliding door wardrobe with full-length mirror. Customizable interior.",
        "price_usd": 520.00,
        "min_order": 1,
        "supplier": "Guangdong Storage Solutions Ltd.",
        "colors": ["white", "walnut", "gray"],
        "materials": ["MDF", "tempered-glass", "aluminum"],
        "dimensions": {"width": 200, "depth": 60, "height": 240},
        "room_fit": ["bedroom"],
        "tags": ["wardrobe", "sliding-door", "mirror", "storage", "modern"],
        "rating": 4.5,
        "reviews": 1560,
        "image_url": "https://sc04.alicdn.com/kf/H1234567893/sliding-wardrobe.jpg",
        "url": "https://www.alibaba.com/product-detail/Sliding-Door-Wardrobe-Mirror_1234567893.html",
        "delivery_days": 28,
        "moq": 1,
    },
    {
        "item_id": "ali-office-001",
        "name": "Ergonomic Executive Office Desk",
        "category": "desk",
        "style": "modern",
        "description": "Height-adjustable executive desk with cable management. Perfect for home office.",
        "price_usd": 280.00,
        "min_order": 1,
        "supplier": "Zhejiang Office Furniture Co.",
        "colors": ["walnut", "white", "black"],
        "materials": ["solid-wood", "steel", "tempered-glass"],
        "dimensions": {"width": 160, "depth": 80, "height": 75},
        "room_fit": ["office", "bedroom"],
        "tags": ["desk", "office", "ergonomic", "height-adjustable", "executive"],
        "rating": 4.6,
        "reviews": 2100,
        "image_url": "https://sc04.alicdn.com/kf/H1234567894/office-desk.jpg",
        "url": "https://www.alibaba.com/product-detail/Ergonomic-Executive-Office-Desk_1234567894.html",
        "delivery_days": 20,
        "moq": 1,
    },
    {
        "item_id": "ali-chair-001",
        "name": "Velvet Accent Chair",
        "category": "chair",
        "style": "modern",
        "description": "Luxurious velvet accent chair with gold metal legs. Adds elegance to any room.",
        "price_usd": 120.00,
        "min_order": 2,
        "supplier": "Foshan Luxury Seating Factory",
        "colors": ["emerald-green", "dusty-pink", "navy-blue", "mustard"],
        "materials": ["velvet", "solid-wood", "gold-metal"],
        "dimensions": {"width": 70, "depth": 75, "height": 85},
        "room_fit": ["living_room", "bedroom", "office"],
        "tags": ["chair", "accent-chair", "velvet", "luxury", "gold"],
        "rating": 4.7,
        "reviews": 3450,
        "image_url": "https://sc04.alicdn.com/kf/H1234567895/velvet-chair.jpg",
        "url": "https://www.alibaba.com/product-detail/Velvet-Accent-Chair-Gold-Legs_1234567895.html",
        "delivery_days": 18,
        "moq": 2,
    },
    {
        "item_id": "ali-tv-001",
        "name": "Floating TV Wall Unit",
        "category": "storage",
        "style": "modern",
        "description": "Wall-mounted TV unit with LED backlight. Includes shelves and cabinets.",
        "price_usd": 340.00,
        "min_order": 1,
        "supplier": "Guangzhou Modern Living Co.",
        "colors": ["white", "walnut", "gray-oak"],
        "materials": ["MDF", "tempered-glass", "LED-strip"],
        "dimensions": {"width": 240, "depth": 35, "height": 180},
        "room_fit": ["living_room"],
        "tags": ["tv-unit", "wall-mounted", "LED", "storage", "modern"],
        "rating": 4.5,
        "reviews": 1230,
        "image_url": "https://sc04.alicdn.com/kf/H1234567896/tv-wall-unit.jpg",
        "url": "https://www.alibaba.com/product-detail/Floating-TV-Wall-Unit-LED_1234567896.html",
        "delivery_days": 25,
        "moq": 1,
    },
    {
        "item_id": "ali-lamp-001",
        "name": "Nordic Pendant Light Cluster",
        "category": "lighting",
        "style": "scandinavian",
        "description": "Minimalist pendant light cluster with adjustable height. E27 bulb compatible.",
        "price_usd": 85.00,
        "min_order": 1,
        "supplier": "Zhongshan Lighting Factory",
        "colors": ["black", "gold", "white"],
        "materials": ["iron", "glass"],
        "dimensions": {"width": 60, "depth": 60, "height": 120},
        "room_fit": ["living_room", "dining_room", "bedroom"],
        "tags": ["lamp", "pendant", "nordic", "cluster", "minimalist"],
        "rating": 4.6,
        "reviews": 4560,
        "image_url": "https://sc04.alicdn.com/kf/H1234567897/pendant-light.jpg",
        "url": "https://www.alibaba.com/product-detail/Nordic-Pendant-Light-Cluster_1234567897.html",
        "delivery_days": 15,
        "moq": 1,
    },
    {
        "item_id": "ali-bookshelf-001",
        "name": "Industrial Pipe Bookshelf",
        "category": "storage",
        "style": "industrial",
        "description": "Rustic industrial bookshelf with metal pipe frame and solid wood shelves.",
        "price_usd": 180.00,
        "min_order": 1,
        "supplier": "Dongguan Industrial Furniture Co.",
        "colors": ["rustic-brown", "black-pipe", "walnut"],
        "materials": ["solid-wood", "iron-pipe"],
        "dimensions": {"width": 120, "depth": 30, "height": 180},
        "room_fit": ["living_room", "office", "bedroom"],
        "tags": ["bookshelf", "industrial", "pipe", "rustic", "storage"],
        "rating": 4.4,
        "reviews": 2890,
        "image_url": "https://sc04.alicdn.com/kf/H1234567898/pipe-bookshelf.jpg",
        "url": "https://www.alibaba.com/product-detail/Industrial-Pipe-Bookshelf_1234567898.html",
        "delivery_days": 20,
        "moq": 1,
    },
    {
        "item_id": "ali-rug-001",
        "name": "Persian Style Area Rug",
        "category": "rug",
        "style": "traditional",
        "description": "Machine-made Persian style area rug with intricate patterns. Soft and durable.",
        "price_usd": 95.00,
        "min_order": 1,
        "supplier": "Tianjin Textile Factory",
        "colors": ["red-gold", "blue-ivory", "green-beige"],
        "materials": ["polypropylene", "cotton-backing"],
        "dimensions": {"width": 200, "depth": 300, "height": 1},
        "room_fit": ["living_room", "dining_room", "bedroom"],
        "tags": ["rug", "persian", "traditional", "area-rug", "pattern"],
        "rating": 4.3,
        "reviews": 5670,
        "image_url": "https://sc04.alicdn.com/kf/H1234567899/persian-rug.jpg",
        "url": "https://www.alibaba.com/product-detail/Persian-Style-Area-Rug_1234567899.html",
        "delivery_days": 15,
        "moq": 1,
    },
    {
        "item_id": "ali-coffee-001",
        "name": "Marble & Gold Coffee Table",
        "category": "table",
        "style": "modern",
        "description": "Luxury marble top coffee table with gold stainless steel base. Statement piece.",
        "price_usd": 220.00,
        "min_order": 1,
        "supplier": "Shenzhen Luxury Home Co.",
        "colors": ["white-marble-gold", "black-marble-gold"],
        "materials": ["marble", "stainless-steel"],
        "dimensions": {"width": 100, "depth": 60, "height": 45},
        "room_fit": ["living_room"],
        "tags": ["coffee-table", "marble", "gold", "luxury", "modern"],
        "rating": 4.7,
        "reviews": 1890,
        "image_url": "https://sc04.alicdn.com/kf/H1234567900/marble-coffee.jpg",
        "url": "https://www.alibaba.com/product-detail/Marble-Gold-Coffee-Table_1234567900.html",
        "delivery_days": 22,
        "moq": 1,
    },
    {
        "item_id": "ali-dresser-001",
        "name": "Modern 6-Drawer Dresser",
        "category": "storage",
        "style": "modern",
        "description": "Sleek 6-drawer dresser with soft-close drawers and metal handles.",
        "price_usd": 195.00,
        "min_order": 1,
        "supplier": "Guangzhou Bedroom Furniture Factory",
        "colors": ["white", "walnut", "gray"],
        "materials": ["MDF", "solid-wood-legs", "metal"],
        "dimensions": {"width": 100, "depth": 45, "height": 110},
        "room_fit": ["bedroom"],
        "tags": ["dresser", "storage", "modern", "soft-close", "bedroom"],
        "rating": 4.5,
        "reviews": 2340,
        "image_url": "https://sc04.alicdn.com/kf/H1234567901/dresser.jpg",
        "url": "https://www.alibaba.com/product-detail/Modern-6-Drawer-Dresser_1234567901.html",
        "delivery_days": 25,
        "moq": 1,
    },
    {
        "item_id": "ali-dining-chair-001",
        "name": "Tulip Style Dining Chair Set",
        "category": "chair",
        "style": "modern",
        "description": "Set of 4 tulip-style dining chairs with cushioned seats. Easy to clean.",
        "price_usd": 280.00,
        "min_order": 1,
        "supplier": "Foshan Dining Furniture Co.",
        "colors": ["white", "black", "gray"],
        "materials": ["ABS-plastic", "fiberglass", "foam-cushion"],
        "dimensions": {"width": 48, "depth": 52, "height": 82},
        "room_fit": ["dining_room", "kitchen"],
        "tags": ["dining-chair", "set", "tulip", "modern", "cushioned"],
        "rating": 4.4,
        "reviews": 3120,
        "image_url": "https://sc04.alicdn.com/kf/H1234567902/tulip-chairs.jpg",
        "url": "https://www.alibaba.com/product-detail/Tulip-Style-Dining-Chair-Set_1234567902.html",
        "delivery_days": 20,
        "moq": 1,
    },
    {
        "item_id": "ali-outdoor-001",
        "name": "Rattan Outdoor Sofa Set",
        "category": "sofa",
        "style": "bohemian",
        "description": "Weather-resistant PE rattan outdoor sofa set with cushions. 4-piece set.",
        "price_usd": 480.00,
        "min_order": 1,
        "supplier": "Guangdong Outdoor Furniture Factory",
        "colors": ["natural-rattan", "dark-brown", "gray"],
        "materials": ["PE-rattan", "aluminum-frame", "polyester-cushion"],
        "dimensions": {"width": 220, "depth": 150, "height": 80},
        "room_fit": ["outdoor", "living_room"],
        "tags": ["outdoor", "rattan", "sofa-set", "weather-resistant", "bohemian"],
        "rating": 4.5,
        "reviews": 1670,
        "image_url": "https://sc04.alicdn.com/kf/H1234567903/rattan-outdoor.jpg",
        "url": "https://www.alibaba.com/product-detail/Rattan-Outdoor-Sofa-Set_1234567903.html",
        "delivery_days": 30,
        "moq": 1,
    },
    {
        "item_id": "ali-mirror-001",
        "name": "Arched Full-Length Mirror",
        "category": "decor",
        "style": "modern",
        "description": "Elegant arched full-length floor mirror with gold metal frame.",
        "price_usd": 75.00,
        "min_order": 1,
        "supplier": "Guangzhou Mirror Factory",
        "colors": ["gold", "black", "silver"],
        "materials": ["iron-frame", "glass"],
        "dimensions": {"width": 60, "depth": 5, "height": 160},
        "room_fit": ["bedroom", "living_room", "bathroom"],
        "tags": ["mirror", "arched", "full-length", "gold", "decor"],
        "rating": 4.8,
        "reviews": 6780,
        "image_url": "https://sc04.alicdn.com/kf/H1234567904/arch-mirror.jpg",
        "url": "https://www.alibaba.com/product-detail/Arched-Full-Length-Mirror_1234567904.html",
        "delivery_days": 12,
        "moq": 1,
    },
]

STYLE_MAP = {
    "modern": ["modern", "scandinavian", "minimalist", "contemporary"],
    "classic": ["classic", "traditional", "bohemian"],
    "scandinavian": ["scandinavian", "modern", "minimalist"],
    "industrial": ["industrial", "modern"],
    "minimalist": ["modern", "scandinavian"],
    "traditional": ["traditional", "classic", "bohemian"],
    "contemporary": ["modern", "scandinavian"],
    "bohemian": ["bohemian", "traditional", "classic"],
    "luxury": ["modern", "contemporary"],
}

ROOM_FURNITURE_MAP = {
    "living_room": ["sofa", "table", "storage", "lighting", "rug", "chair", "decor"],
    "bedroom": ["bed", "storage", "wardrobe", "lighting", "chair", "decor"],
    "dining_room": ["table", "chair", "storage", "lighting"],
    "kitchen": ["table", "chair", "storage"],
    "office": ["desk", "chair", "storage", "lighting"],
    "bathroom": ["storage", "lighting", "decor"],
    "outdoor": ["sofa", "table", "chair"],
}


class AlibabaAIClient:
    """
    Client for Alibaba Cloud DashScope / Qwen AI API.
    Uses the OpenAI-compatible endpoint provided by Alibaba Cloud.
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize the OpenAI-compatible client for DashScope."""
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            logger.info(
                "Alibaba Cloud AI client initialized",
                extra={"model": self.model, "base_url": self.base_url},
            )
        except ImportError:
            logger.warning(
                "openai package not installed; Alibaba AI features disabled. "
                "Install with: pip install openai"
            )
            self._client = None
        except Exception as exc:
            logger.warning(f"Failed to initialize Alibaba AI client: {exc}")
            self._client = None

    def is_available(self) -> bool:
        return self._client is not None and bool(self.api_key)

    def rank_and_enrich(
        self,
        catalog_items: List[Dict],
        query: str,
        style: Optional[str] = None,
        room_type: Optional[str] = None,
        budget: Optional[float] = None,
    ) -> List[Dict]:
        """
        Use Qwen AI to intelligently rank and enrich catalog items based on the query.
        Returns items with AI-generated relevance scores and enhanced descriptions.
        Falls back to catalog items unchanged if AI is unavailable.
        """
        if not self.is_available() or not catalog_items:
            return catalog_items

        try:
            # Build a concise catalog summary for the AI
            items_summary = []
            for item in catalog_items[:20]:  # limit to 20 items for token efficiency
                items_summary.append({
                    "id": item["item_id"],
                    "name": item["name"],
                    "category": item["category"],
                    "style": item.get("style"),
                    "price_usd": item["price_usd"],
                    "tags": item.get("tags", []),
                    "room_fit": item.get("room_fit", []),
                    "rating": item.get("rating", 4.0),
                })

            prompt = f"""You are a furniture recommendation AI for an Alibaba furniture catalog.
Given the following furniture items and a user query, rank them by relevance and return a JSON array.

User Query: "{query}"
Style Preference: {style or 'any'}
Room Type: {room_type or 'any'}
Budget (USD): {budget or 'no limit'}

Furniture Items:
{json.dumps(items_summary, indent=2)}

Return ONLY a valid JSON array of objects with these fields:
- "id": the item_id string
- "score": relevance score from 0.0 to 1.0
- "ai_note": a brief one-sentence reason why this item matches (or doesn't)

Sort by score descending. Include all items."""

            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert furniture recommendation assistant. "
                            "Always respond with valid JSON only, no markdown, no extra text."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
            )

            raw = response.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            ai_rankings = json.loads(raw)

            # Build a score map from AI response
            score_map: Dict[str, Dict] = {}
            for entry in ai_rankings:
                score_map[entry["id"]] = {
                    "score": float(entry.get("score", 0.5)),
                    "ai_note": entry.get("ai_note", ""),
                }

            # Apply AI scores to catalog items
            enriched = []
            for item in catalog_items:
                item_copy = dict(item)
                ai_data = score_map.get(item["item_id"])
                if ai_data:
                    item_copy["_ai_score"] = ai_data["score"]
                    item_copy["_ai_note"] = ai_data["ai_note"]
                else:
                    item_copy["_ai_score"] = 0.3
                    item_copy["_ai_note"] = ""
                enriched.append(item_copy)

            # Sort by AI score
            enriched.sort(key=lambda x: x.get("_ai_score", 0.0), reverse=True)
            logger.info(
                "Alibaba AI ranking applied",
                extra={"items_ranked": len(enriched), "model": self.model},
            )
            return enriched

        except json.JSONDecodeError as exc:
            logger.warning(f"Alibaba AI returned invalid JSON: {exc}")
            return catalog_items
        except Exception as exc:
            logger.warning(f"Alibaba AI ranking failed, using catalog fallback: {exc}")
            return catalog_items

    def generate_room_recommendations(
        self,
        room_type: str,
        style: str = "modern",
        budget: Optional[float] = None,
    ) -> Optional[str]:
        """
        Use Qwen AI to generate a natural-language furniture recommendation
        summary for a given room type and style.
        """
        if not self.is_available():
            return None

        try:
            prompt = (
                f"Suggest the top 5 furniture pieces for a {style} {room_type.replace('_', ' ')}. "
                f"Budget: {'$' + str(budget) if budget else 'flexible'}. "
                "Be concise and practical. Format as a numbered list."
            )

            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert interior design assistant specializing in furniture selection.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.warning(f"Alibaba AI room recommendation failed: {exc}")
            return None


class AlibabaService:
    """Service to search and recommend Alibaba/AliExpress furniture.
    
    Integrates with Alibaba Cloud AI (DashScope / Qwen) for intelligent
    ranking and enrichment of furniture recommendations.
    """

    def __init__(self):
        self.catalog = ALIBABA_CATALOG
        settings = get_settings()

        # Initialize AI client
        self.ai_client = AlibabaAIClient(
            api_key=settings.alibaba_api_key or "",
            base_url=settings.alibaba_api_base_url,
            model=settings.alibaba_ai_model,
        )

        logger.info(
            "Alibaba service initialized",
            extra={
                "catalog_size": len(self.catalog),
                "ai_enabled": self.ai_client.is_available(),
                "ai_model": settings.alibaba_ai_model,
            },
        )

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
        # Step 1: Pre-filter catalog
        candidates = []
        query_lower = query.lower()

        for item in self.catalog:
            if category and item["category"] != category:
                continue
            if max_price and item["price_usd"] > max_price:
                continue
            if min_price and item["price_usd"] < min_price:
                continue
            if room_type and room_type not in item.get("room_fit", []):
                continue
            candidates.append(item)

        # Step 2: AI-powered ranking (if available and query is meaningful)
        use_ai = bool(self.ai_client.is_available() and (query_lower or style or room_type))
        if use_ai:
            candidates = self.ai_client.rank_and_enrich(
                catalog_items=candidates,
                query=query or style or room_type or "furniture",
                style=style,
                room_type=room_type,
                budget=max_price,
            )

        # Step 3: Build results with scores
        results = []
        for item in candidates:
            # Use AI score if available, otherwise compute heuristic score
            if use_ai and "_ai_score" in item:
                score = item["_ai_score"]
            else:
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

                if style:
                    style_lower = style.lower()
                    compatible_styles = STYLE_MAP.get(style_lower, [style_lower])
                    if item.get("style") in compatible_styles:
                        score += 0.2

            score = min(round(score, 3), 1.0)

            # Build description with AI note if available
            description = item.get("description", "")
            ai_note = item.get("_ai_note", "")
            if ai_note:
                description = f"{description} | AI insight: {ai_note}" if description else ai_note

            source = FurnitureSource(
                source="alibaba",
                url=item.get("url"),
                price=item["price_usd"],
                currency="USD",
                availability="available",
                rating=item.get("rating"),
                reviews_count=item.get("reviews"),
                image_url=item.get("image_url"),
                sku=item["item_id"],
                brand=item.get("supplier"),
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
                    description=description,
                    style=item.get("style"),
                    sources=[source],
                    tags=item.get("tags"),
                    room_fit=item.get("room_fit"),
                    metadata={
                        "price_usd": item["price_usd"],
                        "supplier": item.get("supplier"),
                        "moq": item.get("moq", 1),
                        "ai_powered": use_ai,
                    },
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
        """Recommend furniture for a specific room type using AI when available."""
        preferred_categories = ROOM_FURNITURE_MAP.get(room_type, [])
        candidates = []

        for item in self.catalog:
            if item["category"] not in preferred_categories:
                continue
            if room_type not in item.get("room_fit", []):
                continue
            if budget and item["price_usd"] > budget * 0.5:
                continue
            candidates.append(item)

        # AI-powered ranking for room recommendations
        use_ai = bool(self.ai_client.is_available() and bool(candidates))
        if use_ai:
            candidates = self.ai_client.rank_and_enrich(
                catalog_items=candidates,
                query=f"{style} furniture for {room_type.replace('_', ' ')}",
                style=style,
                room_type=room_type,
                budget=budget,
            )

        results = []
        for item in candidates:
            if use_ai and "_ai_score" in item:
                score = item["_ai_score"]
            else:
                compatible_styles = STYLE_MAP.get(style.lower(), [style.lower()])
                style_score = 0.3 if item.get("style") in compatible_styles else 0.0
                rating_score = (item.get("rating", 4.0) - 3.0) / 2.0 * 0.3
                score = round(0.4 + style_score + rating_score, 3)

            score = min(round(score, 3), 1.0)

            description = item.get("description", "")
            ai_note = item.get("_ai_note", "")
            if ai_note:
                description = f"{description} | AI insight: {ai_note}" if description else ai_note

            source = FurnitureSource(
                source="alibaba",
                url=item.get("url"),
                price=item["price_usd"],
                currency="USD",
                availability="available",
                rating=item.get("rating"),
                reviews_count=item.get("reviews"),
                image_url=item.get("image_url"),
                sku=item["item_id"],
                brand=item.get("supplier"),
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
                    description=description,
                    style=item.get("style"),
                    sources=[source],
                    tags=item.get("tags"),
                    room_fit=item.get("room_fit"),
                    metadata={
                        "price_usd": item["price_usd"],
                        "supplier": item.get("supplier"),
                        "moq": item.get("moq", 1),
                        "ai_powered": use_ai,
                    },
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def get_ai_room_summary(
        self,
        room_type: str,
        style: str = "modern",
        budget: Optional[float] = None,
    ) -> Optional[str]:
        """
        Get an AI-generated natural language furniture recommendation summary
        for a room. Returns None if AI is not available.
        """
        return self.ai_client.generate_room_recommendations(
            room_type=room_type,
            style=style,
            budget=budget,
        )


def get_alibaba_service() -> AlibabaService:
    return AlibabaService()
