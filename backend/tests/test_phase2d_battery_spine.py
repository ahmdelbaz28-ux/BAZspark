"""backend/tests/test_phase2d_battery_spine.py — Phase 2D Electrical Battery Sizing Engine Test Suite.

Authoritative Engineering Verification:
1. Context Resolution & Strict Token Budget (<= 1500 tokens)
2. Capability Discovery & Scopes Enforcement
3. Deterministic Engineering Authority & Adversarial LLM Hallucination Rejection
4. Thermal Derating & Chemistry Profiles (VRLA, LiFePO4, NiCad across temperatures)
5. Dual-Mode Semantic Contract (Dry-Run N->N vs Commit N->N+1)
6. Optimistic Concurrency Control (OCC) Multi-Worker Race Conditions
7. Distributed Persistent Idempotency & Collision Detection
8. Security Boundaries (Auth, Scopes, Payload Secrets)
9. Multi-Domain Canonical State Preservation (Spatial, Electrical, Hydraulic, Calculations)
10. Physical Boundary Validation & Low-Temperature Warning Flags
"""

import os
import tempfile
from datetime import UTC, datetime

import pytest

from backend.core.capability_registry import (
    CAP_ELECTRICAL_CALCULATE_BATTERY,
    CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
    CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
    CAP_SPATIAL_PLACE_DEVICES,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
    DomainCommand,
)
from backend.core.context_resolver import ContextResolver
from backend.core.state_store import CommandStateStore
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
def state_store(temp_db):
    return CommandStateStore(db=temp_db)


@pytest.fixture(autouse=True)
def _auto_seed_phase2d_projects(state_store):
    for pid in [
        "proj-adv-bat",
        "proj-thermal",
        "proj-chem",
        "proj-bounds",
        "proj-dry-bat",
        "proj-com-bat",
        "proj-sec-bat",
        "proj-occ-bat",
        "proj-idem-bat",
        "proj-idem-reuse",
        "proj-idem-clash",
        "proj-md-bat",
        "proj-multidomain-all",
    ]:
        state_store.set_project_revision(pid, 1)


@pytest.fixture
def command_bus(state_store):
    return CommandBus(default_capability_registry, state_store)


@pytest.fixture
def engineer_principal():
    return AuthenticatedPrincipal(
        user_id="eng-bat-01",
        email="engineer@fireai.internal",
        role="ENGINEER",
        scopes=[
            "electrical:read",
            "electrical:write",
            "spatial:read",
            "spatial:write",
            "hydraulics:read",
            "hydraulics:write",
        ],
        is_authenticated=True,
    )


@pytest.fixture
def viewer_principal():
    return AuthenticatedPrincipal(
        user_id="viewer-bat-01",
        email="viewer@fireai.internal",
        role="VIEWER",
        scopes=["electrical:read", "spatial:read"],
        is_authenticated=True,
    )


@pytest.fixture
def unauthenticated_principal():
    return AuthenticatedPrincipal(
        user_id="anon",
        email="anon@untrusted.com",
        role="ANONYMOUS",
        scopes=[],
        is_authenticated=False,
    )


class TestBatteryContextResolution:
    """1. Context Resolver Bounding & Token Telemetry Tests"""

    def test_resolve_battery_context_strictly_bounded(self):
        resolver = ContextResolver(token_budget=1500)
        packet = resolver.resolve_battery_context(
            project_id="proj-bat-01",
            panel_id="facp-main",
            revision=1,
            battery_spec={
                "standby_load_amps": 0.85,
                "alarm_load_amps": 3.20,
                "standby_hours": 24.0,
                "alarm_hours": 0.0833,
                "min_temperature_c": 15.0,
                "service_life_years": 5.0,
                "battery_type": "vrla",
                "installed_ah": 55.0,
                "aging_factor": 1.25,
            },
        )

        assert packet.project_id == "proj-bat-01"
        assert packet.panel_id == "facp-main"
        assert packet.revision == 1
        assert packet.token_count <= 1500
        assert packet.is_within_budget is True
        assert packet.telemetry["raw_cad_excluded"] is True
        assert packet.telemetry["geometry_mesh_excluded"] is True
        assert packet.telemetry["whole_project_dump_excluded"] is True
        assert packet.telemetry["measured_tokens"] < 250
        assert packet.telemetry["utilization_pct"] < 20.0

    def test_resolve_battery_context_default_parameters(self):
        resolver = ContextResolver()
        packet = resolver.resolve_battery_context(
            project_id="proj-bat-def",
            panel_id="facp-default",
            revision=1,
            battery_spec=None,
        )

        assert packet.battery_spec["standby_load_amps"] == 0.5
        assert packet.battery_spec["alarm_load_amps"] == 2.0
        assert packet.battery_spec["standby_hours"] == 24.0
        assert packet.battery_spec["battery_type"] == "vrla"
        assert packet.battery_spec["min_temperature_c"] == 20.0
        assert packet.token_count <= 1500


