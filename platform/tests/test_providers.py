import json

import httpx
import pytest

from furniture_ai.config import Settings
from furniture_ai.errors import DomainError
from furniture_ai.providers import Providers


@pytest.mark.parametrize("code,retryable", [(429, True), (503, True), (401, False), (422, False)])
def test_provider_errors_are_redacted(code, retryable):
    p = Providers(
        Settings(_env_file=None), httpx.MockTransport(lambda r: httpx.Response(code, text="secret traceback"))
    )
    with pytest.raises(DomainError) as e:
        p.post("http://model.internal", {}, "test-key")
    assert e.value.retryable == retryable and "secret" not in e.value.message
    p.close()


def test_structured_vlm_uses_schema_and_rejects_truncation(png):
    def handler(request):
        payload = json.loads(request.content)
        assert "json" in payload["structured_outputs"]
        assert payload["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}
        )

    p = Providers(Settings(_env_file=None), httpx.MockTransport(handler))
    with pytest.raises(DomainError, match="complete valid"):
        p.analyze(png, "photo")
    p.close()
