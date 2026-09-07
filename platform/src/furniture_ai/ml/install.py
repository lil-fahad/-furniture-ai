"""Download only pinned public model assets. No serving process downloads models implicitly."""

import argparse
import hashlib
import json
from pathlib import Path

from huggingface_hub import snapshot_download

GROUPS = {
    "perception": ["grounding_dino", "sam2", "depth_anything"],
    "generation": ["sdxl", "controlnet_canny", "controlnet_depth", "vae"],
    "scoring": ["siglip"],
    "evaluator": ["evaluator"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock", type=Path, default=Path("models.lock.json"))
    parser.add_argument("--output", type=Path, default=Path("data/models"))
    parser.add_argument("--group", choices=[*GROUPS, "all"], default="all")
    parser.add_argument(
        "--verify", action="store_true", help="Verify local SHA-256 inventory without downloading"
    )
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text())
    aliases = list(lock["models"]) if args.group == "all" else GROUPS[args.group]
    for alias in aliases:
        record = lock["models"][alias]
        if record.get("source") != "local" and len(record["revision"]) != 40:
            raise ValueError("Model revisions must be immutable commit SHAs")
        target = args.output / record.get("local_subdir", alias)
        inventory = target / "installed.json"
        if args.verify:
            installed = json.loads(inventory.read_text())
            if installed["revision"] != record["revision"]:
                raise ValueError(f"Wrong revision: {alias}")
            for relative, expected in installed["sha256"].items():
                with (target / relative).open("rb") as f:
                    if hashlib.file_digest(f, "sha256").hexdigest() != expected:
                        raise ValueError(f"Corrupt model artifact: {alias}/{relative}")
        else:
            if record.get("source") == "local":
                raise ValueError(
                    "Restore promoted local models from your private artifact store, then use --verify"
                )
            # Safetensors only; ignore legacy pickle and redundant ONNX/Flax weights.
            snapshot_download(
                repo_id=record["repo_id"],
                revision=record["revision"],
                local_dir=target,
                ignore_patterns=[
                    "*.bin",
                    "*.pt",
                    "*.pth",
                    "*.pkl",
                    "*.msgpack",
                    "*.onnx",
                    "*.tflite",
                    "*.h5",
                    "*.ot",
                    "*.ckpt",
                ],
            )
            hashes = {}
            for path in sorted(target.rglob("*")):
                if path.is_file() and ".cache" not in path.parts and path.name != "installed.json":
                    with path.open("rb") as f:
                        hashes[str(path.relative_to(target))] = hashlib.file_digest(f, "sha256").hexdigest()
            inventory.write_text(json.dumps({**record, "sha256": hashes}, indent=2) + "\n")
        print(json.dumps({"model": alias, "revision": record["revision"], "verified": args.verify}))


if __name__ == "__main__":
    main()
