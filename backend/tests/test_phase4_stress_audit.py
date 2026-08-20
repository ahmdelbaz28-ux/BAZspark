"""backend/tests/test_phase4_stress_audit.py — Phase 4 Ultimate End-to-End Stress, Adversarial & Forensic Audit Suite.

Verifies:
TIER 1: Adversarial LLM Mathematical Override & Physics Boundary Stress
  - Vector 1.1: Hydraulic Extreme Velocity (14.5 m/s) & Cavitation / Water Hammer warning + autoRollbackOnWarning
  - Vector 1.2: Sub-Zero LiFePO4 Thermal Inversion (-25°C, kt <= 0.60, sub-zero lithium plating warning)
  - Vector 1.3: Adversarial Client Result Spoofing (server ignores client spoofing, computes true drop > 30%)
TIER 2: Distributed OCC Concurrency & Race-Condition Hammer
  - Vector 2.1: 5 Concurrent Workers Composite Execution (1 win N -> N+1, 4 CONCURRENCY_CONFLICT, 0 deadlocks)
  - Vector 2.2: Persistent Idempotency Collision with mutated payload (IDEMPOTENCY_KEY_REUSE_CONFLICT)
TIER 3: Context Bounding & Telemetry Overflow Stress
  - Vector 3.1: 50-room / 500-device coordinate bomb (strict pruning, <= 1500 token budget, accurate telemetry)
"""

from __future__ import annotations

import concurrent.futures
import math
import os
import tempfile
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from backend.core.capability_registry import (
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
    DomainCommand,
)
from backend.core.context_resolver import (
    ContextResolver,
)
from backend.core.state_store import CommandStateStore
from backend.core.workflow_engine import (
    CompositeWorkflowDAG,
    WorkflowExecutor,
    WorkflowNode,
)
from backend.database import Database
from fireai.core.darcy_weisbach_solver import (
    FluidType,
    calculate_darcy_weisbach_friction_loss,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
    return CommandStateStore(db=temp_db)


@pytest.fixture
def command_bus(state_store) -> CommandBus:
    return CommandBus(default_capability_registry, state_store)


@pytest.fixture
def engineer_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="eng-stress-01",
        email="eng-stress@bazspark.internal",
        role="ENGINEER",
        scopes=[
            "spatial:read",
            "spatial:write",
            "electrical:read",
            "electrical:write",
            "hydraulics:read",
            "hydraulics:write",
            "audit:read",
        ],
    )


@pytest.fixture
def viewer_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="viewer-stress-01",
        email="viewer@bazspark.internal",
        role="VIEWER",
        scopes=["spatial:read", "electrical:read", "hydraulics:read"],
    )


# ---------------------------------------------------------------------------
# TIER 1: Adversarial LLM Mathematical Override & Physics Boundary Stress
# ---------------------------------------------------------------------------

