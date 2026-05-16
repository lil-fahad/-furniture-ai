from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.backend.api.v1.routes import router as api_router
from app.backend.utils.logger import log


@asynccontextmanager
async def lifespan(app: FastAPI):
    log("Backend service starting up")
    try:
        yield
    finally:
        log("Backend service shutting down")


app = FastAPI(title="Furniture AI PRO Backend", version="1.0.0", lifespan=lifespan)

app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"message": "Furniture AI PRO backend is running"}
