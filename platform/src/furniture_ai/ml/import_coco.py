"""Import the user's COCO annotations and acquire licensed furniture images."""

import argparse
import hashlib
import json
import math
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from furniture_ai.ml.dataset_io import (
    digest,
    download_name,
    grouped_splits,
    open_zip,
    proposed_split,
    source_array,
    write_json,
    write_jsonl,
)

CLASSES = {62: "chair", 63: "sofa", 65: "bed", 67: "dining_table"}
LICENSES = {1: "CC-BY-NC-SA-2.0", 2: "CC-BY-NC-2.0", 4: "CC-BY-2.0"}
SOURCE = "https://cocodataset.org/#download"
# HTTPS path-style address of COCO's public S3 bucket; the legacy custom
# images.cocodataset.org endpoint does not reliably serve HTTPS.
IMAGE_BASE = "https://s3.amazonaws.com/images.cocodataset.org"


def inspect_annotations(path, research=False):
    allowed = {1, 2, 4} if research else {4}
    records, report = [], {"annotation_archive_sha256": digest(path), "splits": {}}
    with open_zip(path) as archive:
        for split in ("train2017", "val2017"):
            member = f"annotations/instances_{split}.json"
            licenses = {x["id"]: x for x in source_array(archive, member, "licenses")}
            categories = {x["id"]: x["name"] for x in source_array(archive, member, "categories")}
            if {k: categories.get(k) for k in CLASSES} != {
                62: "chair",
                63: "couch",
                65: "bed",
                67: "dining table",
            }:
                raise ValueError("COCO category IDs do not match the supported contract")
            images = {x["id"]: x for x in source_array(archive, member, "images")}
            annotations = defaultdict(list)
            counts, instances = Counter(), 0
            for ann in source_array(archive, member, "annotations"):
                instances += 1
                if ann["category_id"] not in CLASSES:
                    continue
                counts[CLASSES[ann["category_id"]]] += 1
                if ann["image_id"] not in images:
                    raise ValueError("Annotation refers to an unknown image")
                annotations[ann["image_id"]].append(ann)
            selected = [key for key in sorted(annotations) if images[key]["license"] in allowed]
            for key in selected:
                item = images[key]
                expected_slug = {1: "by-nc-sa", 2: "by-nc", 4: "by"}[item["license"]]
                actual_license_url = (
                    licenses[item["license"]]["url"].replace("http://", "https://").rstrip("/")
                )
                if actual_license_url != f"https://creativecommons.org/licenses/{expected_slug}/2.0":
                    raise ValueError("COCO numeric license ID disagrees with the source license URL")
                download_name(item["file_name"])
                if not 0 < item["width"] * item["height"] <= 24_000_000:
                    raise ValueError("COCO image exceeds pixel bounds")
                records.append(
                    {
                        "image": item,
                        "annotations": annotations[key],
                        "source_split": split,
                        "image_license": licenses[item["license"]],
                    }
                )
            report["splits"][split] = {
                "all_images": len(images),
                "all_instances": instances,
                "furniture_images_all_licenses": len(annotations),
                "furniture_instances": dict(counts),
                "selected_images": len(selected),
                "selected_instances": sum(len(annotations[key]) for key in selected),
                "furniture_images_by_license": dict(Counter(str(images[k]["license"]) for k in annotations)),
            }
    report.update(
        selected_license_ids=sorted(allowed),
        annotation_license="CC-BY-4.0",
        source=SOURCE,
        selection="Four project furniture classes; default image license CC BY 2.0 only",
        image_bytes_in_attachment=False,
    )
    return records, report


class DownloadBudget:
    def __init__(self, maximum):
        self.maximum, self.used, self.lock = maximum, 0, threading.Lock()

    def consume(self, count):
        with self.lock:
            self.used += count
            if self.used > self.maximum:
                raise ValueError("COCO download byte budget exceeded")


