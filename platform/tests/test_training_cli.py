# ruff: noqa: E402 -- Skip before optional training imports.
import json
import os
import subprocess
import sys

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("accelerate")
from safetensors.torch import load_file

pytestmark = pytest.mark.ml


def test_training_checkpoint_resume_and_heldout_prediction(tmp_path):
    for split, count in [("train", 12), ("validation", 4)]:
        rows = [
            {
                "id": f"{split}-{i}",
                "group_id": f"{split}-{i}",
                "split_group": f"{split}-{i}",
                "source": "synthetic-test-only",
                "license": "test-permission",
                "training_use": True,
                "commercial_use": True,
                "consent": True,
                "winner": [0.8] * 7,
                "loser": [0.2] * 7,
            }
            for i in range(count)
        ]
        (tmp_path / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    env = {**os.environ, "OMP_NUM_THREADS": "2", "ACCELERATE_USE_CPU": "true"}
    command = [
        sys.executable,
        "-m",
        "furniture_ai.ml.train",
        "--task",
        "ranker",
        "--train",
        str(tmp_path / "train.jsonl"),
        "--validation",
        str(tmp_path / "validation.jsonl"),
        "--root",
        str(tmp_path),
        "--epochs",
        "2",
        "--batch-size",
        "4",
        "--gradient-accumulation",
        "1",
        "--learning-rate",
        "0.01",
    ]

    def run(args):
        result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stdout + result.stderr

    run(command + ["--output", str(tmp_path / "original")])
    run(command + ["--output", str(tmp_path / "resumed"), "--resume", str(tmp_path / "original/epoch-0001")])
    a = load_file(tmp_path / "original/epoch-0002/model/model.safetensors")
    b = load_file(tmp_path / "resumed/epoch-0002/model/model.safetensors")
    for key in a:
        torch.testing.assert_close(a[key], b[key], rtol=0, atol=0)
    run(
        [
            sys.executable,
            "-m",
            "furniture_ai.ml.predict",
            "--task",
            "ranker",
            "--manifest",
            str(tmp_path / "validation.jsonl"),
            "--root",
            str(tmp_path),
            "--model-path",
            str(tmp_path / "original/epoch-0002/model"),
            "--output",
            str(tmp_path / "predictions"),
            "--device",
            "cpu",
        ]
    )
    predictions = [
        json.loads(x) for x in (tmp_path / "predictions/predictions.jsonl").read_text().splitlines()
    ]
    assert len(predictions) == 4 and all(x["preferred_score"] > x["other_score"] for x in predictions)
