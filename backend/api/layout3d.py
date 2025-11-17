from fastapi import APIRouter, HTTPException

from backend.services.layout_service import get_layout_service
from backend.models.pydantic_schemas import LayoutRequest, Layout3DResponse
from backend.logging.logger import logger

router = APIRouter(prefix="/layout3d", tags=["layout3d"])

layout_service = get_layout_service()


@router.post("/generate", response_model=Layout3DResponse)
async def generate_layout(payload: LayoutRequest) -> Layout3DResponse:
    try:
        return layout_service.generate(payload)
    except Exception as exc:
        logger.exception("layout generation failed")
        raise HTTPException(status_code=500, detail=str(exc))
