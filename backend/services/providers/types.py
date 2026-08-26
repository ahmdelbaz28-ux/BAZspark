"""
backend/services/providers/types.py — Shared type contracts for the unified
LLM Provider Registry (Stage B1 of the agent-platform rebuild).

``LLMResponse`` is THE canonical response dataclass. It previously lived in
``backend/services/llm_service.py``; it moved here so provider adapters can
return it without a circular import (llm_service imports this package, never
the reverse). ``backend/services.llm_service`` re-exports it, so every
existing import site keeps working unchanged (A0 contract).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Streaming event shapes (identical to the pre-registry SSE contract pinned
# by backend/tests/test_a0_llm_regression_contract.py):
#
#   {"type": "chunk", "content": "...", "model": "...", "source": "..."}
#   {"type": "done",  "content": "...", "model": "...", "source": "...",
#    "usage": {...}, "disclaimer": "..."}
#   {"type": "error", "message": "...", "disclaimer": "..."}


@dataclass(frozen=True)
class LLMResponse:
    """Immutable result of an LLM chat completion.

    The ``source`` field always carries the provider name that produced the
    output so downstream code can distinguish AI-generated text from
    deterministic engineering calculations.
    """

    content: str
    model: str
    source: str = "zenmux"
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


__all__ = ["LLMResponse"]
