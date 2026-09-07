"""Task-specific trainable networks. Production loading requires trained safetensors."""

import torch
from torch import nn
from torch.nn import functional as F

CATEGORIES = [
    "sofa",
    "armchair",
    "coffee_table",
    "side_table",
    "bed",
    "nightstand",
    "desk",
    "chair",
    "dining_table",
    "cabinet",
    "lamp",
]
RANK_FEATURES = [
    "style_alignment",
    "visual_quality",
    "requirement_match",
    "structural_consistency",
    "siglip_similarity_01",
    "layout_score_clipped",
    "access_checked",
]


class LayoutTransformer(nn.Module):
    def __init__(self, width=128, layers=4):
        super().__init__()
        self.room = nn.Conv2d(3, width, kernel_size=4, stride=4)
        self.category = nn.Embedding(len(CATEGORIES) + 1, width)
        self.dimensions = nn.Linear(2, width)
        self.positions = nn.Parameter(torch.zeros(1, 80, width))
        nn.init.normal_(self.positions, std=0.02)
        layer = nn.TransformerEncoderLayer(
            width, 4, width * 4, dropout=0.1, batch_first=True, norm_first=True, activation="gelu"
        )
        self.encoder = nn.TransformerEncoder(layer, layers, enable_nested_tensor=False)
        self.head = nn.Sequential(nn.LayerNorm(width), nn.Linear(width, 4))

    def forward(self, room, categories, dimensions, padding_mask=None):
        room_tokens = self.room(room).flatten(2).transpose(1, 2)
        items = self.category(categories) + self.dimensions(dimensions)
        sequence = torch.cat([room_tokens, items], dim=1)
        sequence = sequence + self.positions[:, : sequence.shape[1]]
        mask = None
        if padding_mask is not None:
            mask = torch.cat(
                [
                    torch.zeros(room.shape[0], room_tokens.shape[1], dtype=torch.bool, device=room.device),
                    padding_mask,
                ],
                dim=1,
            )
        encoded = self.encoder(sequence, src_key_padding_mask=mask)
        prediction = self.head(encoded[:, room_tokens.shape[1] :])
        return {"centers": prediction[..., :2].sigmoid(), "rotation_logits": prediction[..., 2:]}


class PairwiseRanker(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(len(RANK_FEATURES), 32), nn.GELU(), nn.Linear(32, 16), nn.GELU(), nn.Linear(16, 1)
        )

    def forward(self, features):
        return self.net(features).squeeze(-1)


class Block(nn.Sequential):
    def __init__(self, inputs, outputs):
        super().__init__(
            nn.Conv2d(inputs, outputs, 3, padding=1),
            nn.GroupNorm(8, outputs),
            nn.GELU(),
            nn.Conv2d(outputs, outputs, 3, padding=1),
            nn.GroupNorm(8, outputs),
            nn.GELU(),
        )


class FloorplanNet(nn.Module):
    """Independent U-Net for 12 room classes and 11 icon classes, trained on licensed labels."""

    def __init__(self):
        super().__init__()
        self.down = nn.ModuleList([Block(3, 32), Block(32, 64), Block(64, 128), Block(128, 256)])
        self.up = nn.ModuleList([Block(256 + 128, 128), Block(128 + 64, 64), Block(64 + 32, 32)])
        self.head = nn.Conv2d(32, 23, 1)

    def forward(self, x):
        features = []
        for i, block in enumerate(self.down):
            x = block(F.max_pool2d(x, 2) if i else x)
            features.append(x)
        for block, skip in zip(self.up, reversed(features[:-1]), strict=True):
            x = block(
                torch.cat(
                    [F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False), skip],
                    dim=1,
                )
            )
        return self.head(x)


def pairwise_loss(model, winner, loser):
    return F.softplus(-(model(winner) - model(loser))).mean()


def multi_positive_siglip_loss(logits, group_ids):
    positive = group_ids[:, None].eq(group_ids[None, :])
    positives = -F.logsigmoid(logits)[positive].mean()
    negatives = -F.logsigmoid(-logits)[~positive]
    return positives + (negatives.mean() if negatives.numel() else logits.sum() * 0)