def fetch_image(row, root, budget):
    image = row["image"]
    relative = Path("images") / row["source_split"] / download_name(image["file_name"])
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("COCO cache path escaped dataset root")
    if row["source_split"] not in {"train2017", "val2017"}:
        raise ValueError("Unknown official COCO image split")
    url = f"{IMAGE_BASE}/{row['source_split']}/{image['file_name']}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(".jpg.part")
        for attempt in range(3):
            try:
                with urlopen(
                    Request(url, headers={"User-Agent": "FurnitureAI-Data/1.0"}), timeout=45
                ) as response:
                    size = 0
                    with temporary.open("wb") as stream:
                        while block := response.read(1024 * 1024):
                            size += len(block)
                            budget.consume(len(block))
                            if size > 20_000_000:
                                raise ValueError("COCO image exceeds byte bound")
                            stream.write(block)
                temporary.replace(path)
                break
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                if isinstance(error, HTTPError) and error.code in {401, 403, 404}:
                    raise
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
    with Image.open(path) as source:
        if source.size != (image["width"], image["height"]) or source.format != "JPEG":
            raise ValueError("Downloaded image does not match COCO dimensions/format")
        source.verify()
    return relative.as_posix(), digest(path), path.stat().st_size


def export_records(records, root):
    from pycocotools import mask as mask_utils

    detection, segmentation = [], []
    skipped = Counter()
    class_ids = list(CLASSES)
    for item in records:
        image, source_split = item["image"], item["source_split"]
        image_path, sha, _ = item["download"]
        provenance = {
            "id": f"coco-{image['id']}",
            "group_id": f"coco-image-{image['id']}",
            "source": SOURCE,
            "source_split": source_split,
            "license": LICENSES[image["license"]],
            "annotation_license": "CC-BY-4.0",
            "license_url": item["image_license"]["url"],
            "attribution_url": image.get("flickr_url"),
            "training_use": True,
            "commercial_use": image["license"] == 4,
            "consent": True,
            "permission_basis": "publisher-listed public image license; no subject consent asserted",
            "image_path": image_path,
            "sha256": sha,
            "proposed_split": "test"
            if source_split == "val2017"
            else proposed_split(f"coco-image-{image['id']}", validation_fraction=0.1, test_fraction=0),
        }
        boxes = []
        for ann in item["annotations"]:
            if ann.get("iscrowd", 0):
                skipped["crowd_annotation"] += 1
                continue
            x, y, width, height = ann["bbox"]
            if not all(math.isfinite(v) for v in (x, y, width, height)) or not (
                0 <= x < x + width <= image["width"] + 1e-5 and 0 <= y < y + height <= image["height"] + 1e-5
            ):
                raise ValueError(f"Invalid COCO bounding box {ann['id']}")
            # Tiny floating-point overshoot is clipped only at the source image edge.
            width, height = min(width, image["width"] - x), min(height, image["height"] - y)
            boxes.append({"xywh": [x, y, width, height], "category_id": class_ids.index(ann["category_id"])})
            source_mask = ann.get("segmentation")
            if not source_mask:
                skipped["missing_source_mask"] += 1
                continue
            if isinstance(source_mask, list):
                rles = mask_utils.frPyObjects(source_mask, image["height"], image["width"])
                encoded = mask_utils.merge(rles)
            else:
                if source_mask.get("size") != [image["height"], image["width"]]:
                    raise ValueError("COCO RLE size disagrees with source image dimensions")
                if isinstance(source_mask.get("counts"), list):
                    encoded = mask_utils.frPyObjects(source_mask, image["height"], image["width"])
                else:
                    encoded = source_mask
            mask = mask_utils.decode(encoded)
            if mask.shape != (image["height"], image["width"]) or not mask.any():
                skipped["empty_or_invalid_source_mask"] += 1
                continue
            relative = Path("masks") / source_split / f"{ann['id']}.png"
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(mask.astype(np.uint8) * 255).save(root / relative)
            segmentation.append(
                {
                    **provenance,
                    "id": f"coco-mask-{ann['id']}",
                    "mask_path": relative.as_posix(),
                    "source_annotation_id": ann["id"],
                    "category": CLASSES[ann["category_id"]],
                }
            )
        if boxes:
            detection.append(
                {**provenance, "categories": [v.replace("_", " ") for v in CLASSES.values()], "boxes": boxes}
            )
        else:
            skipped["image_without_noncrowd_boxes"] += 1
    # Split both tasks together so copies and all masks of an image stay aligned.
    buckets = grouped_splits(detection + segmentation)
    result = {}
    for task in ("dino", "sam2"):
        result[task] = {}
        for split, values in buckets.items():
            selected = [r for r in values if ("mask_path" in r) == (task == "sam2")]
            write_jsonl(root / task / f"{split}.jsonl", selected)
            result[task][split] = len(selected)
    return {"exported_records": result, "excluded": dict(skipped)}


