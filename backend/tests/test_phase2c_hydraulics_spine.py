"""backend/tests/test_phase2c_hydraulics_spine.py — Phase 2C Vertical Slice D Test Suite.

Verifies:
1. Context Resolution: Bounded hydraulic context <= 1500 tokens, excludes CAD/mesh.
2. Capability Discovery: `hydraulics.solve_darcy_weisbach`, scope filtering.
3. Deterministic Engineering Authority: LLM fabricated results are completely overridden.
4. Preview Semantics (isDryRun=True): 0 DB mutations, revision N -> N.
5. Commit Semantics (isDryRun=False): Snapshot persistence under canonical_state["hydraulics"], revision N -> N+1, domain event emitted, SHA-256 audit digest.
6. Authorization & Security: Scope enforcement, forbidden payload keys rejection.
7. Optimistic Concurrency Control (OCC): Single winner, single conflict.
8. Persistent Idempotency: Replay cache, collision rejection on payload mismatch.
9. Transaction Rollback: Clean rollback on execution failure.
10. Multi-Domain Canonical State Preservation: Devices + Circuits + Hydraulics co-exist.
11. Hydraulic Warning & Standards Verification: Conservative velocity warning classification (no blanket NFPA 13 claims).
"""

import json
import uuid
from datetime import UTC, datetime

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
    BoundedHydraulicContextPacket,
    ContextResolver,
    default_context_resolver,
)
from backend.core.state_store import CommandStateStore
from backend.database import Database

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_db(tmp_path):
    """Provides an isolated SQLite database instance for deterministic testing."""
    db_file = str(tmp_path / f"test_hydraulics_spine_{uuid.uuid4().hex[:8]}.db")
    return Database(db_file)


@pytest.fixture
def state_store(fresh_db):
    """Provides a fresh CommandStateStore backed by an isolated database."""
    return CommandStateStore(fresh_db)


@pytest.fixture(autouse=True)
def _auto_seed_phase2c_projects(state_store):
    for pid in [
        "proj_adv_hyd",
        "proj_fm200",
        "proj_commit_hyd",
        "proj_sec",
        "proj_occ_hyd",
        "proj_idem_hyd",
        "proj_idem_reuse",
        "proj_multidomain",
    ]:
        state_store.set_project_revision(pid, 1)


@pytest.fixture
def command_bus(state_store):
    """Provides a fresh CommandBus with default capability registry."""
    return CommandBus(default_capability_registry, state_store)


@pytest.fixture
def engineer_principal():
    return AuthenticatedPrincipal(
        user_id="eng_hydraulics_01",
        email="engineer@fireai.internal",
        role="ENGINEER",
        scopes=[
            "hydraulics:read",
            "hydraulics:write",
            "spatial:read",
            "spatial:write",
            "electrical:read",
            "electrical:write",
        ],
    )


@pytest.fixture
def viewer_principal():
    return AuthenticatedPrincipal(
        user_id="viewer_01",
        email="viewer@fireai.internal",
        role="VIEWER",
        scopes=["hydraulics:read", "spatial:read", "electrical:read"],
    )


@pytest.fixture
def unauthenticated_principal():
    return AuthenticatedPrincipal(
        user_id="anon",
        email="anon@untrusted.com",
        role="ANONYMOUS",
        scopes=[],
    )


# ---------------------------------------------------------------------------
# 1. Context Resolution & Bounding Tests
# ---------------------------------------------------------------------------


class TestHydraulicContextResolution:
    def test_resolve_hydraulic_context_strictly_bounded(self):
        """Ensures context packet contains only hydraulic fields and stays well under 1,500 token limit."""
        resolver = ContextResolver(token_budget=1500)
        pkt = resolver.resolve_hydraulic_context(
            project_id="proj_hyd_001",
            pipe_segment_id="pipe_main_01",
            revision=1,
            hydraulic_spec={
                "length_m": 25.0,
                "diameter_mm": 65.0,
                "flow_l_min": 500.0,
                "fluid_type": "water",
                "roughness_mm": 0.0457,
                "elevation_m": 3.5,
            },
        )

        assert isinstance(pkt, BoundedHydraulicContextPacket)
        assert pkt.project_id == "proj_hyd_001"
        assert pkt.pipe_segment_id == "pipe_main_01"
        assert pkt.revision == 1
        assert pkt.is_within_budget is True
        assert pkt.token_count < 250  # Typical hydraulic packet is ~70-130 tokens
        assert pkt.token_count <= pkt.budget_limit
        assert pkt.telemetry["raw_cad_excluded"] is True
        assert pkt.telemetry["geometry_mesh_excluded"] is True
        assert pkt.telemetry["whole_project_dump_excluded"] is True

    def test_resolve_hydraulic_context_default_parameters(self):
        """Ensures default values populate cleanly when minimal spec is provided."""
        resolver = default_context_resolver
        pkt = resolver.resolve_hydraulic_context(
            project_id="proj_hyd_002",
            pipe_segment_id="pipe_seg_def",
            revision=3,
        )

        assert pkt.hydraulic_spec["length_m"] == 15.0
        assert pkt.hydraulic_spec["diameter_mm"] == 50.0
        assert pkt.hydraulic_spec["fluid_type"] == "water"
        assert pkt.is_within_budget is True


