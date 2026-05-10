from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import analyze, recommend, layout3d
from backend.api import search, catalog
from backend.models.pydantic_schemas import HealthResponse
from backend.core.config import get_settings
from backend.logging.logger import logger

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered furniture recommendation and room layout system. "
        "Analyze floor plans, get smart furniture recommendations from IKEA & Alibaba, "
        "and generate 3D room layouts."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(analyze.router)       # POST /analyze/blueprint
app.include_router(recommend.router)     # POST /recommend/furniture, /recommend/blueprint, /recommend/room
app.include_router(layout3d.router)      # POST /layout3d/generate
app.include_router(search.router)        # POST /search/furniture, GET /search/furniture
app.include_router(catalog.router)       # GET  /catalog/items, /catalog/items/{id}, /catalog/categories, /catalog/styles


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Health check endpoint."""
    logger.info("healthcheck")
    return HealthResponse(status="ok")


@app.get("/", tags=["system"])
async def root() -> dict:
    """API root — returns available endpoints summary."""
    return {
        "name": settings.app_name,
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "analyze": {
                "POST /analyze/blueprint": "Analyze a floor plan image to detect rooms",
            },
            "recommend": {
                "POST /recommend/furniture": "Get furniture recommendations by style/budget",
                "POST /recommend/blueprint": "Upload blueprint → get room-specific recommendations",
                "POST /recommend/room": "Get recommendations for a specific room type",
                "GET  /recommend/ai-summary": "Get AI-generated (Alibaba Cloud / Qwen) room furniture summary",
            },
            "search": {
                "POST /search/furniture": "Search furniture by query/filters (JSON body)",
                "GET  /search/furniture": "Search furniture by query/filters (query params)",
            },
            "catalog": {
                "GET /catalog/items": "Browse full catalog with filters & pagination",
                "GET /catalog/items/{item_id}": "Get details for a specific item",
                "GET /catalog/categories": "List all furniture categories",
                "GET /catalog/styles": "List all furniture styles",
            },
            "layout3d": {
                "POST /layout3d/generate": "Generate a 3D room layout from detected rooms",
            },
        },
    }
