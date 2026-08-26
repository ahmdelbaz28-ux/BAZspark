"""
B1 regression tests — unified LLM ProviderRegistry.

Covers the Stage-B1 acceptance surface:
  * registry protocol checks (register/resolve/list_available)
  * env-driven configuration incl. legacy back-compat and single-key discovery
  * hot reload under lock with client drain
  * shared retry policy: transient + 429/5xx retried (Retry-After honored),
    other 4xx surfaced immediately
  * per-family adapters return tagged responses / correct event shapes:
    openai_compatible, azure, anthropic (native wire), gemini (fake client)
  * SSRF gate on base URLs

Run:
    pytest backend/tests/test_b1_provider_registry.py -q
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


def _clean_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    _provider_keys = (
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
        "XAI_API_KEY",
        "MISTRAL_API_KEY",
        "DEEPSEEK_API_KEY",
        "COHERE_API_KEY",
        "OPENROUTER_API_KEY",
        "KILOCODE_API_KEY",
        "OPENCODE_API_KEY",
        "NVIDIA_API_KEY",
        "GROQ_API_KEY",
        "TOGETHER_API_KEY",
        "FIREWORKS_API_KEY",
        "DEEPINFRA_API_KEY",
        "CEREBRAS_API_KEY",
        "SAMBANOVA_API_KEY",
        "PERPLEXITY_API_KEY",
        "DASHSCOPE_API_KEY",
        "MOONSHOT_API_KEY",
        "ZHIPU_API_KEY",
    )
    for key in _provider_keys:
        monkeypatch.delenv(key, raising=False)


# ── SSRF gate ────────────────────────────────────────────────────────────────


class TestAdapterURLValidation:
    def test_cloud_kinds_require_https(self) -> None:
        from backend.services.providers.adapters import validate_adapter_base_url

        assert validate_adapter_base_url("anthropic", "https://api.anthropic.com")
        with pytest.raises(ValueError, match="HTTPS is required"):
            validate_adapter_base_url("anthropic", "http://api.anthropic.com")
        with pytest.raises(ValueError, match="HTTPS is required"):
            validate_adapter_base_url("gemini", "http://generativelanguage.googleapis.com")

    def test_loopback_http_allowed_for_openai_compatible(self) -> None:
        from backend.services.providers.adapters import validate_adapter_base_url

        url = validate_adapter_base_url("openai_compatible", "http://localhost:11434/v1")
        assert url == "http://localhost:11434/v1"

    def test_remote_plain_http_rejected(self) -> None:
        from backend.services.providers.adapters import validate_adapter_base_url

        with pytest.raises(ValueError, match="SSRF_BLOCKED"):
            validate_adapter_base_url("openai_compatible", "http://internal-vllm.corp/v1")

    def test_metadata_hosts_always_rejected(self) -> None:
        from backend.services.providers.adapters import validate_adapter_base_url

        with pytest.raises(ValueError, match="metadata"):
            validate_adapter_base_url("openai_compatible", "https://169.254.169.254/v1")

    def test_invalid_scheme_rejected(self) -> None:
        from backend.services.providers.adapters import validate_adapter_base_url

        with pytest.raises(ValueError, match="Invalid base_url"):
            validate_adapter_base_url("openai_compatible", "ftp://example.com")


# ── Retry policy ─────────────────────────────────────────────────────────────


class TestRetryPolicy:
    def test_429_then_success_is_retried_with_retry_after(self) -> None:
        from backend.services.providers.adapters import run_with_retry

        calls = {"n": 0}
        sleeps: list[float] = []

        async def _op() -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                from backend.services.providers.adapters import _TransientHTTPError

                raise _TransientHTTPError(429, retry_after=0.01)
            return "ok"

        async def _fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        with patch("asyncio.sleep", side_effect=_fake_sleep):
            result = asyncio.run(run_with_retry(_op))
        assert result == "ok"
        assert calls["n"] == 2
        assert sleeps == [0.01]  # Retry-After honored exactly

    def test_500_retried_exponentially(self) -> None:
        from backend.services.providers.adapters import run_with_retry

        attempts = {"n": 0}

        async def _op() -> None:
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise httpx.HTTPStatusError(
                    "boom",
                    request=httpx.Request("GET", "https://x"),
                    response=httpx.Response(status_code=500, headers={"retry-after": "0"}),
                )
            return

        asyncio.run(run_with_retry(_op, attempts=3))
        assert attempts["n"] == 3

    def test_401_not_retried(self) -> None:
        from backend.services.providers.adapters import run_with_retry

        attempts = {"n": 0}

        async def _op() -> None:
            attempts["n"] += 1
            raise httpx.HTTPStatusError(
                "unauthorized",
                request=httpx.Request("GET", "https://x"),
                response=httpx.Response(status_code=401),
            )

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(run_with_retry(_op, attempts=3))
        assert attempts["n"] == 1  # surfaced immediately


# ── Registry ─────────────────────────────────────────────────────────────────


class TestRegistryBasics:
    def _fresh_registry(self):
        from backend.services.providers.registry import LLMProviderRegistry

        return LLMProviderRegistry()

    def test_register_resolve_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.providers.adapters import OpenAICompatibleAdapter

        _clean_provider_env(monkeypatch)
        reg = self._fresh_registry()
        adapter = OpenAICompatibleAdapter(
            name="test-prov", api_key="k", base_url="https://zenmux.ai/api/v1",
            model="m", timeout=5.0, max_tokens=100,
        )
        reg.register("test-prov", adapter)
        assert reg.resolve("test-prov") is adapter
        assert reg.list_available() == ["test-prov"]
        asyncio.run(reg.aclose_all())

    def test_register_rejects_non_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _clean_provider_env(monkeypatch)
        reg = self._fresh_registry()
        with pytest.raises(TypeError, match="adapter protocol"):
            reg.register("bad", object())  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="non-empty"):
            reg.register("", object())  # type: ignore[arg-type]

    def test_env_driven_chain_ordering(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDERS", "alpha,beta")
        monkeypatch.setenv("LLM_ALPHA_KIND", "openai_compatible")
        monkeypatch.setenv("LLM_ALPHA_API_KEY", "a-key")
        monkeypatch.setenv("LLM_ALPHA_MODEL", "m-alpha")
        monkeypatch.setenv("LLM_BETA_KIND", "gemini")
        monkeypatch.setenv("LLM_BETA_API_KEY", "b-key")

        reg = LLMProviderRegistry()
        try:
            assert reg.list_available() == ["alpha", "beta"]
            alpha = reg.resolve("alpha")
            beta = reg.resolve("beta")
            assert alpha is not None and beta is not None
            assert alpha.default_model == "m-alpha"
            assert beta.capabilities.kind == "gemini"
        finally:
            asyncio.run(reg.aclose_all())

    def test_unknown_kind_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDERS", "weird")
        monkeypatch.setenv("LLM_WEIRD_KIND", "telepathy")
        with pytest.raises(ValueError, match="unknown KIND"):
            LLMProviderRegistry()

    def test_max_tokens_hard_cap(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDERS", "p")
        monkeypatch.setenv("LLM_P_API_KEY", "k")
        monkeypatch.setenv("LLM_P_MAX_TOKENS", "99999")
        configs = LLMProviderRegistry.configs_from_env()
        assert configs[0].max_tokens == 8000


class TestLegacyBackcompatConfig:
    def test_legacy_zenmux_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("ZENMUX_API_KEY", "sk-z")
        configs = LLMProviderRegistry.configs_from_env()
        assert [c.name for c in configs] == ["zenmux"]
        assert configs[0].kind == "openai_compatible"
        assert configs[0].base_url == "https://zenmux.ai/api/v1"

    def test_legacy_full_chain_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("ZENMUX_API_KEY", "sk-z")
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-f")
        configs = LLMProviderRegistry.configs_from_env()
        assert [c.name for c in configs] == ["zenmux", "aliyun-maas"]

    def test_fallback_disabled_stays_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("ZENMUX_API_KEY", "sk-z")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-f")
        configs = LLMProviderRegistry.configs_from_env()
        assert [c.name for c in configs] == ["zenmux"]

    def test_single_key_discovery(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """THE headline promise: add one key → one working provider."""
        from backend.services.providers.registry import LLMProviderRegistry

        cases = [
            ("OPENAI_API_KEY", "openai", "openai_compatible"),
            ("ANTHROPIC_API_KEY", "anthropic", "anthropic"),
            ("GEMINI_API_KEY", "gemini", "gemini"),
            ("XAI_API_KEY", "xai", "openai_compatible"),
            ("DEEPSEEK_API_KEY", "deepseek", "openai_compatible"),
            ("MISTRAL_API_KEY", "mistral", "openai_compatible"),
            ("COHERE_API_KEY", "cohere", "openai_compatible"),
        ]
        for env_var, expected_name, expected_kind in cases:
            _clean_provider_env(monkeypatch)
            monkeypatch.setenv(env_var, "k-" + expected_name)
            configs = LLMProviderRegistry.configs_from_env()
            assert len(configs) == 1
            assert configs[0].name == expected_name
            assert configs[0].kind == expected_kind
            # A discovered provider must always carry a usable endpoint.
            assert configs[0].base_url.startswith("https://")

    def test_azure_needs_explicit_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A deployment URL cannot be derived from the key — must stay off."""
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "azure-key")
        assert LLMProviderRegistry.configs_from_env() == []

        monkeypatch.setenv(
            "LLM_AZURE_BASE_URL", "https://myres.openai.azure.com"
        )
        monkeypatch.setenv("LLM_AZURE_MODEL", "fireai-deployment")
        configs = LLMProviderRegistry.configs_from_env()
        assert [c.name for c in configs] == ["azure"]
        assert configs[0].model == "fireai-deployment"

    def test_requested_provider_catalog(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """User-requested catalog: OpenCode / KiloCode / OpenRouter / NVIDIA
        and the wider roster are all key-enabled with real endpoints."""
        from backend.services.providers.registry import LLMProviderRegistry

        requested = {
            "OPENCODE_API_KEY": ("opencode", "https://opencode.ai/zen/v1/"),
            "KILOCODE_API_KEY": ("kilocode", "https://api.kilocode.ai/v1"),
            "OPENROUTER_API_KEY": ("openrouter", "https://openrouter.ai/api/v1"),
            "NVIDIA_API_KEY": ("nvidia", "https://integrate.api.nvidia.com/v1"),
            "GROQ_API_KEY": ("groq", "https://api.groq.com/openai/v1"),
            "TOGETHER_API_KEY": ("together", "https://api.together.xyz/v1"),
            "FIREWORKS_API_KEY": ("fireworks", "https://api.fireworks.ai/inference/v1"),
            "DEEPINFRA_API_KEY": ("deepinfra", "https://api.deepinfra.com/v1/openai"),
            "CEREBRAS_API_KEY": ("cerebras", "https://api.cerebras.ai/v1"),
            "SAMBANOVA_API_KEY": ("sambanova", "https://api.sambanova.ai/v1"),
            "PERPLEXITY_API_KEY": ("perplexity", "https://api.perplexity.ai"),
            "DASHSCOPE_API_KEY": (
                "dashscope",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            "MOONSHOT_API_KEY": ("moonshot", "https://api.moonshot.cn/v1"),
            "ZHIPU_API_KEY": ("zhipu", "https://open.bigmodel.cn/api/paas/v4"),
        }
        for env_var, (name, base_url) in requested.items():
            _clean_provider_env(monkeypatch)
            monkeypatch.setenv(env_var, "k-" + name)
            configs = LLMProviderRegistry.configs_from_env()
            assert len(configs) == 1, env_var
            assert configs[0].name == name, env_var
            assert configs[0].base_url == base_url, env_var
            assert configs[0].model, f"{env_var} must default a model"

    def test_multiple_keys_build_ordered_chain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Several keys at once → ordered fallback chain, first = primary."""
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("GROQ_API_KEY", "gsk")
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi")
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or")
        names = [c.name for c in LLMProviderRegistry.configs_from_env()]
        # Catalog order defines priority: aggregators before GPU hosts.
        assert names == ["openrouter", "nvidia", "groq"]

    def test_per_provider_overrides(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM_<NAME>_BASE_URL/_MODEL override catalog defaults per provider."""
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi")
        monkeypatch.setenv("LLM_NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
        monkeypatch.setenv("LLM_NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        configs = LLMProviderRegistry.configs_from_env()
        assert configs[0].model == "meta/llama-3.3-70b-instruct"


class TestHotReload:
    def test_reload_picks_up_new_env_and_drains_old(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDERS", "old")
        monkeypatch.setenv("LLM_OLD_API_KEY", "old-key")
        monkeypatch.setenv("LLM_OLD_BASE_URL", "https://zenmux.ai/api/v1")
        reg = LLMProviderRegistry()
        old_adapter = reg.resolve("old")
        assert old_adapter is not None
        drained = {"count": 0}

        async def _spy_close() -> None:
            drained["count"] += 1

        old_adapter.aclose = _spy_close  # type: ignore[method-assign]

        monkeypatch.setenv("LLM_PROVIDERS", "new")
        monkeypatch.setenv("LLM_NEW_API_KEY", "new-key")
        monkeypatch.setenv("LLM_NEW_BASE_URL", "https://api.openai.com/v1")
        available = reg.reload()

        assert available == ["new"]
        assert reg.resolve("old") is None
        assert reg.resolve("new") is not None
        assert drained["count"] == 1
        asyncio.run(reg.aclose_all())


# ── Adapter behaviors ────────────────────────────────────────────────────────


def _make_openai_completion(content: str = "hello", model: str = "gpt-4o") -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    choice.finish_reason = "stop"
    usage = MagicMock()
    usage.prompt_tokens = 11
    usage.completion_tokens = 7
    usage.total_tokens = 18
    completion = MagicMock()
    completion.choices = [choice]
    completion.usage = usage
    completion.model = model
    completion.model_dump.return_value = {"id": "x"}
    return completion


class TestOpenAICompatibleAdapter:
    def _adapter(self):
        from backend.services.providers.adapters import OpenAICompatibleAdapter

        return OpenAICompatibleAdapter(
            name="prov-x", api_key="k", base_url="https://zenmux.ai/api/v1",
            model="z-ai/glm-4.7", timeout=10.0, max_tokens=100,
        )

    def test_chat_tags_source_and_usage(self) -> None:
        adapter = self._adapter()
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_make_openai_completion())
        with patch.object(adapter, "_ensure_client", return_value=client):
            result = asyncio.run(adapter.chat([{"role": "user", "content": "q"}]))
        assert isinstance(result.source, str) and result.source == "prov-x"
        assert result.total_tokens == 18
        asyncio.run(adapter.aclose())

    def test_stream_event_shapes_match_a0_contract(self) -> None:
        adapter = self._adapter()
        create = AsyncMock()
        captured: dict[str, Any] = {}

        async def _stream(*args: Any, **kwargs: Any) -> Any:
            captured.update(kwargs)

            async def _gen() -> Any:
                delta_chunk = MagicMock()
                delta_chunk.choices = [MagicMock()]
                delta_chunk.choices[0].delta.content = "He"
                delta_chunk.usage = None
                usage_chunk = MagicMock()
                usage_chunk.choices = []
                usage_chunk.usage = MagicMock()
                usage_chunk.usage.prompt_tokens = 2
                usage_chunk.usage.completion_tokens = 1
                usage_chunk.usage.total_tokens = 3
                yield delta_chunk
                yield usage_chunk

            return _gen()

        create.side_effect = _stream
        client = MagicMock()
        client.chat.completions.create = create

        async def _run() -> list[dict[str, Any]]:
            events = []
            async for ev in adapter.stream([{"role": "user", "content": "q"}]):
                events.append(ev)
            return events

        with patch.object(adapter, "_ensure_client", return_value=client):
            events = asyncio.run(_run())
        assert captured.get("stream_options") == {"include_usage": True}
        assert events[0]["type"] == "chunk"
        assert events[0]["source"] == "prov-x"
        assert events[-1]["type"] == "done"
        assert events[-1]["content"] == "He"
        assert events[-1]["usage"]["total_tokens"] == 3
        asyncio.run(adapter.aclose())


class TestAnthropicAdapterWire:
    def _handler(self, respond: Any) -> httpx.MockTransport:
        return httpx.MockTransport(respond)

    def test_chat_maps_system_and_usage(self) -> None:
        from backend.services.providers.adapters import AnthropicAdapter

        seen: dict[str, Any] = {}

        def _respond(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={
                    "model": "claude-sonnet-4-5",
                    "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "Bonjour"}],
                    "usage": {"input_tokens": 5, "output_tokens": 3},
                },
            )

        adapter = AnthropicAdapter(
            name="ant", api_key="sk-ant", base_url="https://api.anthropic.com",
            model="claude-sonnet-4-5", timeout=10.0, max_tokens=64,
        )
        adapter._http = httpx.AsyncClient(transport=self._handler(_respond))
        result = asyncio.run(
            adapter.chat(
                [
                    {"role": "system", "content": "You are an engineer."},
                    {"role": "user", "content": "hi"},
                ]
            )
        )
        body = seen["body"]
        assert body["system"] == "You are an engineer."
        assert body["messages"] == [{"role": "user", "content": "hi"}]
        assert body["max_tokens"] == 64
        assert result.content == "Bonjour"
        assert result.prompt_tokens == 5
        assert result.completion_tokens == 3
        assert result.total_tokens == 8
        assert result.source == "ant"
        asyncio.run(adapter.aclose())

    def test_stream_parses_native_sse_events(self) -> None:
        from backend.services.providers.adapters import AnthropicAdapter

        sse = "\n".join(
            [
                'data: {"type":"message_start","message":{"usage":{"input_tokens":4}}}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"Sa"}}',
                'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"lam"}}',
                'data: {"type":"message_delta","usage":{"output_tokens":6}}',
                'data: {"type":"message_stop"}',
                "",
            ]
        )

        def _respond(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=sse.encode(), headers={"content-type": "text/event-stream"}
            )

        adapter = AnthropicAdapter(
            name="ant", api_key="sk-ant", base_url="https://api.anthropic.com",
            model="claude-sonnet-4-5", timeout=10.0, max_tokens=64,
        )
        adapter._http = httpx.AsyncClient(transport=self._handler(_respond))

        async def _run() -> list[dict[str, Any]]:
            events = []
            async for ev in adapter.stream([{"role": "user", "content": "q"}]):
                events.append(ev)
            return events

        events = asyncio.run(_run())
        chunks = [e for e in events if e["type"] == "chunk"]
        done = events[-1]
        assert [c["content"] for c in chunks] == ["Sa", "lam"]
        assert done["content"] == "Salam"
        assert done["usage"] == {"prompt_tokens": 4, "completion_tokens": 6, "total_tokens": 10}
        assert done["disclaimer"]
        asyncio.run(adapter.aclose())


class TestGeminiAdapter:
    def test_chat_via_fake_client(self) -> None:
        from backend.services.providers.adapters import GeminiAdapter

        adapter = GeminiAdapter(
            name="gem", api_key="gk", base_url="", model="gemini-2.0-flash",
            timeout=10.0, max_tokens=128,
        )
        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_response.text = "Marhaba"
        fake_response.usage_metadata.prompt_token_count = 9
        fake_response.usage_metadata.candidates_token_count = 4
        fake_client.aio.models.generate_content = AsyncMock(return_value=fake_response)

        with patch.object(adapter, "_ensure_client", return_value=fake_client):
            result = asyncio.run(
                adapter.chat(
                    [
                        {"role": "system", "content": "sys"},
                        {"role": "assistant", "content": "prev"},
                        {"role": "user", "content": "q"},
                    ]
                )
            )
        call_kwargs = fake_client.aio.models.generate_content.call_args.kwargs
        contents = call_kwargs["contents"]
        assert call_kwargs["config"].system_instruction == "sys"
        assert contents[0]["role"] == "model"
        assert contents[-1]["role"] == "user"
        assert result.content == "Marhaba"
        assert result.total_tokens == 13
        assert result.source == "gem"


class TestAzureAdapter:
    def test_chat_passes_deployment_as_model(self) -> None:
        from unittest.mock import patch as _patch

        from backend.services.providers.adapters import AzureOpenAIAdapter

        adapter = AzureOpenAIAdapter(
            name="azu", api_key="ak", base_url="https://res.openai.azure.com",
            model="fireai-deployment", timeout=10.0, max_tokens=100,
        )
        completions = MagicMock()
        completions.create = AsyncMock(return_value=_make_openai_completion(model="fireai-deployment"))

        class _FakeOuter:
            chat = MagicMock()

        fake_sdk_client = MagicMock()
        fake_sdk_client.chat = MagicMock()
        fake_sdk_client.chat.completions = completions
        assert fake_sdk_client.chat.completions is completions

        def _fake_azure_client(**kwargs: Any) -> MagicMock:
            assert kwargs["azure_endpoint"] == "https://res.openai.azure.com"
            assert kwargs["api_key"] == "ak"
            return fake_sdk_client

        with (
            _patch("openai.AzureOpenAI", side_effect=_fake_azure_client),
        ):
            result = asyncio.run(
                adapter.chat([{"role": "user", "content": "q"}])
            )
        assert completions.create.call_args.kwargs["model"] == "fireai-deployment"
        assert result.source == "azu"


# ── Add-a-provider integration scenario ─────────────────────────────────────


class TestAddProviderWithKeysOnlyScenario:
    def test_three_line_addition_yields_working_chain(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Documented scenario: set 3 env lines, reload, provider works."""
        from backend.services.providers.registry import LLMProviderRegistry

        _clean_provider_env(monkeypatch)
        monkeypatch.setenv("LLM_PROVIDERS", "mygroq")
        monkeypatch.setenv("LLM_MYGROQ_KIND", "openai_compatible")
        monkeypatch.setenv("LLM_MYGROQ_API_KEY", "gsk_test")
        monkeypatch.setenv("LLM_MYGROQ_BASE_URL", "https://api.groq.com/openai/v1")
        monkeypatch.setenv("LLM_MYGROQ_MODEL", "llama-3.3-70b-versatile")

        reg = LLMProviderRegistry()
        try:
            assert reg.list_available() == ["mygroq"]
            adapter = reg.resolve("mygroq")
            assert adapter is not None
            assert adapter.base_url == "https://api.groq.com/openai/v1"
            assert adapter.available is True
        finally:
            asyncio.run(reg.aclose_all())
