"""
Alibaba Cloud DashScope (Qwen LLM) service.
Provides AI-powered furniture descriptions, recommendation reasons,
and style analysis via the OpenAI-compatible DashScope API.
"""
from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

from backend.core.config import get_settings

logger = logging.getLogger("furniture_ai")


class DashScopeService:
    """
    Thin wrapper around the DashScope OpenAI-compatible REST API.
    Uses only stdlib (urllib) — no extra dependencies required.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.dashscope_api_key
        self._model = settings.dashscope_model
        self._base_url = settings.dashscope_base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Core chat completion
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        """Send a chat completion request and return the assistant reply text."""
        if not self._api_key:
            raise RuntimeError(
                "DashScope API key not configured. "
                "Set FURNITURE_DASHSCOPE_API_KEY in your environment."
            )
        payload = json.dumps(
            {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            logger.error("DashScope HTTP error %s: %s", exc.code, err_body)
            raise
        except Exception as exc:
            logger.error("DashScope request failed: %s", exc)
            raise

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def generate_recommendation_reason(
        self,
        product_name: str,
        product_category: str,
        product_styles: List[str],
        product_price: Optional[float],
        user_style: str,
        user_budget: Optional[float],
        user_rooms: Optional[List[str]],
        score: float,
    ) -> str:
        """
        Generate a natural-language reason why this product is recommended
        for the user's specific preferences.
        """
        rooms_str = ", ".join(user_rooms) if user_rooms else "any room"
        budget_str = f"${user_budget:.0f}" if user_budget else "flexible budget"
        price_str = f"${product_price:.0f}" if product_price else "price on request"
        styles_str = ", ".join(product_styles) if product_styles else "versatile"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert interior design assistant. "
                    "Write a single concise sentence (max 25 words) explaining why "
                    "a furniture product is a great match for a customer's preferences. "
                    "Be specific, warm, and helpful. No markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Product: {product_name} ({product_category})\n"
                    f"Product styles: {styles_str}\n"
                    f"Product price: {price_str}\n"
                    f"Customer wants: {user_style} style, {rooms_str}, {budget_str}\n"
                    f"Match score: {score:.0%}\n"
                    "Why is this a great pick?"
                ),
            },
        ]

        try:
            return self.chat(messages, temperature=0.6, max_tokens=60)
        except Exception:
            # Graceful fallback — never break recommendations
            return f"Great {user_style} match for your {rooms_str} at {price_str}"

    def enrich_product_description(
        self,
        product_name: str,
        category: str,
        styles: List[str],
        dimensions: Optional[Dict[str, Any]],
        colors: Optional[List[str]],
    ) -> str:
        """
        Generate an enhanced product description using Qwen AI.
        """
        dim_str = ""
        if dimensions:
            dim_str = (
                f"{dimensions.get('w')}W × {dimensions.get('d')}D × "
                f"{dimensions.get('h')}H {dimensions.get('unit', 'cm')}"
            )
        colors_str = ", ".join(colors) if colors else "various colors"
        styles_str = ", ".join(styles) if styles else "versatile"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional furniture copywriter. "
                    "Write a compelling 2-sentence product description. "
                    "Be specific about materials, design, and use cases. No markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Product: {product_name}\n"
                    f"Category: {category}\n"
                    f"Styles: {styles_str}\n"
                    f"Dimensions: {dim_str}\n"
                    f"Available colors: {colors_str}\n"
                    "Write the product description:"
                ),
            },
        ]

        try:
            return self.chat(messages, temperature=0.7, max_tokens=120)
        except Exception:
            return f"Premium {category} in {styles_str} style, available in {colors_str}."

    def analyze_room_style(
        self,
        room_types: List[str],
        area_sqm: Optional[float],
        style_preference: str,
        budget: Optional[float],
    ) -> Dict[str, Any]:
        """
        Use Qwen AI to analyze room requirements and suggest a furniture plan.
        Returns a dict with keys: summary, priority_categories, tips.
        """
        rooms_str = ", ".join(room_types) if room_types else "general living space"
        area_str = f"{area_sqm:.0f} sqm" if area_sqm else "unknown size"
        budget_str = f"${budget:.0f}" if budget else "flexible"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert interior designer. "
                    "Respond ONLY with valid JSON matching this schema: "
                    '{"summary": "string", "priority_categories": ["string"], "tips": ["string"]}. '
                    "No markdown, no extra text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Rooms: {rooms_str}\n"
                    f"Total area: {area_str}\n"
                    f"Style: {style_preference}\n"
                    f"Budget: {budget_str}\n"
                    "Provide a furniture plan with 3 tips."
                ),
            },
        ]

        try:
            raw = self.chat(messages, temperature=0.5, max_tokens=300)
            # Strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as exc:
            logger.warning("Room style analysis parse failed: %s", exc)
            return {
                "summary": f"Curated {style_preference} furniture plan for {rooms_str}.",
                "priority_categories": ["sofa", "table", "lighting"],
                "tips": [
                    "Start with anchor pieces like a sofa or bed.",
                    "Layer lighting for ambiance and function.",
                    "Add rugs to define zones in open-plan spaces.",
                ],
            }

    def suggest_color_palette(
        self,
        style: str,
        room_type: str,
        existing_colors: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Suggest a color palette for a room using Qwen AI.
        Returns: {"primary": str, "accent": str, "neutral": str, "rationale": str}
        """
        existing_str = ", ".join(existing_colors) if existing_colors else "none specified"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a color theory expert for interior design. "
                    "Respond ONLY with valid JSON: "
                    '{"primary": "color", "accent": "color", "neutral": "color", "rationale": "string"}. '
                    "No markdown, no extra text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Style: {style}\n"
                    f"Room: {room_type}\n"
                    f"Existing colors: {existing_str}\n"
                    "Suggest a harmonious color palette."
                ),
            },
        ]

        try:
            raw = self.chat(messages, temperature=0.6, max_tokens=150)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as exc:
            logger.warning("Color palette suggestion failed: %s", exc)
            return {
                "primary": "warm white",
                "accent": "sage green",
                "neutral": "light oak",
                "rationale": f"Classic {style} palette that works well in a {room_type}.",
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_dashscope_service: Optional[DashScopeService] = None


def get_dashscope_service() -> DashScopeService:
    global _dashscope_service
    if _dashscope_service is None:
        _dashscope_service = DashScopeService()
    return _dashscope_service
