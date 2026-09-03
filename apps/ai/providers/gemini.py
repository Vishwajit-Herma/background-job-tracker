"""Google Gemini REST API Provider."""

import json
import logging
import time
from typing import Any

from django.conf import settings
import requests

from .base import (
    AIConfigurationError,
    AIProvider,
    AIProviderError,
    AIProviderTimeoutError,
)

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Gemini REST API Provider for structured content generation."""

    # Schema definition mapped internally for Gemini responseSchema
    INVESTIGATION_SCHEMA = {
        "type": "OBJECT",
        "properties": {
            "answer": {
                "type": "STRING",
                "description": "Clear, grounded answer to the user query based solely on supplied telemetry.",
            },
            "confidence": {
                "type": "STRING",
                "enum": ["HIGH", "MEDIUM", "LOW", "INSUFFICIENT_EVIDENCE"],
                "description": "Confidence level in the findings.",
            },
            "evidence": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "source": {
                            "type": "STRING",
                            "enum": [
                                "incident",
                                "incident_event",
                                "analytics",
                                "reliability",
                                "incident_intelligence",
                                "runbook",
                                "postmortem",
                                "execution",
                            ],
                            "description": "Source category of the evidence.",
                        },
                        "reference_id": {
                            "type": "STRING",
                            "description": "Entity identifier, event ID, job ID, or metric reference.",
                        },
                        "fact": {
                            "type": "STRING",
                            "description": "Observed empirical fact from the context.",
                        },
                    },
                    "required": ["source", "reference_id", "fact"],
                },
                "description": "List of empirical facts grounding the answer.",
            },
            "recommendations": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "action": {
                            "type": "STRING",
                            "description": "Actionable recommendation or next step.",
                        },
                        "reason": {
                            "type": "STRING",
                            "description": "Reason grounded in evidence.",
                        },
                    },
                    "required": ["action", "reason"],
                },
                "description": "Actionable recommendations for human operators.",
            },
        },
        "required": ["answer", "confidence", "evidence", "recommendations"],
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "GEMINI_API_KEY", "")
        self.model = model or getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash")
        # Fall back to settings, then to a safe default for thinking-capable models.
        if timeout is not None:
            self.timeout = timeout
        else:
            self.timeout = getattr(settings, "GEMINI_TIMEOUT", 60)

    def generate_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON using Gemini REST API generateContent endpoint."""
        if not self.api_key:
            raise AIConfigurationError(
                "GEMINI_API_KEY is not configured on the server. Please set the environment variable."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": self.INVESTIGATION_SCHEMA,
                "temperature": 0.1,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        max_retries = 3
        response = None

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
            except requests.Timeout as err:
                logger.warning("Gemini API request timed out (attempt %s/%s)", attempt + 1, max_retries)
                if attempt == max_retries - 1:
                    raise AIProviderTimeoutError(
                        f"AI service request timed out after {self.timeout} seconds. Please try again."
                    ) from err
            except requests.RequestException as err:
                logger.error("Gemini API network error: %s", err)
                if attempt == max_retries - 1:
                    raise AIProviderError(f"Network error communicating with AI service: {err}") from err

            if response is not None:
                if response.status_code == 200:
                    break
                elif response.status_code in [429, 503] and attempt < max_retries - 1:
                    sleep_sec = 2 * (attempt + 1)
                    logger.warning(
                        "Gemini API returned status %s (high demand). Retrying in %ss (attempt %s/%s)...",
                        response.status_code,
                        sleep_sec,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(sleep_sec)
                    continue
                else:
                    break

        if response is None or response.status_code != 200:
            status_code = response.status_code if response is not None else 500
            if status_code in [429, 503]:
                raise AIProviderError(
                    "High Model Usage: The AI provider is currently experiencing high demand. Please try again in a few moments."
                )
            logger.error("Gemini API error (%s): %s", status_code, response.text if response else "No response")
            raise AIProviderError(
                f"AI provider returned status {status_code}: {response.text[:200] if response else ''}"
            )

        try:
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise AIProviderError("AI provider returned an empty response candidate list.")

            content_parts = candidates[0].get("content", {}).get("parts", [])
            if not content_parts or "text" not in content_parts[0]:
                raise AIProviderError("AI provider response format is missing text parts.")

            raw_text = content_parts[0]["text"]
            return json.loads(raw_text)
        except (KeyError, IndexError, json.JSONDecodeError) as err:
            logger.error("Failed to parse Gemini JSON output: %s", err)
            raise AIProviderError(
                f"Failed to parse structured JSON from AI provider: {err}"
            ) from err
