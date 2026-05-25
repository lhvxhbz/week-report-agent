"""Alibaba Bailian (DashScope) LLM provider implementation.

Uses the OpenAI-compatible API mode provided by DashScope.
"""

from typing import List, Dict, Optional

import openai

from .base import (
    LLMProvider,
    APIKeyError,
    RateLimitError,
    NetworkError,
    ModelNotFoundError,
    LLMProviderError,
)


# Supported Qwen models
SUPPORTED_MODELS = {
    "qwen-turbo": "Qwen Turbo",
    "qwen-plus": "Qwen Plus",
    "qwen-max": "Qwen Max",
}

# Default DashScope compatible API endpoint
DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class BailianProvider(LLMProvider):
    """Alibaba Bailian (DashScope) provider for chat completions.

    Uses the OpenAI-compatible API mode from DashScope.
    Supports models: qwen-turbo, qwen-plus, qwen-max.
    Configuration: BAILIAN_API_KEY, BAILIAN_BASE_URL (optional).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-turbo",
        base_url: Optional[str] = None,
    ):
        """Initialize Bailian provider.

        Args:
            api_key: Bailian/DashScope API key.
            model: Model to use (default: qwen-turbo).
            base_url: API endpoint (default: DashScope compatible mode).
        """
        resolved_url = base_url or DEFAULT_BASE_URL
        super().__init__(api_key, model, resolved_url)
        self._client: Optional[openai.OpenAI] = None

    def _get_client(self) -> openai.OpenAI:
        """Lazy-initialize and return the OpenAI-compatible client."""
        if self._client is None:
            self._client = openai.OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        return self._client

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a chat completion using DashScope OpenAI-compatible API.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            Generated text response.

        Raises:
            APIKeyError: If API key is invalid.
            RateLimitError: If rate limit is exceeded.
            NetworkError: If network connection fails.
            ModelNotFoundError: If model is not available.
            LLMProviderError: For other API errors.
        """
        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        except openai.AuthenticationError as e:
            raise APIKeyError(
                f"Bailian API key is invalid. Please check BAILIAN_API_KEY. ({e})"
            ) from e

        except openai.RateLimitError as e:
            raise RateLimitError(
                f"Bailian rate limit exceeded. Please wait and try again. ({e})"
            ) from e

        except openai.APIConnectionError as e:
            raise NetworkError(
                f"Failed to connect to Bailian API. Check your network. ({e})"
            ) from e

        except openai.APITimeoutError as e:
            raise NetworkError(
                f"Bailian API request timed out. ({e})"
            ) from e

        except openai.NotFoundError as e:
            raise ModelNotFoundError(
                f"Model '{self._model}' not found. Supported: {list(SUPPORTED_MODELS.keys())}. ({e})"
            ) from e

        except openai.APIStatusError as e:
            raise LLMProviderError(
                f"Bailian API error (status {e.status_code}): {e.message}"
            ) from e

        except openai.APIError as e:
            raise LLMProviderError(f"Bailian API error: {e}") from e

    def get_model_name(self) -> str:
        """Get the current model name.

        Returns:
            The model identifier string.
        """
        return self._model

    def validate_api_key(self) -> bool:
        """Validate that the API key is configured.

        Returns:
            True if API key is non-empty, False otherwise.
        """
        if not self._api_key or self._api_key.startswith("sk-your"):
            return False
        return True

    def get_supported_models(self) -> List[str]:
        """Get list of supported Bailian/Qwen models.

        Returns:
            List of supported model identifiers.
        """
        return list(SUPPORTED_MODELS.keys())
