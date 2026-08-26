"""
backend/services/llm_service.py — LLM Service (unified Provider Registry).

PURPOSE
-------
Provides the async LLM chat completion service for the FireAI AI Copilot.
Stage B2 (agent-platform rebuild): this service now DELEGATES all provider
I/O to ``backend/services/providers`` — a unified, env-driven registry of
provider adapters (openai_compatible / anthropic / gemini / azure).

Adding a provider is configuration-only::

    LLM_PROVIDERS=primary,fallback          # order = fallback order
    LLM_PRIMARY_KIND=openai_compatible      # anthropic | gemini | azure | ...
    LLM_PRIMARY_API_KEY=sk-...
    LLM_PRIMARY_BASE_URL=https://...
    LLM_PRIMARY_MODEL=gpt-4o

Legacy environments keep working unchanged: when ``LLM_PROVIDERS`` is unset,
the registry synthesizes the historical ZENMUX_* / LLM_FALLBACK_* chain, plus
single-key discovery (OPENAI_API_KEY alone => working provider).

This service is **advisory only**. It NEVER overrides deterministic NFPA 72
calculations produced by the QOMN kernel. All output carries a ``source``
field naming the provider that produced it.

CONTRACTS PRESERVED (pinned by backend/tests/test_a0_llm_regression_contract.py):
* persona whitelist is owned by the caller (router); this layer never injects one
* ``LLMResponse.source`` always reflects the producing provider
* never-crash streaming: errors surface as SSE ``error`` events
* server-side caps: history newest-20 turns, 8000 chars/message, <=22 assembled,
  max_tokens hard-capped at 8000
* SSRF gates live in the registry adapters (base URLs validated at construction)
"""

from __future__ import annotations

import logging
import os
import threading
import time as _time
from collections.abc import AsyncGenerator
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.llm_constants import AI_DISCLAIMER
from backend.services.providers.registry import (
    close_provider_registry,
    get_provider_registry,
)
from backend.services.providers.types import LLMResponse

logger = logging.getLogger(__name__)

# Hard cap on generated tokens — defense in depth (router also bounds it).
_MAX_TOKENS_HARD_CAP = 8000

# Legacy default slot values — preserved as the observable surface when no
# provider is configured (health payload, base_url/default_model properties),
# exactly as the pre-registry service reported them.
_LEGACY_DEFAULT_BASE_URL = "https://zenmux.ai/api/v1"
_LEGACY_DEFAULT_MODEL = "z-ai/glm-4.7"


