from fastapi import FastAPI

from app.backend.api.v1.routes import router as api_router
from app.backend.utils.logger import configure_logging

app = FastAPI(title="Furniture AI PRO Backend")

configure_logging()
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Simple liveness endpoint."""
    return {"status": "ok"}