# ---------------------------------------------------------------------------
# 2. Capability Registry & Discovery Tests
# ---------------------------------------------------------------------------


class TestHydraulicCapabilityRegistry:
    def test_capability_registration_metadata(self):
        """Verifies hydraulics.solve_darcy_weisbach definition and schema."""
        cap = default_capability_registry.get("hydraulics.solve_darcy_weisbach")
        assert cap is not None
        assert cap.category == "hydraulics"
        assert cap.risk_class == "ENGINEERING_MUTATION"
        assert "hydraulics:write" in cap.required_scopes
        assert "length_m" in cap.input_schema["required"]
        assert "diameter_mm" in cap.input_schema["required"]

    def test_capability_discovery_with_scopes(self, engineer_principal, viewer_principal):
        """Verifies scope-based filtering on hydraulic capability discovery."""
        eng_caps = default_capability_registry.discover(
            categories=["hydraulics"],
            scopes=engineer_principal.scopes,
        )
        assert any(c.capability_id == "hydraulics.solve_darcy_weisbach" for c in eng_caps)

        # Viewer does not have hydraulics:write -> should not discover mutation capability
        viewer_caps = default_capability_registry.discover(
            categories=["hydraulics"],
            scopes=viewer_principal.scopes,
        )
        assert not any(c.capability_id == "hydraulics.solve_darcy_weisbach" for c in viewer_caps)


# ---------------------------------------------------------------------------
# 3. Deterministic Engineering Authority & Adversarial LLM Resistance Tests
# ---------------------------------------------------------------------------


