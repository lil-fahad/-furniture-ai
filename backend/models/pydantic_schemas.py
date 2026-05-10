from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: List[float] = Field(..., description="[x1, y1, x2, y2]")
    room_type: Optional[str] = None
    area_sqm: Optional[float] = None
    suggested_furniture: Optional[List[str]] = None


class AnalyzeResponse(BaseModel):
    rooms: List[Detection]
    preview_url: Optional[str] = None
    total_rooms: int = 0
    blueprint_width: Optional[int] = None
    blueprint_height: Optional[int] = None


# ─── Furniture Source Models ────────────────────────────────────────────────

class FurnitureSource(BaseModel):
    source: str  # "ikea" | "alibaba" | "local"
    url: Optional[str] = None
    price: Optional[float] = None
    currency: str = "USD"
    availability: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    image_url: Optional[str] = None
    sku: Optional[str] = None
    brand: Optional[str] = None
    dimensions: Optional[Dict[str, float]] = None  # width, depth, height in cm
    colors: Optional[List[str]] = None
    materials: Optional[List[str]] = None
    delivery_days: Optional[int] = None


class FurnitureRecommendation(BaseModel):
    item_id: str
    name: str
    category: str
    score: float
    description: Optional[str] = None
    style: Optional[str] = None
    sources: List[FurnitureSource] = []
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    room_fit: Optional[List[str]] = None


class RecommendRequest(BaseModel):
    style: str = "modern"
    budget: Optional[float] = None
    currency: str = "USD"
    rooms: Optional[List[str]] = None
    room_type: Optional[str] = None
    sources: Optional[List[str]] = ["ikea", "alibaba"]
    color_preference: Optional[str] = None
    material_preference: Optional[str] = None
    categories: Optional[List[str]] = None


class RecommendResponse(BaseModel):
    recommendations: List[FurnitureRecommendation]
    total: int = 0
    sources_searched: List[str] = []


# ─── Layout 3D Models ────────────────────────────────────────────────────────

class LayoutRequest(BaseModel):
    blueprint_url: Optional[str] = None
    rooms: Optional[List[Detection]] = None
    style: Optional[str] = "modern"
    furniture_ids: Optional[List[str]] = None


class FurnitureObject3D(BaseModel):
    id: str
    name: str
    category: str
    position: List[float]  # [x, y, z]
    rotation: float = 0.0  # degrees around Y axis
    scale: List[float] = [1.0, 1.0, 1.0]
    color: str = "#8B7355"
    width: float = 1.0
    depth: float = 1.0
    height: float = 1.0
    source_url: Optional[str] = None


class Room3D(BaseModel):
    id: str
    name: str
    width: float
    depth: float
    height: float = 2.8
    position: List[float] = [0.0, 0.0, 0.0]
    furniture: List[FurnitureObject3D] = []
    wall_color: str = "#F5F5F0"
    floor_color: str = "#C8A882"


class Layout3DResponse(BaseModel):
    rooms: List[Room3D]
    total_furniture: int = 0
    metadata: Optional[Dict[str, Any]] = None


# ─── Search Models ────────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    source: Optional[str] = None  # "ikea" | "alibaba" | None (both)
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    style: Optional[str] = None
    limit: int = 20


class SearchResponse(BaseModel):
    results: List[FurnitureRecommendation]
    total: int = 0
    query: str
    source: Optional[str] = None
