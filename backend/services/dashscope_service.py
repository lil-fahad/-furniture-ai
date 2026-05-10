"""
Alibaba Cloud DashScope service — Qwen LLM integration.

Uses the OpenAI-compatible endpoint provided by DashScope.
Supports:
  - General chat completions
  - AI-powered furniture recommendations from style/budget/room context
  - Blueprint analysis text interpretation

Environment variable:
  DASHSCOPE_API_KEY  — set in .env or system environment
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert interior designer and furniture consultant.
You help users choose furniture that matches their style, budget, and room requirements.
When recommending furniture, always provide:
- Item name and category
- Why it fits the style
- Approximate price range
- Where to buy (IKEA or Alibaba/AliExpress)
Respond in clear, concise language. If asked in Arabic, respond in Arabic."""


class DashScopeService:
    """Client for Alibaba Cloud DashScope Qwen LLM API."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._api_key = (
            self._settings.dashscope_api_key
            or os.getenv("DASHSCOPE_API_KEY", "")
        )
        self._model = self._settings.dashscope_model
        self._base_url = self._settings.dashscope_base_url
        self._available = bool(self._api_key)
        if not self._available:
            logger.warning("DashScope API key not configured — AI chat disabled")

    @property
    def is_available(self) -> bool:
        return self._available

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Send a chat completion request to Qwen and return the reply text."""
        if not self._available:
            return "AI service is not configured. Please set DASHSCOPE_API_KEY."

        full_messages = [
            {"role": "system", "content": system_prompt or _SYSTEM_PROMPT}
        ] + messages

        payload = {
            "model": self._model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(
                    f"{self._base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            logger.error("DashScope API error %s: %s", exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("DashScope request failed: %s", exc)
            raise

    def recommend_furniture(
        self,
        style: str,
        budget: Optional[float],
        rooms: Optional[List[str]],
        detected_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Ask Qwen to recommend furniture based on style/budget/rooms.
        Returns a dict with 'recommendations' list and 'summary' text.
        """
        budget_str = f"${budget:.0f}" if budget else "flexible budget"
        rooms_str = ", ".join(rooms) if rooms else "general living space"
        items_str = (
            f"Detected furniture/objects: {', '.join(detected_items)}."
            if detected_items
            else ""
        )

        user_message = (
            f"I need furniture recommendations for a {style} style home. "
            f"Budget: {budget_str}. Rooms: {rooms_str}. {items_str} "
            f"Please recommend 5 specific furniture pieces with names, categories, "
            f"price estimates, and whether to buy from IKEA or Alibaba. "
            f"Format your response as JSON with keys: 'summary' (string) and "
            f"'recommendations' (array of objects with: name, category, price_range, "
            f"source, reason)."
        )

        raw = self.chat(
            messages=[{"role": "user", "content": user_message}],
            temperature=0.6,
            max_tokens=1500,
        )

        # Try to parse JSON from the response
        try:
            # Strip markdown code fences if present
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.split("\n")
                clean = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
            return json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            # Return as plain text wrapped in expected structure
            return {
                "summary": raw,
                "recommendations": [],
            }

    def analyze_blueprint_text(
        self,
        detected_rooms: List[str],
        style: str = "modern",
    ) -> str:
        """Generate a natural language description of a blueprint layout."""
        rooms_str = ", ".join(detected_rooms) if detected_rooms else "unknown rooms"
        user_message = (
            f"I have a floor plan with the following detected rooms: {rooms_str}. "
            f"The desired interior style is {style}. "
            f"Please provide a brief interior design consultation: "
            f"what furniture would work best in each room, color palette suggestions, "
            f"and key design principles to follow."
        )
        return self.chat(
            messages=[{"role": "user", "content": user_message}],
            temperature=0.7,
            max_tokens=800,
        )


_instance: Optional[DashScopeService] = None


def get_dashscope_service() -> DashScopeService:
    global _instance
    if _instance is None:
        _instance = DashScopeService()
    return _instance
