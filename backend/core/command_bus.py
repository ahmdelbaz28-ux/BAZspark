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
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from backend.core.capability_registry import (
    CapabilityRegistry,
    default_capability_registry,
)

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

    commandId: str
    correlationId: str
    capabilityId: str
    projectId: str
    expectedRevision: int
    timestamp: str
    principal: AuthenticatedPrincipal
    riskClass: str = "MEDIUM"  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    isDryRun: bool = False
    payload: dict[str, Any] = field(default_factory=dict)
    causationId: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass
class DomainEvent:
    """Traceable domain event produced upon successful command execution."""

    eventId: str
    commandId: str
    correlationId: str
    projectId: str
    revision: int
    actor: str
    eventType: str
    timestamp: str
    verificationResult: dict[str, Any]
    auditReference: str
    payload: dict[str, Any]
    causationId: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommandResult:
    """Result of command dispatch via CommandBus."""

    success: bool
    commandId: str
    projectId: str
    revision: int
    isDryRun: bool
    resultData: dict[str, Any] = field(default_factory=dict)
    event: DomainEvent | None = None
    errorCode: str | None = None
    errorMessage: str | None = None

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

    def __init__(self, capability_registry: CapabilityRegistry | None = None) -> None:
        self.registry = capability_registry or default_capability_registry
        # In-memory store for canonical project revisions and project states
        self._project_revisions: dict[str, int] = {}
        self._project_canonical_state: dict[str, dict[str, Any]] = {}
        # Idempotency cache: commandId -> CommandResult
        self._idempotency_store: dict[str, CommandResult] = {}
        # Audit event store
        self._audit_events: list[DomainEvent] = []

    def get_project_revision(self, project_id: str) -> int:
        """Get canonical revision of a project (defaulting to 1 for new projects)."""
        return self._project_revisions.get(project_id, 1)

    def set_project_revision(self, project_id: str, revision: int) -> None:
        """Update canonical project revision (e.g. on manual user edit)."""
        self._project_revisions[project_id] = revision

    def get_canonical_state(self, project_id: str) -> dict[str, Any]:
        """Retrieve canonical engineering state for project."""
        return self._project_canonical_state.get(project_id, {"devices": []})

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
        for k in command.payload.keys():
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

        # 5. Idempotency Check (for non-dry-run commands)
        if not command.isDryRun and command.commandId in self._idempotency_store:
            logger.info("Idempotent command replay: %s", command.commandId)
            return self._idempotency_store[command.commandId]

        # 6. Optimistic Concurrency Control (OCC) Check
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

        # 9. Canonical State Commit & Revision Increment (N -> N+1)
        new_revision = current_rev + 1
        self._project_revisions[command.projectId] = new_revision

        # Update canonical state atomically
        existing_state = self._project_canonical_state.get(command.projectId, {"devices": []})
        new_devices = exec_result.get("devices", [])
        updated_state = {
            "devices": new_devices if new_devices else existing_state.get("devices", []),
            "last_mutation": command.capabilityId,
            "revision": new_revision,
        }
        self._project_canonical_state[command.projectId] = updated_state

        # 10. Audit Lineage & Cryptographic Event Generation
        audit_payload = {
            "commandId": command.commandId,
            "capabilityId": command.capabilityId,
            "projectId": command.projectId,
            "revision": new_revision,
            "actor": command.principal.user_id,
            "device_count": len(new_devices),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        audit_ref = hashlib.sha256(
            json.dumps(audit_payload, sort_keys=True).encode()
        ).hexdigest()

        event = DomainEvent(
            eventId=f"evt-{uuid.uuid4().hex[:12]}",
            commandId=command.commandId,
            correlationId=command.correlationId,
            causationId=command.causationId,
            projectId=command.projectId,
            revision=new_revision,
            actor=command.principal.user_id,
            eventType="DEVICES_PLACED" if "place_devices" in command.capabilityId else "COMPLIANCE_VERIFIED",
            timestamp=datetime.now(timezone.utc).isoformat(),
            verificationResult={
                "coverage_pct": exec_result.get("coverage_pct", 100.0),
                "is_compliant": exec_result.get("is_compliant", True),
                "violations": exec_result.get("violations", []),
            },
            auditReference=audit_ref,
            payload=exec_result,
        )
        self._audit_events.append(event)

        result = CommandResult(
            success=True,
            commandId=command.commandId,
            projectId=command.projectId,
            revision=new_revision,
            isDryRun=False,
            resultData=exec_result,
            event=event,
        )

        # Store in idempotency store
        self._idempotency_store[command.commandId] = result
        return result


# Global singleton instance
default_command_bus = CommandBus()
