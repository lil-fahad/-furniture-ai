"""
AI endpoints powered by Alibaba Cloud DashScope (Qwen LLM).

POST /ai/chat                — general chat with the furniture design AI
POST /ai/recommend           — AI-powered furniture recommendations
POST /ai/blueprint-analysis  — natural language blueprint consultation
GET  /ai/status              — check if AI service is configured
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.pydantic_schemas import (
    AIChatRequest,
    AIChatResponse,
    AIRecommendRequest,
    AIRecommendResponse,
    BlueprintAnalysisRequest,
    BlueprintAnalysisResponse,
)
from backend.services.dashscope_service import get_dashscope_service
from backend.core.config import get_settings
from backend.logging.logger import logger

router = APIRouter(prefix="/ai", tags=["ai"])

_ai = get_dashscope_service()
_settings = get_settings()


@router.get("/status")
async def ai_status() -> dict:
    """Check if the DashScope AI service is configured and available."""
    return {
        "available": _ai.is_available,
        "model": _settings.dashscope_model,
        "provider": "Alibaba Cloud DashScope (Qwen)",
    }


@router.post("/chat", response_model=AIChatResponse)
async def ai_chat(payload: AIChatRequest) -> AIChatResponse:
    """
    Send a conversation to the Qwen LLM and get a reply.
    Supports multi-turn conversations via the messages array.
    """
    if not _ai.is_available:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured. Set DASHSCOPE_API_KEY environment variable.",
        )
    try:
        messages = [{"role": m.role, "content": m.content} for m in payload.messages]
        reply = _ai.chat(
            messages=messages,
            system_prompt=payload.system_prompt,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
        logger.info("AI chat completed", extra={"turns": len(messages)})
        return AIChatResponse(reply=reply, model=_settings.dashscope_model)
    except Exception as exc:
        logger.exception("AI chat failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/recommend", response_model=AIRecommendResponse)
async def ai_recommend(payload: AIRecommendRequest) -> AIRecommendResponse:
    """
    Get AI-powered furniture recommendations based on style, budget, and rooms.
    Uses Qwen to generate contextual, personalized suggestions.
    """
    if not _ai.is_available:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured. Set DASHSCOPE_API_KEY environment variable.",
        )
    try:
        result = _ai.recommend_furniture(
            style=payload.style,
            budget=payload.budget,
            rooms=payload.rooms,
            detected_items=payload.detected_items,
        )
        logger.info(
            "AI furniture recommendations",
            extra={"style": payload.style, "count": len(result.get("recommendations", []))},
        )
        return AIRecommendResponse(
            summary=result.get("summary", ""),
            recommendations=result.get("recommendations", []),
            ai_powered=True,
        )
    except Exception as exc:
        logger.exception("AI recommend failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/blueprint-analysis", response_model=BlueprintAnalysisResponse)
async def blueprint_analysis(payload: BlueprintAnalysisRequest) -> BlueprintAnalysisResponse:
    """
    Generate a natural language interior design consultation from detected rooms.
    """
    if not _ai.is_available:
        raise HTTPException(
            status_code=503,
            detail="AI service not configured. Set DASHSCOPE_API_KEY environment variable.",
        )
    try:
        consultation = _ai.analyze_blueprint_text(
            detected_rooms=payload.detected_rooms,
            style=payload.style,
        )
        logger.info("Blueprint AI analysis completed", extra={"rooms": len(payload.detected_rooms)})
        return BlueprintAnalysisResponse(consultation=consultation, ai_powered=True)
    except Exception as exc:
        logger.exception("Blueprint AI analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
