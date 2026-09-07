"""Furniture AI Windows: validate, install, diagnose and train with persistent logs."""

import argparse
import datetime
import json
import os
import shutil
import signal
import struct
import subprocess
import sys
import uuid
from pathlib import Path

from windows_support import (
    ROOT,
    Runner,
    SessionLock,
    check_package,
    locate_archive,
    validate_archive,
    write_json,
)

MODEL_ALIASES = {"dino": "grounding_dino", "sam2": "sam2", "siglip": "siglip"}
ARCHIVES = {
    "dino": ("annotations", "annotations_trainval2017.zip"),
    "sam2": ("annotations", "annotations_trainval2017.zip"),
    "siglip": ("abo_archive", "FurnitureAI-ABO-furniture.zip"),
    "layout": ("spatiallm_archive", "FurnitureAI-SpatialLM-layouts-research.zip"),
}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=list(ARCHIVES), default="dino")
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--abo-archive", type=Path)
    parser.add_argument("--spatiallm-archive", type=Path)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data")
    parser.add_argument("--research", action="store_true")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--cuda", choices=["auto", "cu126", "cu128"], default="auto")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--doctor-only", action="store_true", help="Collect diagnostics without installing")
    actions.add_argument("--setup-only", action="store_true", help="Install dependencies and validate CUDA")
    actions.add_argument("--plan", action="store_true", help="Validate inputs without downloads or training")
    actions.add_argument("--check-package", action="store_true", help="Verify extracted application files")
    parser.add_argument("--skip-install", action="store_true")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--run-dir", type=Path)
    return parser


def make_plan(args, root=ROOT):
    if args.task == "layout" and not args.research:
        raise ValueError("SpatialLM layout training requires --research; its weights remain noncommercial.")
    key, filename = ARCHIVES[args.task]
    archive = locate_archive(getattr(args, key), filename, args.data_root.resolve(), root)
    validate_archive(archive, args.task)
    module = {"dino": "coco", "sam2": "coco", "siglip": "abo", "layout": "spatiallm"}[args.task]
    dataset_name = "coco-research" if module == "coco" and args.research else module
    dataset = args.data_root.resolve() / dataset_name
    split = dataset / args.task if args.task in {"dino", "sam2"} else dataset
    import_args = [
        "-m",
        f"furniture_ai.ml.import_{module}",
        "--annotations" if module == "coco" else "--archive",
        str(archive),
        "--output",
        str(dataset),
    ]
    if module == "coco":
        import_args.append("--download")
    if args.research and module in {"coco", "spatiallm"}:
        import_args.append("--research")
    if args.resume:
        args.resume = args.resume.expanduser().resolve()
        state = args.resume / "training-state.json"
        if not state.is_file():
            raise ValueError(f"Resume checkpoint is missing training-state.json: {args.resume}")
        saved = json.loads(state.read_text(encoding="utf-8"))
        if saved["task"] != args.task or saved["config"]["world_size"] != 1:
            raise ValueError("Resume requires the same task and an original single-process run")
        if args.run_dir is None:
            args.run_dir = args.resume.parent
    return {
        "task": args.task,
        "archive": str(archive),
        "dataset_root": str(dataset),
        "split_root": str(split),
        "import_arguments": import_args,
        "research": args.research,
    }


