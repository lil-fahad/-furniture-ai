# ruff: noqa: E402 -- Optional dependencies are checked before model imports.
"""Real Transformers forward/backward contracts using small, untrained local fixtures."""

import numpy as np
import pytest
from PIL import Image

torch = pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("scipy")
from transformers import (
    BertConfig,
    BertTokenizerFast,
    GroundingDinoConfig,
    GroundingDinoForObjectDetection,
    GroundingDinoImageProcessor,
    GroundingDinoProcessor,
    Sam2Config,
    Sam2HieraDetConfig,
    Sam2ImageProcessorFast,
    Sam2MaskDecoderConfig,
    Sam2Model,
    Sam2Processor,
    Sam2PromptEncoderConfig,
    Sam2VisionConfig,
    SwinConfig,
)

from furniture_ai.ml.tasks import Task

pytestmark = pytest.mark.ml


def make_dino(directory):
    directory.mkdir()
    vocabulary = [f"[unused{i}]" for i in range(1200)]
    for index, word in {
        0: "[PAD]",
        100: "[UNK]",
        101: "[CLS]",
        102: "[SEP]",
        103: "[MASK]",
        1012: ".",
        1029: "?",
        1100: "chair",
        1101: "sofa",
        1102: "bed",
        1103: "dining",
        1104: "table",
    }.items():
        vocabulary[index] = word
    (directory / "vocab.txt").write_text("\n".join(vocabulary), encoding="utf-8")
    tokenizer = BertTokenizerFast(vocab_file=str(directory / "vocab.txt"))
    processor = GroundingDinoProcessor(
        GroundingDinoImageProcessor(size={"shortest_edge": 64, "longest_edge": 96}), tokenizer
    )
    config = GroundingDinoConfig(
        backbone_config=SwinConfig(
            embed_dim=32, depths=[1, 1, 1, 1], num_heads=[1, 2, 4, 8], window_size=2, out_indices=[2, 3, 4]
        ),
        text_config=BertConfig(
            vocab_size=1200, hidden_size=32, intermediate_size=64, num_hidden_layers=1, num_attention_heads=4
        ),
        d_model=32,
        num_queries=8,
        encoder_layers=1,
        decoder_layers=1,
        encoder_attention_heads=4,
        decoder_attention_heads=4,
        encoder_ffn_dim=64,
        decoder_ffn_dim=64,
        disable_custom_kernels=True,
        max_text_len=32,
    )
    GroundingDinoForObjectDetection(config).save_pretrained(directory)
    processor.save_pretrained(directory)


def make_sam(directory):
    backbone = Sam2HieraDetConfig(
        hidden_size=8,
        image_size=[64, 64],
        blocks_per_stage=[1, 1, 1, 1],
        embed_dim_per_stage=[8, 16, 32, 64],
        num_attention_heads_per_stage=[1, 1, 2, 4],
        window_size_per_stage=[2, 2, 2, 2],
        global_attention_blocks=[],
        window_positional_embedding_background_size=[2, 2],
    )
    config = Sam2Config(
        vision_config=Sam2VisionConfig(
            backbone_config=backbone,
            backbone_channel_list=[64, 32, 16, 8],
            backbone_feature_sizes=[[16, 16], [8, 8], [4, 4]],
            fpn_hidden_size=32,
        ),
        prompt_encoder_config=Sam2PromptEncoderConfig(hidden_size=32, image_size=64),
        mask_decoder_config=Sam2MaskDecoderConfig(
            hidden_size=32, mlp_dim=64, num_hidden_layers=1, num_attention_heads=4, iou_head_hidden_dim=32
        ),
    )
    Sam2Model(config).save_pretrained(directory)
    Sam2Processor(
        Sam2ImageProcessorFast(size={"height": 64, "width": 64}, mask_size={"height": 16, "width": 16})
    ).save_pretrained(directory)


@pytest.mark.parametrize("name", ["dino", "sam2"])
def test_foundation_adapter_real_forward_backward(tmp_path, name):
    torch.set_num_threads(2)
    Image.new("RGB", (80, 64), (75, 145, 220)).save(tmp_path / "image.jpg")
    mask = np.zeros((64, 80), dtype=np.uint8)
    mask[10:40, 20:50] = 255
    Image.fromarray(mask).save(tmp_path / "mask.png")
    directory = tmp_path / "model"
    (make_dino if name == "dino" else make_sam)(directory)
    task = Task(name, tmp_path, directory)
    row = {
        "image_path": "image.jpg",
        "mask_path": "mask.png",
        "categories": ["chair", "sofa", "bed", "dining table"],
        "boxes": [{"xywh": [20, 10, 30, 30], "category_id": 3}],
    }
    batch = task.collate([row])
    task.model.train()
    loss = task.loss(task.model, batch)
    assert torch.isfinite(loss)
    loss.backward()
    gradients = [p.grad for p in task.model.parameters() if p.requires_grad and p.grad is not None]
    assert gradients and all(torch.isfinite(g).all() for g in gradients)
    assert any(g.abs().sum() > 0 for g in gradients)
    if name == "sam2":
        assert all(p.grad is None for p in task.model.vision_encoder.parameters())
    else:
        assert batch["labels"][0]["class_labels"].tolist() == [3]
