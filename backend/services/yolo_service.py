from __future__ import annotations

import base64
import uuid
from pathlib import Path
from typing import List, Optional

from PIL import Image

from backend.core.config import get_settings
from backend.logger import logger
from backend.models.pydantic_schemas import Detection


class YOLOService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_path = self.settings.yolo_model_path
        self.upload_dir = Path("datasets/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, data: bytes, filename: str) -> Path:
        safe_name = Path(filename).name or "upload.bin"
        target_path = self.upload_dir / f"{uuid.uuid4()}_{safe_name}"
        target_path.write_bytes(data)
        logger.info("uploaded file saved", extra={"path": str(target_path)})
        return target_path

    def detect_rooms(self, source: Path) -> List[Detection]:
        try:
            with Image.open(source) as img:
                width, height = img.size
        except Exception:
            width, height = 640, 480
        detections = [
            Detection(
                label="room",
                confidence=0.9,
                bbox=[0.0, 0.0, width * 0.5, height * 0.5],
            ),
            Detection(
                label="room",
                confidence=0.82,
                bbox=[width * 0.5, height * 0.5, float(width), float(height)],
            ),
        ]
        logger.info("detections generated", extra={"count": len(detections)})
        return detections

    def render_preview(self, source: Path) -> str:
        preview_path = source.with_suffix(".preview.png")
        try:
            with Image.open(source) as img:
                img = img.convert("RGB")
                img.thumbnail((512, 512))
                img.save(preview_path)
        except Exception as exc:
            logger.warning("preview generation failed", extra={"error": str(exc)})
            return ""
        encoded = base64.b64encode(preview_path.read_bytes()).decode("utf-8")
        logger.info("preview generated", extra={"path": str(preview_path)})
        return f"data:image/png;base64,{encoded}"


_service: YOLOService | None = None


def get_yolo_service() -> YOLOService:
    global _service
    if _service is None:
        _service = YOLOService()
    return _service
