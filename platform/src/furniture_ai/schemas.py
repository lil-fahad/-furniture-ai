from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon

Category = Literal[
    "sofa",
    "armchair",
    "coffee_table",
    "side_table",
    "bed",
    "nightstand",
    "desk",
    "chair",
    "dining_table",
    "cabinet",
    "lamp",
]
RoomType = Literal["living_room", "bedroom", "office", "dining_room", "majlis", "other"]
Scalar = Annotated[float, Field(ge=0, le=50, allow_inf_nan=False)]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Point(Schema):
    x: Scalar
    y: Scalar


class Zone(Schema):
    label: str = Field(min_length=1, max_length=100)
    kind: Literal["door", "fixed", "reserved"]
    polygon: list[Point] = Field(min_length=3, max_length=32)


class Geometry(Schema):
    boundary: list[Point] = Field(min_length=3, max_length=64)
    keepouts: list[Zone] = Field(default_factory=list, max_length=48)
    access_points: list[Point] = Field(default_factory=list, max_length=16)
    confirmed: bool = False

    @model_validator(mode="after")
    def check_polygons(self):
        room = Polygon([(p.x, p.y) for p in self.boundary])
        if not room.is_valid or not 2 <= room.area <= 500:
            raise ValueError("Boundary must be a simple polygon with area 2–500 m²")
        for zone in self.keepouts:
            shape = Polygon([(p.x, p.y) for p in zone.polygon])
            if not shape.is_valid or shape.area < 0.001 or not room.covers(shape):
                raise ValueError("Keepout polygons must be valid and inside the room")
        if any(not room.contains(SPoint(p.x, p.y)) for p in self.access_points):
            raise ValueError("Access points must be inside the room")
        return self


class Requirement(Schema):
    category: Category
    quantity: int = Field(1, ge=1, le=6)
    width_m: float | None = Field(None, gt=0.05, le=10)
    depth_m: float | None = Field(None, gt=0.05, le=10)


class Preferences(Schema):
    style: str = Field("contemporary", min_length=1, max_length=80)
    room_type: RoomType = "living_room"
    requirements: list[Requirement] = Field(
        default_factory=lambda: [
            Requirement(category="sofa"),
            Requirement(category="coffee_table"),
            Requirement(category="armchair"),
        ],
        min_length=1,
        max_length=8,
    )
    clearance_m: float = Field(0.15, ge=0.05, le=1.5)
    walkway_m: float = Field(0.8, ge=0.5, le=1.5)
    prompt: str = Field("", max_length=1000)
    variants: int = Field(3, ge=1, le=4)
    seed: int = Field(42, ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def check_requirements(self):
        if sum(r.quantity for r in self.requirements) > 16:
            raise ValueError("At most 16 furniture pieces per room")
        if len({r.category for r in self.requirements}) != len(self.requirements):
            raise ValueError("Combine duplicate categories into one quantity")
        return self


class ProjectCreate(Schema):
    title: str = Field(min_length=1, max_length=120)
    preferences: Preferences = Field(default_factory=Preferences)
    geometry: Geometry | None = None


class ProjectUpdate(Schema):
    revision: int = Field(ge=1)
    title: str | None = Field(None, min_length=1, max_length=120)
    preferences: Preferences | None = None
    geometry: Geometry | None = None


class Login(Schema):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class JobCreate(Schema):
    kind: Literal["analyze", "design"]


class FeedbackInput(Schema):
    winner: int = Field(ge=0, le=3)
    loser: int = Field(ge=0, le=3)
    consent_training: bool = False

    @model_validator(mode="after")
    def distinct(self):
        if self.winner == self.loser:
            raise ValueError("Choose two different proposals")
        return self


class VisualEvaluation(Schema):
    style_alignment: float = Field(ge=0, le=1)
    visual_quality: float = Field(ge=0, le=1)
    requirement_match: float = Field(ge=0, le=1)
    structural_consistency: float = Field(ge=0, le=1)
    concerns: list[Annotated[str, Field(max_length=300)]] = Field(max_length=12)
    explanation: str = Field(max_length=800)


class RoomAnalysis(Schema):
    room_type: RoomType
    description: str = Field(min_length=1, max_length=1200)
    observed_features: list[str] = Field(max_length=24)
    palette: list[str] = Field(max_length=8)
    suggested_width_m: float | None = Field(None, gt=0, le=50)
    suggested_length_m: float | None = Field(None, gt=0, le=50)
    dimension_evidence: Literal["visible_labels", "uncertain", "none"]
    uncertainties: list[str] = Field(max_length=16)

    @field_validator("palette")
    @classmethod
    def palette_hex(cls, v):
        import re

        if any(not re.fullmatch(r"#[0-9A-Fa-f]{6}", x) for x in v):
            raise ValueError("Palette must contain hex colors")
        return v

    @field_validator("observed_features", "uncertainties")
    @classmethod
    def bounded_strings(cls, v):
        if any(len(s) > 400 for s in v):
            raise ValueError("Descriptions are too long")
        return v
