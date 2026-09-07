import math

import numpy as np


def binary_mask_metrics(prediction, target):
    prediction, target = np.asarray(prediction, dtype=bool), np.asarray(target, dtype=bool)
    if prediction.shape != target.shape:
        raise ValueError("Mask shapes differ")
    intersection = np.logical_and(prediction, target).sum()
    union = np.logical_or(prediction, target).sum()
    total = prediction.sum() + target.sum()
    return {
        "iou": float(intersection / union) if union else 1.0,
        "dice": float(2 * intersection / total) if total else 1.0,
    }


def segmentation_miou(prediction, target, classes, ignore=255):
    if np.shape(prediction) != np.shape(target):
        raise ValueError("Segmentation shapes differ")
    p, t = np.asarray(prediction).ravel(), np.asarray(target).ravel()
    if p.shape != t.shape:
        raise ValueError("Segmentation shapes differ")
    valid = t != ignore
    if np.any((p[valid] < 0) | (p[valid] >= classes) | (t[valid] < 0) | (t[valid] >= classes)):
        raise ValueError("Class IDs out of range")
    confusion = np.bincount(
        classes * t[valid].astype(int) + p[valid].astype(int), minlength=classes * classes
    ).reshape(classes, classes)
    denominator = confusion.sum(0) + confusion.sum(1) - np.diag(confusion)
    iou = np.divide(np.diag(confusion), denominator, out=np.full(classes, np.nan), where=denominator != 0)
    if np.isnan(iou).all():
        raise ValueError("No evaluated classes")
    return float(np.nanmean(iou))


def relative_depth_error(prediction, target):
    p, t = np.asarray(prediction, dtype=float), np.asarray(target, dtype=float)
    if p.shape != t.shape:
        raise ValueError("Depth shapes differ")
    if np.any(~np.isfinite(p) & np.isfinite(t) & (t > 0)):
        raise ValueError("Non-finite prediction on evaluated depth pixels")
    valid = np.isfinite(t) & np.isfinite(p) & (t > 0)
    if valid.sum() < 10:
        raise ValueError("Insufficient valid depth pixels")
    p, t = p[valid], 1 / t[valid]
    design = np.stack([p, np.ones_like(p)], axis=1)
    coefficient = np.linalg.lstsq(design, t, rcond=None)[0]
    aligned = np.maximum(design @ coefficient, 1e-6)
    return float(np.mean(np.abs(aligned - t) / t))


def retrieval_metrics(ranked_ids, relevant_ids, k=10):
    if not relevant_ids:
        raise ValueError("At least one relevant item is required")
    ranking = list(dict.fromkeys(ranked_ids))[:k]
    relevant = set(relevant_ids)
    hits = [int(x in relevant) for x in ranking]
    dcg = sum(hit / math.log2(i + 2) for i, hit in enumerate(hits))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), k)))
    return {
        f"recall_at_{k}": len(set(ranking) & relevant) / len(relevant),
        f"ndcg_at_{k}": dcg / ideal,
        f"hit_rate_at_{k}": float(any(hits)),
    }


def box_iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = (
        max(0, a[2] - a[0]) * max(0, a[3] - a[1]) + max(0, b[2] - b[0]) * max(0, b[3] - b[1]) - intersection
    )
    return intersection / union if union > 0 else 0.0


def detection_ap50(predictions, truths):
    categories = sorted({x["category"] for x in truths})
    if not categories:
        raise ValueError("No ground truth detections")
    aps = []
    for category in categories:
        gt = [x for x in truths if x["category"] == category]
        pred = sorted([x for x in predictions if x["category"] == category], key=lambda x: -x["score"])
        matched, tp, fp = set(), [], []
        for p in pred:
            options = [
                (box_iou(p["box"], g["box"]), i)
                for i, g in enumerate(gt)
                if i not in matched and g["image_id"] == p["image_id"]
            ]
            overlap, index = max(options, default=(0, -1))
            if overlap >= 0.5:
                matched.add(index)
                tp.append(1)
                fp.append(0)
            else:
                tp.append(0)
                fp.append(1)
        tp, fp = np.cumsum(tp), np.cumsum(fp)
        precision = tp / np.maximum(tp + fp, 1)
        recall = tp / len(gt)
        aps.append(np.mean([np.max(precision[recall >= r], initial=0) for r in np.linspace(0, 1, 101)]))
    return float(np.mean(aps))
