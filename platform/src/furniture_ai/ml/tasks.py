"""Supervised losses for each trainable perception component."""

import hashlib

import numpy as np
import torch
from PIL import Image
from torch.nn import functional as F

from furniture_ai.ml.common import layout_inputs
from furniture_ai.ml.data import inside
from furniture_ai.ml.losses import depth_loss, layout_regularization, segmentation_loss
from furniture_ai.ml.networks import (
    CATEGORIES,
    FloorplanNet,
    LayoutTransformer,
    PairwiseRanker,
    multi_positive_siglip_loss,
    pairwise_loss,
)


def device_batch(batch, device):
    if isinstance(batch, torch.Tensor):
        return batch.to(device)
    if isinstance(batch, dict):
        return {k: device_batch(v, device) for k, v in batch.items()}
    if isinstance(batch, list):
        return [device_batch(v, device) for v in batch]
    return batch


class Task:
    def __init__(self, name, root, model_path=None):
        self.name, self.root, self.processor = name, root, None
        if name == "layout":
            self.model = LayoutTransformer()
        elif name == "ranker":
            self.model = PairwiseRanker()
        elif name == "floorplan":
            self.model = FloorplanNet()
        else:
            from transformers import (
                AutoImageProcessor,
                AutoModel,
                AutoModelForDepthEstimation,
                AutoModelForZeroShotObjectDetection,
                AutoProcessor,
                Sam2Model,
                Sam2Processor,
            )

            classes = {
                "siglip": (AutoModel, AutoProcessor),
                "dino": (AutoModelForZeroShotObjectDetection, AutoProcessor),
                "sam2": (Sam2Model, Sam2Processor),
                "depth": (AutoModelForDepthEstimation, AutoImageProcessor),
            }
            cls, proc = classes[name]
            if not model_path:
                raise ValueError(
                    "Foundation fine-tuning requires --model-path with locally installed pinned weights"
                )
            self.processor = proc.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
            self.model = cls.from_pretrained(
                model_path, local_files_only=True, trust_remote_code=False, use_safetensors=True
            )
            if name == "sam2":
                # Adapt the mask and prompt decoders; retain the pretrained image encoder.
                for parameter in self.model.vision_encoder.parameters():
                    parameter.requires_grad = False

    def image(self, row):
        with Image.open(inside(self.root, row["image_path"])) as image:
            return image.convert("RGB")

    def collate(self, rows):
        task = self.name
        if task == "ranker":
            winner = torch.tensor([r["winner"] for r in rows], dtype=torch.float32)
            loser = torch.tensor([r["loser"] for r in rows], dtype=torch.float32)
            if (
                winner.shape[1:] != (7,)
                or loser.shape != winner.shape
                or not torch.isfinite(winner).all()
                or not torch.isfinite(loser).all()
                or min(winner.min(), loser.min()) < 0
                or max(winner.max(), loser.max()) > 1
            ):
                raise ValueError("Ranking pairs must have seven finite 0–1 features")
            return {"winner": winner, "loser": loser}
        if task == "layout":
            inputs = [layout_inputs(r["geometry"], r["pieces"]) for r in rows]
            maximum = max(len(x[1]) for x in inputs)
            if maximum > 16:
                raise ValueError("Layout sequence too long")
            categories = torch.full((len(rows), maximum), len(CATEGORIES), dtype=torch.long)
            dims = torch.zeros(len(rows), maximum, 2)
            padding = torch.ones(len(rows), maximum, dtype=torch.bool)
            centers = torch.zeros(len(rows), maximum, 2)
            rotations = torch.zeros(len(rows), maximum, dtype=torch.long)
            for i, (r, (_, cats, dimensions, bounds)) in enumerate(zip(rows, inputs, strict=True)):
                n = len(cats)
                categories[i, :n], dims[i, :n], padding[i, :n] = cats, dimensions, False
                placements = {p["id"]: p for p in r["placements"]}
                minx, miny, width, depth = bounds
                for j, piece in enumerate(r["pieces"]):
                    p = placements[piece["id"]]
                    angle = p["rotation"]
                    if angle not in {0, 90}:
                        raise ValueError("Layout labels support 0°/90° rotations")
                    w, d = (
                        (piece["depth_m"], piece["width_m"])
                        if angle
                        else (piece["width_m"], piece["depth_m"])
                    )
                    centers[i, j] = torch.tensor(
                        [(p["x"] + w / 2 - minx) / width, (p["y"] + d / 2 - miny) / depth]
                    )
                    rotations[i, j] = int(angle == 90)
            return {
                "room": torch.stack([x[0] for x in inputs]),
                "categories": categories,
                "dimensions": dims,
                "padding_mask": padding,
                "centers": centers,
                "rotations": rotations,
            }
        images = [self.image(r) for r in rows]
        if task == "floorplan":
            pixels, rooms, icons = [], [], []
            for image, row in zip(images, rows, strict=True):
                with np.load(inside(self.root, row["labels_path"]), allow_pickle=False) as labels:
                    for name, count in [("rooms", 12), ("icons", 11)]:
                        value = labels[name]
                        if value.shape != (image.height, image.width) or np.any(
                            (value != 255) & ((value < 0) | (value >= count))
                        ):
                            raise ValueError("Invalid floorplan label shape/classes")
                    rooms.append(
                        torch.from_numpy(
                            np.asarray(
                                Image.fromarray(labels["rooms"].astype("uint8")).resize(
                                    (512, 512), Image.Resampling.NEAREST
                                )
                            ).copy()
                        ).long()
                    )
                    icons.append(
                        torch.from_numpy(
                            np.asarray(
                                Image.fromarray(labels["icons"].astype("uint8")).resize(
                                    (512, 512), Image.Resampling.NEAREST
                                )
                            ).copy()
                        ).long()
                    )
                pixels.append(
                    torch.from_numpy(np.asarray(image.resize((512, 512))).copy()).permute(2, 0, 1).float()
                    / 127.5
                    - 1
                )
            return {"pixels": torch.stack(pixels), "rooms": torch.stack(rooms), "icons": torch.stack(icons)}
        if task == "siglip":
            batch = dict(
                self.processor(
                    images=images,
                    text=[r["caption"] for r in rows],
                    padding="max_length",
                    truncation=True,
                    return_tensors="pt",
                )
            )
            batch["groups"] = torch.tensor(
                [
                    int(hashlib.sha256(str(r.get("product_id", r["id"])).encode()).hexdigest()[:15], 16)
                    for r in rows
                ],
                dtype=torch.long,
            )
            return batch
        if task == "sam2":
            boxes, masks = [], []
            for image, row in zip(images, rows, strict=True):
                with Image.open(inside(self.root, row["mask_path"])) as mask_image:
                    mask = np.asarray(mask_image.convert("L")) >= 128
                if mask.shape != (image.height, image.width) or not mask.any():
                    raise ValueError("SAM supervision requires a nonempty mask aligned with its image")
                ys, xs = np.where(mask)
                boxes.append([[int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]])
                masks.append(
                    torch.from_numpy(
                        np.asarray(
                            Image.fromarray(mask.astype("uint8") * 255).resize(
                                (256, 256), Image.Resampling.NEAREST
                            )
                        ).copy()
                    ).float()
                    / 255
                )
            batch = dict(self.processor(images=images, input_boxes=boxes, return_tensors="pt"))
            batch["targets"] = torch.stack(masks)
            return batch
        if task == "dino":
            prompts, annotations = [], []
            for image, row in zip(images, rows, strict=True):
                categories = row["categories"]
                if not categories or any("." in x or not x.strip() for x in categories):
                    raise ValueError("DINO categories must be nonempty labels without periods")
                prompts.append(". ".join(x.lower() for x in categories) + ".")
                objects = []
                for target in row["boxes"]:
                    x, y, w, h = target["xywh"]
                    label = target["category_id"]
                    if not (
                        0 <= x < x + w <= image.width
                        and 0 <= y < y + h <= image.height
                        and 0 <= label < len(categories)
                    ):
                        raise ValueError("DINO label box/category is outside bounds")
                    objects.append({"bbox": [x, y, w, h], "category_id": label, "area": w * h, "iscrowd": 0})
                annotations.append({"image_id": len(annotations), "annotations": objects})
            return dict(
                self.processor(
                    images=images, text=prompts, annotations=annotations, return_tensors="pt", padding=True
                )
            )
        if task == "depth":
            batch = dict(self.processor(images=images, return_tensors="pt"))
            targets = []
            for image, row in zip(images, rows, strict=True):
                depth = np.load(inside(self.root, row["depth_path"]), allow_pickle=False)
                if depth.shape != (image.height, image.width) or not np.isfinite(depth).all():
                    raise ValueError("Depth must be an aligned finite metric .npy array; 0 means invalid")
                target = torch.from_numpy(depth.astype("float32"))
                targets.append(F.interpolate(target[None, None], size=(512, 512), mode="nearest")[0, 0])
            batch["targets"] = torch.stack(targets)
            return batch
        raise ValueError("Unknown training task")

    def loss(self, model, batch):
        if self.name == "ranker":
            return pairwise_loss(model, batch["winner"], batch["loser"])
        if self.name == "layout":
            prediction = model(**{k: batch[k] for k in ["room", "categories", "dimensions", "padding_mask"]})
            valid = ~batch["padding_mask"]
            position = F.smooth_l1_loss(prediction["centers"][valid], batch["centers"][valid])
            rotation = F.cross_entropy(prediction["rotation_logits"][valid], batch["rotations"][valid])
            return (
                position
                + 0.2 * rotation
                + 0.1
                * layout_regularization(
                    prediction["centers"], prediction["rotation_logits"], batch["dimensions"], valid
                )
            )
        if self.name == "floorplan":
            logits = model(batch["pixels"])
            return segmentation_loss(logits[:, :12], batch["rooms"]) + segmentation_loss(
                logits[:, 12:], batch["icons"]
            )
        if self.name == "siglip":
            output = model(**{k: v for k, v in batch.items() if k != "groups"})
            return multi_positive_siglip_loss(output.logits_per_text, batch["groups"])
        if self.name == "sam2":
            output = model(**{k: v for k, v in batch.items() if k != "targets"}, multimask_output=False)
            logits = output.pred_masks[:, 0, 0]
            targets = F.interpolate(batch["targets"][:, None], size=logits.shape[-2:], mode="nearest")[:, 0]
            probabilities = logits.sigmoid()
            dice = 1 - (2 * (probabilities * targets).sum((-1, -2)) + 1) / (
                probabilities.sum((-1, -2)) + targets.sum((-1, -2)) + 1
            )
            return F.binary_cross_entropy_with_logits(logits, targets) + dice.mean()
        if self.name == "dino":
            return model(**batch).loss
        if self.name == "depth":
            prediction = model(**{k: v for k, v in batch.items() if k != "targets"}).predicted_depth
            prediction = F.interpolate(
                prediction[:, None], size=(512, 512), mode="bilinear", align_corners=False
            )[:, 0]
            losses = []
            for pred, metric in zip(prediction, batch["targets"], strict=True):
                losses.append(depth_loss(pred, metric))
            return torch.stack(losses).mean()
        raise ValueError("Unknown task")
