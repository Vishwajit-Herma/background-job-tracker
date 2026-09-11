"""Unit tests for Gemini dynamic model fallback and Redis cooldown circuit breaker."""

from unittest.mock import MagicMock, patch
from django.core.cache import cache
import pytest
import requests

from apps.ai.providers.base import (
    AIConfigurationError,
    AIProviderError,
)
from apps.ai.providers.gemini import GeminiProvider

MOCK_SUCCESS_BODY = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "text": (
                            '{"answer": "Root cause identified.", "confidence": "HIGH", '
                            '"evidence": [{"source": "incident", "reference_id": "1", "fact": "Timeout"}], '
                            '"recommendations": [{"action": "Scale worker", "reason": "High load"}]}'
                        )
                    }
                ]
            }
        }
    ]
}


def make_mock_response(status_code: int, json_data: dict | None = None, text: str = ""):
    """Helper to construct a mock requests.Response object."""
    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = status_code
    mock_resp.text = text or str(json_data)
    if json_data is not None:
        mock_resp.json.return_value = json_data
    else:
        mock_resp.json.side_effect = ValueError("No JSON")
    return mock_resp


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before and after every test."""
    cache.clear()
    yield
    cache.clear()


class TestGeminiModelFallback:
    """Test suite for GeminiProvider model fallback and circuit breaker."""

    def test_missing_api_key_raises_configuration_error(self):
        provider = GeminiProvider(api_key="", fallback_models=["gemini-3.8-flash"])
        with pytest.raises(AIConfigurationError):
            provider.generate_json("Test prompt")

    def test_primary_model_success_makes_single_call(self):
        """When the primary model returns 200, no failover occurs."""
        provider = GeminiProvider(
            api_key="fake-key",
            model="gemini-3.8-flash",
            fallback_models=["gemini-3.8-flash", "gemini-3.7-flash"],
        )

        mock_resp = make_mock_response(200, json_data=MOCK_SUCCESS_BODY)
        with patch("requests.post", return_value=mock_resp) as mock_post:
            result = provider.generate_json("Explain failure")

            assert mock_post.call_count == 1
            call_url = mock_post.call_args[0][0]
            assert "gemini-3.8-flash" in call_url
            assert result["answer"] == "Root cause identified."
            assert result["confidence"] == "HIGH"

    def test_primary_429_fails_over_to_fallback_model(self):
        """When primary model returns 429, seamlessly failover to second model."""
        provider = GeminiProvider(
            api_key="fake-key",
            model="gemini-3.8-flash",
            fallback_models=["gemini-3.8-flash", "gemini-3.7-flash"],
            cooldown_seconds=300,
        )

        resp_429 = make_mock_response(429, text="Resource exhausted: quota exceeded")
        resp_200 = make_mock_response(200, json_data=MOCK_SUCCESS_BODY)

        with patch("requests.post", side_effect=[resp_429, resp_200]) as mock_post:
            result = provider.generate_json("Explain failure")

            assert mock_post.call_count == 2
            first_url = mock_post.call_args_list[0][0][0]
            second_url = mock_post.call_args_list[1][0][0]
            assert "gemini-3.8-flash" in first_url
            assert "gemini-3.7-flash" in second_url
            assert result["answer"] == "Root cause identified."

        # Primary model must be marked in cache cooldown
        assert cache.get("gemini_quota_exhausted:gemini-3.8-flash") is True
        # Second model must NOT be in cooldown
        assert cache.get("gemini_quota_exhausted:gemini-3.7-flash") is None

    def test_subsequent_request_skips_model_in_cooldown(self):
        """Subsequent requests must immediately skip models in cooldown without attempting them."""
        # Pre-set gemini-3.8-flash in cooldown
        cache.set("gemini_quota_exhausted:gemini-3.8-flash", True, timeout=300)

        provider = GeminiProvider(
            api_key="fake-key",
            model="gemini-3.8-flash",
            fallback_models=["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"],
        )

        resp_200 = make_mock_response(200, json_data=MOCK_SUCCESS_BODY)
        with patch("requests.post", return_value=resp_200) as mock_post:
            result = provider.generate_json("Explain failure")

            # Only 1 call made, directly to gemini-3.7-flash!
            assert mock_post.call_count == 1
            call_url = mock_post.call_args[0][0]
            assert "gemini-3.7-flash" in call_url
            assert result["answer"] == "Root cause identified."

    def test_all_models_rate_limited_raises_provider_error(self):
        """When all candidate models return 429/503, raises clear AIProviderError."""
        provider = GeminiProvider(
            api_key="fake-key",
            model="gemini-3.8-flash",
            fallback_models=["gemini-3.8-flash", "gemini-3.7-flash"],
            cooldown_seconds=300,
            demand_cooldown_seconds=60,
            retry_delay=0,
        )

        resp_429 = make_mock_response(429, text="Rate limit reached")
        resp_503 = make_mock_response(503, text="Service overloaded")

        # 429 fails immediately; 503 retries once then fails (total 3 calls)
        with patch("requests.post", side_effect=[resp_429, resp_503, resp_503]) as mock_post:
            with pytest.raises(AIProviderError) as exc_info:
                provider.generate_json("Explain failure")

            assert "exhausted their rate limits or daily quotas" in str(exc_info.value)
            assert mock_post.call_count == 3

        assert cache.get("gemini_quota_exhausted:gemini-3.8-flash") is True
        assert cache.get("gemini_quota_exhausted:gemini-3.7-flash") is True

    def test_503_retry_succeeds_on_second_attempt_without_fallback(self):
        """When primary model returns 503 transiently, in-model retry succeeds without failing over."""
        provider = GeminiProvider(
            api_key="fake-key",
            model="gemini-3.8-flash",
            fallback_models=["gemini-3.8-flash", "gemini-3.7-flash"],
            retry_delay=0,
        )

        resp_503 = make_mock_response(503, text="Temporary demand spike")
        resp_200 = make_mock_response(200, json_data=MOCK_SUCCESS_BODY)

        with patch("requests.post", side_effect=[resp_503, resp_200]) as mock_post:
            result = provider.generate_json("Explain failure")

            # 2 calls on the SAME primary model
            assert mock_post.call_count == 2
            first_url = mock_post.call_args_list[0][0][0]
            second_url = mock_post.call_args_list[1][0][0]
            assert "gemini-3.8-flash" in first_url
            assert "gemini-3.8-flash" in second_url
            assert result["answer"] == "Root cause identified."

        # Model must NOT be in cooldown because retry succeeded!
        assert cache.get("gemini_quota_exhausted:gemini-3.8-flash") is None

    def test_timeout_on_first_model_fails_over_to_second_model(self):
        """When a model times out on retries, fails over to the next candidate model."""
        provider = GeminiProvider(
            api_key="fake-key",
            model="gemini-3.8-flash",
            fallback_models=["gemini-3.8-flash", "gemini-3.7-flash"],
            timeout=1,
        )

        resp_200 = make_mock_response(200, json_data=MOCK_SUCCESS_BODY)

        # 2 timeouts for primary model (max_retries=2), then 200 for fallback model
        side_effects = [
            requests.Timeout("Connection timed out"),
            requests.Timeout("Connection timed out"),
            resp_200,
        ]

        with patch("requests.post", side_effect=side_effects) as mock_post:
            result = provider.generate_json("Explain failure")

            assert mock_post.call_count == 3
            assert result["confidence"] == "HIGH"
            last_url = mock_post.call_args_list[2][0][0]
            assert "gemini-3.7-flash" in last_url

    def test_all_models_in_cooldown_retries_all_as_last_resort(self):
        """If all models are in cooldown, don't abort — retry them all as last resort."""
        cache.set("gemini_quota_exhausted:gemini-3.8-flash", True, timeout=300)
        cache.set("gemini_quota_exhausted:gemini-3.7-flash", True, timeout=300)

        provider = GeminiProvider(
            api_key="fake-key",
            model="gemini-3.8-flash",
            fallback_models=["gemini-3.8-flash", "gemini-3.7-flash"],
        )

        candidates = provider._get_candidate_models()
        assert candidates == ["gemini-3.8-flash", "gemini-3.7-flash"]

    def test_model_chain_deduplication_and_order(self):
        """Checks that priority chain places configured primary first without duplicates."""
        provider = GeminiProvider(
            api_key="fake-key",
            model="gemini-3.6-flash",
            fallback_models=[
                "gemini-3.8-flash",
                "gemini-3.7-flash",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
            ],
        )

        assert provider.fallback_models == [
            "gemini-3.6-flash",
            "gemini-3.8-flash",
            "gemini-3.7-flash",
            "gemini-3.5-flash",
        ]
