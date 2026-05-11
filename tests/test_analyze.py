"""Tests for the /analyze endpoint."""
from __future__ import annotations
import io
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from PIL import Image

from backend.models.pydantic_schemas import Detection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png_bytes(width: int = 100, height: int = 80) -> bytes:
    """Create a minimal in-memory PNG image."""
    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


_FAKE_DETECTIONS = [
    Detection(
        label="living room",
        confidence=0.92,
        bbox=[0.0, 0.0, 300.0, 200.0],
        room_type="living room",
        area_sqm=18.0,
    ),
    Detection(
        label="bedroom",
        confidence=0.88,
        bbox=[300.0, 0.0, 500.0, 200.0],
        room_type="bedroom",
        area_sqm=12.0,
    ),
]

_FAKE_PREVIEW = "data:image/png;base64,iVBORw0KGgo="


def test_analyze_blueprint_success(client: TestClient) -> None:
    png_bytes = _make_png_bytes()
    with (
        patch("backend.services.yolo_service.YOLOService.detect_rooms", return_value=_FAKE_DETECTIONS),
        patch("backend.services.yolo_service.YOLOService.render_preview", return_value=_FAKE_PREVIEW),
    ):
        response = client.post(
            "/analyze/blueprint",
            files={"file": ("floor_plan.png", png_bytes, "image/png")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "rooms" in data
    assert isinstance(data["rooms"], list)
    assert len(data["rooms"]) == 2
    assert "preview_url" in data


def test_analyze_blueprint_room_schema(client: TestClient) -> None:
    png_bytes = _make_png_bytes()
    with (
        patch("backend.services.yolo_service.YOLOService.detect_rooms", return_value=_FAKE_DETECTIONS),
        patch("backend.services.yolo_service.YOLOService.render_preview", return_value=_FAKE_PREVIEW),
    ):
        response = client.post(
            "/analyze/blueprint",
            files={"file": ("plan.png", png_bytes, "image/png")},
        )
    room = response.json()["rooms"][0]
    assert "label" in room
    assert "confidence" in room
    assert "bbox" in room
    assert len(room["bbox"]) == 4
    assert 0.0 <= room["confidence"] <= 1.0


def test_analyze_blueprint_requires_file(client: TestClient) -> None:
    response = client.post("/analyze/blueprint")
    assert response.status_code == 422  # Unprocessable Entity — file is required
