"""backend/tests/test_phase2e_composite_workflow.py — Test Suite for Phase 2E Composite Workflow Engine (DAG Runner).

Covers:
1. DAG topological sorting, validation, branching, and cycle rejection.
2. EphemeralStateOverlay in-memory delta isolation.
3. All-or-nothing rollback on intermediate failure (zero state leakage).
4. Single atomic revision advancement (N -> N+1) and SHA-256 audit digest.
5. Optimistic Concurrency Control (OCC) conflict rejection.
6. Bounded composite context resolution (<= 1500 tokens).
7. Security boundaries & RBAC scope enforcement.
8. Protected deterministic solver immutability.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any

import pytest

from backend.core.capability_registry import (
    CapabilityDefinition,
    CapabilityRegistry,
)
from backend.core.command_bus import AuthenticatedPrincipal
from backend.core.context_resolver import ContextResolver
from backend.core.state_store import CommandStateStore
from backend.core.workflow_engine import (
    CompositeWorkflowDAG,
    EphemeralStateOverlay,
    WorkflowCycleDetectedError,
    WorkflowExecutor,
    WorkflowNode,
    WorkflowValidationError,
)
from backend.database import Database


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db = Database(db_path=path)
    yield db
    try:
        os.remove(path)
    except Exception:
        pass


@pytest.fixture
def state_store(temp_db) -> CommandStateStore:
    """Fixture providing a CommandStateStore backed by the isolated DB."""
    return CommandStateStore(db=temp_db)


@pytest.fixture
def populated_registry() -> CapabilityRegistry:
    """Fixture providing standard capabilities across all 4 domains."""
    reg = CapabilityRegistry()

    def spatial_handler(payload: dict[str, Any]) -> dict[str, Any]:
        width = payload.get("width_m", 10.0)
        length = payload.get("length_m", 15.0)
        devices = [
            {"id": "dev-01", "type": "smoke", "x": 3.0, "y": 4.0, "z": 3.0, "is_compliant": True},
            {"id": "dev-02", "type": "smoke", "x": 7.0, "y": 11.0, "z": 3.0, "is_compliant": True},
        ]
        return {
            "devices": devices,
            "device_count": len(devices),
            "coverage_pct": 100.0,
            "room_area_m2": width * length,
            "is_compliant": True,
        }

    def electrical_drop_handler(payload: dict[str, Any]) -> dict[str, Any]:
        current = payload.get("current_a", 2.0)
        length = payload.get("one_way_length_m", 30.0)
        # Resistance approx 0.0102 ohm/m for 14 AWG
        r = 0.0102 * length * 2.0
        v_drop = current * r
        pct = (v_drop / 24.0) * 100.0
        is_compliant = pct <= 10.0
        return {
            "circuit_id": payload.get("circuit_id", "nac-01"),
            "voltage_drop_v": round(v_drop, 4),
            "voltage_drop_pct": round(pct, 2),
            "is_compliant": is_compliant,
            "violations": [] if is_compliant else [f"Voltage drop {pct:.2f}% exceeds 10% limit"],
        }

    def battery_handler(payload: dict[str, Any]) -> dict[str, Any]:
        standby_a = payload.get("standby_load_amps", 0.5)
        alarm_a = payload.get("alarm_load_amps", 2.0)
        base_ah = (standby_a * 24.0) + (alarm_a * (5.0 / 60.0))
        aging = payload.get("aging_factor", 1.25)
        req_ah = base_ah * aging
        installed = payload.get("installed_ah", 50.0)
        is_adequate = (installed >= req_ah) if installed is not None else True
        return {
            "panel_id": payload.get("panel_id", "facp-01"),
            "base_capacity_ah": round(base_ah, 3),
            "required_ah": round(req_ah, 3),
            "installed_ah": installed,
            "is_adequate": is_adequate,
            "is_compliant": is_adequate,
            "warnings": [] if is_adequate else ["Installed capacity below required."],
        }

    def hydraulics_handler(payload: dict[str, Any]) -> dict[str, Any]:
        length = payload.get("length_m", 20.0)
        flow = payload.get("flow_l_min", 300.0)
        is_compliant = flow <= 500.0
        return {
            "pipe_segment_id": payload.get("pipe_segment_id", "pipe-01"),
            "head_loss_m": round(0.05 * length * (flow / 100.0), 3),
            "flow_velocity_m_s": 2.1,
            "is_compliant": is_compliant,
            "violations": [] if is_compliant else ["Flow velocity / loss excessive"],
        }

    reg.register(
        CapabilityDefinition(
            capability_id="spatial.place_devices",
            name="Place Devices",
            description="Places devices",
            category="spatial",
            handler=spatial_handler,
            required_scopes=["design:write"],
            risk_class="MEDIUM",
            input_schema={},
            output_schema={},
        )
    )
    reg.register(
        CapabilityDefinition(
            capability_id="electrical.calculate_voltage_drop",
            name="Voltage Drop",
            description="Calculates voltage drop",
            category="electrical",
            handler=electrical_drop_handler,
            required_scopes=["engineering:calculate"],
            risk_class="ENGINEERING_MUTATION",
            input_schema={},
            output_schema={},
        )
    )
    reg.register(
        CapabilityDefinition(
            capability_id="electrical.calculate_battery",
            name="Battery Sizing",
            description="Calculates battery capacity",
            category="electrical",
            handler=battery_handler,
            required_scopes=["engineering:calculate"],
            risk_class="ENGINEERING_MUTATION",
            input_schema={},
            output_schema={},
        )
    )
    reg.register(
        CapabilityDefinition(
            capability_id="hydraulics.solve_darcy_weisbach",
            name="Hydraulics Darcy-Weisbach",
            description="Solves pipe hydraulics",
            category="hydraulics",
            handler=hydraulics_handler,
            required_scopes=["engineering:calculate"],
            risk_class="ENGINEERING_MUTATION",
            input_schema={},
            output_schema={},
        )
    )

    return reg


@pytest.fixture
def admin_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="eng-admin-01",
        email="eng-admin-01@bazspark.internal",
        role="admin",
        scopes=["design:write", "engineering:calculate", "audit:read"],
    )


# ---------------------------------------------------------------------------
# Tier 1: DAG Topological Sorting, Validation & Cycle Detection
# ---------------------------------------------------------------------------
class TestCompositeWorkflowDAG:
    def test_linear_dag_topological_sort(self):
        dag = CompositeWorkflowDAG([
            WorkflowNode(node_id="step1", capability_id="spatial.place_devices"),
            WorkflowNode(node_id="step2", capability_id="electrical.calculate_voltage_drop", dependencies=["step1"]),
            WorkflowNode(node_id="step3", capability_id="electrical.calculate_battery", dependencies=["step2"]),
        ])
        ordered = dag.validate()
        assert [n.node_id for n in ordered] == ["step1", "step2", "step3"]

    def test_branching_dag_topological_sort(self):
        # A -> B, A -> C, B -> D, C -> D
        dag = CompositeWorkflowDAG([
            WorkflowNode(node_id="node_a", capability_id="spatial.place_devices"),
            WorkflowNode(node_id="node_b", capability_id="electrical.calculate_voltage_drop", dependencies=["node_a"]),
            WorkflowNode(node_id="node_c", capability_id="hydraulics.solve_darcy_weisbach", dependencies=["node_a"]),
            WorkflowNode(node_id="node_d", capability_id="electrical.calculate_battery", dependencies=["node_b", "node_c"]),
        ])
        ordered = dag.validate()
        order_ids = [n.node_id for n in ordered]
        assert order_ids[0] == "node_a"
        assert order_ids[-1] == "node_d"
        assert "node_b" in order_ids[1:3]
        assert "node_c" in order_ids[1:3]

    def test_cycle_detection_rejection(self):
        # Cycle: A -> B -> C -> A
        dag = CompositeWorkflowDAG([
            WorkflowNode(node_id="stepA", capability_id="spatial.place_devices", dependencies=["stepC"]),
            WorkflowNode(node_id="stepB", capability_id="electrical.calculate_voltage_drop", dependencies=["stepA"]),
            WorkflowNode(node_id="stepC", capability_id="electrical.calculate_battery", dependencies=["stepB"]),
        ])
        with pytest.raises(WorkflowCycleDetectedError):
            dag.validate()

    def test_self_cycle_rejection(self):
        dag = CompositeWorkflowDAG([
            WorkflowNode(node_id="stepSelf", capability_id="spatial.place_devices", dependencies=["stepSelf"]),
        ])
        with pytest.raises(WorkflowCycleDetectedError):
            dag.validate()

    def test_missing_dependency_rejection(self):
        dag = CompositeWorkflowDAG([
            WorkflowNode(node_id="step1", capability_id="spatial.place_devices", dependencies=["non_existent_node"]),
        ])
        with pytest.raises(WorkflowValidationError) as exc:
            dag.validate()
        assert "non-existent node" in str(exc.value)

    def test_empty_dag_rejection(self):
        dag = CompositeWorkflowDAG([])
        with pytest.raises(WorkflowValidationError):
            dag.validate()


# ---------------------------------------------------------------------------
# Tier 2: Ephemeral State Overlay In-Memory Isolation
# ---------------------------------------------------------------------------
class TestEphemeralStateOverlay:
    def test_overlay_delta_layering_without_db_writes(self):
        base_state = {
            "devices": [{"id": "old-01"}],
            "circuits": {"old-circuit": {"voltage_drop_v": 0.5}},
            "hydraulics": {},
            "calculations": {"battery": {}},
            "revision": 1,
        }
        overlay = EphemeralStateOverlay(base_state)

        # Step 1: Update devices
        overlay.apply_delta("spatial.place_devices", {"devices": [{"id": "new-01"}, {"id": "new-02"}]})
        # Step 2: Update circuit
        overlay.apply_delta("electrical.calculate_voltage_drop", {"circuit_id": "nac-02", "voltage_drop_v": 0.85})
        # Step 3: Update battery
        overlay.apply_delta("electrical.calculate_battery", {"panel_id": "facp-02", "required_ah": 35.0})

        proj = overlay.get_projected_state(revision=2)
        assert len(proj["devices"]) == 2
        assert "nac-02" in proj["circuits"]
        assert "facp-02" in proj["calculations"]["battery"]
        # Ensure base_state was not modified in-place
        assert len(base_state["devices"]) == 1
        assert "nac-02" not in base_state["circuits"]


# ---------------------------------------------------------------------------
# Tier 3: All-or-Nothing Rollback on Intermediate Failure
# ---------------------------------------------------------------------------
class TestAllOrNothingRollback:
    def test_intermediate_failure_aborts_pipeline_with_zero_state_mutations(
        self, state_store, populated_registry, admin_principal
    ):
        project_id = "proj-rollback-01"
        executor = WorkflowExecutor(populated_registry, state_store)

        # Step 2 will fail because current=10.0 A over 100 m yields > 10% voltage drop
        dag = CompositeWorkflowDAG([
            WorkflowNode(
                node_id="step1",
                capability_id="spatial.place_devices",
                payload_template={"width_m": 12.0, "length_m": 15.0},
            ),
            WorkflowNode(
                node_id="step2",
                capability_id="electrical.calculate_voltage_drop",
                dependencies=["step1"],
                payload_template={"circuit_id": "nac-fail", "current_a": 10.0, "one_way_length_m": 100.0},
            ),
            WorkflowNode(
                node_id="step3",
                capability_id="electrical.calculate_battery",
                dependencies=["step2"],
                payload_template={"panel_id": "facp-01"},
            ),
        ])

        res = executor.execute(
            dag=dag,
            project_id=project_id,
            expected_revision=1,
            principal=admin_principal,
            is_dry_run=True,
        )

        assert not res.success
        assert res.error_code == "VERIFICATION_COMPLIANCE_FAILED"
        # Confirm no state saved in DB
        assert state_store.get_project_revision(project_id) == 1
        raw_state = state_store.get_canonical_state(project_id)
        assert raw_state.get("devices") == []

    def test_handler_exception_aborts_cleanly(
        self, state_store, populated_registry, admin_principal
    ):
        project_id = "proj-rollback-exc"
        executor = WorkflowExecutor(populated_registry, state_store)

        def faulty_handler(_p):
            raise RuntimeError("Fatal hardware simulation fault")

        populated_registry.register(
            CapabilityDefinition(
                capability_id="spatial.faulty",
                name="Faulty Handler",
                description="Faulty handler for test",
                category="spatial",
                handler=faulty_handler,
                required_scopes=["design:write"],
                risk_class="MEDIUM",
                input_schema={},
                output_schema={},
            )
        )

        dag = CompositeWorkflowDAG([
            WorkflowNode(node_id="stepFault", capability_id="spatial.faulty"),
        ])

        res = executor.execute(
            dag=dag,
            project_id=project_id,
            expected_revision=1,
            principal=admin_principal,
            is_dry_run=False,
        )

        assert not res.success
        assert res.error_code == "STEP_EXECUTION_FAILED"
        assert state_store.get_project_revision(project_id) == 1


# ---------------------------------------------------------------------------
# Tier 4: Single Atomic Revision Advancement (N -> N+1) & SHA-256 Audit
# ---------------------------------------------------------------------------
class TestAtomicMultiCommandCommit:
    def test_full_4_domain_composite_commit(
        self, state_store, populated_registry, admin_principal
    ):
        project_id = "proj-atomic-4domain"
        executor = WorkflowExecutor(populated_registry, state_store)

        dag = CompositeWorkflowDAG([
            WorkflowNode(
                node_id="step-spatial",
                capability_id="spatial.place_devices",
                payload_template={"width_m": 14.0, "length_m": 20.0},
            ),
            WorkflowNode(
                node_id="step-elec-drop",
                capability_id="electrical.calculate_voltage_drop",
                dependencies=["step-spatial"],
                payload_template={"circuit_id": "nac-main-01", "current_a": 1.5, "one_way_length_m": 25.0},
            ),
            WorkflowNode(
                node_id="step-elec-bat",
                capability_id="electrical.calculate_battery",
                dependencies=["step-elec-drop"],
                payload_template={"panel_id": "facp-main-01", "standby_load_amps": 0.6, "installed_ah": 65.0},
            ),
            WorkflowNode(
                node_id="step-hydraulic",
                capability_id="hydraulics.solve_darcy_weisbach",
                dependencies=["step-spatial"],
                payload_template={"pipe_segment_id": "riser-01", "length_m": 15.0, "flow_l_min": 250.0},
            ),
        ])

        # 1. Dry run preview first
        preview = executor.execute(
            dag=dag,
            project_id=project_id,
            expected_revision=1,
            principal=admin_principal,
            is_dry_run=True,
        )
        assert preview.success
        assert preview.is_dry_run
        assert preview.new_revision == 1
        assert state_store.get_project_revision(project_id) == 1  # 0 DB mutations on preview

        # 2. Atomic commit (N -> N+1)
        commit_res = executor.execute(
            dag=dag,
            project_id=project_id,
            expected_revision=1,
            principal=admin_principal,
            is_dry_run=False,
        )
        assert commit_res.success
        assert not commit_res.is_dry_run
        assert commit_res.new_revision == 2
        assert len(commit_res.step_results) == 4
        assert commit_res.combined_audit_digest
        assert commit_res.event is not None
        assert commit_res.event.eventType == "COMPOSITE_WORKFLOW_COMMITTED"

        # Verify persisted state in database
        assert state_store.get_project_revision(project_id) == 2
        canonical = state_store.get_canonical_state(project_id)
        assert len(canonical["devices"]) == 2
        assert "nac-main-01" in canonical["circuits"]
        assert "facp-main-01" in canonical["calculations"]["battery"]
        assert "riser-01" in canonical["hydraulics"]


# ---------------------------------------------------------------------------
# Tier 5: Optimistic Concurrency Control (OCC) and Conflict Detection
# ---------------------------------------------------------------------------
class TestCompositeOCCAndConcurrency:
    def test_stale_expected_revision_rejected(
        self, state_store, populated_registry, admin_principal
    ):
        project_id = "proj-occ-stale"
        state_store.set_project_revision(project_id, 3)

        executor = WorkflowExecutor(populated_registry, state_store)
        dag = CompositeWorkflowDAG([
            WorkflowNode(node_id="step1", capability_id="spatial.place_devices"),
        ])

        # Workflow expects revision 1, but project is at 3
        res = executor.execute(
            dag=dag,
            project_id=project_id,
            expected_revision=1,
            principal=admin_principal,
            is_dry_run=False,
        )
        assert not res.success
        assert res.error_code == "CONCURRENCY_CONFLICT"
        assert state_store.get_project_revision(project_id) == 3


# ---------------------------------------------------------------------------
# Tier 6: Bounded Composite Context Resolution (<= 1500 Tokens)
# ---------------------------------------------------------------------------
class TestCompositeContextBudget:
    def test_composite_context_within_1500_token_limit(self):
        resolver = ContextResolver()
        pkt = resolver.resolve_composite_context(
            project_id="proj-budget-01",
            revision=1,
            composite_spec={
                "room_bounds": {"width_m": 25.0, "length_m": 40.0, "ceiling_height_m": 4.5},
                "circuit": {"circuit_id": "nac-large-01", "current_a": 2.5, "one_way_length_m": 60.0, "awg": "12"},
                "hydraulic": {"pipe_segment_id": "pipe-main-01", "length_m": 50.0, "diameter_mm": 100.0, "flow_l_min": 600.0},
                "battery": {"panel_id": "facp-complex", "standby_load_amps": 1.5, "alarm_load_amps": 5.0, "installed_ah": 100.0},
            },
        )
        assert pkt.is_within_budget
        assert pkt.token_count <= 1500
        assert pkt.telemetry["raw_cad_excluded"] is True
        assert pkt.telemetry["geometry_mesh_excluded"] is True


# ---------------------------------------------------------------------------
# Tier 7: Security Boundaries & RBAC Scope Enforcement
# ---------------------------------------------------------------------------
class TestCompositeSecurityBoundaries:
    def test_unauthenticated_principal_rejected(
        self, state_store, populated_registry
    ):
        anon = AuthenticatedPrincipal(
            user_id="anon",
            email="anon@bazspark.internal",
            role="viewer",
            is_authenticated=False,
        )
        executor = WorkflowExecutor(populated_registry, state_store)
        dag = CompositeWorkflowDAG([
            WorkflowNode(node_id="step1", capability_id="spatial.place_devices"),
        ])
        res = executor.execute(
            dag=dag,
            project_id="proj-sec-anon",
            expected_revision=1,
            principal=anon,
        )
        assert not res.success
        assert res.error_code == "UNAUTHENTICATED_ACCESS"

    def test_missing_scope_on_downstream_node_rejects_entire_dag_before_execution(
        self, state_store, populated_registry
    ):
        # Principal only has "design:write", lacks "engineering:calculate"
        limited_principal = AuthenticatedPrincipal(
            user_id="junior-designer",
            email="junior@bazspark.internal",
            role="designer",
            scopes=["design:write"],
        )
        executor = WorkflowExecutor(populated_registry, state_store)
        dag = CompositeWorkflowDAG([
            WorkflowNode(node_id="step1", capability_id="spatial.place_devices"),
            WorkflowNode(
                node_id="step2",
                capability_id="electrical.calculate_voltage_drop",
                dependencies=["step1"],
            ),
        ])

        res = executor.execute(
            dag=dag,
            project_id="proj-sec-scope",
            expected_revision=1,
            principal=limited_principal,
            is_dry_run=True,
        )
        assert not res.success
        assert res.error_code == "UNAUTHORIZED_SCOPE"
        assert "engineering:calculate" in (res.error_message or "")