class TestBatteryCapabilityRegistry:
    """2. Capability Discovery & Scopes Verification"""

    def test_capability_registration_metadata(self):
        registry = CapabilityRegistry()
        cap = registry.get(CAP_ELECTRICAL_CALCULATE_BATTERY)
        assert cap is not None
        assert cap.category == "electrical"
        assert cap.risk_class == "ENGINEERING_MUTATION"
        assert cap.required_scopes == ["electrical:write"]

    def test_capability_discovery_with_scopes(self, engineer_principal, viewer_principal):
        registry = CapabilityRegistry()

        # Viewer lacks electrical:write -> cannot discover calculate_battery
        read_only_caps = registry.discover(
            categories=["electrical"],
            scopes=viewer_principal.scopes,
        )
        assert not any(c.capability_id == CAP_ELECTRICAL_CALCULATE_BATTERY for c in read_only_caps)

        # Engineer has electrical:write -> discovers calculate_battery
        write_caps = registry.discover(
            categories=["electrical"],
            scopes=engineer_principal.scopes,
        )
        assert any(c.capability_id == CAP_ELECTRICAL_CALCULATE_BATTERY for c in write_caps)


class TestDeterministicBatteryAuthority:
    """3. Deterministic Engineering Authority & Adversarial Rejection"""

    def test_authoritative_solver_overrides_llm_hallucination(
        self, command_bus, engineer_principal
    ):
        """Adversarial Test: Fabricated client/LLM values must be completely ignored."""
        adversarial_payload = {
            "panel_id": "facp-adv-01",
            "standby_load_amps": 1.0,
            "alarm_load_amps": 4.0,
            "standby_hours": 24.0,
            "alarm_hours": 5.0 / 60.0,
            "min_temperature_c": 20.0,
            "installed_ah": 55.0,
            # Injected fake numbers
            "required_ah": 0.5,
            "usable_ah": 999.0,
            "is_adequate": True,
            "temperature_derating": 1.50,
            "aging_derating": 1.50,
        }

        cmd = DomainCommand(
            commandId="cmd-adv-bat-01",
            correlationId="corr-adv-01",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-adv-bat",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=True,
            payload=adversarial_payload,
        )

        res = command_bus.execute(cmd)
        assert res.success is True
        data = res.resultData

        # Authoritative base capacity: 1.0*24 + 4.0*(5/60) = 24.0 + 0.3333 = 24.3333 Ah
        assert abs(data["base_capacity_ah"] - 24.3333) < 0.05
        # Authoritative required Ah must be calculated deterministically (~34.5 Ah)
        assert data["required_ah"] > 30.0
        assert data["required_ah"] != 0.5  # Fabricated value overridden
        assert data["temperature_derating"] <= 1.0  # Cannot exceed 1.0

    def test_thermal_deratings_across_temperatures(self, command_bus, engineer_principal):
        temps_and_expected = [
            (-20.0, 0.60),  # Below minimum data point -> capped at 0.60
            (0.0, 0.72),  # Freezing point
            (20.0, 0.95),  # Indoor typical
            (25.0, 1.00),  # Rated reference temp
        ]

        for temp_c, expected_factor in temps_and_expected:
            cmd = DomainCommand(
                commandId=f"cmd-temp-{temp_c}",
                correlationId=f"corr-temp-{temp_c}",
                capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
                projectId="proj-thermal",
                expectedRevision=1,
                timestamp=datetime.now(UTC).isoformat(),
                principal=engineer_principal,
                isDryRun=True,
                payload={
                    "panel_id": "facp-thermal",
                    "standby_load_amps": 0.5,
                    "alarm_load_amps": 2.0,
                    "min_temperature_c": temp_c,
                    "battery_type": "vrla",
                },
            )
            res = command_bus.execute(cmd)
            assert res.success is True
            assert abs(res.resultData["temperature_derating"] - expected_factor) < 0.02

    def test_chemistry_specific_warnings(self, command_bus, engineer_principal):
        # LiFePO4 below 0C warning
        cmd_lifepo4 = DomainCommand(
            commandId="cmd-lifepo4-cold",
            correlationId="corr-lifepo4",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-chem",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=True,
            payload={
                "panel_id": "facp-lifepo4",
                "standby_load_amps": 0.5,
                "alarm_load_amps": 2.0,
                "min_temperature_c": -5.0,
                "battery_type": "lifepo4",
            },
        )
        res_lifepo4 = command_bus.execute(cmd_lifepo4)
        assert res_lifepo4.success is True
        assert any("LiFePO4" in w for w in res_lifepo4.resultData["warnings"])

        # VRLA below -10C warning
        cmd_vrla = DomainCommand(
            commandId="cmd-vrla-cold",
            correlationId="corr-vrla",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-chem",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=True,
            payload={
                "panel_id": "facp-vrla",
                "standby_load_amps": 0.5,
                "alarm_load_amps": 2.0,
                "min_temperature_c": -15.0,
                "battery_type": "vrla",
            },
        )
        res_vrla = command_bus.execute(cmd_vrla)
        assert res_vrla.success is True
        assert any("VRLA" in w for w in res_vrla.resultData["warnings"])

    def test_physical_boundary_rejection(self, command_bus, engineer_principal):
        # Negative load current
        cmd_neg_curr = DomainCommand(
            commandId="cmd-neg-curr",
            correlationId="corr-neg",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-bounds",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=True,
            payload={
                "panel_id": "facp-01",
                "standby_load_amps": -1.5,
                "alarm_load_amps": 2.0,
            },
        )
        res_neg_curr = command_bus.execute(cmd_neg_curr)
        assert res_neg_curr.success is False
        assert res_neg_curr.errorCode == "HANDLER_EXECUTION_FAILED"

        # Temperature outside physical range (-40C to 70C)
        cmd_extreme_temp = DomainCommand(
            commandId="cmd-extreme-temp",
            correlationId="corr-temp",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-bounds",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=True,
            payload={
                "panel_id": "facp-01",
                "standby_load_amps": 0.5,
                "alarm_load_amps": 2.0,
                "min_temperature_c": 120.0,
            },
        )
        res_extreme_temp = command_bus.execute(cmd_extreme_temp)
        assert res_extreme_temp.success is False
        assert "outside physical operating boundary" in res_extreme_temp.errorMessage


