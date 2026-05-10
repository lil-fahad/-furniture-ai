"""
AI Chat endpoint — exposes POST /ai/chat for general-purpose
interior design Q&A powered by Alibaba Cloud Qwen.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.services.ai_service import get_ai_service
from backend.logging.logger import logger

router = APIRouter(prefix="/ai", tags=["ai"])

ai_service = get_ai_service()


class ChatRequest(BaseModel):
    message: str
    context: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    model: str


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(payload: ChatRequest) -> ChatResponse:
    """Send a message to the Qwen AI assistant and receive a design-focused reply."""
    try:
        reply = ai_service.chat(
            user_message=payload.message,
            context=payload.context or "",
        )
        return ChatResponse(reply=reply, model=ai_service.model)
    except Exception as exc:
        logger.exception("ai chat failed")
        raise HTTPException(status_code=500, detail=str(exc))
