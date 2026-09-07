"""Record provenance beside inference weights exported by the unchanged upstream SDXL trainers."""

import argparse
import hashlib
import json
from pathlib import Path

from furniture_ai.ml.data import read_jsonl
from furniture_ai.ml.train import validate_splits


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train", type=Path, required=True)
    p.add_argument("--validation", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--kind", choices=["sdxl_lora", "controlnet_canny", "controlnet_depth"], required=True)
    a = p.parse_args()
    train, validation = list(read_jsonl(a.train)), list(read_jsonl(a.validation))
    validate_splits(train, validation)
    if not list(a.model_dir.glob("*.safetensors")):
        raise ValueError("Supply the exported inference checkpoint directory")
    metadata = {
        "kind": a.kind,
        "dataset_sha256": hashlib.sha256(a.train.read_bytes() + a.validation.read_bytes()).hexdigest(),
        "commercial_use": all(r.get("commercial_use") is True for r in train + validation),
        "training_records": len(train),
        "validation_records": len(validation),
        "license": "openrail++",
    }
    (a.model_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
