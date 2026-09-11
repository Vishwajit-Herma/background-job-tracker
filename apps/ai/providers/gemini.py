"""Google Gemini REST API Provider."""

import json
import logging
import time
from typing import Any

from django.conf import settings
from django.core.cache import cache
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

    DEFAULT_FALLBACK_MODELS = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        fallback_models: list[str] | None = None,
        cooldown_seconds: int | None = None,
        demand_cooldown_seconds: int | None = None,
        retry_delay: float = 1.5,
    ) -> None:
        self.api_key = api_key if api_key is not None else getattr(settings, "GEMINI_API_KEY", "")
        self.model = model or getattr(settings, "GEMINI_MODEL", "gemini-3.8-flash")
        # Fall back to settings, then to a safe default for thinking-capable models.
        if timeout is not None:
            self.timeout = timeout
        else:
            self.timeout = getattr(settings, "GEMINI_TIMEOUT", 60)

        raw_fallbacks = fallback_models or getattr(
            settings, "GEMINI_FALLBACK_MODELS", self.DEFAULT_FALLBACK_MODELS
        )
        chain: list[str] = [self.model]
        for m in raw_fallbacks:
            if m and m not in chain:
                chain.append(m)
        self.fallback_models = chain

        if cooldown_seconds is not None:
            self.cooldown_seconds = cooldown_seconds
        else:
            self.cooldown_seconds = getattr(settings, "GEMINI_COOLDOWN_SECONDS", 3600)

        if demand_cooldown_seconds is not None:
            self.demand_cooldown_seconds = demand_cooldown_seconds
        else:
            self.demand_cooldown_seconds = getattr(settings, "GEMINI_DEMAND_COOLDOWN_SECONDS", 60)

        self.retry_delay = retry_delay

    def _get_cache_key(self, model: str) -> str:
        return f"gemini_quota_exhausted:{model}"

    def _is_in_cooldown(self, model: str) -> bool:
        try:
            return bool(cache.get(self._get_cache_key(model)))
        except Exception as err:
            logger.warning("Cache access error checking Gemini model cooldown: %s", err)
            return False

    def _set_cooldown(self, model: str, duration: int | None = None) -> None:
        ttl = duration if duration is not None else self.cooldown_seconds
        try:
            cache.set(self._get_cache_key(model), True, timeout=ttl)
            logger.info(
                "Gemini model '%s' marked in cooldown for %ss.",
                model,
                ttl,
            )
        except Exception as err:
            logger.warning("Cache access error setting Gemini model cooldown: %s", err)

    def _get_candidate_models(self) -> list[str]:
        """Return available models in priority order. If all are in cooldown, retries all as last resort."""
        active = [m for m in self.fallback_models if not self._is_in_cooldown(m)]
        if not active:
            logger.warning(
                "All Gemini fallback models are marked in cooldown. Re-attempting all models as last resort."
            )
            return list(self.fallback_models)
        return active

    def _call_model(
        self,
        model: str,
        payload: dict[str, Any],
    ) -> tuple[requests.Response | None, bool, Exception | None]:
        """
        Execute API call to a specific Gemini model with retry for transient errors.

        Returns:
            (response, is_rate_limited, exception)
        """
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={self.api_key}"
        )
        max_retries = 2
        last_err: Exception | None = None

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout,
                )
            except requests.Timeout:
                logger.warning(
                    "Gemini model '%s' request timed out (attempt %s/%s)",
                    model,
                    attempt + 1,
                    max_retries,
                )
                last_err = AIProviderTimeoutError(
                    f"AI service request for model '{model}' timed out after {self.timeout} seconds."
                )
                continue
            except requests.RequestException as err:
                logger.error("Gemini model '%s' network error: %s", model, err)
                last_err = AIProviderError(
                    f"Network error communicating with AI service ({model}): {err}"
                )
                continue

            if response.status_code == 200:
                return response, False, None
            if response.status_code == 503 and attempt < max_retries - 1:
                logger.warning(
                    "Gemini model '%s' returned 503 (High Demand). Retrying in %ss (attempt %s/%s)...",
                    model,
                    self.retry_delay,
                    attempt + 1,
                    max_retries,
                )
                if self.retry_delay > 0:
                    time.sleep(self.retry_delay)
                continue
            if response.status_code in [429, 503]:
                return response, True, None

            # Non-retryable error on this model (e.g. 400 Bad Request, 404 Model Not Found)
            return response, False, None

        return None, False, last_err

    def generate_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON using Gemini REST API with automatic model failover."""
        if not self.api_key:
            raise AIConfigurationError(
                "GEMINI_API_KEY is not configured on the server. Please set the environment variable."
            )

        candidate_models = self._get_candidate_models()
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

        last_error: Exception | None = None
        rate_limited_models: list[str] = []

        for model in candidate_models:
            response, is_rate_limited, err = self._call_model(model, payload)

            if is_rate_limited:
                status_code = response.status_code if response is not None else 429
                is_demand = status_code == 503
                cooldown = self.demand_cooldown_seconds if is_demand else self.cooldown_seconds
                logger.warning(
                    "Gemini model '%s' hit HTTP %s (%s). Setting %ss cooldown and failing over to next model...",
                    model,
                    status_code,
                    "High Demand" if is_demand else "Rate / Quota Limit",
                    cooldown,
                )
                self._set_cooldown(model, duration=cooldown)
                rate_limited_models.append(model)
                continue

            if err is not None:
                last_error = err
                continue

            if response is not None and response.status_code == 200:
                logger.info("Gemini generation successfully fulfilled using model '%s'.", model)
                return self._parse_response(response)

            if response is not None:
                logger.error(
                    "Gemini model '%s' error (%s): %s",
                    model,
                    response.status_code,
                    response.text[:200],
                )
                last_error = AIProviderError(
                    f"AI provider ({model}) returned status {response.status_code}: {response.text[:200]}"
                )

        if rate_limited_models and len(rate_limited_models) == len(candidate_models):
            raise AIProviderError(
                f"All configured Gemini models ({', '.join(rate_limited_models)}) have exhausted "
                "their rate limits or daily quotas. Please try again later."
            )

        if last_error:
            raise last_error

        raise AIProviderError("Failed to generate content from any available Gemini model.")

    def _parse_response(self, response: requests.Response) -> dict[str, Any]:
        """Extract and parse structured JSON from Gemini API response."""
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
