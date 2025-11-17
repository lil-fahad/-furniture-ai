from fastapi import FastAPI

from app.ai_engine.models.recommender import Recommender
from app.ai_engine.models.yolo import YOLODetector

app = FastAPI(title="AI Engine PRO", version="1.0.0")
detector = YOLODetector()
recommender = Recommender()


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/detect", tags=["ai"], summary="Detect furniture objects in an image")
async def detect_objects(image_url: str) -> dict:
    return {"detections": detector.detect(image_url)}


@app.post("/recommend", tags=["ai"], summary="Recommend complimentary items")
async def recommend(style: str, primary_material: str) -> dict:
    return {"recommendations": recommender.recommend(style, primary_material)}
