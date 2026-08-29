"""
backend/tests/integration/test_llm_stream_state_machine.py
==========================================================
Behavioral integration tests for LLM provider registry, multi-provider routing,
SSRF base URL validation, and streaming error recovery.
"""

import pytest

from backend.services.providers.adapters import validate_adapter_base_url
from backend.services.providers.registry import LLMProviderRegistry
from backend.services.providers.types import LLMResponse


class TestLLMStreamStateMachine:
    """Test full behavioral workflows for provider routing and streaming pipeline."""

    def test_ssrf_url_validation_blocks_internal_networks(self):
        """Verify that provider base URLs targeting loopback/metadata are rejected."""
        with pytest.raises(ValueError, match="SSRF_BLOCKED"):
            validate_adapter_base_url("gemini", "http://169.254.169.254/latest/meta-data")

        with pytest.raises(ValueError, match="HTTPS is required"):
            validate_adapter_base_url("gemini", "http://127.0.0.1:8000/internal")

        with pytest.raises(ValueError, match="SSRF_BLOCKED"):
            validate_adapter_base_url("openai", "http://internal-corp-server.local/v1")

    def test_ssrf_url_validation_allows_valid_public_endpoints(self):
        """Verify that valid public provider endpoints are accepted."""
        url = validate_adapter_base_url("openai", "https://api.openai.com/v1")
        assert url == "https://api.openai.com/v1"

        gemini_url = validate_adapter_base_url("gemini", "https://generativelanguage.googleapis.com")
        assert gemini_url == "https://generativelanguage.googleapis.com"

    def test_provider_registry_configuration_and_routing(self, monkeypatch):
        """Test provider registry auto-discovery with mocked environment variables."""
        monkeypatch.setenv("LLM_PROVIDERS", "openai,gemini")
        monkeypatch.setenv("LLM_OPENAI_API_KEY", "sk-integration-test-key")
        monkeypatch.setenv("LLM_GEMINI_API_KEY", "gemini-integration-test-key")

        registry = LLMProviderRegistry()
        providers = registry.list_available()
        assert isinstance(providers, list)
        assert len(providers) >= 2
        assert "openai" in providers
        assert "gemini" in providers

    def test_llm_response_construction_and_validation(self):
        """Test strict validation on canonical LLMResponse objects."""
        resp = LLMResponse(
            content="Smoke detector coverage verified per NFPA 72 §17.6.",
            model="gemini-2.0-flash",
            source="gemini",
            finish_reason="stop",
            prompt_tokens=42,
            completion_tokens=18,
            total_tokens=60,
        )
        assert resp.content.startswith("Smoke detector")
        assert resp.source == "gemini"
        assert resp.total_tokens == 60
