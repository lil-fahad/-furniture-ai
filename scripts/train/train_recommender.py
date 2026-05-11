"""Professional furniture recommender training.

Builds a hybrid content-based recommender that combines:
- TF-IDF over item text (name + category) for semantic similarity
- Standardised numerical features (price + price-bucket one-hot)
- Cosine kNN over the joint feature space
plus a lightweight popularity prior.

The trained artefact is a single joblib bundle that the API can load to
produce ranked recommendations and similar-item lookups.  Evaluation
uses a leave-one-out protocol with HitRate@K, MRR@K, and NDCG@K.
"""
from __future__ import annotations

import argparse
import csv
import math
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import KBinsDiscretizer, OneHotEncoder, StandardScaler
from scipy import sparse

from scripts.train._utils import (
    append_history,
    configure_logger,
    set_seed,
    utc_now_iso,
    write_report,
)

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models" / "recommender"
LOG_DIR = ROOT / "models" / "logs"

LOGGER = configure_logger("train_recommender", LOG_DIR)


@dataclass
class RecommenderConfig:
    catalog_path: Path = ROOT / "datasets" / "furniture.csv"
    top_k: int = 5
    text_max_features: int = 4096
    text_ngram: tuple[int, int] = (1, 2)
    price_buckets: int = 4
    text_weight: float = 0.7
    numeric_weight: float = 0.3
    seed: int = 42
    extra: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
def _load_catalog(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Catalog not found at {path}. "
            "Run `python scripts/datasets/build_furniture.py` first."
        )
    rows: list[dict] = []
    with path.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row["price"] = float(row.get("price", 0) or 0)
            except Exception:
                row["price"] = 0.0
            row["name"] = (row.get("name") or "").strip()
            row["category"] = (row.get("category") or "misc").strip().lower()
            rows.append(row)
    if not rows:
        raise RuntimeError(f"Catalog at {path} contains no rows")
    return rows


# --------------------------------------------------------------------------- #
# Feature extraction
# --------------------------------------------------------------------------- #
def _build_features(
    items: list[dict], cfg: RecommenderConfig
) -> tuple[sparse.csr_matrix, dict]:
    docs = [f"{it['name']} {it['category']}" for it in items]
    text_vec = TfidfVectorizer(
        max_features=cfg.text_max_features,
        ngram_range=cfg.text_ngram,
        lowercase=True,
        sublinear_tf=True,
    )
    text_X = text_vec.fit_transform(docs)

    prices = np.asarray([[it["price"]] for it in items], dtype=np.float64)
    scaler = StandardScaler()
    price_z = scaler.fit_transform(prices)

    n_unique_prices = int(np.unique(prices).shape[0])
    n_bins = max(2, min(cfg.price_buckets, n_unique_prices))
    if n_unique_prices >= 2:
        bucketer = KBinsDiscretizer(
            n_bins=n_bins, encode="onehot-dense", strategy="quantile"
        )
        price_buckets = bucketer.fit_transform(prices)
    else:
        bucketer = None
        price_buckets = np.zeros((len(items), 1))

    cat_enc = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    cat_X = cat_enc.fit_transform([[it["category"]] for it in items])

    numeric_X = np.hstack([price_z, price_buckets, cat_X])
    numeric_X *= cfg.numeric_weight

    text_X = text_X.multiply(cfg.text_weight).tocsr()
    feats = sparse.hstack([text_X, sparse.csr_matrix(numeric_X)]).tocsr()

    # L2-normalise rows so cosine == dot.
    norms = np.sqrt(np.asarray(feats.multiply(feats).sum(axis=1)).ravel())
    norms[norms == 0] = 1.0
    feats = sparse.diags(1.0 / norms) @ feats

    encoders = {
        "text_vectorizer": text_vec,
        "price_scaler": scaler,
        "price_bucketer": bucketer,
        "category_encoder": cat_enc,
    }
    return feats, encoders


