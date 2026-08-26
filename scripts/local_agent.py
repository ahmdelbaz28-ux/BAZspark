#!/usr/bin/env python3
"""
BAZspark Local Agent — Windows Desktop Bridge
==============================================
Run this script on a Windows machine with AutoCAD and/or Revit installed.
It connects to the BAZspark cloud server via WebSocket and executes
CAD/BIM commands locally using the native COM/API bindings.

Usage:
    python local_agent.py --server wss://ahmdelbaz28-bazspark.hf.space \
                          --api-key YOUR_API_KEY

Requirements (Windows only):
    pip install websockets pywin32 pythonnet

The agent will reconnect automatically on connection drops with
exponential back-off up to 60 seconds.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import os
import sys
import tempfile
import threading
import time
from typing import Any

# ── Command registry (A2: single source of truth) ────────────────────────────
_REPO_ROOT_EARLY = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT_EARLY not in sys.path:
    sys.path.insert(0, _REPO_ROOT_EARLY)

try:
    from core import command_registry as _registry

    _registry_available = True
except Exception as e:  # noqa: BLE001
    logging.getLogger("bazspark-agent").warning(
        "core.command_registry not importable (%s) — pipe routing disabled", e
    )
    _registry_available = False

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bazspark-agent")

# ── Platform check ────────────────────────────────────────────────────────────
if sys.platform != "win32":
    logger.warning(
        "This agent is designed for Windows. COM/API bindings are not "
        "available on %s — running in limited/test mode.",
        sys.platform,
    )

# ── Attempt to import websockets ──────────────────────────────────────────────
try:
    import websockets  # type: ignore
    import websockets.exceptions  # type: ignore
except ImportError:
    logger.error("websockets not installed. Run: pip install websockets")
    sys.exit(1)

# ── Attempt to import local services ─────────────────────────────────────────
# The agent reuses the existing service classes from the BAZspark repo.
# Add the repo root to sys.path so we can import backend packages.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from backend.services.autocad_service import AutoCADService

    _autocad_available = True
except Exception as e:  # noqa: BLE001
    logger.warning("AutoCADService not importable: %s", e)
    _autocad_available = False
    AutoCADService = None  # type: ignore

try:
    from backend.services.revit_service import RevitService

    _revit_available = True
except Exception as e:  # noqa: BLE001
    logger.warning("RevitService not importable: %s", e)
    _revit_available = False
    RevitService = None  # type: ignore


# ── Shared Named Pipe transport with enforced timeout (A5) ───────────────────

_READ_BUFFER_BYTES = 10 * 1024 * 1024  # 10 MB


def _send_pipe_command(
    pipe_name: str, payload: dict, timeout_sec: float
) -> dict:
    """Send one JSON command over a named pipe and read the response.

    A5 FIX: ``win32file.ReadFile`` blocks forever when the add-in never
    answers (e.g. a modal dialog is open in the CAD app). The declared
    TIMEOUT_SEC was never enforced. We now run the blocking read on a worker
    thread with ``join(timeout)``; on expiry we close the handle — which
    unblocks the pending ReadFile — and return a structured PIPE_TIMEOUT
    error instead of hanging the whole agent.
    """
    import pywintypes  # type: ignore
    import win32file  # type: ignore
    import win32pipe  # type: ignore

    h = None
    try:
        # Retry briefly when the pipe is momentarily unavailable: the add-in
        # recreates its server instance after every message (LocalAgentServer.cs
        # runs create→serve→close in a loop), so back-to-back commands can hit
        # ERROR_PIPE_BUSY (231) or a short ERROR_FILE_NOT_FOUND (2) window.
        last_error: Exception | None = None
        for attempt in range(8):
            try:
                h = win32file.CreateFile(
                    pipe_name,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )
                break
            except pywintypes.error as e:
                if e.winerror in (2, 231):
                    last_error = e
                    time.sleep(0.05 * (attempt + 1))
                    continue
                raise
        else:
            raise RuntimeError(f"Pipe {pipe_name!r} stayed unreachable: {last_error}")

        win32pipe.SetNamedPipeHandleState(h, win32pipe.PIPE_READMODE_MESSAGE, None, None)
        win32file.WriteFile(h, (json.dumps(payload) + "\n").encode("utf-8"))

        result: dict[str, Any] = {}

        def _read() -> None:
            try:
                _, data = win32file.ReadFile(h, _READ_BUFFER_BYTES)
                result["data"] = data
            except Exception as exc:  # noqa: BLE001 — handle closed on timeout
                result["read_error"] = exc

        reader = threading.Thread(target=_read, daemon=True)
        reader.start()
        reader.join(timeout_sec)

        if reader.is_alive():
            # Unblock the worker's pending ReadFile by destroying the handle.
            try:
                win32file.CloseHandle(h)
            except Exception:  # noqa: BLE001
                pass
            return {
                "success": False,
                "error": "PIPE_TIMEOUT",
                "detail": (
                    f"Named pipe {pipe_name!r} did not answer within "
                    f"{timeout_sec:.0f}s. A modal dialog may be open in the CAD app."
                ),
            }

        if "data" not in result:
            raise RuntimeError(f"Pipe read failed: {result.get('read_error')}")
        return json.loads(result["data"].decode("utf-8").strip())
    finally:
        if h is not None:
            try:
                win32file.CloseHandle(h)
            except Exception:  # noqa: BLE001
                pass


# ── Named Pipe dispatcher for C# Revit Add-in (thread-safe, no pythonnet calls) ──
class RevitNamedPipeDispatcher:
    """
    Sends JSON commands to the BazSparkRevitBridge C# Add-in via a Named Pipe.
    The Add-in executes them safely on Revit's Main Thread (ExternalEvent).

    This is the PREFERRED dispatcher when the Add-in is installed and running.
    Falls back to RevitService (pythonnet) only when the pipe is unavailable.
    """

    PIPE_NAME = r"\\.\pipe\bazspark_revit"
    TIMEOUT_SEC = 30.0

    def __init__(self) -> None:
        self._available: bool = False
        if sys.platform == "win32":
            try:
                import pywintypes  # type: ignore  # noqa: F401

                self._available = self._ping()
            except ImportError:
                logger.debug("pywin32 not installed — Named Pipe dispatcher unavailable")

    @property
    def available(self) -> bool:
        return self._available

    def _ping(self) -> bool:
        """Quick connectivity test — try to open the pipe."""
        try:
            import win32file  # type: ignore

            h = win32file.CreateFile(
                self.PIPE_NAME,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
            win32file.CloseHandle(h)
            return True
        except Exception:
            return False

    def send(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a command and return the response dict."""
        try:
            import pywintypes  # type: ignore  # noqa: F401 — availability probe
        except ImportError as exc:
            self._available = False
            return {"error": f"pywin32 not available: {exc}"}

        payload = {"command_id": str(time.time()), "action": action, "params": params}
        try:
            return _send_pipe_command(self.PIPE_NAME, payload, self.TIMEOUT_SEC)
        except pywintypes.error as e:
            if e.winerror == 2:  # ERROR_FILE_NOT_FOUND — pipe not running
                self._available = False
                return {
                    "success": False,
                    "error": "BazSparkRevitBridge Add-in not running. Start Revit first.",
                }
            raise


