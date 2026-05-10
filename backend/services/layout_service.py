"""
3D layout service — generates room meshes and places furniture
based on detected rooms from blueprint analysis.
"""
from __future__ import annotations

import logging
import math
import uuid
from typing import List, Optional, Tuple

from backend.models.pydantic_schemas import Detection, Mesh, Layout3DResponse, LayoutRequest

logger = logging.getLogger("furniture_ai")

# Furniture mesh templates (normalized 0-1 scale, will be scaled to room)
FURNITURE_TEMPLATES: dict = {
    "sofa":    {"w": 2.2, "d": 0.9, "h": 0.85, "color": "#8B7355"},
    "chair":   {"w": 0.7, "d": 0.7, "h": 0.9,  "color": "#A0522D"},
    "table":   {"w": 1.4, "d": 0.8, "h": 0.75, "color": "#DEB887"},
    "bed":     {"w": 1.6, "d": 2.0, "h": 0.5,  "color": "#B0C4DE"},
    "desk":    {"w": 1.2, "d": 0.6, "h": 0.75, "color": "#D2B48C"},
    "storage": {"w": 0.8, "d": 0.4, "h": 1.8,  "color": "#C0C0C0"},
    "rug":     {"w": 2.0, "d": 1.5, "h": 0.02, "color": "#CD853F"},
    "lamp":    {"w": 0.4, "d": 0.4, "h": 1.8,  "color": "#FFD700"},
    "room":    {"w": 5.0, "d": 4.0, "h": 2.8,  "color": "#F5F5F5"},
}

ROOM_FURNITURE_LAYOUT: dict = {
    "living room": [
        ("sofa",    (0.5, 0.0, 0.5)),
        ("table",   (0.5, 0.0, 1.5)),
        ("chair",   (2.0, 0.0, 0.5)),
        ("rug",     (0.5, 0.0, 0.8)),
        ("lamp",    (3.0, 0.0, 0.2)),
    ],
    "bedroom": [
        ("bed",     (0.5, 0.0, 0.5)),
        ("storage", (3.0, 0.0, 0.2)),
        ("lamp",    (2.5, 0.0, 0.2)),
        ("rug",     (0.5, 0.0, 1.5)),
    ],
    "office": [
        ("desk",    (0.5, 0.0, 0.5)),
        ("chair",   (0.8, 0.0, 1.2)),
        ("storage", (3.0, 0.0, 0.2)),
        ("lamp",    (0.2, 0.0, 0.2)),
    ],
    "dining room": [
        ("table",   (1.0, 0.0, 1.0)),
        ("chair",   (0.2, 0.0, 1.0)),
        ("chair",   (2.0, 0.0, 1.0)),
        ("lamp",    (1.5, 2.0, 1.5)),
    ],
    "room": [
        ("sofa",    (0.5, 0.0, 0.5)),
        ("table",   (0.5, 0.0, 1.8)),
        ("chair",   (2.5, 0.0, 0.5)),
        ("rug",     (0.5, 0.0, 0.8)),
    ],
}


def _box_mesh(
    x: float, y: float, z: float,
    w: float, h: float, d: float,
    label: str,
    color: str,
    mesh_id: Optional[str] = None,
) -> Mesh:
    """Generate a box mesh at position (x,y,z) with dimensions (w,h,d)."""
    mid = mesh_id or str(uuid.uuid4())
    # 8 vertices of a box
    verts = [
        [x,     y,     z    ],
        [x + w, y,     z    ],
        [x + w, y + h, z    ],
        [x,     y + h, z    ],
        [x,     y,     z + d],
        [x + w, y,     z + d],
        [x + w, y + h, z + d],
        [x,     y + h, z + d],
    ]
    # 12 triangles (2 per face × 6 faces)
    faces = [
        [0, 1, 2], [0, 2, 3],   # front
        [4, 6, 5], [4, 7, 6],   # back
        [0, 4, 5], [0, 5, 1],   # bottom
        [2, 6, 7], [2, 7, 3],   # top
        [0, 3, 7], [0, 7, 4],   # left
        [1, 5, 6], [1, 6, 2],   # right
    ]
    return Mesh(
        id=mid,
        label=label,
        vertices=verts,
        faces=faces,
        color=color,
        position=[x, y, z],
    )


def _room_mesh_from_detection(det: Detection, index: int) -> Tuple[Mesh, dict]:
    """Create a floor-plan room mesh from a Detection bbox."""
    x1, y1, x2, y2 = det.bbox
    scale = 0.01  # pixels → meters (rough)
    rw = max((x2 - x1) * scale, 2.0)
    rd = max((y2 - y1) * scale, 2.0)
    rh = 2.8
    ox = index * (rw + 1.0)
    room_label = det.room_type or det.label or "room"
    mesh = _box_mesh(ox, 0, 0, rw, rh, rd, label=room_label, color="#E8E8E8")
    return mesh, {"ox": ox, "rw": rw, "rd": rd, "rh": rh, "label": room_label}


class LayoutService:
    def generate(self, req: LayoutRequest) -> Layout3DResponse:
        meshes: List[Mesh] = []
        room_bounds_list = []

        rooms = req.rooms or []

        if not rooms:
            # Default single room
            rooms = [Detection(label="room", confidence=1.0, bbox=[0, 0, 500, 400])]

        for idx, det in enumerate(rooms):
            room_mesh, bounds = _room_mesh_from_detection(det, idx)
            meshes.append(room_mesh)
            room_bounds_list.append(bounds)

            # Place furniture inside the room
            room_label = bounds["label"].lower()
            layout_key = room_label if room_label in ROOM_FURNITURE_LAYOUT else "room"
            furniture_layout = ROOM_FURNITURE_LAYOUT[layout_key]

            ox = bounds["ox"]
            rw = bounds["rw"]
            rd = bounds["rd"]

            for ftype, (fx_rel, fy_rel, fz_rel) in furniture_layout:
                tmpl = FURNITURE_TEMPLATES.get(ftype, FURNITURE_TEMPLATES["table"])
                fw, fh, fd = tmpl["w"], tmpl["h"], tmpl["d"]
                color = tmpl["color"]

                # Clamp furniture inside room
                fx = ox + min(fx_rel, rw - fw - 0.1)
                fy = fy_rel
                fz = min(fz_rel, rd - fd - 0.1)

                meshes.append(_box_mesh(fx, fy, fz, fw, fh, fd, label=ftype, color=color))

        total_bounds = {
            "rooms": len(rooms),
            "total_width": sum(b["rw"] for b in room_bounds_list),
            "max_depth": max(b["rd"] for b in room_bounds_list) if room_bounds_list else 4.0,
        }

        logger.info("layout generated", extra={"mesh_count": len(meshes), "rooms": len(rooms)})
        return Layout3DResponse(
            meshes=meshes,
            metadata={"source": req.blueprint_url, "style": req.style},
            room_bounds=total_bounds,
        )


def get_layout_service() -> LayoutService:
    return LayoutService()
