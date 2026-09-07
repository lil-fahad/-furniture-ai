"""Convert the verified ABO furniture package into identity-grouped SigLIP data."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from furniture_ai.ml.dataset_io import (
    digest,
    extract_member,
    grouped_splits,
    open_zip,
    proposed_split,
    write_json,
    write_jsonl,
)


def captions_for(products, languages):
    preferred = {"en": "en_US", "ar": "ar_AE", "zh": "zh_CN", "ko": "ko_KR"}
    options = defaultdict(set)
    for product in products:
        for item in product.get("item_name", []):
            language = item.get("language_tag", "und")
            text = " ".join(item.get("value", "").split())
            if text:
                options[language.split("_")[0]].add((language, text))
    selected = []
    for base in languages:
        if options.get(base):
            language, text = min(options[base], key=lambda x: (x[0] != preferred.get(base), x[0], x[1]))
            selected.append((language, text))
    if not selected and options:
        selected = [min(value for values in options.values() for value in values)]
    return selected


def prepare(path, output, languages=("en", "ar", "zh", "ko")):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    products = defaultdict(list)
    with open_zip(path) as archive:
        with archive.open("furniture_products.jsonl") as stream:
            for line in stream:
                item = json.loads(line)
                products[item["item_id"]].append(item)
        with archive.open("image_index.jsonl") as stream:
            index = {r["image_id"]: r for r in map(json.loads, stream)}
        verified, rows, counts = {}, [], Counter()
        for item_id, variants in sorted(products.items()):
            image_ids = set()
            for item in variants:
                if item.get("main_image_id"):
                    image_ids.add(item["main_image_id"])
                image_ids.update(item.get("other_image_id", []))
            captions = captions_for(variants, languages)
            for image_id in sorted(image_ids):
                if image_id not in index:
                    raise ValueError("ABO furniture image is missing from the verified index")
                image = index[image_id]
                if image_id not in verified:
                    destination = root / image["image_path"]
                    if not destination.exists():
                        destination = extract_member(archive, image["image_path"], root)
                    if digest(destination) != image["sha256"]:
                        raise ValueError("ABO image SHA-256 mismatch")
                    verified[image_id] = image["sha256"]
                for language, caption in captions:
                    rows.append(
                        {
                            "id": f"abo:{item_id}:{image_id}:{language}",
                            "group_id": f"abo-product:{item_id}",
                            "product_id": item_id,
                            "image_id": image_id,
                            "caption": caption,
                            "language": language,
                            "image_path": image["image_path"],
                            "sha256": image["sha256"],
                            "source": "https://amazon-berkeley-objects.s3.amazonaws.com/index.html",
                            "license": "CC-BY-4.0",
                            "training_use": True,
                            "commercial_use": True,
                            "consent": True,
                            "permission_basis": "ABO public CC BY 4.0 license; not a claim of subject consent",
                            "attribution": "Amazon.com and the Amazon Berkeley Objects authors",
                            "proposed_split": proposed_split(f"abo-product:{item_id}"),
                        }
                    )
                    counts[language] += 1
            if len(verified) and len(products) > 1000 and len(rows) % 5000 < 20:
                print(json.dumps({"verified_images": len(verified), "caption_pairs": len(rows)}), flush=True)
        (root / "LICENSE-CC-BY-4.0.txt").write_bytes(archive.read("LICENSE-CC-BY-4.0.txt"))
    splits = grouped_splits(rows)
    for split, records in splits.items():
        write_jsonl(root / f"{split}.jsonl", records)
    report = {
        "dataset": "ABO furniture SigLIP",
        "archive_sha256": digest(path),
        "license": "CC-BY-4.0",
        "images_verified": len(verified),
        "products": len(products),
        "caption_pairs": len(rows),
        "language_records": dict(counts),
        "splits": {k: len(v) for k, v in splits.items()},
        "split_policy": "All views/languages of a product and exact shared image bytes remain in one group",
        "image_maximum_side": 256,
        "image_bytes_changed": False,
        "near_duplicate_limit": "Identity and exact-byte duplicates are grouped; cross-product near-duplicate visual review remains separate",
        "ready_for_training": all(splits[k] for k in ("train", "validation", "test")),
    }
    report["ready_for_training"] = bool(report["ready_for_training"])
    write_json(root / "dataset-card.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.output), indent=2), flush=True)


if __name__ == "__main__":
    main()
