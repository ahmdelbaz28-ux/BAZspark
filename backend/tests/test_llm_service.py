"""
Unit tests for backend/services/llm_service.py.

These tests verify the LLMService class behavior WITHOUT making real API
calls. They use monkeypatching to mock the OpenAI client.

Run:
    pytest backend/tests/test_llm_service.py -v
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend package is importable
# Real provider keys from the developer/CI environment must never leak
# into unit tests (single-key discovery would otherwise build live
# providers and make real network calls).
_PROVIDER_KEY_VARS = (
    "LLM_PROVIDERS",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "NVIDIA_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "TOGETHER_API_KEY",
    "FIREWORKS_API_KEY",
    "DEEPINFRA_API_KEY",
    "CEREBRAS_API_KEY",
    "SAMBANOVA_API_KEY",
    "PERPLEXITY_API_KEY",
    "DASHSCOPE_API_KEY",
    "MOONSHOT_API_KEY",
    "ZHIPU_API_KEY",
    "XAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "MISTRAL_API_KEY",
    "COHERE_API_KEY",
    "OPENCODE_API_KEY",
    "KILOCODE_API_KEY",
    "ZENMUX_API_KEY",
)

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all ZENMUX_* env vars before each test."""
    # list() snapshot is required: monkeypatch.delenv mutates os.environ
    # during iteration, which would raise RuntimeError without it.
    for key in list(os.environ.keys()):  # noqa: S7504 — intentional snapshot
        if key.startswith("ZENMUX_") or key in _PROVIDER_KEY_VARS:
            monkeypatch.delenv(key, raising=False)
    # Also reset BOTH singletons (B2: the provider registry caches adapters
    # built from the environment at first use).
    import backend.services.llm_service as mod
    import backend.services.providers.registry as prov_registry

    mod._llm_service = None
    prov_registry._registry = None
    yield
    mod._llm_service = None
    prov_registry._registry = None


@pytest.fixture
def configured_env(clean_env, monkeypatch):
    """Set up valid ZENMUX env vars."""
    monkeypatch.setenv("ZENMUX_API_KEY", "sk-test-key-12345")
    monkeypatch.setenv("ZENMUX_BASE_URL", "https://zenmux.ai/api/v1")
    monkeypatch.setenv("ZENMUX_MODEL", "z-ai/glm-4.7")
    monkeypatch.setenv("ZENMUX_REQUEST_TIMEOUT", "30")
    monkeypatch.setenv("ZENMUX_MAX_TOKENS", "1000")


# ── LLMResponse dataclass tests ──────────────────────────────────────────────


class TestLLMResponse:
    def test_default_source_is_zenmux(self):
        from backend.services.llm_service import LLMResponse

        r = LLMResponse(content="hello", model="z-ai/glm-4.7")
        assert r.source == "zenmux"
        assert r.content == "hello"
        assert r.model == "z-ai/glm-4.7"
        assert r.finish_reason == "stop"
        assert r.prompt_tokens == 0
        assert r.completion_tokens == 0
        assert r.total_tokens == 0

    def test_is_frozen(self):
        from backend.services.llm_service import LLMResponse

        r = LLMResponse(content="hello", model="m")
        with pytest.raises((AttributeError, Exception)):
            r.content = "changed"  # type: ignore[misc]

    def test_raw_defaults_to_empty_dict(self):
        from backend.services.llm_service import LLMResponse

        r = LLMResponse(content="hello", model="m")
        assert r.raw == {}


# ── LLMService configuration tests ───────────────────────────────────────────


