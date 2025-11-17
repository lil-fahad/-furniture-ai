from typing import Dict, Iterable, List, Optional

from app.backend.db.models import FurnitureItem
from app.backend.utils.logger import get_logger


class FurnitureService:
    def __init__(self, inventory: Optional[Iterable[FurnitureItem]] = None) -> None:
        self._logger = get_logger(__name__)
        self._inventory: Dict[int, FurnitureItem] = {}
        self._seed_inventory(inventory)

    def list_inventory(self) -> List[FurnitureItem]:
        self._logger.info("Returning %s furniture items", len(self._inventory))
        return list(self._inventory.values())

    def get_item(self, item_id: int) -> FurnitureItem:
        item = self._inventory.get(item_id)
        if not item:
            self._logger.warning("Furniture item %s not found", item_id)
            raise KeyError(item_id)
        return item

    def _seed_inventory(self, inventory: Optional[Iterable[FurnitureItem]]) -> None:
        seed_items = inventory or [
            FurnitureItem(id=1, name="Scandi Lounge Chair", style="scandinavian", materials=["oak", "linen"], price=599.0),
            FurnitureItem(id=2, name="Industrial Coffee Table", style="industrial", materials=["steel", "reclaimed wood"], price=429.0),
            FurnitureItem(id=3, name="Minimalist Bookshelf", style="minimalist", materials=["birch", "laminate"], price=349.0),
        ]
        for item in seed_items:
            self._inventory[item.id] = item
        self._logger.info("Seeded %s furniture items", len(self._inventory))
