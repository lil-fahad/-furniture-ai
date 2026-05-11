"""
Build 3D layout training data.

Each training sample contains:
- room mesh (8 vertices / 12 triangles box)
- furniture placements with type, position, dimensions, and style tag

Output files
------------
datasets/layout3d/meshes.json   – room box meshes
datasets/layout3d/layouts.json  – full room + furniture training samples
"""
import json
from pathlib import Path
from typing import List, Tuple
import uuid

# ---------------------------------------------------------------------------
# Room type definitions
# ---------------------------------------------------------------------------
ROOM_TYPES = [
    {
        "label": "living_room",
        "display": "Living Room",
        "dims": {"w": 5.0, "d": 4.0, "h": 2.8},
        "furniture": [
            {"type": "sofa",    "pos": [0.5, 0.0, 0.5],  "dims": [2.2, 0.85, 0.9]},
            {"type": "table",   "pos": [0.5, 0.0, 1.6],  "dims": [1.4, 0.75, 0.8]},
            {"type": "chair",   "pos": [3.2, 0.0, 0.5],  "dims": [0.7, 0.9, 0.7]},
            {"type": "rug",     "pos": [0.4, 0.0, 0.4],  "dims": [2.0, 0.02, 1.5]},
            {"type": "lamp",    "pos": [4.2, 0.0, 0.2],  "dims": [0.4, 1.8, 0.4]},
        ],
    },
    {
        "label": "bedroom",
        "display": "Bedroom",
        "dims": {"w": 4.0, "d": 4.0, "h": 2.8},
        "furniture": [
            {"type": "bed",     "pos": [0.5, 0.0, 0.5],  "dims": [1.6, 0.5, 2.0]},
            {"type": "storage", "pos": [2.8, 0.0, 0.2],  "dims": [0.8, 1.8, 0.4]},
            {"type": "lamp",    "pos": [2.3, 0.0, 0.2],  "dims": [0.4, 1.8, 0.4]},
            {"type": "rug",     "pos": [0.4, 0.0, 1.8],  "dims": [1.8, 0.02, 1.2]},
        ],
    },
    {
        "label": "office",
        "display": "Home Office",
        "dims": {"w": 3.5, "d": 3.0, "h": 2.8},
        "furniture": [
            {"type": "desk",    "pos": [0.3, 0.0, 0.3],  "dims": [1.2, 0.75, 0.6]},
            {"type": "chair",   "pos": [0.55, 0.0, 1.0], "dims": [0.7, 0.9, 0.7]},
            {"type": "storage", "pos": [2.5, 0.0, 0.2],  "dims": [0.8, 1.8, 0.4]},
            {"type": "lamp",    "pos": [0.1, 0.0, 0.1],  "dims": [0.4, 1.8, 0.4]},
        ],
    },
    {
        "label": "dining_room",
        "display": "Dining Room",
        "dims": {"w": 4.0, "d": 3.5, "h": 2.8},
        "furniture": [
            {"type": "table",   "pos": [1.0, 0.0, 0.8],  "dims": [1.6, 0.76, 0.9]},
            {"type": "chair",   "pos": [0.2, 0.0, 0.9],  "dims": [0.5, 0.9, 0.5]},
            {"type": "chair",   "pos": [2.7, 0.0, 0.9],  "dims": [0.5, 0.9, 0.5]},
            {"type": "chair",   "pos": [1.3, 0.0, 0.2],  "dims": [0.5, 0.9, 0.5]},
            {"type": "chair",   "pos": [1.3, 0.0, 1.8],  "dims": [0.5, 0.9, 0.5]},
            {"type": "lamp",    "pos": [1.8, 2.0, 1.2],  "dims": [0.4, 1.8, 0.4]},
        ],
    },
    {
        "label": "kitchen",
        "display": "Kitchen",
        "dims": {"w": 3.5, "d": 3.0, "h": 2.8},
        "furniture": [
            {"type": "storage", "pos": [0.0, 0.0, 0.0],  "dims": [3.5, 0.9, 0.6]},
            {"type": "table",   "pos": [0.5, 0.0, 1.5],  "dims": [1.0, 0.75, 0.6]},
            {"type": "chair",   "pos": [0.5, 0.0, 2.2],  "dims": [0.5, 0.9, 0.5]},
        ],
    },
]

STYLES = ["modern", "scandinavian", "industrial", "classic", "minimalist", "bohemian"]