class TestLLMServiceConfig:
    def test_unavailable_when_no_api_key(self, clean_env):
        from backend.services.llm_service import LLMService

        svc = LLMService()
        assert svc.available is False
        assert svc.base_url == "https://zenmux.ai/api/v1"
        assert svc.default_model == "z-ai/glm-4.7"

    def test_available_when_api_key_set(self, configured_env):
        from backend.services.llm_service import LLMService

        svc = LLMService()
        assert svc.available is True
        assert svc.base_url == "https://zenmux.ai/api/v1"
        assert svc.default_model == "z-ai/glm-4.7"

    def test_custom_base_url(self, clean_env, monkeypatch):
        monkeypatch.setenv("ZENMUX_API_KEY", "k")
        monkeypatch.setenv("ZENMUX_BASE_URL", "https://custom.example.com/v1")
        from backend.services.llm_service import LLMService

        svc = LLMService()
        assert svc.base_url == "https://custom.example.com/v1"

    def test_custom_model(self, clean_env, monkeypatch):
        monkeypatch.setenv("ZENMUX_API_KEY", "k")
        monkeypatch.setenv("ZENMUX_MODEL", "anthropic/claude-fable-5-free")
        from backend.services.llm_service import LLMService

        svc = LLMService()
        assert svc.default_model == "anthropic/claude-fable-5-free"

    def test_custom_timeout(self, clean_env, monkeypatch):
        monkeypatch.setenv("ZENMUX_API_KEY", "k")
        monkeypatch.setenv("ZENMUX_REQUEST_TIMEOUT", "120")
        from backend.services.llm_service import LLMService

        svc = LLMService()
        adapter = svc._registry.resolve("zenmux")
        assert adapter is not None
        assert adapter.timeout == pytest.approx(120.0)


# ── LLMService.chat tests (mocked) ───────────────────────────────────────────


class TestLLMServiceChat:
    def test_chat_raises_when_not_configured(self, clean_env):
        import asyncio

        from backend.services.llm_service import LLMService

        svc = LLMService()

        # there is no running loop. Use asyncio.run() which creates + closes
        # a new event loop automatically.
        async def _raise():
            with pytest.raises(RuntimeError, match="ZENMUX_API_KEY"):
                await svc.chat("hello")

        asyncio.run(_raise())

    def test_chat_raises_on_empty_prompt(self, configured_env):
        from backend.services.llm_service import LLMService

        svc = LLMService()
        import asyncio

        async def run():
            with pytest.raises(ValueError, match="non-empty"):
                await svc.chat("")

        asyncio.run(run())

    def test_chat_returns_response(self, configured_env):
        """Mock the OpenAI client and verify chat() returns LLMResponse."""
        from backend.services.llm_service import LLMService

        svc = LLMService()

        # Build a mock completion response
        mock_message = MagicMock()
        mock_message.content = "NFPA 72 spacing is 9.1m."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_choice.finish_reason = "stop"
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 20
        mock_usage.completion_tokens = 10
        mock_usage.total_tokens = 30
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.usage = mock_usage
        # so hasattr(completion, 'model') is always True. Without this explicit
        # set, completion.model returns a MagicMock object instead of a string,
        # causing: assert <MagicMock> == 'z-ai/glm-4.7' → AssertionError
        mock_completion.model = "z-ai/glm-4.7"
        mock_completion.model_dump.return_value = {"id": "chatcmpl-123"}

        # Mock the client
        mock_client = MagicMock()
        mock_create = AsyncMock(return_value=mock_completion)
        mock_client.chat.completions.create = mock_create

        # B2: the adapter owns the client now - patch it there.
        primary = svc._registry.resolve("zenmux")
        assert primary is not None
        with patch.object(primary, "_ensure_client", return_value=mock_client):
            import asyncio

            async def run():
                return await svc.chat("What is NFPA 72 spacing?", system="You are an engineer.")

            result = asyncio.run(run())

        assert result.content == "NFPA 72 spacing is 9.1m."
        assert result.model == "z-ai/glm-4.7"
        assert result.source == "zenmux"  # primary provider name
        assert result.finish_reason == "stop"
        assert result.prompt_tokens == 20
        assert result.completion_tokens == 10
        assert result.total_tokens == 30

        # Verify the create() was called with correct args
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == "z-ai/glm-4.7"
        assert call_kwargs["temperature"] == pytest.approx(0.1)
        assert len(call_kwargs["messages"]) == 2
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][1]["role"] == "user"

    def test_chat_uses_model_override(self, configured_env):
        from backend.services.llm_service import LLMService

        svc = LLMService()
        mock_completion = MagicMock()
        mock_completion.choices = []
        mock_completion.usage = None
        mock_completion.model_dump.return_value = {}

        mock_client = MagicMock()
        mock_create = AsyncMock(return_value=mock_completion)
        mock_client.chat.completions.create = mock_create

        primary = svc._registry.resolve("zenmux")
        assert primary is not None
        with patch.object(primary, "_ensure_client", return_value=mock_client):
            import asyncio

            async def run():
                return await svc.chat("hi", model="z-ai/glm-4.7-flash-free")

            asyncio.run(run())

        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["model"] == "z-ai/glm-4.7-flash-free"


