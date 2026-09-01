"""Compatibility shim — re-exports everything from canonical backend.core.command_registry.

Canonical location: backend/core/command_registry.py (SSoT)
Canonical data file: backend/core/command_registry.json (SSoT)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import backend.core.command_registry as _impl


def __getattr__(name: str) -> Any:
    return getattr(_impl, name)


def _default_path():
    if _REGISTRY_PATH:
        return Path(_REGISTRY_PATH)
    return _impl._default_path()


# Ensure direct named imports work seamlessly
load_registry = _impl.load_registry
reset_cache = _impl.reset_cache
get_service_names = _impl.get_service_names
get_command_entry = _impl.get_command_entry
is_allowed = _impl.is_allowed
resolve_addin_action = _impl.resolve_addin_action
validate_params = _impl.validate_params
get_allowed_commands = _impl.get_allowed_commands
normalize_params = _impl.normalize_params
expand_update_parameters = _impl.expand_update_parameters
_as_point3 = _impl._as_point3
_passthrough = _impl._passthrough
_norm_create_wall = _impl._norm_create_wall
_norm_place_family_instance = _impl._norm_place_family_instance
_norm_element_command = _impl._norm_element_command
_norm_hosted_instance = _impl._norm_hosted_instance
_REVIT_NORMALIZERS = _impl._REVIT_NORMALIZERS
_AUTOCAD_NORMALIZERS = _impl._AUTOCAD_NORMALIZERS
_lock = _impl._lock
_cache = _impl._cache
_REGISTRY_PATH = _impl._REGISTRY_PATH

__all__ = [
    "_AUTOCAD_NORMALIZERS",
    "_REGISTRY_PATH",
    "_REVIT_NORMALIZERS",
    "_as_point3",
    "_cache",
    "_default_path",
    "_lock",
    "_norm_create_wall",
    "_norm_element_command",
    "_norm_hosted_instance",
    "_norm_place_family_instance",
    "_passthrough",
    "expand_update_parameters",
    "get_allowed_commands",
    "get_command_entry",
    "get_service_names",
    "is_allowed",
    "load_registry",
    "normalize_params",
    "reset_cache",
    "resolve_addin_action",
    "validate_params",
]