def cuda_channel(requested):
    if requested != "auto":
        return requested
    executable = shutil.which("nvidia-smi")
    if not executable:
        raise ValueError(
            "NVIDIA driver utility nvidia-smi was not found. Use Check GPU to inspect the computer."
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


def prepare_environment(args, runner, python):
    if args.skip_install:
        if not python.is_file():
            raise ValueError("Training environment is missing. Use Setup first or remove --skip-install.")
        return
    channel = cuda_channel(args.cuda)
    if not python.is_file():
        runner.run([sys.executable, "-m", "venv", ROOT / ".venv-win"], "Create Python environment")
    runner.run(
        [python, "-m", "pip", "install", "--require-hashes", "-r", ROOT / "requirements-windows-base.lock"],
        "Install application dependencies",
    )
    runner.run(
        [
            python,
            "-m",
            "pip",
            "install",
            "torch==2.8.0",
            "torchvision==0.23.0",
            "--index-url",
            f"https://download.pytorch.org/whl/{channel}",
        ],
        "Install CUDA PyTorch",
    )
    runner.run(
        [python, "-m", "pip", "install", "--require-hashes", "-r", ROOT / "requirements-windows-ml.lock"],
        "Install model dependencies",
    )
    runner.run([python, "-m", "pip", "install", "--no-deps", "-e", ROOT], "Install Furniture AI")
    runner.run([python, "-m", "pip", "check"], "Check dependency compatibility")


def execute_training(args, plan, runner, python, gpu):
    dataset, split = Path(plan["dataset_root"]), Path(plan["split_root"])
    runner.run([python, *plan["import_arguments"]], "Prepare dataset")
    card = json.loads((dataset / "dataset-card.json").read_text(encoding="utf-8"))
    if card.get("ready_for_training") is not True:
        raise ValueError("Dataset is incomplete. Read dataset-card.json and rerun to resume downloads.")
    model_path = None
    if args.task in MODEL_ALIASES:
        alias, model_root = MODEL_ALIASES[args.task], args.data_root.resolve() / "models"
        base = [python, "-m", "furniture_ai.ml.install", "--model", alias, "--output", model_root]
        runner.run(base, "Download pinned model")
        runner.run([*base, "--verify"], "Verify model files")
        model_path = model_root / alias
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = (
        args.run_dir.resolve()
        if args.run_dir
        else ROOT / "checkpoints" / f"{args.task}-{stamp}-{uuid.uuid4().hex[:6]}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    precision = "bf16" if gpu["devices"][0]["bf16_supported"] else "fp16"
    maximum_batch = {"layout": 32, "dino": 2, "sam2": 4, "siglip": 8}[args.task]
    config = None
    if args.resume:
        config = json.loads((args.resume / "training-state.json").read_text(encoding="utf-8"))["config"]
        precision, maximum_batch, args.epochs = (
            config["mixed_precision"],
            config["batch_size"],
            config["epochs"],
        )
    probe_path = run_dir / "gpu-preflight.json"
    command = [
        python,
        "-m",
        "furniture_ai.ml.gpu_preflight",
        "--task",
        args.task,
        "--manifest",
        split / "train.jsonl",
        "--root",
        dataset,
        "--maximum-batch",
        maximum_batch,
        "--mixed-precision",
        precision,
        "--output",
        probe_path,
    ]
    if model_path:
        command.extend(["--model-path", model_path])
    runner.run(command, "Measure GPU training memory")
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    batch_size, accumulation = probe["batch_size"], max(1, 16 // probe["batch_size"])
    rate = {"layout": 0.0001, "dino": 0.00001, "sam2": 0.00001, "siglip": 0.000005}[args.task]
    if config:
        if config["batch_size"] > batch_size:
            raise ValueError("Original resume microbatch no longer fits. Free GPU memory before resuming.")
        batch_size, accumulation = config["batch_size"], config["gradient_accumulation"]
        precision, rate = config["mixed_precision"], config["learning_rate"]
    command = [
        python,
        "-m",
        "furniture_ai.ml.train",
        "--task",
        args.task,
        "--train",
        split / "train.jsonl",
        "--validation",
        split / "validation.jsonl",
        "--root",
        dataset,
        "--output",
        run_dir,
        "--epochs",
        args.epochs,
        "--batch-size",
        batch_size,
        "--gradient-accumulation",
        accumulation,
        "--learning-rate",
        rate,
        "--mixed-precision",
        precision,
        "--seed",
        config["seed"] if config else 42,
    ]
    if model_path:
        command.extend(["--model-path", model_path])
    if args.resume:
        command.extend(["--resume", args.resume])
    write_json(
        run_dir / "windows-run.json",
        {
            "command": list(map(str, command)),
            "gpu": gpu,
            "probe": probe,
            "task": args.task,
            "research": args.research,
            "launcher_log": str(runner.log_path),
        },
    )
    runner.run(command, "Train model")
    print(f"Training completed. Weights and metrics: {run_dir}", flush=True)
    print("Compare held-out evaluation before promoting these weights.", flush=True)


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not 1 <= args.epochs <= 10000:
        parser.error("--epochs must be 1-10000")
    if args.check_package:
        print(json.dumps(check_package()))
        return 0
    plan = None
    if not args.doctor_only and not args.setup_only:
        plan = make_plan(args)
    if args.plan:
        print(json.dumps(plan))
        return 0
    check_package()
    if sys.version_info[:2] != (3, 12) or struct.calcsize("P") != 8:
        raise ValueError("Python 3.12 64-bit is required. Open INSTALL-PYTHON.cmd, then START-WINDOWS.cmd.")
    if sys.platform != "win32" and not args.doctor_only:
        raise ValueError("This installer targets Windows. Use the documented Python commands on Linux.")
    python = ROOT / ".venv-win" / "Scripts" / "python.exe"
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "TOKENIZERS_PARALLELISM": "false",
        "PYTHONUNBUFFERED": "1",
        "PYTHONUTF8": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }
    with SessionLock(ROOT / "logs" / "operation.lock"):
        runner = Runner(ROOT, env)
        try:
            report = args.data_root.resolve() / "gpu-report.json"
            if args.doctor_only:
                selected = python if python.is_file() else Path(sys.executable)
                code = runner.run(
                    [selected, "-m", "furniture_ai.ml.gpu_doctor", "--output", report],
                    "Check GPU",
                    acceptable=(0, 2),
                )
                runner.finish("completed" if code == 0 else "needs_setup")
                print(f"GPU report: {report}", flush=True)
                if code == 2:
                    print("Diagnostics saved. CUDA is not ready; use Setup and check the report.", flush=True)
                return code
            prepare_environment(args, runner, python)
            runner.run(
                [python, "-m", "furniture_ai.ml.gpu_doctor", "--output", report], "Validate CUDA kernels"
            )
            gpu = json.loads(report.read_text(encoding="utf-8"))
            if not gpu.get("kernel_check") or not gpu.get("devices"):
                raise ValueError("CUDA validation did not pass. See gpu-report.json.")
            if not args.setup_only:
                execute_training(args, plan, runner, python, gpu)
            runner.finish("completed")
            print(f"Operation completed. Log: {runner.log_path}", flush=True)
            return 0
        except KeyboardInterrupt:
            runner.finish("cancelled", "Stopped by user")
            print("Stopped. Completed checkpoints and downloads are preserved.", flush=True)
            return 130
        except Exception as error:
            runner.finish("failed", str(error))
            raise


def interrupted(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, interrupted)
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"Furniture AI stopped: {error}", file=sys.stderr)
        sys.exit(1)
