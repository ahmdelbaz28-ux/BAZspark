"""A2/D3 contract test: C# add-in command tables must match core/command_registry.json.

Fails the build when any drift appears between the Python registry (used by
the backend allow-list and scripts/local_agent.py routing) and the actual
command switches inside the two C# add-ins.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core import command_registry

REPO_ROOT = Path(__file__).resolve().parent.parent

REVIT_HANDLER = REPO_ROOT / "revit_addin" / "BazSparkRevitBridge" / "BazSparkExternalEventHandler.cs"
AUTOCAD_HANDLER = (
    REPO_ROOT / "autocad_addin" / "BazSparkAutoCADBridge" / "AutoCADCommandHandler.cs"
)

_SWITCH_ARM_RE = re.compile(r'"([a-z_0-9]+)"\s*=>')


def _extract_switch_actions(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    return set(_SWITCH_ARM_RE.findall(source))


def _registry_action_names(service: str) -> set[str]:
    """All names the C# side may legally expose: canonical addin actions + aliases."""
    commands = command_registry.load_registry()["services"][service]["commands"]
    names: set[str] = set()
    for entry in commands.values():
        names.add(entry["addin_action"])
        names.update(entry.get("aliases", []))
    return names


def _registry_pipe_actions(service: str) -> set[str]:
    commands = command_registry.load_registry()["services"][service]["commands"]
    return {
        entry["addin_action"]
        for entry in commands.values()
        if "pipe" in entry.get("channel", [])
    }


@pytest.mark.parametrize(
    ("service", "handler_path"),
    [
        ("revit", REVIT_HANDLER),
        ("autocad", AUTOCAD_HANDLER),
    ],
)
def test_every_csharp_command_is_registered(service: str, handler_path: Path):
    assert handler_path.exists(), f"Missing add-in handler source: {handler_path}"
    csharp_actions = _extract_switch_actions(handler_path)
    registered = _registry_action_names(service)
    unregistered = csharp_actions - registered
    assert not unregistered, (
        f"{service}: C# add-in exposes commands missing from command_registry.json "
        f"(D4 allow-list gap): {sorted(unregistered)}"
    )


@pytest.mark.parametrize(
    ("service", "handler_path"),
    [
        ("revit", REVIT_HANDLER),
        ("autocad", AUTOCAD_HANDLER),
    ],
)
def test_every_registered_pipe_command_exists_in_csharp(service: str, handler_path: Path):
    csharp_actions = _extract_switch_actions(handler_path)
    pipe_actions = _registry_pipe_actions(service)
    missing = pipe_actions - csharp_actions
    assert not missing, (
        f"{service}: command_registry.json routes these pipe commands but the C# "
        f"add-in cannot execute them: {sorted(missing)}"
    )


def test_registry_covers_backend_agent_calls():
    """Every action sent from backend routers via send_agent_command is allow-listed."""
    routers_dir = REPO_ROOT / "backend" / "routers"
    call_re = re.compile(r'send_agent_command\(\s*"(revit|autocad)"\s*,\s*"([a-z_]+)"')
    used: set[tuple[str, str]] = set()
    for py_file in routers_dir.glob("*.py"):
        for service, action in call_re.findall(py_file.read_text(encoding="utf-8")):
            used.add((service, action))
    assert used, "Expected at least one send_agent_command call site in backend/routers"
    for service, action in used:
        assert command_registry.is_allowed(service, action), (
            f"backend/routers sends '{service}/{action}' which is NOT in the registry"
        )


def test_native_passthrough_commands_are_flagged():
    """post_command/send_command must be marked native_passthrough so they stay gated."""
    for service, cmd in (("revit", "post_command"), ("autocad", "send_command")):
        entry = command_registry.get_command_entry(service, cmd)
        assert entry is not None
        assert entry["risk"] == "native_passthrough"


# ── Registry mechanics (cache / override / unknown-command paths) ───────────


def test_default_path_honors_registry_path_override(monkeypatch, tmp_path):
    override = tmp_path / "reg.json"
    monkeypatch.setattr(command_registry, "_REGISTRY_PATH", str(override))
    assert command_registry._default_path() == override


def test_load_registry_second_call_returns_cached_object():
    first = command_registry.load_registry()
    second = command_registry.load_registry()
    assert second is first


def test_force_reload_returns_fresh_mapping():
    cached = command_registry.load_registry()
    reloaded = command_registry.load_registry(force_reload=True)
    assert reloaded == cached
    assert reloaded is not cached


def test_reset_cache_clears_cached_registry():
    command_registry.load_registry()
    command_registry.reset_cache()
    assert command_registry._cache is None


def test_validate_params_unknown_command_reports_unknown():
    err = command_registry.validate_params("revit", "definitely_not_a_command", {})
    assert err is not None
    assert "Unknown revit command" in err


def test_normalize_params_swallows_normalizer_crash(monkeypatch):
    def _explode(params):
        raise ValueError("bad shape")

    monkeypatch.setitem(command_registry._REVIT_NORMALIZERS, "create_wall", _explode)
    out = command_registry.normalize_params("revit", "create_wall", {"x": 1})
    assert out == {"x": 1}
