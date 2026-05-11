"""Professional 3D layout trainer.

Learns a generative latent representation of furniture meshes:
1. Extract geometric descriptors (vertex stats, bbox, planarity, face areas).
2. Standardise + decorrelate with PCA.
3. Train a Gaussian Mixture Model to learn the latent layout distribution.
4. Train a Multi-Layer Perceptron regressor that maps latent codes back to
   normalised vertex positions, providing a deterministic decoder.

The bundled model exposes `sample()`, `encode()`, and `score()` and is
serialised with joblib.  Evaluation reports reconstruction RMSE,
GMM log-likelihood, BIC, and silhouette score over the latent codes.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import joblib
import numpy as np
from sklearn.decomposition import PCA
from sklearn.metrics import mean_squared_error, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from scripts.train._utils import (
    append_history,
    configure_logger,
    set_seed,
    utc_now_iso,
    write_report,
)

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models" / "layout3d"
LOG_DIR = ROOT / "models" / "logs"

LOGGER = configure_logger("train_3d", LOG_DIR)


@dataclass
class Layout3DConfig:
    meshes_path: Path = ROOT / "datasets" / "layout3d" / "meshes.json"
    latent_dim: int = 8
    n_components: int = 3
    mlp_hidden: tuple[int, ...] = (64, 64)
    mlp_max_iter: int = 500
    mlp_lr: float = 1e-3
    seed: int = 42
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def _triangle_areas(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    if faces.size == 0:
        return np.zeros(0)
    a = vertices[faces[:, 0]]
    b = vertices[faces[:, 1]]
    c = vertices[faces[:, 2]]
    return 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)


def _mesh_descriptor(mesh: dict, target_vertices: int) -> tuple[np.ndarray, np.ndarray]:
    verts = np.asarray(mesh.get("vertices", []), dtype=np.float64)
    faces = np.asarray(mesh.get("faces", []), dtype=np.int64)
    if verts.ndim != 2 or verts.shape[0] == 0:
        verts = np.zeros((1, 3))
    if verts.shape[1] == 2:
        verts = np.hstack([verts, np.zeros((verts.shape[0], 1))])

    centroid = verts.mean(axis=0)
    centered = verts - centroid
    extent = centered.max(axis=0) - centered.min(axis=0)
    cov = np.cov(centered.T) if centered.shape[0] > 1 else np.zeros((3, 3))
    eigvals = np.sort(np.linalg.eigvalsh(cov))[::-1]
    eigvals = np.pad(eigvals, (0, max(0, 3 - eigvals.size)))[:3]
    planarity = (eigvals[1] - eigvals[2]) / (eigvals[0] + 1e-9)
    linearity = (eigvals[0] - eigvals[1]) / (eigvals[0] + 1e-9)

    areas = _triangle_areas(verts, faces) if faces.size else np.zeros(1)
    descriptor = np.concatenate(
        [
            centroid,
            extent,
            eigvals,
            [planarity, linearity, float(verts.shape[0]), float(faces.shape[0])],
            [
                areas.sum(),
                areas.mean() if areas.size else 0.0,
                areas.std() if areas.size else 0.0,
            ],
        ]
    )

    # Build target = resampled, normalised vertex positions.
    if verts.shape[0] >= target_vertices:
        idx = np.linspace(0, verts.shape[0] - 1, target_vertices).astype(int)
        sampled = verts[idx]
    else:
        reps = int(np.ceil(target_vertices / verts.shape[0]))
        sampled = np.tile(verts, (reps, 1))[:target_vertices]
    scale = np.linalg.norm(sampled - centroid, axis=1).max() + 1e-9
    target = ((sampled - centroid) / scale).ravel()

    return descriptor.astype(np.float64), target.astype(np.float64)


# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #
def _load_meshes(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Meshes file not found at {path}. "
            "Run `python scripts/datasets/build_3d.py` first."
        )
    data = json.loads(path.read_text())
    if not isinstance(data, list) or not data:
        raise RuntimeError(f"{path} contains no meshes")
    return data


def train(meshes: Path | None = None, **kwargs) -> Path:
    set_seed(kwargs.get("seed", 42))
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    cfg = Layout3DConfig(
        meshes_path=meshes or Layout3DConfig.meshes_path,
        **{k: v for k, v in kwargs.items() if k in Layout3DConfig.__dataclass_fields__},
    )
    LOGGER.info("starting 3D layout training: %s", cfg)
    started = utc_now_iso()
    t0 = time.perf_counter()

    raw_meshes = _load_meshes(cfg.meshes_path)
    target_vertices = max(int(np.median([len(m.get("vertices", [])) for m in raw_meshes])), 4)
    LOGGER.info("loaded %d meshes, resampling to %d vertices", len(raw_meshes), target_vertices)

    descriptors, targets = [], []
    for m in raw_meshes:
        d, t = _mesh_descriptor(m, target_vertices)
        descriptors.append(d)
        targets.append(t)
    X = np.vstack(descriptors)
    Y = np.vstack(targets)

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    latent_dim = max(1, min(cfg.latent_dim, Xs.shape[0], Xs.shape[1]))
    pca = PCA(n_components=latent_dim, random_state=cfg.seed)
    Z = pca.fit_transform(Xs)
    LOGGER.info(
        "PCA: latent_dim=%d explained_variance=%.4f",
        latent_dim,
        float(pca.explained_variance_ratio_.sum()),
    )

    n_components = max(1, min(cfg.n_components, Xs.shape[0]))
    gmm = GaussianMixture(
        n_components=n_components,
        covariance_type="full" if Xs.shape[0] > latent_dim else "diag",
        reg_covar=1e-4,
        random_state=cfg.seed,
        max_iter=300,
    )
    gmm.fit(Z)
    log_lik = float(gmm.score(Z))
    bic = float(gmm.bic(Z))

    decoder = MLPRegressor(
        hidden_layer_sizes=cfg.mlp_hidden,
        learning_rate_init=cfg.mlp_lr,
        max_iter=cfg.mlp_max_iter,
        random_state=cfg.seed,
        early_stopping=False,
        solver="adam",
        activation="relu",
    )
    decoder.fit(Z, Y)
    Y_hat = decoder.predict(Z)
    rmse = float(np.sqrt(mean_squared_error(Y, Y_hat)))

    sil = float("nan")
    if n_components > 1 and len(Z) > n_components:
        try:
            labels = gmm.predict(Z)
            if len(np.unique(labels)) > 1:
                sil = float(silhouette_score(Z, labels))
        except Exception:
            pass

    elapsed = time.perf_counter() - t0
    metrics = {
        "reconstruction_rmse": rmse,
        "gmm_log_likelihood": log_lik,
        "gmm_bic": bic,
        "silhouette": sil,
        "explained_variance": float(pca.explained_variance_ratio_.sum()),
        "latent_dim": latent_dim,
        "n_components": n_components,
        "n_meshes": len(raw_meshes),
        "target_vertices": target_vertices,
        "train_seconds": elapsed,
    }
    LOGGER.info("training finished in %.3fs, metrics=%s", elapsed, metrics)

    bundle = {
        "version": 2,
        "config": cfg.__dict__,
        "scaler": scaler,
        "pca": pca,
        "gmm": gmm,
        "decoder": decoder,
        "target_vertices": target_vertices,
    }
    model_path = MODEL_DIR / "model.pt"
    joblib.dump(bundle, model_path, compress=3)
    LOGGER.info("saved 3D layout bundle -> %s", model_path)

    payload = {
        "started_at": started,
        "finished_at": utc_now_iso(),
        "duration_seconds": elapsed,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "config": cfg.__dict__,
        "metrics": metrics,
    }
    write_report(MODEL_DIR / "report.json", payload)
    append_history(MODEL_DIR / "history.json", payload)
    return model_path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train 3D layout model")
    p.add_argument("--meshes", type=Path, default=None)
    p.add_argument("--latent-dim", type=int, default=8)
    p.add_argument("--n-components", type=int, default=3)
    p.add_argument("--mlp-max-iter", type=int, default=500)
    p.add_argument("--mlp-lr", type=float, default=1e-3)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    train(
        meshes=args.meshes,
        latent_dim=args.latent_dim,
        n_components=args.n_components,
        mlp_max_iter=args.mlp_max_iter,
        mlp_lr=args.mlp_lr,
        seed=args.seed,
    )
