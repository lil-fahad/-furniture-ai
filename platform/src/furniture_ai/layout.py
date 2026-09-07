"""Deterministic feasibility layer; neural layout coordinates are preferences, never permissions."""

import html
import io
import math
import random
from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from furniture_ai.errors import DomainError
from furniture_ai.schemas import Geometry, Preferences

# Concept dimensions only. No supplier, SKU, inventory, price or purchase claim.
DEFAULT_SIZES = {
    "sofa": (2.2, 0.95, 0.85),
    "armchair": (0.85, 0.85, 0.85),
    "coffee_table": (1.1, 0.6, 0.42),
    "side_table": (0.5, 0.5, 0.5),
    "bed": (1.8, 2.1, 0.6),
    "nightstand": (0.5, 0.45, 0.5),
    "desk": (1.4, 0.7, 0.75),
    "chair": (0.55, 0.55, 0.85),
    "dining_table": (1.6, 0.9, 0.75),
    "cabinet": (1.2, 0.4, 1.2),
    "lamp": (0.4, 0.4, 1.5),
}
COLORS = ["#b49a80", "#607f78", "#c4b9a3", "#9c7964", "#7b8a98", "#a09a85"]


@dataclass(frozen=True)
class Piece:
    id: str
    category: str
    width_m: float
    depth_m: float
    height_m: float
    color: str
    dimension_source: str


def pieces_for(prefs: Preferences) -> list[Piece]:
    pieces = []
    for req in prefs.requirements:
        width, depth, height = DEFAULT_SIZES[req.category]
        for i in range(req.quantity):
            pieces.append(
                Piece(
                    f"{req.category}-{i + 1}",
                    req.category,
                    req.width_m or width,
                    req.depth_m or depth,
                    height,
                    COLORS[len(pieces) % len(COLORS)],
                    "user" if req.width_m and req.depth_m else "concept_assumption",
                )
            )
    return sorted(pieces, key=lambda x: (-x.width_m * x.depth_m, x.id))


def shape(points):
    return Polygon([(p.x, p.y) for p in points])


def footprint(pose):
    return box(pose["x"], pose["y"], pose["x"] + pose["width_m"], pose["y"] + pose["depth_m"])


def reachable(geometry: Geometry, poses: list[dict], width: float) -> bool:
    if not geometry.access_points:
        return True
    room = shape(geometry.boundary)
    physical = [shape(z.polygon) for z in geometry.keepouts if z.kind == "fixed"]
    physical.extend(footprint(p) for p in poses)
    free = room.buffer(-width / 2, join_style=2)
    if physical:
        free = free.difference(unary_union(physical).buffer(width / 2, join_style=2))
    components = list(free.geoms) if hasattr(free, "geoms") else [free]
    return any(
        not c.is_empty and all(c.covers(Point(p.x, p.y)) for p in geometry.access_points) for c in components
    )


def validate_layout(geometry: Geometry, poses: list[dict], prefs: Preferences):
    expected = {p.id: p for p in pieces_for(prefs)}
    if len(poses) != len(expected) or {p.get("id") for p in poses} != set(expected):
        raise DomainError("PIECE_SET", "The layout must contain every requested piece exactly once.")
    for pose in poses:
        spec = expected[pose["id"]]
        if pose.get("rotation") not in (0, 90) or pose.get("category") != spec.category:
            raise DomainError("PIECE_SPEC", "Furniture category or rotation is invalid.")
        required = (spec.depth_m, spec.width_m) if pose["rotation"] == 90 else (spec.width_m, spec.depth_m)
        values = [pose.get(k) for k in ("x", "y", "width_m", "depth_m")]
        if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise DomainError("PIECE_SPEC", "Furniture coordinates must be finite numbers.")
        if any(abs(pose[k] - v) > 1e-6 for k, v in zip(("width_m", "depth_m"), required, strict=True)):
            raise DomainError("PIECE_SPEC", "A layout cannot shrink requested furniture to make it fit.")
    room = shape(geometry.boundary)
    zones = [shape(z.polygon) for z in geometry.keepouts]
    footprints = [footprint(p) for p in poses]
    if any(not room.buffer(1e-8).covers(p) for p in footprints):
        raise DomainError("OUTSIDE_ROOM", "A furniture footprint is outside the room.")
    for i, f in enumerate(footprints):
        if any(f.intersection(z).area > 1e-8 or f.distance(z) + 1e-8 < prefs.clearance_m for z in zones):
            raise DomainError("BLOCKED_ZONE", "Furniture intersects a reserved area.")
        if any(
            f.intersection(g).area > 1e-8 or f.distance(g) + 1e-8 < prefs.clearance_m for g in footprints[:i]
        ):
            raise DomainError("COLLISION", "Furniture clearance is insufficient.")
    if not reachable(geometry, poses, prefs.walkway_m):
        raise DomainError("ACCESS_BLOCKED", "Specified access points do not share a clear walking path.")


