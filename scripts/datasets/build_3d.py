import json
from pathlib import Path
import uuid


def build_layouts(output_dir: Path = Path("datasets/layout3d")) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    layouts = []
    for _ in range(3):
        mesh = {
            "id": str(uuid.uuid4()),
            "vertices": [[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0]],
            "faces": [[0, 1, 2], [0, 2, 3]],
        }
        layouts.append(mesh)
    (output_dir / "meshes.json").write_text(json.dumps(layouts, indent=2))
    print(f"[build_3d] wrote {len(layouts)} meshes to {output_dir / 'meshes.json'}")


if __name__ == "__main__":
    build_layouts()
