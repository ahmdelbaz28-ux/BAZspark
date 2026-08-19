"""backend/tests/test_phase2b_electrical_spine.py — Phase 2B Vertical Slice C Tests.

Validates the AI Operating Spine across a second engineering domain:
  - Capability: electrical.calculate_voltage_drop
  - Standards: NFPA 72-2022 §27.4.1.2 & NEC Chapter 9 Table 8
  - Deterministic Authority, Bounded Context (<=1500 tokens), OCC, Idempotency,
    Transaction Rollback, Security, and Verification Correctness.
"""

from __future__ import annotations

import math
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
    default_context_resolver,
    estimate_token_count,
)
from backend.core.state_store import CommandStateStore
from backend.database import Database
from fireai.core.voltage_drop import (
    calculate_voltage_drop,
    recommend_wire_gauge,
)


@pytest.fixture
def fresh_db(tmp_path: Any) -> Database:
    """Create an isolated, temporary SQLite database for test reproducibility."""
    db_file = str(tmp_path / f"test_phase2b_{uuid.uuid4().hex[:8]}.db")
    return Database(db_file)


@pytest.fixture
def state_store(fresh_db: Database) -> CommandStateStore:
    """Isolated state store for test execution."""
    return CommandStateStore(fresh_db)


@pytest.fixture
def command_bus(state_store: CommandStateStore) -> CommandBus:
    """CommandBus initialized with test state store and default capability registry."""
    return CommandBus(default_capability_registry, state_store)


@pytest.fixture
def authorized_principal() -> AuthenticatedPrincipal:
    """Principal with electrical and spatial write scopes."""
    return AuthenticatedPrincipal(
        user_id="eng-alice",
        email="alice@bazspark.com",
        scopes=["electrical:read", "electrical:write", "spatial:write"],
        role="senior_engineer",
        is_authenticated=True,
    )


@pytest.fixture
def read_only_principal() -> AuthenticatedPrincipal:
    """Principal with only read scopes."""
    return AuthenticatedPrincipal(
        user_id="auditor-bob",
        email="bob@bazspark.com",
        scopes=["electrical:read", "compliance:read"],
        role="viewer",
        is_authenticated=True,
    )


# ============================================================================
# 1. Capability Discovery Tests
# ============================================================================
class TestCapabilityDiscovery:
    def test_discover_electrical_capability(self, authorized_principal: AuthenticatedPrincipal) -> None:
        registry = default_capability_registry
        caps = registry.discover(categories=["electrical"], scopes=authorized_principal.scopes)
        assert len(caps) == 1
        assert caps[0].capability_id == "electrical.calculate_voltage_drop"
        assert caps[0].category == "electrical"
        assert caps[0].risk_class == "ENGINEERING_MUTATION"
        assert "electrical:write" in caps[0].required_scopes

    def test_filter_excludes_unrelated_categories(self, authorized_principal: AuthenticatedPrincipal) -> None:
        registry = default_capability_registry
        caps = registry.discover(categories=["spatial"], scopes=authorized_principal.scopes)
        for cap in caps:
            assert cap.category == "spatial"
            assert cap.capability_id != "electrical.calculate_voltage_drop"

    def test_scope_enforcement_in_discovery(self, read_only_principal: AuthenticatedPrincipal) -> None:
        registry = default_capability_registry
        # Viewer lacks electrical:write -> should not discover mutation capability
        caps = registry.discover(categories=["electrical"], scopes=read_only_principal.scopes)
        assert len(caps) == 0


# ============================================================================
# 2. Context Boundary & Token Budget Tests
# ============================================================================
class TestContextBoundary:
    def test_circuit_context_strictly_within_budget(self) -> None:
        resolver = default_context_resolver
        packet = resolver.resolve_circuit_context(
            project_id="proj-alpha",
            circuit_id="nac-01",
            revision=1,
            circuit_spec={
                "current_a": 1.75,
                "one_way_length_m": 45.0,
                "awg": "14",
                "nominal_voltage": 24.0,
                "temperature_c": 75.0,
            },
            connected_devices=[{"id": f"dev-{i}", "candela": 75} for i in range(20)],
        )

        assert packet.is_within_budget is True
        assert packet.token_count <= 1500
        assert packet.token_count < 300  # Highly compact, minimal circuit packet
        assert packet.telemetry["raw_cad_excluded"] is True
        assert packet.telemetry["whole_project_dump_excluded"] is True

    def test_token_counter_accuracy(self) -> None:
        payload = {
            "circuit_id": "nac-01",
            "current_a": 1.5,
            "one_way_length_m": 30.0,
            "awg": "14",
        }
        tokens = estimate_token_count(payload)
        assert 15 <= tokens <= 50


