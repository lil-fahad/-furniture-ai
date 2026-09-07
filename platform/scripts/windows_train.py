"""Windows launcher: isolated install, real datasets, CUDA probe, resumable training."""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_ALIASES = {"dino": "grounding_dino", "sam2": "sam2", "siglip": "siglip"}


def run(arguments, *, env=None):
    print("Running:", subprocess.list2cmdline([str(x) for x in arguments]), flush=True)
    subprocess.run([str(x) for x in arguments], cwd=ROOT, env=env, check=True)


def locate_archive(explicit, filename, data_root):
    if explicit:
        candidate = Path(explicit).resolve()
        if not candidate.is_file():
            raise ValueError(f"Archive not found: {candidate}")
        return candidate
    for candidate in [data_root / "input" / filename, ROOT / filename, Path.home() / "Downloads" / filename]:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError(f"Put {filename} in {data_root / 'input'} or pass its archive argument.")


def cuda_channel(requested):
    if requested != "auto":
        return requested
    executable = shutil.which("nvidia-smi")
    if not executable:
        raise ValueError(
            "NVIDIA driver utility nvidia-smi was not found. Run --doctor-only and identify the GPU before installing CUDA packages."
        )
    result = subprocess.run(
        [executable, "--query-gpu=compute_cap", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    capabilities = [float(value.strip()) for value in result.stdout.splitlines() if value.strip()]
    if not capabilities:
        raise ValueError("NVIDIA did not report a usable GPU")
    return "cu128" if max(capabilities) >= 10 else "cu126"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=["dino", "sam2", "siglip", "layout"], default="dino")
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--abo-archive", type=Path)
    parser.add_argument("--spatiallm-archive", type=Path)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--cuda", choices=["auto", "cu126", "cu128"], default="auto")
    parser.add_argument("--doctor-only", action="store_true")
    parser.add_argument("--setup-only", action="store_true")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--run-dir", type=Path)
    args = parser.parse_args()
    if not 1 <= args.epochs <= 10000:
        parser.error("--epochs must be 1–10000")
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Use Python 3.12 (64-bit). The launcher does not replace your system Python.")
    if sys.platform != "win32" and not args.doctor_only:
        raise ValueError(
            "This launcher targets Windows. On Linux use the documented Python training commands."
        )
    data_root = args.data_root.resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    python = ROOT / ".venv-win" / "Scripts" / "python.exe"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "PYTHONUNBUFFERED": "1",
        "PYTHONUTF8": "1",
    }
    if args.doctor_only:
        selected_python = python if python.is_file() else Path(sys.executable)
        run(
            [selected_python, "-m", "furniture_ai.ml.gpu_doctor", "--output", data_root / "gpu-report.json"],
            env=env,
        )
        return
    if args.task == "layout" and not args.research:
        raise ValueError("SpatialLM-derived layout weights require --research and remain noncommercial.")
    if not args.skip_install:
        channel = cuda_channel(args.cuda)
        if not python.is_file():
            run([sys.executable, "-m", "venv", ROOT / ".venv-win"])
        run(
            [
                python,
                "-m",
                "pip",
                "install",
                "--require-hashes",
                "-r",
                ROOT / "requirements-windows-base.lock",
            ]
        )
        run(
            [
                python,
                "-m",
                "pip",
                "install",
                "torch==2.8.0",
                "torchvision==0.23.0",
                "--index-url",
                f"https://download.pytorch.org/whl/{channel}",
            ]
        )
        run([python, "-m", "pip", "install", "--require-hashes", "-r", ROOT / "requirements-windows-ml.lock"])
        run([python, "-m", "pip", "install", "--no-deps", "-e", ROOT])
    if not python.is_file():
        raise ValueError("Windows virtual environment missing; rerun without --skip-install")
    report_path = data_root / "gpu-report.json"
    run([python, "-m", "furniture_ai.ml.gpu_doctor", "--output", report_path], env=env)
    gpu = json.loads(report_path.read_text(encoding="utf-8"))
    if not gpu["kernel_check"] or not gpu["devices"]:
        raise ValueError("CUDA validation did not pass")
    if args.setup_only:
        return
    if args.task in {"dino", "sam2"}:
        archive = locate_archive(args.annotations, "annotations_trainval2017.zip", data_root)
        dataset_root = data_root / "coco"
        run(
            [
                python,
                "-m",
                "furniture_ai.ml.import_coco",
                "--annotations",
                archive,
                "--output",
                dataset_root,
                "--download",
            ],
            env=env,
        )
        split_root = dataset_root / args.task
    elif args.task == "siglip":
        archive = locate_archive(args.abo_archive, "FurnitureAI-ABO-furniture.zip", data_root)
        dataset_root = data_root / "abo"
        run(
            [python, "-m", "furniture_ai.ml.import_abo", "--archive", archive, "--output", dataset_root],
            env=env,
        )
        split_root = dataset_root
    else:
        archive = locate_archive(
            args.spatiallm_archive, "FurnitureAI-SpatialLM-layouts-research.zip", data_root
        )
        dataset_root = data_root / "spatiallm"
        run(
            [
                python,
                "-m",
                "furniture_ai.ml.import_spatiallm",
                "--archive",
                archive,
                "--output",
                dataset_root,
                "--research",
            ],
            env=env,
        )
        split_root = dataset_root
    card = json.loads((dataset_root / "dataset-card.json").read_text(encoding="utf-8"))
    if card.get("ready_for_training") is not True:
        raise ValueError("Dataset preparation did not pass")
    model_path = None
    if args.task in MODEL_ALIASES:
        alias = MODEL_ALIASES[args.task]
        model_root = data_root / "models"
        run([python, "-m", "furniture_ai.ml.install", "--model", alias, "--output", model_root], env=env)
        run(
            [python, "-m", "furniture_ai.ml.install", "--model", alias, "--output", model_root, "--verify"],
            env=env,
        )
        model_path = model_root / alias
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.run_dir.resolve() if args.run_dir else ROOT / "checkpoints" / f"{args.task}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    precision = "bf16" if gpu["devices"][0]["bf16_supported"] else "fp16"
    maximum_batch = {"layout": 32, "dino": 2, "sam2": 4, "siglip": 8}[args.task]
    config = None
    if args.resume:
        state = json.loads((args.resume / "training-state.json").read_text(encoding="utf-8"))
        config = state["config"]
        if state["task"] != args.task or config["world_size"] != 1:
            raise ValueError("Windows resume requires the same task and an original single-process run")
        precision = config["mixed_precision"]
        maximum_batch = config["batch_size"]
        args.epochs = config["epochs"]
    probe_path = run_dir / "gpu-preflight.json"
    command = [
        python,
        "-m",
        "furniture_ai.ml.gpu_preflight",
        "--task",
        args.task,
        "--manifest",
        split_root / "train.jsonl",
        "--root",
        dataset_root,
        "--maximum-batch",
        maximum_batch,
        "--mixed-precision",
        precision,
        "--output",
        probe_path,
    ]
    if model_path:
        command.extend(["--model-path", model_path])
    run(command, env=env)
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    batch_size, accumulation = probe["batch_size"], max(1, 16 // probe["batch_size"])
    learning_rate = {"layout": 0.0001, "dino": 0.00001, "sam2": 0.00001, "siglip": 0.000005}[args.task]
    if config:
        if config["batch_size"] > batch_size:
            raise ValueError("The original resume microbatch no longer fits; free GPU memory before resuming")
        batch_size, accumulation = config["batch_size"], config["gradient_accumulation"]
        precision, learning_rate = config["mixed_precision"], config["learning_rate"]
    command = [
        python,
        "-m",
        "furniture_ai.ml.train",
        "--task",
        args.task,
        "--train",
        split_root / "train.jsonl",
        "--validation",
        split_root / "validation.jsonl",
        "--root",
        dataset_root,
        "--output",
        run_dir,
        "--epochs",
        args.epochs,
        "--batch-size",
        batch_size,
        "--gradient-accumulation",
        accumulation,
        "--learning-rate",
        learning_rate,
        "--mixed-precision",
        precision,
        "--seed",
        config["seed"] if config else 42,
    ]
    if model_path:
        command.extend(["--model-path", model_path])
    if args.resume:
        command.extend(["--resume", args.resume.resolve()])
    (run_dir / "windows-run.json").write_text(
        json.dumps(
            {
                "command": [str(v) for v in command],
                "gpu": gpu,
                "probe": probe,
                "task": args.task,
                "research": args.research,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    run(command, env=env)
    print(f"Training completed. Weights and metrics: {run_dir}")
    print("Hold-out evaluation and release approval remain separate; this launcher does not deploy weights.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Windows training stopped: {error}", file=sys.stderr)
        sys.exit(1)
