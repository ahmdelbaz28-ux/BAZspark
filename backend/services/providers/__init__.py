"""
backend/services/providers/ — Unified LLM Provider Registry (Stage B1).

Adding an LLM provider is now configuration-only:

    LLM_PROVIDERS=primary,fallback
    LLM_PRIMARY_KIND=openai_compatible      # or anthropic|gemini|azure
    LLM_PRIMARY_API_KEY=sk-...
    LLM_PRIMARY_MODEL=gpt-4o

See registry.py for the full variable matrix and back-compat rules.
"""

from backend.services.providers.adapters import (
    ADAPTER_KINDS,
    AnthropicAdapter,
    AzureOpenAIAdapter,
    BaseLLMAdapter,
    GeminiAdapter,
    OpenAICompatibleAdapter,
    ProviderCapabilities,
)
from backend.services.providers.registry import (
    LLMProviderRegistry,
    ProviderConfig,
    close_provider_registry,
    get_provider_registry,
)
from backend.services.providers.types import LLMResponse

__all__ = [
    "ADAPTER_KINDS",
    "AnthropicAdapter",
    "AzureOpenAIAdapter",
    "BaseLLMAdapter",
    "GeminiAdapter",
    "LLMProviderRegistry",
    "LLMResponse",
    "OpenAICompatibleAdapter",
    "ProviderCapabilities",
    "ProviderConfig",
    "close_provider_registry",
    "get_provider_registry",
]
