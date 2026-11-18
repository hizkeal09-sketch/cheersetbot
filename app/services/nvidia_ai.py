"""NVIDIA Build AI integration for content moderation."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import Settings


@dataclass
class ModerationResult:
    """Result of image moderation."""

    is_safe: bool
    reason: str | None
    confidence: float
    needs_review: bool


class NVIDIAService:
    """Client for NVIDIA Build API (chat completions, image moderation, etc.)."""

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.nvidia_api_key.get_secret_value() if settings.nvidia_api_key else ""
        self.model = settings.nvidia_model
        self.base_url = settings.nvidia_base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def moderate_image(
        self,
        image_url: str,
        *,
        model: str | None = None,
    ) -> ModerationResult:
        """Moderate an image for nudity and sexually explicit content.

        Uses NVIDIA's vision-language model to analyze the image and return
        a moderation decision.
        """
        if not self.api_key:
            # No API key configured: allow by default but flag for review
            return ModerationResult(
                is_safe=True,
                reason=None,
                confidence=0.0,
                needs_review=True,
            )

        model_name = model or self.model

        system_prompt = (
            "You are a content moderator for a dating app for adults 18+. "
            "Analyze the image for: nudity, sexually explicit content, "
            "pornography, genital exposure, sexual acts, or other inappropriate "
            "adult content unsuitable for a dating platform. "
            "Respond with JSON only: "
            '{"safe": true/false, "reason": "brief explanation", '
            '"confidence": 0.0-1.0, "needs_review": true/false}'
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        try:
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 300,
                "stream": False,
            }
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            import json

            # Try to parse JSON from the response
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: try to extract JSON from markdown code blocks
                import re

                match = re.search(r"```json\s*(\{.*?\})\s*```", content, re.DOTALL)
                if match:
                    result = json.loads(match.group(1))
                else:
                    # Last resort: look for any JSON-like object
                    match = re.search(r"\{.*\}", content, re.DOTALL)
                    if match:
                        result = json.loads(match.group(0))
                    else:
                        return ModerationResult(
                            is_safe=True,
                            reason="moderation_parse_error",
                            confidence=0.0,
                            needs_review=True,
                        )

            return ModerationResult(
                is_safe=bool(result.get("safe", True)),
                reason=result.get("reason"),
                confidence=float(result.get("confidence", 0.0)),
                needs_review=bool(result.get("needs_review", False)),
            )

        except Exception:
            # On any error, fail safe: hold for review
            return ModerationResult(
                is_safe=True,
                reason="moderation_service_error",
                confidence=0.0,
                needs_review=True,
            )

    async def moderate_text(self, text: str) -> ModerationResult:
        """Use an NVIDIA model to check text for inappropriate content."""
        if not self.api_key:
            return ModerationResult(
                is_safe=True,
                reason=None,
                confidence=0.0,
                needs_review=True,
            )

        system_prompt = (
            "You are a content moderator for a dating app for adults 18+. "
            "Check the user-submitted text for: spam, harassment, fake profiles, "
            "underage content, scams, inappropriate content, or contact info sharing "
            "(phone numbers, emails, usernames, links). "
            "Respond with JSON only: "
            '{"safe": true/false, "reason": "...", "confidence": 0.0-1.0, '
            '"needs_review": true/false}'
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ]

        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 200,
                "stream": False,
            }
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            import json

            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re

                match = re.search(r"\{.*\}", content, re.DOTALL)
                if match:
                    result = json.loads(match.group(0))
                else:
                    return ModerationResult(
                        is_safe=True,
                        reason="moderation_parse_error",
                        confidence=0.0,
                        needs_review=True,
                    )

            return ModerationResult(
                is_safe=bool(result.get("safe", True)),
                reason=result.get("reason"),
                confidence=float(result.get("confidence", 0.0)),
                needs_review=bool(result.get("needs_review", False)),
            )

        except Exception:
            return ModerationResult(
                is_safe=True,
                reason="moderation_service_error",
                confidence=0.0,
                needs_review=True,
            )

    async def generate_conversation_starter(self, profile_summary: str) -> str:
        """Generate an icebreaker message based on a profile."""
        messages = [
            {
                "role": "system",
                "content": "Write a friendly, respectful conversation starter for a dating app. "
                           "Keep it under 100 characters. Don't be creepy.",
            },
            {"role": "user", "content": f"Profile: {profile_summary}"},
        ]
        return await self.chat_completion(messages, temperature=0.8, max_tokens=150)

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        """Send a chat completion request to NVIDIA Build."""
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is not configured")

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        response = await self.client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
