"""Configuration management for 周报终结者."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent / ".env")


class Config:
    """Application configuration loaded from environment variables."""

    # LLM Provider: openai, claude, bailian, custom
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")

    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # Claude Configuration
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

    # Alibaba Bailian Configuration
    BAILIAN_API_KEY: str = os.getenv("BAILIAN_API_KEY", "")
    BAILIAN_MODEL: str = os.getenv("BAILIAN_MODEL", "qwen-turbo")
    BAILIAN_BASE_URL: str = os.getenv(
        "BAILIAN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    # Custom OpenAI-compatible API Configuration
    CUSTOM_API_KEY: str = os.getenv("CUSTOM_API_KEY", "")
    CUSTOM_MODEL: str = os.getenv("CUSTOM_MODEL", "")
    CUSTOM_BASE_URL: str = os.getenv("CUSTOM_BASE_URL", "")

    # Application Settings
    SCAN_DIRS: str = os.getenv("SCAN_DIRS", ".")
    FILE_EXTENSIONS: str = os.getenv("FILE_EXTENSIONS", ".txt,.md,.docx,.pdf")
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.7"))

    @classmethod
    def get_api_key(cls) -> str:
        """Get API key for the configured provider."""
        provider_keys = {
            "openai": cls.OPENAI_API_KEY,
            "claude": cls.ANTHROPIC_API_KEY,
            "bailian": cls.BAILIAN_API_KEY,
            "custom": cls.CUSTOM_API_KEY,
        }
        return provider_keys.get(cls.LLM_PROVIDER, "")

    @classmethod
    def get_model(cls) -> str:
        """Get model name for the configured provider."""
        provider_models = {
            "openai": cls.OPENAI_MODEL,
            "claude": cls.ANTHROPIC_MODEL,
            "bailian": cls.BAILIAN_MODEL,
            "custom": cls.CUSTOM_MODEL,
        }
        return provider_models.get(cls.LLM_PROVIDER, "")

    @classmethod
    def get_base_url(cls) -> str:
        """Get base URL for the configured provider."""
        provider_urls = {
            "openai": cls.OPENAI_BASE_URL,
            "bailian": cls.BAILIAN_BASE_URL,
            "custom": cls.CUSTOM_BASE_URL,
        }
        return provider_urls.get(cls.LLM_PROVIDER, "")


config = Config()
