"""
3D Layout Generation Service
Generates a 3D room layout with furniture placement based on detected rooms.
"""
from typing import List, Optional
import uuid
import math

from backend.models.pydantic_schemas import (
    Layout3DResponse,
    LayoutRequest,
    Room3D,
    FurnitureObject3D,
    Detection,
)
from backend.logging.logger import logger

# ─── Furniture 3D Templates ───────────────────────────────────────────────────
FURNITURE_TEMPLATES = {
    "sofa": {
        "width": 2.2, "depth": 0.9, "height": 0.85,
        "color": "#6B7280", "category": "sofa",
    },
    "coffee table": {
        "width": 1.0, "depth": 0.6, "height": 0.45,
        "color": "#92400E", "category": "table",
    },
    "TV unit": {
        "width": 1.8, "depth": 0.45, "height": 0.55,
        "color": "#374151", "category": "storage",
    },
    "bookshelf": {
        "width": 0.8, "depth": 0.3, "height": 2.0,
        "color": "#78350F", "category": "storage",
    },
    "rug": {
        "width": 2.5, "depth": 3.5, "height": 0.02,
        "color": "#D97706", "category": "rug",
    },
    "floor lamp": {
        "width": 0.4, "depth": 0.4, "height": 1.8,
        "color": "#6B7280", "category": "lighting",
    },
    "bed": {
        "width": 1.6, "depth": 2.1, "height": 0.6,
        "color": "#F3F4F6", "category": "bed",
    },
    "wardrobe": {
        "width": 1.6, "depth": 0.6, "height": 2.2,
        "color": "#D1D5DB", "category": "storage",
    },
    "dresser": {
        "width": 1.0, "depth": 0.5, "height": 0.9,
        "color": "#D1D5DB", "category": "storage",
    },
    "nightstand": {
        "width": 0.5, "depth": 0.4, "height": 0.6,
        "color": "#D1D5DB", "category": "table",
    },
    "desk lamp": {
        "width": 0.2, "depth": 0.2, "height": 0.5,
        "color": "#6B7280", "category": "lighting",
    },
    "dining table": {
        "width": 1.6, "depth": 0.9, "height": 0.75,
        "color": "#92400E", "category": "table",
    },
    "chairs": {
        "width": 0.5, "depth": 0.5, "height": 0.9,
        "color": "#6B7280", "category": "chair",
    },
    "kitchen island": {
        "width": 1.2, "depth": 0.8, "height": 0.9,
        "color": "#F9FAFB", "category": "table",
    },
    "bar stools": {
        "width": 0.4, "depth": 0.4, "height": 1.1,
        "color": "#6B7280", "category": "chair",
    },
    "sideboard": {
        "width": 1.5, "depth": 0.45, "height": 0.85,
        "color": "#92400E", "category": "storage",
    },
    "pendant light": {
        "width": 0.4, "depth": 0.4, "height": 0.6,
        "color": "#FCD34D", "category": "lighting",
    },
    "vanity": {
        "width": 0.9, "depth": 0.5, "height": 0.85,
        "color": "#F9FAFB", "category": "storage",
    },
    "mirror": {
        "width": 0.6, "depth": 0.05, "height": 1.5,
        "color": "#E5E7EB", "category": "decor",
    },
    "towel rack": {
        "width": 0.6, "depth": 0.1, "height": 1.2,
        "color": "#9CA3AF", "category": "storage",
    },
    "storage cabinet": {
        "width": 0.8, "depth": 0.4, "height": 1.8,
        "color": "#F9FAFB", "category": "storage",
    },
    "desk": {
        "width": 1.4, "depth": 0.7, "height": 0.75,
        "color": "#D1D5DB", "category": "desk",
    },
    "office chair": {
        "width": 0.6, "depth": 0.6, "height": 1.2,
        "color": "#1F2937", "category": "chair",
    },
    "filing cabinet": {
        "width": 0.45, "depth": 0.6, "height": 1.3,
        "color": "#9CA3AF", "category": "storage",
    },
    "console table": {
        "width": 1.2, "depth": 0.35, "height": 0.8,
        "color": "#92400E", "category": "table",
    },
    "coat rack": {
        "width": 0.4, "depth": 0.4, "height": 1.8,
        "color": "#6B7280", "category": "storage",
    },
    "bench": {
        "width": 1.2, "depth": 0.4, "height": 0.5,
        "color": "#92400E", "category": "chair",
    },
    "outdoor chairs": {
        "width": 0.6, "depth": 0.6, "height": 0.9,
        "color": "#6B7280", "category": "chair",
    },
    "small table": {
        "width": 0.6, "depth": 0.6, "height": 0.7,
        "color": "#92400E", "category": "table",
    },
    "plant stand": {
        "width": 0.3, "depth": 0.3, "height": 0.8,
        "color": "#065F46", "category": "decor",
    },
}

