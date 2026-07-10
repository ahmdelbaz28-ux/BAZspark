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
* ``ZENMUX_API_KEY``       — API key (required for production use)
* ``ZENMUX_BASE_URL``      — defaults to ``https://zenmux.ai/api/v1``
* ``ZENMUX_MODEL``         — default chat model (e.g. ``z-ai/glm-4.7``)
* ``ZENMUX_REQUEST_TIMEOUT`` — seconds, default 60 (LLM calls can be slow)
* ``ZENMUX_MAX_TOKENS``    — default 2000

USAGE
-----
    from backend.services.llm_service import get_llm_service
    svc = get_llm_service()
    if not svc.available:
        raise HTTPException(503, "LLM service not configured")
    result = await svc.chat("Explain NFPA 72 §17.7.3.2.3", system="You are a fire protection engineer.")
    print(result.content)
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Defaults ─────────────────────────────────────────────────────────────────
_DEFAULT_BASE_URL = "https://zenmux.ai/api/v1"
_DEFAULT_MODEL = "z-ai/glm-4.7"
_DEFAULT_TIMEOUT = 60.0
_DEFAULT_MAX_TOKENS = 2000
_DEFAULT_TEMPERATURE = 0.1  # low temperature for deterministic engineering advice

# Conservative retry policy — LLM calls can be slow, so we allow up to 3
# attempts with exponential backoff. Only network/timeout errors are retried;
# 4xx errors (auth, quota, bad request) are surfaced immediately.
_MAX_RETRIES = 3
_RETRY_MIN_WAIT = 1.0
_RETRY_MAX_WAIT = 10.0


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
        self._api_key: str = os.environ.get("ZENMUX_API_KEY", "")
        self._base_url: str = os.environ.get("ZENMUX_BASE_URL", _DEFAULT_BASE_URL)
        self._default_model: str = os.environ.get("ZENMUX_MODEL", _DEFAULT_MODEL)
        self._timeout: float = float(
            os.environ.get("ZENMUX_REQUEST_TIMEOUT", _DEFAULT_TIMEOUT)
        )
        self._max_tokens: int = int(
            os.environ.get("ZENMUX_MAX_TOKENS", _DEFAULT_MAX_TOKENS)
        )
        self._client: Any = None  # openai.AsyncOpenAI | None
        self._lock = threading.Lock()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """True if the service is configured (API key present)."""
        return bool(self._api_key)

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def default_model(self) -> str:
        return self._default_model

    # ── Client lifecycle ──────────────────────────────────────────────────

    def _get_client(self) -> Any:
        """Lazily create the OpenAI async client.

        We import ``openai`` inside the method so the module can be imported
        even if the ``openai`` package is not installed (graceful degradation
        — the router will report 503 if the service is unavailable).
        """
        if self._client is not None:
            return self._client
        if not self.available:
            raise RuntimeError(
                "ZENMUX_API_KEY is not set. Configure it to enable the LLM service."
            )
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The 'openai' package is not installed. "
                "Install with: pip install openai"
            ) from exc

        with self._lock:
            if self._client is None:
                self._client = AsyncOpenAI(
                    api_key=self._api_key,
                    base_url=self._base_url,
                    timeout=self._timeout,
                    max_retries=0,  # we handle retries via tenacity
                )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client (graceful shutdown)."""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                logger.debug("Error closing LLM client", exc_info=True)
            self._client = None

    # ── Core chat method ──────────────────────────────────────────────────

    async def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
        temperature: float = _DEFAULT_TEMPERATURE,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send a chat completion request and return the response.

        Args:
            prompt: The user message. Must be non-empty.
            system: Optional system message (sets the assistant's persona).
            model: Override the default model.
            temperature: Sampling temperature [0.0, 2.0]. Default 0.1 for
                deterministic engineering advice.
            max_tokens: Max tokens to generate. Defaults to ZENMUX_MAX_TOKENS.

        Returns:
            LLMResponse with the generated content and usage stats.

        Raises:
            RuntimeError: If the service is not configured (no API key).
            Exception: On API errors after retries are exhausted.
        """
        if not prompt or not prompt.strip():
            raise ValueError("prompt must be non-empty")
        if not self.available:
            raise RuntimeError(
                "LLM service not configured. Set ZENMUX_API_KEY to enable."
            )

        client = self._get_client()
        use_model = model or self._default_model
        use_max_tokens = max_tokens or self._max_tokens

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # tenacity retry on transient network errors
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
            return await client.chat.completions.create(
                model=use_model,
                messages=messages,
                temperature=temperature,
                max_tokens=use_max_tokens,
            )

        try:
            completion = await _do_completion()
        except Exception:
            logger.exception(
                "LLM chat completion failed (model=%s, base_url=%s)",
                use_model,
                self._base_url,
            )
            raise

        choice = completion.choices[0] if completion.choices else None
        content = choice.message.content if choice and choice.message else ""
        finish = choice.finish_reason if choice else "unknown"

        usage = completion.usage
        prompt_t = usage.prompt_tokens if usage else 0
        completion_t = usage.completion_tokens if usage else 0
        total_t = usage.total_tokens if usage else 0

        # Safely serialize the raw response for debugging
        raw: dict[str, Any] = {}
        try:
            raw = completion.model_dump() if hasattr(completion, "model_dump") else {}
        except Exception:
            raw = {"id": getattr(completion, "id", "")}

        return LLMResponse(
            content=content or "",
            model=use_model,
            source="zenmux",
            finish_reason=finish or "stop",
            prompt_tokens=prompt_t,
            completion_tokens=completion_t,
            total_tokens=total_t,
            raw=raw,
        )

    # ── Health check ──────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Return a health/status dict (never raises)."""
        return {
            "available": self.available,
            "base_url": self._base_url,
            "default_model": self._default_model,
            "timeout_s": self._timeout,
            "max_tokens": self._max_tokens,
        }


def _get_transient_errors() -> tuple[type[Exception], ...]:
    """Return the tuple of exception types that should trigger a retry.

    We retry on network/connection errors but NOT on 4xx HTTP errors (auth,
    quota, bad request) — those are surfaced immediately to the caller.
    """
    import httpx

    transient: list[type[Exception]] = [httpx.HTTPError, httpx.TimeoutException]
    try:
        from openai import APIConnectionError, APITimeoutError, APIStatusError

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


__all__ = [
    "LLMResponse",
    "LLMService",
    "get_llm_service",
    "close_llm_service",
]
