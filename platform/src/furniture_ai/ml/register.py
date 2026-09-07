"""Promote evaluated local weights into an immutable model directory and a new lock file."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def inventory(directory):
    directory = Path(directory)
    values = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Promotion requires materialized files, not symbolic links")
        if path.is_file() and ".cache" not in path.parts and path.name != "installed.json":
            if path.suffix in {".bin", ".pt", ".pth", ".pkl", ".ckpt"}:
                raise ValueError("Only safe serialized inference checkpoints may be promoted")
            with path.open("rb") as f:
                values[str(path.relative_to(directory))] = hashlib.file_digest(f, "sha256").hexdigest()
    if not values or not any(name.endswith(".safetensors") for name in values):
        raise ValueError("No safetensors weights in inference directory")
    return values


def artifact_digest(directory):
    return hashlib.sha256(json.dumps(inventory(directory), sort_keys=True).encode()).hexdigest()


def promote(source, report_path, lock_path, output_lock, models_dir, alias):
    report = json.loads(Path(report_path).read_text())
    digest = artifact_digest(source)
    if (
        report.get("passed") is not True
        or report.get("artifact_sha256") != digest
        or not report.get("requirements")
    ):
        raise ValueError("A passing evaluation bound to these exact weights and nonempty gates is required")
    metadata_path = Path(source) / "metadata.json"
    if not metadata_path.exists():
        metadata_path = Path(source).parent / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("commercial_use") is not True:
        raise ValueError("Promotion requires commercial training rights metadata")
    lock = json.loads(Path(lock_path).read_text())
    if alias not in {*lock["models"], "sdxl_lora", "layout", "ranker", "floorplan"}:
        raise ValueError("Unknown model alias")
    target = Path(models_dir) / f"{alias}__{digest[:16]}"
    if Path(output_lock).exists() or target.exists():
        raise ValueError("Release target already exists; choose a new release file")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".cache", "installed.json"))
    record = {
        "repo_id": f"local/{alias}",
        "revision": digest,
        "source": "local",
        "local_subdir": target.name,
        "license": metadata.get("license", "first-party-training-rights"),
        "evaluation_sha256": hashlib.sha256(Path(report_path).read_bytes()).hexdigest(),
    }
    (target / "installed.json").write_text(
        json.dumps({**record, "sha256": inventory(target)}, indent=2) + "\n"
    )
    lock["models"][alias] = record
    Path(output_lock).write_text(json.dumps(lock, indent=2) + "\n")
    return {"alias": alias, "revision": digest, "path": str(target)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument("--lock", type=Path, default=Path("models.lock.json"))
    p.add_argument("--output-lock", type=Path, required=True)
    p.add_argument("--models-dir", type=Path, default=Path("data/models"))
    p.add_argument("--alias", required=True)
    a = p.parse_args()
    print(json.dumps(promote(a.source, a.report, a.lock, a.output_lock, a.models_dir, a.alias)))


if __name__ == "__main__":
    main()
