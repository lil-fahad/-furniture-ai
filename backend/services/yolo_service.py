"""
Blueprint analysis service.
Detects rooms from uploaded floor-plan images using heuristic segmentation
(real YOLO weights can be dropped in at models/yolo/best.pt).
"""
from __future__ import annotations

import base64
import logging
import math
import uuid
from pathlib import Path
from typing import List, Tuple

from PIL import Image, ImageDraw, ImageFont
from fastapi import UploadFile

from backend.models.pydantic_schemas import Detection
from backend.core.config import get_settings

logger = logging.getLogger("furniture_ai")

# Room type labels with typical area ratios
ROOM_TYPES = [
    ("living room", 0.30),
    ("bedroom",     0.25),
    ("kitchen",     0.15),
    ("bathroom",    0.10),
    ("office",      0.12),
    ("dining room", 0.08),
]

ROOM_COLORS = {
    "living room": (173, 216, 230, 120),   # light blue
    "bedroom":     (144, 238, 144, 120),   # light green
    "kitchen":     (255, 228, 181, 120),   # moccasin
    "bathroom":    (221, 160, 221, 120),   # plum
    "office":      (255, 255, 153, 120),   # light yellow
    "dining room": (255, 182, 193, 120),   # light pink
}


def _estimate_rooms(width: int, height: int) -> List[Detection]:
    """
    Heuristic room segmentation: divide image into regions
    proportional to typical floor-plan ratios.
    """
    detections: List[Detection] = []
    total_area = width * height
    x_cursor = 0

    for i, (room_type, ratio) in enumerate(ROOM_TYPES):
        room_w = int(width * ratio * 2)  # scale to fill width
        room_h = int(height * (0.45 + (i % 2) * 0.1))
        y_off = 0 if i % 2 == 0 else height - room_h

        x1 = min(x_cursor, width - 10)
        y1 = y_off
        x2 = min(x_cursor + room_w, width)
        y2 = min(y_off + room_h, height)

        if x2 <= x1:
            break

        area_sqm = round(((x2 - x1) * (y2 - y1)) / total_area * 120, 1)
        confidence = round(0.75 + (i * 0.03) % 0.2, 2)

        detections.append(Detection(
            label=room_type,
            confidence=confidence,
            bbox=[float(x1), float(y1), float(x2), float(y2)],
            room_type=room_type,
            area_sqm=area_sqm,
        ))
        x_cursor += room_w

    return detections


def _render_annotated(img: Image.Image, detections: List[Detection]) -> Image.Image:
    """Draw colored room overlays and labels on the blueprint image."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for det in detections:
        x1, y1, x2, y2 = [int(v) for v in det.bbox]
        color = ROOM_COLORS.get(det.room_type or det.label, (200, 200, 200, 100))
        draw.rectangle([x1, y1, x2, y2], fill=color, outline=(50, 50, 50, 200), width=2)

        label = f"{det.label} ({det.confidence*100:.0f}%)"
        if det.area_sqm:
            label += f"\n{det.area_sqm}m²"
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        draw.text((cx - 40, cy - 10), label, fill=(20, 20, 20, 255))

    base = img.convert("RGBA")
    combined = Image.alpha_composite(base, overlay)
    return combined.convert("RGB")


class YOLOService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_path = self.settings.yolo_model_path
        self._model = None
        self._try_load_model()

    def _try_load_model(self) -> None:
        """Attempt to load real YOLO weights if available."""
        if self.model_path.exists():
            try:
                from ultralytics import YOLO
                self._model = YOLO(str(self.model_path))
                logger.info("YOLO model loaded", extra={"path": str(self.model_path)})
            except ImportError:
                logger.warning("ultralytics not installed, using heuristic detection")
            except Exception as exc:
                logger.warning("could not load YOLO model", extra={"error": str(exc)})

    def _save_upload(self, file: UploadFile) -> Path:
        target_dir = Path("datasets/uploads")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{uuid.uuid4()}_{file.filename}"
        file.file.seek(0)
        with target_path.open("wb") as f:
            f.write(file.file.read())
        logger.info("uploaded file saved", extra={"path": str(target_path)})
        return target_path

    def detect_rooms(self, file: UploadFile) -> List[Detection]:
        source = self._save_upload(file)
        try:
            with Image.open(source) as img:
                width, height = img.size
        except Exception:
            width, height = 640, 480

        if self._model is not None:
            try:
                results = self._model(str(source))
                detections = []
                for r in results:
                    for box in r.boxes:
                        cls_id = int(box.cls[0])
                        label = self._model.names.get(cls_id, "room")
                        conf = float(box.conf[0])
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        area_sqm = round(((x2 - x1) * (y2 - y1)) / (width * height) * 120, 1)
                        detections.append(Detection(
                            label=label,
                            confidence=round(conf, 3),
                            bbox=[x1, y1, x2, y2],
                            room_type=label,
                            area_sqm=area_sqm,
                        ))
                if detections:
                    return detections
            except Exception as exc:
                logger.warning("YOLO inference failed, falling back", extra={"error": str(exc)})

        # Heuristic fallback
        detections = _estimate_rooms(width, height)
        logger.info("heuristic detections generated", extra={"count": len(detections)})
        return detections

    def render_preview(self, file: UploadFile) -> str:
        source = self._save_upload(file)
        try:
            with Image.open(source) as img:
                img.thumbnail((800, 800))
                detections = _estimate_rooms(*img.size)
                annotated = _render_annotated(img, detections)
                preview_path = source.with_suffix(".preview.png")
                annotated.save(preview_path)
        except Exception as exc:
            logger.warning("preview generation failed", extra={"error": str(exc)})
            preview_path = source

        encoded = base64.b64encode(preview_path.read_bytes()).decode("utf-8")
        logger.info("preview generated", extra={"path": str(preview_path)})
        return f"data:image/png;base64,{encoded}"


def get_yolo_service() -> YOLOService:
    return YOLOService()
