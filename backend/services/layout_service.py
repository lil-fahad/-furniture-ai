from typing import List
import uuid

from backend.models.pydantic_schemas import Mesh, Layout3DResponse, LayoutRequest
from backend.logging.logger import logger


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
        return Layout3DResponse(meshes=meshes, metadata={"source": req.blueprint_url})


def get_layout_service() -> LayoutService:
    return LayoutService()
