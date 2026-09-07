"""Run actual local weights on a held-out manifest and emit evaluator-compatible predictions."""

import argparse
import json
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.nn import functional as F

from furniture_ai.errors import DomainError
from furniture_ai.layout import plan_layouts
from furniture_ai.ml.common import layout_inputs, load_checkpoint
from furniture_ai.ml.data import inside, read_jsonl
from furniture_ai.ml.tasks import Task, device_batch
from furniture_ai.schemas import Geometry, Preferences


@torch.inference_mode()
def predict(task, rows, root, output, device):
    output.mkdir(parents=True, exist_ok=False)
    model = task.model.eval().to(device)
    records, image_embeddings, text_embeddings = [], [], []
    for index, row in enumerate(rows):
        start = time.perf_counter()
        batch = device_batch(task.collate([row]), device)
        record = {"id": row["id"]}
        name = f"{index:07d}"
        if task.name == "ranker":
            record.update(
                preferred_score=model(batch["winner"]).item(), other_score=model(batch["loser"]).item()
            )
        elif task.name == "layout":
            prediction = model(**{k: batch[k] for k in ["room", "categories", "dimensions", "padding_mask"]})
            _, _, _, bounds = layout_inputs(row["geometry"], row["pieces"])
            minx, miny, width, depth = bounds
            targets = []
            for p, center, angle in zip(
                row["pieces"],
                prediction["centers"][0].cpu().tolist(),
                prediction["rotation_logits"][0].argmax(-1).cpu().tolist(),
                strict=True,
            ):
                w, d = (p["depth_m"], p["width_m"]) if angle else (p["width_m"], p["depth_m"])
                targets.append(
                    {
                        "id": p["id"],
                        "x": minx + center[0] * width - w / 2,
                        "y": miny + center[1] * depth - d / 2,
                        "rotation": angle * 90,
                    }
                )
            record.update(geometry=row["geometry"], preferences=row["preferences"])
            try:
                record["layout"] = plan_layouts(
                    Geometry.model_validate(row["geometry"]),
                    Preferences.model_validate(row["preferences"]),
                    targets,
                )[0]
            except DomainError:
                record["layout"] = {"pieces": []}
        else:
            image = task.image(row)
            if task.name == "floorplan":
                logits = model(batch["pixels"])
                rooms = F.interpolate(
                    logits[:, :12], size=(image.height, image.width), mode="bilinear", align_corners=False
                ).argmax(1)[0]
                np.save(output / f"{name}-room.npy", rooms.cpu().numpy())
                with np.load(inside(root, row["labels_path"]), allow_pickle=False) as labels:
                    np.save(output / f"{name}-room-target.npy", labels["rooms"])
                record.update(room_prediction=f"{name}-room.npy", room_target=f"{name}-room-target.npy")
            elif task.name == "depth":
                result = model(**{k: v for k, v in batch.items() if k != "targets"}).predicted_depth
                depth = F.interpolate(
                    result[:, None], size=(image.height, image.width), mode="bilinear", align_corners=False
                )[0, 0]
                np.save(output / f"{name}-depth.npy", depth.cpu().numpy())
                shutil.copyfile(inside(root, row["depth_path"]), output / f"{name}-depth-target.npy")
                record.update(depth_prediction=f"{name}-depth.npy", depth_target=f"{name}-depth-target.npy")
            elif task.name == "sam2":
                result = model(**{k: v for k, v in batch.items() if k != "targets"}, multimask_output=False)
                masks = task.processor.post_process_masks(
                    result.pred_masks.cpu(), batch["original_sizes"].cpu()
                )[0]
                Image.fromarray(masks[0, 0].numpy().astype("uint8") * 255).save(output / f"{name}-mask.png")
                with Image.open(inside(root, row["mask_path"])) as target:
                    target.convert("L").save(output / f"{name}-mask-target.png")
                record.update(mask_prediction=f"{name}-mask.png", mask_target=f"{name}-mask-target.png")
            elif task.name == "dino":
                result = model(**{k: v for k, v in batch.items() if k != "labels"})
                detected = task.processor.post_process_grounded_object_detection(
                    result,
                    batch["input_ids"],
                    threshold=0.05,
                    text_threshold=0.25,
                    target_sizes=[image.size[::-1]],
                )[0]
                record["detections"] = [
                    {"box": box.cpu().tolist(), "score": score.item(), "category": str(label)}
                    for box, score, label in zip(
                        detected["boxes"], detected["scores"], detected["text_labels"], strict=True
                    )
                ]
                record["target_detections"] = [
                    {
                        "box": [
                            b["xywh"][0],
                            b["xywh"][1],
                            b["xywh"][0] + b["xywh"][2],
                            b["xywh"][1] + b["xywh"][3],
                        ],
                        "category": row["categories"][b["category_id"]].lower(),
                    }
                    for b in row["boxes"]
                ]
            elif task.name == "siglip":
                result = model(**{k: v for k, v in batch.items() if k != "groups"})
                image_embeddings.append(F.normalize(result.image_embeds.float(), dim=-1).cpu())
                text_embeddings.append(F.normalize(result.text_embeds.float(), dim=-1).cpu())
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        record["latency_seconds"] = time.perf_counter() - start
        records.append(record)
    if task.name == "siglip":
        gallery = torch.cat(image_embeddings)
        identities = [r.get("product_id", r["id"]) for r in rows]
        for index, query in enumerate(text_embeddings):
            scores = query @ gallery.T
            ranking = scores[0].argsort(descending=True).tolist()
            records[index].update(
                ranked_ids=[identities[i] for i in ranking], relevant_ids=[identities[index]]
            )
    (output / "predictions.jsonl").write_text("".join(json.dumps(r, allow_nan=False) + "\n" for r in records))
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--task", choices=["dino", "sam2", "depth", "floorplan", "siglip", "layout", "ranker"], required=True
    )
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--model-path", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--device", default="cuda")
    a = p.parse_args()
    rows = list(read_jsonl(a.manifest))
    if not 1 <= len(rows) <= 10000:
        raise ValueError("Evaluate 1–10,000 held-out records per invocation")
    task = Task(a.task, a.root, a.model_path)
    if a.task in {"layout", "ranker", "floorplan"}:
        task.model, _ = load_checkpoint(task.model, a.model_path, a.task)
    predict(task, rows, a.root, a.output, a.device)
    print(json.dumps({"predictions": len(rows), "output": str(a.output)}))


if __name__ == "__main__":
    main()
