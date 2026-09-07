"""Bounded internal Qwen protocol; only inline images and project-owned schemas."""

import json
import re
from typing import Annotated, Literal

from pydantic import Field, model_validator

from furniture_ai.schemas import RoomAnalysis, Schema, VisualEvaluation


class InlineImage(Schema):
    url: str = Field(pattern=r"^data:image/(png|jpeg|webp);base64,", max_length=20 * 1024 * 1024)


class ImagePart(Schema):
    type: Literal["image_url"]
    image_url: InlineImage


class TextPart(Schema):
    type: Literal["text"]
    text: str = Field(min_length=1, max_length=24000)


class ChatMessage(Schema):
    role: Literal["system", "user"]
    content: str | list[Annotated[TextPart | ImagePart, Field(discriminator="type")]]

    @model_validator(mode="after")
    def bounded(self):
        if isinstance(self.content, str):
            if not 1 <= len(self.content) <= 24000:
                raise ValueError("Message length outside bounds")
        elif not 1 <= len(self.content) <= 8:
            raise ValueError("Message parts outside bounds")
        return self


class OutputSchema(Schema):
    json_schema: dict = Field(alias="json")


class ChatRequest(Schema):
    model: Literal["Qwen/Qwen2.5-VL-7B-Instruct"]
    messages: list[ChatMessage] = Field(min_length=1, max_length=4)
    temperature: float = Field(0.1, ge=0, le=1)
    max_tokens: int = Field(1600, ge=1, le=2048)
    structured_outputs: OutputSchema

    @model_validator(mode="after")
    def valid_schema(self):
        schema_type(self.structured_outputs.json_schema)
        image_count = sum(
            isinstance(part, ImagePart)
            for message in self.messages
            if isinstance(message.content, list)
            for part in message.content
        )
        if not 1 <= image_count <= 2:
            raise ValueError("Provide one or two inline images")
        return self


def schema_type(value):
    for candidate in (RoomAnalysis, VisualEvaluation):
        if value == candidate.model_json_schema():
            return candidate
    raise ValueError("Unsupported response schema")


def structured_response(text, schema):
    candidate = schema_type(schema)
    text = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    parsed = candidate.model_validate_json(text)
    return {
        "choices": [
            {"message": {"role": "assistant", "content": parsed.model_dump_json()}, "finish_reason": "stop"}
        ]
    }


def message_parts(request):
    messages, encoded_images = [], []
    for message in request.messages:
        if isinstance(message.content, str):
            content = message.content
        else:
            content = []
            for part in message.content:
                if isinstance(part, TextPart):
                    content.append({"type": "text", "text": part.text})
                else:
                    encoded_images.append(part.image_url.url.split(",", 1)[1])
                    content.append({"type": "image"})
        messages.append({"role": message.role, "content": content})
    instruction = (
        "Return only JSON matching this schema. Never invent missing measurements. Schema: "
        + json.dumps(request.structured_outputs.json_schema)
    )
    messages.insert(0, {"role": "system", "content": instruction})
    return messages, encoded_images