# ============================================================================
# 3. Command Contract & Schema Validation Tests
# ============================================================================
class TestCommandContract:
    def test_valid_electrical_command_executes(
        self, command_bus: CommandBus, authorized_principal: AuthenticatedPrincipal
    ) -> None:
        cmd = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-101",
            capabilityId="electrical.calculate_voltage_drop",
            projectId="proj-contract-test",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            isDryRun=False,
            payload={
                "circuit_id": "nac-circuit-01",
                "current_a": 1.2,
                "one_way_length_m": 25.0,
                "awg": "14",
                "nominal_voltage": 24.0,
            },
        )

        result = command_bus.execute(cmd)
        assert result.success is True
        assert result.errorCode is None
        assert result.resultData["circuit_id"] == "nac-circuit-01"
        assert result.resultData["is_compliant"] is True
        assert result.resultData["voltage_drop_v"] > 0
        assert result.resultData["recommended_awg"] == "14"
        assert result.revision == 2
        assert result.event is not None
        assert result.event.eventType == "VOLTAGE_DROP_CALCULATED"

    def test_unknown_capability_rejected(
        self, command_bus: CommandBus, authorized_principal: AuthenticatedPrincipal
    ) -> None:
        cmd = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-102",
            capabilityId="electrical.nonexistent_calc",
            projectId="proj-invalid",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={},
        )
        result = command_bus.execute(cmd)
        assert result.success is False
        assert result.errorCode == "UNKNOWN_CAPABILITY"


# ============================================================================
# 4. Deterministic Engineering Authority Tests
# ============================================================================
class TestDeterministicAuthority:
    def test_llm_cannot_override_deterministic_voltage_drop(
        self, command_bus: CommandBus, authorized_principal: AuthenticatedPrincipal
    ) -> None:
        """Verify authoritative result comes strictly from Ohm's law & NEC tables,

        even if an adversarial caller injects fake 'voltage_drop_v' or 'is_compliant'.
        """
        fake_llm_payload = {
            "circuit_id": "nac-circuit-spoofed",
            "current_a": 3.0,  # 3A on 100m AWG 14 -> V_drop = 3 * 2 * 100 * 0.0103 = 6.18V (25.75% drop -> Non-compliant)
            "one_way_length_m": 100.0,
            "awg": "14",
            "nominal_voltage": 24.0,
            # Injected hallucinated/fake claims by an AI agent:
            "voltage_drop_v": 0.05,
            "voltage_drop_pct": 0.2,
            "is_compliant": True,
        }

        cmd = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-det-auth",
            capabilityId="electrical.calculate_voltage_drop",
            projectId="proj-det-auth",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            payload=fake_llm_payload,
        )

        result = command_bus.execute(cmd)
        assert result.success is True
        # Deterministic engine OVERRIDES fake LLM claims:
        # True physics: 3A * 200m * 0.0103 ohm/m = 6.18V
        assert math.isclose(result.resultData["voltage_drop_v"], 6.18, rel_tol=1e-2)
        assert result.resultData["is_compliant"] is False  # 25.75% > 10% max drop!
        assert result.resultData["recommended_awg"] in ("8", "6", "4")  # Safe recommendation
        assert len(result.resultData["violations"]) > 0