class TestBatteryDualModeSemantics:
    """4. Dual-Mode Semantic Contract (Dry-Run N->N vs Commit N->N+1)"""

    def test_preview_mode_zero_mutation_guarantee(self, command_bus, engineer_principal):
        cmd = DomainCommand(
            commandId="cmd-dryrun-bat-01",
            correlationId="corr-dry-01",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-dry-bat",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=True,
            payload={
                "panel_id": "facp-preview",
                "standby_load_amps": 0.6,
                "alarm_load_amps": 2.5,
                "installed_ah": 33.0,
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is True
        assert res.isDryRun is True
        assert res.revision == 1
        assert res.event is None

        # Verify zero database mutation
        state = command_bus.state_store.get_canonical_state("proj-dry-bat")
        assert "calculations" not in state or "battery" not in state.get("calculations", {})
        assert command_bus.get_project_revision("proj-dry-bat") == 1

    def test_commit_mode_persists_canonical_snapshot(self, command_bus, engineer_principal):
        cmd = DomainCommand(
            commandId="cmd-commit-bat-01",
            correlationId="corr-com-01",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-com-bat",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload={
                "panel_id": "facp-com-01",
                "standby_load_amps": 0.75,
                "alarm_load_amps": 3.0,
                "installed_ah": 55.0,
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is True
        assert res.isDryRun is False
        assert res.revision == 2
        assert res.event is not None
        assert res.event.eventType == "BATTERY_CALCULATION_SOLVED"
        assert len(res.event.auditReference) == 64  # Valid SHA-256

        # Canonical state verification
        state = command_bus.state_store.get_canonical_state("proj-com-bat")
        assert state["revision"] == 2
        assert "calculations" in state
        assert "battery" in state["calculations"]
        bat_entry = state["calculations"]["battery"]["facp-com-01"]
        assert bat_entry["panel_id"] == "facp-com-01"
        assert bat_entry["installed_ah"] == 55.0
        assert bat_entry["required_ah"] > 0


class TestBatterySecurityBoundaries:
    """5. Security Boundaries (Auth, Scopes, Payload Secrets)"""

    def test_unauthenticated_principal_rejected(self, command_bus, unauthenticated_principal):
        cmd = DomainCommand(
            commandId="cmd-sec-anon",
            correlationId="corr-anon",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-sec-bat",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=unauthenticated_principal,
            isDryRun=True,
            payload={"panel_id": "facp-01", "standby_load_amps": 0.5, "alarm_load_amps": 2.0},
        )

        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode == "UNAUTHENTICATED_ACCESS"

    def test_insufficient_scope_mutation_rejected(self, command_bus, viewer_principal):
        cmd = DomainCommand(
            commandId="cmd-sec-scope",
            correlationId="corr-scope",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-sec-bat",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=viewer_principal,
            isDryRun=False,  # Needs electrical:write
            payload={"panel_id": "facp-01", "standby_load_amps": 0.5, "alarm_load_amps": 2.0},
        )

        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode == "UNAUTHORIZED_SCOPE"

    def test_forbidden_payload_keys_rejected(self, command_bus, engineer_principal):
        cmd = DomainCommand(
            commandId="cmd-sec-secret",
            correlationId="corr-secret",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-sec-bat",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=True,
            payload={
                "panel_id": "facp-01",
                "standby_load_amps": 0.5,
                "alarm_load_amps": 2.0,
                "api_key": "secret_leak_123",
            },
        )

        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode == "FORBIDDEN_PAYLOAD_SECRET"


class TestBatteryOCC:
    """6. Optimistic Concurrency Control (OCC) Multi-Worker Verification"""

    def test_concurrent_battery_commits_single_winner(self, temp_db):
        """Worker A and Worker B race on expectedRevision=1."""
        bus_a = CommandBus(default_capability_registry, CommandStateStore(temp_db))
        bus_b = CommandBus(default_capability_registry, CommandStateStore(temp_db))

        worker_a = AuthenticatedPrincipal(
            "worker-a", "a@fireai.internal", "ENGINEER", ["electrical:write"]
        )
        worker_b = AuthenticatedPrincipal(
            "worker-b", "b@fireai.internal", "ENGINEER", ["electrical:write"]
        )

        cmd_a = DomainCommand(
            commandId="cmd-occ-a",
            correlationId="corr-occ-a",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-occ-bat",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=worker_a,
            isDryRun=False,
            payload={"panel_id": "facp-01", "standby_load_amps": 0.5, "alarm_load_amps": 2.0},
        )

        cmd_b = DomainCommand(
            commandId="cmd-occ-b",
            correlationId="corr-occ-b",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-occ-bat",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=worker_b,
            isDryRun=False,
            payload={"panel_id": "facp-01", "standby_load_amps": 0.8, "alarm_load_amps": 3.0},
        )

        res_a = bus_a.execute(cmd_a)
        assert res_a.success is True
        assert res_a.revision == 2

        res_b = bus_b.execute(cmd_b)
        assert res_b.success is False
        assert res_b.errorCode == "CONCURRENCY_CONFLICT"
        assert res_b.revision == 2


class TestBatteryIdempotency:
    """7. Distributed Persistent Idempotency & Collision Detection"""

    def test_idempotent_replay_returns_cached_result(self, command_bus, engineer_principal):
        payload = {"panel_id": "facp-01", "standby_load_amps": 0.6, "alarm_load_amps": 2.5}
        cmd = DomainCommand(
            commandId="cmd-idem-bat-01",
            correlationId="corr-idem-01",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-idem-bat",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload=payload,
        )

        res1 = command_bus.execute(cmd)
        assert res1.success is True
        assert res1.revision == 2

        # Replay identical commandId and payload
        res2 = command_bus.execute(cmd)
        assert res2.success is True
        assert res2.revision == 2
        assert res2.resultData["required_ah"] == res1.resultData["required_ah"]

    def test_idempotency_key_reuse_conflict_on_altered_payload(
        self, command_bus, engineer_principal
    ):
        cmd1 = DomainCommand(
            commandId="cmd-idem-clash-01",
            correlationId="corr-idem-01",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-idem-clash",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload={"panel_id": "facp-01", "standby_load_amps": 0.5, "alarm_load_amps": 2.0},
        )

        res1 = command_bus.execute(cmd1)
        assert res1.success is True

        # Reused commandId with altered payload
        cmd2 = DomainCommand(
            commandId="cmd-idem-clash-01",
            correlationId="corr-idem-02",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-idem-clash",
            expectedRevision=2,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload={"panel_id": "facp-01", "standby_load_amps": 1.5, "alarm_load_amps": 6.0},
        )

        res2 = command_bus.execute(cmd2)
        assert res2.success is False
        assert res2.errorCode == "IDEMPOTENCY_KEY_REUSE_CONFLICT"


class TestMultiDomainPreservation:
    """8. Multi-Domain Coexistence (Spatial, Electrical, Hydraulic, Calculations)"""

    def test_spatial_electrical_hydraulic_and_battery_state_coexistence(
        self, command_bus, engineer_principal
    ):
        # 1. Spatial Placement (Rev 1 -> 2)
        cmd_spatial = DomainCommand(
            commandId="cmd-multi-spatial",
            correlationId="corr-multi-1",
            capabilityId=CAP_SPATIAL_PLACE_DEVICES,
            projectId="proj-multidomain-all",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload={"room_id": "main-hall", "width_m": 12.0, "length_m": 18.0},
        )
        res_sp = command_bus.execute(cmd_spatial)
        assert res_sp.success is True
        assert res_sp.revision == 2

        # 2. Voltage Drop Calculation (Rev 2 -> 3)
        cmd_elec = DomainCommand(
            commandId="cmd-multi-elec",
            correlationId="corr-multi-2",
            capabilityId=CAP_ELECTRICAL_CALCULATE_VOLTAGE_DROP,
            projectId="proj-multidomain-all",
            expectedRevision=2,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload={
                "circuit_id": "nac-01",
                "current_a": 2.5,
                "one_way_length_m": 45.0,
                "awg": "14",
            },
        )
        res_el = command_bus.execute(cmd_elec)
        assert res_el.success is True
        assert res_el.revision == 3

        # 3. Hydraulic Darcy-Weisbach Calculation (Rev 3 -> 4)
        cmd_hyd = DomainCommand(
            commandId="cmd-multi-hyd",
            correlationId="corr-multi-3",
            capabilityId=CAP_HYDRAULICS_SOLVE_DARCY_WEISBACH,
            projectId="proj-multidomain-all",
            expectedRevision=3,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload={
                "pipe_segment_id": "pipe-01",
                "length_m": 30.0,
                "diameter_mm": 65.0,
                "flow_l_min": 350.0,
            },
        )
        res_hy = command_bus.execute(cmd_hyd)
        assert res_hy.success is True
        assert res_hy.revision == 4

        # 4. Battery Capacity Sizing Calculation (Rev 4 -> 5)
        cmd_bat = DomainCommand(
            commandId="cmd-multi-bat",
            correlationId="corr-multi-4",
            capabilityId=CAP_ELECTRICAL_CALCULATE_BATTERY,
            projectId="proj-multidomain-all",
            expectedRevision=4,
            timestamp=datetime.now(UTC).isoformat(),
            principal=engineer_principal,
            isDryRun=False,
            payload={
                "panel_id": "facp-01",
                "standby_load_amps": 0.8,
                "alarm_load_amps": 3.5,
                "installed_ah": 55.0,
            },
        )
        res_bat = command_bus.execute(cmd_bat)
        assert res_bat.success is True
        assert res_bat.revision == 5

        # Verify all 4 domains coexist in canonical state revision 5
        final_state = command_bus.state_store.get_canonical_state("proj-multidomain-all")
        assert final_state["revision"] == 5
        assert len(final_state["devices"]) > 0
        assert "nac-01" in final_state["circuits"]
        assert "pipe-01" in final_state["hydraulics"]
        assert "facp-01" in final_state["calculations"]["battery"]
