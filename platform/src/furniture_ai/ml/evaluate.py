"""Score held-out annotations and fail closed when a required release metric is missing."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from furniture_ai.layout import validate_layout
from furniture_ai.ml.data import inside, read_jsonl
from furniture_ai.ml.metrics import (
    binary_mask_metrics,
    detection_ap50,
    relative_depth_error,
    retrieval_metrics,
    segmentation_miou,
)
from furniture_ai.schemas import Geometry, Preferences, RoomAnalysis, VisualEvaluation


def evaluate(rows, root):
    scores, detections, labels = {}, [], []
    detection_samples = 0

    def add(name, value):
        if not np.isfinite(value):
            raise ValueError("Non-finite evaluation value")
        scores.setdefault(name, []).append(float(value))

    for row in rows:
        if "evaluation_prediction" in row:
            try:
                predicted = VisualEvaluation.model_validate(row["evaluation_prediction"])
                reference = VisualEvaluation.model_validate(row["evaluation_target"])
                add("vlm_schema_valid_rate", 1)
                add(
                    "evaluator_mae",
                    np.mean(
                        [
                            abs(getattr(predicted, k) - getattr(reference, k))
                            for k in [
                                "style_alignment",
                                "visual_quality",
                                "requirement_match",
                                "structural_consistency",
                            ]
                        ]
                    ),
                )
            except ValueError:
                add("vlm_schema_valid_rate", 0)
        if "analysis_prediction" in row:
            try:
                analysis = RoomAnalysis.model_validate(row["analysis_prediction"])
                add("vlm_schema_valid_rate", 1)
                # The reference label is annotated independently, never taken from the prediction.
                if row["dimension_labels_present"] is False:
                    add(
                        "unsupported_dimension_rate",
                        float(
                            analysis.suggested_width_m is not None or analysis.suggested_length_m is not None
                        ),
                    )
            except ValueError:
                add("vlm_schema_valid_rate", 0)
        if "render_path" in row:
            original = np.asarray(Image.open(inside(root, row["original_path"])).convert("RGB"))
            generated = np.asarray(Image.open(inside(root, row["render_path"])).convert("RGB"))
            mask = np.asarray(Image.open(inside(root, row["edit_mask_path"])).convert("L")) >= 128
            if original.shape != generated.shape or mask.shape != original.shape[:2] or mask.all():
                raise ValueError("Pixel preservation requires aligned images and some unedited pixels")
            add("unedited_pixel_mae", np.abs(original.astype(float) - generated)[~mask].mean())
        if "human_prefers_candidate" in row:
            if type(row["human_prefers_candidate"]) is not bool:
                raise ValueError("Human preference must be an independently recorded boolean vote")
            add("human_preference_win_rate", float(row["human_prefers_candidate"]))
        if "mask_prediction" in row:
            pred = np.asarray(Image.open(inside(root, row["mask_prediction"])).convert("L")) > 127
            target = np.asarray(Image.open(inside(root, row["mask_target"])).convert("L")) > 127
            for key, value in binary_mask_metrics(pred, target).items():
                add("mask_" + key, value)
        if "depth_prediction" in row:
            add(
                "depth_si_absrel",
                relative_depth_error(
                    np.load(inside(root, row["depth_prediction"]), allow_pickle=False),
                    np.load(inside(root, row["depth_target"]), allow_pickle=False),
                ),
            )
        if "room_prediction" in row:
            add(
                "floorplan_room_miou",
                segmentation_miou(
                    np.load(inside(root, row["room_prediction"]), allow_pickle=False),
                    np.load(inside(root, row["room_target"]), allow_pickle=False),
                    12,
                ),
            )
        if "ranked_ids" in row:
            for key, value in retrieval_metrics(row["ranked_ids"], row["relevant_ids"], 10).items():
                add("retrieval_" + key, value)
        if "preferred_score" in row:
            add("ranking_pair_accuracy", float(row["preferred_score"] > row["other_score"]))
        if "layout" in row:
            try:
                validate_layout(
                    Geometry.model_validate(row["geometry"]),
                    row["layout"]["pieces"],
                    Preferences.model_validate(row["preferences"]),
                )
                passed = 1
            except ValueError:
                passed = 0
            except Exception as e:
                from furniture_ai.errors import DomainError

                if not isinstance(e, DomainError):
                    raise
                passed = 0
            add("hard_layout_pass_rate", passed)
        if "detections" in row:
            detection_samples += 1
            detections.extend({**x, "image_id": row["id"]} for x in row["detections"])
            labels.extend({**x, "image_id": row["id"]} for x in row["target_detections"])
        if "latency_seconds" in row:
            add("latency_seconds", row["latency_seconds"])
    metrics = {name: float(np.mean(values)) for name, values in scores.items()}
    if labels:
        metrics["detection_ap50"] = detection_ap50(detections, labels)
    if "latency_seconds" in scores:
        metrics["latency_p95_seconds"] = float(np.percentile(scores["latency_seconds"], 95))
    samples = {k: len(v) for k, v in scores.items()}
    samples["detection_ap50"] = detection_samples
    samples["latency_p95_seconds"] = len(scores.get("latency_seconds", []))
    return {"metrics": metrics, "samples": samples}


def gate(report, requirements):
    failures = []
    for name, rule in requirements.items():
        value = report["metrics"].get(name)
        if value is None or not np.isfinite(value):
            failures.append(f"Missing required metric: {name}")
        elif ("min" in rule and value < rule["min"]) or ("max" in rule and value > rule["max"]):
            failures.append(f"Metric threshold failed: {name}")
        if rule.get("min_samples", 0) > report.get("samples", {}).get(name, 0):
            failures.append(f"Insufficient held-out samples: {name}")
    return {**report, "passed": not failures, "failures": failures}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--predictions", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--gates", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, help="Bind this report to exact inference weights for promotion")
    a = p.parse_args()
    requirements = json.loads(a.gates.read_text())
    if not requirements:
        raise ValueError("At least one evaluation gate is required")
    report = gate(evaluate(list(read_jsonl(a.predictions)), a.root), requirements)
    report["requirements"] = requirements
    report["predictions_sha256"] = __import__("hashlib").sha256(a.predictions.read_bytes()).hexdigest()
    if a.model_dir:
        from furniture_ai.ml.register import artifact_digest

        report["artifact_sha256"] = artifact_digest(a.model_dir)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
