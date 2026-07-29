"""
backend/routers/settings.py — User settings persistence endpoint.

Stores and retrieves user preferences (apiTimeout, reportFormat, theme, etc.)
in a per-user JSON file under the data directory. Falls back gracefully
when the data directory is not writable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/settings", tags=["settings"])

# ── Storage ─────────────────────────────────────────────────────────────

_DATA_DIR = Path(os.environ.get("FIREAI_DATA_DIR", "/app/data"))
_SETTINGS_FILE = _DATA_DIR / "user_settings.json"


def _ensure_data_dir() -> None:
    """Create the data directory if it doesn't exist."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def _load_settings() -> dict[str, Any]:
    """Load settings from the JSON file. Returns {} if file doesn't exist."""
    if not _SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_settings(data: dict[str, Any]) -> None:
    """Persist settings to the JSON file."""
    _ensure_data_dir()
    # Strip sensitive keys
    SENSITIVE_KEYS = {"apikey", "api_key", "password", "token", "secret"}
    safe = {k: v for k, v in data.items() if k.lower() not in SENSITIVE_KEYS}
    _SETTINGS_FILE.write_text(
        json.dumps(safe, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ── Endpoints ───────────────────────────────────────────────────────────


@router.get("")
async def get_settings() -> dict[str, Any]:
    """Retrieve the current user settings."""
    settings = _load_settings()
    return {"success": True, "data": settings}


@router.put("")
async def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Save user settings (partial update — merges with existing)."""
    current = _load_settings()
    current.update(settings)
    try:
        _save_settings(current)
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to persist settings: {exc}",
        ) from exc
    return {"success": True, "data": current}
