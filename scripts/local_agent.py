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
import time
import traceback
from typing import Any, Dict

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
        "available on %s — running in limited/test mode.", sys.platform
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


# ── Lazy service singletons ───────────────────────────────────────────────────
_autocad_svc: Any = None
_revit_svc: Any = None


def _get_autocad() -> Any:
    global _autocad_svc
    if _autocad_svc is None and _autocad_available:
        _autocad_svc = AutoCADService()
    return _autocad_svc


def _get_revit() -> Any:
    global _revit_svc
    if _revit_svc is None and _revit_available:
        _revit_svc = RevitService()
    return _revit_svc


# ── Command dispatcher ────────────────────────────────────────────────────────

def _dispatch_autocad(action: str, args: Dict[str, Any]) -> Any:
    """Dispatch an AutoCAD action locally and return the result dict."""
    svc = _get_autocad()
    if svc is None:
        return {"error": "AutoCADService not available on this machine"}

    if action == "connect":
        ok = svc.connect(visible=args.get("visible", True), force_new=args.get("force_new", False))
        return {
            "success": ok,
            "message": "Connected to AutoCAD" if ok else "Failed to connect",
            "connected": svc.connected,
            "simulation_mode": svc.simulation_mode,
        }

    elif action == "disconnect":
        ok = svc.disconnect()
        return {
            "success": ok,
            "message": "Disconnected" if ok else "Failed to disconnect",
            "connected": svc.connected,
            "simulation_mode": getattr(svc, "simulation_mode", False),
        }

    elif action == "status":
        doc_info = svc.get_document_info() if svc.connected else {}
        return {
            "connected": svc.connected,
            "message": "AutoCAD service status",
            "document_info": doc_info if doc_info else None,
        }

    elif action == "documents":
        doc_info = svc.get_document_info()
        return {"success": True, "documents": [doc_info] if doc_info else []}

    elif action == "read_dwg":
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

    elif action == "write_dwg":
        ok = svc.write_dwg(args["filepath"], args.get("entities", []))
        if not ok:
            return {"error": "Failed to write DWG file"}
        return {"success": True, "message": "Successfully wrote DWG file"}

    elif action == "draw_line":
        handle = svc.draw_line(
            start_point=args["start_point"],
            end_point=args["end_point"],
            layer=args.get("layer", "0"),
            color=args.get("color", 0),
        )
        if not handle:
            return {"error": "Failed to draw line"}
        return {"success": True, "message": "Line drawn successfully", "handle": handle}

    elif action == "draw_polyline":
        handle = svc.draw_polyline(
            vertices=args["vertices"],
            layer=args.get("layer", "0"),
            color=args.get("color", 0),
            closed=args.get("closed", False),
        )
        if not handle:
            return {"error": "Failed to draw polyline"}
        return {"success": True, "message": "Polyline drawn successfully", "handle": handle}

    elif action == "draw_circle":
        handle = svc.draw_circle(
            center=args["center"],
            radius=args["radius"],
            layer=args.get("layer", "0"),
            color=args.get("color", 0),
        )
        if not handle:
            return {"error": "Failed to draw circle"}
        return {"success": True, "message": "Circle drawn successfully", "handle": handle}

    elif action == "draw_text":
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

    elif action == "save":
        ok = svc.save(args.get("filepath", ""))
        if not ok:
            return {"error": "Failed to save document"}
        return {"success": True, "message": "Document saved successfully"}

    elif action == "upload_dwg":
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

    elif action == "delete_entity":
        ok = svc.delete_entity(args["handle"])
        if not ok:
            return {"error": "Failed to delete entity"}
        return {"success": True, "message": "Entity deleted successfully"}

    elif action == "modify_entity":
        ok = svc.modify_entity(handle=args["handle"], properties=args.get("properties", {}))
        if not ok:
            return {"error": "Failed to modify entity"}
        return {"success": True, "message": "Entity modified successfully"}

    else:
        return {"error": f"Unknown AutoCAD action: {action}"}


