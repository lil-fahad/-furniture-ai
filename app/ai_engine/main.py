from fastapi import FastAPI

from app.ai_engine.models.recommender import Recommender
from app.ai_engine.models.yolo import YOLODetector

app = FastAPI(title="Furniture AI PRO - AI Engine")

detector = YOLODetector()
recommender = Recommender()


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/detect", tags=["vision"])
def detect_objects() -> dict[str, list[dict[str, str]]]:
    """Stub YOLO detection endpoint."""
    return {"detections": detector.detect()}


@app.get("/recommendations", tags=["recommendations"])
def recommend_styles() -> dict[str, list[str]]:
    """Return demo recommendations for a furniture layout."""
    return {"recommendations": recommender.recommend()}