def plan_layouts(geometry: Geometry, prefs: Preferences, targets: list[dict] | None = None):
    if not geometry.confirmed:
        raise DomainError("GEOMETRY_REQUIRED", "Confirm the room dimensions before creating a measured plan.")
    room = shape(geometry.boundary)
    obstacles = [shape(z.polygon) for z in geometry.keepouts]
    specs = pieces_for(prefs)
    minx, miny, maxx, maxy = room.bounds
    rng = random.Random(prefs.seed)
    beam = [(0.0, [])]
    target_by_id = {p["id"]: p for p in targets or []}
    for spec in specs:
        candidates = []
        for rotation, w, d in [(0, spec.width_m, spec.depth_m), (90, spec.depth_m, spec.width_m)]:
            if w > maxx - minx or d > maxy - miny:
                continue
            # A finite grid makes runtime independent of input resolution.
            xs = set(float(x) for x in np.linspace(minx, maxx - w, 12))
            ys = set(float(y) for y in np.linspace(miny, maxy - d, 12))
            target = target_by_id.get(spec.id)
            if target:
                xs.add(max(minx, min(float(target["x"]), maxx - w)))
                ys.add(max(miny, min(float(target["y"]), maxy - d)))
            for x in sorted(xs):
                for y in sorted(ys):
                    poly = box(x, y, x + w, y + d)
                    if not room.covers(poly) or any(poly.distance(z) < prefs.clearance_m for z in obstacles):
                        continue
                    wall_distance = min(x - minx, y - miny, maxx - x - w, maxy - y - d)
                    is_central = spec.category in {"coffee_table", "dining_table"}
                    center_dist = poly.centroid.distance(room.centroid) / max(maxx - minx, maxy - miny)
                    score = (1 - center_dist) if is_central else (1 / (1 + wall_distance))
                    if target:
                        score += 2 / (1 + math.hypot(x - target["x"], y - target["y"]))
                        score += 0.2 * (rotation == target.get("rotation"))
                    score += rng.random() * 0.06
                    pose = {
                        **asdict(spec),
                        "x": round(x, 6),
                        "y": round(y, 6),
                        "width_m": w,
                        "depth_m": d,
                        "rotation": rotation,
                    }
                    candidates.append((score, pose, poly))
        candidates.sort(key=lambda c: -c[0])
        # Keep a geographically spread shortlist, not only a cluster at one corner.
        shortlist, bins = [], set()
        for cand in candidates:
            p = cand[1]
            b = (round(p["x"] * 2), round(p["y"] * 2), p["rotation"])
            if b not in bins:
                bins.add(b)
                shortlist.append(cand)
            if len(shortlist) == 96:
                break
        expanded = []
        for base_score, placed in beam:
            occupied = [footprint(p) for p in placed]
            for score, pose, poly in shortlist:
                if any(
                    poly.intersection(p).area > 1e-8 or poly.distance(p) + 1e-8 < prefs.clearance_m
                    for p in occupied
                ):
                    continue
                updated = placed + [pose]
                if reachable(geometry, updated, prefs.walkway_m):
                    expanded.append((base_score + score, updated))
        if not expanded:
            raise DomainError(
                "NO_FEASIBLE_LAYOUT",
                "No layout found within the bounded search. Reduce furniture "
                "sizes or quantities, or revise the confirmed reserved areas.",
            )
        expanded.sort(key=lambda x: -x[0])
        beam = expanded[:32]
    output = []
    signatures = []
    for score, poses in beam:
        signature = np.array([[p["x"], p["y"]] for p in poses])
        if any(np.mean(np.linalg.norm(signature - x, axis=1)) < 0.25 for x in signatures):
            continue
        validate_layout(geometry, poses, prefs)
        output.append(
            {
                "pieces": poses,
                "layout_score": round(score / len(specs), 4),
                "access_checked": bool(geometry.access_points),
                "area_m2": round(room.area, 3),
            }
        )
        signatures.append(signature)
        if len(output) == prefs.variants:
            break
    return output


