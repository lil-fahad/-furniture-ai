import torch
from torch.nn import functional as F


def segmentation_loss(logits, labels):
    """Cross entropy plus class-balanced soft Dice; ignored pixels never become background."""
    valid = labels != 255
    if not valid.any():
        raise ValueError("Segmentation supervision has no valid pixels")
    target = F.one_hot(labels.masked_fill(~valid, 0), logits.shape[1]).permute(0, 3, 1, 2)
    target = target * valid[:, None]
    probabilities = logits.softmax(1) * valid[:, None]
    intersection = (probabilities * target).sum((0, 2, 3))
    denominator = probabilities.sum((0, 2, 3)) + target.sum((0, 2, 3))
    present = target.sum((0, 2, 3)) > 0
    dice = 1 - ((2 * intersection + 1) / (denominator + 1))[present].mean()
    return F.cross_entropy(logits, labels, ignore_index=255) + 0.5 * dice


def depth_loss(prediction, metric):
    """Relative inverse-depth supervision with masked multiscale gradient consistency."""
    valid = metric > 0
    if valid.sum() < 100:
        raise ValueError("Depth supervision requires at least 100 valid pixels")
    truth = 1 / metric.clamp_min(0.01)

    def normalized(x):
        med = x[valid].median()
        return (x - med) / (x[valid] - med).abs().mean().clamp_min(1e-6)

    pred, truth = normalized(prediction), normalized(truth)
    loss = (pred - truth)[valid].abs().mean()
    for stride in (1, 2, 4):
        delta = (pred - truth)[::stride, ::stride]
        mask = valid[::stride, ::stride]
        horizontal = mask[:, 1:] & mask[:, :-1]
        vertical = mask[1:, :] & mask[:-1, :]
        if horizontal.any():
            loss = loss + 0.05 * (delta[:, 1:] - delta[:, :-1])[horizontal].abs().mean()
        if vertical.any():
            loss = loss + 0.05 * (delta[1:, :] - delta[:-1, :])[vertical].abs().mean()
    return loss


def layout_regularization(centers, rotation_logits, dimensions, valid):
    rotation = rotation_logits.softmax(-1)[..., 1:2]
    sizes = dimensions * (1 - rotation) + dimensions.flip(-1) * rotation
    minimum, maximum = centers - sizes / 2, centers + sizes / 2
    outside = (F.relu(-minimum) + F.relu(maximum - 1))[valid].mean()
    intersection = F.relu(
        torch.minimum(maximum[:, :, None], maximum[:, None, :])
        - torch.maximum(minimum[:, :, None], minimum[:, None, :])
    ).prod(-1)
    pairs = valid[:, :, None] & valid[:, None, :]
    pairs &= ~torch.eye(valid.shape[1], dtype=torch.bool, device=valid.device)[None]
    overlap = intersection[pairs].mean() if pairs.any() else centers.sum() * 0
    return outside + overlap
