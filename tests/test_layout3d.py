"""Tests for the /layout3d endpoint."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_generate_layout_default(client: TestClient) -> None:
    response = client.post("/layout3d/generate", json={})
    assert response.status_code == 200
    data = response.json()
    assert "meshes" in data
    assert isinstance(data["meshes"], list)
    assert len(data["meshes"]) > 0


def test_generate_layout_mesh_schema(client: TestClient) -> None:
    response = client.post("/layout3d/generate", json={})
    assert response.status_code == 200
    mesh = response.json()["meshes"][0]
    assert "id" in mesh
    assert "label" in mesh
    assert "vertices" in mesh
    assert "faces" in mesh
    assert isinstance(mesh["vertices"], list)
    assert isinstance(mesh["faces"], list)
    # Each vertex is [x, y, z]
    for vertex in mesh["vertices"]:
        assert len(vertex) == 3
    # Each face is a triangle [i, j, k]
    for face in mesh["faces"]:
        assert len(face) == 3


def test_generate_layout_with_style(client: TestClient) -> None:
    response = client.post("/layout3d/generate", json={"style": "scandinavian"})
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["style"] == "scandinavian"


def test_generate_layout_with_rooms(client: TestClient) -> None:
    payload = {
        "rooms": [
            {
                "label": "living room",
                "confidence": 0.95,
                "bbox": [0.0, 0.0, 500.0, 400.0],
                "room_type": "living room",
                "area_sqm": 25.0,
            }
        ],
        "style": "modern",
    }
    response = client.post("/layout3d/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["meshes"]) > 1  # room mesh + furniture meshes


def test_generate_layout_room_bounds(client: TestClient) -> None:
    response = client.post("/layout3d/generate", json={})
    assert response.status_code == 200
    data = response.json()
    assert "room_bounds" in data
    bounds = data["room_bounds"]
    assert "rooms" in bounds
    assert bounds["rooms"] >= 1


def test_generate_layout_multi_room(client: TestClient) -> None:
    payload = {
        "rooms": [
            {
                "label": "bedroom",
                "confidence": 0.90,
                "bbox": [0.0, 0.0, 400.0, 350.0],
                "room_type": "bedroom",
                "area_sqm": 20.0,
            },
            {
                "label": "office",
                "confidence": 0.85,
                "bbox": [400.0, 0.0, 700.0, 350.0],
                "room_type": "office",
                "area_sqm": 15.0,
            },
        ]
    }
    response = client.post("/layout3d/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["room_bounds"]["rooms"] == 2
