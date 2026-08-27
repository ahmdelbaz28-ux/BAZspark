"""
tests/test_skills_loader.py
===========================

Tests for Stage C1: the dynamic SkillLoader (skills/loader.py).

Covers front-matter parsing, the four gating mechanisms (schema validation,
version-compatibility, permission deny-list, max-execution-time), successful
ToolSelector registration, EventBus publication, and the module-level
singleton/convenience helpers.

Skill fixtures (SKILL.md files) are created on a per-test tmp_path so no
real skill directories are touched.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from fireai.agents.tool_selector import ToolSelector
from fireai.core.event_bus import EventBus
from skills.loader import (
    EVENT_SKILL_DIRS_SCANNED,
    EVENT_SKILL_LOADED,
    EVENT_SKILL_REJECTED,
    LoadedSkill,
    SkillLoader,
    get_skill_loader,
)

# ── Fixtures ───────────────────────────────────────────────────────────────────


VALID_FRONTMATTER = textwrap.dedent("""\
    ---
    metadata:
      name: test-skill
      version: 1.0.0
      author: test-author
    description:
      short_description: A skill that does useful things for testing
      trigger_words:
        - test
        - testing
    requirements:
      max_execution_time: 60
    version_compatibility: "1.0"
    ---

    # Test Skill

    This is the markdown body.
