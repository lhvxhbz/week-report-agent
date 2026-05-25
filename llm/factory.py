"""LLM provider factory.

Creates the appropriate LLM provider instance based on configuration.
Auto-detects which API keys are configured.
"""

from typing import Dict, List, Optional, Type

from .base import LLMProvider
from .openai_provider import OpenAIProvider
from .claude_provider import ClaudeProvider
from .bailian_provider import BailianProvider
from .custom_provider import CustomProvider


def _get_config():
    """Lazy-load Config to avoid circular imports and path issues."""
    from config import Config
    return Config


# Registry of provider name -> class
PROVIDER_REGISTRY: Dict[str, Type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "bailian": BailianProvider,
    "custom": CustomProvider,
}

# Friendly display names
PROVIDER_DISPLAY_NAMES: Dict[str, str] = {
    "openai": "OpenAI",
    "claude": "Anthropic Claude",
    "bailian": "Alibaba Bailian (DashScope)",
    "custom": "Custom API",
}


def create_provider(provider_name: Optional[str] = None) -> LLMProvider:
    """Create an LLM provider instance based on configuration.

    Args:
        provider_name: Provider to create. If None, uses LLM_PROVIDER from config.

    Returns:
        An initialized LLMProvider instance.

    Raises:
        ValueError: If provider name is unknown.
        ValueError: If required configuration is missing.
    """
    Config = _get_config()
    name = (provider_name or Config.LLM_PROVIDER).lower().strip()

    if name not in PROVIDER_REGISTRY:
        available = ", ".join(PROVIDER_REGISTRY.keys())
        raise ValueError(
            f"Unknown LLM provider: '{name}'. Available providers: {available}"
        )

    api_key = Config.get_api_key()
    model = Config.get_model()
    base_url = Config.get_base_url()

    # Validate required configuration
    if name == "custom":
        if not Config.CUSTOM_BASE_URL:
            raise ValueError(
                "CUSTOM_BASE_URL is required for custom provider. "
                "Please set it in your .env file."
            )
        if not Config.CUSTOM_MODEL:
            raise ValueError(
                "CUSTOM_MODEL is required for custom provider. "
                "Please set it in your .env file."
            )
    elif not api_key:
        display_name = PROVIDER_DISPLAY_NAMES.get(name, name)
        env_key = _get_env_key_name(name)
        raise ValueError(
            f"{display_name} API key is not configured. "
            f"Please set {env_key} in your .env file."
        )

    # Create provider instance
    provider_class = PROVIDER_REGISTRY[name]

    if name == "custom":
        return provider_class(
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
    elif base_url:
        return provider_class(
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
    else:
        return provider_class(api_key=api_key, model=model)


def get_configured_providers() -> List[str]:
    """Detect which providers have API keys configured.

    Returns:
        List of provider names that have valid API keys configured.
    """
    Config = _get_config()
    configured = []

    # Check OpenAI
    if Config.OPENAI_API_KEY and not Config.OPENAI_API_KEY.startswith("sk-your"):
        configured.append("openai")

    # Check Claude
    if Config.ANTHROPIC_API_KEY and not Config.ANTHROPIC_API_KEY.startswith("sk-ant-your"):
        configured.append("claude")

    # Check Bailian
    if Config.BAILIAN_API_KEY and not Config.BAILIAN_API_KEY.startswith("sk-your"):
        configured.append("bailian")

    # Check Custom (needs URL + model, API key is optional)
    if Config.CUSTOM_BASE_URL and Config.CUSTOM_MODEL:
        configured.append("custom")

    return configured


def get_available_providers() -> Dict[str, Dict[str, str]]:
    """Get information about all providers and their configuration status.

    Returns:
        Dict mapping provider name to info dict with keys:
        - 'display_name': Human-readable name
        - 'configured': 'yes' or 'no'
        - 'model': Configured model name
        - 'env_key': Environment variable name for the API key
    """
    configured = set(get_configured_providers())
    result = {}

    for name in PROVIDER_REGISTRY:
        result[name] = {
            "display_name": PROVIDER_DISPLAY_NAMES.get(name, name),
            "configured": "yes" if name in configured else "no",
            "model": _get_model_for_provider(name),
            "env_key": _get_env_key_name(name),
        }

    return result


def _get_env_key_name(provider_name: str) -> str:
    """Get the environment variable name for a provider's API key.

    Args:
        provider_name: Provider name.

    Returns:
        Environment variable name string.
    """
    env_keys = {
        "openai": "OPENAI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "bailian": "BAILIAN_API_KEY",
        "custom": "CUSTOM_API_KEY",
    }
    return env_keys.get(provider_name, "")


def _get_model_for_provider(provider_name: str) -> str:
    """Get the configured model for a provider.

    Args:
        provider_name: Provider name.

    Returns:
        Model name string.
    """
    Config = _get_config()
    models = {
        "openai": Config.OPENAI_MODEL,
        "claude": Config.ANTHROPIC_MODEL,
        "bailian": Config.BAILIAN_MODEL,
        "custom": Config.CUSTOM_MODEL,
    }
    return models.get(provider_name, "")
