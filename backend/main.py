from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import analyze, recommend, layout3d, ai as ai_router
from backend.api import search as search_router
from backend.models.pydantic_schemas import HealthResponse
from backend.core.config import get_settings
from backend.logging.logger import logger

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="AI-powered furniture design system with IKEA and Alibaba integration",
    version="2.0.0",
)
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
app.include_router(search_router.router)
app.include_router(ai_router.router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    logger.info("healthcheck")
    return HealthResponse(status="ok")