# ── LLMService.health tests ──────────────────────────────────────────────────


class TestLLMServiceHealth:
    def test_health_unconfigured(self, clean_env):
        from backend.services.llm_service import LLMService

        svc = LLMService()
        import asyncio

        async def run():
            return await svc.health()

        result = asyncio.run(run())
        assert result["available"] is False
        assert "primary" in result
        assert "fallback" in result
        assert "timeout_s" in result

    def test_health_configured(self, configured_env):
        from backend.services.llm_service import LLMService

        svc = LLMService()
        import asyncio

        async def run():
            return await svc.health()

        result = asyncio.run(run())
        assert result["available"] is True
        assert result["primary"]["name"] == "zenmux"
        assert result["primary"]["available"] is True
        assert result["primary"]["base_url"] == "https://zenmux.ai/api/v1"
        assert result["primary"]["model"] == "z-ai/glm-4.7"
        assert result["fallback"]["name"] == "aliyun-maas"
        assert result["fallback"]["enabled"] is False


# ── Singleton tests ──────────────────────────────────────────────────────────


class TestSingleton:
    def test_get_llm_service_returns_same_instance(self, clean_env):
        from backend.services.llm_service import get_llm_service

        svc1 = get_llm_service()
        svc2 = get_llm_service()
        assert svc1 is svc2

    def test_singleton_picks_up_env_changes_after_reset(self, clean_env, monkeypatch):
        import backend.services.llm_service as mod
        import backend.services.providers.registry as prov_registry

        monkeypatch.setenv("ZENMUX_API_KEY", "key-1")
        svc1 = mod.get_llm_service()
        assert svc1.available is True

        # Reset BOTH singletons (B2: the provider registry caches adapters).
        mod._llm_service = None
        prov_registry._registry = None

        # Change env
        monkeypatch.setenv("ZENMUX_API_KEY", "key-2")
        svc2 = mod.get_llm_service()
        assert svc2 is not svc1
        adapter = svc2._registry.resolve("zenmux")
        assert adapter is not None
        assert adapter.api_key == "key-2"


# ── Fallback provider tests ──────────────────────────────────────────────────


class TestFallbackProvider:
    def test_fallback_disabled_by_default(self, configured_env):
        from backend.services.llm_service import LLMService

        svc = LLMService()
        assert svc.fallback_available is False

    def test_fallback_enabled_when_configured(self, configured_env, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-ws-test")
        from backend.services.llm_service import LLMService

        svc = LLMService()
        assert svc.fallback_available is True
        fallback = svc._registry.resolve("aliyun-maas")
        assert fallback is not None
        assert fallback.default_model == "qwen-plus-latest"

    def test_fallback_used_when_primary_fails(self, configured_env, monkeypatch):
        """If primary provider raises, fallback should be tried."""
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-ws-test")
        from backend.services.llm_service import LLMService

        svc = LLMService()

        # Mock: primary raises, fallback succeeds
        mock_fallback_completion = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = "Fallback response"
        mock_choice = MagicMock()
        mock_choice.message = mock_msg
        mock_choice.finish_reason = "stop"
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 5
        mock_usage.completion_tokens = 5
        mock_usage.total_tokens = 10
        mock_fallback_completion.choices = [mock_choice]
        mock_fallback_completion.usage = mock_usage
        mock_fallback_completion.model_dump.return_value = {}

        mock_primary_client = MagicMock()
        mock_primary_client.chat.completions.create = AsyncMock(
            side_effect=RuntimeError("primary failed")
        )
        mock_fallback_client = MagicMock()
        mock_fallback_client.chat.completions.create = AsyncMock(
            return_value=mock_fallback_completion
        )

        # B2: patch each adapter's client instead of the removed _get_client.
        primary = svc._registry.resolve("zenmux")
        fallback = svc._registry.resolve("aliyun-maas")
        assert primary is not None and fallback is not None
        with (
            patch.object(primary, "_ensure_client", return_value=mock_primary_client),
            patch.object(fallback, "_ensure_client", return_value=mock_fallback_client),
        ):
            import asyncio

            async def run():
                return await svc.chat("test prompt")

            result = asyncio.run(run())

        assert result.content == "Fallback response"
        assert result.source == "aliyun-maas"
        assert result.total_tokens == 10
