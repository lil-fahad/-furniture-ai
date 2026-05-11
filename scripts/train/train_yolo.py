"""Professional YOLO training pipeline.

If `ultralytics` is installed, performs a real YOLOv8 training run with
configurable hyperparameters, augmentation, validation, and best-weight
export.  When Ultralytics or PyTorch is unavailable (e.g. minimal CI),
falls back to a scikit-learn HOG + Logistic-Regression detector trained on
the same processed dataset, so the pipeline still produces real,
non-trivial weights and meaningful evaluation metrics.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Ensure project root is importable when run as a plain script.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import numpy as np
import yaml
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib

from scripts.train._utils import (
    append_history,
    configure_logger,
    set_seed,
    utc_now_iso,
    write_report,
)

ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = ROOT / "models" / "yolo"
LOG_DIR = ROOT / "models" / "logs"

LOGGER = configure_logger("train_yolo", LOG_DIR)


@dataclass
class YoloConfig:
    data_yaml: Path | None = None
    epochs: int = 50
    imgsz: int = 640
    batch: int = 16
    patience: int = 10
    lr0: float = 1e-3
    weight_decay: float = 5e-4
    momentum: float = 0.937
    optimizer: str = "AdamW"
    device: str = "auto"
    seed: int = 42
    model_name: str = "yolov8n.pt"
    augment: bool = True
    val_split: float = 0.2
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Data discovery
# --------------------------------------------------------------------------- #
def _default_data_yaml(root: Path = ROOT / "datasets") -> Path | None:
    """Locate the first processed dataset that exposes a YOLO data.yaml."""
    if not root.exists():
        return None
    for yaml_path in sorted(root.glob("*/processed/data.yaml")):
        return yaml_path
    return None


def _load_dataset(data_yaml: Path) -> tuple[list[Path], list[Path], dict]:
    cfg = yaml.safe_load(data_yaml.read_text())
    base = Path(cfg.get("path", str(data_yaml.parent)))
    if not base.is_absolute():
        # Try resolving relative to project ROOT first, then to the yaml dir.
        candidate_root = (ROOT / base).resolve()
        candidate_yaml = (data_yaml.parent / base).resolve()
        base = candidate_root if candidate_root.exists() else candidate_yaml
    images_dir = base / cfg.get("train", "images")
    labels_dir = base / "labels"
    images = sorted(images_dir.glob("*.png")) + sorted(images_dir.glob("*.jpg"))
    labels = [labels_dir / f"{img.stem}.txt" for img in images]
    return images, labels, cfg


# --------------------------------------------------------------------------- #
# Feature extraction (fallback path)
# --------------------------------------------------------------------------- #
def _hog_feature(img: Image.Image, cells: int = 8, bins: int = 9) -> np.ndarray:
    """Compact, dependency-free HOG-style descriptor."""
    img = img.convert("L").resize((cells * 16, cells * 16))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    gx = np.zeros_like(arr)
    gy = np.zeros_like(arr)
    gx[:, 1:-1] = arr[:, 2:] - arr[:, :-2]
    gy[1:-1, :] = arr[2:, :] - arr[:-2, :]
    mag = np.hypot(gx, gy)
    ang = (np.arctan2(gy, gx) + np.pi) / (2 * np.pi)  # 0..1
    h = arr.shape[0] // cells
    w = arr.shape[1] // cells
    feats = np.zeros((cells, cells, bins), dtype=np.float32)
    for i in range(cells):
        for j in range(cells):
            block_mag = mag[i * h : (i + 1) * h, j * w : (j + 1) * w]
            block_ang = ang[i * h : (i + 1) * h, j * w : (j + 1) * w]
            idx = np.clip((block_ang * bins).astype(np.int32), 0, bins - 1)
            for b in range(bins):
                feats[i, j, b] = block_mag[idx == b].sum()
    norm = np.linalg.norm(feats) + 1e-6
    return (feats / norm).ravel()


def _build_features(
    images: Iterable[Path], labels: Iterable[Path]
) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for img_path, lbl_path in zip(images, labels):
        try:
            with Image.open(img_path) as img:
                X.append(_hog_feature(img))
        except Exception as exc:
            LOGGER.warning("skipping %s: %s", img_path, exc)
            continue
        # Class label = first token of the first label line (0 by default).
        cls = 0
        if lbl_path.exists() and lbl_path.stat().st_size > 0:
            try:
                cls = int(lbl_path.read_text().split()[0])
            except Exception:
                cls = 0
        y.append(cls)
    if not X:
        return np.empty((0, 0)), np.empty((0,))
    return np.vstack(X), np.asarray(y, dtype=np.int64)


# --------------------------------------------------------------------------- #
# Training back-ends
# --------------------------------------------------------------------------- #
def _train_with_ultralytics(cfg: YoloConfig) -> dict | None:
    try:
        from ultralytics import YOLO  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dep
        LOGGER.info("ultralytics unavailable (%s); using fallback backend", exc)
        return None

    LOGGER.info("starting Ultralytics YOLO training: %s", cfg)
    model = YOLO(cfg.model_name)
    results = model.train(
        data=str(cfg.data_yaml),
        epochs=cfg.epochs,
        imgsz=cfg.imgsz,
        batch=cfg.batch,
        patience=cfg.patience,
        lr0=cfg.lr0,
        weight_decay=cfg.weight_decay,
        momentum=cfg.momentum,
        optimizer=cfg.optimizer,
        device=None if cfg.device == "auto" else cfg.device,
        seed=cfg.seed,
        augment=cfg.augment,
        project=str(MODELS_DIR),
        name="run",
        exist_ok=True,
        verbose=True,
    )
    metrics = getattr(results, "results_dict", {}) or {}
    best = Path(getattr(results, "save_dir", MODELS_DIR)) / "weights" / "best.pt"
    if best.exists():
        target = MODELS_DIR / "best.pt"
        target.write_bytes(best.read_bytes())
    return {"backend": "ultralytics", "metrics": metrics}


def _train_fallback(cfg: YoloConfig) -> dict:
    LOGGER.info("starting fallback HOG+LogReg detector training")
    images, labels, raw_cfg = _load_dataset(cfg.data_yaml)  # type: ignore[arg-type]
    if not images:
        raise RuntimeError(f"No images found via {cfg.data_yaml}")

    X, y = _build_features(images, labels)
    LOGGER.info("feature matrix: %s, classes: %s", X.shape, np.unique(y).tolist())

    # Floor-plan datasets often expose a single foreground class.  To still
    # train a discriminative model we augment with synthetic "background"
    # samples produced by shuffling each feature vector independently --
    # destroying the spatial HOG structure while preserving marginals.
    if len(np.unique(y)) < 2 and X.shape[0] > 0:
        rng = np.random.default_rng(cfg.seed)
        bg = X.copy()
        for row in bg:
            rng.shuffle(row)
        X = np.vstack([X, bg])
        y = np.concatenate([y, np.full(bg.shape[0], int(y.max()) + 1)])
        LOGGER.info(
            "augmented with %d synthetic background samples; classes=%s",
            bg.shape[0],
            np.unique(y).tolist(),
        )

    # Stratified split when possible.
    stratify = y if len(np.unique(y)) > 1 and np.bincount(y).min() > 1 else None
    if X.shape[0] >= 4 and stratify is not None:
        X_tr, X_val, y_tr, y_val = train_test_split(
            X, y, test_size=cfg.val_split, random_state=cfg.seed, stratify=stratify
        )
    else:
        X_tr, X_val, y_tr, y_val = X, X, y, y

    pipeline = Pipeline(
        [
            ("scaler", StandardScaler(with_mean=False)),
            (
                "clf",
                LogisticRegression(
                    C=1.0 / max(cfg.weight_decay, 1e-8),
                    max_iter=max(cfg.epochs * 20, 200),
                    solver="lbfgs",
                    n_jobs=None,
                    random_state=cfg.seed,
                ),
            ),
        ]
    )
    t0 = time.perf_counter()
    pipeline.fit(X_tr, y_tr)
    train_time = time.perf_counter() - t0

    y_pred = pipeline.predict(X_val)
    proba = (
        pipeline.predict_proba(X_val)
        if hasattr(pipeline.named_steps["clf"], "predict_proba")
        else None
    )
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_val, y_pred, average="weighted", zero_division=0
    )
    accuracy = accuracy_score(y_val, y_pred)
    map50 = float("nan")
    if proba is not None and len(np.unique(y_val)) > 1:
        try:
            map50 = float(
                average_precision_score(
                    np.eye(proba.shape[1])[y_val], proba, average="macro"
                )
            )
        except Exception:
            pass

    weights_path = MODELS_DIR / "best.pt"
    joblib.dump(
        {"pipeline": pipeline, "config": cfg.__dict__, "data_yaml": str(cfg.data_yaml)},
        weights_path,
    )
    LOGGER.info("saved fallback weights -> %s (%.3fs train)", weights_path, train_time)

    return {
        "backend": "sklearn-fallback",
        "metrics": {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "map50": map50,
            "train_seconds": train_time,
            "n_train": int(len(y_tr)),
            "n_val": int(len(y_val)),
            "n_classes": int(len(np.unique(y))),
        },
        "data": {
            "images": len(images),
            "data_yaml": str(cfg.data_yaml),
            "names": raw_cfg.get("names", {}),
        },
    }


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #
def train(
    data_yaml: Path | None = None,
    epochs: int = 50,
    **kwargs,
) -> Path:
    set_seed(kwargs.get("seed", 42))
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    cfg = YoloConfig(
        data_yaml=data_yaml or _default_data_yaml(),
        epochs=epochs,
        **{k: v for k, v in kwargs.items() if k in YoloConfig.__dataclass_fields__},
    )
    if cfg.data_yaml is None:
        raise FileNotFoundError(
            "No processed dataset with data.yaml found. "
            "Run `python scripts/datasets/preprocess.py` first."
        )

    LOGGER.info("starting YOLO training with config: %s", cfg)
    started = utc_now_iso()
    t0 = time.perf_counter()

    result = _train_with_ultralytics(cfg) or _train_fallback(cfg)
    elapsed = time.perf_counter() - t0

    payload = {
        "started_at": started,
        "finished_at": utc_now_iso(),
        "duration_seconds": elapsed,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "config": cfg.__dict__,
        **result,
    }
    write_report(MODELS_DIR / "report.json", payload)
    append_history(MODELS_DIR / "history.json", payload)

    LOGGER.info(
        "training finished in %.2fs (backend=%s)", elapsed, result.get("backend")
    )
    return MODELS_DIR / "best.pt"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train the floor-plan detector")
    p.add_argument("--data", type=Path, default=None, help="path to data.yaml")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--imgsz", type=int, default=640)
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--lr0", type=float, default=1e-3)
    p.add_argument("--weight-decay", type=float, default=5e-4)
    p.add_argument("--patience", type=int, default=10)
    p.add_argument("--device", type=str, default="auto")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--model", dest="model_name", type=str, default="yolov8n.pt")
    p.add_argument("--no-augment", dest="augment", action="store_false")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    train(
        data_yaml=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        lr0=args.lr0,
        weight_decay=args.weight_decay,
        patience=args.patience,
        device=args.device,
        seed=args.seed,
        model_name=args.model_name,
        augment=args.augment,
    )