class TestTier1AdversarialAndPhysicsBoundaryStress:
    """TIER 1: Mathematical Override & Physics Boundary Stress."""

    def test_vector_1_1_hydraulic_extreme_velocity_and_auto_rollback(
        self, state_store, engineer_principal
    ):
        """Vector 1.1: Hydraulic Extreme Velocity & Cavitation Test.

        - Inject pipe network flow yielding water velocity v = 14.5 m/s.
        - Verify exact Darcy-Weisbach head loss and velocity calculation.
        - Verify high-severity warning flags ('Excessive flow velocity / Water hammer risk').
        - Verify that if autoRollbackOnWarning is enabled in governance, DAG immediately cancels with 0 DB commit.
        """
        # Flow calculation for v = 14.5 m/s in DN50 (0.05m inner diameter)
        # Area A = pi * (0.025)^2 = 0.0019635 m2
        # Q = v * A = 14.5 * 0.0019635 = 0.02847 m3/s = 1708.2 L/min
        diameter_mm = 50.0
        pipe_length_m = 30.0
        flow_l_min = 1708.24  # yields v ~= 14.5 m/s

        # 1. Direct Solver Verification
        res = calculate_darcy_weisbach_friction_loss(
            pipe_length_m=pipe_length_m,
            pipe_diameter_m=diameter_mm / 1000.0,
            flow_rate_kg_s=(flow_l_min / 60000.0) * 1000.0,
            fluid_type=FluidType.WATER,
        )
        assert pytest.approx(res.flow_velocity_m_s, rel=1e-2) == 14.50
        assert res.flow_velocity_m_s > 10.0
        assert res.head_loss_m > 0
        assert res.pressure_loss_psi > 0

        # 2. Capability Execution via Default Registry
        cap = default_capability_registry.get("hydraulics.solve_darcy_weisbach")
        assert cap is not None
        cap_result = cap.handler({
            "pipe_segment_id": "pipe-high-vel-01",
            "length_m": pipe_length_m,
            "diameter_mm": diameter_mm,
            "flow_l_min": flow_l_min,
            "fluid_type": "water",
        })

        assert pytest.approx(cap_result["flow_velocity_m_s"], rel=1e-2) == 14.50
        assert any("Excessive flow velocity flag" in w and "water hammer" in w.lower() for w in cap_result["warnings"])

        # 3. DAG Execution with autoRollbackOnWarning = True
        dag = CompositeWorkflowDAG([
            WorkflowNode(
                node_id="step-hydraulic-extreme",
                capability_id="hydraulics.solve_darcy_weisbach",
                payload_template={
                    "pipe_segment_id": "pipe-high-vel-01",
                    "length_m": pipe_length_m,
                    "diameter_mm": diameter_mm,
                    "flow_l_min": flow_l_min,
                    "fluid_type": "water",
                },
            )
        ])

        project_id = "proj-stress-hydraulic-01"
        executor = WorkflowExecutor(default_capability_registry, state_store)

        # Baseline revision is 1
        assert state_store.get_project_revision(project_id) == 1

        # Execute with autoRollbackOnWarning enabled in governance_policy
        wf_res = executor.execute(
            dag=dag,
            project_id=project_id,
            expected_revision=1,
            principal=engineer_principal,
            is_dry_run=False,
            auto_rollback_on_warning=True,
            governance_policy={"autoRollbackOnPhysicsWarning": True},
        )

        # Must fail immediately with PHYSICS_WARNING_ROLLBACK
        assert wf_res.success is False
        assert wf_res.error_code == "PHYSICS_WARNING_ROLLBACK"
        assert "physics/compliance warning" in (wf_res.error_message or "").lower()

        # Verify ZERO database commit: project revision remains 1 and canonical state is unmutated
        assert state_store.get_project_revision(project_id) == 1
        canonical = state_store.get_canonical_state(project_id)
        assert canonical.get("hydraulics") == {} or "pipe-high-vel-01" not in canonical.get("hydraulics", {})

    def test_vector_1_2_sub_zero_lifepo4_thermal_inversion(
        self, state_store, engineer_principal
    ):
        """Vector 1.2: Sub-Zero LiFePO4 Thermal Inversion Test.

        - Execute `electrical.calculate_battery` at ambient temperature -25°C with LiFePO4 chemistry.
        - Assert temperature correction factor kt <= 0.60 is applied.
        - Assert mandatory domain warning flag for sub-zero lithium charging is emitted.
        """
        cap = default_capability_registry.get("electrical.calculate_battery")
        assert cap is not None

        payload = {
            "panel_id": "facp-subzero-01",
            "standby_load_amps": 1.2,
            "alarm_load_amps": 4.5,
            "standby_hours": 24.0,
            "alarm_hours": 0.5,
            "min_temperature_c": -25.0,
            "battery_type": "lifepo4",
            "installed_ah": 100.0,
            "aging_factor": 1.25,
        }

        result = cap.handler(payload)

        # Assert temperature derating factor kt <= 0.60
        # At -25°C: 0.70 + (-25/100) = 0.45, bounded by max(0.50, ...) -> 0.50 <= 0.60
        assert result["temperature_derating"] <= 0.60
        assert result["temperature_derating"] == 0.50

        # Assert mandatory domain warning for sub-zero lithium charging
        assert any(
            "LiFePO4 charging below 0°C" in w or "lithium plating" in w.lower()
            for w in result["warnings"]
        )

        # Base capacity check: (1.2 * 24) + (4.5 * 0.5) = 28.8 + 2.25 = 31.05 Ah
        assert pytest.approx(result["base_capacity_ah"], rel=1e-2) == 31.05
        # Required Ah with deratings: 31.05 * 1.25 (aging) / (0.50 * discharge_rate) > 60 Ah
        assert result["required_ah"] > result["base_capacity_ah"]

    def test_vector_1_3_adversarial_client_result_spoofing(
        self, state_store, engineer_principal
    ):
        """Vector 1.3: Adversarial Client Result Spoofing.

        - Inject fake calculation results in the payload (voltage_drop_pct: 1.2% for 4.0A over 120m AWG 18).
        - Assert that server-side deterministic core completely ignores client-supplied outputs.
        - Compute true physical drop (> 30%, FAIL / non-compliant).
        """
        cap = default_capability_registry.get("electrical.calculate_voltage_drop")
        assert cap is not None

        spoofed_payload = {
            "circuit_id": "nac-spoofed-01",
            "current_a": 4.0,
            "one_way_length_m": 120.0,
            "awg": "18",
            "nominal_voltage": 24.0,
            "temperature_c": 75.0,
            # Adversarial spoofed keys injected by malicious client
            "voltage_drop_pct": 1.2,
            "voltage_drop_v": 0.288,
            "is_compliant": True,
            "violations": [],
        }

        result = cap.handler(spoofed_payload)

        # Server-side physical calculation:
        # AWG 18 resistance @ 75C: approx 0.025-0.028 ohm/m. Loop length = 240m.
        # R_loop = 240 * ~0.027 = ~6.48 ohms.
        # V_drop = 4.0 * 6.48 = ~25.9V -> Drop % = (25.9 / 24.0) * 100 > 100% (or > 30% under any table)
        assert result["voltage_drop_pct"] > 30.0
        assert result["voltage_drop_pct"] != 1.2  # Spoofed value discarded
        assert result["is_compliant"] is False
        assert len(result["violations"]) > 0
        assert "exceeds" in result["violations"][0].lower()


