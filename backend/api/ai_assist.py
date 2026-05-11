"""
AI-assist endpoints powered by Alibaba Cloud DashScope (Qwen LLM).
Provides room planning, color palette suggestions, and product description enrichment.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.dashscope_service import get_dashscope_service
from backend.logging.logger import logger

router = APIRouter(prefix="/ai", tags=["ai-assist"])


# ---------------------------------------------------------------------------
# Request / Response schemas (local — no need to pollute pydantic_schemas)
# ---------------------------------------------------------------------------

class RoomPlanRequest(BaseModel):
    room_types: List[str]
    area_sqm: Optional[float] = None
    style: str = "modern"
    budget: Optional[float] = None


class RoomPlanResponse(BaseModel):
    summary: str
    priority_categories: List[str]
    tips: List[str]


class ColorPaletteRequest(BaseModel):
    style: str = "modern"
    room_type: str = "living room"
    existing_colors: Optional[List[str]] = None


class ColorPaletteResponse(BaseModel):
    primary: str
    accent: str
    neutral: str
    rationale: str


class EnrichDescriptionRequest(BaseModel):
    product_name: str
    category: str
    styles: Optional[List[str]] = None
    dimensions: Optional[Dict[str, Any]] = None
    colors: Optional[List[str]] = None


class EnrichDescriptionResponse(BaseModel):
    description: str


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None   # e.g. "user is designing a modern living room"


class ChatResponse(BaseModel):
    reply: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/room-plan", response_model=RoomPlanResponse)
async def room_plan(payload: RoomPlanRequest) -> RoomPlanResponse:
    """
    Generate an AI-powered furniture plan for the given rooms.
    Uses Alibaba Cloud Qwen LLM via DashScope.
    """
    try:
        ai = get_dashscope_service()
        result = ai.analyze_room_style(
            room_types=payload.room_types,
            area_sqm=payload.area_sqm,
            style_preference=payload.style,
            budget=payload.budget,
        )
        return RoomPlanResponse(**result)
    except Exception as exc:
        logger.exception("room-plan AI failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/color-palette", response_model=ColorPaletteResponse)
async def color_palette(payload: ColorPaletteRequest) -> ColorPaletteResponse:
    """
    Suggest a harmonious color palette for a room using Qwen AI.
    """
    try:
        ai = get_dashscope_service()
        result = ai.suggest_color_palette(
            style=payload.style,
            room_type=payload.room_type,
            existing_colors=payload.existing_colors,
        )
        return ColorPaletteResponse(**result)
    except Exception as exc:
        logger.exception("color-palette AI failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/enrich-description", response_model=EnrichDescriptionResponse)
async def enrich_description(payload: EnrichDescriptionRequest) -> EnrichDescriptionResponse:
    """
    Generate an AI-enhanced product description using Qwen LLM.
    """
    try:
        ai = get_dashscope_service()
        description = ai.enrich_product_description(
            product_name=payload.product_name,
            category=payload.category,
            styles=payload.styles or [],
            dimensions=payload.dimensions,
            colors=payload.colors,
        )
        return EnrichDescriptionResponse(description=description)
    except Exception as exc:
        logger.exception("enrich-description AI failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(payload: ChatRequest) -> ChatResponse:
    """
    General-purpose interior design chat powered by Alibaba Cloud Qwen.
    """
    try:
        ai = get_dashscope_service()
        system_prompt = (
            "You are an expert interior designer and furniture consultant. "
            "Give helpful, concise advice about furniture selection, room layout, "
            "color schemes, and interior design. Keep answers under 150 words."
        )
        if payload.context:
            system_prompt += f" Context: {payload.context}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": payload.message},
        ]
        reply = ai.chat(messages, temperature=0.7, max_tokens=200)
        return ChatResponse(reply=reply)
    except Exception as exc:
        logger.exception("ai-chat failed")
        raise HTTPException(status_code=500, detail=str(exc))