""")


def _write_skill_file(
    dir_path: Path,
    filename: str = "SKILL.md",
    content: str = VALID_FRONTMATTER,
) -> Path:
    """Write a SKILL.md file (possibly under a sub-directory) and return its path."""
    path = dir_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def fake_event_bus() -> EventBus:
    """A fresh, non-singleton EventBus for capturing published events."""
    return EventBus()


@pytest.fixture
def fake_tool_selector(tmp_path: Path) -> ToolSelector:
    """A ToolSelector backed by a temp SQLite DB (no pollution of real DB)."""
    db = str(tmp_path / "test_tools.sqlite3")
    return ToolSelector(db_path=db)


@pytest.fixture
def loader(
    tmp_path: Path,
    fake_event_bus: EventBus,
    fake_tool_selector: ToolSelector,
) -> SkillLoader:
    """A SkillLoader pointed at a temp skills dir, using fake bus & selector."""
    return SkillLoader(
        tool_selector=fake_tool_selector,
        event_bus=fake_event_bus,
        skills_dirs=str(tmp_path),
    )


# ── Front-matter parsing ──────────────────────────────────────────────────────


class TestFrontMatterParsing:
    """Unit tests for _parse_frontmatter (a static method)."""

    def test_valid_frontmatter(self, tmp_path: Path) -> None:
        path = _write_skill_file(tmp_path)
        data = SkillLoader._parse_frontmatter(path)
        assert data["metadata"]["name"] == "test-skill"
        assert data["description"]["trigger_words"] == ["test", "testing"]

    def test_missing_delimiter(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        path.write_text("# No frontmatter here\n\nJust markdown.", encoding="utf-8")
        with pytest.raises(ValueError, match="missing YAML front-matter delimiter"):
            SkillLoader._parse_frontmatter(path)

    def test_unterminated_frontmatter(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        path.write_text("---\nname: foo\n", encoding="utf-8")
        with pytest.raises(ValueError, match="unterminated front-matter"):
            SkillLoader._parse_frontmatter(path)

    def test_frontmatter_not_a_mapping(self, tmp_path: Path) -> None:
        path = tmp_path / "SKILL.md"
        path.write_text("---\njust a string\n---\n\nbody", encoding="utf-8")
        with pytest.raises(ValueError, match="front-matter must be a YAML mapping"):
            SkillLoader._parse_frontmatter(path)

    def test_empty_dirs_listed(self, loader: SkillLoader, tmp_path: Path) -> None:
        """No SKILL.md files → both loaded and rejected are empty."""
        loaded, rejected = loader.load_all()
        assert loaded == []
        assert rejected == []


# ── Gate 1: Schema validation ─────────────────────────────────────────────────


class TestSchemaValidation:
    def test_valid_skill_loads(self, tmp_path: Path, loader: SkillLoader) -> None:
        _write_skill_file(tmp_path)
        loaded, rejected = loader.load_all()
        assert len(loaded) == 1
        assert rejected == []
        skill = loaded[0]
        assert isinstance(skill, LoadedSkill)
        assert skill.manifest.metadata.name == "test-skill"

    def test_invalid_manifest_rejected(self, tmp_path: Path, loader: SkillLoader) -> None:
        bad_fm = textwrap.dedent("""\
            ---
            metadata:
              name: ""
              version: not-valid
              author: test-author
            description:
              short_description: A test
              trigger_words:
                - test
            ---
            body
        """)
        _write_skill_file(tmp_path, content=bad_fm)
        loaded, rejected = loader.load_all()
        assert loaded == []
        assert len(rejected) == 1
        assert rejected[0].gate == "validation"
        assert rejected[0].name is None


# ── Gate 2: Version compatibility ─────────────────────────────────────────────


class TestVersionCompatibility:
    def test_compatible_version(self, tmp_path: Path, loader: SkillLoader) -> None:
        _write_skill_file(tmp_path)
        loaded, rejected = loader.load_all()
        assert len(loaded) == 1
        assert rejected == []

    def test_incompatible_version_rejected(self, tmp_path: Path) -> None:
        bus = EventBus()
        selector = ToolSelector(db_path=str(tmp_path / "v.sqlite3"))
        loader = SkillLoader(
            tool_selector=selector,
            event_bus=bus,
            skills_dirs=str(tmp_path),
            system_version="2.0",
        )
        _write_skill_file(tmp_path)
        loaded, rejected = loader.load_all()
        assert loaded == []
        assert len(rejected) == 1
        assert rejected[0].gate == "version_compatibility"
        selector.close()


# ── Gate 3: Permissions deny-list ────────────────────────────────────────────


class TestPermissionsGate:
    def test_allowed_permissions_load(self, tmp_path: Path, loader: SkillLoader) -> None:
        _write_skill_file(tmp_path)
        loaded, _rejected = loader.load_all()
        assert len(loaded) == 1

    def test_denied_permission_rejected(self, tmp_path: Path) -> None:
        fm = textwrap.dedent("""\
            ---
            metadata:
              name: net-skill
              version: 1.0.0
              author: test-author
            description:
              short_description: A networking skill for testing
              trigger_words:
                - network
            requirements:
              permissions:
                network: true
              max_execution_time: 30
            version_compatibility: "1.0"
            ---
            body
        """)
        bus = EventBus()
        selector = ToolSelector(db_path=str(tmp_path / "p.sqlite3"))
        loader = SkillLoader(
            tool_selector=selector,
            event_bus=bus,
            skills_dirs=str(tmp_path),
            deny_permissions="network",
        )
        _write_skill_file(tmp_path, content=fm)
        loaded, rejected = loader.load_all()
        assert loaded == []
        assert len(rejected) == 1
        assert rejected[0].gate == "permissions"
        assert "network" in rejected[0].reason
        selector.close()


# ── Gate 4: Max execution time ────────────────────────────────────────────────


class TestMaxExecutionTime:
    def test_within_limit(self, tmp_path: Path, loader: SkillLoader) -> None:
        _write_skill_file(tmp_path)
        loaded, _rejected = loader.load_all()
        assert len(loaded) == 1

    def test_exceeds_limit_rejected(self, tmp_path: Path) -> None:
        # Pydantic caps max_execution_time at 3600 (le=3600), so we set a value
        # within that range but above the loader's ceiling (100).
        fm_content = VALID_FRONTMATTER.replace("max_execution_time: 60", "max_execution_time: 200")
        bus = EventBus()
        selector = ToolSelector(db_path=str(tmp_path / "t.sqlite3"))
        loader = SkillLoader(
            tool_selector=selector,
            event_bus=bus,
            skills_dirs=str(tmp_path),
            max_exec_time=100,
        )
        _write_skill_file(tmp_path, content=fm_content)
        loaded, rejected = loader.load_all()
        assert loaded == []
        assert len(rejected) == 1
        assert rejected[0].gate == "execution_time"
        selector.close()


# ── ToolSelector registration ─────────────────────────────────────────────────


class TestToolSelectorRegistration:
    def test_capability_registration(self, tmp_path: Path, loader: SkillLoader, fake_tool_selector: ToolSelector) -> None:
        _write_skill_file(tmp_path)
        loader.load_all()
        assert "test-skill" in fake_tool_selector._tools
        caps = fake_tool_selector._tools["test-skill"]["capabilities"]
        assert "skill:test" in caps
        assert "skill:testing" in caps

    def test_score_fn_works(self, tmp_path: Path, loader: SkillLoader, fake_tool_selector: ToolSelector) -> None:
        from fireai.agents.tool_selector import Task

        _write_skill_file(tmp_path)
        loader.load_all()
        task = Task(description="I need to do some testing", required_capabilities=[])
        score_fn = fake_tool_selector._score_fns["test-skill"]
        score = score_fn(task, None)
        # Trigger word "testing" is in the task description.
        assert score > 0.0


# ── EventBus publication ──────────────────────────────────────────────────────


class TestEventBus:
    def test_skill_loaded_event(self, tmp_path: Path, loader: SkillLoader, fake_event_bus: EventBus) -> None:
        events: list = []
        fake_event_bus.subscribe(EVENT_SKILL_LOADED, events.append)
        _write_skill_file(tmp_path)
        loader.load_all()
        assert len(events) == 1
        assert events[0].data["name"] == "test-skill"

    def test_skill_rejected_event(self, tmp_path: Path, loader: SkillLoader, fake_event_bus: EventBus) -> None:
        bad_fm = textwrap.dedent("""\
            ---
            metadata:
              name: ""
              version: bad
            description: ""
            ---
            body
        """)
        events: list = []
        fake_event_bus.subscribe(EVENT_SKILL_REJECTED, events.append)
        _write_skill_file(tmp_path, content=bad_fm)
        loader.load_all()
        assert len(events) == 1
        assert events[0].data["gate"] == "validation"

    def test_scan_event(self, tmp_path: Path, loader: SkillLoader, fake_event_bus: EventBus) -> None:
        events: list = []
        fake_event_bus.subscribe(EVENT_SKILL_DIRS_SCANNED, events.append)
        _write_skill_file(tmp_path)
        loader.load_all()
        assert len(events) == 1
        assert events[0].data["loaded_count"] == 1
        assert events[0].data["rejected_count"] == 0


# ── Reload ────────────────────────────────────────────────────────────────────


class TestReload:
    def test_reload_clears_and_reloads(self, tmp_path: Path, loader: SkillLoader) -> None:
        path1 = tmp_path / "skill_a" / "SKILL.md"
        path2 = tmp_path / "skill_b" / "SKILL.md"
        path1.parent.mkdir(parents=True, exist_ok=True)
        path2.parent.mkdir(parents=True, exist_ok=True)
        path1.write_text(VALID_FRONTMATTER.replace("test-skill", "skill-a").replace(
            "test-skill", "skill-a"
        ), encoding="utf-8")
        path2.write_text(VALID_FRONTMATTER.replace("test-skill", "skill-b"), encoding="utf-8")

        loaded_a, _ = loader.load_all()
        assert len(loaded_a) == 2

        # Reload should re-scan.
        loaded_b, rejected_b = loader.reload()
        assert len(loaded_b) == 2
        assert rejected_b == []

    def test_reload_clears_rejected(self, tmp_path: Path, loader: SkillLoader) -> None:
        _write_skill_file(tmp_path)
        loader.load_all()
        # Add a bad file and reload.
        bad_fm = textwrap.dedent("""\
            ---
            name: bad
            ---
            body
        """)
        _write_skill_file(tmp_path / "bad_skill", content=bad_fm)
        _loaded, rejected = loader.reload()
        assert len(rejected) == 1


# ── Nested directory discovery ────────────────────────────────────────────────


class TestDiscovery:
    def test_nested_skill_files(self, tmp_path: Path, loader: SkillLoader) -> None:
        _write_skill_file(tmp_path / "sub" / "deep" / "nested")
        loaded, rejected = loader.load_all()
        assert len(loaded) == 1
        assert rejected == []

    def test_nonexistent_dir_skipped(self, tmp_path: Path) -> None:
        loader = SkillLoader(
            skills_dirs=str(tmp_path / "does_not_exist"),
        )
        loaded, rejected = loader.load_all()
        assert loaded == []
        assert rejected == []


# ── Module-level helpers ──────────────────────────────────────────────────────


class TestModuleHelpers:
    def test_get_skill_loader_singleton(self) -> None:
        a = get_skill_loader()
        b = get_skill_loader()
        assert a is b