def _dispatch_revit(action: str, args: Dict[str, Any]) -> Any:
    """Dispatch a Revit action locally and return the result dict."""
    svc = _get_revit()
    if svc is None:
        return {"error": "RevitService not available on this machine"}

    if action == "connect":
        ok = svc.connect(method=args.get("method", "auto"))
        return {
            "success": ok,
            "message": f"Connected via {getattr(svc, 'connection_method', 'unknown')}",
            "connected": svc.connected,
            "simulation_mode": getattr(svc, "simulation_mode", False),
            "connection_method": getattr(svc, "connection_method", None),
        }

    elif action == "disconnect":
        ok = svc.disconnect()
        return {
            "success": ok,
            "message": "Disconnected from Revit" if ok else "Disconnect failed",
            "connected": svc.connected,
            "simulation_mode": getattr(svc, "simulation_mode", False),
        }

    elif action == "status":
        doc_info = svc.get_document_info() if svc.connected else {}
        return {
            "connected": svc.connected,
            "message": "Revit service status",
            "connection_method": getattr(svc, "connection_method", None),
            "document_info": doc_info if doc_info else None,
        }

    elif action == "get_elements":
        elements = svc.get_elements(
            category=args.get("category"),
            element_class=args.get("element_class"),
        )
        return {"success": True, "elements": elements, "count": len(elements)}

    elif action == "get_selected_elements":
        elements = svc.get_selected_elements()
        return {"success": True, "elements": elements, "count": len(elements)}

    elif action == "get_element":
        element = svc.get_element_by_id(args["element_id"])
        if element:
            return {"success": True, "element": element}
        return {"success": False, "error": "Element not found"}

    elif action == "get_element_parameters":
        params = svc.get_element_parameters(args["element_id"])
        return {"success": True, "parameters": params}

    elif action == "create_wall":
        eid = svc.create_wall(
            start_point=args["start_point"], end_point=args["end_point"],
            height=args.get("height"), level=args.get("level"), wall_type=args.get("wall_type")
        )
        return {"success": eid is not None, "message": f"Wall: {eid}" if eid else "Failed", "element_id": eid}

    elif action == "create_floor":
        eid = svc.create_floor(
            boundary_points=args["boundary_points"], level=args.get("level"), floor_type=args.get("floor_type")
        )
        return {"success": eid is not None, "message": f"Floor: {eid}" if eid else "Failed", "element_id": eid}

    elif action == "create_door":
        eid = svc.create_door(
            host_wall_id=args["host_wall_id"], location_point=args["location_point"],
            family_type=args.get("family_type"), level=args.get("level")
        )
        return {"success": eid is not None, "message": f"Door: {eid}" if eid else "Failed", "element_id": eid}

    elif action == "create_window":
        eid = svc.create_window(
            host_wall_id=args["host_wall_id"], location_point=args["location_point"],
            family_type=args.get("family_type"), level=args.get("level")
        )
        return {"success": eid is not None, "message": f"Window: {eid}" if eid else "Failed", "element_id": eid}

    elif action == "create_column":
        eid = svc.create_column(
            location_point=args["location_point"], height=args.get("height"),
            level=args.get("level"), column_type=args.get("column_type")
        )
        return {"success": eid is not None, "message": f"Column: {eid}" if eid else "Failed", "element_id": eid}

    elif action == "create_beam":
        eid = svc.create_beam(
            start_point=args["start_point"], end_point=args["end_point"],
            level=args.get("level"), beam_type=args.get("beam_type")
        )
        return {"success": eid is not None, "message": f"Beam: {eid}" if eid else "Failed", "element_id": eid}

    elif action == "create_family":
        eid = svc.create_family_instance(
            family_name=args["family_name"], category=args.get("category"),
            location_point=args["location_point"], level=args.get("level"),
            parameters=args.get("parameters", {})
        )
        return {"success": eid is not None, "message": f"Family: {eid}" if eid else "Failed", "element_id": eid}

    elif action == "update_parameters":
        success = True
        for pname, val in args.get("parameters", {}).items():
            if not svc.set_element_parameter(args["element_id"], pname, val):
                success = False
        return {"success": success, "message": "Parameters updated" if success else "Some parameters failed"}

    elif action == "delete_element":
        ok = svc.delete_element(args["element_id"])
        if ok:
            return {"success": True, "message": f"Element {args['element_id']} deleted"}
        return {"error": "Failed to delete element"}

    elif action in ("get_views", "get_levels", "get_grids", "get_worksets"):
        method = getattr(svc, action)
        items = method()
        return {"success": True, "elements": items, "count": len(items)}

    elif action == "execute_ai_command":
        return svc.execute_ai_command(args.get("command", ""), args.get("context", {}))

    else:
        return {"error": f"Unknown Revit action: {action}"}


def _dispatch(action_full: str, args: Dict[str, Any]) -> Any:
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

async def _agent_loop(uri: str) -> None:
    """Connect, listen for commands, execute them, and send back results."""
    logger.info("Connecting to %s …", uri)
    async with websockets.connect(uri, ping_interval=20, ping_timeout=30) as ws:
        logger.info("✅ Connected to BAZspark server. Waiting for commands …")
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Received non-JSON message, skipping")
                continue

            msg_type = msg.get("type")

            if msg_type == "pong":
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
                except Exception:  # noqa: BLE001
                    payload = {"error": traceback.format_exc()}

                await ws.send(json.dumps({"type": "response", "id": cmd_id, "payload": payload}))
                logger.info("◀ Response sent for [%s]", cmd_id)

            else:
                logger.debug("Unhandled message type: %s", msg_type)


async def run(server_url: str, api_key: str) -> None:
    """Main loop with exponential back-off reconnection."""
    uri = f"{server_url.rstrip('/')}/api/v1/agent/ws?api_key={api_key}"
    backoff = 2.0
    max_backoff = 60.0

    while True:
        try:
            await _agent_loop(uri)
            backoff = 2.0  # reset on clean disconnect
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 4003:
                logger.error("❌ Authentication failed: invalid API key. Exiting.")
                return
            logger.warning("Connection rejected (status %s). Retrying in %.0fs …", e.status_code, backoff)
        except (OSError, websockets.exceptions.WebSocketException) as e:
            logger.warning("Connection error: %s. Retrying in %.0fs …", e, backoff)
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected error: %s. Retrying in %.0fs …", e, backoff)

        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


# ── CLI entry-point ───────────────────────────────────────────────────────────

def main() -> None:
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