def prepare(path, output, download=False, research=False, max_images=None, max_gb=5, workers=8):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    rows, report = inspect_annotations(path, research)
    configuration = {
        "source_sha256": report["annotation_archive_sha256"],
        "research": research,
        "max_images_per_split": max_images,
        "classes": CLASSES,
        "format": 1,
    }
    configuration = json.loads(json.dumps(configuration))
    config_path = root / "preparation-config.json"
    if config_path.exists() and json.loads(config_path.read_text(encoding="utf-8")) != configuration:
        raise ValueError("This output contains a different COCO selection; choose a new output directory")
    write_json(config_path, configuration)
    # Invalidate old readiness before a new attempt, including failed exports.
    write_json(root / "dataset-card.json", {"ready_for_training": False, "configuration": configuration})
    if max_images is not None:
        if max_images < 2:
            raise ValueError("Select at least two images per source split")
        rows = [
            r
            for split in ("train2017", "val2017")
            for r in sorted(
                (r for r in rows if r["source_split"] == split),
                key=lambda r: hashlib.sha256(str(r["image"]["id"]).encode()).hexdigest(),
            )[:max_images]
        ]
    report["selected_after_limit"] = len(rows)
    write_json(root / "annotation-audit.json", report)
    write_jsonl(root / "selected-source-records.jsonl", rows)
    if not download:
        report["ready_for_training"] = False
        return report
    budget = DownloadBudget(int(max_gb * 1e9))
    errors = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 12))) as pool:
        pending = {pool.submit(fetch_image, row, root, budget): row for row in rows}
        for number, future in enumerate(as_completed(pending), 1):
            row = pending[future]
            try:
                row["download"] = future.result()
            except Exception as error:
                errors.append({"image_id": row["image"]["id"], "error": str(error)})
            if number % 100 == 0 or number == len(rows):
                print(
                    json.dumps({"images_checked": number, "selected": len(rows), "errors": len(errors)}),
                    flush=True,
                )
    report.update(downloaded_bytes=budget.used, download_errors=errors, ready_for_training=not errors)
    write_json(root / "annotation-audit.json", report)
    if errors:
        raise ValueError("Some COCO images could not be verified; inspect annotation-audit.json and resume")
    report.update(export_records(rows, root))
    report["ready_for_training"] = all(
        report["exported_records"][task][split] > 0
        for task in ("dino", "sam2")
        for split in ("train", "validation", "test")
    )
    report["image_download_base"] = IMAGE_BASE
    report["holdout_policy"] = (
        "Official val2017 kept as test; 10% of train2017 image groups for validation; exact duplicates merged. Property identities unavailable."
    )
    write_json(root / "dataset-card.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--max-images", type=int, help="Deterministic cap per official source split")
    parser.add_argument("--max-gb", type=float, default=5)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if not math.isfinite(args.max_gb) or args.max_gb <= 0:
        parser.error("--max-gb must be positive and finite")
    print(
        json.dumps(
            prepare(
                args.annotations,
                args.output,
                args.download,
                args.research,
                args.max_images,
                args.max_gb,
                args.workers,
            ),
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