# ── Named Pipe dispatcher for C# AutoCAD Add-in ─────────────────────────────────
class AutoCADNamedPipeDispatcher:
    """
    Sends JSON commands to the BazSparkAutoCADBridge C# Add-in via a Named Pipe.
    The Add-in executes them safely inside a document lock on AutoCAD's Main Thread.

    This is the PREFERRED dispatcher when the Add-in is loaded and running.
    Falls back to AutoCADService (COM) only when the pipe is unavailable.
    """

    PIPE_NAME = r"\\.\pipe\bazspark_autocad"
    TIMEOUT_SEC = 30.0

    def __init__(self) -> None:
        self._available: bool = False
        if sys.platform == "win32":
            try:
                import pywintypes  # type: ignore  # noqa: F401

                self._available = self._ping()
            except ImportError:
                logger.debug("pywin32 not installed — Named Pipe dispatcher unavailable")

    @property
    def available(self) -> bool:
        return self._available

    def _ping(self) -> bool:
        """Quick connectivity test — try to open the pipe."""
        try:
            import win32file  # type: ignore

            h = win32file.CreateFile(
                self.PIPE_NAME,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
            win32file.CloseHandle(h)
            return True
        except Exception:
            return False

    def send(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a command and return the response dict."""
        # V291 SAFETY FIX: pywintypes/win32file/win32pipe are Windows-only.
        # Previously this method imported them unconditionally at the top,
        # causing ModuleNotFoundError on Linux/macOS CI — which made the
        # entire test suite report pywintypes as the failure reason and
        # blocked CI from reporting real issues.
        # Now we fail gracefully with a clear error message on non-Windows.
        if sys.platform != "win32":
            self._available = False
            return {
                "success": False,
                "error": (
                    "Named Pipe dispatcher is only available on Windows. "
                    "On Linux/macOS, install pywin32 in a Windows environment "
                    "or use the HTTP/COM fallback dispatcher."
                ),
            }

        try:
            import pywintypes  # type: ignore  # noqa: F401 — availability probe
        except ImportError as exc:
            self._available = False
            return {
                "success": False,
                "error": (
                    f"pywin32 not installed on this Windows system — Named Pipe "
                    f"dispatcher unavailable. Install with: pip install pywin32. "
                    f"ImportError: {exc}"
                ),
            }

        payload = {"command_id": str(time.time()), "action": action, "params": params}
        try:
            return _send_pipe_command(self.PIPE_NAME, payload, self.TIMEOUT_SEC)
        except pywintypes.error as e:
            if e.winerror == 2:  # ERROR_FILE_NOT_FOUND — pipe not running
                self._available = False
                return {
                    "success": False,
                    "error": "BazSparkAutoCADBridge Add-in not running. Load the DLL in AutoCAD first.",
                }
            raise


# ── Lazy service singletons ───────────────────────────────────────────────────
_autocad_svc: Any = None
_revit_svc: Any = None
_revit_pipe: RevitNamedPipeDispatcher | None = None
_autocad_pipe: AutoCADNamedPipeDispatcher | None = None


def _get_autocad() -> Any:
    global _autocad_svc
    if _autocad_svc is None and _autocad_available:
        _autocad_svc = AutoCADService()
    return _autocad_svc


def _get_autocad_pipe() -> AutoCADNamedPipeDispatcher:
    """Return the AutoCAD Named Pipe dispatcher (preferred, thread-safe)."""
    global _autocad_pipe
    if _autocad_pipe is None:
        _autocad_pipe = AutoCADNamedPipeDispatcher()
    return _autocad_pipe


def _get_revit_pipe() -> RevitNamedPipeDispatcher:
    """Return the Named Pipe dispatcher (preferred, thread-safe)."""
    global _revit_pipe
    if _revit_pipe is None:
        _revit_pipe = RevitNamedPipeDispatcher()
    return _revit_pipe


def _get_revit() -> Any:
    global _revit_svc
    if _revit_svc is None and _revit_available:
        _revit_svc = RevitService()
    return _revit_svc


# ── Command handlers ───────────────────────────────────────────────────────────


def _build_status_response(
    connected: bool, message: str, document_info: dict | None = None
) -> dict:
    return {
        "connected": connected,
        "message": message,
        "document_info": document_info if document_info else None,
    }


def _handle_autocad_connect(svc, args):
    """Handle the 'connect' action for AutoCAD."""
    ok = svc.connect(visible=args.get("visible", True), force_new=args.get("force_new", False))
    return {
        "success": ok,
        "message": "Connected to AutoCAD" if ok else "Failed to connect",
        "connected": svc.connected,
        "simulation_mode": svc.simulation_mode,
    }


def _handle_autocad_disconnect(svc, args):
    """Handle the 'disconnect' action for AutoCAD."""
    ok = svc.disconnect()
    return {
        "success": ok,
        "message": "Disconnected" if ok else "Failed to disconnect",
        "connected": svc.connected,
        "simulation_mode": getattr(svc, "simulation_mode", False),
    }


def _handle_autocad_status(svc, args):
    """Handle the 'status' action for AutoCAD."""
    doc_info = svc.get_document_info() if svc.connected else {}
    return _build_status_response(
        svc.connected, "AutoCAD service status", doc_info if doc_info else None
    )


def _handle_autocad_documents(svc, args):
    """Handle the 'documents' action for AutoCAD."""
    doc_info = svc.get_document_info()
    return {"success": True, "documents": [doc_info] if doc_info else []}


def _handle_autocad_read_dwg(svc, args):
    """Handle the 'read_dwg' action for AutoCAD."""
    result = svc.read_dwg(args["filepath"])
    if not result.get("success"):
        return {"error": result.get("error", "Failed to read DWG")}
    return {
        "filepath": args["filepath"],
        "metadata": result.get("metadata", {}),
        "layers": result.get("layers", []),
        "entities": result.get("entities", []),
        "blocks": result.get("blocks", {}),
        "entity_count": len(result.get("entities", [])),
    }


def _handle_autocad_write_dwg(svc, args):
    """Handle the 'write_dwg' action for AutoCAD."""
    ok = svc.write_dwg(args["filepath"], args.get("entities", []))
    if not ok:
        return {"error": "Failed to write DWG file"}
    return {"success": True, "message": "Successfully wrote DWG file"}


def _handle_autocad_draw_line(svc, args):
    """Handle the 'draw_line' action for AutoCAD."""
    handle = svc.draw_line(
        start_point=args["start_point"],
        end_point=args["end_point"],
        layer=args.get("layer", "0"),
        color=args.get("color", 0),
    )
    if not handle:
        return {"error": "Failed to draw line"}
    return {"success": True, "message": "Line drawn successfully", "handle": handle}


def _handle_autocad_draw_polyline(svc, args):
    """Handle the 'draw_polyline' action for AutoCAD."""
    handle = svc.draw_polyline(
        vertices=args["vertices"],
        layer=args.get("layer", "0"),
        color=args.get("color", 0),
        closed=args.get("closed", False),
    )
    if not handle:
        return {"error": "Failed to draw polyline"}
    return {"success": True, "message": "Polyline drawn successfully", "handle": handle}


def _handle_autocad_draw_circle(svc, args):
    """Handle the 'draw_circle' action for AutoCAD."""
    handle = svc.draw_circle(
        center=args["center"],
        radius=args["radius"],
        layer=args.get("layer", "0"),
        color=args.get("color", 0),
    )
    if not handle:
        return {"error": "Failed to draw circle"}
    return {"success": True, "message": "Circle drawn successfully", "handle": handle}


def _handle_autocad_draw_text(svc, args):
    """Handle the 'draw_text' action for AutoCAD."""
    handle = svc.draw_text(
        text=args["text"],
        insertion_point=args["insertion_point"],
        height=args.get("height", 0.2),
        layer=args.get("layer", "0"),
        color=args.get("color", 0),
    )
    if not handle:
        return {"error": "Failed to draw text"}
    return {"success": True, "message": "Text drawn successfully", "handle": handle}


def _handle_autocad_save(svc, args):
    """Handle the 'save' action for AutoCAD."""
    ok = svc.save(args.get("filepath", ""))
    if not ok:
        return {"error": "Failed to save document"}
    return {"success": True, "message": "Document saved successfully"}


def _handle_autocad_upload_dwg(svc, args):
    """Handle the 'upload_dwg' action for AutoCAD."""
    # Decode base64 content, write to temp file, read it
    contents = base64.b64decode(args["contents_base64"])
    safe_name = args.get("filename", "upload.dwg")
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, safe_name)
    try:
        with open(temp_path, "wb") as f:
            f.write(contents)
        result = svc.read_dwg(temp_path)
        if not result.get("success"):
            return {"error": result.get("error", "Failed to read DWG")}
        return {
            "filepath": safe_name,
            "metadata": result.get("metadata", {}),
            "layers": result.get("layers", []),
            "entities": result.get("entities", []),
            "blocks": result.get("blocks", {}),
            "entity_count": len(result.get("entities", [])),
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)


def _handle_autocad_delete_entity(svc, args):
    """Handle the 'delete_entity' action for AutoCAD."""
    ok = svc.delete_entity(args["handle"])
    if not ok:
        return {"error": "Failed to delete entity"}
    return {"success": True, "message": "Entity deleted successfully"}


def _handle_autocad_modify_entity(svc, args):
    """Handle the 'modify_entity' action for AutoCAD."""
    ok = svc.modify_entity(handle=args["handle"], properties=args.get("properties", {}))
    if not ok:
        return {"error": "Failed to modify entity"}
    return {"success": True, "message": "Entity modified successfully"}


def _registry_entry_or_none(service: str, action: str):
    """Resolve action against the unified registry (None when unavailable/disabled)."""
    if not _registry_available:
        return None
    return _registry.get_command_entry(service, action)


def _pipe_routed(service: str, entry) -> bool:
    """True when this command is supported by the C# add-in named pipe."""
    return "pipe" in (entry.get("channel") or [])


def _dispatch_via_pipe(
    service: str, dispatcher, canonical_action: str, entry, args: dict[str, Any]
) -> dict[str, Any]:
    """Send one command over the pipe using addin action name + normalized params."""
    assert _registry_available  # noqa: S101 — callers guarantee availability
    addin_action = entry["addin_action"]
    params = _registry.normalize_params(service, canonical_action, args)
    logger.info(
        "[%s] Routing %s via Named Pipe (C# Add-in action=%s)",
        service.capitalize(),
        canonical_action,
        addin_action,
    )
    return dispatcher.send(addin_action, params)


def _dispatch_autocad(
    action: str, args: dict[str, Any]
) -> Any:  # NOSONAR — S3776: cognitive complexity is inherent to the safety-critical algorithm
    """
    Dispatch an AutoCAD action locally and return the result dict.

    Routing priority:
    1. AutoCADNamedPipeDispatcher — sends command to BazSparkAutoCADBridge C# Add-in
       via Named Pipe so it runs on AutoCAD's main thread inside a document lock.
       Actions and params are resolved/normalized through core/command_registry.json.
    2. AutoCADService (COM fallback) — direct COM API calls, only when the Add-in
       is not loaded.
    """
    entry = _registry_entry_or_none("autocad", action)

    if _registry_available and entry is None:
        # D4 mirror on the agent side: unregistered commands never touch CAD apps.
        return {"success": False, "error": f"Unknown AutoCAD command: {action}"}

    if entry is not None and _pipe_routed("autocad", entry):
        pipe = _get_autocad_pipe()
        if pipe.available:
            try:
                return _dispatch_via_pipe("autocad", pipe, action, entry, args)
            except RuntimeError:
                pass  # stale singleton or pipe vanished mid-call — fall through to fallback
        logger.warning(
            "[AutoCAD] Named Pipe unavailable for %s — "
            "is BazSparkAutoCADBridge loaded in AutoCAD?",
            action,
        )

    svc = _get_autocad()
    if svc is None:
        return {"error": "AutoCADService not available on this machine"}

    # Map actions to handler functions to reduce cognitive complexity
    action_handlers = {
        "connect": _handle_autocad_connect,
        "disconnect": _handle_autocad_disconnect,
        "status": _handle_autocad_status,
        "documents": _handle_autocad_documents,
        "read_dwg": _handle_autocad_read_dwg,
        "write_dwg": _handle_autocad_write_dwg,
        "draw_line": _handle_autocad_draw_line,
        "draw_polyline": _handle_autocad_draw_polyline,
        "draw_circle": _handle_autocad_draw_circle,
        "draw_text": _handle_autocad_draw_text,
        "save": _handle_autocad_save,
        "upload_dwg": _handle_autocad_upload_dwg,
        "delete_entity": _handle_autocad_delete_entity,
        "modify_entity": _handle_autocad_modify_entity,
    }

    if action in action_handlers:
        return action_handlers[action](svc, args)
    elif entry is not None:
        # Registered but pipe-only (e.g. send_command / plot_pdf / capture_screen).
        return {
            "success": False,
            "error": (
                f"{action} requires the BazSparkAutoCADBridge C# Add-in "
                "(named pipe). Load the DLL in AutoCAD first."
            ),
        }
    else:
        return {"error": f"Unknown AutoCAD action: {action}"}


def _handle_revit_connect(svc, args):
    """Handle the 'connect' action for Revit."""
    ok = svc.connect(method=args.get("method", "auto"))
    return {
        "success": ok,
        "message": f"Connected via {getattr(svc, 'connection_method', 'unknown')}",
        "connected": svc.connected,
        "simulation_mode": getattr(svc, "simulation_mode", False),
        "connection_method": getattr(svc, "connection_method", None),
    }


def _handle_revit_disconnect(svc, args):
    """Handle the 'disconnect' action for Revit."""
    ok = svc.disconnect()
    return {
        "success": ok,
        "message": "Disconnected from Revit" if ok else "Disconnect failed",
        "connected": svc.connected,
        "simulation_mode": getattr(svc, "simulation_mode", False),
    }


def _handle_revit_status(svc, args):
    """Handle the 'status' action for Revit."""
    doc_info = svc.get_document_info() if svc.connected else {}
    return {
        "connected": svc.connected,
        "message": "Revit service status",
        "connection_method": getattr(svc, "connection_method", None),
        "document_info": doc_info if doc_info else None,
    }


def _handle_revit_get_elements(svc, args):
    """Handle the 'get_elements' action for Revit."""
    elements = svc.get_elements(
        category=args.get("category"),
        element_class=args.get("element_class"),
    )
    return {"success": True, "elements": elements, "count": len(elements)}


def _handle_revit_get_selected_elements(svc, args):
    """Handle the 'get_selected_elements' action for Revit."""
    elements = svc.get_selected_elements()
    return {"success": True, "elements": elements, "count": len(elements)}


def _handle_revit_get_element(svc, args):
    """Handle the 'get_element' action for Revit."""
    element = svc.get_element_by_id(args["element_id"])
    if element:
        return {"success": True, "element": element}
    return {"success": False, "error": "Element not found"}


def _handle_revit_get_element_parameters(svc, args):
    """Handle the 'get_element_parameters' action for Revit."""
    params = svc.get_element_parameters(args["element_id"])
    return {"success": True, "parameters": params}


def _handle_revit_create_wall(svc, args):
    """Handle the 'create_wall' action for Revit."""
    eid = svc.create_wall(
        start_point=args["start_point"],
        end_point=args["end_point"],
        height=args.get("height"),
        level=args.get("level"),
        wall_type=args.get("wall_type"),
    )
    return {
        "success": eid is not None,
        "message": f"Wall: {eid}" if eid else "Failed",
        "element_id": eid,
    }


def _handle_revit_create_floor(svc, args):
    """Handle the 'create_floor' action for Revit."""
    eid = svc.create_floor(
        boundary_points=args["boundary_points"],
        level=args.get("level"),
        floor_type=args.get("floor_type"),
    )
    return {
        "success": eid is not None,
        "message": f"Floor: {eid}" if eid else "Failed",
        "element_id": eid,
    }


def _handle_revit_create_door(svc, args):
    """Handle the 'create_door' action for Revit."""
    eid = svc.create_door(
        host_wall_id=args["host_wall_id"],
        location_point=args["location_point"],
        family_type=args.get("family_type"),
        level=args.get("level"),
    )
    return {
        "success": eid is not None,
        "message": f"Door: {eid}" if eid else "Failed",
        "element_id": eid,
    }


def _handle_revit_create_window(svc, args):
    """Handle the 'create_window' action for Revit."""
    eid = svc.create_window(
        host_wall_id=args["host_wall_id"],
        location_point=args["location_point"],
        family_type=args.get("family_type"),
        level=args.get("level"),
    )
    return {
        "success": eid is not None,
        "message": f"Window: {eid}" if eid else "Failed",
        "element_id": eid,
    }


def _handle_revit_create_column(svc, args):
    """Handle the 'create_column' action for Revit."""
    eid = svc.create_column(
        location_point=args["location_point"],
        height=args.get("height"),
        level=args.get("level"),
        column_type=args.get("column_type"),
    )
    return {
        "success": eid is not None,
        "message": f"Column: {eid}" if eid else "Failed",
        "element_id": eid,
    }


def _handle_revit_create_beam(svc, args):
    """Handle the 'create_beam' action for Revit."""
    eid = svc.create_beam(
        start_point=args["start_point"],
        end_point=args["end_point"],
        level=args.get("level"),
        beam_type=args.get("beam_type"),
    )
    return {
        "success": eid is not None,
        "message": f"Beam: {eid}" if eid else "Failed",
        "element_id": eid,
    }


def _handle_revit_create_family(svc, args):
    """Handle the 'create_family' action for Revit."""
    eid = svc.create_family_instance(
        family_name=args["family_name"],
        category=args.get("category"),
        location_point=args["location_point"],
        level=args.get("level"),
        parameters=args.get("parameters", {}),
    )
    return {
        "success": eid is not None,
        "message": f"Family: {eid}" if eid else "Failed",
        "element_id": eid,
    }


def _handle_revit_update_parameters(svc, args):
    """Handle the 'update_parameters' action for Revit."""
    success = True
    for pname, val in args.get("parameters", {}).items():
        if not svc.set_element_parameter(args["element_id"], pname, val):
            success = False
    return {
        "success": success,
        "message": "Parameters updated" if success else "Some parameters failed",
    }


def _handle_revit_delete_element(svc, args):
    """Handle the 'delete_element' action for Revit."""
    ok = svc.delete_element(args["element_id"])
    if ok:
        return {"success": True, "message": f"Element {args['element_id']} deleted"}
    return {"error": "Failed to delete element"}


def _handle_revit_get_special_actions(svc, args):  # NOSONAR - python:S1481
    """Handle special actions like get_views, get_levels, get_grids, get_worksets for Revit."""
    action = args.get("special_action", "")
    method = getattr(svc, action)
    items = method()
    return {"success": True, "elements": items, "count": len(items)}


def _handle_revit_execute_ai_command(svc, args):
    """Handle the 'execute_ai_command' action for Revit."""
    return svc.execute_ai_command(args.get("command", ""), args.get("context", {}))


def _dispatch_revit(
    action: str, args: dict[str, Any]
) -> Any:  # NOSONAR — S3776: cognitive complexity is inherent to the safety-critical algorithm
    """
    Dispatch a Revit action locally and return the result dict.

    Routing priority:
    1. RevitNamedPipeDispatcher — sends command to BazSparkRevitBridge C# Add-in
       via Named Pipe so it runs on Revit's Main Thread (ExternalEvent). SAFE.
       Actions and param shapes are resolved/normalized through
       core/command_registry.json (A2) — e.g. canonical ``get_views`` maps to
       add-in ``list_views``, ``start_point/end_point`` map to ``x1/y1/x2/y2``.
    2. RevitService (pythonnet fallback) — direct API calls, only safe in limited
       contexts and only when the Add-in is not installed.
    """
    entry = _registry_entry_or_none("revit", action)

    if _registry_available and entry is None:
        # D4 mirror on the agent side: unregistered commands never touch CAD apps.
        return {"success": False, "error": f"Unknown Revit command: {action}"}

    # ── update_parameters fans out into N set_parameter calls over the pipe ──
    if entry is not None and entry.get("expands_to") == "set_parameter":
        target_canonical, calls = _registry.expand_update_parameters(args)
        target_entry = _registry.get_command_entry("revit", target_canonical)
        pipe = _get_revit_pipe()
        if pipe.available and target_entry is not None:
            updated, failed = 0, []
            for call in calls:
                try:
                    res = _dispatch_via_pipe(
                        "revit", pipe, target_canonical, target_entry, call
                    )
                except RuntimeError:
                    failed.append(call.get("name"))
                    continue
                if isinstance(res, dict) and res.get("success"):
                    updated += 1
                else:
                    failed.append(call.get("name"))
            return {
                "success": not failed,
                "updated": updated,
                "failed": failed,
                "message": "Parameters updated" if not failed else "Some parameters failed",
            }
        # fall through to local handler below

    if entry is not None and _pipe_routed("revit", entry):
        pipe = _get_revit_pipe()
        if pipe.available:
            try:
                return _dispatch_via_pipe("revit", pipe, action, entry, args)
            except RuntimeError:
                pass  # stale singleton or pipe vanished mid-call — fall through to fallback
        logger.warning(
            "[Revit] Named Pipe unavailable for %s — "
            "is BazSparkRevitBridge Add-in loaded in Revit?",
            action,
        )
        # Fall through to RevitService (pythonnet) below

    svc = _get_revit()
    if svc is None:
        return {"error": "RevitService not available on this machine"}

    # Map actions to handler functions to reduce cognitive complexity
    action_handlers = {
        "connect": _handle_revit_connect,
        "disconnect": _handle_revit_disconnect,
        "status": _handle_revit_status,
        "get_elements": _handle_revit_get_elements,
        "get_selected_elements": _handle_revit_get_selected_elements,
        "get_element": _handle_revit_get_element,
        "get_element_parameters": _handle_revit_get_element_parameters,
        "create_wall": _handle_revit_create_wall,
        "create_floor": _handle_revit_create_floor,
        "create_door": _handle_revit_create_door,
        "create_window": _handle_revit_create_window,
        "create_column": _handle_revit_create_column,
        "create_beam": _handle_revit_create_beam,
        "create_family": _handle_revit_create_family,
        "update_parameters": _handle_revit_update_parameters,
        "delete_element": _handle_revit_delete_element,
        "execute_ai_command": _handle_revit_execute_ai_command,
    }

    if action in action_handlers:
        return action_handlers[action](svc, args)
    elif action in ("get_views", "get_levels", "get_grids", "get_worksets"):
        return _handle_revit_get_special_actions(svc, {"special_action": action})
    elif entry is not None:
        # Registered but pipe-only (e.g. post_command / export_pdf / capture_screen).
        return {
            "success": False,
            "error": (
                f"{action} requires the BazSparkRevitBridge C# Add-in "
                "(named pipe). Start Revit with the Add-in loaded first."
            ),
        }
    else:
        return {"error": f"Unknown Revit action: {action}"}


def _dispatch(action_full: str, args: dict[str, Any]) -> Any:
    """Route action 'autocad/draw_line' or 'revit/create_wall' to the right service."""
    if "/" not in action_full:
        return {"error": f"Malformed action: {action_full!r}"}
    service, action = action_full.split("/", 1)
    if service == "autocad":
        return _dispatch_autocad(action, args)
    elif service == "revit":
        return _dispatch_revit(action, args)
    else:
        return {"error": f"Unknown service: {service!r}"}


# ── WebSocket agent loop ──────────────────────────────────────────────────────


def _build_ws_connect_kwargs(api_key: str) -> dict:
    """Build websockets.connect kwargs across library versions.

    websockets >= 14 renamed ``extra_headers`` to ``additional_headers``;
    older releases only accept ``extra_headers``. Detected at runtime so the
    agent works with either install.
    """
    import inspect

    kwargs: dict[str, Any] = {"ping_interval": 20, "ping_timeout": 30}
    if not api_key:
        return kwargs

    try:
        params = inspect.signature(websockets.connect).parameters
    except (TypeError, ValueError):  # pragma: no cover — defensive
        return kwargs

    if "additional_headers" in params:
        # websockets >= 14: list of 2-tuples.
        kwargs["additional_headers"] = [("X-API-Key", api_key)]
    elif "extra_headers" in params:
        kwargs["extra_headers"] = {"X-API-Key": api_key}
    else:  # pragma: no cover — unknown future signature
        logger.warning(
            "websockets.connect supports no header argument; "
            "pass the key via ?token= query param instead"
        )
    return kwargs


async def _agent_loop(uri: str, api_key: str = "") -> None:
    """Connect, listen for commands, execute them, and send back results."""
    logger.info("Connecting to %s …", uri)
    connect_kwargs = _build_ws_connect_kwargs(api_key)
    async with websockets.connect(uri, **connect_kwargs) as ws:
        logger.info("✅ Connected to BAZspark server. Waiting for commands …")
        _partial = ""
        async for raw in ws:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            _partial += raw
            try:
                msg = json.loads(_partial)
            except (json.JSONDecodeError, TypeError):
                continue
            _partial = ""

            msg_type = msg.get("type")

            if msg_type == "pong":
                continue

            if msg_type == "ping":
                # Server heartbeat (WS_PING_INTERVAL_SECONDS): MUST be
                # answered or the server closes the socket with 4008 after
                # WS_HEARTBEAT_TIMEOUT_SECONDS, dropping in-flight commands.
                await ws.send(json.dumps({"type": "pong"}))
                continue

            if msg_type == "command":
                cmd_id = msg.get("id")
                action = msg.get("action", "")
                args = msg.get("args", {})
                logger.info("▶ Command [%s]: %s args=%s", cmd_id, action, list(args.keys()))

                try:
                    payload = await asyncio.get_event_loop().run_in_executor(
                        None, _dispatch, action, args
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Command %s failed", action)
                    payload = {"error": f"Command failed: {type(exc).__name__}"}

                await ws.send(json.dumps({"type": "response", "id": cmd_id, "payload": payload}))
                logger.info("◀ Response sent for [%s]", cmd_id)

            else:
                logger.debug("Unhandled message type: %s", msg_type)


async def run(server_url: str, api_key: str) -> None:
    """Main loop with exponential back-off reconnection."""
    uri = f"{server_url.rstrip('/')}/api/v1/agent/ws"
    backoff = 2.0
    max_backoff = 60.0

    while True:
        try:
            await _agent_loop(uri, api_key=api_key)
            backoff = 2.0  # reset on clean disconnect
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 4003:
                logger.error("❌ Authentication failed: invalid API key. Exiting.")
                return
            logger.warning(
                "Connection rejected (status %s). Retrying in %.0fs …", e.status_code, backoff
            )
        except (OSError, websockets.exceptions.WebSocketException) as e:
            logger.warning("Connection error: %s. Retrying in %.0fs …", e, backoff)
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error: %s. Retrying in %.0fs …", e, backoff)

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


# ── CLI entry-point ───────────────────────────────────────────────────────────


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    parser = argparse.ArgumentParser(
        description="BAZspark Local Agent — bridges cloud commands to local AutoCAD/Revit",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--server",
        default=os.getenv("BAZSPARK_SERVER", "wss://ahmdelbaz28-bazspark.hf.space"),
        help="WebSocket server URL (wss://…)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("BAZSPARK_API_KEY", ""),
        help="Your BAZspark API key",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    args = parser.parse_args()

    logging.getLogger().setLevel(args.log_level)

    if not args.api_key:
        parser.error("API key is required. Pass --api-key or set BAZSPARK_API_KEY env var.")

    logger.info("BAZspark Local Agent starting …")
    logger.info("  Server  : %s", args.server)
    logger.info("  Platform: %s", sys.platform)
    logger.info("  AutoCAD : %s", "available" if _autocad_available else "NOT available")
    logger.info("  Revit   : %s", "available" if _revit_available else "NOT available")

    asyncio.run(run(args.server, args.api_key))


if __name__ == "__main__":
    main()