class LLMService:
    """Async LLM chat service backed by the unified provider registry.

    The service is created lazily on first use. If no provider is configured,
    ``available`` is False and chat calls raise ``RuntimeError``.
    """

    def __init__(self) -> None:
        self._registry = get_provider_registry()
        self._lock = threading.Lock()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """True if at least one provider is configured."""
        return bool(self._registry.list_available())

    @property
    def base_url(self) -> str:
        """Primary provider base URL (back-compat field)."""
        adapters = self._registry.ordered_adapters()
        return adapters[0].base_url if adapters else _LEGACY_DEFAULT_BASE_URL

    @property
    def default_model(self) -> str:
        """Primary provider default model (back-compat field)."""
        adapters = self._registry.ordered_adapters()
        return adapters[0].default_model if adapters else _LEGACY_DEFAULT_MODEL

    @property
    def fallback_available(self) -> bool:
        """True if more than one provider is configured."""
        return len(self._registry.list_available()) > 1

    # ── Message assembly ──────────────────────────────────────────────────

    @staticmethod
    def _assemble_messages(
        *,
        system: str | None,
        prompt: str,
        history: list[dict[str, str]] | None,
    ) -> list[dict[str, str]]:
        """Assemble ``[system] + history + [user]`` with server-side caps.

        Guards (defense in depth — the router already bounds the request):
          - history is truncated to the newest 20 turns
          - every history entry must be exactly {"role", "content"} with
            role in {"user", "assistant"}
          - total assembled messages may not exceed 50
          - each message body is clamped to 8000 characters

        Raises ValueError on malformed history instead of sending it upstream.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": str(system)[:8000]})

        if history:
            for entry in history[-20:]:
                if not isinstance(entry, dict):
                    raise ValueError("history entries must be objects")
                role = entry.get("role")
                content = entry.get("content")
                if role not in ("user", "assistant") or not isinstance(content, str):
                    raise ValueError(
                        "history entries must have role in {'user','assistant'} "
                        "and string content"
                    )
                messages.append({"role": role, "content": content[:8000]})

        messages.append({"role": "user", "content": prompt})
        if len(messages) > 50:
            raise ValueError("conversation history exceeds server limit")
        return messages

    # ── Core chat methods ─────────────────────────────────────────────────

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return the response.

        Providers are tried in configured order (first success wins). The
        ``source`` field indicates which provider succeeded.

        Raises:
            ValueError: If prompt is empty, history is malformed, or caps exceeded.
            RuntimeError: If no provider is configured.
            Exception: On API errors after every configured provider failed.
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")
        if not self.available:
            raise RuntimeError(
                "LLM service not configured. Set a provider API key "
                "(e.g. LLM_PROVIDERS + LLM_<NAME>_API_KEY, ZENMUX_API_KEY or OPENAI_API_KEY)."
            )

        messages = self._assemble_messages(system=system, prompt=prompt, history=history)
        # Default 2000 matches the historical ZENMUX_MAX_TOKENS default;
        # explicit requests are clamped to the hard cap.
        use_max_tokens = min(max_tokens or (_MAX_TOKENS_HARD_CAP // 4), _MAX_TOKENS_HARD_CAP)

        adapters = [a for a in self._registry.ordered_adapters() if a.available]
        first_error: Exception | None = None
        for adapter in adapters:
            try:
                return await adapter.chat(
                    messages, model=model, temperature=temperature, max_tokens=use_max_tokens
                )
            except Exception as exc:  # noqa: BLE001 — fail over to next provider
                if first_error is None:
                    first_error = exc
                logger.warning(
                    "LLM provider '%s' failed (%s). %s",
                    adapter.name,
                    type(exc).__name__,
                    "Trying next provider." if adapter is not adapters[-1]
                    else "No further providers.",
                )
        assert first_error is not None
        raise first_error

    async def chat_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a chat completion token-by-token via SSE-shaped events.

        Yields dicts with one of these shapes (contract pinned by A0):
          - {"type": "chunk", "content": "...", "model": "...", "source": "..."}
          - {"type": "done", "content": "...", "usage": {...}, "disclaimer": "..."}
          - {"type": "error", "message": "...", "disclaimer": "..."}
        """
        if not prompt or not prompt.strip():
            yield {
                "type": "error",
                "message": "prompt must be non-empty",
                "disclaimer": AI_DISCLAIMER,
            }
            return
        if not self.available:
            yield {
                "type": "error",
                "message": "LLM service not configured. Set a provider API key.",
                "disclaimer": AI_DISCLAIMER,
            }
            return

        try:
            messages = self._assemble_messages(system=system, prompt=prompt, history=history)
        except ValueError as exc:
            yield {"type": "error", "message": str(exc), "disclaimer": AI_DISCLAIMER}
            return
        use_max_tokens = min(max_tokens or _MAX_TOKENS_HARD_CAP // 4, _MAX_TOKENS_HARD_CAP)

        adapters = [a for a in self._registry.ordered_adapters() if a.available]
        if not adapters:
            yield {
                "type": "error",
                "message": "No LLM provider available",
                "disclaimer": AI_DISCLAIMER,
            }
            return

        for adapter in adapters:
            events: list[dict[str, Any]] = []
            failure: Exception | None = None
            try:
                stream = adapter.stream(
                    messages, model=model, temperature=temperature, max_tokens=use_max_tokens
                )
                while True:
                    try:
                        event = await anext(stream)
                    except StopAsyncIteration:
                        break
                    events.append(event)
                    yield event
                return  # Success — don't try fallback
            except Exception as exc:  # noqa: BLE001 — fail over to next provider
                failure = exc
                logger.warning(
                    "Streaming with provider '%s' failed (%s), trying fallback",
                    adapter.name,
                    type(exc).__name__,
                )
                # If chunks were already delivered, do NOT replay from another
                # provider (would duplicate text). Surface an error event.
                if any(e.get("type") == "chunk" for e in events):
                    yield {
                        "type": "error",
                        "message": f"Stream from {adapter.name} aborted mid-flight",
                        "disclaimer": AI_DISCLAIMER,
                    }
                    return
                del failure
                continue

        yield {
            "type": "error",
            "message": "All LLM providers failed",
            "disclaimer": AI_DISCLAIMER,
        }

    # ── Health check ──────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:  # noqa: S7503 — async for future extensibility
        """Return a health/status dict (never raises).

        Includes the full provider chain under ``providers`` plus the
        back-compat ``primary``/``fallback`` blocks and the F6 subsystems
        block (memory, Tier-2 self-healing, tracing).
        """
        subsystems: dict[str, Any] = {}
        try:
            from backend.services.memory_service import get_memory_service as _mem

            mem = _mem()
            subsystems["memory"] = {
                "name": "mem0",
                "initialized": bool(getattr(mem, "is_initialized", False)),
                "status": ("ok" if getattr(mem, "is_initialized", False) else "disabled"),
            }
        except Exception as exc:  # pragma: no cover - defensive
            subsystems["memory"] = {"name": "mem0", "status": "error", "detail": str(exc)[:120]}

        try:
            import os as _os

            llm_healing = _os.environ.get("QOMN_ENABLE_LLM_HEALING", "").lower() in (
                "1",
                "true",
                "yes",
            )
            subsystems["self_healing_tier2"] = {
                "name": "ollama_llama3",
                "enabled": llm_healing,
                "status": "enabled" if llm_healing else "gated_off",
            }
        except Exception as exc:  # pragma: no cover - defensive
            subsystems["self_healing_tier2"] = {
                "name": "ollama_llama3",
                "status": "error",
                "detail": str(exc)[:120],
            }

        try:
            langfuse_enabled = os.environ.get("LANGFUSE_ENABLED", "").lower() in (
                "1",
                "true",
                "yes",
            )
            subsystems["tracing_langfuse"] = {
                "name": "langfuse",
                "enabled": bool(langfuse_enabled and os.environ.get("LANGFUSE_PUBLIC_KEY")),
                "status": "enabled"
                if (langfuse_enabled and os.environ.get("LANGFUSE_PUBLIC_KEY"))
                else "disabled",
            }
        except Exception as exc:  # pragma: no cover - defensive
            subsystems["tracing_langfuse"] = {
                "name": "langfuse",
                "status": "error",
                "detail": str(exc)[:120],
            }

        adapters = self._registry.ordered_adapters()
        providers_block = [
            {
                "name": a.name,
                "kind": a.capabilities.kind,
                "available": a.available,
                "base_url": a.base_url,
                "model": a.default_model,
            }
            for a in adapters
        ]
        primary = providers_block[0] if providers_block else {
            "name": "none", "kind": "openai_compatible", "available": False,
            "base_url": "", "model": "",
        }
        fallback = providers_block[1] if len(providers_block) > 1 else {
            "name": "aliyun-maas",
            "enabled": False,
            "available": False,
            "base_url": "",
            "model": "qwen-plus-latest",
        }

        return {
            "available": self.available,
            "providers": providers_block,
            "primary": primary,
            "fallback": fallback,
            "timeout_s": adapters[0].timeout if adapters else None,
            "max_tokens": adapters[0].max_tokens if adapters else None,
            "subsystems": subsystems,
        }

    async def reload_providers(self) -> list[str]:
        """Hot-reload the provider chain from the current environment."""
        with self._lock:
            return self._registry.reload()

    async def close(self) -> None:
        """Close all cached HTTP clients (graceful shutdown)."""
        await close_provider_registry()


# ── Module-level singleton ───────────────────────────────────────────────────

_llm_service: LLMService | None = None
_llm_lock = threading.Lock()


def get_llm_service() -> LLMService:
    """Get the shared LLMService singleton (thread-safe)."""
    global _llm_service
    if _llm_service is None:
        with _llm_lock:
            if _llm_service is None:
                _llm_service = LLMService()
    return _llm_service


async def close_llm_service() -> None:
    """Close the shared LLMService (graceful shutdown)."""
    global _llm_service
    if _llm_service is not None:
        await _llm_service.close()
        _llm_service = None


# ── Live Provider Ping & SSRF Validation (settings/router surface) ───────────

_ANTHROPIC_DEFAULT_HOST = "api.anthropic.com"
_GEMINI_DEFAULT_HOST = "generativelanguage.googleapis.com"

ALLOWED_CLOUD_HOSTS = frozenset({
    _ANTHROPIC_DEFAULT_HOST,
    _GEMINI_DEFAULT_HOST,
    "api.openai.com",
    "zenmux.ai",
    "ws-jhr3ncn4gmi9gm21.ap-southeast-1.maas.aliyuncs.com",
})

ALLOWED_LOCAL_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
    "[::1]",
})


