"""
backend/services/providers/adapters.py — Provider adapters for the unified
LLM Provider Registry (Stage B1).

One adapter per provider family:

* ``OpenAICompatibleAdapter`` — zenmux / openrouter / groq / nvidia / vllm /
  ollama(/v1) and any OpenAI-compatible endpoint.
* ``AnthropicAdapter``        — native Messages API + native SSE streaming.
* ``GeminiAdapter``           — native generateContent via google-genai.
* ``AzureOpenAIAdapter``      — Azure deployment auth via openai.AzureOpenAI.

Adapter protocol (duck-typed, checked by the registry):

    chat(messages, model=..., temperature=..., max_tokens=...) -> LLMResponse
    stream(messages, ...) -> AsyncIterator[event-dict]   # chunk/done/error
    ping() -> tuple[bool, float, str | None]
    capabilities -> dict
    aclose() -> None

SAFETY (must not be lost — enforced by A0 tests):
* SSRF: base URLs are validated at construction. Cloud kinds require HTTPS;
  plain HTTP is only allowed on loopback (ollama/vllm local dev); cloud
  metadata endpoints are always rejected.
* Source tagging: every response/event carries ``source=<adapter name>``.
* Token caps: callers pass max_tokens; the adapter never raises a cap.

Retry policy: transient network/timeout errors AND HTTP 429/5xx are retried
(up to 3 attempts) with exponential backoff, honoring a numeric Retry-After
header when present. 4xx errors other than 429 surface immediately. This
extends (never shrinks) the pre-registry behavior documented in A0.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from backend.llm_constants import AI_DISCLAIMER
from backend.services.providers.types import LLMResponse

logger = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_MIN_WAIT = 1.0
_RETRY_MAX_WAIT = 10.0
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})
_METADATA_HOSTS = frozenset({"169.254.169.254", "metadata.google.internal", "metadata.azure.com"})

_ANTHROPIC_DEFAULT_HOST = "api.anthropic.com"
_GEMINI_DEFAULT_HOST = "generativelanguage.googleapis.com"
_OPENAI_DEFAULT_BASE = "https://api.openai.com/v1"
_AZURE_DEFAULT_API_VERSION = "2024-10-21"


# ── URL validation (SSRF gate) ───────────────────────────────────────────────


def validate_adapter_base_url(kind: str, base_url: str) -> str:
    """Validate an adapter base URL against SSRF rules; return cleaned URL.

    Rules:
      * scheme must be http(s); cloud kinds (anthropic/gemini/azure) and any
        non-loopback host require https;
      * cloud metadata endpoints are rejected outright;
      * trailing slash is stripped.
    """
    url = (base_url or "").strip().rstrip("/")
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()

    if not url or scheme not in ("http", "https"):
        raise ValueError(f"Invalid base_url '{url}' for provider kind '{kind}' (need http(s))")
    if host in _METADATA_HOSTS:
        raise ValueError(f"SSRF_BLOCKED: cloud metadata host '{host}' is never allowed")
    if kind in ("anthropic", "gemini", "azure") and scheme != "https":
        raise ValueError(f"HTTPS is required for provider kind '{kind}'")
    if host not in _LOOPBACK_HOSTS and scheme != "https":
        raise ValueError(
            f"SSRF_BLOCKED: plain HTTP is only allowed for loopback hosts, got '{host}'"
        )
    return f"{scheme}://{host}{f':{parsed.port}' if parsed.port else ''}{parsed.path.rstrip('/')}"


# ── Retry policy ─────────────────────────────────────────────────────────────


class _TransientHTTPError(Exception):
    """Internal wrapper marking a retryable HTTP status (429/5xx)."""

    def __init__(self, status_code: int, retry_after: float | None) -> None:
        super().__init__(f"retryable HTTP status {status_code}")
        self.status_code = status_code
        self.retry_after = retry_after


def _extract_retry_after(response: Any) -> float | None:
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return min(value, 60.0)


def is_retryable_exception(exc: BaseException) -> bool:
    """True for network/timeouts and 429/5xx; False for other 4xx."""
    if isinstance(exc, _TransientHTTPError):
        return True
    # HTTP status errors must be classified by status code FIRST — both
    # openai.APIStatusError and httpx.HTTPStatusError subclass generic
    # transport error classes that would otherwise match below.
    try:
        from openai import APIStatusError

        if isinstance(exc, APIStatusError):
            return getattr(exc, "status_code", 0) in _RETRYABLE_STATUS
    except ImportError:  # pragma: no cover — openai is a hard dep since A1
        pass
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    # Transport-level errors (connect/timeout/read) are always transient.
    if isinstance(exc, (httpx.HTTPError, httpx.TimeoutException)):
        return True
    # openai SDK connection/timeout errors
    try:
        from openai import APIConnectionError, APITimeoutError

        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return True
    except ImportError:  # pragma: no cover
        pass
    return False


async def run_with_retry(operation: Any, *, attempts: int = _RETRY_ATTEMPTS) -> Any:
    """Run an async operation under the shared transient-retry policy.

    Honors numeric Retry-After headers (clamped to [0, 60]s), else
    exponential backoff between _RETRY_MIN_WAIT and _RETRY_MAX_WAIT.
    """
    delay = _RETRY_MIN_WAIT
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:  # noqa: BLE001 — classified below
            if not is_retryable_exception(exc):
                raise
            last_exc = exc
            if attempt == attempts:
                break
            retry_after = getattr(exc, "retry_after", None)
            sleep_for = (
                float(retry_after)
                if isinstance(retry_after, int | float)
                else min(delay, _RETRY_MAX_WAIT)
            )
            logger.warning(
                "Provider call failed (%s) — retry %s/%s in %.2fs",
                type(exc).__name__,
                attempt,
                attempts - 1,
                sleep_for,
            )
            await asyncio.sleep(sleep_for)
            delay = min(delay * 2, _RETRY_MAX_WAIT)
    assert last_exc is not None
    raise last_exc


# ── Capabilities ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProviderCapabilities:
    kind: str
    streaming: bool
    vision: bool
    supports_system_message: bool


# ── Base adapter ─────────────────────────────────────────────────────────────


class BaseLLMAdapter(ABC):
    """Common plumbing shared by all adapters."""

    kind: str = "base"

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_tokens: int,
    ) -> None:
        if not name:
            raise ValueError("adapter name must be non-empty")
        self.name = name
        self.api_key = api_key
        self.base_url = validate_adapter_base_url(self.kind, base_url)
        self.default_model = model
        self.timeout = float(timeout)
        self.max_tokens = int(max_tokens)

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            kind=self.kind, streaming=True, vision=False, supports_system_message=True
        )

    @property
    def source(self) -> str:
        return self.name

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        use_max = max_tokens or self.max_tokens
        use_model = model or self.default_model
        result: LLMResponse = await run_with_retry(
            lambda: self._chat_once(messages, model=use_model, temperature=temperature,
                                    max_tokens=use_max)
        )
        return result

    @abstractmethod
    async def _chat_once(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse: ...

    def stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        use_max = max_tokens or self.max_tokens
        return self._stream_impl(messages, model=model or self.default_model,
                                 temperature=temperature, max_tokens=use_max)

    @abstractmethod
    def _stream_impl(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[dict[str, Any]]: ...

    @abstractmethod
    async def ping(self) -> tuple[bool, float, str | None]: ...

    async def aclose(self) -> None:
        """Release HTTP clients. Subclasses override as needed."""
        return

    # -- shared event helpers -------------------------------------------------

    @staticmethod
    def _chunk_event(content: str, model: str, source: str) -> dict[str, Any]:
        return {"type": "chunk", "content": content, "model": model, "source": source}

    @staticmethod
    def _done_event(
        content: str, model: str, source: str, usage: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "type": "done",
            "content": content,
            "model": model,
            "source": source,
            "usage": usage,
            "disclaimer": AI_DISCLAIMER,
        }

    @staticmethod
    def _error_event(message: str) -> dict[str, Any]:
        return {"type": "error", "message": message, "disclaimer": AI_DISCLAIMER}


# ── OpenAI-compatible ────────────────────────────────────────────────────────


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """Covers zenmux/openrouter/groq/nvidia/vllm/ollama-/v1 endpoints."""

    kind = "openai_compatible"

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_tokens: int,
    ) -> None:
        super().__init__(name, api_key, base_url, model, timeout, max_tokens)
        self._client: Any = None
        self._lock = asyncio.Lock()

    def _ensure_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=0,  # retries handled by run_with_retry
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:  # pragma: no cover — best-effort drain
                logger.debug("Error closing %s client", self.name, exc_info=True)
            self._client = None

    async def _chat_once(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        client = self._ensure_client()
        completion = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=self.timeout,
        )
        content = ""
        finish_reason = "stop"
        if hasattr(completion, "choices") and completion.choices:
            content = completion.choices[0].message.content or ""
            finish_reason = completion.choices[0].finish_reason or "stop"
        usage = getattr(completion, "usage", None)
        raw = (
            completion.model_dump()
            if hasattr(completion, "model_dump")
            else {}
        )
        return LLMResponse(
            content=content,
            model=getattr(completion, "model", model),
            source=self.source,
            finish_reason=finish_reason,
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
            raw=raw,
        )

    def _stream_impl(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[dict[str, Any]]:
        adapter = self

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            client = adapter._ensure_client()
            full = ""
            usage_data: dict[str, Any] = {}
            stream = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    stream_options={"include_usage": True},
                ),
                timeout=adapter.timeout,
            )
            async for chunk in stream:
                if not chunk.choices:
                    if chunk.usage:
                        usage_data = {
                            "prompt_tokens": chunk.usage.prompt_tokens,
                            "completion_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens,
                        }
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full += delta.content
                    yield adapter._chunk_event(delta.content, model, adapter.source)
                if chunk.usage:
                    usage_data = {
                        "prompt_tokens": chunk.usage.prompt_tokens,
                        "completion_tokens": chunk.usage.completion_tokens,
                        "total_tokens": chunk.usage.total_tokens,
                    }
            yield adapter._done_event(full, model, adapter.source, usage_data)

        return _gen()

    async def ping(self) -> tuple[bool, float, str | None]:
        start = time.perf_counter()
        try:
            client = self._ensure_client()
            await asyncio.wait_for(client.models.list(), timeout=5.0)
            return True, round((time.perf_counter() - start) * 1000, 2), None
        except Exception as exc:  # noqa: BLE001 — probe reports failures as data
            latency = round((time.perf_counter() - start) * 1000, 2)
            message = str(exc)
            if self.api_key and self.api_key in message:
                message = message.replace(self.api_key, "[REDACTED]")
            return False, latency, f"Probe error: {message[:200]}"


# ── Azure (deployment auth) ──────────────────────────────────────────────────


class AzureOpenAIAdapter(BaseLLMAdapter):
    """Azure OpenAI with deployment-based auth (api-key header)."""

    kind = "azure"

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_tokens: int,
        api_version: str = _AZURE_DEFAULT_API_VERSION,
    ) -> None:
        super().__init__(name, api_key, base_url, model, timeout, max_tokens)
        self.api_version = api_version
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            from openai import AzureOpenAI

            self._client = AzureOpenAI(
                azure_endpoint=self.base_url,
                api_key=self.api_key,
                api_version=self.api_version,
                timeout=self.timeout,
                max_retries=0,
            ).chat.completions
        return self._client

    async def aclose(self) -> None:
        # openai.AzureOpenAI exposes a sync close; nothing to await.
        self._client = None

    async def _chat_once(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        completions = self._ensure_client()
        completion = await asyncio.wait_for(
            completions.create(
                model=model,  # deployment name
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=self.timeout,
        )
        content = ""
        finish_reason = "stop"
        if getattr(completion, "choices", None):
            content = completion.choices[0].message.content or ""
            finish_reason = completion.choices[0].finish_reason or "stop"
        usage = getattr(completion, "usage", None)
        return LLMResponse(
            content=content,
            model=getattr(completion, "model", model),
            source=self.source,
            finish_reason=finish_reason,
            prompt_tokens=getattr(usage, "prompt_tokens", 0),
            completion_tokens=getattr(usage, "completion_tokens", 0),
            total_tokens=getattr(usage, "total_tokens", 0),
        )

    def _stream_impl(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[dict[str, Any]]:
        adapter = self

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            completions = adapter._ensure_client()
            full = ""
            stream = await asyncio.wait_for(
                completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                ),
                timeout=adapter.timeout,
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full += delta.content
                    yield adapter._chunk_event(delta.content, model, adapter.source)
            yield adapter._done_event(full, model, adapter.source, {})

        return _gen()

    async def ping(self) -> tuple[bool, float, str | None]:
        start = time.perf_counter()
        url = f"{self.base_url}/openai/deployments?api-version={self.api_version}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=5.0)) as client:
                resp = await client.get(url, headers={"api-key": self.api_key})
            latency = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code in (200, 401, 403):
                if resp.status_code in (401, 403):
                    return False, latency, "Authentication failed: Invalid Azure API key"
                return True, latency, None
            return False, latency, f"Azure returned HTTP {resp.status_code}"
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            latency = round((time.perf_counter() - start) * 1000, 2)
            return False, latency, f"Azure unreachable: {type(exc).__name__}"


# ── Anthropic (native Messages API) ──────────────────────────────────────────


class AnthropicAdapter(BaseLLMAdapter):
    """Native Anthropic Messages API over httpx, with native SSE streaming."""

    kind = "anthropic"

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_tokens: int,
    ) -> None:
        super().__init__(name, api_key, base_url or f"https://{_ANTHROPIC_DEFAULT_HOST}",
                         model, timeout, max_tokens)
        self._http: httpx.AsyncClient | None = None

    def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=min(self.timeout, 10.0)),
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    @staticmethod
    def _split_system(messages: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
        system_parts: list[str] = []
        rest: list[dict[str, str]] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_parts.append(str(msg.get("content", "")))
            else:
                rest.append({"role": str(msg.get("role")), "content": str(msg.get("content"))})
        return "\n\n".join(system_parts), rest

    async def _chat_once(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        system, convo = self._split_system(messages)
        body: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": convo,
        }
        if system:
            body["system"] = system
        http = self._ensure_http()
        resp = await http.post(f"{self.base_url}/v1/messages", json=body)
        if resp.status_code >= 400:
            if resp.status_code in _RETRYABLE_STATUS:
                raise _TransientHTTPError(resp.status_code, _extract_retry_after(resp))
            raise RuntimeError(f"Anthropic HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        text_blocks = [
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        ]
        usage = data.get("usage", {})
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        return LLMResponse(
            content="".join(text_blocks),
            model=data.get("model", model),
            source=self.source,
            finish_reason=data.get("stop_reason", "stop"),
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            raw=data,
        )

    def _stream_impl(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[dict[str, Any]]:
        adapter = self

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            system, convo = adapter._split_system(messages)
            body: dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": convo,
                "stream": True,
            }
            if system:
                body["system"] = system
            http = adapter._ensure_http()
            usage_data: dict[str, Any] = {}
            full = ""
            async with http.stream(
                "POST", f"{adapter.base_url}/v1/messages", json=body
            ) as resp:
                if resp.status_code >= 400:
                    body_text = (await resp.aread()).decode("utf-8", errors="replace")
                    raise RuntimeError(f"Anthropic HTTP {resp.status_code}: {body_text[:200]}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if not payload or payload == "[DONE]":
                        continue
                    event = json.loads(payload)
                    etype = event.get("type")
                    if etype == "content_block_delta":
                        text = (event.get("delta") or {}).get("text", "")
                        if text:
                            full += text
                            yield adapter._chunk_event(text, model, adapter.source)
                    elif etype == "message_start":
                        msg_usage = ((event.get("message") or {}).get("usage")) or {}
                        if msg_usage.get("input_tokens") is not None:
                            usage_data["prompt_tokens"] = int(msg_usage["input_tokens"])
                    elif etype == "message_delta":
                        msg_usage = event.get("usage") or {}
                        if msg_usage.get("output_tokens") is not None:
                            usage_data["completion_tokens"] = int(msg_usage["output_tokens"])
                    elif etype == "message_stop":
                        break
            usage_data.setdefault("prompt_tokens", 0)
            usage_data.setdefault("completion_tokens", 0)
            usage_data["total_tokens"] = (
                usage_data["prompt_tokens"] + usage_data["completion_tokens"]
            )
            yield adapter._done_event(full, model, adapter.source, usage_data)

        return _gen()

    async def ping(self) -> tuple[bool, float, str | None]:
        start = time.perf_counter()
        try:
            http = self._ensure_http()
            resp = await http.get(f"{self.base_url}/v1/models")
            latency = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code == 200:
                return True, latency, None
            if resp.status_code in (401, 403):
                return False, latency, "Authentication failed: Invalid Anthropic API key"
            if resp.status_code == 404:
                # Models listing disabled but endpoint reachable & authenticated.
                return True, latency, None
            return False, latency, f"Anthropic returned HTTP {resp.status_code}"
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            latency = round((time.perf_counter() - start) * 1000, 2)
            return False, latency, f"Anthropic unreachable: {type(exc).__name__}"


# ── Gemini (native generateContent) ──────────────────────────────────────────


class GeminiAdapter(BaseLLMAdapter):
    """Native Gemini via the official google-genai SDK (A1 dependency)."""

    kind = "gemini"

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        max_tokens: int,
    ) -> None:
        super().__init__(
            name, api_key, base_url or f"https://{_GEMINI_DEFAULT_HOST}", model, timeout,
            max_tokens,
        )
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            from google import genai as _google_genai

            http_options = None
            if self.base_url.rstrip("/") != f"https://{_GEMINI_DEFAULT_HOST}":
                from google.genai import types as _types

                http_options = _types.HttpOptions(base_url=self.base_url)
            self._client = _google_genai.Client(api_key=self.api_key, http_options=http_options)
        return self._client

    async def aclose(self) -> None:
        self._client = None

    @staticmethod
    def _to_gemini_contents(
        messages: list[dict[str, str]],
    ) -> tuple[str, list[dict[str, Any]]]:
        system = ""
        contents: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system = f"{system}\n{content}".strip() if system else content
            elif role == "assistant":
                contents.append({"role": "model", "parts": [{"text": content}]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})
        return system, contents

    async def _chat_once(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        from google.genai import types as _types

        system, contents = self._to_gemini_contents(messages)
        config = _types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system or None,
        )
        client = self._ensure_client()
        response = await asyncio.wait_for(
            client.aio.models.generate_content(model=model, contents=contents, config=config),
            timeout=self.timeout,
        )
        usage = getattr(response, "usage_metadata", None)
        prompt_toks = int(getattr(usage, "prompt_token_count", 0) or 0)
        cand_toks = int(getattr(usage, "candidates_token_count", 0) or 0)
        return LLMResponse(
            content=response.text or "",
            model=model,
            source=self.source,
            finish_reason="stop",
            prompt_tokens=prompt_toks,
            completion_tokens=cand_toks,
            total_tokens=prompt_toks + cand_toks,
            raw={},
        )

    def _stream_impl(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[dict[str, Any]]:
        adapter = self

        async def _gen() -> AsyncIterator[dict[str, Any]]:
            from google.genai import types as _types

            system, contents = adapter._to_gemini_contents(messages)
            config = _types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system or None,
            )
            client = adapter._ensure_client()
            full = ""
            async for chunk in await asyncio.wait_for(
                client.aio.models.generate_content_stream(
                    model=model, contents=contents, config=config
                ),
                timeout=adapter.timeout,
            ):
                text = chunk.text or ""
                if text:
                    full += text
                    yield adapter._chunk_event(text, model, adapter.source)
            yield adapter._done_event(full, model, adapter.source, {})

        return _gen()

    async def ping(self) -> tuple[bool, float, str | None]:
        start = time.perf_counter()
        params = {"key": self.api_key} if self.api_key else None
        url = f"{self.base_url}/v1beta/models"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=5.0)) as client:
                resp = await client.get(url, params=params)
            latency = round((time.perf_counter() - start) * 1000, 2)
            if resp.status_code == 200:
                return True, latency, None
            if resp.status_code in (400, 401, 403) and self.api_key:
                return False, latency, "Authentication failed: Invalid Gemini API key"
            return False, latency, f"Gemini returned HTTP {resp.status_code}"
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            latency = round((time.perf_counter() - start) * 1000, 2)
            return False, latency, f"Gemini unreachable: {type(exc).__name__}"


ADAPTER_KINDS: dict[str, type[BaseLLMAdapter]] = {
    "openai_compatible": OpenAICompatibleAdapter,
    "azure": AzureOpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
}

__all__ = [
    "ADAPTER_KINDS",
    "AnthropicAdapter",
    "AzureOpenAIAdapter",
    "BaseLLMAdapter",
    "GeminiAdapter",
    "OpenAICompatibleAdapter",
    "ProviderCapabilities",
    "is_retryable_exception",
    "run_with_retry",
    "validate_adapter_base_url",
]
