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


# ---------------------------------------------------------------------------
# External product schemas (IKEA / Alibaba)
# ---------------------------------------------------------------------------

class ExternalProduct(BaseModel):
    """A product fetched from an external retailer (IKEA or Alibaba)."""
    item_id: str
    name: str
    category: str
    price: Optional[float] = None
    currency: str = "USD"
    image_url: Optional[str] = None
    product_url: Optional[str] = None
    source: str  # "ikea" | "alibaba"
    description: Optional[str] = None


class ProductSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    max_results: int = Field(default=10, ge=1, le=50)


class ProductSearchResponse(BaseModel):
    source: str
    products: List[ExternalProduct]
    total: int


class BlueprintRecommendRequest(BaseModel):
    """Request furniture recommendations based on a detected blueprint layout."""
    style: str = "modern"
    budget: Optional[float] = None
    rooms: Optional[List[str]] = None
    sources: List[str] = Field(default=["ikea", "alibaba"], description="Which stores to search")
    max_per_source: int = Field(default=5, ge=1, le=20)


class BlueprintRecommendResponse(BaseModel):
    ikea_products: List[ExternalProduct]
    alibaba_products: List[ExternalProduct]
    ai_recommendations: List[FurnitureRecommendation]
