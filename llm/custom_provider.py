"""Custom OpenAI-compatible LLM provider implementation.

Supports any API endpoint that implements the OpenAI chat completions API format.
"""

from typing import List, Dict, Optional

import openai

from .base import (
    LLMProvider,
    APIKeyError,
    RateLimitError,
    NetworkError,
    LLMProviderError,
)


class CustomProvider(LLMProvider):
    """Custom OpenAI-compatible API provider for chat completions.

    Works with any API that implements the OpenAI chat completions format,
    such as local LLM servers (Ollama, vLLM, LM Studio), or third-party
    API providers.

    Configuration: CUSTOM_API_KEY, CUSTOM_BASE_URL, CUSTOM_MODEL_NAME.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
    ):
        """Initialize custom provider.

        Args:
            api_key: API key for the custom endpoint.
            model: Model identifier to use.
            base_url: Base URL of the OpenAI-compatible API endpoint.

        Raises:
            ValueError: If base_url or model is empty.
        """
        if not base_url:
            raise ValueError(
                "CUSTOM_BASE_URL is required for custom provider. "
                "Please set it in your .env file."
            )
        if not model:
            raise ValueError(
                "CUSTOM_MODEL is required for custom provider. "
                "Please set it in your .env file."
            )
        super().__init__(api_key, model, base_url)
        self._client: Optional[openai.OpenAI] = None

    def _get_client(self) -> openai.OpenAI:
        """Lazy-initialize and return the OpenAI-compatible client."""
        if self._client is None:
            kwargs = {
                "api_key": self._api_key or "no-key",
                "base_url": self._base_url,
            }
            self._client = openai.OpenAI(**kwargs)
        return self._client

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a chat completion using the custom OpenAI-compatible API.

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
                f"Custom API key is invalid. Please check CUSTOM_API_KEY. ({e})"
            ) from e

        except openai.RateLimitError as e:
            raise RateLimitError(
                f"Custom API rate limit exceeded. Please wait and try again. ({e})"
            ) from e

        except openai.APIConnectionError as e:
            raise NetworkError(
                f"Failed to connect to custom API at {self._base_url}. "
                f"Check your network and CUSTOM_BASE_URL. ({e})"
            ) from e

        except openai.APITimeoutError as e:
            raise NetworkError(
                f"Custom API request timed out. ({e})"
            ) from e

        except openai.NotFoundError as e:
            raise LLMProviderError(
                f"Model '{self._model}' not found at {self._base_url}. "
                f"Check CUSTOM_MODEL setting. ({e})"
            ) from e

        except openai.APIStatusError as e:
            raise LLMProviderError(
                f"Custom API error (status {e.status_code}): {e.message}"
            ) from e

        except openai.APIError as e:
            raise LLMProviderError(f"Custom API error: {e}") from e

    def get_model_name(self) -> str:
        """Get the current model name.

        Returns:
            The model identifier string.
        """
        return self._model

    def validate_api_key(self) -> bool:
        """Validate that the configuration is present.

        For custom providers, some endpoints don't require API keys,
        so we only check that base_url and model are configured.

        Returns:
            True if base_url and model are configured, False otherwise.
        """
        if not self._base_url:
            return False
        if not self._model:
            return False
        return True

    def get_supported_models(self) -> List[str]:
        """Custom provider supports any model the endpoint provides.

        Returns:
            List containing the configured model name.
        """
        return [self._model]
