"""Tests for the /ai/* endpoints (AI assist)."""
from __future__ import annotations
import json
from unittest.mock import patch

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared mock responses
# ---------------------------------------------------------------------------

_ROOM_PLAN_RESPONSE = json.dumps({
    "summary": "A curated modern plan for your living room.",
    "priority_categories": ["sofa", "table", "lighting"],
    "tips": [
        "Start with an anchor piece like a sofa.",
        "Layer lighting for ambiance.",
        "Use rugs to define zones.",
    ],
})

_COLOR_PALETTE_RESPONSE = json.dumps({
    "primary": "warm white",
    "accent": "sage green",
    "neutral": "light oak",
    "rationale": "A timeless modern palette for a living room.",
})

_ENRICH_DESC_RESPONSE = "A beautifully crafted modern sofa with premium fabric."

_CHAT_RESPONSE = "Consider adding a statement rug to anchor the room."


def _mock_chat(messages, temperature=0.7, max_tokens=512) -> str:
    """Return a pre-canned response based on message content."""
    user_content = messages[-1].get("content", "")
    if "color palette" in user_content.lower() or "Suggest a harmonious" in user_content:
        return _COLOR_PALETTE_RESPONSE
    if "furniture plan" in user_content.lower() or "Provide a furniture plan" in user_content:
        return _ROOM_PLAN_RESPONSE
    if "product description" in user_content.lower() or "Write the product description" in user_content:
        return _ENRICH_DESC_RESPONSE
    return _CHAT_RESPONSE


# ---------------------------------------------------------------------------
# /ai/room-plan
# ---------------------------------------------------------------------------

def test_room_plan_success(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.chat",
        side_effect=_mock_chat,
    ):
        response = client.post(
            "/ai/room-plan",
            json={"room_types": ["living room", "bedroom"], "style": "modern", "area_sqm": 50.0},
        )
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "priority_categories" in data
    assert isinstance(data["priority_categories"], list)
    assert "tips" in data
    assert isinstance(data["tips"], list)


def test_room_plan_minimal_payload(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.chat",
        side_effect=_mock_chat,
    ):
        response = client.post("/ai/room-plan", json={"room_types": ["office"]})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /ai/color-palette
# ---------------------------------------------------------------------------

def test_color_palette_success(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.chat",
        side_effect=_mock_chat,
    ):
        response = client.post(
            "/ai/color-palette",
            json={"style": "modern", "room_type": "living room"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "primary" in data
    assert "accent" in data
    assert "neutral" in data
    assert "rationale" in data


def test_color_palette_with_existing_colors(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.chat",
        side_effect=_mock_chat,
    ):
        response = client.post(
            "/ai/color-palette",
            json={"style": "classic", "room_type": "bedroom", "existing_colors": ["navy", "gold"]},
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /ai/enrich-description
# ---------------------------------------------------------------------------

def test_enrich_description_success(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.chat",
        side_effect=_mock_chat,
    ):
        response = client.post(
            "/ai/enrich-description",
            json={
                "product_name": "KIVIK Sofa",
                "category": "sofa",
                "styles": ["modern", "scandinavian"],
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert "description" in data
    assert isinstance(data["description"], str)
    assert len(data["description"]) > 0


# ---------------------------------------------------------------------------
# /ai/chat
# ---------------------------------------------------------------------------

def test_ai_chat_success(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.chat",
        side_effect=_mock_chat,
    ):
        response = client.post(
            "/ai/chat",
            json={"message": "How should I decorate my living room?"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert isinstance(data["reply"], str)
    assert len(data["reply"]) > 0


def test_ai_chat_with_context(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.chat",
        side_effect=_mock_chat,
    ):
        response = client.post(
            "/ai/chat",
            json={
                "message": "What rug should I choose?",
                "context": "user is designing a modern living room",
            },
        )
    assert response.status_code == 200
    assert "reply" in response.json()


def test_ai_chat_requires_message(client: TestClient) -> None:
    response = client.post("/ai/chat", json={})
    assert response.status_code == 422  # message field is required
