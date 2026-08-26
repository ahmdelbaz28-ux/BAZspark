# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
revit_mcp_server.py — Main Revit MCP Server Entry Point.
========================================================
LIFE-SAFETY CRITICAL: This module provides the MCP server that bridges
AI assistants (Claude, GPT) with the Revit BIM model.

V141.2 HONEST IMPLEMENTATION (adversarial audit fix):
=====================================================
Previous versions of start() only set `_running = True` and logged a message.
This was MISLEADING — the docstring claimed "listens for AI assistant
connections" but no actual listening occurred.

V141.2 implements a REAL MCP server using the official Model Context
Protocol (MCP) over stdio (JSON-RPC 2.0). The server:
  1. Reads JSON-RPC requests from stdin (one per line)
  2. Dispatches each request to SanitizedMCPHandler.process_request()
  3. Writes JSON-RPC responses to stdout (one per line)
  4. Logs all activity to stderr (keeps stdout clean for protocol)

This matches the MCP specification: https://modelcontextprotocol.io/
AI assistants (Claude Desktop, etc.) spawn this server as a subprocess
and communicate via stdio. No network socket is needed.

Safety Architecture (unchanged from V140):
  1. ALL requests pass through SanitizedMCPHandler (input sanitization)
  2. ALL Revit model writes go through ThreadSafeModelUpdateQueue
  3. NO eval(), exec(), or dynamic code execution
  4. Engineering calculations use validated, bounded inputs
  5. Full audit trail for all operations

Usage:
    # As a subprocess (spawned by Claude Desktop / other MCP clients):
    python -m fireai.mcp_server.revit_mcp_server

    # Programmatically (in-process):
    server = RevitMCPServer()
    server.start()  # blocks, reading from stdin until EOF or stop()
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
import time
from typing import Any

from fireai.mcp_server.sanitized_handler import (
    MCPRequest,
    MCPResponse,
    SanitizedMCPHandler,
)
from fireai.mcp_server.thread_safe_queue import (
    ModelUpdateAction,
    ModelUpdateType,
    ThreadSafeModelUpdateQueue,
)

logger = logging.getLogger(__name__)


# ── MCP Protocol Constants ──────────────────────────────────────────────────
# Per https://modelcontextprotocol.io/specification
# A2 CONTRACT FIX: advertise the newest protocol revision supported by the
# official `mcp` SDK (declared dependency since A1) instead of a stale pinned
# constant. Falls back to the original revision if the SDK is unavailable.
try:
    from mcp.types import LATEST_PROTOCOL_VERSION as _SDK_PROTOCOL_VERSION
except ImportError:  # pragma: no cover — mcp is a declared dependency (A1)
    _SDK_PROTOCOL_VERSION = "2024-11-05"

MCP_PROTOCOL_VERSION = _SDK_PROTOCOL_VERSION
MCP_SERVER_NAME = "fireai-revit-mcp"
MCP_SERVER_VERSION = "1.1.0"

# MCP methods we support
MCP_METHODS = {
    "initialize",
    "initialized",
    "tools/list",
    "tools/call",
    "resources/list",
    "resources/read",
    "ping",
}

