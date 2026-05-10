from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.services.yolo_service import get_yolo_service
from backend.services.ai_service import get_ai_service
from backend.models.pydantic_schemas import AnalyzeResponse
from backend.logging.logger import logger

router = APIRouter(prefix="/analyze", tags=["analyze"])

yolo_service = get_yolo_service()
ai_service = get_ai_service()


@router.post("/blueprint", response_model=AnalyzeResponse)
async def analyze_blueprint(file: UploadFile = File(...)) -> AnalyzeResponse:
    try:
        detections = yolo_service.detect_rooms(file)
        preview = yolo_service.render_preview(file)

        # Enrich with an AI-generated design brief for the detected rooms
        room_labels = [d.label for d in detections]
        design_brief = ai_service.analyze_room_description(
            room_labels=room_labels,
            style_hint="modern",
        )

        metadata: dict = {}
        if design_brief:
            metadata["design_brief"] = design_brief
            logger.info("analyze: AI design brief attached")

        return AnalyzeResponse(
            rooms=detections,
            preview_url=preview,
            # Attach brief in metadata if the schema supports it; otherwise silently skip
            **({"metadata": metadata} if hasattr(AnalyzeResponse.model_fields, "metadata") else {}),
        )
    except Exception as exc:
        logger.exception("analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
