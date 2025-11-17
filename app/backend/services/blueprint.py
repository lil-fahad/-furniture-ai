from typing import List

from app.backend.utils.logger import log


class BlueprintService:
    def compose_blueprint(self, name: str, style: str, materials: List[str]) -> dict:
        log(f"Composing blueprint for {name}")
        layout_steps = [
            "Sketch structural frame",
            "Place load-bearing joints",
            "Add ergonomic curves",
            "Finalize finish layers",
        ]
        material_notes = [
            f"Primary material: {materials[0]}" if materials else "Primary material: pine",
            f"Accent materials: {', '.join(materials[1:])}" if len(materials) > 1 else "Accent materials: none",
        ]

        return {
            "layout": [f"{idx + 1}. {step}" for idx, step in enumerate(layout_steps)],
            "notes": material_notes + [f"Style reference: {style}"],
        }
