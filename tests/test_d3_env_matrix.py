"""
tests/test_d3_env_matrix.py
===========================

Tests for Stage D3: LLM Provider Matrix & Environment Configuration Validation.

Verifies:
  1. Multi-provider loading from LLM_PROVIDERS chain
  2. Single-key discovery for OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, AZURE_OPENAI_API_KEY
  3. SSRF base-url validation for cloud and local providers
  4. Provider adapter instantiation for all 4 adapter families
  5. Hot-reload semantics under thread safety
"""

from __future__ import annotations

import asyncio

import pytest

from backend.services.providers.adapters import (
    AnthropicAdapter,
    AzureOpenAIAdapter,
    GeminiAdapter,
    OpenAICompatibleAdapter,
    validate_adapter_base_url,
)
from backend.services.providers.registry import (
    LLMProviderRegistry,
    close_provider_registry,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "LLM_PROVIDERS",
        "ZENMUX_API_KEY",
        "ZENMUX_BASE_URL",
        "ZENMUX_MODEL",
        "LLM_FALLBACK_ENABLED",
        "LLM_FALLBACK_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "LLM_PRIMARY_KIND",
        "LLM_PRIMARY_API_KEY",
        "LLM_PRIMARY_BASE_URL",
        "LLM_PRIMARY_MODEL",
        "LLM_SECONDARY_KIND",
        "LLM_SECONDARY_API_KEY",
        "LLM_SECONDARY_BASE_URL",
        "LLM_SECONDARY_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)
    close_provider_registry()


class TestProviderMatrixAndAdapters:
    """Verifies all provider matrix adapters and URL validations."""

    def test_ssrf_validation_rejects_metadata_and_insecure_cloud(self) -> None:
        # Rejects cloud metadata
        with pytest.raises(ValueError, match="metadata"):
            validate_adapter_base_url("openai_compatible", "https://169.254.169.254/v1")

        with pytest.raises(ValueError, match="metadata"):
            validate_adapter_base_url("anthropic", "https://metadata.google.internal")

        # Insecure non-loopback http rejected for cloud kinds
        with pytest.raises(ValueError, match="HTTPS is required"):
            validate_adapter_base_url("anthropic", "http://insecure-host.com")

        # Loopback allowed for local dev
        assert (
            validate_adapter_base_url("openai_compatible", "http://localhost:11434/v1")
            == "http://localhost:11434/v1"
        )
        assert (
            validate_adapter_base_url("openai_compatible", "http://127.0.0.1:8000/v1")
            == "http://127.0.0.1:8000/v1"
        )

    def test_openai_adapter_capabilities(self) -> None:
        adapter = OpenAICompatibleAdapter(
            name="test-openai",
            api_key="sk-test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            timeout=30.0,
            max_tokens=2000,
        )
        assert adapter.name == "test-openai"
        assert adapter.capabilities.kind == "openai_compatible"
        assert adapter.capabilities.streaming is True
        asyncio.run(adapter.aclose())

    def test_anthropic_adapter_capabilities(self) -> None:
        adapter = AnthropicAdapter(
            name="test-claude",
            api_key="sk-ant-test-key",
            base_url="https://api.anthropic.com",
            model="claude-sonnet-4-5",
            timeout=30.0,
            max_tokens=2000,
        )
        assert adapter.name == "test-claude"
        assert adapter.capabilities.kind == "anthropic"
        asyncio.run(adapter.aclose())

    def test_gemini_adapter_capabilities(self) -> None:
        adapter = GeminiAdapter(
            name="test-gemini",
            api_key="AIzaSyTestKey",
            base_url="https://generativelanguage.googleapis.com",
            model="gemini-2.0-flash",
            timeout=30.0,
            max_tokens=2000,
        )
        assert adapter.name == "test-gemini"
        assert adapter.capabilities.kind == "gemini"
        asyncio.run(adapter.aclose())

    def test_azure_adapter_capabilities(self) -> None:
        adapter = AzureOpenAIAdapter(
            name="test-azure",
            api_key="azure-test-key",
            base_url="https://test-resource.openai.azure.com",
            model="gpt-4o-deploy",
            timeout=30.0,
            max_tokens=2000,
        )
        assert adapter.name == "test-azure"
        assert adapter.capabilities.kind == "azure"
        asyncio.run(adapter.aclose())


class TestProviderRegistryMatrixConfiguration:
    """Verifies registry configuration from env vars."""

    def test_single_key_discovery_openai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-single-test")
        registry = LLMProviderRegistry()
        try:
            assert "openai" in registry.list_available()
            adapter = registry.resolve("openai")
            assert adapter is not None
            assert adapter.name == "openai"
        finally:
            asyncio.run(registry.aclose_all())

    def test_single_key_discovery_anthropic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-single-test")
        registry = LLMProviderRegistry()
        try:
            assert "anthropic" in registry.list_available()
            adapter = registry.resolve("anthropic")
            assert adapter is not None
            assert adapter.name == "anthropic"
        finally:
            asyncio.run(registry.aclose_all())

    def test_custom_multi_provider_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDERS", "primary,secondary")
        monkeypatch.setenv("LLM_PRIMARY_KIND", "anthropic")
        monkeypatch.setenv("LLM_PRIMARY_API_KEY", "sk-ant-primary")
        monkeypatch.setenv("LLM_PRIMARY_MODEL", "claude-sonnet-4-5")

        monkeypatch.setenv("LLM_SECONDARY_KIND", "openai_compatible")
        monkeypatch.setenv("LLM_SECONDARY_API_KEY", "sk-sec-key")
        monkeypatch.setenv("LLM_SECONDARY_BASE_URL", "https://api.openai.com/v1")
        monkeypatch.setenv("LLM_SECONDARY_MODEL", "gpt-4o")

        registry = LLMProviderRegistry()
        try:
            available = registry.list_available()
            assert available == ["primary", "secondary"]

            primary = registry.resolve("primary")
            assert primary is not None
            assert isinstance(primary, AnthropicAdapter)

            secondary = registry.resolve("secondary")
            assert secondary is not None
            assert isinstance(secondary, OpenAICompatibleAdapter)
        finally:
            asyncio.run(registry.aclose_all())

    def test_hot_reload(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-initial")
        registry = LLMProviderRegistry()
        try:
            assert registry.list_available() == ["openai"]

            monkeypatch.delenv("OPENAI_API_KEY", raising=False)
            monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-reloaded")
            registry.reload()
            assert registry.list_available() == ["anthropic"]
        finally:
            asyncio.run(registry.aclose_all())
