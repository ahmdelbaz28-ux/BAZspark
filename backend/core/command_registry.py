"""Unified CAD command registry for BAZspark backend.

Single source of truth mapping canonical command names (used by the backend
REST/LLM orchestrator surface) to the C# add-in action names executed over
the named pipes / desktop agents, plus parameter normalization and validation.

Consumers:
- ``backend.routers.agent_ws`` (D4): allow-list validation before ``send_agent_command``.
- ``backend.core.cad_control_contracts``: validation and dispatching for desktop capabilities.
- Contract tests: verification against C# add-in command switch tables.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_REGISTRY_PATH: Optional[str] = None
_lock = threading.Lock()
_cache: Optional[dict[str, Any]] = None


def _default_path() -> Path:
    if _REGISTRY_PATH:
        return Path(_REGISTRY_PATH)
    try:
        import sys
        shim_mod = sys.modules.get("core.command_registry")
        if shim_mod and getattr(shim_mod, "_REGISTRY_PATH", None):
            return Path(shim_mod._REGISTRY_PATH)
    except Exception:
        pass
    candidate = Path(__file__).resolve().parent / "command_registry.json"
    return candidate


def load_registry(force_reload: bool = False) -> dict[str, Any]:
    """Load and cache the command registry JSON."""
    global _cache
    if _cache is not None and not force_reload:
        return _cache
    with _lock:
        if _cache is not None and not force_reload:
            return _cache
        path = _default_path()
        with open(path, "r", encoding="utf-8") as fh:
            _cache = json.load(fh)
        return _cache


def reset_cache() -> None:
    """Reset the cached registry (test hook)."""
    global _cache
    with _lock:
        _cache = None


def get_service_names() -> tuple[str, ...]:
    """Return all supported desktop service names (e.g. ('revit', 'autocad'))."""
    return tuple(load_registry().get("services", {}).keys())


def get_command_entry(service: str, canonical: str) -> Optional[dict[str, Any]]:
    """Resolve a canonical name or alias to its registry entry.

    Returns ``None`` when the service is unknown or the command is not
    registered — callers MUST treat that as a hard rejection (D4 fail-closed allow-list).
    """
    services = load_registry().get("services", {})
    svc = services.get(service)
    if not svc:
        return None
    commands = svc.get("commands", {})
    entry = commands.get(canonical)
    if entry is not None:
        return entry
    for candidate in commands.values():
        if canonical in candidate.get("aliases", []):
            return candidate
    return None


def is_allowed(service: str, canonical: str) -> bool:
    """Allow-list check used before dispatching any command to a desktop agent."""
    return get_command_entry(service, canonical) is not None


def resolve_addin_action(service: str, canonical: str) -> Optional[str]:
    """Resolve the C# add-in action string for a canonical command."""
    entry = get_command_entry(service, canonical)
    if entry is None:
        return None
    return entry.get("addin_action")


def validate_params(service: str, canonical: str, params: dict[str, Any]) -> Optional[str]:
    """Return an error string when required params are missing, else None."""
    entry = get_command_entry(service, canonical)
    if entry is None:
        return f"Unknown {service} command: {canonical!r}"
    schema = entry.get("params", {})
    missing = [name for name in schema.get("required", []) if params.get(name) is None]
    if missing:
        return f"Missing required params for {service}/{canonical}: {', '.join(missing)}"
    return None


def get_allowed_commands(service: str) -> list[str]:
    """Get all allowed command names and aliases for a given service."""
    services = load_registry().get("services", {})
    svc = services.get(service)
    if not svc:
        return []
    commands = svc.get("commands", {})
    names: list[str] = []
    for cmd, data in commands.items():
        names.append(cmd)
        names.extend(data.get("aliases", []))
    return sorted(set(names))


# ──────────────────────────────────────────────────────────────────────────────
# Parameter normalization: backend/REST shape → C# add-in shape.
# Pure functions; no I/O. Each returns the transformed params dict.
# ──────────────────────────────────────────────────────────────────────────────


def _as_point3(value: Any, default_z: float = 0.0) -> list[float]:
    pts = [float(v) for v in value]
    while len(pts) < 3:
        pts.append(default_z)
    return pts[:3]


def _passthrough(out: dict[str, Any], p: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        if key in p and p[key] is not None:
            out[key] = p[key]


def _norm_create_wall(p: dict[str, Any]) -> dict[str, Any]:
    sp = _as_point3(p.get("start_point", [0, 0]))
    ep = _as_point3(p.get("end_point", [0, 0]))
    out: dict[str, Any] = {"x1": sp[0], "y1": sp[1], "x2": ep[0], "y2": ep[1]}
    _passthrough(out, p, ("height", "level", "wall_type"))
    return out


def _norm_create_floor(p: dict[str, Any]) -> dict[str, Any]:
    out = {"points": p.get("boundary_points")}
    _passthrough(out, p, ("level", "floor_type"))
    return out


def _norm_place_family_instance(p: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    loc = p.get("location_point")
    pt = _as_point3(loc) if loc else [0.0, 0.0, 0.0]
    out["x"], out["y"], out["z"] = pt[0], pt[1], pt[2]
    if "family_name" in p:
        out["family"] = p["family_name"]
        out["family_name"] = p["family_name"]
    _passthrough(
        out,
        p,
        (
            "symbol",
            "symbol_name",
            "family_file_path",
            "family_path",
            "parameters",
            "level",
            "category",
        ),
    )
    return out


def _norm_element_command(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    if "element_id" in p:
        out["id"] = p["element_id"]
    return out


def _norm_hosted_instance(p: dict[str, Any]) -> dict[str, Any]:
    pt = _as_point3(p.get("location_point", [0, 0, 0]))
    family = p.get("family_type") or p.get("family_name") or ""
    out: dict[str, Any] = {
        "x": pt[0],
        "y": pt[1],
        "z": pt[2],
        "host_id": p.get("host_wall_id"),
        "family": family,
        "family_name": family,
        "symbol": family,
    }
    _passthrough(out, p, ("level", "parameters"))
    return out


_REVIT_NORMALIZERS = {
    "create_wall": _norm_create_wall,
    "create_floor": _norm_create_floor,
    "place_family_instance": _norm_place_family_instance,
    "create_family": _norm_place_family_instance,
    "place_family_instance_hosted": _norm_hosted_instance,
    "create_door": _norm_hosted_instance,
    "create_window": _norm_hosted_instance,
    "get_parameter": _norm_element_command,
    "set_parameter": _norm_element_command,
}

_AUTOCAD_NORMALIZERS: dict[str, Any] = {}


def normalize_params(service: str, canonical: str, params: dict[str, Any]) -> dict[str, Any]:
    """Normalize REST-style params into the shape the C# add-in expects."""
    normalizers = _REVIT_NORMALIZERS if service == "revit" else _AUTOCAD_NORMALIZERS
    fn = normalizers.get(canonical)
    if fn is None:
        return dict(params)
    try:
        return fn(params)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Param normalization failed for %s/%s: %s", service, canonical, exc)
        return dict(params)


def expand_update_parameters(
    params: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Expand ``update_parameters`` into N ``set_parameter`` calls."""
    element_id = params.get("element_id")
    parameters = params.get("parameters") or {}
    calls = [
        {"element_id": element_id, "id": element_id, "name": name, "value": value}
        for name, value in parameters.items()
    ]
    return "set_parameter", calls
