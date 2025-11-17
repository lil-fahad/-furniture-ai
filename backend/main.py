from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import analyze, recommend, layout3d
from backend.models.pydantic_schemas import HealthResponse
from backend.core.config import get_settings
from backend.logging.logger import logger

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(recommend.router)
app.include_router(layout3d.router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    logger.info("healthcheck")
    return HealthResponse(status="ok")
