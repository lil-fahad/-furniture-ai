"""Prepare an ImageFolder from a rights-checked split for the vendored SDXL trainers."""

import argparse
import json
import shutil
from pathlib import Path

from furniture_ai.ml.data import inside, read_jsonl


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--research", action="store_true")
    p.add_argument("--controlnet", action="store_true", help="Write embedded image-pair Parquet shards")
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    rows = list(read_jsonl(a.manifest))
    if a.controlnet:
        from datasets import Dataset, Features, Value
        from datasets import Image as DatasetImage

        features = Features(
            {"image": DatasetImage(), "conditioning_image": DatasetImage(), "text": Value("string")}
        )
        for start in range(0, len(rows), 64):
            shard = []
            for row in rows[start : start + 64]:
                if (
                    row.get("training_use") is not True
                    or row.get("consent") is not True
                    or not row.get("split_group")
                ):
                    raise ValueError("Use an approved prepared data split")
                if not a.research and row.get("commercial_use") is not True:
                    raise ValueError("Noncommercial training record")
                values = {"text": row["caption"]}
                for key, field in [
                    ("image", "image_path"),
                    ("conditioning_image", "conditioning_image_path"),
                ]:
                    path = inside(a.root, row[field])
                    values[key] = {"path": path.name, "bytes": path.read_bytes()}
                shard.append(values)
            Dataset.from_list(shard, features=features).to_parquet(
                a.output / f"train-{start // 64:05d}.parquet"
            )
        print(json.dumps({"records": len(rows), "format": "embedded-image-parquet"}))
        return
    with (a.output / "metadata.jsonl").open("w") as out:
        for i, row in enumerate(rows):
            if (
                not row.get("split_group")
                or row.get("training_use") is not True
                or row.get("consent") is not True
            ):
                raise ValueError("Use an approved prepared data split")
            if not a.research and row.get("commercial_use") is not True:
                raise ValueError("Noncommercial training record")
            if not row.get("caption"):
                raise ValueError("Every diffusion training image requires a caption")
            source = inside(a.root, row["image_path"])
            name = f"{i:07d}{source.suffix.lower()}"
            shutil.copyfile(source, a.output / name)
            out.write(json.dumps({"file_name": name, "text": row["caption"]}) + "\n")
    print(json.dumps({"records": len(rows), "output": str(a.output)}))


if __name__ == "__main__":
    main()