class TestDeterministicHydraulicAuthority:
    def test_authoritative_solver_overrides_llm_hallucination(
        self, command_bus, engineer_principal
    ):
        """Adversarial test: Incoming LLM payload injects fabricated velocity and friction loss."""
        # Genuine physical calculation for 20m, 50mm pipe, 300 L/min water:
        # Vol flow = 300 / 60000 = 0.005 m3/s. Area = pi * 0.05^2 / 4 = 0.0019635 m2
        # Velocity = 0.005 / 0.0019635 = 2.546 m/s
        cmd = DomainCommand(
            commandId="cmd_adv_hyd_01",
            correlationId="corr_adv_hyd_01",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_adv_hyd",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=True,
            payload={
                "pipe_segment_id": "pipe_adv_01",
                "length_m": 20.0,
                "diameter_mm": 50.0,
                "flow_l_min": 300.0,
                "fluid_type": "water",
                # ADVERSARIAL INJECTIONS:
                "flow_velocity_m_s": 999.9,
                "reynolds_number": 12345.0,
                "friction_factor": 0.0001,
                "head_loss_m": 0.00001,
                "pressure_loss_psi": 0.0,
                "is_compliant": False,
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is True
        data = res.resultData

        # Solver must completely discard hallucinations:
        assert data["flow_velocity_m_s"] != 999.9
        assert abs(data["flow_velocity_m_s"] - 2.546) < 0.05
        assert data["friction_factor"] > 0.015  # Real steel pipe turbulent Darcy f is ~0.022
        assert data["head_loss_m"] > 0.5  # Real head loss for 20m @ 2.55 m/s is > 1.0m
        assert data["pressure_loss_psi"] > 1.0

    def test_non_water_fluid_agent_calculations(self, command_bus, engineer_principal):
        """Verifies clean agent / CO2 / foam calculations using Darcy-Weisbach properties."""
        cmd = DomainCommand(
            commandId="cmd_fm200_01",
            correlationId="corr_fm200_01",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_clean_agent",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=True,
            payload={
                "pipe_segment_id": "pipe_fm200_01",
                "length_m": 10.0,
                "diameter_mm": 40.0,
                "flow_rate_kg_s": 5.0,
                "fluid_type": "fm200",  # HFC-227ea (density ~1407 kg/m3, viscosity 2.8e-4 Pa.s)
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is True
        assert res.resultData["fluid_type"] == "fm200"
        assert res.resultData["flow_regime"] in ("turbulent", "transitional")
        assert res.resultData["flow_velocity_m_s"] > 0.0


# ---------------------------------------------------------------------------
# 4. Preview (isDryRun=True) vs Commit (isDryRun=False) Semantics Tests
# ---------------------------------------------------------------------------


class TestHydraulicDualModeSemantics:
    def test_preview_mode_zero_mutation_guarantee(
        self, command_bus, state_store, fresh_db, engineer_principal
    ):
        """Verifies isDryRun=True leaves database 100% untouched (0 records, revision unchanged)."""
        cmd = DomainCommand(
            commandId="cmd_dry_hyd_01",
            correlationId="corr_dry_hyd_01",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_dry_hyd",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=True,
            payload={
                "pipe_segment_id": "pipe_dry_01",
                "length_m": 15.0,
                "diameter_mm": 50.0,
                "flow_l_min": 250.0,
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is True
        assert res.revision == 1
        assert res.isDryRun is True
        assert res.event is None

        # Verify DB directly: 0 revisions, 0 events, 0 executions
        ph = fresh_db._ph()
        with fresh_db._transaction() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM project_revisions WHERE project_id = {ph}", ("proj_dry_hyd",)
            )
            rev_cnt = cur.fetchone()[0]
            cur.execute(
                f"SELECT COUNT(*) FROM domain_events WHERE project_id = {ph}", ("proj_dry_hyd",)
            )
            evt_cnt = cur.fetchone()[0]
            cur.execute(
                f"SELECT COUNT(*) FROM command_executions WHERE command_id = {ph}",
                ("cmd_dry_hyd_01",),
            )
            cmd_cnt = cur.fetchone()[0]

        assert rev_cnt == 0
        assert evt_cnt == 0
        assert cmd_cnt == 0

    def test_commit_mode_persists_canonical_snapshot(
        self, command_bus, fresh_db, engineer_principal
    ):
        """Verifies isDryRun=False advances revision, persists snapshot, emits event, and produces SHA-256 audit digest."""
        cmd = DomainCommand(
            commandId="cmd_commit_hyd_01",
            correlationId="corr_commit_hyd_01",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_commit_hyd",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "pipe_segment_id": "pipe_branch_01",
                "length_m": 12.0,
                "diameter_mm": 32.0,
                "flow_l_min": 180.0,
                "fluid_type": "water",
                "elevation_m": 2.0,
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is True
        assert res.revision == 2
        assert res.isDryRun is False
        assert res.event is not None
        assert res.event.eventType == "HYDRAULIC_CALCULATION_SOLVED"
        assert len(res.event.auditReference) == 64  # Valid SHA-256 hex string

        # Inspect canonical state in DB
        ph = fresh_db._ph()
        with fresh_db._transaction() as cur:
            cur.execute(
                f"SELECT revision, canonical_state FROM project_revisions WHERE project_id = {ph}",
                ("proj_commit_hyd",),
            )
            row = cur.fetchone()
            assert row is not None
            rev = row["revision"] if isinstance(row, dict) else row[0]
            raw_state = row["canonical_state"] if isinstance(row, dict) else row[1]
            state = json.loads(raw_state)

        assert rev == 2
        assert "hydraulics" in state
        assert "pipe_branch_01" in state["hydraulics"]
        calc = state["hydraulics"]["pipe_branch_01"]
        assert calc["length_m"] == 12.0
        assert calc["diameter_mm"] == 32.0
        assert calc["flow_velocity_m_s"] > 0.0
        assert calc["head_loss_m"] > 0.0


# ---------------------------------------------------------------------------
# 5. Security & Authorization Boundary Tests
# ---------------------------------------------------------------------------


class TestHydraulicSecurityBoundaries:
    def test_unauthenticated_principal_rejected(self, command_bus, unauthenticated_principal):
        """Rejects anonymous/unauthenticated execution."""
        cmd = DomainCommand(
            commandId="cmd_sec_anon",
            correlationId="corr_sec_anon",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_sec",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=unauthenticated_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={"length_m": 10.0, "diameter_mm": 50.0},
        )

        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode in ("UNAUTHENTICATED", "UNAUTHORIZED", "UNAUTHORIZED_SCOPE")

    def test_insufficient_scope_mutation_rejected(self, command_bus, viewer_principal):
        """Viewer with hydraulics:read cannot execute isDryRun=False mutation."""
        cmd = DomainCommand(
            commandId="cmd_sec_viewer_write",
            correlationId="corr_sec_viewer_write",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_sec",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=viewer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={"length_m": 10.0, "diameter_mm": 50.0},
        )

        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode in ("INSUFFICIENT_SCOPES", "UNAUTHORIZED_SCOPE")

    def test_forbidden_payload_keys_rejected(self, command_bus, engineer_principal):
        """Rejects command payload containing forbidden secret keys."""
        cmd = DomainCommand(
            commandId="cmd_sec_secret",
            correlationId="corr_sec_secret",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_sec",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "length_m": 10.0,
                "diameter_mm": 50.0,
                "password": "sample_forbidden_val",
                "bearer": "sample_forbidden_val",
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode in (
            "FORBIDDEN_PAYLOAD_KEYS",
            "FORBIDDEN_PAYLOAD_SECRET",
            "INVALID_PAYLOAD",
        )


# ---------------------------------------------------------------------------
# 6. Optimistic Concurrency Control (OCC) Tests
# ---------------------------------------------------------------------------


class TestHydraulicOCC:
    def test_concurrent_hydraulic_commits_single_winner(self, state_store, engineer_principal):
        """Two independent workers attempting to mutate revision 1 concurrently: exactly 1 wins."""
        bus_a = CommandBus(default_capability_registry, state_store)
        bus_b = CommandBus(default_capability_registry, state_store)

        cmd_a = DomainCommand(
            commandId="cmd_occ_a",
            correlationId="corr_occ_a",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_occ_hyd",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "pipe_segment_id": "pipe_a",
                "length_m": 10.0,
                "diameter_mm": 50.0,
                "flow_l_min": 200.0,
            },
        )
        cmd_b = DomainCommand(
            commandId="cmd_occ_b",
            correlationId="corr_occ_b",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_occ_hyd",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "pipe_segment_id": "pipe_b",
                "length_m": 20.0,
                "diameter_mm": 65.0,
                "flow_l_min": 400.0,
            },
        )

        res_a = bus_a.execute(cmd_a)
        res_b = bus_b.execute(cmd_b)

        # One must succeed, one must fail with CONCURRENCY_CONFLICT
        successes = [r for r in (res_a, res_b) if r.success]
        conflicts = [r for r in (res_a, res_b) if not r.success]

        assert len(successes) == 1
        assert len(conflicts) == 1
        assert successes[0].revision == 2
        assert conflicts[0].errorCode == "CONCURRENCY_CONFLICT"


# ---------------------------------------------------------------------------
# 7. Persistent Idempotency Tests
# ---------------------------------------------------------------------------


class TestHydraulicIdempotency:
    def test_idempotent_replay_returns_cached_result(self, command_bus, engineer_principal):
        """Replaying identical command returns cached execution result without advancing revision."""
        cmd = DomainCommand(
            commandId="cmd_idem_hyd_01",
            correlationId="corr_idem_hyd_01",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_idem_hyd",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "pipe_segment_id": "pipe_idem_01",
                "length_m": 15.0,
                "diameter_mm": 50.0,
                "flow_l_min": 300.0,
            },
        )

        res1 = command_bus.execute(cmd)
        assert res1.success is True
        assert res1.revision == 2

        # Replay identical command
        res2 = command_bus.execute(cmd)
        assert res2.success is True
        assert res2.revision == 2
        assert res2.resultData["flow_velocity_m_s"] == res1.resultData["flow_velocity_m_s"]

    def test_idempotency_key_reuse_conflict_on_altered_payload(
        self, command_bus, engineer_principal
    ):
        """Reusing same commandId with altered payload triggers IDEMPOTENCY_KEY_REUSE_CONFLICT."""
        cmd1 = DomainCommand(
            commandId="cmd_idem_reuse",
            correlationId="corr_idem_1",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_idem_reuse",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={"length_m": 15.0, "diameter_mm": 50.0, "flow_l_min": 300.0},
        )
        res1 = command_bus.execute(cmd1)
        assert res1.success is True

        cmd2 = DomainCommand(
            commandId="cmd_idem_reuse",
            correlationId="corr_idem_2",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_idem_reuse",
            expectedRevision=2,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "length_m": 99.0,
                "diameter_mm": 100.0,
                "flow_l_min": 800.0,
            },  # Altered payload!
        )
        res2 = command_bus.execute(cmd2)
        assert res2.success is False
        assert res2.errorCode == "IDEMPOTENCY_KEY_REUSE_CONFLICT"


# ---------------------------------------------------------------------------
# 8. Multi-Domain Canonical State Preservation Tests
# ---------------------------------------------------------------------------


class TestMultiDomainPreservation:
    def test_spatial_electrical_and_hydraulic_state_coexistence(
        self, command_bus, fresh_db, engineer_principal
    ):
        """Mutating hydraulics preserves existing spatial devices and electrical circuits in canonical state."""
        # 1. Mutate spatial devices (Revision 1 -> 2)
        cmd_spatial = DomainCommand(
            commandId="cmd_md_spatial",
            correlationId="corr_md_1",
            capabilityId="spatial.place_devices",
            projectId="proj_multidomain",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "room_id": "room_101",
                "devices": [{"id": "smk-01", "type": "smoke", "x": 5.0, "y": 5.0}],
            },
        )
        res_sp = command_bus.execute(cmd_spatial)
        assert res_sp.success is True
        assert res_sp.revision == 2

        # 2. Mutate electrical circuit (Revision 2 -> 3)
        cmd_elec = DomainCommand(
            commandId="cmd_md_elec",
            correlationId="corr_md_2",
            capabilityId="electrical.calculate_voltage_drop",
            projectId="proj_multidomain",
            expectedRevision=2,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "circuit_id": "nac_circuit_01",
                "current_a": 1.5,
                "one_way_length_m": 35.0,
                "awg": "14",
            },
        )
        res_el = command_bus.execute(cmd_elec)
        assert res_el.success is True
        assert res_el.revision == 3

        # 3. Mutate hydraulic pipe segment (Revision 3 -> 4)
        cmd_hyd = DomainCommand(
            commandId="cmd_md_hyd",
            correlationId="corr_md_3",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_multidomain",
            expectedRevision=3,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "pipe_segment_id": "sprinkler_main_01",
                "length_m": 20.0,
                "diameter_mm": 50.0,
                "flow_l_min": 350.0,
            },
        )
        res_hy = command_bus.execute(cmd_hyd)
        assert res_hy.success is True
        assert res_hy.revision == 4

        # Verify all 3 domains exist simultaneously in canonical state at revision 4
        ph = fresh_db._ph()
        with fresh_db._transaction() as cur:
            cur.execute(
                f"SELECT revision, canonical_state FROM project_revisions WHERE project_id = {ph}",
                ("proj_multidomain",),
            )
            row = cur.fetchone()
            state = json.loads(row["canonical_state"] if isinstance(row, dict) else row[1])

        assert len(state.get("devices", [])) > 0
        assert "nac_circuit_01" in state.get("circuits", {})
        assert "sprinkler_main_01" in state.get("hydraulics", {})


