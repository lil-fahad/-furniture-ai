import json
import logging
import secrets
import threading
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import Field

from furniture_ai.middleware import SecurityMiddleware
from furniture_ai.ml.config import ModelSettings
from furniture_ai.ml.install import GROUPS
from furniture_ai.ml.networks import RANK_FEATURES
from furniture_ai.ml.runtime import ModelRuntime
from furniture_ai.ml.vlm_protocol import ChatRequest
from furniture_ai.schemas import Category, Geometry, Schema


class ImageRequest(Schema):
    image: str = Field(min_length=32, max_length=20 * 1024 * 1024)


class PerceptionRequest(ImageRequest):
    kind: Literal["photo", "floor_plan"]


class GenerationRequest(PerceptionRequest):
    mask: str | None = Field(None, max_length=20 * 1024 * 1024)
    depth: str | None = Field(None, max_length=20 * 1024 * 1024)
    prompt: str = Field(min_length=1, max_length=1800)
    seed: int = Field(ge=0, le=2**32 - 1)
    steps: int = Field(30, ge=10, le=60)


class SimilarityRequest(ImageRequest):
    text: str = Field(min_length=1, max_length=1200)


class LayoutPiece(Schema):
    id: str = Field(min_length=1, max_length=80)
    category: Category
    width_m: float = Field(gt=0.05, le=10)
    depth_m: float = Field(gt=0.05, le=10)
    height_m: float = Field(gt=0.05, le=6)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")
    dimension_source: Literal["user", "concept_assumption"]


class LayoutRequest(Schema):
    geometry: Geometry
    pieces: list[LayoutPiece] = Field(min_length=1, max_length=16)
    seed: int = Field(42, ge=0, le=2**31 - 1)


class RankingRequest(Schema):
    features: list[Annotated[float, Field(ge=0, le=1)]] = Field(
        min_length=len(RANK_FEATURES), max_length=len(RANK_FEATURES)
    )


def create_model_app(settings=None, runtime=None):
    settings = settings or ModelSettings()
    if len(settings.api_key.get_secret_value()) < 32:
        raise ValueError("Set FURNITURE_ML_API_KEY to 32+ random characters")
    app = FastAPI(title="Furniture AI private model service", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SecurityMiddleware, max_bytes=28 * 1024 * 1024)
    runtime = runtime or ModelRuntime(settings)
    gate = threading.Lock()

    @app.exception_handler(RequestValidationError)
    async def invalid(request, error):
        return JSONResponse(
            {"error": "INVALID_INPUT", "fields": [".".join(map(str, e["loc"])) for e in error.errors()]},
            status_code=422,
        )

    def auth(request: Request):
        if not secrets.compare_digest(
            request.headers.get("authorization", ""), "Bearer " + settings.api_key.get_secret_value()
        ):
            from fastapi import HTTPException

            raise HTTPException(401, "Unauthorized")

    def invoke(role, function, payload):
        if settings.role not in {role, "all"}:
            return JSONResponse({"error": "WRONG_SERVICE"}, status_code=404)
        if not gate.acquire(blocking=False):
            return JSONResponse({"error": "BUSY"}, status_code=429, headers={"Retry-After": "5"})
        try:
            return function(payload)
        except (FileNotFoundError, ValueError) as e:
            logging.error(
                json.dumps(
                    {
                        "operation": function.__name__,
                        "error_type": type(e).__name__,
                        "code": "MODEL_OR_INPUT_INVALID",
                    }
                )
            )
            return JSONResponse({"error": "MODEL_OR_INPUT_INVALID"}, status_code=422)
        except Exception as e:
            logging.error(json.dumps({"operation": function.__name__, "error_type": type(e).__name__}))
            return JSONResponse({"error": "MODEL_EXECUTION_FAILED"}, status_code=503)
        finally:
            gate.release()

    @app.get("/health/live")
    def live():
        return {"status": "alive", "role": settings.role}

    @app.get("/health/ready")
    def ready():
        try:
            aliases = (
                [alias for group in GROUPS.values() for alias in group]
                if settings.role == "all"
                else GROUPS[settings.role]
            )
            for alias in aliases:
                settings.model_path(alias)
            return {"status": "ready", "role": settings.role}
        except (OSError, KeyError, ValueError):
            return JSONResponse({"status": "models_not_installed"}, status_code=503)

    @app.post("/v1/perceive", dependencies=[Depends(auth)])
    def perceive(body: PerceptionRequest):
        return invoke("perception", runtime.perceive, body)

    @app.post("/v1/generate", dependencies=[Depends(auth)])
    def generate(body: GenerationRequest):
        return invoke("generation", runtime.generate, body)

    @app.post("/v1/similarity", dependencies=[Depends(auth)])
    def similarity(body: SimilarityRequest):
        return invoke("scoring", runtime.similarity, body)

    @app.post("/v1/layout", dependencies=[Depends(auth)])
    def layout(body: LayoutRequest):
        return invoke("scoring", runtime.layout, body)

    @app.post("/v1/rank", dependencies=[Depends(auth)])
    def rank(body: RankingRequest):
        return invoke("scoring", runtime.rank, body)

    @app.post("/v1/chat/completions", dependencies=[Depends(auth)])
    def chat(body: ChatRequest):
        return invoke("evaluator", runtime.chat, body)

    return app
