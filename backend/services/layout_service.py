from __future__ import annotations

import uuid
from typing import List, Optional

from backend.logger import logger
from backend.models.pydantic_schemas import Layout3DResponse, LayoutRequest, Mesh


class LayoutService:
    def generate(self, req: LayoutRequest) -> Layout3DResponse:
        meshes: List[Mesh] = [
            Mesh(
                id=str(uuid.uuid4()),
                vertices=[[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
                faces=[[0, 1, 2], [0, 2, 3]],
            )
        ]
        logger.info("layout generated", extra={"mesh_count": len(meshes)})
        return Layout3DResponse(
            meshes=meshes,
            metadata={"source": req.blueprint_url or "synthetic"},
        )


_service: LayoutService | None = None


def get_layout_service() -> LayoutService:
    global _service
    if _service is None:
        _service = LayoutService()
    return _service
