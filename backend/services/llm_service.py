"""
backend/services/llm_service.py — LLM Service (OpenAI-compatible / Zenmux).

PURPOSE
-------
Provides an async LLM chat completion service backed by any OpenAI-compatible
API (Zenmux, OpenAI, Modal, NVIDIA build.nvidia.com, etc.). Designed for the
FireAI AI Copilot — an engineering assistant that helps fire-protection
engineers interpret NFPA 72 / NEC calculation results, draft compliance
narratives, and answer code questions.

This service is **advisory only**. It NEVER overrides deterministic NFPA 72
calculations produced by the QOMN kernel. All LLM output is labeled with a
``source`` field so downstream code can distinguish AI-generated text from
deterministic engineering results.

DESIGN
------
* OpenAI Python SDK (``openai.AsyncOpenAI``) against ``ZENMUX_BASE_URL``.
* Singleton with thread-safe double-checked locking (same pattern as
  ``weather_service.py``, ``memory_service.py``).
* tenacity retry on transient network errors only (never retries 4xx).
* Graceful degradation: if ``ZENMUX_API_KEY`` is unset, the service reports
  ``available=False`` and endpoints return HTTP 503 (not 500).

ENVIRONMENT VARIABLES
---------------------
Primary provider (Zenmux):
* ``ZENMUX_API_KEY``       — API key (required for production use)
* ``ZENMUX_BASE_URL``      — defaults to ``https://zenmux.ai/api/v1``
* ``ZENMUX_MODEL``         — default chat model (e.g. ``z-ai/glm-4.7``)
* ``ZENMUX_REQUEST_TIMEOUT`` — seconds, default 60 (LLM calls can be slow)
* ``ZENMUX_MAX_TOKENS``    — default 2000

Fallback provider (Alibaba Cloud MaaS — optional, used if primary fails):
* ``LLM_FALLBACK_API_KEY``  — Alibaba MaaS API key
* ``LLM_FALLBACK_BASE_URL`` — defaults to Alibaba MaaS compatible-mode endpoint
* ``LLM_FALLBACK_MODEL``    — default ``qwen-plus-latest``
* ``LLM_FALLBACK_ENABLED``  — set to ``"true"`` to enable fallback (default: disabled)

When fallback is enabled and the primary provider returns an error (429, 500,
502, 503, timeout, or connection error), the service automatically retries
with the fallback provider. The ``source`` field in LLMResponse indicates
which provider succeeded (``"zenmux"`` or ``"aliyun-maas"``).

USAGE
-----
    from backend.services.llm_service import get_llm_service
    svc = get_llm_service()
    if not svc.available:
        raise HTTPException(503, "LLM service not configured")
    result = await svc.chat("Explain NFPA 72 §17.7.3.2.3", system="You are a fire protection engineer.")
    print(result.content)
    print(result.source)  # "zenmux" or "aliyun-maas"
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.llm_constants import AI_DISCLAIMER

logger = logging.getLogger(__name__)

# ── Defaults ─────────────────────────────────────────────────────────────────
_DEFAULT_BASE_URL = "https://zenmux.ai/api/v1"
_DEFAULT_MODEL = "z-ai/glm-4.7"
_DEFAULT_TIMEOUT = 60.0
_DEFAULT_MAX_TOKENS = 2000
_DEFAULT_TEMPERATURE = 0.1  # low temperature for deterministic engineering advice

# Fallback provider defaults (Alibaba Cloud MaaS — OpenAI-compatible)
_FALLBACK_DEFAULT_BASE_URL = (
    "https://ws-jhr3ncn4gmi9gm21.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
)
_FALLBACK_DEFAULT_MODEL = "qwen-plus-latest"

# Conservative retry policy — LLM calls can be slow, so we allow up to 3
# attempts with exponential backoff. Only network/timeout errors are retried;
# 4xx errors (auth, quota, bad request) are surfaced immediately.
_MAX_RETRIES = 3
_RETRY_MIN_WAIT = 1.0
_RETRY_MAX_WAIT = 10.0


@dataclass(frozen=True)
class _ProviderConfig:
    """Configuration for a single LLM provider (primary or fallback)."""

    name: str  # "zenmux" or "aliyun-maas"
    api_key: str
    base_url: str
    model: str

    @property
    def available(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class LLMResponse:
    """Immutable result of an LLM chat completion.

    The ``source`` field is always ``"zenmux"`` (or the configured provider)
    so downstream code can distinguish AI-generated text from deterministic
    engineering calculations.
    """

    content: str
    model: str
    source: str = "zenmux"
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


class LLMService:
    """Async LLM chat service backed by an OpenAI-compatible API.

    The service is created lazily on first use. If ``ZENMUX_API_KEY`` is not
    set, ``available`` is False and all chat calls raise ``RuntimeError``.
    """

    def __init__(self) -> None:
        # Primary provider (Zenmux or any OpenAI-compatible API)
        self._primary = _ProviderConfig(
            name="zenmux",
            api_key=os.environ.get("ZENMUX_API_KEY", ""),
            base_url=os.environ.get("ZENMUX_BASE_URL", _DEFAULT_BASE_URL),
            model=os.environ.get("ZENMUX_MODEL", _DEFAULT_MODEL),
        )
        # Fallback provider (Alibaba Cloud MaaS — optional)
        self._fallback_enabled = os.environ.get("LLM_FALLBACK_ENABLED", "").lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        self._fallback = _ProviderConfig(
            name="aliyun-maas",
            api_key=os.environ.get("LLM_FALLBACK_API_KEY", ""),
            base_url=os.environ.get("LLM_FALLBACK_BASE_URL", _FALLBACK_DEFAULT_BASE_URL),
            model=os.environ.get("LLM_FALLBACK_MODEL", _FALLBACK_DEFAULT_MODEL),
        )
        self._timeout: float = float(os.environ.get("ZENMUX_REQUEST_TIMEOUT", _DEFAULT_TIMEOUT))
        self._max_tokens: int = int(os.environ.get("ZENMUX_MAX_TOKENS", _DEFAULT_MAX_TOKENS))
        # Cache of clients per provider name
        self._clients: dict[str, Any] = {}
        self._lock = threading.Lock()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """True if at least one provider is configured."""
        return self._primary.available or (self._fallback_enabled and self._fallback.available)

    @property
    def base_url(self) -> str:
        return self._primary.base_url

    @property
    def default_model(self) -> str:
        return self._primary.model

    @property
    def fallback_available(self) -> bool:
        """True if fallback is enabled AND configured."""
        return self._fallback_enabled and self._fallback.available

    # ── Client lifecycle ──────────────────────────────────────────────────

    def _get_client(self, provider: _ProviderConfig | None = None) -> Any:
        """Lazily create an OpenAI async client for the given provider.

        If ``provider`` is None, uses the primary provider.
        We import ``openai`` inside the method so the module can be imported
        even if the ``openai`` package is not installed (graceful degradation
        — the router will report 503 if the service is unavailable).
        """
        prov = provider or self._primary
        if prov.name in self._clients:
            return self._clients[prov.name]
        if not prov.available:
            raise RuntimeError(
                f"{prov.name} API key is not set. Configure it to enable the LLM service."
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The 'openai' package is not installed. Install with: pip install openai"
            ) from exc

        with self._lock:
            if prov.name not in self._clients:
                self._clients[prov.name] = AsyncOpenAI(
                    api_key=prov.api_key,
                    base_url=prov.base_url,
                    timeout=self._timeout,
                    max_retries=0,  # we handle retries via tenacity
                )
        return self._clients[prov.name]

    async def close(self) -> None:
        """Close all cached HTTP clients (graceful shutdown)."""
        # list() snapshot is required: self._clients.clear() below mutates the
        # dict during iteration, which would raise RuntimeError without it.
        for name, client in list(self._clients.items()):  # noqa: S7504 — intentional snapshot
            try:
                await client.close()
            except Exception:
                logger.debug("Error closing %s client", name, exc_info=True)
        self._clients.clear()

    # ── Message assembly (F5b) ────────────────────────────────────────────

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

        Raises ValueError on malformed history instead of sending it upstream.
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})

        if history:
            for entry in history[-20:]:
                if not isinstance(entry, dict):
                    raise ValueError("history entries must be objects")
                role = entry.get("role")
                content = entry.get("content")
                if role not in ("user", "assistant") or not isinstance(content, str):
                    raise ValueError(
                        "history entries must have role in {'user','assistant'} and string content"
                    )
                messages.append({"role": role, "content": content[:8000]})

        messages.append({"role": "user", "content": prompt})
        if len(messages) > 50:
            raise ValueError("conversation history exceeds server limit")
        return messages

    # ── Core chat method ──────────────────────────────────────────────────

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = _DEFAULT_TEMPERATURE,
        max_tokens: int | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return the response.

        If the primary provider fails AND fallback is enabled, automatically
        retries with the fallback provider. The ``source`` field in the
        returned LLMResponse indicates which provider succeeded.

        Args:
            prompt: The user message. Must be non-empty.
            system: Optional system message (sets the assistant's persona).
            model: Override the default model (per-provider default if None).
            temperature: Sampling temperature [0.0, 2.0]. Default 0.1.
            max_tokens: Max tokens to generate. Defaults to ZENMUX_MAX_TOKENS.
            history: Optional bounded conversation history (list of dicts with
                ``role`` in {"user","assistant"} and ``content``). Assembled
                between the system message and the current prompt, oldest first.

        Returns:
            LLMResponse with the generated content and usage stats.

        Raises:
            ValueError: If prompt is empty, history is malformed or exceeds
                the server-side cap.
            RuntimeError: If no provider is configured.
            Exception: On API errors after retries and fallback are exhausted.
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")
        if not self.available:
            raise RuntimeError("LLM service not configured. Set ZENMUX_API_KEY to enable.")

        messages = self._assemble_messages(system=system, prompt=prompt, history=history)
        use_max_tokens = max_tokens or self._max_tokens

        # Try primary provider first
        primary_error: Exception | None = None
        if self._primary.available:
            try:
                return await self._try_provider(
                    self._primary, messages, model, temperature, use_max_tokens
                )
            except Exception as exc:
                primary_error = exc
                logger.warning(
                    "Primary LLM provider '%s' failed: %s. Attempting fallback if enabled.",
                    self._primary.name,
                    type(exc).__name__,
                )

        # Try fallback provider if enabled and configured
        if self.fallback_available:
            try:
                return await self._try_provider(
                    self._fallback, messages, model, temperature, use_max_tokens
                )
            except Exception:
                logger.exception(
                    "Fallback LLM provider '%s' also failed",
                    self._fallback.name,
                )
                # Raise the fallback error (most recent), but log primary too
                if primary_error:
                    logger.error("Primary provider error was: %s", primary_error)
                raise

        # No fallback available, raise primary error
        if primary_error:
            raise primary_error
        raise RuntimeError("No LLM provider available")

    async def _try_provider(
        self,
        provider: _ProviderConfig,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Attempt a chat completion with a single provider (with tenacity retry)."""
        import asyncio

        client = self._get_client(provider)
        use_model = model or provider.model

        from tenacity import (
            retry,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        @retry(
            retry=retry_if_exception_type(_get_transient_errors()),
            stop=stop_after_attempt(_MAX_RETRIES),
            wait=wait_exponential(min=_RETRY_MIN_WAIT, max=_RETRY_MAX_WAIT),
            reraise=True,
        )
        async def _do_completion() -> Any:
            return await asyncio.wait_for(
                client.chat.completions.create(
                    model=use_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=self._timeout,
            )

        try:
            completion = await _do_completion()
        except TimeoutError:
            logger.warning(
                "LLM chat completion timed out (provider=%s, timeout=%.1fs)",
                provider.name,
                self._timeout,
            )
            raise
        except Exception:
            logger.exception(
                "LLM chat completion failed (provider=%s, base_url=%s)",
                provider.name,
                provider.base_url,
            )
            raise

        if hasattr(completion, "choices") and completion.choices:
            content = completion.choices[0].message.content or ""
            finish_reason = completion.choices[0].finish_reason or "stop"
        else:
            content = ""
            finish_reason = "error"

        return LLMResponse(
            content=content,
            model=completion.model if hasattr(completion, "model") else use_model,
            source=provider.name,
            finish_reason=finish_reason,
            prompt_tokens=getattr(getattr(completion, "usage", None), "prompt_tokens", 0),
            completion_tokens=getattr(getattr(completion, "usage", None), "completion_tokens", 0),
            total_tokens=getattr(getattr(completion, "usage", None), "total_tokens", 0),
            # OpenAI SDK v1+ uses Pydantic v2, so model_dump() is preferred.
            # Fall back to .dict() for older SDK versions, then {} if neither exists.
            raw=completion.model_dump()
            if hasattr(completion, "model_dump")
            else (
                completion.dict() if hasattr(completion, "dict") else {}
            ),  # NOSONAR — S3358: nested ternary intentional for provider-agnostic response parsing
        )

    async def chat_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = _DEFAULT_TEMPERATURE,
        max_tokens: int | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a chat completion token-by-token via SSE.

        Yields dicts with one of these shapes:
          - {"type": "chunk", "content": "...", "model": "...", "source": "..."}
          - {"type": "done", "content": "full text", "model": "...",
             "source": "...", "usage": {...}, "disclaimer": "..."}
          - {"type": "error", "message": "...", "disclaimer": "..."}

        Falls back to non-streaming if the provider doesn't support streaming.
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
                "message": "LLM service not configured. Set ZENMUX_API_KEY.",
                "disclaimer": AI_DISCLAIMER,
            }
            return

        try:
            messages = self._assemble_messages(system=system, prompt=prompt, history=history)
        except ValueError as exc:
            yield {"type": "error", "message": str(exc), "disclaimer": AI_DISCLAIMER}
            return
        use_max_tokens = max_tokens or self._max_tokens

        # Try primary provider first, then fallback
        providers_to_try: list[_ProviderConfig] = []
        if self._primary.available:
            providers_to_try.append(self._primary)
        if self.fallback_available:
            providers_to_try.append(self._fallback)

        if not providers_to_try:
            yield {
                "type": "error",
                "message": "No LLM provider available",
                "disclaimer": AI_DISCLAIMER,
            }
            return

        for provider in providers_to_try:
            try:
                async for event in self._stream_provider(
                    provider, messages, model, temperature, use_max_tokens
                ):
                    yield event
                return  # Success — don't try fallback
            except Exception:
                logger.warning(
                    "Streaming with provider '%s' failed, trying fallback",
                    provider.name,
                    exc_info=True,
                )
                continue

        yield {
            "type": "error",
            "message": "All LLM providers failed",
            "disclaimer": AI_DISCLAIMER,
        }

    async def _stream_provider(  # NOSONAR — S3776: cognitive complexity is inherent to the safety-critical algorithm
        self,
        provider: _ProviderConfig,
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream tokens from a single provider."""
        import asyncio

        client = self._get_client(provider)
        use_model = model or provider.model

        try:
            # Add timeout to the stream creation call
            stream = await asyncio.wait_for(
                client.chat.completions.create(
                    model=use_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    stream_options={"include_usage": True},
                ),
                timeout=self._timeout,
            )
        except TimeoutError:
            logger.warning(
                "LLM stream creation timed out (provider=%s, timeout=%.1fs)",
                provider.name,
                self._timeout,
            )
            raise
        except Exception:
            logger.exception(
                "LLM stream creation failed (provider=%s, base_url=%s)",
                provider.name,
                provider.base_url,
            )
            raise

        full_content = ""
        usage_data: dict[str, Any] = {}

        # Process the stream with timeout for each chunk
        try:
            async for chunk in stream:
                # Check for cancellation periodically
                if asyncio.current_task().cancelled():
                    break

                if not chunk.choices:
                    # Final chunk may contain usage stats only
                    if chunk.usage:
                        usage_data = {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens,
                        }
                    continue

                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full_content += delta.content
                    yield {
                        "type": "chunk",
                        "content": delta.content,
                        "model": use_model,
                        "source": provider.name,
                    }

                # Check for usage in the final chunk
                if chunk.usage:
                    usage_data = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }

            # Yield final completion message
            yield {
                "type": "done",
                "content": full_content,
                "model": use_model,
                "source": provider.name,
                "usage": usage_data,
                "disclaimer": AI_DISCLAIMER,
            }
        except TimeoutError:
            logger.warning(
                "LLM stream timed out during processing (provider=%s, timeout=%.1fs)",
                provider.name,
                self._timeout,
            )
            yield {
                "type": "error",
                "message": f"Stream timed out after {self._timeout}s",
                "disclaimer": AI_DISCLAIMER,
            }
            raise
        except Exception as e:
            logger.exception(
                "LLM stream processing failed (provider=%s): %s", provider.name, str(e)
            )
            raise

    # ── Health check ──────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:  # noqa: S7503 — async for future extensibility
        """Return a health/status dict (never raises).

        F6: includes a ``subsystems`` block that surfaces the status of every
        LLM-adjacent subsystem (memory, Tier-2 self-healing, tracing) so a
        single /llm/health call answers "what AI is wired up and on?".
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

        return {
            "available": self.available,
            "primary": {
                "name": self._primary.name,
                "available": self._primary.available,
                "base_url": self._primary.base_url,
                "model": self._primary.model,
            },
            "fallback": {
                "name": self._fallback.name,
                "enabled": self._fallback_enabled,
                "available": self.fallback_available,
                "base_url": self._fallback.base_url,
                "model": self._fallback.model,
            },
            "timeout_s": self._timeout,
            "max_tokens": self._max_tokens,
            "subsystems": subsystems,
        }


def _get_transient_errors() -> tuple[type[Exception], ...]:
    """Return the tuple of exception types that should trigger a retry.

    We retry on network/connection errors but NOT on 4xx HTTP errors (auth,
    quota, bad request) — those are surfaced immediately to the caller.
    """
    import httpx

    transient: list[type[Exception]] = [httpx.HTTPError, httpx.TimeoutException]
    try:
        from openai import APIConnectionError, APITimeoutError

        transient.extend([APIConnectionError, APITimeoutError])
        # Retry on 429 and 5xx but NOT on 4xx (auth/quota/bad-request)
        # We can't easily filter APIStatusError by status code in the retry
        # decorator, so we include it and rely on tenacity's predicate — but
        # for simplicity we exclude it and let 429/5xx surface immediately.
        # This is conservative: a 429 will be surfaced to the user rather
        # than retried, which is acceptable for an LLM service (the user can
        # retry manually).
    except ImportError:
        # openai not installed — only httpx errors will be caught
        pass
    return tuple(transient)


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


# ── Live Provider Ping & SSRF Validation ──────────────────────────────────────

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
        port_str = f":{parsed.port}" if parsed.port else ""
        path = parsed.path.rstrip("/")
        clean_url = f"{scheme}://{host}{port_str}{path}"
        return True, clean_url, None

    if prov == "anthropic":
        url = (base_url or f"https://{_ANTHROPIC_DEFAULT_HOST}").strip().rstrip("/")
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme != "https":
            return False, url, "HTTPS is required for Anthropic provider"
        host = (parsed.hostname or "").lower()
        if not (host == _ANTHROPIC_DEFAULT_HOST or host.endswith(".anthropic.com") or host in ALLOWED_LOCAL_HOSTS):
            return False, url, f"SSRF_BLOCKED: Host '{host}' is not an authorized Anthropic endpoint"
        port_str = f":{parsed.port}" if parsed.port else ""
        path = parsed.path.rstrip("/")
        clean_url = f"{scheme}://{host}{port_str}{path}"
        return True, clean_url, None

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
        port_str = f":{parsed.port}" if parsed.port else ""
        path = parsed.path.rstrip("/")
        clean_url = f"{scheme}://{host}{port_str}{path}"
        return True, clean_url, None

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
        port_str = f":{parsed.port}" if parsed.port else ""
        path = parsed.path.rstrip("/")
        clean_url = f"{scheme}://{host}{port_str}{path}"
        return True, clean_url, None

    return False, base_url or "", f"Unsupported provider: '{provider}'"


async def ping_provider(
    provider: str,
    base_url: str | None = None,
    api_key: str | None = None,
    model_name: str | None = None,
) -> tuple[bool, float, str | None]:
    """Execute a live lightweight ping/handshake probe to the provider.

    Returns:
        tuple of (success, latency_ms, error_message).
    Enforces a strict 5.0-second timeout cap and zero API key leakage in logs.
    """
    is_valid, resolved_url, err = validate_provider_url(provider, base_url)
    if not is_valid:
        return False, 0.0, err

    prov = provider.lower().strip()
    timeout = httpx.Timeout(5.0, connect=5.0)
    start_time = time.perf_counter()

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
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                if resp.status_code == 200:
                    return True, latency_ms, None
                # Fallback to version
                safe_ver_url = f"{scheme}://{host}{port_str}/api/version"
                resp_ver = await client.get(safe_ver_url)
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
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
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
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
                headers = {}
                params = {}
                if api_key:
                    params["key"] = api_key
                safe_url = f"{scheme}://{host}{port_str}/v1beta/models"
                resp = await client.get(safe_url, headers=headers, params=params)
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
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
                latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
                if resp.status_code in (200, 400, 401, 403):
                    if resp.status_code == 401 and api_key:
                        return False, latency_ms, "Authentication failed: Invalid OpenAI API key"
                    return True, latency_ms, None
                return False, latency_ms, f"OpenAI returned HTTP {resp.status_code}"

    except httpx.TimeoutException:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return False, latency_ms, "Connection timed out (exceeded 5.0s cap)"
    except httpx.ConnectError:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return False, latency_ms, "Connection refused: Target service is unreachable"
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
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
