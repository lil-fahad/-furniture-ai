from pathlib import Path
from typing import List
import base64
import uuid
from PIL import Image
from fastapi import UploadFile

from backend.models.pydantic_schemas import Detection
from backend.core.config import get_settings
from backend.logging.logger import logger


class YOLOService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.model_path = self.settings.yolo_model_path

    def _save_upload(self, file: UploadFile) -> Path:
        target_dir = Path("datasets/uploads")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{uuid.uuid4()}_{file.filename}"
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
        detections = [
            Detection(label="room", confidence=0.9, bbox=[0, 0, width * 0.5, height * 0.5]),
            Detection(label="room", confidence=0.82, bbox=[width * 0.5, height * 0.5, width, height]),
        ]
        logger.info("detections generated", extra={"count": len(detections)})
        return detections

    def render_preview(self, file: UploadFile) -> str:
        source = self._save_upload(file)
        with Image.open(source) as img:
            img.thumbnail((512, 512))
            preview_path = source.with_suffix(".preview.png")
            img.save(preview_path)
        encoded = base64.b64encode(preview_path.read_bytes()).decode("utf-8")
        logger.info("preview generated", extra={"path": str(preview_path)})
        return f"data:image/png;base64,{encoded}"


def get_yolo_service() -> YOLOService:
    return YOLOService()
