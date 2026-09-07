"""Provenance validation and deterministic group/duplicate-safe training splits."""

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            if line.strip():
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(f"Invalid JSON at line {number}") from error


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Dataset paths must identify files inside the dataset root")
    return path


class BKTree:
    """Hamming metric tree for small-distance perceptual duplicate candidate lookup."""

    def __init__(self):
        self.root = None

    def insert(self, value, index):
        if self.root is None:
            self.root = [value, index, {}]
            return
        node = self.root
        while True:
            distance = (value ^ node[0]).bit_count()
            if distance == 0:
                return
            if distance not in node[2]:
                node[2][distance] = [value, index, {}]
                return
            node = node[2][distance]

    def near(self, value, radius=3):
        stack = [self.root] if self.root else []
        result = []
        while stack:
            node = stack.pop()
            distance = (value ^ node[0]).bit_count()
            if distance <= radius:
                result.append(node[1])
            stack.extend(
                child for edge, child in node[2].items() if distance - radius <= edge <= distance + radius
            )
        return result


def prepare(manifest, root, output, seed=42, research=False):
    rows = list(read_jsonl(manifest))
    if not rows or len(rows) > 1_000_000:
        raise ValueError("Supply 1–1,000,000 records")
    parent = list(range(len(rows)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        parent[find(a)] = find(b)

    groups, hashes, ids, tree = {}, {}, set(), BKTree()
    licenses = Counter()
    for i, row in enumerate(rows):
        required = {"id", "group_id", "source", "license", "training_use", "commercial_use", "consent"}
        if not required <= row.keys() or any(
            not isinstance(row[x], str) or not row[x].strip() for x in ["id", "group_id", "source", "license"]
        ):
            raise ValueError(f"Record {i} lacks complete provenance")
        if row["id"] in ids:
            raise ValueError("Duplicate record ID")
        ids.add(row["id"])
        if row["training_use"] is not True or row["consent"] is not True:
            raise ValueError("Every record requires training rights and consent")
        if not research and row["commercial_use"] is not True:
            raise ValueError("Noncommercial record in a commercial dataset")
        if row["group_id"] in groups:
            union(i, groups[row["group_id"]])
        groups[row["group_id"]] = i
        licenses[row["license"]] += 1
        if row.get("image_path"):
            path = inside(root, row["image_path"])
            with path.open("rb") as f:
                sha = hashlib.file_digest(f, "sha256").hexdigest()
            if row.get("sha256") and row["sha256"] != sha:
                raise ValueError(f"Image digest mismatch in record {i}")
            row["sha256"] = sha
            if sha in hashes:
                union(i, hashes[sha])
            hashes[sha] = i
            with Image.open(path) as image:
                if image.width * image.height > 24_000_000:
                    raise ValueError("Dataset image exceeds pixel limit")
                gray = np.asarray(image.convert("L").resize((9, 8)))
                if gray.std() >= 3:
                    bits = gray[:, 1:] > gray[:, :-1]
                    dhash = sum(int(bit) << j for j, bit in enumerate(bits.flatten()))
                    for match in tree.near(dhash):
                        union(i, match)
                    tree.insert(dhash, i)
            for field in [
                "mask_path",
                "depth_path",
                "labels_path",
                "generated_image_path",
                "conditioning_image_path",
            ]:
                if row.get(field):
                    inside(root, row[field])
    connected = sorted({find(i) for i in range(len(rows))})
    if len(connected) < 3:
        raise ValueError("At least three independent scene/design groups are required after deduplication")
    random.Random(seed).shuffle(connected)
    ntest = max(1, round(len(connected) * 0.15))
    nval = max(1, round(len(connected) * 0.15))
    assignment = {
        k: "test" if n < ntest else "validation" if n < ntest + nval else "train"
        for n, k in enumerate(connected)
    }
    buckets = {"train": [], "validation": [], "test": []}
    for i, row in enumerate(rows):
        row["split_group"] = hashlib.sha256(str(find(i)).encode()).hexdigest()[:16]
        buckets[assignment[find(i)]].append(row)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for split, values in buckets.items():
        (output / f"{split}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in values)
        )
    sha = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()
    report = {
        "records": len(rows),
        "independent_groups": len(connected),
        "splits": {k: len(v) for k, v in buckets.items()},
        "source_manifest_sha256": sha,
        "licenses": dict(licenses),
        "commercial_use": not research,
        "seed": seed,
        "near_duplicate_method": "dHash Hamming distance <= 3; candidates grouped conservatively",
    }
    (output / "dataset-card.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("manifest", type=Path)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--research", action="store_true")
    a = p.parse_args()
    print(json.dumps(prepare(a.manifest, a.root, a.output, a.seed, a.research), indent=2))


if __name__ == "__main__":
    main()