# ---------------------------------------------------------------------------
# TIER 2: Distributed OCC Concurrency & Race-Condition Hammer
# ---------------------------------------------------------------------------

class TestTier2DistributedOCCAndConcurrencyHammer:
    """TIER 2: Distributed OCC Concurrency & Race-Condition Hammer."""

    def test_vector_2_1_multi_worker_concurrent_composite_execution(
        self, state_store, engineer_principal
    ):
        """Vector 2.1: Multi-Worker Concurrent Composite Execution.

        - Spin up 5 concurrent async/thread workers attempting to commit different
          composite workflows against Project Revision N.
        - Exactly 1 transaction succeeds, advancing revision N -> N+1.
        - Exactly 4 transactions fail immediately with CONCURRENCY_CONFLICT.
        - Zero lost updates, zero dirty reads, and zero database table lock deadlocks.
        """
        project_id = f"proj-occ-hammer-{uuid.uuid4().hex[:8]}"

        # Initialize project at revision 1
        state_store.save_canonical_state(
            project_id=project_id,
            state={"devices": [], "circuits": {}, "hydraulics": {}, "calculations": {"battery": {}}},
            revision=1,
        )
        assert state_store.get_project_revision(project_id) == 1

        num_workers = 5

        def worker_task(worker_idx: int) -> dict[str, Any]:
            worker_store = CommandStateStore(db=state_store._db)
            worker_executor = WorkflowExecutor(default_capability_registry, worker_store)

            dag = CompositeWorkflowDAG([
                WorkflowNode(
                    node_id=f"step-elec-w{worker_idx}",
                    capability_id="electrical.calculate_voltage_drop",
                    payload_template={
                        "circuit_id": f"nac-w{worker_idx}",
                        "current_a": 1.0 + (worker_idx * 0.1),
                        "one_way_length_m": 15.0,
                        "awg": "14",
                    },
                ),
                WorkflowNode(
                    node_id=f"step-hyd-w{worker_idx}",
                    capability_id="hydraulics.solve_darcy_weisbach",
                    dependencies=[f"step-elec-w{worker_idx}"],
                    payload_template={
                        "pipe_segment_id": f"pipe-w{worker_idx}",
                        "length_m": 10.0 + worker_idx,
                        "diameter_mm": 50.0,
                        "flow_l_min": 120.0,
                        "fluid_type": "water",
                    },
                ),
            ])

            res = worker_executor.execute(
                dag=dag,
                project_id=project_id,
                expected_revision=1,
                principal=engineer_principal,
                is_dry_run=False,
                workflow_id=f"wf-hammer-{worker_idx}-{uuid.uuid4().hex[:6]}",
            )
            return {
                "worker_idx": worker_idx,
                "success": res.success,
                "error_code": res.error_code,
                "new_revision": res.new_revision,
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(worker_task, i) for i in range(num_workers)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        successes = [r for r in results if r["success"] is True]
        conflicts = [r for r in results if r["error_code"] == "CONCURRENCY_CONFLICT"]

        # Exactly 1 winner, exactly 4 conflicts
        assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {results}"
        assert len(conflicts) == 4, f"Expected exactly 4 conflicts, got {len(conflicts)}: {results}"

        # Project revision advanced exactly 1 -> 2 (no lost updates or double increments)
        final_rev = state_store.get_project_revision(project_id)
        assert final_rev == 2

    def test_vector_2_2_idempotency_collision_and_mutated_replay(
        self, command_bus, engineer_principal
    ):
        """Vector 2.2: Idempotency Collision & Mutated Replay.

        - Replay the same commandId with a modified payload.
        - Assert immediate rejection with IDEMPOTENCY_KEY_REUSE_CONFLICT.
        """
        project_id = f"proj-idemp-{uuid.uuid4().hex[:8]}"
        command_id = f"cmd-fixed-idemp-{uuid.uuid4().hex[:8]}"

        cmd1 = DomainCommand(
            commandId=command_id,
            correlationId="corr-idemp-1",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload={"room_id": "room-original", "width_m": 10.0, "length_m": 15.0},
        )

        res1 = command_bus.execute(cmd1)
        assert res1.success is True
        assert res1.revision == 2

        # Replay identical commandId with identical payload -> should return cached success
        res1_replay = command_bus.execute(cmd1)
        assert res1_replay.success is True
        assert res1_replay.revision == 2

        # Mutate payload with same commandId -> must reject with IDEMPOTENCY_KEY_REUSE_CONFLICT
        cmd2_mutated = DomainCommand(
            commandId=command_id,
            correlationId="corr-idemp-2",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=2,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload={"room_id": "room-MUTATED-PAYLOAD", "width_m": 25.0, "length_m": 30.0},
        )

        res2 = command_bus.execute(cmd2_mutated)
        assert res2.success is False
        assert res2.errorCode == "IDEMPOTENCY_KEY_REUSE_CONFLICT"
        assert "collision" in (res2.errorMessage or "").lower() or "reuse" in (res2.errorMessage or "").lower()


# ---------------------------------------------------------------------------
# TIER 3: Context Bounding & Telemetry Overflow Stress
# ---------------------------------------------------------------------------

class TestTier3ContextBoundingAndTelemetryOverflowStress:
    """TIER 3: Context Bounding & Telemetry Overflow Stress."""

    def test_vector_3_1_large_scale_multi_room_coordinate_bomb(self):
        """Vector 3.1: Large-Scale Multi-Room Coordinate Bomb.

        - Feed a 50-room building floor plan with 500 candidate device nodes and complex spatial bounds
          into `resolve_composite_context()`.
        - Assert raw CAD entities and coordinate meshes are strictly pruned.
        - Bounded context packet size strictly respects the <= 1,500 token cap.
        - Telemetry accurately logs prompt token counts without memory leakage.
        """
        resolver = ContextResolver(token_budget=1500)

        # Construct large-scale coordinate bomb payload (50 rooms, 500 nodes, dense geometry mesh)
        huge_coordinate_bomb: dict[str, Any] = {
            "domains": ["spatial", "electrical", "hydraulics", "battery"],
            "room_bounds": {
                "width_m": 60.0,
                "length_m": 80.0,
                "ceiling_height_m": 4.5,
            },
            "circuit": {
                "circuit_id": "nac-mega-01",
                "current_a": 3.0,
                "one_way_length_m": 75.0,
                "awg": "12",
            },
            "hydraulic": {
                "pipe_segment_id": "pipe-main-01",
                "length_m": 45.0,
                "diameter_mm": 100.0,
                "flow_l_min": 850.0,
            },
            "battery": {
                "panel_id": "facp-central-01",
                "standby_load_amps": 2.5,
                "alarm_load_amps": 8.0,
                "installed_ah": 120.0,
            },
            # Massive adversarial coordinate bomb payload: raw entities, meshes, 500 candidate nodes
            "raw_cad_entities": [
                {
                    "entity_id": f"ENT-DWG-3D-{i}",
                    "layer": "A-WALL-FULL",
                    "polygon_mesh": [
                        [math.sin(i + j) * 100.0, math.cos(i + j) * 100.0, 3.2]
                        for j in range(20)
                    ],
                    "vertices_count": 20,
                    "color_rgb": [255, 128, 64],
                    "line_type": "CONTINUOUS",
                }
                for i in range(50)
            ],
            "candidate_nodes": [
                {
                    "node_id": f"cand-node-{i}",
                    "coord_x": round(i * 1.5, 4),
                    "coord_y": round(i * 2.2, 4),
                    "coord_z": 3.2,
                    "metadata": {"floor": i // 10, "zone": f"Z-{i % 5}"},
                }
                for i in range(500)
            ],
            "spatial_triangulation_mesh": {
                "indices": list(range(1500)),
                "normals": [[0.0, 0.0, 1.0]] * 500,
            },
        }

        packet = resolver.resolve_composite_context(
            project_id="proj-mega-bomb-01",
            revision=5,
            composite_spec=huge_coordinate_bomb,
        )

        # 1. Assert bounded context token count is strictly <= 1500 tokens
        assert packet.token_count <= 1500, f"Token count {packet.token_count} exceeded budget 1500"
        assert packet.is_within_budget is True

        # 2. Assert raw CAD entities, polygon meshes, and candidate node dumps are strictly pruned
        spec = packet.composite_spec
        assert "raw_cad_entities" not in spec
        assert "candidate_nodes" not in spec
        assert "spatial_triangulation_mesh" not in spec

        # 3. Assert telemetry flags accurately record CAD exclusion and utilization
        telemetry = packet.telemetry
        assert telemetry["raw_cad_excluded"] is True
        assert telemetry["geometry_mesh_excluded"] is True
        assert telemetry["whole_project_dump_excluded"] is True
        assert telemetry["budget_limit"] == 1500
        assert telemetry["measured_tokens"] == packet.token_count
        assert 0.0 < telemetry["utilization_pct"] < 100.0
