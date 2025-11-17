from fastapi import APIRouter

from app.backend.services.blueprint import BlueprintService
from app.backend.services.furniture import FurnitureService

router = APIRouter(tags=["api"])

blueprint_service = BlueprintService()
furniture_service = FurnitureService()


@router.get("/blueprints")
def list_blueprints() -> dict[str, list[dict[str, str]]]:
    """List saved blueprint drafts."""
    return {"blueprints": blueprint_service.list_blueprints()}


@router.post("/blueprints")
def create_blueprint(name: str) -> dict[str, dict[str, str]]:
    """Create a new blueprint stub."""
    blueprint = blueprint_service.create(name)
    return {"blueprint": blueprint}


@router.get("/furniture")
def list_furniture() -> dict[str, list[dict[str, str]]]:
    """List staged furniture assets."""
    return {"furniture": furniture_service.list_items()}
