"""backend/core/command_bus.py — Production Deterministic CommandBus with OCC & Audit.

Frozen Phase 1 Architecture:
- Contract 2: Semantic DomainCommand with server-originated AuthenticatedPrincipal.
- Contract 5: Traceable DomainEvent with audit hash and lineage.
- Contract 10: Validation, Optimistic Concurrency Control (OCC), Idempotency, Atomicity, and Dry-run.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime, timezone

    UTC = timezone.utc
from typing import Any

from backend.core.capability_registry import (
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.state_store import CommandStateStore, default_state_store

logger = logging.getLogger(__name__)

# Sensitive keywords strictly forbidden from entering domain command payloads
FORBIDDEN_PAYLOAD_KEYS = {
    "password",
    "secret",
    "token",
    "bearer",
    "api_key",
    "session_cookie",
    "credentials",
    "auth_header",
}


@dataclass
class AuthenticatedPrincipal:
    """Server-side authenticated principal derived from transport boundary."""

    user_id: str
    email: str
    role: str  # e.g., "engineer", "admin", "viewer"
    scopes: list[str] = field(default_factory=list)
    is_authenticated: bool = True

    def has_scope(self, scope: str) -> bool:
        return "*" in self.scopes or scope in self.scopes


@dataclass
class DomainCommand:
    """Frozen DomainCommand structure for deterministic mutation and planning."""

    commandId: str  # NOSONAR — frozen API contract (camelCase JSON wire format)
    correlationId: str  # NOSONAR
    capabilityId: str  # NOSONAR
    projectId: str  # NOSONAR
    expectedRevision: int  # NOSONAR
    timestamp: str
    principal: AuthenticatedPrincipal
    riskClass: str = "MEDIUM"  # NOSONAR — "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    isDryRun: bool = False  # NOSONAR
    payload: dict[str, Any] = field(default_factory=dict)
    causationId: str | None = None  # NOSONAR

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class DomainEvent:
    """Traceable domain event produced upon successful command execution."""

    eventId: str  # NOSONAR — frozen API contract (camelCase JSON wire format)
    commandId: str  # NOSONAR
    correlationId: str  # NOSONAR
    projectId: str  # NOSONAR
    revision: int
    actor: str
    eventType: str  # NOSONAR
    timestamp: str
    verificationResult: dict[str, Any]  # NOSONAR
    auditReference: str  # NOSONAR
    payload: dict[str, Any]
    causationId: str | None = None  # NOSONAR

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommandResult:
    """Result of command dispatch via CommandBus."""

    success: bool
    commandId: str  # NOSONAR — frozen API contract (camelCase JSON wire format)
    projectId: str  # NOSONAR
    revision: int
    isDryRun: bool  # NOSONAR
    resultData: dict[str, Any] = field(default_factory=dict)  # NOSONAR
    event: DomainEvent | None = None
    errorCode: str | None = None  # NOSONAR
    errorMessage: str | None = None  # NOSONAR

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "commandId": self.commandId,
            "projectId": self.projectId,
            "revision": self.revision,
            "isDryRun": self.isDryRun,
            "resultData": self.resultData,
            "event": self.event.to_dict() if self.event else None,
            "errorCode": self.errorCode,
            "errorMessage": self.errorMessage,
        }


class ConcurrencyConflictError(Exception):
    """Raised when command expectedRevision does not match current canonical project revision."""


class UnauthorizedCommandError(Exception):
    """Raised when principal lacks required permissions or authentication."""


class InvalidPayloadError(Exception):
    """Raised when payload contains forbidden security tokens or schema violations."""


class CommandBus:
    """Production CommandBus orchestrating validation, OCC, deterministic execution, and audit."""

    def __init__(
        self,
        capability_registry: CapabilityRegistry | None = None,
        state_store: CommandStateStore | None = None,
    ) -> None:
        self.registry = capability_registry or default_capability_registry
        self.state_store = state_store or default_state_store

    def get_project_revision(self, project_id: str) -> int:
        """Get canonical revision of a project from persistent storage."""
        return self.state_store.get_project_revision(project_id)

    def set_project_revision(self, project_id: str, revision: int) -> None:
        """Update canonical project revision in persistent storage."""
        self.state_store.set_project_revision(project_id, revision)

    def get_canonical_state(self, project_id: str) -> dict[str, Any]:
        """Retrieve canonical engineering state for project from persistent storage."""
        return self.state_store.get_canonical_state(project_id)

    def save_canonical_state(
        self, project_id: str, state: dict[str, Any], revision: int
    ) -> None:
        """Save canonical engineering state to persistent storage."""
        self.state_store.save_canonical_state(project_id, state, revision)

    def execute(self, command: DomainCommand) -> CommandResult:
        """Execute or preview a domain command with strict validation and OCC enforcement."""
        # 1. Security & Authentication Checks
        if not command.principal.is_authenticated:
            return CommandResult(
                success=False,
                commandId=command.commandId,
                projectId=command.projectId,
                revision=self.get_project_revision(command.projectId),
                isDryRun=command.isDryRun,
                errorCode="UNAUTHENTICATED_ACCESS",
                errorMessage="Command rejected: Principal is not authenticated.",
            )

        # 2. Secret Leakage Prevention in Payload
        for k in command.payload:
            if any(forbidden in k.lower() for forbidden in FORBIDDEN_PAYLOAD_KEYS):
                return CommandResult(
                    success=False,
                    commandId=command.commandId,
                    projectId=command.projectId,
                    revision=self.get_project_revision(command.projectId),
                    isDryRun=command.isDryRun,
                    errorCode="FORBIDDEN_PAYLOAD_SECRET",
                    errorMessage=f"Command payload contains forbidden security key: {k}",
                )

        # 3. Capability Lookup
        cap = self.registry.get(command.capabilityId)
        if not cap:
            return CommandResult(
                success=False,
                commandId=command.commandId,
                projectId=command.projectId,
                revision=self.get_project_revision(command.projectId),
                isDryRun=command.isDryRun,
                errorCode="UNKNOWN_CAPABILITY",
                errorMessage=f"Capability '{command.capabilityId}' is not registered.",
            )

        # 4. Scope & Authorization Check
        for req_scope in cap.required_scopes:
            if not command.principal.has_scope(req_scope):
                return CommandResult(
                    success=False,
                    commandId=command.commandId,
                    projectId=command.projectId,
                    revision=self.get_project_revision(command.projectId),
                    isDryRun=command.isDryRun,
                    errorCode="UNAUTHORIZED_SCOPE",
                    errorMessage=f"Principal '{command.principal.user_id}' lacks required scope: {req_scope}",
                )

        # 5. Persistent Idempotency Check with Collision Detection
        payload_hash = hashlib.sha256(
            json.dumps(command.payload, sort_keys=True).encode()
        ).hexdigest()

        if not command.isDryRun:
            cached_result, is_collision = self.state_store.get_idempotent_command(
                command.commandId, payload_hash
            )
            if is_collision:
                current_rev = self.get_project_revision(command.projectId)
                logger.warning(
                    "Idempotency Key Reuse Conflict: commandId '%s' with different payload",
                    command.commandId,
                )
                return CommandResult(
                    success=False,
                    commandId=command.commandId,
                    projectId=command.projectId,
                    revision=current_rev,
                    isDryRun=command.isDryRun,
                    errorCode="IDEMPOTENCY_KEY_REUSE_CONFLICT",
                    errorMessage=(
                        f"Idempotency Key Reuse Conflict: commandId '{command.commandId}' "
                        f"was already executed with a different command payload."
                    ),
                )
            if cached_result is not None:
                logger.info("Idempotent command replay from persistent store: %s", command.commandId)
                return cached_result

        # 6. Optimistic Concurrency Control (OCC) Pre-Check
        current_rev = self.get_project_revision(command.projectId)
        if not command.isDryRun and command.expectedRevision != current_rev:
            return CommandResult(
                success=False,
                commandId=command.commandId,
                projectId=command.projectId,
                revision=current_rev,
                isDryRun=command.isDryRun,
                errorCode="CONCURRENCY_CONFLICT",
                errorMessage=(
                    f"Concurrency Conflict: Command expected revision {command.expectedRevision}, "
                    f"but project canonical revision is {current_rev}. The project was modified concurrently."
                ),
            )

        # 7. Deterministic Execution
        if not cap.handler:
            return CommandResult(
                success=False,
                commandId=command.commandId,
                projectId=command.projectId,
                revision=current_rev,
                isDryRun=command.isDryRun,
                errorCode="CAPABILITY_EXECUTION_ERROR",
                errorMessage=f"Capability '{command.capabilityId}' has no execution handler.",
            )

        try:
            exec_result = cap.handler(command.payload)
        except Exception as err:
            logger.exception("Error executing capability handler: %s", err)
            return CommandResult(
                success=False,
                commandId=command.commandId,
                projectId=command.projectId,
                revision=current_rev,
                isDryRun=command.isDryRun,
                errorCode="HANDLER_EXECUTION_FAILED",
                errorMessage=str(err),
            )

        # 8. Dry-Run Response (Planning/Preview Phase — No State Mutation)
        if command.isDryRun:
            return CommandResult(
                success=True,
                commandId=command.commandId,
                projectId=command.projectId,
                revision=current_rev,
                isDryRun=True,
                resultData=exec_result,
            )

        # 9. Build DomainEvent & Cryptographic Audit Reference
        new_revision = current_rev + 1
        new_devices = exec_result.get("devices", [])
        audit_payload = {
            "commandId": command.commandId,
            "capabilityId": command.capabilityId,
            "projectId": command.projectId,
            "revision": new_revision,
            "actor": command.principal.user_id,
            "device_count": len(new_devices),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        audit_ref = hashlib.sha256(
            json.dumps(audit_payload, sort_keys=True).encode()
        ).hexdigest()
        if "place_devices" in command.capabilityId:
            evt_type = "DEVICES_PLACED"
        elif "voltage_drop" in command.capabilityId:
            evt_type = "VOLTAGE_DROP_CALCULATED"
        elif "calculate_battery" in command.capabilityId or "battery" in command.capabilityId:
            evt_type = "BATTERY_CALCULATION_SOLVED"
        elif "solve_darcy_weisbach" in command.capabilityId or "hydraulics" in command.capabilityId:
            evt_type = "HYDRAULIC_CALCULATION_SOLVED"
        else:
            evt_type = "COMPLIANCE_VERIFIED"

        verification_result: dict[str, Any] = {
            "is_compliant": exec_result.get("is_compliant", True),
            "violations": exec_result.get("violations", []),
            "warnings": exec_result.get("warnings", []),
        }
        if "coverage_pct" in exec_result:
            verification_result["coverage_pct"] = exec_result["coverage_pct"]
        if "voltage_drop_pct" in exec_result:
            verification_result["voltage_drop_pct"] = exec_result["voltage_drop_pct"]
        if "recommended_awg" in exec_result:
            verification_result["recommended_awg"] = exec_result["recommended_awg"]
        if "head_loss_m" in exec_result:
            verification_result["head_loss_m"] = exec_result["head_loss_m"]
        if "flow_velocity_m_s" in exec_result:
            verification_result["flow_velocity_m_s"] = exec_result["flow_velocity_m_s"]
        if "pressure_loss_psi" in exec_result:
            verification_result["pressure_loss_psi"] = exec_result["pressure_loss_psi"]
        if "friction_factor" in exec_result:
            verification_result["friction_factor"] = exec_result["friction_factor"]
        if "reynolds_number" in exec_result:
            verification_result["reynolds_number"] = exec_result["reynolds_number"]
        if "flow_regime" in exec_result:
            verification_result["flow_regime"] = exec_result["flow_regime"]
        if "required_ah" in exec_result:
            verification_result["required_ah"] = exec_result["required_ah"]
        if "base_capacity_ah" in exec_result:
            verification_result["base_capacity_ah"] = exec_result["base_capacity_ah"]
        if "temperature_derating" in exec_result:
            verification_result["temperature_derating"] = exec_result["temperature_derating"]
        if "aging_derating" in exec_result:
            verification_result["aging_derating"] = exec_result["aging_derating"]
        if "discharge_rate_correction" in exec_result:
            verification_result["discharge_rate_correction"] = exec_result["discharge_rate_correction"]
        if "installed_ah" in exec_result:
            verification_result["installed_ah"] = exec_result["installed_ah"]
        if "usable_ah" in exec_result:
            verification_result["usable_ah"] = exec_result["usable_ah"]
        if "is_adequate" in exec_result:
            verification_result["is_adequate"] = exec_result["is_adequate"]
        if "margin_pct" in exec_result:
            verification_result["margin_pct"] = exec_result["margin_pct"]

        event = DomainEvent(
            eventId=f"evt-{uuid.uuid4().hex[:12]}",
            commandId=command.commandId,
            correlationId=command.correlationId,
            causationId=command.causationId,
            projectId=command.projectId,
            revision=new_revision,
            actor=command.principal.user_id,
            eventType=evt_type,
            timestamp=datetime.now(UTC).isoformat(),
            verificationResult=verification_result,
            auditReference=audit_ref,
            payload=exec_result,
        )

        # 10. Atomic Database Transaction: OCC commit + command execution + domain event
        committed, error_code = self.state_store.commit_transaction(
            command=command,
            new_revision=new_revision,
            exec_result=exec_result,
            event=event,
            payload_hash=payload_hash,
        )

        if not committed:
            latest_rev = self.get_project_revision(command.projectId)
            return CommandResult(
                success=False,
                commandId=command.commandId,
                projectId=command.projectId,
                revision=latest_rev,
                isDryRun=False,
                errorCode=error_code or "TRANSACTION_COMMIT_FAILED",
                errorMessage=(
                    f"Concurrency Conflict: Revision {command.expectedRevision} could not be committed. "
                    f"Project canonical revision is now {latest_rev}."
                ),
            )

        return CommandResult(
            success=True,
            commandId=command.commandId,
            projectId=command.projectId,
            revision=new_revision,
            isDryRun=False,
            resultData=exec_result,
            event=event,
        )


# Global singleton instance
default_command_bus = CommandBus()
