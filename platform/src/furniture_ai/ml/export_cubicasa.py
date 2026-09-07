"""Research-only bridge to the official CubiCasa5K annotation loader; no LMDB/pickle input."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--code", type=Path, required=True)
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--list", required=True, help="Official train.txt, val.txt or test.txt inside the dataset")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--acknowledge-noncommercial", action="store_true", required=True)
    a = p.parse_args()
    dataset = a.dataset.resolve()
    from furniture_ai.ml.data import inside

    listing = inside(dataset, a.list)
    # Validate every official folder before invoking the third-party loader.
    for folder in listing.read_text().splitlines():
        if folder.strip():
            inside(dataset, folder.strip().lstrip("/") + "/model.svg")
            inside(dataset, folder.strip().lstrip("/") + "/F1_scaled.png")
    sys.path.insert(0, str(a.code.resolve()))
    from floortrans.loaders import FloorplanSVG

    source = FloorplanSVG(str(dataset) + "/", a.list, is_transform=False, format="txt")
    a.output.mkdir(parents=True, exist_ok=True)
    with (a.output / "manifest.jsonl").open("w") as manifest:
        for i in range(len(source)):
            item = source[i]
            image = item["image"].numpy().transpose(1, 2, 0).astype("uint8")
            labels = item["label"].numpy().astype("uint8")
            Image.fromarray(image).save(a.output / f"{i:06d}.png")
            np.savez_compressed(a.output / f"{i:06d}.npz", rooms=labels[0], icons=labels[1])
            record = {
                "id": f"cubicasa-{item['folder']}",
                "group_id": str(item["folder"]),
                "image_path": f"{i:06d}.png",
                "labels_path": f"{i:06d}.npz",
                "source": "https://github.com/CubiCasa/CubiCasa5k",
                "license": "CC-BY-NC-4.0",
                "training_use": True,
                "commercial_use": False,
                "consent": True,
            }
            manifest.write(json.dumps(record) + "\n")
    print(json.dumps({"records": len(source), "commercial_use": False}))


if __name__ == "__main__":
    main()
