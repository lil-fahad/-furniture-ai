import json

import pytest

from furniture_ai.schemas import RoomAnalysis


def request_payload(image_url="data:image/png;base64,AAAA"):
    return {
        "model": "Qwen/Qwen2.5-VL-7B-Instruct",
        "messages": [
            {"role": "system", "content": "Return JSON"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this room"},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            },
        ],
        "max_tokens": 1600,
        "temperature": 0.1,
        "structured_outputs": {"json": RoomAnalysis.model_json_schema()},
    }


def test_vlm_request_rejects_remote_image_urls():
    from furniture_ai.ml.vlm_protocol import ChatRequest

    with pytest.raises(ValueError):
        ChatRequest.model_validate(request_payload("https://example.com/private.jpg"))


def test_vlm_rejects_unbounded_token_request():
    from furniture_ai.ml.vlm_protocol import ChatRequest

    payload = request_payload()
    payload["max_tokens"] = 1000000
    with pytest.raises(ValueError):
        ChatRequest.model_validate(payload)


def test_vlm_response_rejects_invalid_analysis_instead_of_filling_defaults():
    from furniture_ai.ml.vlm_protocol import structured_response

    with pytest.raises(ValueError):
        structured_response('{"invented": true}', RoomAnalysis.model_json_schema())


def test_vlm_response_rejects_unknown_schema():
    from furniture_ai.ml.vlm_protocol import structured_response

    with pytest.raises(ValueError, match="schema"):
        structured_response(json.dumps({"value": 1}), {"type": "object"})


def test_valid_fenced_analysis_preserves_unknown_dimensions():
    from furniture_ai.ml.vlm_protocol import structured_response

    value = {
        "room_type": "living_room",
        "description": "A room with a chair",
        "observed_features": ["chair"],
        "palette": ["#112233"],
        "dimension_evidence": "none",
        "uncertainties": ["No metric scale"],
    }
    result = structured_response("```json\n" + json.dumps(value) + "\n```", RoomAnalysis.model_json_schema())
    choice = result["choices"][0]
    assert choice["finish_reason"] == "stop"
    parsed = json.loads(choice["message"]["content"])
    assert parsed["suggested_width_m"] is None and parsed["suggested_length_m"] is None
    assert parsed["observed_features"] == ["chair"]
