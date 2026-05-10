from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.services.yolo_service import get_yolo_service
from backend.models.pydantic_schemas import AnalyzeResponse
from backend.logging.logger import logger

router = APIRouter(prefix="/analyze", tags=["analyze"])

yolo_service = get_yolo_service()


@router.post("/blueprint", response_model=AnalyzeResponse)
async def analyze_blueprint(file: UploadFile = File(...)) -> AnalyzeResponse:
    """
    Analyze a floor plan / blueprint image.
    Detects rooms, estimates dimensions, and returns an annotated preview.
    """
    try:
        detections, preview = yolo_service.analyze(file)
        return AnalyzeResponse(
            rooms=detections,
            preview_url=preview,
            total_rooms=len(detections),
        )
    except Exception as exc:
        logger.exception("analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