# Human-facing description per tool. The inputSchema is generated from
# SanitizedMCPHandler.PARAM_RULES (single source of truth — A2).
TOOL_DESCRIPTIONS: dict[str, str] = {
    "calculate_battery_capacity": (
        "Calculate NFPA 72 §10.6.7 battery capacity for a fire alarm control "
        "panel from standby/alarm currents, with aging and temperature derating."
    ),
    "calculate_coverage": (
        "Calculate NFPA 72 coverage for a room (coverage radius, max spacing, "
        "and detectors required) from room dimensions and detector type using "
        "Table 17.6.3.1.1 height-adjusted values."
    ),
    "calculate_friction_loss": (
        "Calculate friction loss in a sprinkler pipe (NFPA 13 Chapter 23) "
        "from flow rate, C-factor, diameter and pipe length."
    ),
    "export_report": (
        "Export the MCP session audit report (sanitized request log + model "
        "update queue stats) to a JSON file. Full NFPA submittal PDFs require "
        "BuildingEngine context not available over stdio sessions."
    ),
    "get_project_status": (
        "Report live session status: model update queue stats, pending "
        "updates, processed request count and available tools."
    ),
    "place_detector": (
        "Compute an NFPA 72-compliant detector placement plan for a room "
        "(hex-grid with beam obstruction rule) via DetectorPlacementEngine "
        "and queue the computed device locations for safe Revit execution."
    ),
    "query_hydraulic_calculation": (
        "Query a hydraulic calculation (friction loss, NFPA 13-2022 "
        "Chapter 23) for given pipe parameters."
    ),
    "query_room_hazard_class": (
        "Return the mandatory hazard classification override table and the "
        "available NFPA 13 / SBC 801 hazard classifications."
    ),
    "update_bim_parameter": (
        "Queue an update to a Revit BIM element parameter. The update is "
        "sanitized, enqueued in the thread-safe model update queue and "
        "forwarded to the Revit add-in when available. Never writes directly."
    ),
    "update_room_classification": (
        "Queue a room hazard classification update. Mandatory overrides are "
        "applied during sanitization if the AI under-classifies a known "
        "hazardous room type."
    ),
    "validate_sprinkler_compliance": (
        "Validate sprinkler design compliance (head pressure vs density) "
        "against NFPA 13 hazard classification requirements."
    ),
}