def plan_svg(geometry: Geometry, layout: dict) -> str:
    room = shape(geometry.boundary)
    minx, miny, maxx, maxy = room.bounds
    scale = min(840 / (maxx - minx), 640 / (maxy - miny))

    def coords(points):
        return " ".join(f"{50 + (p.x - minx) * scale:.2f},{50 + (p.y - miny) * scale:.2f}" for p in points)

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 770" role="img" '
        'aria-label="Measured furniture plan">',
        '<rect width="940" height="770" fill="#faf7f0"/>',
        f'<polygon points="{coords(geometry.boundary)}" fill="#e9e3d8" stroke="#243e39" stroke-width="5"/>',
    ]
    for zone in geometry.keepouts:
        out.append(f'<polygon points="{coords(zone.polygon)}" fill="#e6ada2" opacity="0.8"/>')
    for i, p in enumerate(layout["pieces"]):
        x, y, w, d = (
            50 + (p["x"] - minx) * scale,
            50 + (p["y"] - miny) * scale,
            p["width_m"] * scale,
            p["depth_m"] * scale,
        )
        out.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{d:.2f}" rx="5" '
            f'fill="{p["color"]}" stroke="#40514c" stroke-width="1.5"/>'
        )
        out.append(
            f'<text x="{x + w / 2:.2f}" y="{y + d / 2:.2f}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="17" fill="#152f28">{i + 1}</text>'
        )
    for p in geometry.access_points:
        out.append(
            f'<circle cx="{50 + (p.x - minx) * scale:.2f}" cy="{50 + (p.y - miny) * scale:.2f}" r="7" fill="#186a5d"/>'
        )
    label = html.escape(f"{maxx - minx:.2f} × {maxy - miny:.2f} m bounding dimensions · {room.area:.2f} m²")
    out.append(
        f'<text x="50" y="740" font-family="sans-serif" font-size="20" fill="#243e39">{label}</text></svg>'
    )
    return "".join(out)


def plan_image(geometry: Geometry, layout: dict, size: int = 1024) -> bytes:
    room = shape(geometry.boundary)
    minx, miny, maxx, maxy = room.bounds
    factor = (size - 96) / max(maxx - minx, maxy - miny)

    def xy(x, y):
        return (48 + (x - minx) * factor, 48 + (y - miny) * factor)

    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon([xy(p.x, p.y) for p in geometry.boundary], fill="#eee9df", outline="black", width=8)
    for z in geometry.keepouts:
        draw.polygon([xy(p.x, p.y) for p in z.polygon], fill="#a1a1a1", outline="black", width=4)
    for p in layout["pieces"]:
        draw.rectangle(
            [xy(p["x"], p["y"]), xy(p["x"] + p["width_m"], p["y"] + p["depth_m"])],
            fill=p["color"],
            outline="black",
            width=4,
        )
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()
