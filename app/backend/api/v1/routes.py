from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.backend.services.blueprint import BlueprintService
from app.backend.services.furniture import FurnitureService

router = APIRouter()
blueprint_service = BlueprintService()
furniture_service = FurnitureService(blueprint_service=blueprint_service)


class FurnitureRequest(BaseModel):
    name: str = Field(..., description="Furniture item name", example="Armchair")
    style: str = Field("modern", description="Preferred aesthetic style")
    materials: List[str] = Field(default_factory=list, description="List of preferred materials")


class PreviewResponse(BaseModel):
    name: str
    style: str
    materials: List[str]
    instructions: List[str]
    generated_at: datetime


class BlueprintResponse(BaseModel):
    layout: List[str]
    notes: List[str]


@router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/furniture/preview", response_model=PreviewResponse, tags=["furniture"])
async def create_preview(request: FurnitureRequest) -> PreviewResponse:
    preview = furniture_service.generate_preview(
        name=request.name,
        style=request.style,
        materials=request.materials,
    )
    return preview


@router.post("/blueprints", response_model=BlueprintResponse, tags=["blueprints"])
async def create_blueprint(request: FurnitureRequest) -> BlueprintResponse:
    if not request.materials:
        raise HTTPException(status_code=400, detail="At least one material must be provided")

    blueprint = blueprint_service.compose_blueprint(
        name=request.name, style=request.style, materials=request.materials
    )
    return blueprint