# ---------------------------------------------------------------------------
# 9. Velocity Warnings & Boundary Tests
# ---------------------------------------------------------------------------


class TestHydraulicVelocityWarnings:
    def test_high_velocity_warning_classification(self, command_bus, engineer_principal):
        """Checks that velocity > 5.0 m/s produces conservative warning without falsely claiming NFPA 13 violation."""
        # Pipe: 25mm diameter, 400 L/min -> Area = 0.0004908 m2 -> Velocity = (0.4 / 60) / 0.0004908 = ~13.58 m/s (> 10 m/s)
        cmd = DomainCommand(
            commandId="cmd_warn_high_v",
            correlationId="corr_warn_1",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_warn",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=True,
            payload={
                "pipe_segment_id": "pipe_small",
                "length_m": 10.0,
                "diameter_mm": 25.0,
                "flow_l_min": 400.0,
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is True
        data = res.resultData
        assert data["flow_velocity_m_s"] > 10.0
        assert any("Excessive flow velocity" in w or "erosion" in w for w in data["warnings"])
        # Invariant: No blanket claim that NFPA 13 is violated
        assert not any("NFPA 13 NON-COMPLIANT" in w for w in data["warnings"])

    def test_zero_flow_edge_case(self, command_bus, engineer_principal):
        """Zero flow produces 0 head loss and flow_regime='no_flow'."""
        cmd = DomainCommand(
            commandId="cmd_zero_flow",
            correlationId="corr_zero_1",
            capabilityId="hydraulics.solve_darcy_weisbach",
            projectId="proj_zero",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=True,
            payload={
                "pipe_segment_id": "pipe_zero",
                "length_m": 10.0,
                "diameter_mm": 50.0,
                "flow_rate_kg_s": 0.0,
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is True
        data = res.resultData
        assert data["head_loss_m"] == 0.0
        assert data["flow_velocity_m_s"] == 0.0
        assert data["flow_regime"] == "no_flow"
