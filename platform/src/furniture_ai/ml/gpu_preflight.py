"""Measure an actual training step before launching a Windows GPU job."""

import argparse
import gc
import itertools
import json
from pathlib import Path

import torch

from furniture_ai.ml.data import read_jsonl
from furniture_ai.ml.dataset_io import write_json
from furniture_ai.ml.tasks import Task, device_batch


def probe(task_name, manifest, root, model_path, maximum_batch, mixed_precision):
    if not torch.cuda.is_available():
        raise RuntimeError("GPU preflight requires a CUDA device; it does not silently switch to CPU")
    minimum = 2 if task_name == "siglip" else 1
    rows = list(itertools.islice(read_jsonl(manifest), maximum_batch))
    size = min(maximum_batch, len(rows))
    trials = []
    while size >= minimum:
        task = optimizer = batch = loss = None
        try:
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
            task = Task(task_name, root, model_path)
            task.model.to("cuda").train()
            optimizer = torch.optim.AdamW([p for p in task.model.parameters() if p.requires_grad], lr=1e-5)
            batch = device_batch(task.collate(rows[:size]), "cuda")
            dtype = torch.bfloat16 if mixed_precision == "bf16" else torch.float16
            with torch.autocast("cuda", dtype=dtype, enabled=mixed_precision != "no"):
                loss = task.loss(task.model, batch)
            if not torch.isfinite(loss):
                raise FloatingPointError("Preflight loss is nonfinite")
            scaler = torch.amp.GradScaler("cuda", enabled=mixed_precision == "fp16")
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            torch.cuda.synchronize()
            peak = torch.cuda.max_memory_reserved()
            trials.append({"batch_size": size, "peak_reserved_bytes": peak, "status": "passed"})
            return {
                "task": task_name,
                "batch_size": size,
                "mixed_precision": mixed_precision,
                "trials": trials,
                "probe_updates_discarded": True,
            }
        except torch.cuda.OutOfMemoryError:
            trials.append({"batch_size": size, "status": "out_of_memory"})
            size //= 2
        finally:
            del task, optimizer, batch, loss
            gc.collect()
            torch.cuda.empty_cache()
    raise RuntimeError(f"No supported microbatch fits this GPU. Trials: {trials}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=["dino", "sam2", "siglip", "layout"], required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--maximum-batch", type=int, default=4)
    parser.add_argument("--mixed-precision", choices=["no", "fp16", "bf16"], default="fp16")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.maximum_batch <= 64:
        parser.error("Batch size must be 1–64")
    report = probe(
        args.task, args.manifest, args.root, args.model_path, args.maximum_batch, args.mixed_precision
    )
    write_json(args.output, report)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
