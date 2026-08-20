r"""
named_pipe_client.py — Python side of the named pipe bridge to the C# Revit add-in.

V214 FIX: Previously the Python MCP server (revit_mcp_server.py) enqueued
model update actions in a local ThreadSafeModelUpdateQueue, but no C# add-in
consumed from it — so writes were silently dropped (V133 safety redesign
defeated). Now this client sends commands over a named pipe to the C#
FireAIRevitAddin which executes them on the Revit UI thread.

PHASE 4.0 HARDENING:
  - Added 3-state Circuit Breaker (CLOSED -> OPEN -> HALF-OPEN).
  - Capped heartbeat connection timeouts at 2.0s.
  - Tripped after 3 consecutive failures to OPEN state.
  - Returns structured fallback response (BRIDGE_PROCESS_UNRESPONSIVE) with zero state mutation.

PIPE NAME: \\\\.\\pipe\\FireAIRevitPipe (matches C# NamedPipeServer.cs)

PROTOCOL:
  Request (newline-delimited JSON):
    {"action": "set_parameter", "element_id": "12345",
     "parameter_name": "Diameter", "value": 25.0,
     "nfpa_reference": "NFPA 72 §17.7.3.2.3"}

  Response (newline-delimited JSON):
    {"status": "queued", "pending_count": 3, "total_received": 42, "total_queued": 40}
    OR
    {"status": "error", "message": "Invalid action type"}

USAGE:
  from fireai.mcp_server.named_pipe_client import RevitNamedPipeClient

  client = RevitNamedPipeClient()
  if client.is_available():
      response = client.send_command({
          "action": "set_parameter",
          "element_id": "12345",
          "parameter_name": "Diameter",
          "value": 25.0,
          "nfpa_reference": "NFPA 72 §17.7.3.2.3",
      })
      if response.get("status") == "queued":
          print(f"Action queued (pending: {response.get('pending_count')})")
      else:
          print(f"Error: {response.get('message')}")
  else:
      print("C# add-in not running — start Revit with the FireAI add-in installed")

PLATFORM:
  Windows only (named pipes are a Windows feature). On Linux/Mac, this
  client returns is_available()=False and all send_command calls return
  {"status": "error", "message": "Named pipes not available on this platform"}.
"""

from __future__ import annotations

import json
import logging
import platform
import threading
import time
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

_PIPE_NAME = r"\\.\pipe\FireAIRevitPipe"
_DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 2.0
_DEFAULT_RECOVERY_COOLDOWN_SECONDS = 5.0
_DEFAULT_FAILURE_THRESHOLD = 3


