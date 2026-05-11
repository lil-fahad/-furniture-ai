"""Scheduled training orchestrator.

Runs the YOLO, recommender and 3D layout trainers with their professional
configuration, captures their exit status, and writes a timestamped
checkpoint plus a roll-up report aggregating every trainer's metrics.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models"
CHECKPOINT_DIR = MODELS_DIR / "checkpoints"
CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

PYTHON = sys.executable or "python3"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")


def run(cmd: list[str]) -> int:
    print(f"[auto:train] running {' '.join(cmd)}", flush=True)
    return subprocess.call(cmd, cwd=ROOT)


def checkpoint(name: str, metadata: dict | None = None) -> Path:
    stamp = _utc_stamp()
    dest = CHECKPOINT_DIR / f"{name}-{stamp}.json"
    payload = {"name": name, "timestamp": stamp, **(metadata or {})}
    dest.write_text(json.dumps(payload, indent=2))
    print(f"[auto:train] wrote checkpoint {dest}", flush=True)
    return dest


def _load_report(report_path: Path) -> dict:
    if not report_path.exists():
        return {}
    try:
        return json.loads(report_path.read_text())
    except Exception:
        return {}


def train_recommender_daily() -> dict:
    code = run([PYTHON, "scripts/train/train_recommender.py"])
    report = _load_report(MODELS_DIR / "recommender" / "report.json")
    checkpoint("recommender", {"exit": code, "metrics": report.get("metrics")})
    return {"exit": code, "report": report}


def train_yolo_weekly() -> dict:
    code = run([PYTHON, "scripts/train/train_yolo.py", "--epochs", "50"])
    report = _load_report(MODELS_DIR / "yolo" / "report.json")
    checkpoint("yolo", {"exit": code, "metrics": report.get("metrics")})
    return {"exit": code, "report": report}


def train_layout3d() -> dict:
    code = run([PYTHON, "scripts/train/train_3d.py"])
    report = _load_report(MODELS_DIR / "layout3d" / "report.json")
    checkpoint("layout3d", {"exit": code, "metrics": report.get("metrics")})
    return {"exit": code, "report": report}


def main() -> int:
    started = _utc_stamp()
    t0 = time.perf_counter()
    summary = {
        "started_at": started,
        "recommender": train_recommender_daily(),
        "yolo": train_yolo_weekly(),
        "layout3d": train_layout3d(),
    }
    summary["duration_seconds"] = time.perf_counter() - t0
    summary["finished_at"] = _utc_stamp()

    summary_path = MODELS_DIR / "training_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"[auto:train] wrote summary {summary_path}", flush=True)

    failures = [k for k in ("recommender", "yolo", "layout3d") if summary[k]["exit"] != 0]
    if failures:
        print(f"[auto:train] failures: {failures}", flush=True)
        return 1
    print("[auto:train] all trainers succeeded", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
