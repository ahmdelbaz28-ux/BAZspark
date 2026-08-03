"""
fireai/infrastructure/mem0_workflow_bridge.py — Mem0 workflow enrichment bridge.

PURPOSE
-------
Implements the enrichment contract that
``backend.services.workflow_service.node_memory_enrich`` already calls
(see ``workflow_service.py:551-566``). Previously this module did not exist
and the ``ImportError`` at ``workflow_service.py:575`` silently degraded the
pipeline to "no memory context" — a dead feature that was documented but never
active. This bridge makes the declared memory-enrichment feature real.

CONTRACT (must stay compatible with the caller):
    enrich_with_memory_context(
        rooms: list[dict],
        workflow_id: str,
        engineer_id: str,
        env_context: dict,
    ) -> MemoryEnrichmentResult
    with:
        .hints                    -> list of objects exposing .to_dict()
        .total_memories_searched  -> int
        .enrichment_time_ms       -> float
        .hint_count               -> int (property)

SAFETY CONTRACT (per agent.md / memory_service.py):
- Memory is ADVISORY CONTEXT, never authoritative.
- Every hint is tagged source="memory" (never "nfpa_engine").
- Enrichment NEVER raises and NEVER blocks the pipeline: if the memory layer
  is uninitialized or a search fails, it returns zero hints (fail-safe).
- Only READ operations are performed (search). No memory writes happen here,
  so no LLM-based extraction is triggered by this bridge.
- Scoping: user_id=engineer_id, agent_id="fireai", run_id=workflow_id —
  matching the memory_service multi-scope model (USER/PROJECT/AGENT).

SEARCH STRATEGY (mirrors the documented strategy in
``workflow_service.py:521-533``):
1. Per-room occupancy: detector patterns + code references
2. Kitchen-specific: NFPA 72 §17.6.4 heat detector requirement
3. Hazardous area: IEC 60079 for electrical/mechanical rooms
4. Regional: Gulf Civil Defense codes when is_gulf_state=True
5. Seismic: bracing requirements when severe weather alerts exist
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Fixed agent scope for all enrichment lookups.
_AGENT_ID = "fireai"

# Conservative caps so enrichment stays cheap and never dominates the
# pipeline latency budget.
_MAX_QUERIES = 8
_TOP_K_PER_QUERY = 3
_SEARCH_THRESHOLD = 0.3
_MEMORY_MAX_LEN = 2000
_MAX_HINTS = 10


# ── Result types ─────────────────────────────────────────────────────────────


@dataclass
class MemoryHint:
    """A single advisory hint returned by the bridge (source="memory")."""

    text: str
    category: str = "general"
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "memory"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "category": self.category,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "source": self.source,
        }


@dataclass
class MemoryEnrichmentResult:
    """Return value of ``enrich_with_memory_context``."""

    hints: list[MemoryHint]
    total_memories_searched: int = 0
    enrichment_time_ms: float = 0.0
    error: str | None = None

    @property
    def hint_count(self) -> int:
        return len(self.hints)


# ── Query building ───────────────────────────────────────────────────────────


def _room_occupancy(room: dict[str, Any]) -> str:
    """Best-effort occupancy label for a room dict (unknown schema)."""
    for key in ("occupancy", "occupancy_type", "use", "use_type", "room_type", "name"):
        value = room.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _build_queries(
    rooms: list[dict[str, Any]],
    env_context: dict[str, Any],
) -> list[str]:
    """Build the search query list per the documented strategy (capped)."""
    queries: list[str] = []

    # 1. Per-room occupancy patterns
    for room in rooms[:_MAX_QUERIES]:
        occupancy = _room_occupancy(room)
        room_name = str(room.get("name", "") or "").strip().lower()
        if not occupancy and not room_name:
            continue
        combined = f"{occupancy} {room_name}".lower()

        # 2. Kitchen-specific heat detector rule (NFPA 72 §17.6.4)
        if "kitchen" in combined:
            queries.append(
                "NFPA 72 17.6.4 heat detector kitchen fire alarm requirement"
            )
        # 3. Hazardous-area IEC 60079 for electrical/mechanical rooms
        if any(
            kw in combined
            for kw in ("electrical", "mechanical", "hazardous", "generator")
        ):
            queries.append("IEC 60079 hazardous area fire alarm detector selection")

        queries.append(
            f"{occupancy or room_name} fire alarm detector placement patterns NFPA 72"
        )

    # 4. Regional standards (Gulf Civil Defense codes)
    if isinstance(env_context, dict):
        if env_context.get("is_gulf_state") or str(
            env_context.get("region", "")
        ).lower() in (
            "gulf",
            "uae",
            "saudi",
            "ksa",
            "qatar",
            "kuwait",
            "oman",
            "bahrain",
        ):
            queries.append("Civil Defense fire alarm code Gulf state requirements")

        # 5. Seismic bracing (severe weather alerts present)
        severe = env_context.get("severe_weather_alerts") or env_context.get(
            "severe_weather"
        )
        if severe:
            queries.append("seismic bracing fire alarm equipment requirements")

    # Deduplicate, keep order, enforce cap
    seen: set[str] = set()
    unique: list[str] = []
    for q in queries:
        key = q.lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(q)
        if len(unique) >= _MAX_QUERIES:
            break
    return unique


# ── Enrichment entrypoint ────────────────────────────────────────────────────


def enrich_with_memory_context(
    rooms: list[dict[str, Any]],
    workflow_id: str,
    engineer_id: str,
    env_context: dict[str, Any],
) -> MemoryEnrichmentResult:
    """
    Search the memory layer for advisory hints relevant to the workflow.

    NEVER raises. Returns zero hints when the memory layer is unavailable
    or a search fails (fail-safe, matches the pipeline's design).
    """
    started = time.perf_counter()
    queries = _build_queries(rooms or [], env_context or {})

    if not queries:
        return MemoryEnrichmentResult(
            hints=[],
            total_memories_searched=0,
            enrichment_time_ms=(time.perf_counter() - started) * 1000.0,
        )

    try:
        from backend.services.memory_service import (
            MemorySearchRequest,
            get_memory_service,
        )
    except ImportError as exc:  # pragma: no cover - backend unavailable
        logger.debug("mem0_workflow_bridge: backend not importable (%s)", exc)
        return MemoryEnrichmentResult(
            hints=[],
            total_memories_searched=0,
            enrichment_time_ms=(time.perf_counter() - started) * 1000.0,
            error="memory_service_unavailable",
        )

    service = get_memory_service()
    if not service.is_initialized:
        logger.debug(
            "mem0_workflow_bridge: MemoryService not initialized — "
            "returning zero hints (fail-safe)."
        )
        return MemoryEnrichmentResult(
            hints=[],
            total_memories_searched=0,
            enrichment_time_ms=(time.perf_counter() - started) * 1000.0,
            error="memory_service_not_initialized",
        )

    hints: list[MemoryHint] = []
    total_searched = 0
    seen_text: set[str] = set()

    for query in queries:
        try:
            response = service.search_memories(
                MemorySearchRequest(
                    query=query,
                    user_id=engineer_id or None,
                    agent_id=_AGENT_ID,
                    run_id=workflow_id or None,
                    top_k=_TOP_K_PER_QUERY,
                    threshold=_SEARCH_THRESHOLD,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "mem0_workflow_bridge: search failed for query %r: %s",
                query[:80],
                type(exc).__name__,
            )
            continue

        total_searched += len(response.results)
        for result in response.results:
            text = (result.memory or "").strip()
            if not text or text in seen_text:
                continue
            seen_text.add(text)
            meta = dict(result.metadata or {})
            hints.append(
                MemoryHint(
                    text=text[:_MEMORY_MAX_LEN],
                    category=str(meta.get("category", "general")),
                    confidence=(
                        float(result.score) if result.score is not None else 0.5
                    ),
                    metadata=meta,
                )
            )

        # Stop early once we have a healthy context budget.
        if len(hints) >= _MAX_HINTS:
            break

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    logger.info(
        "mem0_workflow_bridge: %d hints from %d memories in %.1fms "
        "(engineer=%s, workflow=%s)",
        len(hints),
        total_searched,
        elapsed_ms,
        engineer_id,
        workflow_id,
    )

    return MemoryEnrichmentResult(
        hints=hints,
        total_memories_searched=total_searched,
        enrichment_time_ms=elapsed_ms,
    )


__all__ = [
    "MemoryEnrichmentResult",
    "MemoryHint",
    "enrich_with_memory_context",
]
