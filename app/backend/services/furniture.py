from app.backend.utils.logger import log


class FurnitureService:
    """Manage furniture assets and metadata."""

    def __init__(self) -> None:
        self._items: list[dict[str, str]] = []

    def list_items(self) -> list[dict[str, str]]:
        """Return all tracked furniture items."""
        return list(self._items)

    def add_item(self, name: str, category: str | None = None) -> dict[str, str]:
        """Register a new furniture item placeholder."""
        item = {"name": name, "category": category or "unspecified"}
        self._items.append(item)
        log(f"Furniture item added: {name}")
        return item
