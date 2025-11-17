from datetime import datetime
from typing import List

from app.backend.services.blueprint import BlueprintService
from app.backend.utils.logger import log


class FurnitureService:
    def __init__(self, blueprint_service: BlueprintService | None = None) -> None:
        self.blueprint_service = blueprint_service or BlueprintService()

    def generate_preview(self, name: str, style: str, materials: List[str]) -> dict:
        log(f"Generating preview for {name} in {style} style")
        blueprint = self.blueprint_service.compose_blueprint(name=name, style=style, materials=materials)

        instructions = [
            f"Model the {name} following the {style} style principles.",
            "Reinforce structural joints for durability.",
            f"Use materials: {', '.join(materials) if materials else 'standard composites' }.",
            "Render a 360-degree preview for review.",
        ]

        return {
            "name": name,
            "style": style,
            "materials": materials,
            "instructions": instructions + blueprint["notes"],
            "generated_at": datetime.utcnow(),
        }