# ============================================================================
# 5. Security & Scope Boundary Tests
# ============================================================================
class TestSecurityBoundaries:
    def test_unauthenticated_request_rejected(self, command_bus: CommandBus) -> None:
        unauth_principal = AuthenticatedPrincipal(
            user_id="anon",
            email="anon@bazspark.com",
            scopes=["electrical:write"],
            role="anonymous",
            is_authenticated=False,
        )
        cmd = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-sec-1",
            capabilityId="electrical.calculate_voltage_drop",
            projectId="proj-sec",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=unauth_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={"current_a": 1.0, "one_way_length_m": 20.0, "awg": "14"},
        )
        result = command_bus.execute(cmd)
        assert result.success is False
        assert result.errorCode == "UNAUTHENTICATED_ACCESS"

    def test_insufficient_scope_rejected(
        self, command_bus: CommandBus, read_only_principal: AuthenticatedPrincipal
    ) -> None:
        cmd = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-sec-2",
            capabilityId="electrical.calculate_voltage_drop",
            projectId="proj-sec",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=read_only_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={"current_a": 1.0, "one_way_length_m": 20.0, "awg": "14"},
        )
        result = command_bus.execute(cmd)
        assert result.success is False
        assert result.errorCode == "UNAUTHORIZED_SCOPE"

    def test_payload_secrets_rejected(
        self, command_bus: CommandBus, authorized_principal: AuthenticatedPrincipal
    ) -> None:
        cmd = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-sec-3",
            capabilityId="electrical.calculate_voltage_drop",
            projectId="proj-sec",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={
                "current_a": 1.0,
                "one_way_length_m": 20.0,
                "awg": "14",
                "api_key": "secret_token_12345",
            },
        )
        result = command_bus.execute(cmd)
        assert result.success is False
        assert result.errorCode == "FORBIDDEN_PAYLOAD_SECRET"


# ============================================================================
# 6. Optimistic Concurrency Control (OCC) Tests
# ============================================================================
class TestOCC:
    def test_concurrent_electrical_commands_race_condition(
        self, command_bus: CommandBus, authorized_principal: AuthenticatedPrincipal
    ) -> None:
        project_id = "proj-occ-race"

        cmd1 = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-race-1",
            capabilityId="electrical.calculate_voltage_drop",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={"circuit_id": "nac-01", "current_a": 1.0, "one_way_length_m": 20.0, "awg": "14"},
        )

        cmd2 = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-race-2",
            capabilityId="electrical.calculate_voltage_drop",
            projectId=project_id,
            expectedRevision=1,  # Stale revision after cmd1 executes
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={"circuit_id": "nac-02", "current_a": 2.0, "one_way_length_m": 35.0, "awg": "12"},
        )

        res1 = command_bus.execute(cmd1)
        assert res1.success is True
        assert res1.revision == 2

        res2 = command_bus.execute(cmd2)
        assert res2.success is False
        assert res2.errorCode == "CONCURRENCY_CONFLICT"
        assert res2.revision == 2


# ============================================================================
# 7. Distributed Idempotency & Collision Tests
# ============================================================================
class TestIdempotency:
    def test_idempotent_replay_returns_cached_result(
        self, command_bus: CommandBus, authorized_principal: AuthenticatedPrincipal
    ) -> None:
        command_id = f"cmd-idem-{uuid.uuid4().hex[:10]}"
        cmd = DomainCommand(
            commandId=command_id,
            correlationId="corr-idem-1",
            capabilityId="electrical.calculate_voltage_drop",
            projectId="proj-idem",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={"circuit_id": "nac-01", "current_a": 1.5, "one_way_length_m": 30.0, "awg": "14"},
        )

        res1 = command_bus.execute(cmd)
        assert res1.success is True
        assert res1.revision == 2

        # Replay same commandId with same payload -> must return cached result without double increment
        res2 = command_bus.execute(cmd)
        assert res2.success is True
        assert res2.commandId == command_id
        assert res2.revision == 2
        assert command_bus.get_project_revision("proj-idem") == 2

    def test_idempotency_key_reuse_conflict(
        self, command_bus: CommandBus, authorized_principal: AuthenticatedPrincipal
    ) -> None:
        command_id = f"cmd-idem-collision-{uuid.uuid4().hex[:10]}"
        cmd1 = DomainCommand(
            commandId=command_id,
            correlationId="corr-idem-2",
            capabilityId="electrical.calculate_voltage_drop",
            projectId="proj-idem-collision",
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={"circuit_id": "nac-01", "current_a": 1.0, "one_way_length_m": 20.0, "awg": "14"},
        )
        res1 = command_bus.execute(cmd1)
        assert res1.success is True

        # Reusing same commandId with different payload
        cmd2 = DomainCommand(
            commandId=command_id,
            correlationId="corr-idem-3",
            capabilityId="electrical.calculate_voltage_drop",
            projectId="proj-idem-collision",
            expectedRevision=2,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={"circuit_id": "nac-01", "current_a": 2.5, "one_way_length_m": 60.0, "awg": "10"},
        )
        res2 = command_bus.execute(cmd2)
        assert res2.success is False
        assert res2.errorCode == "IDEMPOTENCY_KEY_REUSE_CONFLICT"


