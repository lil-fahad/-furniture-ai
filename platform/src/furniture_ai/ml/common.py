import base64
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw
from safetensors.torch import load_file, save_file

from furniture_ai.ml.networks import CATEGORIES
from furniture_ai.schemas import Geometry


def image_from_base64(value):
    if not value or len(value) > 20 * 1024 * 1024:
        raise ValueError("Image payload outside bounds")
    data = base64.b64decode(value, validate=True)
    image = Image.open(io.BytesIO(data))
    if image.width * image.height > 24_000_000:
        raise ValueError("Too many pixels")
    image.load()
    return image.convert("RGB")


def image_b64(image):
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def load_checkpoint(model, directory, kind):
    directory = Path(directory)
    metadata = json.loads((directory / "metadata.json").read_text())
    if metadata.get("kind") != kind or metadata.get("format") != 1:
        raise ValueError("Checkpoint architecture mismatch")
    path = directory / "model.safetensors"
    with path.open("rb") as f:
        revision = hashlib.file_digest(f, "sha256").hexdigest()
    if revision != metadata.get("sha256"):
        raise ValueError("Checkpoint digest mismatch")
    model.load_state_dict(load_file(path), strict=True)
    return model, metadata


def save_checkpoint(model, directory, kind, metadata):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    weights = directory / "model.safetensors"
    save_file({k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()}, str(weights))
    with weights.open("rb") as f:
        sha = hashlib.file_digest(f, "sha256").hexdigest()
    (directory / "metadata.json").write_text(
        json.dumps({**metadata, "format": 1, "kind": kind, "sha256": sha}, indent=2, allow_nan=False) + "\n"
    )


def layout_inputs(geometry, pieces):
    geometry = Geometry.model_validate(geometry)
    xs, ys = [p.x for p in geometry.boundary], [p.y for p in geometry.boundary]
    minx, miny, width, depth = min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)

    def xy(p):
        return ((p.x - minx) / width * 31, (p.y - miny) / depth * 31)

    channels = [Image.new("L", (32, 32)) for _ in range(3)]
    ImageDraw.Draw(channels[0]).polygon([xy(p) for p in geometry.boundary], fill=255)
    for zone in geometry.keepouts:
        ImageDraw.Draw(channels[1]).polygon([xy(p) for p in zone.polygon], fill=255)
    for p in geometry.access_points:
        x, y = xy(p)
        ImageDraw.Draw(channels[2]).ellipse((x - 1, y - 1, x + 1, y + 1), fill=255)
    raster = torch.from_numpy(np.stack([np.asarray(im) for im in channels]).astype("float32") / 255)
    categories = torch.tensor([CATEGORIES.index(p["category"]) for p in pieces], dtype=torch.long)
    dimensions = torch.tensor([[p["width_m"] / width, p["depth_m"] / depth] for p in pieces])
    return raster, categories, dimensions, (minx, miny, width, depth)
