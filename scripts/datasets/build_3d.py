import json
import math
import random
import uuid
from pathlib import Path


def _box(w: float, h: float, d: float) -> dict:
    """Generate vertices and triangle faces for an axis-aligned box."""
    x, y, z = w / 2, d / 2, h / 2
    verts = [
        [-x, -y, -z], [x, -y, -z], [x, y, -z], [-x, y, -z],
        [-x, -y, z], [x, -y, z], [x, y, z], [-x, y, z],
    ]
    faces = [
        [0, 1, 2], [0, 2, 3],
        [4, 6, 5], [4, 7, 6],
        [0, 4, 5], [0, 5, 1],
        [1, 5, 6], [1, 6, 2],
        [2, 6, 7], [2, 7, 3],
        [3, 7, 4], [3, 4, 0],
    ]
    return {"vertices": verts, "faces": faces}


def _cylinder(radius: float, height: float, segments: int = 12) -> dict:
    verts = []
    for i in range(segments):
        ang = 2 * math.pi * i / segments
        verts.append([radius * math.cos(ang), radius * math.sin(ang), -height / 2])
    for i in range(segments):
        ang = 2 * math.pi * i / segments
        verts.append([radius * math.cos(ang), radius * math.sin(ang), height / 2])
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append([i, j, segments + j])
        faces.append([i, segments + j, segments + i])
    return {"vertices": verts, "faces": faces}


PROTOTYPES = [
    ("chair", lambda r: _box(0.5 + r.uniform(-0.05, 0.05), 0.9, 0.5)),
    ("sofa", lambda r: _box(2.0 + r.uniform(-0.2, 0.2), 0.8, 0.9)),
    ("table", lambda r: _box(1.4, 0.75, 0.8 + r.uniform(-0.1, 0.1))),
    ("bed", lambda r: _box(2.0, 0.5, 1.6)),
    ("lamp", lambda r: _cylinder(0.15, 1.5 + r.uniform(-0.1, 0.1))),
    ("shelf", lambda r: _box(1.2, 1.8 + r.uniform(-0.1, 0.1), 0.3)),
]


def build_layouts(output_dir: Path = Path("datasets/layout3d"), n_per_class: int = 6) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(0)
    layouts = []
    for label, builder in PROTOTYPES:
        for _ in range(n_per_class):
            mesh = builder(rng)
            mesh["id"] = str(uuid.uuid4())
            mesh["label"] = label
            layouts.append(mesh)
    (output_dir / "meshes.json").write_text(json.dumps(layouts, indent=2))
    print(f"[build_3d] wrote {len(layouts)} meshes to {output_dir / 'meshes.json'}")


if __name__ == "__main__":
    build_layouts()
