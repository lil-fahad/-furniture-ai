from typing import List

from fastapi import APIRouter, HTTPException, status

from app.backend.db.models import Blueprint, FurnitureItem
from app.backend.services.blueprint import BlueprintService
from app.backend.services.furniture import FurnitureService

router = APIRouter(prefix="/v1")

furniture_service = FurnitureService()
blueprint_service = BlueprintService(furniture_service)


@router.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@router.get("/furniture", response_model=List[FurnitureItem])
def list_furniture() -> List[FurnitureItem]:
    return furniture_service.list_inventory()


@router.get("/furniture/{item_id}", response_model=FurnitureItem)
def get_furniture_item(item_id: int) -> FurnitureItem:
    try:
        return furniture_service.get_item(item_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Furniture item not found")


@router.get("/blueprints", response_model=List[Blueprint])
def list_blueprints() -> List[Blueprint]:
    return blueprint_service.list_blueprints()


@router.get("/blueprints/{blueprint_id}", response_model=Blueprint)
def get_blueprint(blueprint_id: int) -> Blueprint:
    try:
        return blueprint_service.get_blueprint(blueprint_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found")
