"""Anthropic Claude LLM provider implementation."""

from typing import List, Dict, Optional

import anthropic

from .base import (
    LLMProvider,
    APIKeyError,
    RateLimitError,
    NetworkError,
    ModelNotFoundError,
    LLMProviderError,
)


# Supported models
SUPPORTED_MODELS = {
    "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
    "claude-3-5-sonnet-latest": "Claude 3.5 Sonnet (Latest)",
    "claude-3-haiku-20240307": "Claude 3 Haiku",
    "claude-3-haiku-latest": "Claude 3 Haiku (Latest)",
}


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider for chat completions.

    Supports models: claude-3-5-sonnet, claude-3-haiku.
    Configuration: ANTHROPIC_API_KEY.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: Optional[str] = None,
    ):
        """Initialize Claude provider.

        Args:
            api_key: Anthropic API key.
            model: Model to use (default: claude-3-5-sonnet-20241022).
            base_url: Optional base URL override (unused for Claude).
        """
        super().__init__(api_key, model, base_url)
        self._client: Optional[anthropic.Anthropic] = None

    def _get_client(self) -> anthropic.Anthropic:
        """Lazy-initialize and return the Anthropic client."""
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a chat completion using Anthropic Claude API.

        Claude API requires separating the system message from the
        messages list. This method handles that conversion automatically.

        Args:
            messages: List of message dicts with 'role' and 'content'.
                Supports 'system', 'user', 'assistant' roles.
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

            # Extract system message (Claude API handles it separately)
            system_message = ""
            chat_messages = []
            for msg in messages:
                if msg["role"] == "system":
                    system_message = msg["content"]
                else:
                    chat_messages.append(msg)

            # Ensure messages alternate and start with user
            if not chat_messages:
                chat_messages = [{"role": "user", "content": "Hello"}]

            # Build API call kwargs
            kwargs = {
                "model": self._model,
                "messages": chat_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if system_message:
                kwargs["system"] = system_message

            response = client.messages.create(**kwargs)

            # Extract text from response content blocks
            result = ""
            for block in response.content:
                if hasattr(block, "text"):
                    result += block.text
            return result

        except anthropic.AuthenticationError as e:
            raise APIKeyError(
                f"Anthropic API key is invalid. Please check ANTHROPIC_API_KEY. ({e})"
            ) from e

        except anthropic.RateLimitError as e:
            raise RateLimitError(
                f"Anthropic rate limit exceeded. Please wait and try again. ({e})"
            ) from e

        except anthropic.APIConnectionError as e:
            raise NetworkError(
                f"Failed to connect to Anthropic API. Check your network. ({e})"
            ) from e

        except anthropic.APITimeoutError as e:
            raise NetworkError(
                f"Anthropic API request timed out. ({e})"
            ) from e

        except anthropic.NotFoundError as e:
            raise ModelNotFoundError(
                f"Model '{self._model}' not found. Supported: {list(SUPPORTED_MODELS.keys())}. ({e})"
            ) from e

        except anthropic.APIStatusError as e:
            raise LLMProviderError(
                f"Anthropic API error (status {e.status_code}): {e.message}"
            ) from e

        except anthropic.APIError as e:
            raise LLMProviderError(f"Anthropic API error: {e}") from e

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
        if not self._api_key or self._api_key.startswith("sk-ant-your"):
            return False
        return True

    def get_supported_models(self) -> List[str]:
        """Get list of supported Claude models.

        Returns:
            List of supported model identifiers.
        """
        return list(SUPPORTED_MODELS.keys())
