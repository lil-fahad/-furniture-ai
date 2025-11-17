from typing import List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: List[float] = Field(..., description="[x1, y1, x2, y2]")


class AnalyzeResponse(BaseModel):
    rooms: List[Detection]
    preview_url: Optional[str]


class FurnitureRecommendation(BaseModel):
    item_id: str
    name: str
    category: str
    score: float
    metadata: Optional[dict]


class RecommendRequest(BaseModel):
    style: str
    budget: Optional[float]
    rooms: Optional[List[str]]


class RecommendResponse(BaseModel):
    recommendations: List[FurnitureRecommendation]


class LayoutRequest(BaseModel):
    blueprint_url: Optional[str]
    rooms: Optional[List[Detection]]


class Mesh(BaseModel):
    id: str
    vertices: List[List[float]]
    faces: List[List[int]]


class Layout3DResponse(BaseModel):
    meshes: List[Mesh]
    metadata: Optional[dict]
