"""Parse SpatialLM declarative labels safely into conservative floor-layout supervision."""

import argparse
import ast
import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Polygon, box
from shapely.ops import polygonize, unary_union

from furniture_ai.errors import DomainError
from furniture_ai.layout import pieces_for, validate_layout
from furniture_ai.ml.dataset_io import (
    digest,
    grouped_splits,
    open_zip,
    proposed_split,
    write_json,
    write_jsonl,
)
from furniture_ai.schemas import Geometry, Preferences

CATEGORIES = {
    "sofa": "sofa",
    "armchair": "armchair",
    "coffee_table": "coffee_table",
    "side_table": "side_table",
    "bed": "bed",
    "nightstand": "nightstand",
    "desk": "desk",
    "chair": "chair",
    "dining_table": "dining_table",
    "cabinet": "cabinet",
    "tv_cabinet": "cabinet",
}
NONBLOCKING = {
    "carpet",
    "rug",
    "curtain",
    "decoration",
    "lighting",
    "air_conditioner",
    "painting",
    "picture",
    "wall_decoration",
}
ARITIES = {"Wall": 8, "Door": 6, "Window": 6, "Bbox": 8}


class RejectedLayout(ValueError):
    pass


def parse_layout(text):
    if len(text) > 250_000:
        raise RejectedLayout("oversized_layout")
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        raise RejectedLayout("invalid_syntax") from error
    if len(tree.body) > 500:
        raise RejectedLayout("too_many_statements")
    records, names = [], set()
    for statement in tree.body:
        if not (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
        ):
            raise RejectedLayout("nondeclarative_statement")
        name, call = statement.targets[0].id, statement.value
        kind = call.func.id
        if kind not in ARITIES or len(call.args) != ARITIES[kind] or call.keywords or name in names:
            raise RejectedLayout("invalid_constructor")
        names.add(name)
        values = []
        for i, node in enumerate(call.args):
            if i == 0 and kind != "Wall":
                if isinstance(node, ast.Name):
                    value = node.id
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    value = node.value
                else:
                    raise RejectedLayout("invalid_symbol")
                if not value or len(value) > 100:
                    raise RejectedLayout("invalid_symbol")
            else:
                sign = 1
                if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
                    sign, node = (-1 if isinstance(node.op, ast.USub) else 1), node.operand
                if not isinstance(node, ast.Constant) or type(node.value) not in (int, float):
                    raise RejectedLayout("nonnumeric_coordinate")
                value = sign * float(node.value)
                if not math.isfinite(value) or abs(value) > 1000:
                    raise RejectedLayout("coordinate_out_of_bounds")
            values.append(value)
        records.append((name, kind, values))
    return records


def polygon_points(polygon, dx, dy):
    return [{"x": round(x - dx, 6), "y": round(y - dy, 6)} for x, y in list(polygon.exterior.coords)[:-1]]


