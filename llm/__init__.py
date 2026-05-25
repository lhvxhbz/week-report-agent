"""LLM provider abstraction layer.

Provides a unified interface for multiple LLM providers including
OpenAI, Anthropic Claude, Alibaba Bailian, and custom OpenAI-compatible APIs.
"""

from .base import (
    LLMProvider,
    LLMProviderError,
    APIKeyError,
    RateLimitError,
    NetworkError,
    ModelNotFoundError,
)
from .openai_provider import OpenAIProvider
from .claude_provider import ClaudeProvider
from .bailian_provider import BailianProvider
from .custom_provider import CustomProvider
from .factory import (
    create_provider,
    get_configured_providers,
    get_available_providers,
    PROVIDER_REGISTRY,
)

__all__ = [
    # Base
    "LLMProvider",
    "LLMProviderError",
    "APIKeyError",
    "RateLimitError",
    "NetworkError",
    "ModelNotFoundError",
    # Providers
    "OpenAIProvider",
    "ClaudeProvider",
    "BailianProvider",
    "CustomProvider",
    # Factory
    "create_provider",
    "get_configured_providers",
    "get_available_providers",
    "PROVIDER_REGISTRY",
]
