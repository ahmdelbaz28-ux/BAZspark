"""
backend/services/providers/registry.py — Unified LLM Provider Registry
(Stage B1 of the agent-platform rebuild).

Design (mirrors BIMProviderRegistry in fireai/bridges/bim_provider.py):

* ``LLMProviderRegistry.register(name, adapter)`` — register an adapter.
* ``LLMProviderRegistry.resolve(name)``            — lookup by name.
* ``LLMProviderRegistry.list_available()``         — configured names, in
  fallback order.

Configuration is ENV-DRIVEN ("add a provider = add keys"):

    LLM_PROVIDERS=primary,fallback,third      # names, order = fallback order
    LLM_<NAME>_KIND=openai_compatible         # default; anthropic|gemini|azure
    LLM_<NAME>_API_KEY=...
    LLM_<NAME>_BASE_URL=...
    LLM_<NAME>_MODEL=...
    LLM_<NAME>_TIMEOUT=60                     # seconds (default 60)
    LLM_<NAME>_MAX_TOKENS=2000                # default 2000, hard cap 8000

Back-compat: when ``LLM_PROVIDERS`` is absent the registry synthesizes the
legacy chain from ZENMUX_* / LLM_FALLBACK_* exactly as llm_service.py did,
plus single-provider discovery for well-known keys (OPENAI_API_KEY,
ANTHROPIC_API_KEY, GEMINI_API_KEY, AZURE_OPENAI_API_KEY) so that "add one
key" yields a working provider.

Hot reload: ``reload()`` re-reads the environment under a lock and closes
the previous adapters' HTTP clients. It is exposed via an RBAC-protected
admin endpoint (POST /admin/llm-providers/reload).
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass

from backend.services.providers.adapters import (
    ADAPTER_KINDS,
    BaseLLMAdapter,
)
from backend.services.providers.types import LLMResponse

logger = logging.getLogger(__name__)

_MAX_TOKENS_HARD_CAP = 8000
_DEFAULT_TIMEOUT = 60.0
_DEFAULT_MAX_TOKENS = 2000


@dataclass(frozen=True)
class _WellKnownProvider:
    """A provider the user can enable by setting ONE env var (the API key)."""

    env_var: str
    name: str
    kind: str
    base_url: str = ""
    model: str = ""


# Single-key discovery catalog ("add a key → it works").
# Order IS the fallback priority when several keys are set at once.
# Every default is overridable via LLM_<NAME>_BASE_URL / LLM_<NAME>_MODEL.
_WELL_KNOWN_PROVIDERS: tuple[_WellKnownProvider, ...] = (
    # ── First-party native APIs ──────────────────────────────────────────
    _WellKnownProvider("OPENAI_API_KEY", "openai", "openai_compatible",
                       "https://api.openai.com/v1", "gpt-4o"),
    _WellKnownProvider("ANTHROPIC_API_KEY", "anthropic", "anthropic",
                       "https://api.anthropic.com", "claude-sonnet-4-5"),
    _WellKnownProvider("GEMINI_API_KEY", "gemini", "gemini",
                       "https://generativelanguage.googleapis.com",
                       "gemini-2.0-flash"),
    _WellKnownProvider("GOOGLE_API_KEY", "gemini-google", "gemini",
                       "https://generativelanguage.googleapis.com",
                       "gemini-2.0-flash"),
    _WellKnownProvider("AZURE_OPENAI_API_KEY", "azure", "azure", "", ""),
    _WellKnownProvider("XAI_API_KEY", "xai", "openai_compatible",
                       "https://api.x.ai/v1", "grok-2-latest"),
    _WellKnownProvider("MISTRAL_API_KEY", "mistral", "openai_compatible",
                       "https://api.mistral.ai/v1", "mistral-large-latest"),
    _WellKnownProvider("DEEPSEEK_API_KEY", "deepseek", "openai_compatible",
                       "https://api.deepseek.com/v1", "deepseek-chat"),
    _WellKnownProvider("COHERE_API_KEY", "cohere", "openai_compatible",
                       "https://api.cohere.ai/compatibility/v1", "command-r-plus"),
    # ── Aggregators / coding-tool gateways ───────────────────────────────
    _WellKnownProvider("OPENROUTER_API_KEY", "openrouter", "openai_compatible",
                       "https://openrouter.ai/api/v1", "openai/gpt-4o"),
    _WellKnownProvider("KILOCODE_API_KEY", "kilocode", "openai_compatible",
                       "https://api.kilocode.ai/v1", "x-ai/grok-code-fast-1"),
    _WellKnownProvider("OPENCODE_API_KEY", "opencode", "openai_compatible",
                       "https://opencode.ai/zen/v1/", "gpt-4o"),
    _WellKnownProvider("ZENMUX_API_KEY", "zenmux-discovered", "openai_compatible",
                       "https://zenmux.ai/api/v1", "z-ai/glm-4.7"),
    # ── GPU clouds / inference hosts ─────────────────────────────────────
    _WellKnownProvider("NVIDIA_API_KEY", "nvidia", "openai_compatible",
                       "https://integrate.api.nvidia.com/v1",
                       "meta/llama-3.1-8b-instruct"),
    _WellKnownProvider("GROQ_API_KEY", "groq", "openai_compatible",
                       "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    _WellKnownProvider("TOGETHER_API_KEY", "together", "openai_compatible",
                       "https://api.together.xyz/v1",
                       "meta-llama/Llama-3.3-70B-Instruct-Turbo"),
    _WellKnownProvider("FIREWORKS_API_KEY", "fireworks", "openai_compatible",
                       "https://api.fireworks.ai/inference/v1",
                       "accounts/fireworks/models/llama-v3p3-70b-instruct"),
    _WellKnownProvider("DEEPINFRA_API_KEY", "deepinfra", "openai_compatible",
                       "https://api.deepinfra.com/v1/openai",
                       "meta-llama/Llama-3.3-70B-Instruct"),
    _WellKnownProvider("CEREBRAS_API_KEY", "cerebras", "openai_compatible",
                       "https://api.cerebras.ai/v1", "llama3.1-8b"),
    _WellKnownProvider("SAMBANOVA_API_KEY", "sambanova", "openai_compatible",
                       "https://api.sambanova.ai/v1",
                       "Meta-Llama-3.3-70B-Instruct"),
    _WellKnownProvider("PERPLEXITY_API_KEY", "perplexity", "openai_compatible",
                       "https://api.perplexity.ai",
                       "llama-3.1-sonar-small-128k-online"),
    # ── Regional / CN providers ──────────────────────────────────────────
    _WellKnownProvider("DASHSCOPE_API_KEY", "dashscope", "openai_compatible",
                       "https://dashscope.aliyuncs.com/compatible-mode/v1",
                       "qwen-plus-latest"),
    _WellKnownProvider("MOONSHOT_API_KEY", "moonshot", "openai_compatible",
                       "https://api.moonshot.cn/v1", "moonshot-v1-32k"),
    _WellKnownProvider("ZHIPU_API_KEY", "zhipu", "openai_compatible",
                       "https://open.bigmodel.cn/api/paas/v4", "glm-4-plus"),
)

# Back-compat alias used by older call sites/tests.
_WELL_KNOWN_KEY_VARS: tuple[tuple[str, str, str], ...] = tuple(
    (p.env_var, p.name, p.kind) for p in _WELL_KNOWN_PROVIDERS
)


@dataclass(frozen=True)
class ProviderConfig:
    """Environment-derived configuration for a single provider slot."""

    name: str
    kind: str
    api_key: str
    base_url: str
    model: str
    timeout: float = _DEFAULT_TIMEOUT
    max_tokens: int = _DEFAULT_MAX_TOKENS

    @property
    def available(self) -> bool:
        return bool(self.api_key)


class LLMProviderRegistry:
    """Thread-safe registry of named LLM adapters with hot-reload support."""

    def __init__(self) -> None:
        self._adapters: dict[str, BaseLLMAdapter] = {}
        self._order: list[str] = []
        self._lock = threading.RLock()
        self.reload()

    # ── Registration / lookup ────────────────────────────────────────────

    def register(self, name: str, adapter: BaseLLMAdapter) -> None:
        """Register an adapter instance under ``name``.

        Raises TypeError when the object does not satisfy the adapter
        protocol (chat/stream/ping/capabilities/aclose), ValueError on an
        empty name.
        """
        if not name or not isinstance(name, str):
            raise ValueError("Provider name must be a non-empty string")
        required_methods = ("chat", "stream", "ping", "capabilities", "aclose")
        for method in required_methods:
            # hasattr (not callable()) because `capabilities` is a property.
            if not hasattr(adapter, method):
                raise TypeError(
                    f"Provider '{name}' ({type(adapter).__name__}) does not "
                    f"satisfy the adapter protocol: missing '{method}'"
                )
        with self._lock:
            if name in self._order:
                old = self._adapters.get(name)
                if old is not None and old is not adapter:
                    logger.info("Replacing registered provider '%s'", name)
            self._adapters[name] = adapter
            if name not in self._order:
                self._order.append(name)
        logger.info("LLM provider registered: %s (%s)", name, type(adapter).__name__)

    def resolve(self, name: str) -> BaseLLMAdapter | None:
        with self._lock:
            return self._adapters.get(name)

    def list_available(self) -> list[str]:
        """Names of configured providers in fallback order."""
        with self._lock:
            return [
                n for n in self._order if self._adapters[n].available
            ]

    def ordered_adapters(self) -> list[BaseLLMAdapter]:
        """All registered adapters in fallback order."""
        with self._lock:
            return [self._adapters[n] for n in self._order]

    async def aclose_all(self) -> None:
        with self._lock:
            adapters = list(self._adapters.values())
            self._adapters.clear()
            self._order.clear()
        for adapter in adapters:
            try:
                await adapter.aclose()
            except Exception:  # noqa: BLE001 — drain must never raise
                logger.debug("Error closing provider '%s'", getattr(adapter, "name", "?"),
                             exc_info=True)

    # ── Environment parsing ──────────────────────────────────────────────

    @staticmethod
    def configs_from_env(environ: dict[str, str] | os._Environ[str] | None = None) -> list[ProviderConfig]:  # noqa: E501 — signature line
        """Parse provider configuration from environment variables.

        Pure function of ``environ`` (defaults to os.environ) so tests can
        inject temporary environments without monkeypatching globals.
        """
        env = os.environ if environ is None else environ
        raw_names = (env.get("LLM_PROVIDERS") or "").strip()
        configs: list[ProviderConfig] = []

        if raw_names:
            for name in [n.strip() for n in raw_names.split(",") if n.strip()]:
                prefix = f"LLM_{name.upper()}_"
                kind = (env.get(prefix + "KIND") or "openai_compatible").lower().strip()
                if kind not in ADAPTER_KINDS:
                    raise ValueError(
                        f"Provider '{name}': unknown KIND '{kind}'. "
                        f"Supported kinds: {sorted(ADAPTER_KINDS)}"
                    )
                defaults = _KIND_DEFAULTS.get(kind, {})
                base_url = env.get(prefix + "BASE_URL") or defaults.get("base_url", "")
                model = env.get(prefix + "MODEL") or defaults.get("model", "")
                try:
                    timeout = float(env.get(prefix + "TIMEOUT", _DEFAULT_TIMEOUT))
                    max_tokens = min(
                        int(env.get(prefix + "MAX_TOKENS", _DEFAULT_MAX_TOKENS)),
                        _MAX_TOKENS_HARD_CAP,
                    )
                except ValueError as exc:
                    raise ValueError(f"Provider '{name}': invalid TIMEOUT/MAX_TOKENS: {exc}")
                configs.append(
                    ProviderConfig(
                        name=name,
                        kind=kind,
                        api_key=env.get(prefix + "API_KEY", ""),
                        base_url=base_url,
                        model=model,
                        timeout=max(timeout, 1.0),
                        max_tokens=max(max_tokens, 1),
                    )
                )
            return configs

        configs.extend(_legacy_configs_from_env(env))
        if configs:
            return configs

        # Single-key discovery: any well-known key yields a ready provider.
        # Azure is skipped unless its resource endpoint was also provided —
        # a deployment URL cannot be derived from the API key alone.
        for known in _WELL_KNOWN_PROVIDERS:
            key_value = env.get(known.env_var)
            if not key_value:
                continue
            prefix = f"LLM_{known.name.upper()}_"
            base_url = env.get(prefix + "BASE_URL") or known.base_url
            model = env.get(prefix + "MODEL") or known.model
            if not base_url:
                logger.debug(
                    "Provider '%s' key found but no base_url available — "
                    "set %sBASE_URL to enable it",
                    known.name,
                    prefix,
                )
                continue
            configs.append(
                ProviderConfig(
                    name=known.name,
                    kind=known.kind,
                    api_key=key_value,
                    base_url=base_url,
                    model=model,
                )
            )
        return configs

    def reload(self) -> list[str]:
        """Re-read configuration from the environment; drain replaced clients.

        Called at construction, from the RBAC-protected admin endpoint, and
        by tests. Returns the newly-available provider names.
        """
        configs = self.configs_from_env()
        new_order: list[str] = []
        new_adapters: dict[str, BaseLLMAdapter] = {}
        for config in configs:
            if not config.available:
                logger.debug(
                    "Provider '%s' skipped (no API key configured)", config.name
                )
                continue
            adapter_cls = ADAPTER_KINDS[config.kind]
            kwargs: dict = {
                "name": config.name,
                "api_key": config.api_key,
                "base_url": config.base_url,
                "model": config.model,
                "timeout": config.timeout,
                "max_tokens": config.max_tokens,
            }
            new_adapters[config.name] = adapter_cls(**kwargs)
            new_order.append(config.name)

        with self._lock:
            replaced = [
                self._adapters[n]
                for n in self._order
                if n not in new_adapters or self._adapters[n] is not new_adapters.get(n)
            ]
            self._adapters = new_adapters
            self._order = new_order

        for stale in replaced:
            try:
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    asyncio.run(stale.aclose())
                else:
                    loop.create_task(stale.aclose())
            except Exception:  # noqa: BLE001 — drain is best-effort
                logger.debug("Error draining replaced provider", exc_info=True)

        logger.info(
            "LLM provider registry loaded %d provider(s): %s",
            len(new_order),
            new_order,
        )
        return list(new_order)


_KIND_DEFAULTS: dict[str, dict[str, str]] = {
    "openai_compatible": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o"},
    "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-sonnet-4-5"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com",
               "model": "gemini-2.0-flash"},
    "azure": {"base_url": "", "model": ""},
}


def _legacy_configs_from_env(env: dict[str, str] | os._Environ[str]) -> list[ProviderConfig]:
    """Synthesize the pre-registry two-slot chain from ZENMUX_*/LLM_FALLBACK_*."""
    configs: list[ProviderConfig] = []
    zenmux_key = env.get("ZENMUX_API_KEY", "")
    if zenmux_key:
        try:
            timeout = float(env.get("ZENMUX_REQUEST_TIMEOUT", _DEFAULT_TIMEOUT))
        except ValueError:
            timeout = _DEFAULT_TIMEOUT
        try:
            max_tokens = int(env.get("ZENMUX_MAX_TOKENS", _DEFAULT_MAX_TOKENS))
        except ValueError:
            max_tokens = _DEFAULT_MAX_TOKENS
        configs.append(
            ProviderConfig(
                name="zenmux",
                kind="openai_compatible",
                api_key=zenmux_key,
                base_url=env.get("ZENMUX_BASE_URL", "https://zenmux.ai/api/v1"),
                model=env.get("ZENMUX_MODEL", "z-ai/glm-4.7"),
                timeout=max(timeout, 1.0),
                max_tokens=max(min(max_tokens, _MAX_TOKENS_HARD_CAP), 1),
            )
        )
    fallback_enabled = env.get("LLM_FALLBACK_ENABLED", "").lower() in ("1", "true", "yes", "on")
    fallback_key = env.get("LLM_FALLBACK_API_KEY", "")
    if fallback_enabled and fallback_key:
        configs.append(
            ProviderConfig(
                name="aliyun-maas",
                kind="openai_compatible",
                api_key=fallback_key,
                base_url=(
                    env.get(
                        "LLM_FALLBACK_BASE_URL",
                        "https://ws-jhr3ncn4gmi9gm21.ap-southeast-1.maas.aliyuncs.com"
                        "/compatible-mode/v1",
                    )
                ),
                model=env.get("LLM_FALLBACK_MODEL", "qwen-plus-latest"),
            )
        )
    return configs


# ── Module-level singleton ───────────────────────────────────────────────────

_registry: LLMProviderRegistry | None = None
_registry_lock = threading.Lock()


def get_provider_registry() -> LLMProviderRegistry:
    """Return the shared registry singleton (thread-safe)."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = LLMProviderRegistry()
    return _registry


async def close_provider_registry() -> None:
    """Close and reset the shared registry singleton (graceful shutdown)."""
    global _registry
    if _registry is not None:
        await _registry.aclose_all()
        _registry = None


__all__ = [
    "LLMProviderRegistry",
    "LLMResponse",
    "ProviderConfig",
    "close_provider_registry",
    "get_provider_registry",
]
