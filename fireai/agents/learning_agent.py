# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
fireai/agents/learning_agent.py — Knowledge Accumulation Agent.
=================================================================
Persistent memory store using SQLite. Stores design experiences,
discovers and registers design patterns, retrieves similar scenarios
via weighted feature comparison.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import to avoid triggering eager fireai.core.__init__ at agents import time.
try:
    from fireai.core.event_bus import EventBus, Events
except ImportError:  # pragma: no cover
    EventBus = None  # type: ignore[misc]
    Events = None  # type: ignore[misc]

# ── data classes ──────────────────────────────────────────────────────────────


@dataclass
class DesignExperience:
    experience_id: str = ""
    room_config: str = ""  # JSON string of room geometry/config
    detector_count: int = 0
    coverage_pct: float = 0.0
    compliance_passed: bool = False
    patterns_used: list[str] = field(default_factory=list)
    outcome: str = ""  # "success", "partial", "failure"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)


@dataclass
class DesignPattern:
    pattern_id: str = ""
    room_type: str = ""
    constraints: dict[str, Any] = field(default_factory=dict)
    solution_summary: str = ""
    effectiveness_score: float = 0.0
    usage_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── similarity matching ─────────────────────────────────────────────────────


def _extract_features_from_config(config_json: str) -> dict[str, float]:
    try:
        config = json.loads(config_json) if isinstance(config_json, str) else {}
    except (json.JSONDecodeError, TypeError):
        config = {}
    return {
        "room_area": float(config.get("room_area", 0)),
        "ceiling_height": float(config.get("ceiling_height", 3.0)),
        "width": float(config.get("width", 0)),
        "length": float(config.get("length", 0)),
        "obstruction_count": float(config.get("obstruction_count", 0)),
        "ceiling_type": 1.0
        if config.get("ceiling_type") in ("flat", "FLAT")
        else (
            2.0
            if config.get("ceiling_type") in ("sloped", "SLOPED", "beam", "BEAM")
            else 3.0  # NOSONAR — S3358: nested ternary acceptable in this localized context
        ),
    }


def _extract_room_features(design: Any) -> dict[str, float]:
    if isinstance(design, dict):
        return {
            "room_area": float(design.get("area", design.get("room_area", 0))),
            "ceiling_height": float(design.get("ceiling_height", 3.0)),
            "width": float(design.get("width", 0)),
            "length": float(design.get("length", 0)),
            "obstruction_count": float(design.get("obstruction_count", 0)),
            "ceiling_type": 1.0,
        }
    return {
        "room_area": 0.0,
        "ceiling_height": 3.0,
        "width": 0.0,
        "length": 0.0,
        "obstruction_count": 0.0,
        "ceiling_type": 1.0,
    }


def _compute_similarity(a: dict[str, float], b: dict[str, float]) -> float:
    weights = {
        "room_area": 0.25,
        "ceiling_height": 0.20,
        "width": 0.15,
        "length": 0.15,
        "obstruction_count": 0.15,
        "ceiling_type": 0.10,
    }
    total_weight = 0.0
    total = 0.0
    for key, weight in weights.items():
        va = a.get(key, 0)
        vb = b.get(key, 0)
        if va == 0 and vb == 0:
            continue
        denom = max(va, vb, 0.01)
        diff = abs(va - vb) / denom
        sim = max(0.0, 1.0 - diff)
        total += weight * sim
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return total / total_weight


# ── LearningAgent ────────────────────────────────────────────────────────────