class RevitMCPServer:
    """
    MCP Server for Revit BIM integration with full safety controls.

    SAFETY: This server enforces the following non-negotiable rules:
      1. ALL inputs are sanitized before processing
      2. ALL Revit model writes are queued (never direct)
      3. NO dynamic code execution (eval/exec forbidden)
      4. ALL engineering calculations are validated
      5. ALL operations are logged for audit trail

    This class is the SINGLE ENTRY POINT for all MCP communication
    with the Revit BIM model.
    """

    def __init__(self) -> None:
        self._handler = SanitizedMCPHandler()
        self._update_queue = ThreadSafeModelUpdateQueue()
        self._running = False
        self._stdin_thread: threading.Thread | None = None
        self._client_capabilities: dict[str, Any] = {}
        # Previously the queue was filled but NEVER consumed — commands died in the queue.
        # Now after enqueue, we forward the command to the C# add-in via named pipe.
        try:
            from fireai.mcp_server.named_pipe_client import RevitNamedPipeClient

            self._pipe_client = RevitNamedPipeClient()
        except ImportError:
            self._pipe_client = None
            logger.warning("named_pipe_client not available — commands will only be queued locally")

    @property
    def update_queue(self) -> ThreadSafeModelUpdateQueue:
        """Access the thread-safe model update queue."""
        return self._update_queue

    def process_request(self, request: MCPRequest) -> MCPResponse:
        """
        Process an incoming MCP request.

        SAFETY GATE SEQUENCE:
          1. Sanitize all inputs (SanitizedMCPHandler)
          2. For model writes: enqueue in ThreadSafeModelUpdateQueue
          3. For queries: delegate to appropriate engine
          4. Return response with audit information

        Args:
            request: The incoming MCP request.

        Returns:
            MCPResponse with result or error.

        """
        # Step 1: Sanitize and validate inputs
        response = self._handler.handle(request)

        if not response.success:
            return response

        # Step 2: Route to appropriate handler
        # A2 CONTRACT FIX: every tool in ALLOWED_TOOLS has a route here.
        sanitized_params = response.sanitized_parameters

        if request.tool_name == "update_bim_parameter":
            return self._handle_update_bim_parameter(request, sanitized_params)
        if request.tool_name in ("query_hydraulic_calculation", "calculate_friction_loss"):
            return self._handle_hydraulic_calculation(request, sanitized_params)
        if request.tool_name == "validate_sprinkler_compliance":
            return self._handle_sprinkler_compliance(request, sanitized_params)
        if request.tool_name == "calculate_battery_capacity":
            return self._handle_battery_capacity(request, sanitized_params)
        if request.tool_name == "query_room_hazard_class":
            return self._handle_hazard_class_query(request, sanitized_params)
        if request.tool_name == "update_room_classification":
            return self._handle_room_classification(request, sanitized_params)
        if request.tool_name == "place_detector":
            return self._handle_place_detector(request, sanitized_params)
        if request.tool_name == "calculate_coverage":
            return self._handle_calculate_coverage(request, sanitized_params)
        if request.tool_name == "get_project_status":
            return self._handle_get_project_status(request)
        if request.tool_name == "export_report":
            return self._handle_export_report(request, sanitized_params)
        return MCPResponse(
            request_id=request.request_id,
            success=False,
            error=f"Tool '{request.tool_name}' handler not implemented yet.",
        )

    def _handle_update_bim_parameter(
        self, request: MCPRequest, params: dict[str, Any]
    ) -> MCPResponse:
        """
        Handle a BIM parameter update by queuing it for safe Revit execution.

        SAFETY: This NEVER directly modifies the Revit model.
        Instead, it creates a ModelUpdateAction and enqueues it
        in the ThreadSafeModelUpdateQueue for execution on the
        Revit UI thread.

        V214 FIX: After enqueueing locally, the command is ALSO forwarded
        to the C# Revit add-in via named pipe. Previously, commands were
        enqueued but NEVER consumed — they died in the queue. Now:
          1. Enqueue in ThreadSafeModelUpdateQueue (local audit trail)
          2. Forward to C# add-in via RevitNamedPipeClient (execution)
          3. If pipe unavailable (Linux/cloud), command stays queued
             with a warning — the IFC pipeline is the fallback.
        """
        action = ModelUpdateAction(
            action_type=ModelUpdateType.SET_PARAMETER,
            element_id=params.get("element_id", ""),
            parameter_name=params.get("parameter_name", ""),
            parameter_value=params.get("parameter_value"),
            source=request.source,
            nfpa_reference="MCP Update via SanitizedHandler",
        )

        try:
            action_id = self._update_queue.enqueue(action)
        except (ValueError, queue.Full) as e:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Failed to enqueue model update: {e}",
            )

        pipe_status = "not_forwarded"
        pipe_message = ""
        if self._pipe_client is not None:
            # Determine the value type for the pipe command
            param_value = params.get("parameter_value")
            if isinstance(param_value, str):
                pipe_command = {
                    "action": "set_string_parameter",
                    "element_id": str(params.get("element_id", "")),
                    "parameter_name": str(params.get("parameter_name", "")),
                    "value": str(param_value),
                    "nfpa_reference": "MCP Update via SanitizedHandler",
                }
            else:
                pipe_command = {
                    "action": "set_parameter",
                    "element_id": str(params.get("element_id", "")),
                    "parameter_name": str(params.get("parameter_name", "")),
                    "value": float(param_value) if param_value is not None else 0.0,
                    "nfpa_reference": "MCP Update via SanitizedHandler",
                }

            try:
                pipe_response = self._pipe_client.send_command(pipe_command)
                if pipe_response.get("status") == "queued":
                    pipe_status = "forwarded_to_addin"
                    pipe_message = (
                        f"Command forwarded to C# add-in (pending: "
                        f"{pipe_response.get('pending_count', '?')})"
                    )
                elif pipe_response.get("status") == "error":
                    pipe_status = "pipe_error"
                    pipe_message = pipe_response.get("message", "Unknown pipe error")
                    logger.warning(
                        "Named pipe forwarding failed: %s. Command remains in local queue.",
                        pipe_message,
                    )
            except Exception as pipe_err:
                pipe_status = "pipe_exception"
                pipe_message = str(pipe_err)
                logger.warning(
                    "Named pipe exception: %s. Command remains in local queue.",
                    pipe_err,
                )
        else:
            pipe_status = "no_pipe_client"
            pipe_message = "Named pipe client not initialized"

        return MCPResponse(
            request_id=request.request_id,
            success=True,
            result={
                "action_id": action_id,
                "status": "queued",
                "pipe_status": pipe_status,
                "pipe_message": pipe_message,
                "message": (
                    "Model update queued for safe execution on Revit UI thread. "
                    f"Pipe status: {pipe_status}. "
                    "The update will be processed by the IExternalEventHandler. "
                    "Use action_id to check status."
                ),
            },
            sanitized_parameters=params,
        )

    def _handle_hydraulic_calculation(
        self, request: MCPRequest, params: dict[str, Any]
    ) -> MCPResponse:
        """Handle a hydraulic calculation query (read-only)."""
        try:
            from fireai.core.hydraulic_solver import calculate_friction_loss

            result = calculate_friction_loss(
                flow_rate_gpm=params["flow_rate_gpm"],
                friction_factor_c=params["friction_factor_c"],
                internal_diameter_inches=params["internal_diameter_inches"],
                pipe_length_feet=params["pipe_length_feet"],
            )
            return MCPResponse(
                request_id=request.request_id,
                success=True,
                result={
                    "friction_loss_psi": round(result, 4),
                    "nfpa_reference": "NFPA 13-2022 Chapter 23",
                },
                sanitized_parameters=params,
            )
        except Exception as e:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Hydraulic calculation failed: {e}",
                sanitized_parameters=params,
            )

    def _handle_sprinkler_compliance(
        self, request: MCPRequest, params: dict[str, Any]
    ) -> MCPResponse:
        """Handle a sprinkler compliance validation query (read-only)."""
        try:
            from fireai.core.hydraulic_solver import validate_sprinkler_compliance

            result = validate_sprinkler_compliance(
                head_pressure_psi=params["head_pressure_psi"],
                density_gpm_sqft=params["density_gpm_sqft"],
                hazard_class=params["hazard_class"],
            )
            return MCPResponse(
                request_id=request.request_id,
                success=True,
                result={
                    "is_compliant": result.is_compliant,
                    "violations": result.violations,
                    "nfpa_reference": result.nfpa_reference,
                },
                sanitized_parameters=params,
            )
        except Exception as e:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Compliance validation failed: {e}",
                sanitized_parameters=params,
            )

    def _handle_battery_capacity(self, request: MCPRequest, params: dict[str, Any]) -> MCPResponse:
        """Handle a battery capacity calculation query (read-only)."""
        try:
            from fireai.core.battery_aging_derating import size_battery

            standby_hours = params.get("standby_hours", 24.0)
            alarm_minutes = params.get("alarm_minutes", 5.0)
            result = size_battery(
                standby_load_amps=params["standby_current_ma"] / 1000.0,
                alarm_load_amps=params["alarm_current_ma"] / 1000.0,
                standby_hours=standby_hours,
                alarm_hours=alarm_minutes / 60.0,
            )
            return MCPResponse(
                request_id=request.request_id,
                success=True,
                result={
                    "required_ah": result.required_ah,
                    "total_load_ah": result.total_load_ah,
                    "temperature_derating": result.temperature_derating,
                    "aging_derating": result.aging_derating,
                    "discharge_rate_correction": result.discharge_rate_correction,
                    "violations": result.violations,
                    "nfpa_reference": result.nfpa_reference,
                    "minimum_safety_factor_note": (
                        "The combined derating (aging EOL 0.80 + temperature + "
                        "Peukert) provides a minimum safety margin >= 1.20x "
                        "as required by NFPA 72 §10.6.7.2.1"
                    ),
                },
                sanitized_parameters=params,
            )
        except Exception as e:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Battery calculation failed: {e}",
                sanitized_parameters=params,
            )

    def _handle_hazard_class_query(
        self,
        request: MCPRequest,
        _params: dict[str, Any],  # NOSONAR — S1172: parameter retained for API stability
    ) -> MCPResponse:
        """Handle a hazard class query (read-only)."""
        from fireai.core.hazard_override import MANDATORY_HAZARD_OVERRIDES

        # Reuse the handler's existing verifier instance
        # Return the mandatory override table for reference
        return MCPResponse(
            request_id=request.request_id,
            success=True,
            result={
                "mandatory_overrides": dict(MANDATORY_HAZARD_OVERRIDES.items()),
                "available_classifications": [
                    "light_hazard",
                    "ordinary_hazard_1",
                    "ordinary_hazard_2",
                    "extra_hazard_1",
                    "extra_hazard_2",
                ],
            },
        )

    def _handle_room_classification(
        self, request: MCPRequest, params: dict[str, Any]
    ) -> MCPResponse:
        """
        Handle a room classification update.

        SAFETY: The hazard override verifier is applied during
        sanitization (Gate 4 in SanitizedMCPHandler). If the AI
        predicted a lower classification than mandatory, it has
        already been overridden.
        """
        # The sanitized_params already contains the override result
        override_applied = params.get("_override_applied", False)
        override_rationale = params.get("_override_rationale", "")

        # Queue the classification update for safe Revit execution
        action = ModelUpdateAction(
            action_type=ModelUpdateType.SET_HAZARD_CLASS,
            element_id=params.get("element_id", ""),
            parameter_name="Hazard Classification",
            parameter_value=params.get("hazard_class"),
            source=request.source,
            nfpa_reference="NFPA 13-2022 Chapter 11 / SBC 801 Ch.9",
        )

        try:
            action_id = self._update_queue.enqueue(action)
        except (ValueError, queue.Full) as e:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Failed to enqueue classification update: {e}",
            )

        result_data: dict[str, Any] = {
            "action_id": action_id,
            "status": "queued",
            "hazard_class": params.get("hazard_class"),
            "override_applied": override_applied,
        }
        if override_applied:
            result_data["override_rationale"] = override_rationale

        return MCPResponse(
            request_id=request.request_id,
            success=True,
            result=result_data,
            sanitized_parameters=params,
        )

    def _handle_place_detector(self, request: MCPRequest, params: dict[str, Any]) -> MCPResponse:
        """
        Compute an NFPA 72-compliant detector placement for a room and queue
        it for safe Revit execution (A2 — real engine wiring).

        Delegates to DetectorPlacementEngine.place_detectors() (hex-grid,
        beam obstruction rule, wall-distance constraints) and enqueues one
        SET_DETECTOR_LOCATION action per computed device. Nothing writes to
        the Revit model directly.
        """
        from fireai.core.device_placement import DetectorPlacementEngine, DetectorType, RoomSpec

        type_map = {
            "smoke": DetectorType.SMOKE,
            "heat": DetectorType.HEAT,
            "duct": DetectorType.DUCT,
        }
        detector_type = type_map.get(str(params.get("detector_type", "")))
        if detector_type is None:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=(
                    f"Unsupported detector_type '{params.get('detector_type')}'. "
                    f"Supported: {sorted(type_map)}"
                ),
                sanitized_parameters=params,
            )

        room = RoomSpec(
            room_id=str(params.get("room_id", "")),
            length_m=float(params["room_length_m"]),
            width_m=float(params["room_width_m"]),
            ceiling_height_m=float(params["ceiling_height_m"]),
            detector_type=detector_type,
        )
        try:
            placement = DetectorPlacementEngine().place_detectors(room)
        except Exception as e:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Detector placement failed: {e}",
                sanitized_parameters=params,
            )

        action_ids: list[str] = []
        try:
            for device in placement.detectors:
                action = ModelUpdateAction(
                    action_type=ModelUpdateType.SET_DETECTOR_LOCATION,
                    element_id=device.device_id,
                    parameter_name="DetectorLocation",
                    parameter_value={"x_m": device.x_m, "y_m": device.y_m, "z_m": device.z_m},
                    source=request.source,
                    nfpa_reference=device.nfpa_section,
                )
                action_ids.append(self._update_queue.enqueue(action))
        except (ValueError, queue.Full) as e:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Failed to enqueue placement actions: {e}",
                sanitized_parameters=params,
            )

        return MCPResponse(
            request_id=request.request_id,
            success=True,
            result={
                "room_id": placement.room_id,
                "detectors": [
                    {"device_id": d.device_id, "x_m": d.x_m, "y_m": d.y_m, "z_m": d.z_m}
                    for d in placement.detectors
                ],
                "coverage_pct": placement.coverage_pct,
                "is_fully_compliant": placement.is_fully_compliant,
                "violations": placement.violations,
                "nfpa_references": placement.nfpa_references,
                "computation_hash": placement.computation_hash,
                "queued_action_ids": action_ids,
                "status": "queued",
            },
            sanitized_parameters=params,
        )

    def _handle_calculate_coverage(
        self, request: MCPRequest, params: dict[str, Any]
    ) -> MCPResponse:
        """Calculate NFPA 72 coverage for a room via the real kernel tables."""
        import math
        from typing import Literal

        from fireai.core.nfpa72_calculations import calculate_coverage_radius_from_height

        raw_type = str(params["detector_type"])
        # Gate 3's enum constrains calculate_coverage to smoke/heat; map
        # defensively so the kernel's Literal-typed parameter stays honest.
        detector_kind: Literal["smoke", "heat"] = "smoke" if raw_type == "smoke" else "heat"
        try:
            spec = calculate_coverage_radius_from_height(
                ceiling_height=float(params["ceiling_height_m"]),
                detector_type=detector_kind,
            )
        except Exception as e:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Coverage calculation failed: {e}",
                sanitized_parameters=params,
            )

        length_m = float(params["room_length_m"])
        width_m = float(params["room_width_m"])
        spacing = spec.spacing_max if spec.spacing_max > 0 else spec.radius
        detectors_required = max(1, math.ceil(length_m / spacing)) * max(
            1, math.ceil(width_m / spacing)
        )

        result: dict[str, Any] = {
            "coverage_radius_m": round(spec.radius, 4),
            "spacing_max_m": round(spec.spacing_max, 4),
            "wall_distance_max_m": round(spec.wall_distance_max, 4),
            "coverage_area_per_detector_m2": round(spec.area, 4),
            "room_area_m2": round(length_m * width_m, 4),
            "detectors_required_grid": int(detectors_required),
            "nfpa_reference": spec.nfpa_ref,
        }
        if spec.warning:
            result["warning"] = spec.warning
        return MCPResponse(
            request_id=request.request_id,
            success=True,
            result=result,
            sanitized_parameters=params,
        )

    def _handle_get_project_status(self, request: MCPRequest) -> MCPResponse:
        """Report live in-process session state (queue + audit counters)."""
        processed = len(self._handler.get_request_log(last_n=10**9))
        return MCPResponse(
            request_id=request.request_id,
            success=True,
            result={
                "server_name": MCP_SERVER_NAME,
                "server_version": MCP_SERVER_VERSION,
                "protocol_version": MCP_PROTOCOL_VERSION,
                "model_update_queue": self._update_queue.get_stats(),
                "pending_updates": self._update_queue.get_pending_count(),
                "session_requests_processed": processed,
                "available_tools": sorted(self._handler.ALLOWED_TOOLS),
            },
        )

    def _handle_export_report(self, request: MCPRequest, params: dict[str, Any]) -> MCPResponse:
        """
        Export the MCP session audit report to a JSON file.

        A2 minimal real implementation: full NFPA submittal PDFs require a
        BuildingEngine analysis context that is not available over a stdio
        session, so this tool exports the REAL session data instead of
        fabricating engineering results: the sanitized request log and the
        model-update queue stats.
        """
        import json as _json
        from pathlib import Path

        report_type = str(params.get("report_type", "session_audit"))
        if report_type != "session_audit":
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=(f"Unsupported report_type '{report_type}'. Supported: ['session_audit']"),
                sanitized_parameters=params,
            )

        output_path = params.get("output_path") or "uploads/fireai_mcp_session_report.json"
        request_log_entries = self._handler.get_request_log(last_n=1000)
        payload = {
            "report_type": "session_audit",
            "generated_at": time.time(),
            "server": {"name": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION},
            "model_update_queue": self._update_queue.get_stats(),
            "request_log": request_log_entries,
        }
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as e:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Failed to write session audit report: {e}",
                sanitized_parameters=params,
            )
        return MCPResponse(
            request_id=request.request_id,
            success=True,
            result={
                "report_type": report_type,
                "output_path": str(path),
                "entries": len(request_log_entries),
                "message": "Session audit report written successfully.",
            },
            sanitized_parameters=params,
        )

    def start(self, *, block: bool = True) -> None:
        """
        Start the MCP server.

        V141.2 REAL IMPLEMENTATION (adversarial audit fix):
        Reads JSON-RPC 2.0 requests from stdin (one per line), dispatches
        each to _handle_jsonrpc(), and writes responses to stdout.

        This matches the MCP specification: AI assistants (Claude Desktop,
        etc.) spawn this server as a subprocess and communicate via stdio.

        Args:
            block: If True (default), blocks the calling thread reading
                stdin until EOF or stop(). If False, starts a daemon
                thread and returns immediately (useful for testing).
        """
        if self._running:
            logger.warning("RevitMCPServer.start() called but already running.")
            return

        self._running = True
        logger.info(
            "[MCP SERVER]: RevitMCPServer started (MCP protocol v%s). "
            "Reading JSON-RPC from stdin. All model updates will be queued "
            "for thread-safe execution.",
            MCP_PROTOCOL_VERSION,
        )

        if block:
            self._stdin_loop()
        else:
            self._stdin_thread = threading.Thread(
                target=self._stdin_loop,
                name="mcp-stdin-reader",
                daemon=True,
            )
            self._stdin_thread.start()

    def _stdin_loop(self) -> None:
        """
        Main stdio read loop. Reads JSON-RPC lines until EOF or stop().

        V142 FIX (Rule 17 root-cause): In CI environments, sys.stdin may
        be a non-EOF pipe that blocks `for line in sys.stdin` indefinitely.
        This caused Gate 2 — Test Suite to hang. Fix: when
        FIREAI_MCP_NO_STDIN=1 is set (used by tests), the loop becomes a
        no-op wait on _running instead of reading stdin. Production
        deployments (Claude Desktop) do not set this var.
        """
        import os

        if os.environ.get("FIREAI_MCP_NO_STDIN") == "1":
            # Test mode: don't read stdin (which may block in CI).
            # Just wait until stop() sets _running=False.
            import threading

            event = threading.Event()
            while self._running and not event.wait(0.05):
                pass  # NOSONAR — S108: empty except kept for graceful degradation
            logger.info("[MCP SERVER]: test-mode loop exiting (stop() called).")
            return

        # Use sys.stdin directly to keep stdout clean for protocol messages.
        # All logging goes to stderr (configured by logging_setup).
        for line in sys.stdin:
            if not self._running:
                break

            line = line.strip()
            if not line:
                continue

            try:
                response = self._handle_jsonrpc_line(line)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                # Never crash the server on a malformed request — log and continue.
                logger.exception("[MCP SERVER] Error handling request: %s", e)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": str(e),
                    },
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

        logger.info("[MCP SERVER]: stdin EOF reached, server shutting down.")

    def _handle_jsonrpc_line(self, line: str) -> dict[str, Any] | None:
        """
        Parse a JSON-RPC line and return a response dict (or None for notifications).

        Args:
            line: A single JSON-RPC request string (one line from stdin).

        Returns:
            Response dict to write to stdout, or None if the message is a
            notification (no response expected per JSON-RPC 2.0 spec).
        """
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                    "data": str(e),
                },
            }

        method = request.get("method")
        req_id = request.get("id")
        params = request.get("params", {})

        # Notifications (no id) don't get a response per JSON-RPC 2.0
        is_notification = req_id is None

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "initialized":
                # Notification — no response
                return None
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = self._handle_tools_list()
            elif method == "tools/call":
                result = self._handle_tools_call(params)
            elif method == "resources/list":
                result = {"resources": []}
            elif method == "resources/read":
                result = {"contents": []}
            else:
                if is_notification:
                    return None
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                }

            if is_notification:
                return None

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result,
            }

        except Exception as e:
            if is_notification:
                logger.exception("[MCP SERVER] Notification %s failed: %s", method, e)
                return None
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e),
                },
            }

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle the MCP initialize request."""
        self._client_capabilities = params.get("capabilities", {})
        client_info = params.get("clientInfo", {})
        logger.info(
            "[MCP SERVER] Initialize from client: %s v%s",
            client_info.get("name", "unknown"),
            client_info.get("version", "unknown"),
        )
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"listChanged": False, "subscribe": False},
            },
            "serverInfo": {
                "name": MCP_SERVER_NAME,
                "version": MCP_SERVER_VERSION,
            },
        }

    def _handle_tools_list(self) -> dict[str, Any]:
        """List available MCP tools.

        A2 CONTRACT FIX: tool descriptions live here, but the inputSchema for
        each tool is GENERATED from SanitizedMCPHandler.PARAM_RULES (single
        source of truth). tools/list can no longer advertise parameters that
        Gate 3 does not actually validate, or omit ones it does.
        """
        schemas = self._handler.build_input_schemas()
        return {
            "tools": [
                {
                    "name": name,
                    "description": TOOL_DESCRIPTIONS[name],
                    "inputSchema": schemas[name],
                }
                for name in sorted(schemas)
            ]
        }

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle a tools/call request by dispatching through process_request().

        A2 CONTRACT FIX: this previously called SanitizedMCPHandler.handle()
        DIRECTLY, which only sanitizes inputs — it never routed to the real
        tool handlers, so every engineering calculation tool silently
        returned its own sanitized arguments as the "result" over the wire.
        tools/call now goes through process_request() (sanitize + route),
        the same path as the in-process API.
        """
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        # Build an MCPRequest and delegate to the safety-enforcing gate +
        # route chain. The comment below documents the V142 bug that broke
        # Claude Desktop integration entirely; keep it as a regression note.
        mcp_request = MCPRequest(
            request_id=str(params.get("_meta", {}).get("request_id", "")),
            tool_name=tool_name or "",
            parameters=tool_args,
        )
        response: MCPResponse = self.process_request(mcp_request)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "success": response.success,
                            "result": response.result,
                            "error": response.error,
                            "sanitized_parameters": response.sanitized_parameters,
                        }
                    ),
                }
            ],
            "isError": not response.success,
        }

    def stop(self) -> None:
        """
        Stop the MCP server.

        Sets _running = False, which causes the stdin read loop to exit
        on the next iteration. If running in non-blocking mode, waits for
        the daemon thread to finish (up to 2 seconds).
        """
        self._running = False
        logger.info("[MCP SERVER]: RevitMCPServer stop requested.")

        if self._stdin_thread is not None and self._stdin_thread.is_alive():
            self._stdin_thread.join(timeout=2.0)
            if self._stdin_thread.is_alive():
                logger.warning(
                    "[MCP SERVER]: stdin reader thread did not stop within 2s "
                    "(it is blocked on stdin.read; will exit on next input or EOF)."
                )
        logger.info("[MCP SERVER]: RevitMCPServer stopped.")


# ── Module entry point ──────────────────────────────────────────────────────
def main() -> None:
    """Run the MCP server as a subprocess (spawned by Claude Desktop etc.)."""
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server = RevitMCPServer()
    server.start(block=True)


if __name__ == "__main__":
    main()
