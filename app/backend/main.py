from fastapi import FastAPI

from app.backend.api.v1.routes import router as api_router
from app.backend.utils.logger import log

app = FastAPI(title="Furniture AI PRO Backend", version="1.0.0")


@app.on_event("startup")
async def on_startup() -> None:
    log("Backend service starting up")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    log("Backend service shutting down")


app.include_router(api_router, prefix="/api/v1")


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {"message": "Furniture AI PRO backend is running"}