class LearningAgent:
    """
    Agent that accumulates knowledge across sessions:
    - Persistent memory store (SQLite)
    - Experience storage (design decisions, outcomes)
    - Knowledge accumulation pattern library
    - Experience retrieval for similar scenarios.
    """

    def __init__(self, db_path: str = "fireai_learning.sqlite3") -> None:
        self.db_path = db_path
        # V215 SAFETY FIX (report 5.8): SQLite connection is shared across
        # calls. check_same_thread=False allows cross-thread use but provides
        # NO serialization. A reentrant lock guards every DB operation to
        # prevent "database is locked" errors and data races in threaded
        # contexts (e.g. FastAPI, async pipelines). RLock allows nested
        # method calls within the same thread to re-acquire safely.
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # B5 SQLite hardening: WAL mode allows concurrent readers alongside a
        # single writer — critical for FastAPI/async pipeline scenarios where
        # EventBus callbacks and API routes access the DB simultaneously.
        # busy_timeout=5000 ms: instead of raising SQLITE_BUSY immediately,
        # the connection retries for up to 5 seconds before giving up.
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self._create_tables()

        # D1.1: EventBus integration — LearningAgent subscribes to ANALYSIS_COMPLETE
        # events (read-only) and stores a DesignExperience for each completed room
        # analysis, building a persistent knowledge base across sessions.
        self._bus: Any = None
        self._subscribed = False
        if EventBus is not None:
            self._bus = EventBus.instance()
            self.subscribe_to_events()

    def _create_tables(self) -> None:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiences (
                    experience_id TEXT PRIMARY KEY,
                    room_config TEXT NOT NULL,
                    detector_count INTEGER NOT NULL,
                    coverage_pct REAL NOT NULL,
                    compliance_passed INTEGER NOT NULL,
                    patterns_used TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patterns (
                    pattern_id TEXT PRIMARY KEY,
                    room_type TEXT NOT NULL,
                    constraints TEXT NOT NULL,
                    solution_summary TEXT NOT NULL,
                    effectiveness_score REAL NOT NULL,
                    usage_count INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pattern_experience_links (
                    pattern_id TEXT NOT NULL,
                    experience_id TEXT NOT NULL,
                    PRIMARY KEY (pattern_id, experience_id)
                )
            """)
            # Performance indexes for common query patterns
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_experiences_timestamp ON experiences(timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_patterns_effectiveness "
                "ON patterns(effectiveness_score DESC, usage_count DESC)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_patterns_room_type ON patterns(room_type)"
            )
            self.conn.commit()

    def store_experience(self, experience: DesignExperience) -> str:
        exp_id = experience.experience_id or str(uuid.uuid4())
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO experiences
                (experience_id, room_config, detector_count, coverage_pct,
                 compliance_passed, patterns_used, outcome, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    exp_id,
                    experience.room_config,
                    experience.detector_count,
                    experience.coverage_pct,
                    1 if experience.compliance_passed else 0,
                    json.dumps(experience.patterns_used),
                    experience.outcome,
                    experience.timestamp,
                ),
            )
            for pid in experience.patterns_used:
                cursor.execute(
                    "INSERT OR IGNORE INTO pattern_experience_links (pattern_id, experience_id) VALUES (?, ?)",
                    (pid, exp_id),
                )
            self.conn.commit()
        logger.info("Stored experience %s", exp_id)
        return exp_id

    def retrieve_similar(
        self, design: Any, top_k: int = 5, limit: int = 100
    ) -> list[DesignExperience]:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM experiences ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()

        query_features = _extract_room_features(design)

        scored: list[tuple] = []
        for row in rows:
            exp_features = _extract_features_from_config(row["room_config"])
            sim = _compute_similarity(query_features, exp_features)
            scored.append((sim, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[DesignExperience] = []
        for _sim, row in scored[:top_k]:
            results.append(
                DesignExperience(
                    experience_id=row["experience_id"],
                    room_config=row["room_config"],
                    detector_count=row["detector_count"],
                    coverage_pct=row["coverage_pct"],
                    compliance_passed=bool(row["compliance_passed"]),
                    patterns_used=json.loads(row["patterns_used"]),
                    outcome=row["outcome"],
                    timestamp=row["timestamp"],
                )
            )
        return results

    def get_pattern(self, pattern_id: str) -> DesignPattern | None:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM patterns WHERE pattern_id = ?", (pattern_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return DesignPattern(
            pattern_id=row["pattern_id"],
            room_type=row["room_type"],
            constraints=json.loads(row["constraints"]),
            solution_summary=row["solution_summary"],
            effectiveness_score=row["effectiveness_score"],
            usage_count=row["usage_count"],
        )

    def register_pattern(self, pattern: DesignPattern) -> str:
        pid = pattern.pattern_id or str(uuid.uuid4())
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO patterns
                (pattern_id, room_type, constraints, solution_summary,
                 effectiveness_score, usage_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    pid,
                    pattern.room_type,
                    json.dumps(pattern.constraints),
                    pattern.solution_summary,
                    pattern.effectiveness_score,
                    pattern.usage_count,
                ),
            )
            self.conn.commit()
        logger.info(
            "Registered pattern %s (type=%s, score=%.3f)",
            pid,
            pattern.room_type,
            pattern.effectiveness_score,
        )
        return pid

    def suggest_patterns(self, design: Any, limit: int = 100) -> list[DesignPattern]:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT * FROM patterns ORDER BY effectiveness_score DESC, usage_count DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
        if not rows:
            return []

        query_features = _extract_room_features(design)

        scored: list[tuple] = []
        for row in rows:
            constraints = (
                json.loads(row["constraints"])
                if isinstance(row["constraints"], str)
                else row["constraints"]
            )
            pat_features = {
                "room_area": float(constraints.get("max_area", constraints.get("min_area", 0))),
                "ceiling_height": float(
                    constraints.get("max_ceiling", constraints.get("min_ceiling", 0))
                ),
                "obstruction_count": float(constraints.get("max_obstructions", 100)),
                "ceiling_type": 2.0
                if constraints.get("ceiling_type") in ("sloped", "SLOPED", "beam", "BEAM")
                else 1.0,
                "width": 0.0,
                "length": 0.0,
            }
            sim = _compute_similarity(query_features, pat_features)

            eff = row["effectiveness_score"]
            usage = min(row["usage_count"] / 100.0, 1.0)
            combined = 0.6 * sim + 0.3 * eff + 0.1 * usage
            scored.append((combined, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: list[DesignPattern] = []
        for _score, row in scored[:5]:
            results.append(
                DesignPattern(
                    pattern_id=row["pattern_id"],
                    room_type=row["room_type"],
                    constraints=json.loads(row["constraints"]),
                    solution_summary=row["solution_summary"],
                    effectiveness_score=row["effectiveness_score"],
                    usage_count=row["usage_count"],
                )
            )
        return results

    def _on_room_analysis_complete(self, event: Any) -> None:
        """Callback for ROOM_ANALYSIS_COMPLETE events.

        Read-only subscriber: stores a DesignExperience whenever a room
        analysis completes, feeding the persistent knowledge base.
        """
        data = event.data if hasattr(event, "data") else (event if isinstance(event, dict) else {})
        room_id = data.get("room_id", "unknown")
        try:
            experience = DesignExperience(
                room_config=json.dumps(data),
                detector_count=data.get("detector_count", 0),
                coverage_pct=data.get("coverage_pct", 0.0),
                compliance_passed=data.get("nfpa_valid", False),
                outcome="success"
                if data.get("success") and data.get("nfpa_valid")
                else ("partial" if data.get("success") else "failure"),
                patterns_used=[room_id],
            )
            self.store_experience(experience)
        except Exception as e:  # noqa: BLE001
            logger.warning("LearningAgent failed to store experience for room %s: %s", room_id, e)

    def subscribe_to_events(self) -> None:
        """Subscribe to EventBus events (read-only).

        Subscribes to ROOM_ANALYSIS_COMPLETE to accumulate design experiences.
        Idempotent — calling twice is a no-op.
        """
        if self._subscribed or self._bus is None or Events is None:
            return
        self._bus.subscribe(Events.ROOM_ANALYSIS_COMPLETE, self._on_room_analysis_complete)
        self._subscribed = True
        logger.debug("LearningAgent subscribed to %s", Events.ROOM_ANALYSIS_COMPLETE)

    def unsubscribe_from_events(self) -> None:
        """Unsubscribe from all EventBus events."""
        if not self._subscribed or self._bus is None or Events is None:
            return
        self._bus.unsubscribe(Events.ROOM_ANALYSIS_COMPLETE, self._on_room_analysis_complete)
        self._subscribed = False

    def close(self) -> None:
        self.unsubscribe_from_events()
        with self._lock:
            if self.conn:
                self.conn.close()