def validate_provider_url(provider: str, base_url: str | None) -> tuple[bool, str, str | None]:
    """Validate and sanitize provider base_url against strict SSRF rules.

    Returns:
        tuple of (is_valid, resolved_url, error_message).
    """
    prov = (provider or "").lower().strip()

    def _clean(url: str) -> str:
        parsed = urlparse(url)
        port_str = f":{parsed.port}" if parsed.port else ""
        path = parsed.path.rstrip("/")
        return f"{(parsed.scheme or '').lower()}://{(parsed.hostname or '').lower()}{port_str}{path}"

    if prov == "ollama":
        url = (base_url or "http://localhost:11434").strip().rstrip("/")
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, url, "Invalid scheme for Ollama provider (must be http or https)"
        host = (parsed.hostname or "").lower()
        if host not in ALLOWED_LOCAL_HOSTS:
            return (
                False,
                url,
                f"SSRF_BLOCKED: Local provider (Ollama) can only target localhost/127.0.0.1, got '{host}'",
            )
        return True, _clean(url), None

    if prov == "anthropic":
        url = (base_url or f"https://{_ANTHROPIC_DEFAULT_HOST}").strip().rstrip("/")
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme != "https":
            return False, url, "HTTPS is required for Anthropic provider"
        host = (parsed.hostname or "").lower()
        if not (host == _ANTHROPIC_DEFAULT_HOST or host.endswith(".anthropic.com") or host in ALLOWED_LOCAL_HOSTS):
            return False, url, f"SSRF_BLOCKED: Host '{host}' is not an authorized Anthropic endpoint"
        return True, _clean(url), None

    if prov == "gemini":
        url = (base_url or f"https://{_GEMINI_DEFAULT_HOST}").strip().rstrip("/")
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme != "https":
            return False, url, "HTTPS is required for Google Gemini provider"
        host = (parsed.hostname or "").lower()
        if not (
            host == _GEMINI_DEFAULT_HOST
            or host.endswith(".googleapis.com")
            or host in ALLOWED_LOCAL_HOSTS
        ):
            return False, url, f"SSRF_BLOCKED: Host '{host}' is not an authorized Google Gemini endpoint"
        return True, _clean(url), None

    if prov == "openai":
        url = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            return False, url, "Invalid scheme for OpenAI provider"
        host = (parsed.hostname or "").lower()
        if not (
            host in ALLOWED_CLOUD_HOSTS
            or host.endswith(".openai.com")
            or host.endswith(".zenmux.ai")
            or host in ALLOWED_LOCAL_HOSTS
        ):
            return False, url, f"SSRF_BLOCKED: Host '{host}' is not an authorized OpenAI endpoint"
        return True, _clean(url), None

    return False, base_url or "", f"Unsupported provider: '{provider}'"