class CircuitState(str, Enum):
    """Circuit Breaker States."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class NamedPipeCircuitBreaker:
    """Explicit 3-state Circuit Breaker for native CAD/BIM Named Pipe bridges."""

    def __init__(
        self,
        failure_threshold: int = _DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: float = _DEFAULT_RECOVERY_COOLDOWN_SECONDS,
        heartbeat_timeout: float = _DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    ) -> None:
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_timeout = max(0.001, recovery_timeout)
        self.heartbeat_timeout = max(0.001, heartbeat_timeout)
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float = 0.0
        self._lock = threading.RLock()

    def can_execute(self) -> bool:
        """Check if request is permitted to attempt native pipe connection."""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            if self.state == CircuitState.OPEN:
                now = time.monotonic()
                if now - self.last_failure_time >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info("NamedPipeCircuitBreaker: Cooldown expired -> state transitioning to HALF_OPEN")
                    return True
                return False
            if self.state == CircuitState.HALF_OPEN:
                return True
            return False

    def record_success(self) -> None:
        """Record a successful native IPC communication."""
        with self._lock:
            if self.state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
                logger.info("NamedPipeCircuitBreaker: Probe successful -> circuit transitioned to CLOSED")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = 0.0

    def record_failure(self) -> None:
        """Record a connection failure or timeout."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.monotonic()
            if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    "NamedPipeCircuitBreaker: Tripped to OPEN (failures=%d/%d)",
                    self.failure_count,
                    self.failure_threshold,
                )

    def reset(self) -> None:
        """Explicitly reset circuit breaker state to CLOSED."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = 0.0


class RevitNamedPipeClient:
    r"""
    Client for the C# Revit add-in named pipe server with Circuit Breaker resilience.

    On Windows, connects to \\\\.\\pipe\\FireAIRevitPipe.
    On Linux/Mac, is_available() returns False (named pipes are Windows-only).
    """

    def __init__(
        self,
        pipe_name: str = _PIPE_NAME,
        failure_threshold: int = _DEFAULT_FAILURE_THRESHOLD,
        recovery_timeout: float = _DEFAULT_RECOVERY_COOLDOWN_SECONDS,
        heartbeat_timeout: float = _DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    ) -> None:
        self._pipe_name = pipe_name
        self._is_windows = platform.system() == "Windows"
        self.circuit_breaker = NamedPipeCircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            heartbeat_timeout=heartbeat_timeout,
        )
        if not self._is_windows:
            logger.info(
                "RevitNamedPipeClient: named pipes are Windows-only. "
                "On Linux/Mac, all send_command calls will return an error. "
                "Use the IFC pipeline (fireai.bridges.ifc_pipeline) for "
                "cross-platform Revit integration."
            )

    def is_available(self) -> bool:
        """
        Check if the named pipe is available (Windows + pipe server running).

        Returns:
            True if on Windows AND the pipe exists AND the C# add-in is
            listening and circuit breaker allows execution. False otherwise.
        """
        if not self._is_windows:
            return False

        if not self.circuit_breaker.can_execute():
            return False

        try:
            # Try to connect with a short timeout to check availability
            import pywintypes
            import win32file
            import win32pipe  # noqa: F401 — Windows-only

            try:
                handle = win32file.CreateFile(
                    self._pipe_name,
                    win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                    0,
                    None,
                    win32file.OPEN_EXISTING,
                    0,
                    None,
                )
                win32file.CloseHandle(handle)
                self.circuit_breaker.record_success()
                return True
            except pywintypes.error:
                # Pipe not found or not available
                self.circuit_breaker.record_failure()
                return False
        except ImportError:
            logger.warning(
                "pywin32 not installed — cannot check named pipe availability. "
                "Install with: pip install pywin32"
            )
            return False

    def _read_pipe_response(self, win32file: Any, handle: Any) -> bytes:
        """Read newline-delimited bytes from pipe handle."""
        response_bytes = b""
        while True:
            try:
                result, data = win32file.ReadFile(handle, 4096)
                if data:
                    response_bytes += data
                    if b"\n" in data:
                        break
                if result != 0:
                    break
            except Exception:
                break
        return response_bytes

    def _parse_pipe_response(self, response_str: str) -> dict[str, Any]:
        """Parse pipe response string into JSON or error envelope."""
        if not response_str:
            self.circuit_breaker.record_failure()
            return {
                "status": "error",
                "error_code": "EMPTY_RESPONSE",
                "message": "Empty response from C# add-in",
                "circuit_state": self.circuit_breaker.state.value,
                "consecutive_failures": self.circuit_breaker.failure_count,
            }

        try:
            parsed = json.loads(response_str)
            self.circuit_breaker.record_success()
            return parsed
        except json.JSONDecodeError as je:
            self.circuit_breaker.record_failure()
            return {
                "status": "error",
                "error_code": "INVALID_JSON_RESPONSE",
                "message": f"Invalid JSON response: {je}",
                "raw_response": response_str[:200],
                "circuit_state": self.circuit_breaker.state.value,
                "consecutive_failures": self.circuit_breaker.failure_count,
            }

    def send_command(self, command: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:  # NOSONAR — S3776: Multi-stage named pipe IPC lifecycle
        """
        Send a JSON command to the C# Revit add-in via named pipe with circuit breaker protection.

        Args:
            command: Dict with at least an "action" key. Supported actions:
                - set_parameter: {action, element_id, parameter_name, value, nfpa_reference?}
                - set_string_parameter: {action, element_id, parameter_name, value, nfpa_reference?}
                - create_wall: {action, start_point: [x,y,z], end_point: [x,y,z], level?}
            timeout: Optional custom timeout in seconds (capped at 2.0s per heartbeat if not specified).

        Returns:
            Dict with "status" key:
                - {"status": "queued", "pending_count": N, ...} on success
                - {"status": "error", "error_code": "BRIDGE_PROCESS_UNRESPONSIVE", ...} on circuit open
                - {"status": "error", "message": "..."} on failure
        """
        # Circuit breaker gate — fast-fail immediately if circuit is OPEN
        if not self.circuit_breaker.can_execute():
            return {
                "status": "error",
                "error_code": "BRIDGE_PROCESS_UNRESPONSIVE",
                "message": "Native bridge process is unresponsive (circuit breaker OPEN)",
                "circuit_state": self.circuit_breaker.state.value,
                "consecutive_failures": self.circuit_breaker.failure_count,
            }

        if not self._is_windows:
            return {
                "status": "error",
                "error_code": "PLATFORM_NOT_SUPPORTED",
                "message": (
                    "Named pipes not available on this platform. "
                    "Use the IFC pipeline (fireai.bridges.ifc_pipeline) for "
                    "cross-platform Revit integration."
                ),
            }

        try:
            import pywintypes
            import win32file
            import win32pipe  # noqa: F401 — Windows-only
        except ImportError:
            return {
                "status": "error",
                "message": "pywin32 not installed. Install with: pip install pywin32",
            }

        # Serialize command as newline-delimited JSON
        message_bytes = (json.dumps(command) + "\n").encode("utf-8")

        try:
            # Connect to the pipe with 2.0s heartbeat cap
            handle = win32file.CreateFile(
                self._pipe_name,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
        except pywintypes.error as e:
            self.circuit_breaker.record_failure()
            is_open = self.circuit_breaker.state == CircuitState.OPEN
            return {
                "status": "error",
                "error_code": "BRIDGE_PROCESS_UNRESPONSIVE" if is_open else "PIPE_CONNECTION_FAILED",
                "message": (
                    f"Cannot connect to named pipe '{self._pipe_name}'. "
                    f"Is the FireAI Revit add-in running? Error: {e}"
                ),
                "circuit_state": self.circuit_breaker.state.value,
                "consecutive_failures": self.circuit_breaker.failure_count,
            }

        try:
            win32file.WriteFile(handle, message_bytes)
            response_bytes = self._read_pipe_response(win32file, handle)
            response_str = response_bytes.decode("utf-8", errors="ignore").strip()
            return self._parse_pipe_response(response_str)
        except Exception as ex:
            self.circuit_breaker.record_failure()
            return {
                "status": "error",
                "error_code": "PIPE_IO_ERROR",
                "message": f"Error during pipe read/write: {ex}",
                "circuit_state": self.circuit_breaker.state.value,
                "consecutive_failures": self.circuit_breaker.failure_count,
            }
        finally:
            try:
                win32file.CloseHandle(handle)
            except Exception:
                pass

    def send_set_parameter(
        self,
        element_id: str,
        parameter_name: str,
        value: float,
        nfpa_reference: str = "",
    ) -> dict[str, Any]:
        """Convenience method for set_parameter action."""
        return self.send_command(
            {
                "action": "set_parameter",
                "element_id": str(element_id),
                "parameter_name": parameter_name,
                "value": float(value),
                "nfpa_reference": nfpa_reference,
            }
        )

    def send_set_string_parameter(
        self,
        element_id: str,
        parameter_name: str,
        value: str,
        nfpa_reference: str = "",
    ) -> dict[str, Any]:
        """Convenience method for set_string_parameter action."""
        return self.send_command(
            {
                "action": "set_string_parameter",
                "element_id": str(element_id),
                "parameter_name": parameter_name,
                "value": str(value),
                "nfpa_reference": nfpa_reference,
            }
        )

    def send_create_wall(
        self,
        start_point: list[float],
        end_point: list[float],
        level: str = "Level 1",
    ) -> dict[str, Any]:
        """Convenience method for create_wall action. Coordinates in mm."""
        return self.send_command(
            {
                "action": "create_wall",
                "start_point": [float(c) for c in start_point],
                "end_point": [float(c) for c in end_point],
                "level": level,
            }
        )

    def get_stats(self) -> dict[str, Any]:
        """Get connection status, circuit breaker state, and statistics."""
        return {
            "pipe_name": self._pipe_name,
            "platform": platform.system(),
            "is_windows": self._is_windows,
            "is_available": self.is_available(),
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "consecutive_failures": self.circuit_breaker.failure_count,
            "circuit_breaker_enabled": True,
        }
