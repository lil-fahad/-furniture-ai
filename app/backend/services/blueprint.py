from typing import Dict, Iterable, List, Optional

from app.backend.db.models import Blueprint
from app.backend.services.furniture import FurnitureService
from app.backend.utils.logger import get_logger


class BlueprintService:
    def __init__(self, furniture_service: FurnitureService, blueprints: Optional[Iterable[Blueprint]] = None) -> None:
        self._logger = get_logger(__name__)
        self._furniture_service = furniture_service
        self._blueprints: Dict[int, Blueprint] = {}
        self._seed_blueprints(blueprints)

    def list_blueprints(self) -> List[Blueprint]:
        self._logger.info("Returning %s blueprint concepts", len(self._blueprints))
        return list(self._blueprints.values())

    def get_blueprint(self, blueprint_id: int) -> Blueprint:
        blueprint = self._blueprints.get(blueprint_id)
        if not blueprint:
            self._logger.warning("Blueprint %s not found", blueprint_id)
            raise KeyError(blueprint_id)
        return blueprint

    def _seed_blueprints(self, blueprints: Optional[Iterable[Blueprint]]) -> None:
        inventory_ids = [item.id for item in self._furniture_service.list_inventory()]
        sample_blueprints = blueprints or [
            Blueprint(
                id=1,
                name="Cozy Reading Nook",
                description="A scandinavian-inspired nook with soft seating and warm woods.",
                furniture_items=inventory_ids[:2],
            ),
            Blueprint(
                id=2,
                name="Loft Living Room",
                description="Industrial loft layout with steel accents and airy shelving.",
                furniture_items=inventory_ids[1:],
            ),
        ]
        for blueprint in sample_blueprints:
            self._blueprints[blueprint.id] = blueprint
        self._logger.info("Seeded %s blueprint ideas", len(self._blueprints))