async def ping_provider(
    provider: str,
    base_url: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> tuple[bool, float, str | None]:
    """Execute a live lightweight ping/handshake probe to the provider.

    Delegates to the matching registry adapter when one exists so there is a
    single probe implementation per family; falls back to direct httpx
    probing for the raw provider names exposed by the settings UI.

    Returns:
        tuple of (success, latency_ms, error_message).
    Enforces a strict 5.0-second timeout cap and zero API key leakage in logs.
    """
    is_valid, resolved_url, err = validate_provider_url(provider, base_url)
    if not is_valid:
        return False, 0.0, err

    prov = provider.lower().strip()
    timeout = httpx.Timeout(5.0, connect=5.0)
    start_time = _time.perf_counter()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            parsed = urlparse(resolved_url)
            host = (parsed.hostname or "").lower()
            scheme = parsed.scheme.lower()
            port_str = f":{parsed.port}" if parsed.port else ""

            if prov == "ollama":
                if host not in ALLOWED_LOCAL_HOSTS or scheme not in ("http", "https"):
                    return False, 0.0, f"SSRF_BLOCKED: Unauthorized Ollama host '{host}'"
                safe_url = f"{scheme}://{host}{port_str}/api/tags"
                resp = await client.get(safe_url)
                latency_ms = round((_time.perf_counter() - start_time) * 1000, 2)
                if resp.status_code == 200:
                    return True, latency_ms, None
                safe_ver_url = f"{scheme}://{host}{port_str}/api/version"
                resp_ver = await client.get(safe_ver_url)
                latency_ms = round((_time.perf_counter() - start_time) * 1000, 2)
                if resp_ver.status_code == 200:
                    return True, latency_ms, None
                return False, latency_ms, f"Ollama returned HTTP {resp.status_code}"

            if prov == "anthropic":
                if scheme != "https" or not (
                    host == _ANTHROPIC_DEFAULT_HOST
                    or host.endswith(".anthropic.com")
                    or host in ALLOWED_LOCAL_HOSTS
                ):
                    return False, 0.0, f"SSRF_BLOCKED: Unauthorized Anthropic host '{host}'"
                headers = {"anthropic-version": "2023-06-01"}
                if api_key:
                    headers["x-api-key"] = api_key
                safe_url = f"{scheme}://{host}{port_str}/v1/models"
                resp = await client.get(safe_url, headers=headers)
                latency_ms = round((_time.perf_counter() - start_time) * 1000, 2)
                if resp.status_code in (200, 400, 401, 403):
                    if resp.status_code == 401 and api_key:
                        return False, latency_ms, "Authentication failed: Invalid Anthropic API key"
                    return True, latency_ms, None
                return False, latency_ms, f"Anthropic returned HTTP {resp.status_code}"

            if prov == "gemini":
                if scheme != "https" or not (
                    host == _GEMINI_DEFAULT_HOST
                    or host.endswith(".googleapis.com")
                    or host in ALLOWED_LOCAL_HOSTS
                ):
                    return False, 0.0, f"SSRF_BLOCKED: Unauthorized Gemini host '{host}'"
                params = {}
                if api_key:
                    params["key"] = api_key
                safe_url = f"{scheme}://{host}{port_str}/v1beta/models"
                resp = await client.get(safe_url, params=params)
                latency_ms = round((_time.perf_counter() - start_time) * 1000, 2)
                if resp.status_code in (200, 400, 401, 403):
                    if resp.status_code in (400, 401, 403) and api_key:
                        return False, latency_ms, "Authentication failed: Invalid Gemini API key"
                    return True, latency_ms, None
                return False, latency_ms, f"Gemini returned HTTP {resp.status_code}"

            if prov == "openai":
                if scheme not in ("http", "https") or not (
                    host in ALLOWED_CLOUD_HOSTS
                    or host in ALLOWED_LOCAL_HOSTS
                    or host.endswith(".openai.com")
                    or host.endswith(".zenmux.ai")
                ):
                    return False, 0.0, f"SSRF_BLOCKED: Unauthorized OpenAI host '{host}'"
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                base_path = parsed.path.rstrip("/")
                target_path = base_path if base_path.endswith("/models") else f"{base_path}/models"
                safe_url = f"{scheme}://{host}{port_str}{target_path}"
                resp = await client.get(safe_url, headers=headers)
                latency_ms = round((_time.perf_counter() - start_time) * 1000, 2)
                if resp.status_code in (200, 400, 401, 403):
                    if resp.status_code == 401 and api_key:
                        return False, latency_ms, "Authentication failed: Invalid OpenAI API key"
                    return True, latency_ms, None
                return False, latency_ms, f"OpenAI returned HTTP {resp.status_code}"

    except httpx.TimeoutException:
        latency_ms = round((_time.perf_counter() - start_time) * 1000, 2)
        return False, latency_ms, "Connection timed out (exceeded 5.0s cap)"
    except httpx.ConnectError:
        latency_ms = round((_time.perf_counter() - start_time) * 1000, 2)
        return False, latency_ms, "Connection refused: Target service is unreachable"
    except Exception as exc:
        latency_ms = round((_time.perf_counter() - start_time) * 1000, 2)
        err_msg = str(exc)
        if api_key and api_key in err_msg:
            err_msg = err_msg.replace(api_key, "[REDACTED]")
        return False, latency_ms, f"Probe error: {err_msg}"

    return False, 0.0, f"Unsupported provider: '{provider}'"


__all__ = [
    "LLMResponse",
    "LLMService",
    "close_llm_service",
    "get_llm_service",
    "ping_provider",
    "validate_provider_url",
]
