from collections.abc import Iterable
from typing import Dict, List

from app.backend.utils.logger import log


class BlueprintService:
    """Manage user-provided room blueprints."""

    def __init__(self) -> None:
        self._blueprints: List[Dict[str, str]] = []

    def list_blueprints(self) -> list[dict[str, str]]:
        """Return all stored blueprints."""
        return list(self._blueprints)

    def create(self, name: str) -> dict[str, str]:
        """Save a lightweight blueprint placeholder."""
        blueprint = {"name": name}
        self._blueprints.append(blueprint)
        log(f"Blueprint registered: {name}")
        return blueprint

    def bulk_import(self, names: Iterable[str]) -> None:
        """Convenience helper for loading many blueprint names at once."""
        for name in names:
            self.create(name)
