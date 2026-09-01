"""Base abstraction and exception hierarchy for AI providers."""

from abc import ABC, abstractmethod
from typing import Any


class AIError(Exception):
    """Base exception for all AI-related errors."""


class AIConfigurationError(AIError):
    """Raised when an AI provider is missing required configuration (e.g. API key)."""


class AIProviderError(AIError):
    """Raised when an external AI provider fails or returns an invalid response."""


class AIProviderTimeoutError(AIProviderError):
    """Raised when an external AI provider times out."""


class AIValidationError(AIError):
    """Raised when the AI output fails validation against domain schema."""


class AIProvider(ABC):
    """Abstract base class for AI LLM providers."""

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON response given a prompt and optional system instructions.

        Args:
            prompt: Main user/context prompt text.
            system_instruction: Optional system instruction grounding the model.

        Returns:
            Parsed JSON dictionary conforming to expected structure.

        Raises:
            AIConfigurationError: If provider is improperly configured.
            AIProviderTimeoutError: If the remote call times out.
            AIProviderError: If the remote call or parsing fails.
        """
