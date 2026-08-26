"""backend/core/workflow_engine.py — Deterministic Composite Workflow Engine (DAG Runner).

Architecture:
1. CompositeWorkflowDAG: Validates dependency graph and rejects cycles via Kahn's algorithm.
2. EphemeralStateOverlay: Manages in-memory state projections during dry-run preview with 0 DB leakage.
3. WorkflowExecutor: Orchestrates multi-step capability pipelines with strict all-or-nothing rollback
   and single atomic revision advancement (N -> N+1) upon commit.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.core.capability_registry import (
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    DomainCommand,
    DomainEvent,
)
from backend.core.state_store import (
    CommandStateStore,
    default_state_store,
)

logger = logging.getLogger(__name__)


class WorkflowError(Exception):
    """Base exception for workflow engine failures."""


class WorkflowCycleDetectedError(WorkflowError):
    """Raised when a circular dependency is detected in the DAG."""


class WorkflowValidationError(WorkflowError):
    """Raised when DAG structure or parameter mapping fails validation."""


class WorkflowExecutionError(WorkflowError):
    """Raised when a step in the workflow fails deterministic verification."""


@dataclass
class WorkflowNode:
    """Represents an atomic capability execution step in a DAG."""

    node_id: str
    capability_id: str
    dependencies: list[str] = field(default_factory=list)
    payload_template: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowNode:
        return cls(
            node_id=data["node_id"],
            capability_id=data["capability_id"],
            dependencies=data.get("dependencies", []),
            payload_template=data.get("payload_template", {}),
            description=data.get("description", ""),
        )


class CompositeWorkflowDAG:
    """Directed Acyclic Graph (DAG) validator and topological planner."""

    def __init__(self, nodes: list[WorkflowNode] | None = None) -> None:
        self.nodes: dict[str, WorkflowNode] = {}
        if nodes:
            for node in nodes:
                self.add_node(node)

    def add_node(self, node: WorkflowNode) -> None:
        if node.node_id in self.nodes:
            raise WorkflowValidationError(f"Duplicate node_id: '{node.node_id}'")
        self.nodes[node.node_id] = node

    def validate(self) -> list[WorkflowNode]:
        """Validate DAG topology, ensure all dependencies exist, and return topological order."""
        if not self.nodes:
            raise WorkflowValidationError("Workflow DAG contains no nodes.")

        # Check all dependency references exist
        for node in self.nodes.values():
            for dep in node.dependencies:
                if dep not in self.nodes:
                    raise WorkflowValidationError(
                        f"Node '{node.node_id}' depends on non-existent node '{dep}'"
                    )
                if dep == node.node_id:
                    raise WorkflowCycleDetectedError(
                        f"Self-referencing cycle in node '{node.node_id}'"
                    )

        # Kahn's algorithm for topological sorting and cycle detection
        in_degree: dict[str, int] = dict.fromkeys(self.nodes, 0)
        adj: dict[str, list[str]] = defaultdict(list)

        for node_id, node in self.nodes.items():
            for dep in node.dependencies:
                adj[dep].append(node_id)
                in_degree[node_id] += 1

        queue: deque[str] = deque([node_id for node_id, deg in in_degree.items() if deg == 0])
        ordered_ids: list[str] = []

        while queue:
            curr_id = queue.popleft()
            ordered_ids.append(curr_id)

            for neighbor in adj[curr_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(ordered_ids) != len(self.nodes):
            unresolved = [node_id for node_id, deg in in_degree.items() if deg > 0]
            raise WorkflowCycleDetectedError(
                f"Cyclic dependency detected in workflow DAG. Unresolved nodes: {unresolved}"
            )

        return [self.nodes[node_id] for node_id in ordered_ids]

    def get_topological_order(self) -> list[WorkflowNode]:
        return self.validate()

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [node.to_dict() for node in self.nodes.values()]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompositeWorkflowDAG:
        nodes = [WorkflowNode.from_dict(n) for n in data.get("nodes", [])]
        return cls(nodes=nodes)


class EphemeralStateOverlay:
    """Manages in-memory state projections during multi-step preview with 0 DB writes."""

    def __init__(self, base_canonical_state: dict[str, Any]) -> None:
        self.base_state = json.loads(json.dumps(base_canonical_state))
        self.overlay_devices: list[dict[str, Any]] = list(self.base_state.get("devices", []))
        self.overlay_circuits: dict[str, Any] = dict(self.base_state.get("circuits", {}))
        self.overlay_hydraulics: dict[str, Any] = dict(self.base_state.get("hydraulics", {}))
        calculations = self.base_state.get("calculations", {})
        self.overlay_calculations: dict[str, Any] = {
            "battery": dict(calculations.get("battery", {}))
        }

    def apply_delta(self, capability_id: str, result_data: dict[str, Any]) -> None:
        """Apply step results into the ephemeral in-memory projection."""
        if "devices" in result_data and isinstance(result_data["devices"], list):
            self.overlay_devices = list(result_data["devices"])

        if "voltage_drop_v" in result_data:
            cid = str(result_data.get("circuit_id", "nac-circuit-01"))
            self.overlay_circuits[cid] = result_data

        if "head_loss_m" in result_data or "flow_velocity_m_s" in result_data:
            pid = str(result_data.get("pipe_segment_id", "pipe-seg-01"))
            self.overlay_hydraulics[pid] = result_data

        if "required_ah" in result_data or "base_capacity_ah" in result_data:
            pnl_id = str(result_data.get("panel_id", "facp-01"))
            self.overlay_calculations["battery"][pnl_id] = result_data

    def get_projected_state(self, revision: int) -> dict[str, Any]:
        """Return projected canonical state at specified revision."""
        return {
            "devices": self.overlay_devices,
            "circuits": self.overlay_circuits,
            "hydraulics": self.overlay_hydraulics,
            "calculations": self.overlay_calculations,
            "revision": revision,
        }


@dataclass
class WorkflowExecutionStepResult:
    node_id: str
    capability_id: str
    command_id: str
    success: bool
    result_data: dict[str, Any]
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompositeWorkflowResult:
    workflow_id: str
    correlation_id: str
    project_id: str
    expected_revision: int
    new_revision: int
    is_dry_run: bool
    success: bool
    step_results: list[WorkflowExecutionStepResult]
    projected_state: dict[str, Any]
    combined_audit_digest: str
    event: DomainEvent | None = None
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "correlation_id": self.correlation_id,
            "project_id": self.project_id,
            "expected_revision": self.expected_revision,
            "new_revision": self.new_revision,
            "is_dry_run": self.is_dry_run,
            "success": self.success,
            "step_results": [s.to_dict() for s in self.step_results],
            "projected_state": self.projected_state,
            "combined_audit_digest": self.combined_audit_digest,
            "event": self.event.to_dict() if self.event else None,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class WorkflowExecutor:
    """Orchestrates validation, preview overlays, and atomic multi-command execution."""

    def __init__(
        self,
        capability_registry: CapabilityRegistry | None = None,
        state_store: CommandStateStore | None = None,
    ) -> None:
        self.registry = capability_registry or default_capability_registry
        self.state_store = state_store or default_state_store

    def execute(
        self,
        dag: CompositeWorkflowDAG,
        project_id: str,
        expected_revision: int,
        principal: AuthenticatedPrincipal,
        is_dry_run: bool = True,
        workflow_id: str | None = None,
        correlation_id: str | None = None,
        auto_rollback_on_warning: bool = False,
        governance_policy: dict[str, Any] | None = None,
        on_step_progress: Callable[[int, int, str, float, str], None] | None = None,
    ) -> CompositeWorkflowResult:
        w_id = workflow_id or f"wf-{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}"
        corr_id = correlation_id or f"corr-{w_id}"

        # Resolve auto-rollback policy from governance settings if provided
        if governance_policy is not None:
            auto_rollback_on_warning = bool(
                governance_policy.get("autoRollbackOnPhysicsWarning", auto_rollback_on_warning)
                or governance_policy.get("autoRollbackOnWarning", auto_rollback_on_warning)
            )

        # 1. Validate topological order & absence of cycles
        try:
            ordered_nodes = dag.validate()
        except WorkflowError as e:
            return CompositeWorkflowResult(
                workflow_id=w_id,
                correlation_id=corr_id,
                project_id=project_id,
                expected_revision=expected_revision,
                new_revision=expected_revision,
                is_dry_run=is_dry_run,
                success=False,
                step_results=[],
                projected_state={},
                combined_audit_digest="",
                error_code="INVALID_WORKFLOW_DAG",
                error_message=str(e),
            )

        # 2. Check Security & Principal Authentication
        if not principal.is_authenticated:
            return CompositeWorkflowResult(
                workflow_id=w_id,
                correlation_id=corr_id,
                project_id=project_id,
                expected_revision=expected_revision,
                new_revision=expected_revision,
                is_dry_run=is_dry_run,
                success=False,
                step_results=[],
                projected_state={},
                combined_audit_digest="",
                error_code="UNAUTHENTICATED_ACCESS",
                error_message="Principal is not authenticated.",
            )

        # Verify required scopes for ALL nodes before executing any step
        for node in ordered_nodes:
            cap = self.registry.get(node.capability_id)
            if not cap:
                return CompositeWorkflowResult(
                    workflow_id=w_id,
                    correlation_id=corr_id,
                    project_id=project_id,
                    expected_revision=expected_revision,
                    new_revision=expected_revision,
                    is_dry_run=is_dry_run,
                    success=False,
                    step_results=[],
                    projected_state={},
                    combined_audit_digest="",
                    error_code="CAPABILITY_NOT_FOUND",
                    error_message=f"Capability '{node.capability_id}' is not registered.",
                )
            for req_scope in cap.required_scopes:
                if not principal.has_scope(req_scope):
                    return CompositeWorkflowResult(
                        workflow_id=w_id,
                        correlation_id=corr_id,
                        project_id=project_id,
                        expected_revision=expected_revision,
                        new_revision=expected_revision,
                        is_dry_run=is_dry_run,
                        success=False,
                        step_results=[],
                        projected_state={},
                        combined_audit_digest="",
                        error_code="UNAUTHORIZED_SCOPE",
                        error_message=(
                            f"Principal '{principal.user_id}' lacks required scope: {req_scope} "
                            f"for step '{node.node_id}'"
                        ),
                    )

        # 3. Check Current Project Revision (OCC Check)
        current_rev = self.state_store.get_project_revision(project_id)
        if current_rev != expected_revision:
            return CompositeWorkflowResult(
                workflow_id=w_id,
                correlation_id=corr_id,
                project_id=project_id,
                expected_revision=expected_revision,
                new_revision=current_rev,
                is_dry_run=is_dry_run,
                success=False,
                step_results=[],
                projected_state={},
                combined_audit_digest="",
                error_code="CONCURRENCY_CONFLICT",
                error_message=(
                    f"Project '{project_id}' is at revision {current_rev}, "
                    f"workflow expected {expected_revision}."
                ),
            )

        # 4. Initialize Ephemeral State Overlay from Canonical State
        canonical_state = self.state_store.get_canonical_state(project_id)
        overlay = EphemeralStateOverlay(canonical_state)

        step_results: list[WorkflowExecutionStepResult] = []
        commands_to_commit: list[DomainCommand] = []
        exec_results_to_commit: list[dict[str, Any]] = []

        last_command_id: str | None = None

        # 5. Execute Steps sequentially over Ephemeral State Overlay
        for step_idx, node in enumerate(ordered_nodes, 1):
            t_step_start = time.perf_counter()
            cap = self.registry.get(node.capability_id)
            if not cap or not cap.handler:
                return CompositeWorkflowResult(
                    workflow_id=w_id,
                    correlation_id=corr_id,
                    project_id=project_id,
                    expected_revision=expected_revision,
                    new_revision=expected_revision,
                    is_dry_run=is_dry_run,
                    success=False,
                    step_results=step_results,
                    projected_state=overlay.get_projected_state(expected_revision),
                    combined_audit_digest="",
                    error_code="HANDLER_NOT_FOUND",
                    error_message=f"No execution handler registered for capability '{node.capability_id}'",
                )

            step_cmd_id = f"cmd-{w_id}-{node.node_id}"
            now_iso = datetime.now(UTC).isoformat()

            cmd = DomainCommand(
                commandId=step_cmd_id,
                correlationId=corr_id,
                capabilityId=node.capability_id,
                projectId=project_id,
                expectedRevision=expected_revision,
                timestamp=now_iso,
                principal=principal,
                riskClass=cap.risk_class,
                isDryRun=is_dry_run,
                payload=dict(node.payload_template),
                causationId=last_command_id,
            )

            try:
                result_data = cap.handler(node.payload_template)
            except Exception as e:
                logger.error("Step '%s' handler failed: %s", node.node_id, str(e), exc_info=True)
                step_results.append(
                    WorkflowExecutionStepResult(
                        node_id=node.node_id,
                        capability_id=node.capability_id,
                        command_id=step_cmd_id,
                        success=False,
                        result_data={},
                        error_code="HANDLER_EXECUTION_FAILED",
                        error_message=str(e),
                    )
                )
                return CompositeWorkflowResult(
                    workflow_id=w_id,
                    correlation_id=corr_id,
                    project_id=project_id,
                    expected_revision=expected_revision,
                    new_revision=expected_revision,
                    is_dry_run=is_dry_run,
                    success=False,
                    step_results=step_results,
                    projected_state=canonical_state,  # Rollback: unmutated state
                    combined_audit_digest="",
                    error_code="STEP_EXECUTION_FAILED",
                    error_message=f"Step '{node.node_id}' failed: {e}",
                )

            # Check compliance / verification flags if present
            if "is_compliant" in result_data and not result_data["is_compliant"]:
                step_results.append(
                    WorkflowExecutionStepResult(
                        node_id=node.node_id,
                        capability_id=node.capability_id,
                        command_id=step_cmd_id,
                        success=False,
                        result_data=result_data,
                        error_code="VERIFICATION_COMPLIANCE_FAILED",
                        error_message=f"Step '{node.node_id}' failed compliance checks.",
                    )
                )
                return CompositeWorkflowResult(
                    workflow_id=w_id,
                    correlation_id=corr_id,
                    project_id=project_id,
                    expected_revision=expected_revision,
                    new_revision=expected_revision,
                    is_dry_run=is_dry_run,
                    success=False,
                    step_results=step_results,
                    projected_state=canonical_state,  # Rollback to original
                    combined_audit_digest="",
                    error_code="VERIFICATION_COMPLIANCE_FAILED",
                    error_message=f"Step '{node.node_id}' produced non-compliant result.",
                )

            # Auto-rollback if physics/compliance warnings emitted and auto_rollback_on_warning enabled
            if auto_rollback_on_warning and result_data.get("warnings"):
                step_results.append(
                    WorkflowExecutionStepResult(
                        node_id=node.node_id,
                        capability_id=node.capability_id,
                        command_id=step_cmd_id,
                        success=False,
                        result_data=result_data,
                        error_code="PHYSICS_WARNING_ROLLBACK",
                        error_message=f"Step '{node.node_id}' triggered auto-rollback due to physics warnings: {result_data['warnings']}",
                    )
                )
                return CompositeWorkflowResult(
                    workflow_id=w_id,
                    correlation_id=corr_id,
                    project_id=project_id,
                    expected_revision=expected_revision,
                    new_revision=expected_revision,
                    is_dry_run=is_dry_run,
                    success=False,
                    step_results=step_results,
                    projected_state=canonical_state,  # Rollback to original unmutated state
                    combined_audit_digest="",
                    error_code="PHYSICS_WARNING_ROLLBACK",
                    error_message=f"Step '{node.node_id}' triggered auto-rollback due to physics/compliance warning.",
                )

            # Apply delta into ephemeral overlay
            overlay.apply_delta(node.capability_id, result_data)

            step_results.append(
                WorkflowExecutionStepResult(
                    node_id=node.node_id,
                    capability_id=node.capability_id,
                    command_id=step_cmd_id,
                    success=True,
                    result_data=result_data,
                )
            )

            commands_to_commit.append(cmd)
            exec_results_to_commit.append(result_data)
            last_command_id = step_cmd_id

            t_step_elapsed_ms = (time.perf_counter() - t_step_start) * 1000.0
            if on_step_progress is not None:
                try:
                    on_step_progress(
                        step_idx,
                        len(ordered_nodes),
                        node.node_id,
                        t_step_elapsed_ms,
                        "in_progress" if step_idx < len(ordered_nodes) else "completed",
                    )
                except Exception as cb_err:
                    logger.debug("Progress callback error: %s", cb_err)

        # 6. Compute Combined Cryptographic SHA-256 Audit Digest
        combined_payload = {
            "workflow_id": w_id,
            "project_id": project_id,
            "expected_revision": expected_revision,
            "step_results": [
                {"node_id": s.node_id, "capability_id": s.capability_id, "result": s.result_data}
                for s in step_results
            ],
        }
        digest = hashlib.sha256(
            json.dumps(combined_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

        # 7. Commit Mode: Atomically advance revision N -> N+1 in single DB transaction
        new_rev = expected_revision if is_dry_run else expected_revision + 1
        domain_event: DomainEvent | None = None

        if not is_dry_run:
            committed, err = self.state_store.commit_composite_transaction(
                project_id=project_id,
                expected_revision=expected_revision,
                commands=commands_to_commit,
                exec_results=exec_results_to_commit,
                combined_audit_digest=digest,
            )
            if not committed:
                return CompositeWorkflowResult(
                    workflow_id=w_id,
                    correlation_id=corr_id,
                    project_id=project_id,
                    expected_revision=expected_revision,
                    new_revision=self.state_store.get_project_revision(project_id),
                    is_dry_run=False,
                    success=False,
                    step_results=step_results,
                    projected_state=canonical_state,
                    combined_audit_digest="",
                    error_code=err or "COMPOSITE_COMMIT_FAILED",
                    error_message=f"Atomic composite transaction failed with {err}",
                )

            domain_event = DomainEvent(
                eventId=f"evt-wf-{w_id}",
                commandId=w_id,
                correlationId=corr_id,
                projectId=project_id,
                revision=new_rev,
                actor=principal.user_id,
                eventType="COMPOSITE_WORKFLOW_COMMITTED",
                timestamp=datetime.now(UTC).isoformat(),
                verificationResult={
                    "total_steps": len(ordered_nodes),
                    "steps": [s.node_id for s in step_results],
                    "combined_audit_digest": digest,
                },
                auditReference=digest,
                payload=combined_payload,
            )

        return CompositeWorkflowResult(
            workflow_id=w_id,
            correlation_id=corr_id,
            project_id=project_id,
            expected_revision=expected_revision,
            new_revision=new_rev,
            is_dry_run=is_dry_run,
            success=True,
            step_results=step_results,
            projected_state=overlay.get_projected_state(new_rev),
            combined_audit_digest=digest,
            event=domain_event,
        )
