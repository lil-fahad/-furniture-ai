from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.logger import logger
from backend.models.pydantic_schemas import AnalyzeResponse
from backend.services.yolo_service import get_yolo_service

router = APIRouter(prefix="/analyze", tags=["analyze"])

yolo_service = get_yolo_service()


@router.post("/blueprint", response_model=AnalyzeResponse)
async def analyze_blueprint(file: UploadFile = File(...)) -> AnalyzeResponse:
    try:
        contents = await file.read()
        saved_path = yolo_service.save_bytes(contents, file.filename or "upload.bin")
        detections = yolo_service.detect_rooms(saved_path)
        preview = yolo_service.render_preview(saved_path)
        return AnalyzeResponse(rooms=detections, preview_url=preview)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
