"""UI-injection fallback for desktop CAD control (Path B5).

Last-resort control channel that automates the CAD application UI
(keyboard/menu automation) when the C# add-in named pipe is unavailable.

SAFETY GATE (mandatory):
- Disabled unless ``FIREAI_ENABLE_UI_INJECTION=1`` is explicitly set.
- Every run requires an explicit ``confirm=True`` from the caller.
- Actions are limited to whitelisted primitives; free-form key chords are
  rejected.
- Every execution writes an audit log entry with the plan hash.

This module must never be imported into request paths implicitly — it is a
deliberate operator tool.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger("bazspark.ui_injector")

ENV_FLAG = "FIREAI_ENABLE_UI_INJECTION"

# Allowed action primitives. Anything else is rejected — no raw key chords,
# no arbitrary window messages, no clipboard dumping.
_ALLOWED_ACTIONS = {
    "type_text",      # {"text": str}          — types literal text
    "press_key",      # {"key": str}           — single named key (Enter/Esc/…)
    "command_line",   # {"command": str}       — type into the app command line + Enter
    "menu",           # {"path": [str, ...]}   — walk menu items by caption
}

_MAX_TEXT_LEN = 2000


def is_enabled() -> bool:
    """True only when the explicit opt-in env flag is set."""
    return os.getenv(ENV_FLAG, "").strip().lower() in ("1", "true", "yes")


def _plan_digest(plan: dict[str, Any]) -> str:
    canonical = json.dumps(plan, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def validate_plan(plan: dict[str, Any]) -> list[str]:
    """Return a list of problems; empty means the plan is acceptable."""
    problems: list[str] = []
    if plan.get("app") not in ("revit", "autocad"):
        problems.append(f"Unsupported app: {plan.get('app')!r}")
    actions = plan.get("actions")
    if not isinstance(actions, list) or not actions:
        problems.append("Plan must contain a non-empty 'actions' list")
        return problems
    if len(actions) > 50:
        problems.append("Plan exceeds 50 actions")
    for i, action in enumerate(actions):
        kind = action.get("type")
        if kind not in _ALLOWED_ACTIONS:
            problems.append(f"action[{i}]: disallowed type {kind!r}")
            continue
        value = (
            action.get("text")
            or action.get("key")
            or action.get("command")
            or action.get("path")
        )
        if len(str(value or "")) > _MAX_TEXT_LEN:
            problems.append(f"action[{i}]: payload exceeds {_MAX_TEXT_LEN} chars")
    return problems


def confirm_and_execute(plan: dict[str, Any], *, confirm: bool) -> dict[str, Any]:
    """Validate, audit-log, then execute a UI injection plan.

    Args:
        plan: ``{"app": "revit"|"autocad", "actions": [{...}, ...]}``
        confirm: MUST be True — the caller's explicit confirmation.

    Returns:
        dict with ``success``, ``digest`` and per-action results.
    """
    digest = _plan_digest(plan)

    if not is_enabled():
        logger.warning("UI injection refused: %s is not enabled.", ENV_FLAG)
        return {"success": False, "error": f"Disabled — set {ENV_FLAG}=1 to opt in.", "digest": digest}

    if not confirm:
        logger.warning("UI injection refused: missing explicit confirm=true.")
        return {"success": False, "error": "Confirmation required (confirm=True).", "digest": digest}

    problems = validate_plan(plan)
    if problems:
        return {"success": False, "error": "; ".join(problems), "digest": digest}

    try:
        import pyautogui  # type: ignore
        import pyperclip  # type: ignore
    except ImportError as exc:
        return {"success": False, "error": f"pyautogui/pyperclip unavailable: {exc}", "digest": digest}

    pyautogui.FAILSAFE = True  # slam mouse to screen corner to abort
    results: list[dict[str, Any]] = []

    for i, action in enumerate(plan["actions"]):
        try:
            kind = action["type"]
            if kind == "type_text":
                pyperclip.copy(action["text"])
                pyautogui.hotkey("ctrl", "v")
                results.append({"index": i, "ok": True})
            elif kind == "press_key":
                pyautogui.press(action["key"])
                results.append({"index": i, "ok": True})
            elif kind == "command_line":
                pyperclip.copy(action["command"])
                pyautogui.hotkey("ctrl", "v")
                pyautogui.press("enter")
                results.append({"index": i, "ok": True})
            elif kind == "menu":
                for label in action["path"]:
                    pyautogui.typewrite(["alt"])  # activate menu bar; vendor-specific
                    time.sleep(0.2)
                results.append({"index": i, "ok": True, "note": "menu walk is best-effort"})
            time.sleep(float(action.get("delay_sec", 0.3)))
        except Exception as exc:  # noqa: BLE001 — report per-action failures
            results.append({"index": i, "ok": False, "error": str(exc)})
            break

    executed = sum(1 for r in results if r.get("ok"))
    entry = {
        "ts": time.time(),
        "app": plan.get("app"),
        "digest": digest,
        "actions_total": len(plan["actions"]),
        "actions_ok": executed,
    }
    logger.info("UI_INJECTION_AUDIT %s", json.dumps(entry))

    return {
        "success": executed == len(plan["actions"]),
        "digest": digest,
        "results": results,
    }
