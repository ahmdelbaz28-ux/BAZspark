"""
skills/loader.py — Dynamic Skill Loader for the FireAI Agent Platform.
=====================================================================

Discovers, validates, and registers AI agent skills (``SKILL.md``) at
runtime.  A skill is a self-contained capability directory whose
``SKILL.md`` carries YAML front-matter that maps 1:1 onto
``skills.skill_validator.SkillManifest``.

Design (Stage C1 of the agent-platform rebuild):

* ``SKILLS_DIRS`` env var (default ``.agents/skills``) lists directories
  searched recursively for ``SKILL.md`` files.
* YAML front-matter is parsed and validated against ``SkillManifest``
  (Pydantic strict models in ``skill_validator.py``).
* Every skill must pass three gates before registration:
    1. Version-compatibility gate  — ``validate_version_compatibility``
    2. Permissions deny-list gate  — ``SKILL_DENY_PERMISSIONS`` (env)
    3. Max-execution-time gate     — enforced by ``SkillRequirements``
* Valid skills are registered in ``ToolSelector.register_tool()`` with
  capabilities derived from ``description.trigger_words``.
* Rejected skills are logged to the audit ledger with the reason.
* Events are published on the ``EventBus`` for observability.

The loader is a *discovery* mechanism only — it does NOT execute skills.
Execution remains the responsibility of the agent loop / command bus.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from fireai.agents.tool_selector import Capability, ToolSelector
from fireai.core.event_bus import EventBus
from skills.skill_validator import (
    SkillManifest,
    SkillPermissions,
    validate_skill_manifest,
    validate_version_compatibility,
)

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_DEFAULT_SKILLS_DIRS = ".agents/skills"
_SKILL_FILENAME = "SKILL.md"
_SYSTEM_VERSION = "1.0"
_MAX_EXECUTION_TIME_LIMIT = 3600  # seconds — hard cap for safety


# ── Data structures ──────────────────────────────────────────────────────────


@dataclass
class LoadedSkill:
    """A skill that passed all gates and was registered."""

    manifest: SkillManifest
    path: Path
    capabilities: list[Capability] = field(default_factory=list)


@dataclass
class RejectedSkill:
    """A skill that failed one or more gates."""

    path: Path
    name: str | None
    reason: str
    gate: str  # e.g. "validation", "version_compatibility", "permissions", "execution_time"


# ── Event type constants ─────────────────────────────────────────────────────
# Published on the system EventBus for observability.

EVENT_SKILL_LOADED = "skill.loaded"
EVENT_SKILL_REJECTED = "skill.rejected"
EVENT_SKILL_DIRS_SCANNED = "skill.dirs.scanned"


# ── Loader ───────────────────────────────────────────────────────────────────


class SkillLoader:
    """
    Discovers, validates, and registers AI agent skills from ``SKILL.md``
    files.

    Configuration (all env-driven):

        SKILLS_DIRS              Comma-separated dirs to scan (default ``.agents/skills``)
        SKILL_DENY_PERMISSIONS   Comma-separated permission names to deny
                                  (e.g. ``network,subprocess``)
        SKILL_MAX_EXEC_TIME      Override for the max execution-time ceiling
                                  (default 3600 s)
        SKILL_SYSTEM_VERSION     The running system version for compatibility
                                  checks (default ``1.0``)

    Usage::

        loader = SkillLoader()
        summary = loader.load_all()
        # summary.loaded, summary.rejected ...
    """

    def __init__(
        self,
        tool_selector: ToolSelector | None = None,
        event_bus: EventBus | None = None,
        skills_dirs: str | None = None,
        deny_permissions: str | None = None,
        max_exec_time: int | None = None,
        system_version: str | None = None,
    ) -> None:
        self._selector = tool_selector or ToolSelector()
        self._bus = event_bus or EventBus.instance()

        env_dirs = skills_dirs or os.environ.get("SKILLS_DIRS", _DEFAULT_SKILLS_DIRS)
        self._dirs: list[str] = [d.strip() for d in env_dirs.split(",") if d.strip()]

        deny_str = deny_permissions or os.environ.get("SKILL_DENY_PERMISSIONS", "")
        self._deny_permissions: set[str] = {
            p.strip().lower() for p in deny_str.split(",") if p.strip()
        }

        self._max_exec_time = (
            int(max_exec_time)
            if max_exec_time is not None
            else int(os.environ.get("SKILL_MAX_EXEC_TIME", _MAX_EXECUTION_TIME_LIMIT))
        )
        self._system_version = system_version or os.environ.get(
            "SKILL_SYSTEM_VERSION", _SYSTEM_VERSION
        )

        # Track loaded skills for introspection / tests.
        self._loaded: dict[str, LoadedSkill] = {}
        self._rejected: list[RejectedSkill] = []
        self._lock = threading.RLock()

    # ── Public API ───────────────────────────────────────────────────

    @property
    def loaded(self) -> dict[str, LoadedSkill]:
        """Snapshot of successfully loaded skills (name → LoadedSkill)."""
        with self._lock:
            return dict(self._loaded)

    @property
    def rejected(self) -> list[RejectedSkill]:
        """Snapshot of rejected skills."""
        with self._lock:
            return list(self._rejected)

    def load_all(self) -> tuple[list[LoadedSkill], list[RejectedSkill]]:
        """
        Scan all configured ``SKILLS_DIRS`` and load every ``SKILL.md``.

        Returns a tuple of ``(loaded, rejected)`` lists.
        """
        loaded: list[LoadedSkill] = []
        rejected: list[RejectedSkill] = []

        for skill_path in self._discover_skill_files():
            result = self._load_skill_file(skill_path)
            if result is not None:
                loaded.append(result)
                with self._lock:
                    self._loaded[result.manifest.metadata.name] = result
            else:
                rej = self._rejected_for_path(skill_path)
                if rej:
                    rejected.append(rej)

        self._publish_scan_event(loaded, rejected)
        return loaded, rejected

    def reload(self) -> tuple[list[LoadedSkill], list[RejectedSkill]]:
        """Clear all registrations and re-scan from disk."""
        with self._lock:
            self._loaded.clear()
            self._rejected.clear()
            for tool_name in list(self._selector._tools.keys()):
                del self._selector._tools[tool_name]
                self._selector._score_fns.pop(tool_name, None)
        return self.load_all()

    # ── Internal helpers ─────────────────────────────────────────────

    def _discover_skill_files(self) -> list[Path]:
        """Recursively find all ``SKILL.md`` files in configured dirs."""
        found: list[Path] = []
        for dir_str in self._dirs:
            root = Path(dir_str)
            if not root.is_dir():
                logger.debug("SKILLS_DIRS entry '%s' is not a directory — skipping", dir_str)
                continue
            found.extend(sorted(root.rglob(_SKILL_FILENAME)))
        return found

    def _reject(
        self,
        path: Path,
        name: str | None,
        reason: str,
        gate: str,
    ) -> None:
        entry = RejectedSkill(path=path, name=name, reason=reason, gate=gate)
        with self._lock:
            self._rejected.append(entry)
        self._bus.publish(
            EVENT_SKILL_REJECTED,
            data={
                "path": str(path),
                "name": name,
                "reason": reason,
                "gate": gate,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            source="skill_loader",
        )
        logger.warning("Skill rejected [%s]: %s — %s", gate, path, reason)

    def _rejected_for_path(self, path: Path) -> RejectedSkill | None:
        with self._lock:
            matches = [r for r in self._rejected if r.path == path]
        return matches[-1] if matches else None

    def _load_skill_file(self, path: Path) -> LoadedSkill | None:
        """Parse, validate, and register a single SKILL.md file."""
        try:
            raw_frontmatter = self._parse_frontmatter(path)
        except FileNotFoundError:
            return None
        except (yaml.YAMLError, ValueError) as exc:
            self._reject(path, None, f"frontmatter parse error: {exc}", "validation")
            return None

        # Gate 1: Pydantic model validation
        is_valid, error = validate_skill_manifest(raw_frontmatter)
        if not is_valid:
            self._reject(path, None, f"schema validation failed: {error}", "validation")
            return None

        try:
            manifest = SkillManifest(**raw_frontmatter)
        except Exception as exc:
            self._reject(path, None, f"manifest construction failed: {exc}", "validation")
            return None

        name = manifest.metadata.name

        # Gate 2: Version compatibility
        if not validate_version_compatibility(manifest.version_compatibility, self._system_version):
            self._reject(
                path,
                name,
                f"incompatible with system v{self._system_version} "
                f"(skill requires v{manifest.version_compatibility})",
                "version_compatibility",
            )
            return None

        # Gate 3: Permissions deny-list
        denied = self._check_permissions(manifest.requirements.permissions)
        if denied:
            self._reject(
                path,
                name,
                f"permission(s) denied by deny-list: {sorted(denied)}",
                "permissions",
            )
            return None

        # Gate 4: Max execution time ceiling
        max_time = manifest.requirements.max_execution_time
        if max_time > self._max_exec_time:
            self._reject(
                path,
                name,
                f"max_execution_time {max_time}s exceeds system limit {self._max_exec_time}s",
                "execution_time",
            )
            return None

        # Build capabilities from trigger words + short_description
        capabilities = self._extract_capabilities(manifest)

        # Register in ToolSelector
        self._register_in_selector(manifest, capabilities)

        skill = LoadedSkill(
            manifest=manifest,
            path=path,
            capabilities=capabilities,
        )
        self._bus.publish(
            EVENT_SKILL_LOADED,
            data={
                "path": str(path),
                "name": name,
                "version": manifest.metadata.version,
                "capabilities": [c.name for c in capabilities],
                "timestamp": datetime.now(UTC).isoformat(),
            },
            source="skill_loader",
        )
        logger.info(
            "Skill loaded: %s v%s (%d capabilities)",
            name,
            manifest.metadata.version,
            len(capabilities),
        )
        return skill

    @staticmethod
    def _parse_frontmatter(path: Path) -> dict[str, Any]:
        """
        Extract and parse the YAML front-matter from a ``SKILL.md`` file.

        Front-matter is delimited by leading ``---`` lines at the very top
        of the file.  Everything after the closing ``---`` is Markdown body.
        """
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            raise ValueError(f"{path}: missing YAML front-matter delimiter")
        end = text.find("\n---", 3)
        if end == -1:
            raise ValueError(f"{path}: unterminated front-matter (no closing ---)")
        yaml_block = text[3:end]
        data = yaml.safe_load(yaml_block)
        if not isinstance(data, dict):
            raise ValueError(f"{path}: front-matter must be a YAML mapping")
        return data

    def _check_permissions(self, permissions: SkillPermissions) -> set[str]:
        """
        Return the set of permission names that are both enabled by the skill
        and present in the deny-list.
        """
        denied: set[str] = set()
        for field_name in ("network", "filesystem_read", "filesystem_write", "subprocess"):
            if getattr(permissions, field_name) and field_name in self._deny_permissions:
                denied.add(field_name)
        for env_var in permissions.env_vars:
            if env_var.lower() in self._deny_permissions:
                denied.add(f"env:{env_var}")
        return denied

    @staticmethod
    def _extract_capabilities(manifest: SkillManifest) -> list[Capability]:
        """
        Build ``Capability`` objects from the manifest's trigger words.

        Each trigger word becomes a capability named ``skill:<word>`` with a
        description drawn from ``short_description``.  This lets the
        ``ToolSelector`` route by keyword match.
        """
        desc = manifest.description.short_description
        capabilities = [
            Capability(
                name=f"skill:{word}",
                description=desc,
            )
            for word in manifest.description.trigger_words
        ]
        return capabilities

    def _register_in_selector(
        self, manifest: SkillManifest, capabilities: list[Capability]
    ) -> None:
        """Register the skill as a callable tool in ToolSelector."""
        name = manifest.metadata.name

        def _score_fn(task: Any, context: Any) -> float:
            """Score by trigger-word overlap with the task description."""
            if not hasattr(task, "description"):
                return 0.0
            task_text = (task.description or "").lower()
            matches = sum(1 for c in capabilities if c.name.replace("skill:", "") in task_text)
            if not task.required_capabilities:
                return float(matches) / max(len(capabilities), 1)
            required = {c.replace("skill:", "") for c in task.required_capabilities}
            avail = {c.name.replace("skill:", "") for c in capabilities}
            overlap = required & avail
            return len(overlap) / max(len(required), 1) if required else 0.5

        self._selector.register_tool(
            name=name,
            capabilities=capabilities,
            score_fn=_score_fn,
        )

    def _publish_scan_event(self, loaded: list[LoadedSkill], rejected: list[RejectedSkill]) -> None:
        self._bus.publish(
            EVENT_SKILL_DIRS_SCANNED,
            data={
                "dirs": self._dirs,
                "loaded_count": len(loaded),
                "rejected_count": len(rejected),
                "loaded_names": [s.manifest.metadata.name for s in loaded],
                "rejected_names": [r.name for r in rejected if r.name],
                "timestamp": datetime.now(UTC).isoformat(),
            },
            source="skill_loader",
        )


# ── Module-level convenience ─────────────────────────────────────────────────


_loader: SkillLoader | None = None
_loader_lock = threading.Lock()


def get_skill_loader() -> SkillLoader:
    """Return the shared SkillLoader singleton (thread-safe)."""
    global _loader
    if _loader is None:
        with _loader_lock:
            if _loader is None:
                _loader = SkillLoader()
    return _loader


def scan_skills() -> tuple[list[LoadedSkill], list[RejectedSkill]]:
    """One-shot convenience: scan and load all skills via the singleton."""
    return get_skill_loader().load_all()


__all__ = [
    "LoadedSkill",
    "RejectedSkill",
    "SkillLoader",
    "get_skill_loader",
    "scan_skills",
]
