from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: List[float] = Field(..., description="[x1, y1, x2, y2]")
    room_type: Optional[str] = None
    area_sqm: Optional[float] = None


class AnalyzeResponse(BaseModel):
    rooms: List[Detection]
    preview_url: Optional[str]
    total_area_sqm: Optional[float] = None


class FurnitureProduct(BaseModel):
    item_id: str
    name: str
    category: str
    source: Literal["ikea", "alibaba", "local"] = "local"
    price: Optional[float] = None
    currency: str = "USD"
    image_url: Optional[str] = None
    buy_url: Optional[str] = None
    description: Optional[str] = None
    dimensions: Optional[dict] = None   # {"w": 80, "d": 60, "h": 75, "unit": "cm"}
    colors: Optional[List[str]] = None
    styles: Optional[List[str]] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    in_stock: bool = True


class FurnitureRecommendation(BaseModel):
    product: FurnitureProduct
    score: float
    reason: Optional[str] = None
    # legacy flat fields kept for backward compat
    item_id: str = ""
    name: str = ""
    category: str = ""
    metadata: Optional[dict] = None

    def model_post_init(self, __context):
        self.item_id = self.product.item_id
        self.name = self.product.name
        self.category = self.product.category


class RecommendRequest(BaseModel):
    style: str = "modern"
    budget: Optional[float] = None
    rooms: Optional[List[str]] = None
    room_area_sqm: Optional[float] = None
    preferred_sources: Optional[List[str]] = None   # ["ikea", "alibaba"]
    color_preference: Optional[str] = None


class RecommendResponse(BaseModel):
    recommendations: List[FurnitureRecommendation]
    total_results: int = 0
    sources_used: List[str] = []


class LayoutRequest(BaseModel):
    blueprint_url: Optional[str] = None
    rooms: Optional[List[Detection]] = None
    style: Optional[str] = "modern"
    furniture_ids: Optional[List[str]] = None


class Mesh(BaseModel):
    id: str
    label: str = "object"
    vertices: List[List[float]]
    faces: List[List[int]]
    color: Optional[str] = "#a0aec0"
    position: Optional[List[float]] = None


class Layout3DResponse(BaseModel):
    meshes: List[Mesh]
    metadata: Optional[dict] = None
    room_bounds: Optional[dict] = None