def convert_layout(text, source_row):
    records = parse_layout(text)
    walls = {name: values for name, kind, values in records if kind == "Wall"}
    lines = [
        LineString([(round(v[0], 4), round(v[1], 4)), (round(v[3], 4), round(v[4], 4))])
        for v in walls.values()
    ]
    polygons = list(polygonize(unary_union(lines)))
    if len(polygons) != 1 or polygons[0].interiors:
        raise RejectedLayout("nonunique_closed_room")
    room = polygons[0]
    minx, miny, maxx, maxy = room.bounds
    if max(maxx - minx, maxy - miny) > 50 or not 2 <= room.area <= 500:
        raise RejectedLayout("room_outside_application_bounds")
    pieces, obstacles, door_zones, categories = [], [], [], Counter()
    skipped = Counter()
    for name, kind, values in records:
        if kind in {"Door", "Window"} and values[0] not in walls:
            raise RejectedLayout("opening_without_wall")
        if kind == "Door":
            wall_id, cx, cy, _, width, _ = values
            wall = walls[wall_id]
            dx, dy = wall[3] - wall[0], wall[4] - wall[1]
            length = math.hypot(dx, dy)
            if length <= 0 or width <= 0:
                raise RejectedLayout("invalid_door")
            segment = LineString(
                [
                    (cx - dx / length * width / 2, cy - dy / length * width / 2),
                    (cx + dx / length * width / 2, cy + dy / length * width / 2),
                ]
            )
            zone = segment.buffer(0.15, cap_style=2).intersection(room)
            if isinstance(zone, Polygon) and zone.area >= 0.001:
                door_zones.append((name, zone))
        if kind != "Bbox":
            continue
        category, x, y, z, angle, width, depth, height = values
        if min(width, depth, height) <= 0:
            raise RejectedLayout("invalid_object_dimensions")
        if category in NONBLOCKING or z - height / 2 > 0.3:
            skipped["nonfloor_or_nonblocking_object"] += 1
            continue
        if category not in CATEGORIES:
            footprint = affinity.rotate(
                box(x - width / 2, y - depth / 2, x + width / 2, y + depth / 2),
                angle,
                origin=(x, y),
                use_radians=True,
            ).intersection(room)
            if isinstance(footprint, Polygon) and footprint.area >= 0.001:
                obstacles.append((name, footprint))
            continue
        quarter = round(angle / (math.pi / 2))
        if abs(angle - quarter * math.pi / 2) > math.radians(0.25):
            raise RejectedLayout("unsupported_object_yaw")
        mapped = CATEGORIES[category]
        categories[mapped] += 1
        rotation = 90 * (quarter % 2)
        w, d = (depth, width) if rotation else (width, depth)
        pieces.append(
            {
                "source_object_id": name,
                "category": mapped,
                "width_m": width,
                "depth_m": depth,
                "height_m": height,
                "rotation": rotation,
                "x": x - minx - w / 2,
                "y": y - miny - d / 2,
            }
        )
    if not 1 <= len(pieces) <= 16 or len(categories) > 8 or max(categories.values(), default=0) > 6:
        raise RejectedLayout("unsupported_piece_count")
    requirements = []
    for category in sorted(categories):
        values = sorted((p for p in pieces if p["category"] == category), key=lambda p: (p["x"], p["y"]))
        width, depth = values[0]["width_m"], values[0]["depth_m"]
        if any(abs(p["width_m"] - width) > 1e-6 or abs(p["depth_m"] - depth) > 1e-6 for p in values):
            raise RejectedLayout("heterogeneous_sizes_in_one_requirement")
        requirements.append(
            {"category": category, "quantity": len(values), "width_m": width, "depth_m": depth}
        )
        for i, value in enumerate(values, 1):
            value["id"] = f"{category}-{i}"
    try:
        geometry = Geometry.model_validate(
            {
                "boundary": polygon_points(room, minx, miny),
                "confirmed": True,
                "keepouts": [
                    {"label": name, "kind": kind, "polygon": polygon_points(poly, minx, miny)}
                    for kind, values in [("fixed", obstacles), ("door", door_zones)]
                    for name, poly in values
                ],
            }
        )
        preferences = Preferences.model_validate(
            {
                "requirements": requirements,
                "clearance_m": 0.05,
                "walkway_m": 0.5,
                "variants": 1,
                "room_type": "other",
            }
        )
        pieces.sort(key=lambda p: (-p["width_m"] * p["depth_m"], p["id"]))
        poses = []
        specifications = {p.id: p for p in pieces_for(preferences)}
        for piece in pieces:
            spec = specifications[piece["id"]]
            width, depth = (spec.depth_m, spec.width_m) if piece["rotation"] else (spec.width_m, spec.depth_m)
            poses.append({**piece, "width_m": width, "depth_m": depth})
        validate_layout(geometry, poses, preferences)
    except (ValueError, DomainError) as error:
        raise RejectedLayout(getattr(error, "code", "schema_rejected")) from error
    payload = {
        "geometry": geometry.model_dump(),
        "preferences": preferences.model_dump(),
        "pieces": [{k: p[k] for k in ["id", "category", "width_m", "depth_m", "height_m"]} for p in pieces],
        "placements": [{k: p[k] for k in ["id", "x", "y", "rotation"]} for p in pieces],
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    scene = source_row["scene_id"]
    return {
        **payload,
        "id": source_row["id"],
        "group_id": scene,
        "content_sha256": fingerprint,
        "source_layout_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source": "https://huggingface.co/datasets/manycore-research/SpatialLM-Dataset",
        "source_split": source_row["split"],
        "source_room_type": source_row["room_type"],
        "license": "CC-BY-NC-4.0",
        "training_use": True,
        "commercial_use": False,
        "consent": True,
        "permission_basis": "Publisher public noncommercial license; not a claim of subject consent",
        "proposed_split": proposed_split(scene) if source_row["split"] == "train" else "reserved",
        "conversion": {
            "units": "metres",
            "origin_translation": [minx, miny],
            "maximum_yaw_snap_degrees": 0.25,
            "wall_join_rounding_metres": 0.0001,
            "door_keepout": "15 cm threshold proxy; door hinge/swing not supplied",
            "ignored_objects": dict(skipped),
            "source_style_label_available": False,
        },
    }


def prepare(path, output, research=False):
    if not research:
        raise ValueError("SpatialLM is noncommercial: pass --research for the separate research data path")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    accepted, rejected = [], Counter()
    rejection_examples, rooms = defaultdict(list), {}
    with open_zip(path) as outer:
        source_rows = list(csv.DictReader(io.StringIO(outer.read("valid_layout_split.csv").decode())))
        for row in sorted(source_rows, key=lambda r: r["id"]):
            rooms.setdefault((row["scene_id"], row["room_id"]), row)
        selected = {row["id"]: row for row in rooms.values()}
        for chunk in sorted(
            n for n in outer.namelist() if n.startswith("spatiallm/layout/") and n.endswith(".zip")
        ):
            with open_zip(io.BytesIO(outer.read(chunk))) as inner:
                for member in inner.infolist():
                    key = Path(member.filename).stem
                    if key not in selected:
                        continue
                    try:
                        accepted.append(convert_layout(inner.read(member).decode(), selected[key]))
                    except RejectedLayout as error:
                        reason = str(error)
                        rejected[reason] += 1
                        if len(rejection_examples[reason]) < 5:
                            rejection_examples[reason].append(key)
            print(
                json.dumps(
                    {"chunk": Path(chunk).name, "accepted": len(accepted), "rejected": sum(rejected.values())}
                ),
                flush=True,
            )
        (root / "LICENSE-CC-BY-NC-4.0.txt").write_bytes(outer.read("spatiallm/LICENSE"))
    splits = grouped_splits(accepted)
    for split, rows in splits.items():
        write_jsonl(root / f"{split}.jsonl", rows)
    report = {
        "dataset": "SpatialLM floor-layout research subset",
        "license": "CC-BY-NC-4.0",
        "archive_sha256": digest(path),
        "source_layout_records": len(source_rows),
        "source_unique_rooms": len(rooms),
        "accepted_rooms": len(accepted),
        "rejected_rooms": sum(rejected.values()),
        "rejection_reasons": dict(rejected),
        "rejection_examples": dict(rejection_examples),
        "splits": {k: len(v) for k, v in splits.items()},
        "split_policy": "Only publisher-train scenes are split 70/15/15 by scene identity; original val/test/reserved rooms remain quarantined",
        "geometry_policy": "Closed source wall polygon; floor objects only; unsupported objects retained as fixed obstacles; dimensions are not resized to pass validation",
        "source_pointclouds_included": False,
        "commercial_use": False,
        "ready_for_training": all(bool(splits[k]) for k in ("train", "validation", "test")),
    }
    write_json(root / "dataset-card.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--research", action="store_true")
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.output, args.research), indent=2), flush=True)


if __name__ == "__main__":
    main()
