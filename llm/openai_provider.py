"""OpenAI LLM provider implementation."""

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


# Supported models and their display names
SUPPORTED_MODELS = {
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-3.5-turbo": "GPT-3.5 Turbo",
}


class OpenAIProvider(LLMProvider):
    """OpenAI API provider for chat completions.

    Supports models: gpt-4o, gpt-4o-mini, gpt-3.5-turbo.
    Configuration: OPENAI_API_KEY, OPENAI_BASE_URL (optional, for proxy).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key.
            model: Model to use (default: gpt-4o-mini).
            base_url: Optional base URL for proxy support.
        """
        super().__init__(api_key, model, base_url)
        self._client: Optional[openai.OpenAI] = None

    def _get_client(self) -> openai.OpenAI:
        """Lazy-initialize and return the OpenAI client."""
        if self._client is None:
            kwargs = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = openai.OpenAI(**kwargs)
        return self._client

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a chat completion using OpenAI API.

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
                f"OpenAI API key is invalid. Please check OPENAI_API_KEY. ({e})"
            ) from e

        except openai.RateLimitError as e:
            raise RateLimitError(
                f"OpenAI rate limit exceeded. Please wait and try again. ({e})"
            ) from e

        except openai.APIConnectionError as e:
            raise NetworkError(
                f"Failed to connect to OpenAI API. Check your network. ({e})"
            ) from e

        except openai.APITimeoutError as e:
            raise NetworkError(
                f"OpenAI API request timed out. ({e})"
            ) from e

        except openai.NotFoundError as e:
            raise ModelNotFoundError(
                f"Model '{self._model}' not found. Supported: {list(SUPPORTED_MODELS.keys())}. ({e})"
            ) from e

        except openai.APIStatusError as e:
            raise LLMProviderError(
                f"OpenAI API error (status {e.status_code}): {e.message}"
            ) from e

        except openai.APIError as e:
            raise LLMProviderError(f"OpenAI API error: {e}") from e

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
        """Get list of supported OpenAI models.

        Returns:
            List of supported model identifiers.
        """
        return list(SUPPORTED_MODELS.keys())
