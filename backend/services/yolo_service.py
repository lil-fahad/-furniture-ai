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

    def save_bytes(self, data: bytes, filename: str) -> Path:
        target_dir = Path("datasets/uploads")
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name or "upload.bin"
        target_path = target_dir / f"{uuid.uuid4()}_{safe_name}"
        target_path.write_bytes(data)
        logger.info("uploaded file saved", extra={"path": str(target_path)})
        return target_path

    def _save_upload(self, file: UploadFile) -> Path:
        # Backwards-compatible synchronous helper.
        file.file.seek(0)
        data = file.file.read()
        return self.save_bytes(data, file.filename or "upload.bin")

    def detect_rooms_from_path(self, source: Path) -> List[Detection]:
        try:
            with Image.open(source) as img:
                width, height = img.size
        except Exception:
            width, height = 640, 480
        detections = [
            Detection(label="room", confidence=0.9, bbox=[0, 0, width * 0.5, height * 0.5]),
            Detection(
                label="room",
                confidence=0.82,
                bbox=[width * 0.5, height * 0.5, float(width), float(height)],
            ),
        ]
        logger.info("detections generated", extra={"count": len(detections)})
        return detections

    def render_preview_from_path(self, source: Path) -> str:
        with Image.open(source) as img:
            if img.mode not in ("RGB", "RGBA"):
                has_alpha = "A" in img.mode or (img.mode == "P" and "transparency" in img.info)
                img = img.convert("RGBA" if has_alpha else "RGB")
            img.thumbnail((512, 512))
            preview_path = source.parent / f"{source.stem}.preview.png"
            img.save(preview_path)
        encoded = base64.b64encode(preview_path.read_bytes()).decode("utf-8")
        logger.info("preview generated", extra={"path": str(preview_path)})
        return f"data:image/png;base64,{encoded}"

    def detect_rooms(self, file: UploadFile) -> List[Detection]:
        return self.detect_rooms_from_path(self._save_upload(file))

    def render_preview(self, file: UploadFile) -> str:
        return self.render_preview_from_path(self._save_upload(file))


def get_yolo_service() -> YOLOService:
    return YOLOService()