ROOM_WALL_COLORS = {
    "living_room": "#F5F5F0",
    "bedroom": "#FDF4FF",
    "kitchen": "#F0FDF4",
    "dining_room": "#FFFBEB",
    "bathroom": "#F0F9FF",
    "office": "#F8FAFC",
    "hallway": "#F9FAFB",
    "room": "#F5F5F0",
}

ROOM_FLOOR_COLORS = {
    "living_room": "#C8A882",
    "bedroom": "#D4B896",
    "kitchen": "#E5E7EB",
    "dining_room": "#C8A882",
    "bathroom": "#F3F4F6",
    "office": "#D1D5DB",
    "hallway": "#9CA3AF",
    "room": "#C8A882",
}


def _place_furniture(
    room_width: float,
    room_depth: float,
    furniture_list: List[str],
    style: str = "modern",
) -> List[FurnitureObject3D]:
    """Place furniture items in a room with smart positioning."""
    objects: List[FurnitureObject3D] = []
    placed_zones: List[dict] = []

    # Placement strategies per furniture type
    placement_rules = {
        "sofa": {"x_ratio": 0.5, "z_ratio": 0.75, "wall": "back"},
        "coffee table": {"x_ratio": 0.5, "z_ratio": 0.55, "wall": "center"},
        "TV unit": {"x_ratio": 0.5, "z_ratio": 0.1, "wall": "front"},
        "bookshelf": {"x_ratio": 0.9, "z_ratio": 0.3, "wall": "right"},
        "rug": {"x_ratio": 0.5, "z_ratio": 0.5, "wall": "center"},
        "floor lamp": {"x_ratio": 0.85, "z_ratio": 0.7, "wall": "corner"},
        "bed": {"x_ratio": 0.5, "z_ratio": 0.7, "wall": "back"},
        "wardrobe": {"x_ratio": 0.1, "z_ratio": 0.2, "wall": "left"},
        "dresser": {"x_ratio": 0.85, "z_ratio": 0.2, "wall": "right"},
        "nightstand": {"x_ratio": 0.65, "z_ratio": 0.7, "wall": "back"},
        "desk lamp": {"x_ratio": 0.5, "z_ratio": 0.5, "wall": "center"},
        "dining table": {"x_ratio": 0.5, "z_ratio": 0.5, "wall": "center"},
        "chairs": {"x_ratio": 0.5, "z_ratio": 0.35, "wall": "center"},
        "kitchen island": {"x_ratio": 0.5, "z_ratio": 0.5, "wall": "center"},
        "bar stools": {"x_ratio": 0.5, "z_ratio": 0.35, "wall": "center"},
        "sideboard": {"x_ratio": 0.85, "z_ratio": 0.5, "wall": "right"},
        "pendant light": {"x_ratio": 0.5, "z_ratio": 0.5, "wall": "ceiling"},
        "vanity": {"x_ratio": 0.5, "z_ratio": 0.1, "wall": "front"},
        "mirror": {"x_ratio": 0.5, "z_ratio": 0.05, "wall": "front"},
        "towel rack": {"x_ratio": 0.85, "z_ratio": 0.5, "wall": "right"},
        "storage cabinet": {"x_ratio": 0.1, "z_ratio": 0.5, "wall": "left"},
        "desk": {"x_ratio": 0.5, "z_ratio": 0.15, "wall": "front"},
        "office chair": {"x_ratio": 0.5, "z_ratio": 0.3, "wall": "center"},
        "filing cabinet": {"x_ratio": 0.9, "z_ratio": 0.15, "wall": "right"},
        "console table": {"x_ratio": 0.5, "z_ratio": 0.05, "wall": "front"},
        "coat rack": {"x_ratio": 0.1, "z_ratio": 0.1, "wall": "corner"},
        "bench": {"x_ratio": 0.5, "z_ratio": 0.05, "wall": "front"},
        "outdoor chairs": {"x_ratio": 0.3, "z_ratio": 0.5, "wall": "center"},
        "small table": {"x_ratio": 0.5, "z_ratio": 0.5, "wall": "center"},
        "plant stand": {"x_ratio": 0.15, "z_ratio": 0.85, "wall": "corner"},
    }

    for furniture_name in furniture_list:
        template = FURNITURE_TEMPLATES.get(furniture_name)
        if not template:
            # Generic fallback
            template = {
                "width": 0.8, "depth": 0.8, "height": 0.8,
                "color": "#9CA3AF", "category": "misc",
            }

        rule = placement_rules.get(furniture_name, {"x_ratio": 0.5, "z_ratio": 0.5})
        x = room_width * rule["x_ratio"]
        z = room_depth * rule["z_ratio"]

        # Clamp to room bounds with margin
        margin = 0.3
        x = max(margin + template["width"] / 2, min(room_width - margin - template["width"] / 2, x))
        z = max(margin + template["depth"] / 2, min(room_depth - margin - template["depth"] / 2, z))

        # Rotation based on wall placement
        wall = rule.get("wall", "center")
        rotation = 0.0
        if wall == "back":
            rotation = 180.0
        elif wall == "left":
            rotation = 90.0
        elif wall == "right":
            rotation = 270.0

        obj = FurnitureObject3D(
            id=str(uuid.uuid4()),
            name=furniture_name,
            category=template["category"],
            position=[round(x, 2), 0.0, round(z, 2)],
            rotation=rotation,
            scale=[1.0, 1.0, 1.0],
            color=template["color"],
            width=template["width"],
            depth=template["depth"],
            height=template["height"],
        )
        objects.append(obj)

    return objects


