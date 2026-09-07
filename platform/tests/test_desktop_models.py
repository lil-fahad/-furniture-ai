# ruff: noqa: E402 -- These integration contracts need the optional ML runtime.
import pytest
from fastapi.testclient import TestClient

pytest.importorskip("torch")
pytest.importorskip("cv2")
pytest.importorskip("safetensors")
from furniture_ai.ml.config import ModelSettings
from furniture_ai.ml.runtime import ModelRuntime
from furniture_ai.ml.service import create_model_app

pytestmark = pytest.mark.ml


def test_model_cache_recovers_after_loading_a_different_family_fails():
    runtime = ModelRuntime(ModelSettings(device="cpu"))
    old = object()
    assert runtime.load("first", lambda: old) is old

    def fail():
        raise ValueError("weight load failed")

    with pytest.raises(ValueError):
        runtime.load("second", fail)
    replacement = object()
    assert runtime.load("first", lambda: replacement) is replacement


def test_unified_service_routes_scoring_and_perception_with_authentication():
    class RuntimeFixture:
        def perceive(self, request):
            return {"kind": request.kind}

        def similarity(self, request):
            return {"score": 0.75}

        def generate(self, request):
            raise AssertionError("Generation was not requested")

        def layout(self, request):
            raise AssertionError("Layout was not requested")

        def rank(self, request):
            raise AssertionError("Ranking was not requested")

        def chat(self, request):
            raise AssertionError("Chat was not requested")

    settings = ModelSettings(role="all", api_key="a" * 40, device="cpu")
    with TestClient(create_model_app(settings, RuntimeFixture())) as client:
        payload = {"image": "a" * 32, "kind": "photo"}
        assert client.post("/v1/perceive", json=payload).status_code == 401
        client.headers["authorization"] = "Bearer " + "a" * 40
        assert client.post("/v1/perceive", json=payload).json() == {"kind": "photo"}
        result = client.post("/v1/similarity", json={"image": "a" * 32, "text": "chair"})
        assert result.status_code == 200 and result.json()["score"] == 0.75
