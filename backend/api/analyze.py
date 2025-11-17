from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.services.yolo_service import get_yolo_service
from backend.models.pydantic_schemas import AnalyzeResponse
from backend.logging.logger import logger

router = APIRouter(prefix="/analyze", tags=["analyze"])

yolo_service = get_yolo_service()


@router.post("/blueprint", response_model=AnalyzeResponse)
async def analyze_blueprint(file: UploadFile = File(...)) -> AnalyzeResponse:
    try:
        detections = yolo_service.detect_rooms(file)
        preview = yolo_service.render_preview(file)
        return AnalyzeResponse(rooms=detections, preview_url=preview)
    except Exception as exc:
        logger.exception("analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