def _detection_to_room3d(
    detection: Detection,
    index: int,
    img_width: int = 640,
    img_height: int = 480,
    style: str = "modern",
    scale_m_per_px: float = 0.05,
) -> Room3D:
    """Convert a Detection into a Room3D object with furniture."""
    bbox = detection.bbox
    x1, y1, x2, y2 = bbox
    w_px = x2 - x1
    h_px = y2 - y1
    room_width = max(2.0, round(w_px * scale_m_per_px, 1))
    room_depth = max(2.0, round(h_px * scale_m_per_px, 1))

    room_type = detection.room_type or detection.label or "room"
    furniture_list = detection.suggested_furniture or []

    furniture_objects = _place_furniture(room_width, room_depth, furniture_list, style)

    # Position rooms side by side
    offset_x = index * (room_width + 1.0)

    return Room3D(
        id=str(uuid.uuid4()),
        name=room_type.replace("_", " ").title(),
        width=room_width,
        depth=room_depth,
        height=2.8,
        position=[round(offset_x, 2), 0.0, 0.0],
        furniture=furniture_objects,
        wall_color=ROOM_WALL_COLORS.get(room_type, "#F5F5F0"),
        floor_color=ROOM_FLOOR_COLORS.get(room_type, "#C8A882"),
    )


class LayoutService:
    """3D Layout generation service."""

    def generate(self, req: LayoutRequest) -> Layout3DResponse:
        rooms_3d: List[Room3D] = []
        style = req.style or "modern"

        if req.rooms:
            for i, detection in enumerate(req.rooms):
                room = _detection_to_room3d(detection, i, style=style)
                rooms_3d.append(room)
        else:
            # Default single room if no detections provided
            default_detection = Detection(
                label="living_room",
                confidence=1.0,
                bbox=[0.0, 0.0, 200.0, 150.0],
                room_type="living_room",
                area_sqm=15.0,
                suggested_furniture=["sofa", "coffee table", "TV unit", "rug", "floor lamp"],
            )
            rooms_3d.append(_detection_to_room3d(default_detection, 0, style=style))

        total_furniture = sum(len(r.furniture) for r in rooms_3d)

        logger.info(
            "3D layout generated",
            extra={"rooms": len(rooms_3d), "furniture": total_furniture},
        )

        return Layout3DResponse(
            rooms=rooms_3d,
            total_furniture=total_furniture,
            metadata={
                "style": style,
                "blueprint_url": req.blueprint_url,
                "furniture_ids": req.furniture_ids,
            },
        )


def get_layout_service() -> LayoutService:
    return LayoutService()
