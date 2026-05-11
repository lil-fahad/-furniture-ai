"""Tests for the /recommend endpoint."""
from __future__ import annotations
from unittest.mock import patch

from fastapi.testclient import TestClient


_MOCK_REASON = "Great modern match for your living room."


def _mock_generate_reason(**kwargs) -> str:
    return _MOCK_REASON


def test_recommend_default(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.generate_recommendation_reason",
        side_effect=_mock_generate_reason,
    ):
        response = client.post("/recommend/furniture", json={})
    assert response.status_code == 200
    data = response.json()
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) > 0


def test_recommend_response_schema(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.generate_recommendation_reason",
        side_effect=_mock_generate_reason,
    ):
        response = client.post("/recommend/furniture", json={"style": "modern"})
    assert response.status_code == 200
    rec = response.json()["recommendations"][0]
    assert "product" in rec
    assert "score" in rec
    assert "reason" in rec
    assert 0.0 <= rec["score"] <= 1.0
    product = rec["product"]
    assert "item_id" in product
    assert "name" in product
    assert "category" in product
    assert "source" in product


def test_recommend_with_budget(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.generate_recommendation_reason",
        side_effect=_mock_generate_reason,
    ):
        response = client.post(
            "/recommend/furniture",
            json={"style": "modern", "budget": 300.0},
        )
    assert response.status_code == 200
    data = response.json()
    recs = data["recommendations"]
    # Products within budget receive a higher score than those over budget;
    # verify results list is non-empty and scores are valid.
    assert len(recs) > 0
    for rec in recs:
        assert 0.0 <= rec["score"] <= 1.0


def test_recommend_ikea_only(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.generate_recommendation_reason",
        side_effect=_mock_generate_reason,
    ):
        response = client.post(
            "/recommend/furniture",
            json={"preferred_sources": ["ikea"]},
        )
    assert response.status_code == 200
    data = response.json()
    for rec in data["recommendations"]:
        assert rec["product"]["source"] == "ikea"


def test_recommend_alibaba_only(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.generate_recommendation_reason",
        side_effect=_mock_generate_reason,
    ):
        response = client.post(
            "/recommend/furniture",
            json={"preferred_sources": ["alibaba"]},
        )
    assert response.status_code == 200
    data = response.json()
    for rec in data["recommendations"]:
        assert rec["product"]["source"] == "alibaba"


def test_recommend_with_rooms(client: TestClient) -> None:
    with patch(
        "backend.services.dashscope_service.DashScopeService.generate_recommendation_reason",
        side_effect=_mock_generate_reason,
    ):
        response = client.post(
            "/recommend/furniture",
            json={"rooms": ["living room", "bedroom"], "style": "scandinavian"},
        )
    assert response.status_code == 200
    assert len(response.json()["recommendations"]) > 0
