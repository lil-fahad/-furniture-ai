import argparse
import hashlib
import json
import math
import os
import random
from pathlib import Path

import numpy as np
import torch
from accelerate import Accelerator
from accelerate.utils import set_seed
from torch.utils.data import DataLoader

from furniture_ai.ml.common import save_checkpoint
from furniture_ai.ml.data import read_jsonl
from furniture_ai.ml.networks import RANK_FEATURES
from furniture_ai.ml.tasks import Task, device_batch


def validate_splits(train, validation):
    if not train or not validation:
        raise ValueError("Training and validation sets must both be nonempty")
    for key in ["id", "group_id", "split_group", "sha256"]:
        a = {r[key] for r in train if r.get(key)}
        b = {r[key] for r in validation if r.get(key)}
        if a & b:
            raise ValueError(f"Training/validation leakage through {key}")
    for row in train + validation:
        if (
            row.get("training_use") is not True
            or row.get("consent") is not True
            or not row.get("split_group")
        ):
            raise ValueError("Use provenance-validated output from ml.data")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task", required=True, choices=["layout", "ranker", "floorplan", "siglip", "dino", "sam2", "depth"]
    )
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--mixed-precision", choices=["no", "fp16", "bf16"], default="no")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", type=Path, help="Trusted locally produced epoch directory")
    args = parser.parse_args()
    if not (1 <= args.epochs <= 10000 and 1 <= args.batch_size <= 256 and args.gradient_accumulation >= 1):
        raise ValueError("Training argument bounds invalid")
    if args.task == "siglip" and args.batch_size < 2:
        raise ValueError("SigLIP contrastive training needs batch size >= 2")
    train, validation = list(read_jsonl(args.train)), list(read_jsonl(args.validation))
    validate_splits(train, validation)
    accelerator = Accelerator(
        gradient_accumulation_steps=args.gradient_accumulation, mixed_precision=args.mixed_precision
    )
    set_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)
    task = Task(args.task, args.root, args.model_path)
    loader = DataLoader(
        train,
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=task.collate,
        num_workers=0,
        drop_last=args.task == "siglip",
    )
    val_loader = DataLoader(validation, batch_size=args.batch_size, collate_fn=task.collate, num_workers=0)
    if len(loader) == 0:
        raise ValueError("The training dataset is smaller than the configured contrastive batch")
    optimizer = torch.optim.AdamW(
        [p for p in task.model.parameters() if p.requires_grad], lr=args.learning_rate, weight_decay=0.01
    )
    model, optimizer, loader, val_loader = accelerator.prepare(task.model, optimizer, loader, val_loader)
    total_steps = args.epochs * math.ceil(len(loader) / args.gradient_accumulation)

    def schedule(step):
        warmup = max(1, int(total_steps * 0.05))
        if step < warmup:
            return max(0.01, (step + 1) / warmup)
        return max(
            0.05, 0.5 * (1 + math.cos(math.pi * min(1, (step - warmup) / max(1, total_steps - warmup))))
        )

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, schedule)
    accelerator.register_for_checkpointing(scheduler)
    start, best = 0, float("inf")
    dataset_sha = hashlib.sha256(args.train.read_bytes() + args.validation.read_bytes()).hexdigest()
    resume_config = {
        k: getattr(args, k)
        for k in ["epochs", "batch_size", "gradient_accumulation", "learning_rate", "mixed_precision", "seed"]
    }
    resume_config["world_size"] = accelerator.num_processes
    if args.resume:
        record = json.loads((args.resume / "training-state.json").read_text())
        if record["dataset_sha256"] != dataset_sha or record["task"] != args.task:
            raise ValueError("Resume checkpoint belongs to a different task/dataset")
        if record.get("config") != resume_config:
            raise ValueError("Exact resume requires the original training configuration and world size")
        accelerator.load_state(str(args.resume / "resume"))
        start, best = record["completed_epochs"], record["best_validation_loss"]
    args.output.mkdir(parents=True, exist_ok=True)
    for epoch in range(start, args.epochs):
        model.train()
        losses = []
        for batch in loader:
            with accelerator.accumulate(model):
                loss = task.loss(model, device_batch(batch, accelerator.device))
                if not torch.isfinite(loss):
                    raise FloatingPointError("Training loss became non-finite")
                accelerator.backward(loss)
                if accelerator.sync_gradients:
                    accelerator.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                if accelerator.sync_gradients:
                    scheduler.step()
                optimizer.zero_grad(set_to_none=True)
            losses.append(float(loss.detach()))
        model.eval()
        validation_losses = []
        with torch.no_grad():
            for batch in val_loader:
                with accelerator.autocast():
                    loss = task.loss(model, device_batch(batch, accelerator.device))
                validation_losses.extend(accelerator.gather(loss.detach().reshape(1)).cpu().tolist())
        value = float(np.mean(validation_losses))
        if not np.isfinite(value):
            raise FloatingPointError("Validation loss is non-finite")
        improved = value < best
        best = min(best, value)
        epoch_dir = args.output / f"epoch-{epoch + 1:04d}"
        if accelerator.is_main_process:
            epoch_dir.mkdir(parents=True, exist_ok=False)
        accelerator.wait_for_everyone()
        accelerator.save_state(str(epoch_dir / "resume"))
        if accelerator.is_main_process:
            raw = accelerator.unwrap_model(model)
            metadata = {
                "dataset_sha256": dataset_sha,
                "training_records": len(train),
                "validation_records": len(validation),
                "validation_mean_batch_loss": value,
                "epoch": epoch + 1,
                "seed": args.seed,
                "world_size": accelerator.num_processes,
                "commercial_use": all(r.get("commercial_use") is True for r in train + validation),
                "features": RANK_FEATURES if args.task == "ranker" else None,
                "base_model_path": str(args.model_path) if args.model_path else None,
            }
            if task.processor:
                raw.save_pretrained(epoch_dir / "model", safe_serialization=True)
                task.processor.save_pretrained(epoch_dir / "model")
                (epoch_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
            else:
                save_checkpoint(raw, epoch_dir / "model", args.task, metadata)
            state = {
                "completed_epochs": epoch + 1,
                "best_validation_loss": best,
                "dataset_sha256": dataset_sha,
                "task": args.task,
                "config": resume_config,
            }
            (epoch_dir / "training-state.json").write_text(json.dumps(state, indent=2) + "\n")
            record = {
                "epoch": epoch + 1,
                "train_loss": float(np.mean(losses)),
                "validation_mean_batch_loss": value,
            }
            with (args.output / "metrics.jsonl").open("a") as f:
                f.write(json.dumps(record) + "\n")
            if improved:
                temporary = args.output / "best.tmp"
                temporary.write_text(
                    json.dumps({"path": str((epoch_dir / "model").resolve()), **record}) + "\n"
                )
                os.replace(temporary, args.output / "best.json")
            print(json.dumps(record), flush=True)
        accelerator.wait_for_everyone()
    accelerator.end_training()


if __name__ == "__main__":
    main()