# --------------------------------------------------------------------------- #
# Evaluation: leave-one-out HitRate / MRR / NDCG
# --------------------------------------------------------------------------- #
def _leave_one_out_eval(
    feats: sparse.csr_matrix, items: list[dict], k: int
) -> dict[str, float]:
    n = feats.shape[0]
    if n < 3:
        return {"HitRate@K": float("nan"), "MRR@K": float("nan"), "NDCG@K": float("nan")}

    cats = np.asarray([it["category"] for it in items])
    sims = (feats @ feats.T).toarray()
    np.fill_diagonal(sims, -np.inf)

    hits, mrr, ndcg = 0.0, 0.0, 0.0
    eligible = 0
    for i in range(n):
        same_cat_mask = cats == cats[i]
        same_cat_mask[i] = False
        if not same_cat_mask.any():
            continue
        eligible += 1
        topk = np.argsort(-sims[i])[:k]
        relevant = same_cat_mask[topk]
        if relevant.any():
            hits += 1.0
            rank = int(np.argmax(relevant)) + 1
            mrr += 1.0 / rank
            dcg = sum(int(r) / math.log2(idx + 2) for idx, r in enumerate(relevant))
            ideal = sum(1 / math.log2(idx + 2) for idx in range(min(k, int(same_cat_mask.sum()))))
            ndcg += dcg / ideal if ideal > 0 else 0.0
    if eligible == 0:
        return {"HitRate@K": 0.0, "MRR@K": 0.0, "NDCG@K": 0.0}
    return {
        "HitRate@K": hits / eligible,
        "MRR@K": mrr / eligible,
        "NDCG@K": ndcg / eligible,
        "evaluated": eligible,
    }


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #
def train(catalog_path: Path | None = None, **kwargs) -> Path:
    set_seed(kwargs.get("seed", 42))
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    cfg = RecommenderConfig(
        catalog_path=catalog_path or RecommenderConfig.catalog_path,
        **{k: v for k, v in kwargs.items() if k in RecommenderConfig.__dataclass_fields__},
    )
    LOGGER.info("starting recommender training: %s", cfg)
    started = utc_now_iso()
    t0 = time.perf_counter()

    items = _load_catalog(cfg.catalog_path)
    LOGGER.info("loaded %d catalog items", len(items))

    feats, encoders = _build_features(items, cfg)
    LOGGER.info(
        "feature matrix: shape=%s nnz=%d density=%.4f",
        feats.shape,
        feats.nnz,
        feats.nnz / max(feats.shape[0] * feats.shape[1], 1),
    )

    # Popularity prior (uniform fallback when no signal).
    prices = np.asarray([it["price"] for it in items], dtype=np.float64)
    pop = np.exp(-((prices - prices.mean()) ** 2) / (2 * (prices.std() + 1e-6) ** 2))
    pop = pop / pop.sum() if pop.sum() > 0 else np.full(len(items), 1.0 / len(items))

    n_neighbors = min(cfg.top_k + 1, len(items))
    knn = NearestNeighbors(n_neighbors=n_neighbors, metric="cosine", algorithm="brute")
    knn.fit(feats)

    metrics = _leave_one_out_eval(feats, items, k=cfg.top_k)
    elapsed = time.perf_counter() - t0
    LOGGER.info("training finished in %.3fs, metrics=%s", elapsed, metrics)

    bundle = {
        "version": 2,
        "config": cfg.__dict__,
        "items": items,
        "features": feats,
        "knn": knn,
        "encoders": encoders,
        "popularity": pop,
    }
    model_path = MODEL_DIR / "model.pt"
    joblib.dump(bundle, model_path, compress=3)
    LOGGER.info("saved recommender bundle -> %s", model_path)

    payload = {
        "started_at": started,
        "finished_at": utc_now_iso(),
        "duration_seconds": elapsed,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "config": cfg.__dict__,
        "n_items": len(items),
        "feature_dim": int(feats.shape[1]),
        "metrics": metrics,
        "avg_price": float(prices.mean()),
        "categories": sorted(set(it["category"] for it in items)),
    }
    write_report(MODEL_DIR / "report.json", payload)
    append_history(MODEL_DIR / "history.json", payload)
    return model_path


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train furniture recommender")
    p.add_argument("--catalog", type=Path, default=None)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--text-weight", type=float, default=0.7)
    p.add_argument("--numeric-weight", type=float, default=0.3)
    p.add_argument("--text-max-features", type=int, default=4096)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    train(
        catalog_path=args.catalog,
        top_k=args.top_k,
        text_weight=args.text_weight,
        numeric_weight=args.numeric_weight,
        text_max_features=args.text_max_features,
        seed=args.seed,
    )
