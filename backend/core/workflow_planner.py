"""backend/core/workflow_planner.py — Autonomous Engineering Workflow Planner.

Phase 6 Architecture:
End-to-End Autonomous Engineering Workflows:
    User Intent (Natural Language / Structured Spec)
    ↓
    Context Resolution (ContextResolver)
    ↓
    Capability Discovery & Scope Verification (CapabilityRegistry)
    ↓
    Deterministic DAG Synthesis (CompositeWorkflowDAG)
    ↓
    Execution Policy Evaluation (ExecutionPolicy)
    ↓
    Dry-Run Preview (WorkflowExecutor + EphemeralStateOverlay)
    ↓
    Durable Lifecycle Dispatch (AgentRunOrchestrator + CommandBus OCC)
    ↓
    Validation, Canonical State Update (N -> N+1), Audit Trail, Deliverable Registration

Non-negotiable invariants:
- The LLM has ZERO engineering authority: all engineering computations are executed by deterministic
  registered capabilities.
- The backend is the sole authority for Authentication, Authorization, RBAC, OCC, Idempotency, and Audit.
- All step dependencies and execution ordering are strictly validated via Kahn's algorithm (CompositeWorkflowDAG).
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from backend.core.agent_run_orchestrator import (
    AgentRun,
    AgentRunOrchestrator,
    default_agent_run_orchestrator,
)
from backend.core.agent_run_store import ApprovalMode
from backend.core.capability_registry import (
    CAP_ELECTRICAL_CALCULATE_BATTERY,
    CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
    CAP_EXPORT_EXECUTE_EXPORT,
    CAP_EXPORT_PLAN_EXPORT,
    CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
    CAP_IMPORT_EXECUTE_IMPORT,
    CAP_IMPORT_INSPECT_FILE,
    CAP_IMPORT_PLAN_IMPORT,
    CAP_SPATIAL_PLACE_DEVICES,
    CAP_SPATIAL_VERIFY_SPACING,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
    default_command_bus,
)
from backend.core.context_resolver import (
    ContextResolver,
    default_context_resolver,
)
from backend.core.execution_policy import (
    PolicyResult,
    build_policy_context,
    evaluate_execution_policy,
)
from backend.core.workflow_engine import (
    CompositeWorkflowDAG,
    WorkflowExecutor,
    WorkflowNode,
)

logger = logging.getLogger(__name__)


class AutonomousPlannerError(Exception):
    """Base error for autonomous workflow planning failures."""


class CapabilityUnavailableError(AutonomousPlannerError):
    """Required capability is not available or principal lacks required scopes."""


class InvalidWorkflowIntentError(AutonomousPlannerError):
    """Intent cannot be parsed or resolved into valid engineering capabilities."""


@dataclass
class PlannedStep:
    """Represents a planned, policy-evaluated step in an autonomous workflow."""

    step_id: str
    capability_id: str
    description: str
    dependencies: list[str] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    risk_class: str = "LOW"
    policy_result: str = "AUTO_APPROVED"
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AutonomousPlan:
    """Complete, server-authoritative autonomous workflow plan ready for preview or execution."""

    plan_id: str
    project_id: str
    expected_revision: int
    intent_summary: str
    intent_category: str
    steps: list[PlannedStep]
    dag: dict[str, Any]
    requires_human_approval: bool
    overall_policy_decision: str
    projected_state: dict[str, Any]
    combined_audit_digest: str
    token_telemetry: dict[str, Any]
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [s.to_dict() if hasattr(s, "to_dict") else s for s in self.steps]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AutonomousPlan:
        steps_data = data.get("steps", [])
        steps = [PlannedStep(**s) if isinstance(s, dict) else s for s in steps_data]
        return cls(
            plan_id=str(data.get("plan_id", "")),
            project_id=str(data.get("project_id", "")),
            expected_revision=int(data.get("expected_revision", 1)),
            intent_summary=str(data.get("intent_summary", "")),
            intent_category=str(data.get("intent_category", "composite")),
            steps=steps,
            dag=dict(data.get("dag", {})),
            requires_human_approval=bool(data.get("requires_human_approval", False)),
            overall_policy_decision=str(data.get("overall_policy_decision", "AUTO_APPROVED")),
            projected_state=dict(data.get("projected_state", {})),
            combined_audit_digest=str(data.get("combined_audit_digest", "")),
            token_telemetry=dict(data.get("token_telemetry", {})),
            created_at=str(data.get("created_at", "")),
        )

    def to_agent_run_steps(self) -> list[dict[str, Any]]:
        """Format steps for consumption by AgentRunOrchestrator.start_run."""
        return [
            {
                "step_id": s.step_id,
                "capability_id": s.capability_id,
                "description": s.description,
                "payload": s.payload,
            }
            for s in self.steps
        ]


class AutonomousWorkflowPlanner:
    """Server-authoritative planner synthesizing natural language & structured intents into validated DAGs."""

    def __init__(
        self,
        command_bus: CommandBus | None = None,
        capability_registry: CapabilityRegistry | None = None,
        context_resolver: ContextResolver | None = None,
        orchestrator: AgentRunOrchestrator | None = None,
        environment: str | None = None,
    ) -> None:
        self._bus = command_bus or default_command_bus
        self._registry = capability_registry or default_capability_registry
        self._resolver = context_resolver or default_context_resolver
        self._orchestrator = orchestrator or default_agent_run_orchestrator
        self._environment = environment

    # ── Intent Parsing & Entity Extraction ────────────────────────────────────

    def _extract_spatial_spec(self, prompt: str, spec: dict[str, Any]) -> dict[str, Any]:
        width = float(spec.get("width_m") or spec.get("width") or 12.0)
        length = float(spec.get("length_m") or spec.get("length") or 16.0)
        height = float(spec.get("ceiling_height_m") or spec.get("height") or 3.2)
        room_id = str(spec.get("room_id") or spec.get("roomId") or "zone-a")

        # Regex extraction from prompt if present
        m_w = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:m|meter|meters)?\s*(?:x|by|×)\s*(\d+(?:\.\d+)?)\s*(?:m|meter|meters)?",
            prompt,
            re.I,
        )
        if m_w:
            width = float(m_w.group(1))
            length = float(m_w.group(2))

        m_room = re.search(r"(?:room|zone|area)\s*([a-zA-Z0-9_-]+)", prompt, re.I)
        if m_room:
            room_id = m_room.group(1)

        det_type = "smoke"
        if "heat" in prompt.lower() or "heat" in str(spec.get("detector_type", "")).lower():
            det_type = "heat"

        return {
            "room_id": room_id,
            "width_m": width,
            "length_m": length,
            "ceiling_height_m": height,
            "detector_type": det_type,
        }

    def _extract_electrical_spec(self, prompt: str, spec: dict[str, Any]) -> dict[str, Any]:
        circuit_id = str(spec.get("circuit_id") or spec.get("circuitId") or "nac-01")
        current_a = float(spec.get("current_a") or spec.get("currentA") or 2.0)
        length_m = float(spec.get("one_way_length_m") or spec.get("oneWayLengthM") or 40.0)
        awg = str(spec.get("awg") or "14").strip()

        m_curr = re.search(r"(\d+(?:\.\d+)?)\s*(?:a|amp|amps|amperes)", prompt, re.I)
        if m_curr:
            current_a = float(m_curr.group(1))

        m_len = re.search(
            r"(\d+(?:\.\d+)?)\s*(?:m|meter|meters)\s*(?:run|length|wire|cable)", prompt, re.I
        )
        if m_len:
            length_m = float(m_len.group(1))

        m_awg = re.search(r"(\d+)\s*awg", prompt, re.I)
        if m_awg:
            awg = m_awg.group(1)

        return {
            "circuit_id": circuit_id,
            "current_a": current_a,
            "one_way_length_m": length_m,
            "awg": awg,
        }

    def _extract_battery_spec(self, prompt: str, spec: dict[str, Any]) -> dict[str, Any]:
        panel_id = str(spec.get("panel_id") or spec.get("panelId") or "facp-01")
        standby_load = float(spec.get("standby_load_amps") or 0.8)
        alarm_load = float(spec.get("alarm_load_amps") or 3.0)
        standby_hours = float(spec.get("standby_hours") or 24.0)
        alarm_hours = float(spec.get("alarm_hours") or (5.0 / 60.0))
        installed_ah = float(spec["installed_ah"]) if spec.get("installed_ah") is not None else 50.0

        m_standby = re.search(r"(\d+(?:\.\d+)?)\s*h(?:our|ours)?\s*standby", prompt, re.I)
        if m_standby:
            standby_hours = float(m_standby.group(1))

        return {
            "panel_id": panel_id,
            "standby_load_amps": standby_load,
            "alarm_load_amps": alarm_load,
            "standby_hours": standby_hours,
            "alarm_hours": alarm_hours,
            "installed_ah": installed_ah,
        }

    def _extract_hydraulic_spec(self, prompt: str, spec: dict[str, Any]) -> dict[str, Any]:
        pipe_id = str(spec.get("pipe_segment_id") or spec.get("pipeId") or "pipe-01")
        length_m = float(spec.get("length_m") or 15.0)
        diameter_mm = float(spec.get("diameter_mm") or 50.0)
        flow_l_min = float(spec.get("flow_l_min") or 250.0)
        fluid_type = str(spec.get("fluid_type") or "water").lower()

        m_dia = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*pipe", prompt, re.I)
        if m_dia:
            diameter_mm = float(m_dia.group(1))

        m_flow = re.search(r"(\d+(?:\.\d+)?)\s*(?:l/min|gpm|lpm)", prompt, re.I)
        if m_flow:
            flow_l_min = float(m_flow.group(1))

        return {
            "pipe_segment_id": pipe_id,
            "length_m": length_m,
            "diameter_mm": diameter_mm,
            "flow_l_min": flow_l_min,
            "fluid_type": fluid_type,
        }

    def _extract_export_format(self, prompt: str, spec: dict[str, Any]) -> str:
        fmt = str(spec.get("target_format") or spec.get("format") or "").lower()
        if fmt in ("dxf", "ifc", "revit", "xlsx", "csv", "pdf", "json"):
            return fmt

        p = prompt.lower()
        if "ifc" in p:
            return "ifc"
        if "revit" in p:
            return "revit"
        if "xlsx" in p or "excel" in p or "boq" in p or "schedule" in p:
            return "xlsx"
        if "csv" in p:
            return "csv"
        if "pdf" in p or "report" in p:
            return "pdf"
        if "json" in p:
            return "json"
        return "dxf"

    # ── Plan Synthesis ────────────────────────────────────────────────────────

    def plan_workflow(
        self,
        prompt: str,
        *,
        principal: AuthenticatedPrincipal,
        project_id: str = "",
        expected_revision: int | None = None,
        composite_spec: dict[str, Any] | None = None,
        approval_mode: ApprovalMode | str = ApprovalMode.AUTO,
        governance_policy: dict[str, Any] | None = None,
    ) -> AutonomousPlan:
        """Analyze intent, resolve context, discover capabilities, synthesize DAG, evaluate policy, and run dry-run."""
        if not principal.is_authenticated:
            raise AutonomousPlannerError(
                "Principal must be authenticated to plan an autonomous workflow."
            )

        if expected_revision is None:
            expected_revision = self._bus.get_project_revision(project_id)
            if expected_revision is None:
                raise AutonomousPlannerError(
                    f"Project '{project_id}' is uninitialized or missing canonical revision."
                )

        spec = dict(composite_spec or {})
        prompt_clean = prompt.strip()
        lower_prompt = prompt_clean.lower()

        # Classify intent & construct workflow nodes
        nodes: list[WorkflowNode] = []
        intent_category = "composite"

        # Check for Import Workflow Intent
        if spec.get("file_id") or "import" in lower_prompt or "upload" in lower_prompt:
            intent_category = "import"
            file_id = str(spec.get("file_id") or "staged-drawing-01")
            nodes.append(
                WorkflowNode(
                    node_id="step-1-inspect",
                    capability_id=CAP_IMPORT_INSPECT_FILE,
                    dependencies=[],
                    payload_template={"file_id": file_id},
                    description="Inspect and validate drawing file structure & layers",
                )
            )
            nodes.append(
                WorkflowNode(
                    node_id="step-2-plan-import",
                    capability_id=CAP_IMPORT_PLAN_IMPORT,
                    dependencies=["step-1-inspect"],
                    payload_template={"file_id": file_id, "project_id": project_id},
                    description="Generate deterministic entity mapping & revision plan",
                )
            )
            nodes.append(
                WorkflowNode(
                    node_id="step-3-execute-import",
                    capability_id=CAP_IMPORT_EXECUTE_IMPORT,
                    dependencies=["step-2-plan-import"],
                    payload_template={
                        "file_id": file_id,
                        "project_id": project_id,
                        "expected_revision": expected_revision,
                    },
                    description="Atomically commit imported devices to canonical state",
                )
            )

        # Check for Pure Export Workflow Intent
        elif (
            "export" in lower_prompt or "download" in lower_prompt or spec.get("target_format")
        ) and not any(
            k in lower_prompt for k in ("place", "layout", "calculate", "design", "solve")
        ):
            intent_category = "export"
            fmt = self._extract_export_format(lower_prompt, spec)
            nodes.append(
                WorkflowNode(
                    node_id="step-1-plan-export",
                    capability_id=CAP_EXPORT_PLAN_EXPORT,
                    dependencies=[],
                    payload_template={"project_id": project_id, "target_format": fmt},
                    description=f"Plan {fmt.upper()} export artifact mapping & validation",
                )
            )
            nodes.append(
                WorkflowNode(
                    node_id="step-2-execute-export",
                    capability_id=CAP_EXPORT_EXECUTE_EXPORT,
                    dependencies=["step-1-plan-export"],
                    payload_template={
                        "project_id": project_id,
                        "expected_revision": expected_revision,
                        "target_format": fmt,
                    },
                    description=f"Generate and verify signed {fmt.upper()} deliverable",
                )
            )

        # Multi-step Engineering Analysis & Placement Pipeline
        else:
            is_spatial = any(
                k in lower_prompt
                for k in (
                    "place",
                    "layout",
                    "detector",
                    "room",
                    "spacing",
                    "smoke",
                    "heat",
                    "area",
                    "zone",
                    "device",
                    "coverage",
                )
            )
            is_electrical = any(
                k in lower_prompt
                for k in ("voltage", "drop", "wire", "awg", "nac", "slc", "circuit", "cable")
            )
            is_battery = any(
                k in lower_prompt for k in ("battery", "standby", "backup", "power", "ah", "facp")
            )
            is_hydraulic = any(
                k in lower_prompt
                for k in (
                    "hydraulic",
                    "pipe",
                    "flow",
                    "pressure",
                    "darcy",
                    "head loss",
                    "sprinkler",
                )
            )
            is_export = any(
                k in lower_prompt
                for k in ("export", "download", "deliverable", "ifc", "dxf", "revit", "report")
            )

            if not (is_spatial or is_electrical or is_battery or is_hydraulic or is_export or spec):
                raise InvalidWorkflowIntentError(
                    f"Prompt '{prompt_clean}' does not contain recognized engineering intent keywords."
                )

            intent_category = "engineering_workflow"
            # Node 1: Spatial Placement
            sp_spec = self._extract_spatial_spec(lower_prompt, spec)
            nodes.append(
                WorkflowNode(
                    node_id="step-1-spatial-layout",
                    capability_id=CAP_SPATIAL_PLACE_DEVICES,
                    dependencies=[],
                    payload_template=sp_spec,
                    description=f"Auto-layout NFPA 72 compliant {sp_spec['detector_type']} detectors in {sp_spec['room_id']}",
                )
            )

            # Node 2: Spacing Verification
            nodes.append(
                WorkflowNode(
                    node_id="step-2-spacing-audit",
                    capability_id=CAP_SPATIAL_VERIFY_SPACING,
                    dependencies=["step-1-spatial-layout"],
                    payload_template={
                        "room_id": sp_spec["room_id"],
                        "width_m": sp_spec["width_m"],
                        "length_m": sp_spec["length_m"],
                        "ceiling_height_m": sp_spec["ceiling_height_m"],
                        "detector_type": sp_spec["detector_type"],
                    },
                    description="Verify prescriptive detector spacing & boundary coverage",
                )
            )

            # Node 3: Electrical Voltage Drop (if requested or in full composite)
            if (
                any(
                    k in lower_prompt
                    for k in ("voltage", "drop", "circuit", "nac", "slc", "electrical", "wiring")
                )
                or len(nodes) >= 1
            ):
                el_spec = self._extract_electrical_spec(lower_prompt, spec)
                nodes.append(
                    WorkflowNode(
                        node_id="step-3-electrical-drop",
                        capability_id=CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
                        dependencies=["step-2-spacing-audit"],
                        payload_template=el_spec,
                        description=f"Calculate end-of-line voltage drop for circuit {el_spec['circuit_id']}",
                    )
                )

            # Node 4: Battery Sizing (if requested)
            if any(
                k in lower_prompt for k in ("battery", "standby", "backup", "power", "ah", "facp")
            ):
                bat_spec = self._extract_battery_spec(lower_prompt, spec)
                last_dep = nodes[-1].node_id if nodes else []
                nodes.append(
                    WorkflowNode(
                        node_id="step-4-battery-sizing",
                        capability_id=CAP_ELECTRICAL_CALCULATE_BATTERY,
                        dependencies=[last_dep] if last_dep else [],
                        payload_template=bat_spec,
                        description=f"Size secondary power supply battery for {bat_spec['panel_id']}",
                    )
                )

            # Node 5: Hydraulic Calculation (if requested)
            if any(
                k in lower_prompt
                for k in (
                    "hydraulic",
                    "pipe",
                    "flow",
                    "pressure",
                    "darcy",
                    "head loss",
                    "sprinkler",
                )
            ):
                hyd_spec = self._extract_hydraulic_spec(lower_prompt, spec)
                last_dep = nodes[-1].node_id if nodes else []
                nodes.append(
                    WorkflowNode(
                        node_id="step-5-hydraulic-calc",
                        capability_id=CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
                        dependencies=[last_dep] if last_dep else [],
                        payload_template=hyd_spec,
                        description=f"Solve Darcy-Weisbach friction loss for pipe {hyd_spec['pipe_segment_id']}",
                    )
                )

            # Node 6: Export Deliverable (if user mentioned deliverable / export / report)
            if any(
                k in lower_prompt
                for k in ("export", "download", "dxf", "pdf", "report", "boq", "excel")
            ):
                fmt = self._extract_export_format(lower_prompt, spec)
                last_dep = nodes[-1].node_id if nodes else []
                nodes.append(
                    WorkflowNode(
                        node_id="step-6-export-deliverable",
                        capability_id=CAP_EXPORT_EXECUTE_EXPORT,
                        dependencies=[last_dep] if last_dep else [],
                        payload_template={
                            "project_id": project_id,
                            "expected_revision": expected_revision,
                            "target_format": fmt,
                        },
                        description=f"Generate and sign final {fmt.upper()} project deliverable",
                    )
                )

        if not nodes:
            raise InvalidWorkflowIntentError(
                "Unable to synthesize any valid engineering steps from user prompt."
            )

        # Construct and validate DAG topology (Kahn's algorithm)
        dag = CompositeWorkflowDAG(nodes=nodes)
        dag.validate()

        # Capability Discovery & Scope Verification
        planned_steps: list[PlannedStep] = []
        requires_approval = False
        overall_policy = PolicyResult.AUTO_APPROVED

        mode = ApprovalMode(approval_mode) if isinstance(approval_mode, str) else approval_mode

        for node in nodes:
            cap = self._registry.get(node.capability_id)
            if cap is None:
                raise CapabilityUnavailableError(
                    f"Required capability '{node.capability_id}' is not registered."
                )

            # Scope check
            if not all(principal.has_scope(s) for s in cap.required_scopes):
                raise CapabilityUnavailableError(
                    f"Principal '{principal.user_id}' lacks required scopes {cap.required_scopes} for capability '{node.capability_id}'."
                )

            # Execution Policy Evaluation
            ctx = build_policy_context(
                self._registry,
                node.capability_id,
                principal,
                execution_mode=mode,
                project_id=project_id,
                governance_policy=governance_policy,
                environment=self._environment,
            )
            policy_decision = evaluate_execution_policy(ctx)

            step_requires_approval = policy_decision.result in (
                PolicyResult.REQUIRES_APPROVAL,
                PolicyResult.MANDATORY_HUMAN_REVIEW,
            )
            if step_requires_approval:
                requires_approval = True

            if policy_decision.result == PolicyResult.DENIED:
                overall_policy = PolicyResult.DENIED
            elif step_requires_approval and overall_policy != PolicyResult.DENIED:
                overall_policy = policy_decision.result

            planned_steps.append(
                PlannedStep(
                    step_id=node.node_id,
                    capability_id=node.capability_id,
                    description=node.description,
                    dependencies=list(node.dependencies),
                    payload=dict(node.payload_template),
                    risk_class=str(cap.risk_class),
                    policy_result=policy_decision.result.value,
                    requires_approval=step_requires_approval,
                )
            )

        # Dry-run execution to project state & create audit digest
        executor = WorkflowExecutor(self._registry, self._bus.state_store)
        try:
            dry_run_res = executor.execute(
                dag=dag,
                project_id=project_id,
                expected_revision=expected_revision,
                principal=principal,
                is_dry_run=True,
                workflow_id=f"wf-plan-{uuid.uuid4().hex[:8]}",
                correlation_id=f"corr-plan-{uuid.uuid4().hex[:8]}",
                governance_policy=governance_policy,
            )
            projected_state = dry_run_res.projected_state
            combined_audit = dry_run_res.combined_audit_digest
            dry_run_success = dry_run_res.success
        except Exception as exc:
            logger.warning("Dry-run preview failed: %s", exc)
            projected_state = {"devices": [], "revision": expected_revision}
            combined_audit = ""
            dry_run_success = False

        plan_id = f"plan-{uuid.uuid4().hex[:12]}"
        intent_summary = f"Autonomous Engineering Workflow ({len(nodes)} steps: {', '.join(n.capability_id for n in nodes)})"

        telemetry = {
            "prompt_length": len(prompt),
            "step_count": len(planned_steps),
            "dry_run_success": dry_run_success,
            "projected_devices": len(projected_state.get("devices", [])),
        }

        return AutonomousPlan(
            plan_id=plan_id,
            project_id=project_id,
            expected_revision=expected_revision,
            intent_summary=intent_summary,
            intent_category=intent_category,
            steps=planned_steps,
            dag=dag.to_dict(),
            requires_human_approval=requires_approval,
            overall_policy_decision=overall_policy.value,
            projected_state=projected_state,
            combined_audit_digest=combined_audit,
            token_telemetry=telemetry,
        )

    # ── Plan Execution Dispatch ───────────────────────────────────────────────

    def execute_plan(
        self,
        plan: AutonomousPlan,
        *,
        principal: AuthenticatedPrincipal,
        approval_mode: ApprovalMode | str = ApprovalMode.AUTO,
        conversation_id: str = "",
        governance_policy: dict[str, Any] | None = None,
    ) -> AgentRun:
        """Dispatch a validated plan to the durable AgentRunOrchestrator."""
        if not principal.is_authenticated:
            raise AutonomousPlannerError("Principal is not authenticated.")

        steps_payload = plan.to_agent_run_steps()
        plan_doc = {
            "plan_id": plan.plan_id,
            "intent_summary": plan.intent_summary,
            "intent_category": plan.intent_category,
            "dag": plan.dag,
            "expected_revision": plan.expected_revision,
            "combined_audit_digest": plan.combined_audit_digest,
        }
        if governance_policy:
            plan_doc["governance_policy"] = governance_policy

        return self._orchestrator.start_run(
            principal,
            project_id=plan.project_id,
            steps=steps_payload,
            approval_mode=approval_mode,
            conversation_id=conversation_id,
            plan=plan_doc,
            governance_policy=governance_policy,
        )


default_workflow_planner = AutonomousWorkflowPlanner()
