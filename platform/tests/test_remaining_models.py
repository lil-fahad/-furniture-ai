# ruff: noqa: E402 -- Optional model dependencies are checked first.
"""Executable loss/gradient contracts for matching, depth and floor-plan training."""

import numpy as np
import pytest
from PIL import Image

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")
from transformers import (
    BertTokenizerFast,
    DepthAnythingConfig,
    DepthAnythingForDepthEstimation,
    Dinov2Config,
    DPTImageProcessor,
    SiglipConfig,
    SiglipImageProcessor,
    SiglipModel,
    SiglipProcessor,
    SiglipTextConfig,
    SiglipVisionConfig,
)

from furniture_ai.ml.tasks import Task

pytestmark = pytest.mark.ml


def test_siglip_fixed_resolution_multi_positive_training(tmp_path):
    # Google's selected SigLIP 2 fixed-resolution checkpoint uses the SiglipModel architecture.
    torch.set_num_threads(2)
    directory = tmp_path / "model"
    directory.mkdir()
    (directory / "vocab.txt").write_text("[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\nchair\ntable\n")
    tokenizer = BertTokenizerFast(
        vocab_file=str(directory / "vocab.txt"),
        model_max_length=16,
        model_input_names=["input_ids", "attention_mask"],
    )
    config = SiglipConfig(
        text_config=SiglipTextConfig(
            vocab_size=7,
            hidden_size=32,
            intermediate_size=64,
            num_hidden_layers=1,
            num_attention_heads=4,
            max_position_embeddings=16,
            pad_token_id=0,
            bos_token_id=2,
            eos_token_id=3,
        ).to_dict(),
        vision_config=SiglipVisionConfig(
            hidden_size=32,
            intermediate_size=64,
            num_hidden_layers=1,
            num_attention_heads=4,
            image_size=64,
            patch_size=16,
        ).to_dict(),
    )
    SiglipModel(config).save_pretrained(directory)
    SiglipProcessor(SiglipImageProcessor(size={"height": 64, "width": 64}), tokenizer).save_pretrained(
        directory
    )
    Image.new("RGB", (80, 64), "navy").save(tmp_path / "chair.jpg")
    Image.new("RGB", (80, 64), "brown").save(tmp_path / "table.jpg")
    task = Task("siglip", tmp_path, directory)
    rows = [
        {"id": "a-en", "product_id": "a", "caption": "chair", "image_path": "chair.jpg"},
        {"id": "a-other", "product_id": "a", "caption": "chair", "image_path": "chair.jpg"},
        {"id": "b-en", "product_id": "b", "caption": "table", "image_path": "table.jpg"},
    ]
    batch = task.collate(rows)
    assert batch["groups"][0] == batch["groups"][1] != batch["groups"][2]
    loss = task.loss(task.model, batch)
    loss.backward()
    assert torch.isfinite(loss)
    assert task.model.text_model.embeddings.token_embedding.weight.grad.abs().sum() > 0
    assert task.model.vision_model.embeddings.patch_embedding.weight.grad.abs().sum() > 0


def test_depth_anything_real_model_backward(tmp_path):
    torch.set_num_threads(2)
    config = DepthAnythingConfig(
        backbone_config=Dinov2Config(
            hidden_size=32,
            num_hidden_layers=4,
            num_attention_heads=4,
            image_size=56,
            patch_size=14,
            out_indices=[1, 2, 3, 4],
            reshape_hidden_states=False,
        ),
        reassemble_hidden_size=32,
        neck_hidden_sizes=[8, 16, 32, 64],
        fusion_hidden_size=16,
        head_hidden_size=8,
    )
    directory = tmp_path / "model"
    DepthAnythingForDepthEstimation(config).save_pretrained(directory)
    DPTImageProcessor(size={"height": 56, "width": 56}, ensure_multiple_of=14).save_pretrained(directory)
    Image.new("RGB", (64, 48), "beige").save(tmp_path / "image.jpg")
    depth = np.linspace(1, 4, 48 * 64, dtype=np.float32).reshape(48, 64)
    np.save(tmp_path / "depth.npy", depth)
    task = Task("depth", tmp_path, directory)
    loss = task.loss(task.model, task.collate([{"image_path": "image.jpg", "depth_path": "depth.npy"}]))
    loss.backward()
    gradients = [p.grad for p in task.model.parameters() if p.grad is not None]
    assert torch.isfinite(loss) and gradients and all(torch.isfinite(g).all() for g in gradients)
    assert any(g.abs().sum() > 0 for g in gradients)


def test_floorplan_model_backward_on_both_label_heads(tmp_path):
    torch.set_num_threads(2)
    Image.new("RGB", (32, 32), "white").save(tmp_path / "plan.png")
    rooms = np.zeros((32, 32), dtype=np.uint8)
    rooms[8:24, 8:24] = 1
    icons = np.zeros_like(rooms)
    icons[8:12, 12:16] = 2
    np.savez(tmp_path / "labels.npz", rooms=rooms, icons=icons)
    task = Task("floorplan", tmp_path)
    batch = task.collate([{"image_path": "plan.png", "labels_path": "labels.npz"}])
    loss = task.loss(task.model, batch)
    loss.backward()
    assert torch.isfinite(loss)
    assert task.model.head.weight.grad[:12].abs().sum() > 0
    assert task.model.head.weight.grad[12:].abs().sum() > 0
