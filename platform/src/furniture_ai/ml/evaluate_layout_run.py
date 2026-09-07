"""Compare an unchanged seed baseline and validation-selected layout weights on held-out rooms."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from accelerate.utils import set_seed
from shapely.geometry import box

from furniture_ai.errors import DomainError
from furniture_ai.layout import validate_layout
from furniture_ai.ml.common import layout_inputs, load_checkpoint
from furniture_ai.ml.data import read_jsonl
from furniture_ai.ml.dataset_io import digest, write_json
from furniture_ai.ml.tasks import Task, device_batch
from furniture_ai.ml.train import validate_splits
from furniture_ai.schemas import Geometry, Preferences


@torch.inference_mode()
def measure(task, rows, device):
    task.model.eval().to(device)
    errors, normalized, rotations, overlaps, losses = [], [], [], [], []
    failures = Counter()
    for row in rows:
        batch = device_batch(task.collate([row]), device)
        losses.append(float(task.loss(task.model, batch)))
        prediction = task.model(**{k: batch[k] for k in ("room", "categories", "dimensions", "padding_mask")})
        centers = prediction["centers"][0].cpu().numpy()
        truth = batch["centers"][0].cpu().numpy()
        angles = prediction["rotation_logits"][0].argmax(-1).cpu().numpy()
        rotation_truth = batch["rotations"][0].cpu().numpy()
        minx, miny, width, depth = layout_inputs(row["geometry"], row["pieces"])[-1]
        errors.extend(np.linalg.norm((centers - truth) * [width, depth], axis=1).tolist())
        normalized.extend(np.abs(centers - truth).mean(axis=1).tolist())
        rotations.extend((angles == rotation_truth).tolist())
        poses = []
        for index, piece in enumerate(row["pieces"]):
            w, d = (
                (piece["depth_m"], piece["width_m"])
                if angles[index]
                else (piece["width_m"], piece["depth_m"])
            )
            x, y = (
                minx + float(centers[index, 0]) * width - w / 2,
                miny + float(centers[index, 1]) * depth - d / 2,
            )
            poses.append(
                {**piece, "x": x, "y": y, "width_m": w, "depth_m": d, "rotation": int(angles[index]) * 90}
            )
            tw, td = (
                (piece["depth_m"], piece["width_m"])
                if rotation_truth[index]
                else (piece["width_m"], piece["depth_m"])
            )
            tx, ty = (
                minx + float(truth[index, 0]) * width - tw / 2,
                miny + float(truth[index, 1]) * depth - td / 2,
            )
            pred_box, target_box = box(x, y, x + w, y + d), box(tx, ty, tx + tw, ty + td)
            overlaps.append(pred_box.intersection(target_box).area / pred_box.union(target_box).area)
        try:
            validate_layout(
                Geometry.model_validate(row["geometry"]),
                poses,
                Preferences.model_validate(row["preferences"]),
            )
        except DomainError as error:
            failures[error.code] += 1
    if not errors or not np.isfinite(errors + losses).all():
        raise ValueError("Empty or nonfinite held-out predictions")
    return {
        "rooms": len(rows),
        "pieces": len(errors),
        "mean_room_loss": float(np.mean(losses)),
        "center_distance_mean_m": float(np.mean(errors)),
        "center_distance_median_m": float(np.median(errors)),
        "center_normalized_axis_mae": float(np.mean(normalized)),
        "rotation_accuracy": float(np.mean(rotations)),
        "footprint_iou": float(np.mean(overlaps)),
        "raw_layout_pass_rate": 1 - sum(failures.values()) / len(rows),
        "raw_layout_failure_counts": dict(failures),
    }


def evaluate_run(run_dir, data_root, device="cpu"):
    run_dir, data_root = Path(run_dir), Path(data_root)
    best = json.loads((run_dir / "best.json").read_text(encoding="utf-8"))
    epoch = best["epoch"]
    if type(epoch) is not int or not 1 <= epoch <= 10000:
        raise ValueError("Invalid best epoch")
    directory = run_dir / f"epoch-{epoch:04d}"
    state = json.loads((directory / "training-state.json").read_text(encoding="utf-8"))
    if state["task"] != "layout":
        raise ValueError("This evaluator requires a layout checkpoint")
    train_path, val_path, test_path = (
        data_root / f"{split}.jsonl" for split in ("train", "validation", "test")
    )
    dataset_sha = hashlib.sha256(train_path.read_bytes() + val_path.read_bytes()).hexdigest()
    if dataset_sha != state["dataset_sha256"]:
        raise ValueError("Training dataset differs from checkpoint provenance")
    train, validation, test = (list(read_jsonl(path)) for path in (train_path, val_path, test_path))
    validate_splits(train, validation)
    validate_splits(train + validation, test)
    if any(row.get("split") != "test" for row in test):
        raise ValueError("Evaluation requires an explicitly held-out test manifest")
    set_seed(state["config"]["seed"])
    task = Task("layout", data_root)
    baseline = measure(task, test, device)
    task.model, metadata = load_checkpoint(task.model, directory / "model", "layout")
    trained = measure(task, test, device)
    return {
        "task": "FurnitureLayoutTransformer",
        "device": device,
        "torch": torch.__version__,
        "selected_epoch": epoch,
        "selection": "Lowest validation mean batch loss; test not used for selection",
        "baseline": "Same architecture and original seed before any optimizer updates",
        "training_config": state["config"],
        "train_rooms": len(train),
        "validation_rooms": len(validation),
        "test_manifest_sha256": digest(test_path),
        "dataset_sha256": dataset_sha,
        "weights_sha256": metadata["sha256"],
        "commercial_use": metadata["commercial_use"],
        "initial": baseline,
        "trained": trained,
        "solver_applied": False,
        "production_approved": False,
        "limits": [
            "Reference-placement fidelity does not measure design preference",
            "Conservative SpatialLM subset; source licence remains CC BY-NC 4.0",
            "Geometric pass rate is measured on raw neural predictions before the application solver",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = evaluate_run(args.run_dir, args.data_root, args.device)
    write_json(args.output, report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
