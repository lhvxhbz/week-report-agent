"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""

    pass


class APIKeyError(LLMProviderError):
    """Raised when API key is invalid or missing."""

    pass


class RateLimitError(LLMProviderError):
    """Raised when API rate limit is exceeded."""

    pass


class NetworkError(LLMProviderError):
    """Raised when network connection fails."""

    pass


class ModelNotFoundError(LLMProviderError):
    """Raised when the specified model is not available."""

    pass


class LLMProvider(ABC):
    """Abstract base class for all LLM providers.

    All LLM provider implementations must inherit from this class
    and implement the abstract methods.
    """

    def __init__(self, api_key: str, model: str, base_url: Optional[str] = None):
        """Initialize the LLM provider.

        Args:
            api_key: API key for authentication.
            model: Model identifier to use.
            base_url: Optional base URL for API requests (for proxies).
        """
        self._api_key = api_key
        self._model = model
        self._base_url = base_url

    @abstractmethod
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a chat completion response.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.
                Roles: 'system', 'user', 'assistant'.
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens in the response.

        Returns:
            The generated text response.

        Raises:
            APIKeyError: If API key is invalid.
            RateLimitError: If rate limit is exceeded.
            NetworkError: If network connection fails.
            ModelNotFoundError: If model is not available.
            LLMProviderError: For other API errors.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the current model name.

        Returns:
            The model identifier string.
        """
        pass

    @abstractmethod
    def validate_api_key(self) -> bool:
        """Validate that the API key is configured and potentially valid.

        Returns:
            True if the API key appears valid, False otherwise.
        """
        pass

    def get_supported_models(self) -> List[str]:
        """Get list of supported models for this provider.

        Returns:
            List of supported model identifier strings.
        """
        return []

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        return f"{self.__class__.__name__}(model={self._model!r})"
