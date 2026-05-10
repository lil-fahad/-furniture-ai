"""
AI Service — integrates with Alibaba Cloud DashScope (Qwen LLM) via the
OpenAI-compatible API endpoint provided by DashScope.

DashScope OpenAI-compatible base URL:
  https://dashscope.aliyuncs.com/compatible-mode/v1

Authentication: Bearer token using the ALIBABA_API_KEY / DASHSCOPE_API_KEY
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx

from backend.core.config import get_settings
from backend.logging.logger import logger

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class QwenAIService:
    """Thin wrapper around the DashScope OpenAI-compatible chat completions API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.api_key: Optional[str] = self.settings.effective_api_key
        self.model: str = self.settings.qwen_model
        if not self.api_key:
            logger.warning("No Alibaba/DashScope API key configured — AI features disabled")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Send a chat completion request and return the assistant message text."""
        if not self.api_key:
            return ""

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{DASHSCOPE_BASE_URL}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            logger.error(
                "DashScope API HTTP error",
                extra={"status": exc.response.status_code, "body": exc.response.text},
            )
            raise
        except Exception as exc:
            logger.error("DashScope API request failed", extra={"error": str(exc)})
            raise

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enhance_furniture_recommendations(
        self,
        style: str,
        budget: Optional[float],
        rooms: Optional[list[str]],
        base_catalog: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Use Qwen to enrich/rank base catalog recommendations according to
        user style, budget, and room types.

        Returns a list of dicts with keys:
          item_id, name, category, score, ai_reason
        """
        if not self.api_key:
            logger.info("ai_service: no API key, skipping AI enrichment")
            return []

        catalog_summary = json.dumps(
            [{"item_id": i["item_id"], "name": i["name"], "category": i.get("category", "misc")}
             for i in base_catalog],
            ensure_ascii=False,
        )
        budget_str = f"${budget:.0f}" if budget else "no specific budget"
        rooms_str = ", ".join(rooms) if rooms else "general living space"

        system_prompt = (
            "You are an expert interior designer and furniture consultant. "
            "Your responses are always valid JSON arrays — no markdown, no extra text."
        )
        user_message = (
            f"A customer wants furniture in the '{style}' style for a {rooms_str}, "
            f"with a budget of {budget_str}.\n\n"
            f"Available catalog items:\n{catalog_summary}\n\n"
            "Select the 3 most suitable items from the catalog (you must use the exact "
            "item_id values). Return ONLY a JSON array of objects with these fields:\n"
            '  item_id (string), name (string), category (string), '
            'score (float 0-1), ai_reason (string, ≤20 words)\n'
            "Example: "
            '[{"item_id":"chair-1","name":"Modern Chair","category":"chair",'
            '"score":0.95,"ai_reason":"Clean lines match modern style perfectly."}]'
        )

        try:
            raw = self._chat(system_prompt, user_message, temperature=0.4, max_tokens=512)
            # Strip potential markdown code fences
            raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
            items = json.loads(raw)
            logger.info("ai_service: recommendations enriched", extra={"count": len(items)})
            return items
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("ai_service: could not parse AI response", extra={"error": str(exc)})
            return []

    def analyze_room_description(
        self,
        room_labels: list[str],
        style_hint: str = "modern",
    ) -> str:
        """
        Given detected room labels, ask Qwen for a natural-language interior
        design brief for those rooms.
        """
        if not self.api_key:
            return ""

        rooms_str = ", ".join(room_labels) if room_labels else "unknown rooms"
        system_prompt = (
            "You are a professional interior designer. "
            "Write concise, actionable design briefs (2-3 sentences max)."
        )
        user_message = (
            f"Blueprint analysis detected these rooms: {rooms_str}. "
            f"Preferred style: {style_hint}. "
            "Provide a short design brief covering layout suggestions and key furniture needs."
        )
        try:
            brief = self._chat(system_prompt, user_message, temperature=0.6, max_tokens=256)
            logger.info("ai_service: room analysis brief generated")
            return brief.strip()
        except Exception as exc:
            logger.warning("ai_service: room analysis failed", extra={"error": str(exc)})
            return ""

    def chat(self, user_message: str, context: str = "") -> str:
        """
        General-purpose furniture/interior design chat.
        Exposed via POST /ai/chat endpoint.
        """
        if not self.api_key:
            return "AI features are not configured. Please set ALIBABA_API_KEY."

        system_prompt = (
            "You are a helpful AI assistant specialising in interior design, "
            "furniture selection, and home layout optimisation. "
            "Be concise, friendly, and practical."
        )
        full_message = f"{context}\n\n{user_message}".strip() if context else user_message
        try:
            return self._chat(system_prompt, full_message, temperature=0.7, max_tokens=512)
        except Exception as exc:
            logger.error("ai_service: chat failed", extra={"error": str(exc)})
            return f"Sorry, I encountered an error: {exc}"


def get_ai_service() -> QwenAIService:
    return QwenAIService()
