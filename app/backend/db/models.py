from typing import List

from pydantic import BaseModel, Field


class FurnitureItem(BaseModel):
    id: int
    name: str
    style: str
    materials: List[str]
    price: float


class Blueprint(BaseModel):
    id: int
    name: str
    description: str
    furniture_items: List[int] = Field(default_factory=list)