STYLE_COLORS: dict = {
    "modern":       {"room": "#F0F0F0", "sofa": "#808080", "table": "#C0C0C0"},
    "scandinavian": {"room": "#FAFAF8", "sofa": "#B0A898", "table": "#D4C4A8"},
    "industrial":   {"room": "#D8D0C8", "sofa": "#6B6560", "table": "#8B8378"},
    "classic":      {"room": "#FFF8F0", "sofa": "#8B6914", "table": "#DEB887"},
    "minimalist":   {"room": "#FFFFFF", "sofa": "#E0E0E0", "table": "#E8E8E8"},
    "bohemian":     {"room": "#FFF0E8", "sofa": "#CD853F", "table": "#D2691E"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _box_vertices(x: float, y: float, z: float,
                  w: float, h: float, d: float) -> List[List[float]]:
    """8 corners of an axis-aligned box."""
    return [
        [x,     y,     z    ],
        [x + w, y,     z    ],
        [x + w, y + h, z    ],
        [x,     y + h, z    ],
        [x,     y,     z + d],
        [x + w, y,     z + d],
        [x + w, y + h, z + d],
        [x,     y + h, z + d],
    ]


def _box_faces() -> List[List[int]]:
    """12 triangles for 6 faces of a box (CCW winding)."""
    return [
        [0, 1, 2], [0, 2, 3],   # front
        [4, 6, 5], [4, 7, 6],   # back
        [0, 4, 5], [0, 5, 1],   # bottom
        [2, 6, 7], [2, 7, 3],   # top
        [0, 3, 7], [0, 7, 4],   # left
        [1, 5, 6], [1, 6, 2],   # right
    ]


def _make_mesh(x: float, y: float, z: float,
               w: float, h: float, d: float,
               label: str, color: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "label": label,
        "vertices": _box_vertices(x, y, z, w, h, d),
        "faces": _box_faces(),
        "color": color,
        "position": [x, y, z],
        "dimensions": {"w": w, "h": h, "d": d},
    }


def _make_sample(room_type: dict, style: str, x_offset: float = 0.0) -> dict:
    """Create one training sample for a room type + style combination."""
    dims = room_type["dims"]
    rw, rd, rh = dims["w"], dims["d"], dims["h"]
    style_colors = STYLE_COLORS.get(style, STYLE_COLORS["modern"])

    room_mesh = _make_mesh(
        x_offset, 0, 0, rw, rh, rd,
        label=room_type["label"],
        color=style_colors.get("room", "#F0F0F0"),
    )

    furniture_meshes = []
    for item in room_type["furniture"]:
        fw, fh, fd = item["dims"]
        fx, fy, fz = item["pos"]
        # Clamp inside room
        fx = x_offset + min(fx, rw - fw - 0.05)
        fz = min(fz, rd - fd - 0.05)
        color = style_colors.get(item["type"], "#A0A0A0")
        furniture_meshes.append(
            _make_mesh(fx, fy, fz, fw, fh, fd,
                       label=item["type"], color=color)
        )

    return {
        "id": str(uuid.uuid4()),
        "room_type": room_type["label"],
        "room_display": room_type["display"],
        "style": style,
        "room_mesh": room_mesh,
        "furniture": furniture_meshes,
        "metadata": {
            "total_meshes": 1 + len(furniture_meshes),
            "area_m2": rw * rd,
            "ceiling_height_m": rh,
        },
    }


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------

def build_meshes(output_dir: Path = Path("datasets/layout3d")) -> None:
    """Write flat list of room box meshes (backward-compatible format)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    meshes = []
    x_offset = 0.0
    for room_type in ROOM_TYPES:
        dims = room_type["dims"]
        rw, rd, rh = dims["w"], dims["d"], dims["h"]
        mesh = _make_mesh(x_offset, 0, 0, rw, rh, rd,
                          label=room_type["label"], color="#E8E8E8")
        meshes.append(mesh)
        x_offset += rw + 1.0

    (output_dir / "meshes.json").write_text(json.dumps(meshes, indent=2))
    print(f"[build_3d] wrote {len(meshes)} room meshes -> {output_dir / 'meshes.json'}")


def build_layouts(output_dir: Path = Path("datasets/layout3d")) -> None:
    """Write full training samples (room + furniture) for every room × style."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Also rebuild meshes.json for backward compat
    build_meshes(output_dir)

    samples = []
    for room_type in ROOM_TYPES:
        for style in STYLES:
            sample = _make_sample(room_type, style)
            samples.append(sample)

    (output_dir / "layouts.json").write_text(json.dumps(samples, indent=2))
    total_meshes = sum(s["metadata"]["total_meshes"] for s in samples)
    print(
        f"[build_3d] wrote {len(samples)} layout samples "
        f"({total_meshes} total meshes) -> {output_dir / 'layouts.json'}"
    )
    return samples


if __name__ == "__main__":
    build_layouts()
