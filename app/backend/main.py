from fastapi import FastAPI

from app.backend.api.v1.routes import router as api_router

app = FastAPI(title="Furniture AI PRO Backend")
app.include_router(api_router)


@app.get("/")
def root() -> dict:
    return {"service": "furniture-ai-pro", "version": "v1"}
