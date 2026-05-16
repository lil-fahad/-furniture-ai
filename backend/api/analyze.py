import io

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.services.yolo_service import get_yolo_service
from backend.models.pydantic_schemas import AnalyzeResponse
from backend.logging.logger import logger

router = APIRouter(prefix="/analyze", tags=["analyze"])

yolo_service = get_yolo_service()

_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
_CHUNK_SIZE = 64 * 1024  # 64 KB


@router.post("/blueprint", response_model=AnalyzeResponse)
async def analyze_blueprint(file: UploadFile = File(...)) -> AnalyzeResponse:
    try:
        buf = io.BytesIO()
        total = 0
        while True:
            chunk = await file.read(_CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > _MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Upload exceeds maximum allowed size of {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
                )
            buf.write(chunk)
        filename = file.filename or "upload.bin"
        saved_path = yolo_service.save_bytes(buf.getvalue(), filename)
        detections = yolo_service.detect_rooms_from_path(saved_path)
        preview = yolo_service.render_preview_from_path(saved_path)
        return AnalyzeResponse(rooms=detections, preview_url=preview)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
