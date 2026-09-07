# ruff: noqa: E402 -- ML tests skip before optional ML imports on API-only installations.
import json

import pytest

torch = pytest.importorskip("torch")

from furniture_ai.ml.common import load_checkpoint, save_checkpoint
from furniture_ai.ml.data import prepare
from furniture_ai.ml.evaluate import evaluate, gate
from furniture_ai.ml.losses import depth_loss, segmentation_loss
from furniture_ai.ml.metrics import relative_depth_error
from furniture_ai.ml.networks import PairwiseRanker, multi_positive_siglip_loss, pairwise_loss
from furniture_ai.ml.register import artifact_digest, promote
from furniture_ai.ml.tasks import Task

pytestmark = pytest.mark.ml


def test_pairwise_training_learns_preferences_and_serializes(tmp_path):
    torch.manual_seed(7)
    model = PairwiseRanker()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.02)
    winner, loser = torch.ones(12, 7), torch.zeros(12, 7)
    first = pairwise_loss(model, winner, loser).item()
    for _ in range(25):
        optimizer.zero_grad()
        loss = pairwise_loss(model, winner, loser)
        loss.backward()
        optimizer.step()
    assert loss.item() < first / 5
    save_checkpoint(model, tmp_path / "weights", "ranker", {"commercial_use": True})
    restored, _ = load_checkpoint(PairwiseRanker(), tmp_path / "weights", "ranker")
    torch.testing.assert_close(restored(winner), model(winner))
    with (tmp_path / "weights/model.safetensors").open("ab") as f:
        f.write(b"corruption")
    with pytest.raises(ValueError, match="digest"):
        load_checkpoint(PairwiseRanker(), tmp_path / "weights", "ranker")


def test_layout_training_has_finite_gradients(tmp_path, geometry):
    task = Task("layout", tmp_path)
    row = {
        "geometry": geometry,
        "pieces": [{"id": "sofa-1", "category": "sofa", "width_m": 2.2, "depth_m": 0.95}],
        "placements": [{"id": "sofa-1", "x": 0, "y": 0, "rotation": 0}],
    }
    loss = task.loss(task.model, task.collate([row]))
    loss.backward()
    assert torch.isfinite(loss) and torch.isfinite(task.model.head[-1].weight.grad).all()


def test_segmentation_ignores_unlabelled_pixels_and_depth_is_relative():
    logits = torch.randn(1, 3, 12, 12, requires_grad=True)
    labels = torch.zeros(1, 12, 12, dtype=torch.long)
    labels[:, :2] = 255
    segmentation_loss(logits, labels).backward()
    assert torch.count_nonzero(logits.grad[:, :, :2]) == 0
    metric = torch.linspace(1, 6, 400).reshape(20, 20)
    prediction = (3 / metric + 4).requires_grad_()
    loss = depth_loss(prediction, metric)
    loss.backward()
    assert loss < 1e-4 and torch.isfinite(prediction.grad).all()
    assert relative_depth_error(prediction.detach().numpy(), metric.numpy()) < 1e-5


def test_same_identity_images_are_not_false_negatives():
    groups = torch.tensor([1, 1, 2])
    logits = torch.tensor([[3.0, 3.0, -3.0], [3.0, 3.0, -3.0], [-3.0, -3.0, 3.0]], requires_grad=True)
    loss = multi_positive_siglip_loss(logits, groups)
    loss.backward()
    assert loss < 0.1 and logits.grad[0, 1] < 0 and logits.grad[0, 2] > 0


def test_provenance_and_duplicate_split_isolation(tmp_path, png):
    (tmp_path / "room.png").write_bytes(png)
    rows = [
        {
            "id": str(i),
            "group_id": str(i),
            "source": "test",
            "license": "test-permission",
            "training_use": True,
            "commercial_use": True,
            "consent": True,
        }
        for i in range(12)
    ]
    for r in rows[:2]:
        r["image_path"] = "room.png"
    source = tmp_path / "manifest.jsonl"
    source.write_text("".join(json.dumps(r) + "\n" for r in rows))
    report = prepare(source, tmp_path, tmp_path / "splits")
    assert report["independent_groups"] == 11
    locations = {}
    for split in ("train", "validation", "test"):
        for line in (tmp_path / f"splits/{split}.jsonl").read_text().splitlines():
            r = json.loads(line)
            locations[r["id"]] = split
    assert locations["0"] == locations["1"]
    rows[0]["consent"] = False
    source.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError, match="consent"):
        prepare(source, tmp_path, tmp_path / "invalid")


def test_evaluation_counts_gate_and_weight_binding(tmp_path):
    rows = [
        {
            "id": "test",
            "latency_seconds": 0.5,
            "detections": [{"category": "sofa", "box": [0, 0, 10, 10], "score": 0.9}],
            "target_detections": [{"category": "sofa", "box": [0, 0, 10, 10]}],
        }
    ]
    report = evaluate(rows, tmp_path)
    requirements = {
        "detection_ap50": {"min": 0.8, "min_samples": 1},
        "latency_p95_seconds": {"max": 1, "min_samples": 1},
    }
    assert gate(report, requirements)["passed"]
    assert not gate(report, {"missing": {"min": 0.5}})["passed"]
    model_path = tmp_path / "model"
    save_checkpoint(PairwiseRanker(), model_path, "ranker", {"commercial_use": True})
    report = {
        **gate(report, requirements),
        "artifact_sha256": artifact_digest(model_path),
        "requirements": requirements,
    }
    report_path, lock_path = tmp_path / "report.json", tmp_path / "lock.json"
    report_path.write_text(json.dumps(report))
    lock_path.write_text('{"models": {}}')
    release = promote(
        model_path, report_path, lock_path, tmp_path / "release.json", tmp_path / "installed", "ranker"
    )
    assert release["revision"] == report["artifact_sha256"]
    report["artifact_sha256"] = "wrong"
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="exact weights"):
        promote(
            model_path, report_path, lock_path, tmp_path / "release2.json", tmp_path / "installed", "ranker"
        )