# ============================================================================
# 8. Transaction Isolation & Canonical State Preservation Tests
# ============================================================================
class TestTransactionPersistence:
    def test_circuit_state_persisted_alongside_devices(
        self, command_bus: CommandBus, authorized_principal: AuthenticatedPrincipal
    ) -> None:
        project_id = "proj-multi-domain"

        # 1. Place devices (Spatial domain)
        cmd_spatial = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-multi-1",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="MEDIUM",
            payload={"room_id": "room-101", "width_m": 8.0, "length_m": 12.0},
        )
        res_spatial = command_bus.execute(cmd_spatial)
        assert res_spatial.success is True
        assert res_spatial.revision == 2

        # 2. Calculate circuit voltage drop (Electrical domain)
        cmd_electrical = DomainCommand(
            commandId=f"cmd-{uuid.uuid4().hex[:12]}",
            correlationId="corr-multi-2",
            capabilityId="electrical.calculate_voltage_drop",
            projectId=project_id,
            expectedRevision=2,
            timestamp=datetime.now(UTC).isoformat(),
            principal=authorized_principal,
            riskClass="ENGINEERING_MUTATION",
            payload={"circuit_id": "nac-circuit-01", "current_a": 1.2, "one_way_length_m": 25.0, "awg": "14"},
        )
        res_electrical = command_bus.execute(cmd_electrical)
        assert res_electrical.success is True
        assert res_electrical.revision == 3

        # 3. Verify canonical state preserves BOTH spatial devices and electrical circuits
        state = command_bus.get_canonical_state(project_id)
        assert len(state.get("devices", [])) > 0
        assert "nac-circuit-01" in state.get("circuits", {})
        assert state["circuits"]["nac-circuit-01"]["is_compliant"] is True
        assert state["revision"] == 3


# ============================================================================
# 9. Verification Correctness & Edge Cases
# ============================================================================
class TestVerificationCorrectness:
    def test_normal_compliant_circuit(self) -> None:
        res = calculate_voltage_drop(current_a=1.0, one_way_length_m=20.0, awg="14")
        assert res["is_compliant"] is True
        assert res["voltage_drop_pct"] < 10.0

    def test_boundary_10pct_drop(self) -> None:
        # At 24V, 10% is 2.4V max drop
        # R_total = 2.4 / 1.0 = 2.4 ohm -> L = 2.4 / (2 * 0.0103) = ~116.5m
        res_pass = calculate_voltage_drop(current_a=1.0, one_way_length_m=110.0, awg="14")
        assert res_pass["is_compliant"] is True

        res_fail = calculate_voltage_drop(current_a=1.0, one_way_length_m=130.0, awg="14")
        assert res_fail["is_compliant"] is False
        rec = recommend_wire_gauge(current_a=1.0, one_way_length_m=130.0)
        assert rec["is_compliant"] is True
        assert rec["recommended_awg"] in ("12", "10")

    def test_invalid_parameters_raise_cleanly(self) -> None:
        with pytest.raises(ValueError, match="must be >= 0"):
            calculate_voltage_drop(current_a=-1.0, one_way_length_m=10.0)

        with pytest.raises(ValueError, match="must be a finite number"):
            calculate_voltage_drop(current_a=float("nan"), one_way_length_m=10.0)

        with pytest.raises(ValueError, match="Unknown AWG gauge"):
            calculate_voltage_drop(current_a=1.0, one_way_length_m=10.0, awg="99")
