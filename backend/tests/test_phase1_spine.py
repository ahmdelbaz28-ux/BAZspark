"""backend/tests/test_phase1_spine.py — Phase 1 Architectural Spine Vertical Slice Test Suite.

Validates the complete frozen architecture:
- Command Contract & Schema Validation
- Security Boundary & Secret Leakage Prevention
- Optimistic Concurrency Control (OCC)
- Context Resolution & Token Budgeting (<= 1,500 tokens)
- Dynamic Capability Discovery
- End-to-End Vertical Slice B (Dry-run -> Preview -> Approval -> Commit -> Audit)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
import pytest

from backend.core.capability_registry import (
    CapabilityDefinition,
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
    DomainCommand,
    default_command_bus,
)
from backend.core.context_resolver import (
    BoundedContextPacket,
    ContextResolver,
    default_context_resolver,
    estimate_token_count,
)


@pytest.fixture
def test_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="engineer-user-01",
        email="engineer@bazspark.com",
        role="engineer",
        scopes=["spatial:write", "compliance:read"],
        is_authenticated=True,
    )


@pytest.fixture
def readonly_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="viewer-user-02",
        email="viewer@bazspark.com",
        role="viewer",
        scopes=["compliance:read"],  # lacks spatial:write
        is_authenticated=True,
    )


@pytest.fixture
def unauthenticated_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="anon",
        email="anon@unknown.com",
        role="anonymous",
        scopes=[],
        is_authenticated=False,
    )


@pytest.fixture
def command_bus() -> CommandBus:
    return CommandBus(default_capability_registry)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. COMMAND CONTRACT & VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCommandContract:
    def test_valid_command_execution(self, command_bus: CommandBus, test_principal: AuthenticatedPrincipal):
        cmd = DomainCommand(
            commandId="cmd-test-valid-01",
            correlationId="corr-01",
            capabilityId="spatial.place_devices",
            projectId="proj-contract-01",
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            riskClass="MEDIUM",
            isDryRun=False,
            payload={
                "room_id": "room-north-wing",
                "width_m": 12.0,
                "length_m": 18.0,
                "ceiling_height_m": 3.0,
                "detector_type": "smoke",
            },
        )
        res = command_bus.execute(cmd)
        assert res.success is True
        assert res.revision == 2
        assert res.errorCode is None
        assert len(res.resultData.get("devices", [])) > 0
        assert res.event is not None
        assert res.event.eventType == "DEVICES_PLACED"

    def test_unknown_capability_rejection(self, command_bus: CommandBus, test_principal: AuthenticatedPrincipal):
        cmd = DomainCommand(
            commandId="cmd-test-unknown-01",
            correlationId="corr-02",
            capabilityId="unregistered.arbitrary_tool",
            projectId="proj-contract-02",
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"action": "mutate_database"},
        )
        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode == "UNKNOWN_CAPABILITY"
        assert "not registered" in (res.errorMessage or "")

    def test_idempotency_duplicate_command_id(self, command_bus: CommandBus, test_principal: AuthenticatedPrincipal):
        cmd = DomainCommand(
            commandId="cmd-idempotent-unique-01",
            correlationId="corr-03",
            capabilityId="spatial.place_devices",
            projectId="proj-idempotent-01",
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-A", "width_m": 10.0, "length_m": 10.0},
        )
        res1 = command_bus.execute(cmd)
        assert res1.success is True
        assert res1.revision == 2

        # Replaying identical commandId must return cached result and NOT increment revision again
        res2 = command_bus.execute(cmd)
        assert res2.success is True
        assert res2.revision == 2
        assert command_bus.get_project_revision("proj-idempotent-01") == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SECURITY BOUNDARY & SECRET LEAKAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecurityBoundary:
    def test_unauthenticated_principal_rejected(
        self, command_bus: CommandBus, unauthenticated_principal: AuthenticatedPrincipal
    ):
        cmd = DomainCommand(
            commandId="cmd-unauth-01",
            correlationId="corr-unauth",
            capabilityId="spatial.place_devices",
            projectId="proj-sec-01",
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=unauthenticated_principal,
            isDryRun=False,
            payload={"room_id": "room-sec", "width_m": 10.0, "length_m": 10.0},
        )
        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode == "UNAUTHENTICATED_ACCESS"

    def test_unauthorized_scope_rejected(
        self, command_bus: CommandBus, readonly_principal: AuthenticatedPrincipal
    ):
        cmd = DomainCommand(
            commandId="cmd-unauthz-01",
            correlationId="corr-unauthz",
            capabilityId="spatial.place_devices",  # requires spatial:write
            projectId="proj-sec-02",
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=readonly_principal,
            isDryRun=False,
            payload={"room_id": "room-sec", "width_m": 10.0, "length_m": 10.0},
        )
        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode == "UNAUTHORIZED_SCOPE"
        assert "spatial:write" in (res.errorMessage or "")

    def test_sensitive_secret_leakage_in_payload_rejected(
        self, command_bus: CommandBus, test_principal: AuthenticatedPrincipal
    ):
        cmd = DomainCommand(
            commandId="cmd-leak-01",
            correlationId="corr-leak",
            capabilityId="spatial.place_devices",
            projectId="proj-sec-03",
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={
                "room_id": "room-leak",
                "width_m": 10.0,
                "length_m": 10.0,
                "bearer_token": "secret_jwt_token_12345",
            },
        )
        res = command_bus.execute(cmd)
        assert res.success is False
        assert res.errorCode == "FORBIDDEN_PAYLOAD_SECRET"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. OPTIMISTIC CONCURRENCY CONTROL (OCC) TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestOptimisticConcurrencyControl:
    def test_stale_revision_rejected_concurrency_conflict(
        self, command_bus: CommandBus, test_principal: AuthenticatedPrincipal
    ):
        project_id = "proj-occ-01"
        command_bus.set_project_revision(project_id, 3)

        # AI planned against revision 2
        stale_cmd = DomainCommand(
            commandId="cmd-stale-01",
            correlationId="corr-stale",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=2,  # Stale! Current is 3
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-occ", "width_m": 10.0, "length_m": 10.0},
        )
        res = command_bus.execute(stale_cmd)
        assert res.success is False
        assert res.errorCode == "CONCURRENCY_CONFLICT"
        assert res.revision == 3

    def test_mandatory_concurrency_scenario(
        self, command_bus: CommandBus, test_principal: AuthenticatedPrincipal
    ):
        """Mandatory Scenario (Directive Section 13):
        A. Initial state: Project revision = N (e.g. 1)
        B. AI resolves context at revision N
        C. AI generates dry-run preview
        D. User concurrently modifies the project -> revision becomes N+1 (2)
        E. AI attempts commit with expectedRevision = N (1)
        F. CommandBus rejects command with CONCURRENCY_CONFLICT
        G. Existing user modification is preserved intact
        H. AI refreshes context at N+1 and replans with expectedRevision = N+1
        I. Second commit succeeds and advances revision to N+2 (3).
        """
        project_id = "proj-scenario-mandatory"
        command_bus.set_project_revision(project_id, 1)

        # Step 1: Dry-Run at revision 1
        dry_run_cmd = DomainCommand(
            commandId="cmd-dryrun-step1",
            correlationId="corr-scen",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=True,
            payload={"room_id": "room-101", "width_m": 10.0, "length_m": 15.0},
        )
        preview_res = command_bus.execute(dry_run_cmd)
        assert preview_res.success is True
        assert preview_res.isDryRun is True
        assert preview_res.revision == 1

        # Step 2: Concurrently, user manually edits the canvas -> project revision advances to 2
        command_bus.set_project_revision(project_id, 2)
        command_bus._project_canonical_state[project_id] = {
            "devices": [{"id": "user-manual-dev-1", "x_m": 2.0, "y_m": 2.0, "type": "smoke"}],
            "last_mutation": "user_manual_edit",
            "revision": 2,
        }

        # Step 3: AI attempts to commit with stale expectedRevision = 1
        stale_commit_cmd = DomainCommand(
            commandId="cmd-commit-stale",
            correlationId="corr-scen",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,  # Stale!
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-101", "width_m": 10.0, "length_m": 15.0},
        )
        conflict_res = command_bus.execute(stale_commit_cmd)
        assert conflict_res.success is False
        assert conflict_res.errorCode == "CONCURRENCY_CONFLICT"

        # Verify user's manual change is preserved intact
        current_state = command_bus.get_canonical_state(project_id)
        assert current_state["devices"][0]["id"] == "user-manual-dev-1"

        # Step 4: AI refreshes context at revision 2 and replans commit with expectedRevision = 2
        refreshed_commit_cmd = DomainCommand(
            commandId="cmd-commit-refreshed",
            correlationId="corr-scen",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=2,  # Current!
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            isDryRun=False,
            payload={"room_id": "room-101", "width_m": 10.0, "length_m": 15.0},
        )
        success_res = command_bus.execute(refreshed_commit_cmd)
        assert success_res.success is True
        assert success_res.revision == 3
        assert command_bus.get_project_revision(project_id) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CONTEXT RESOLUTION & TOKEN BUDGET TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestContextResolutionAndTokenBudget:
    def test_context_packet_budget_under_1500_tokens(self):
        resolver = ContextResolver(token_budget=1500)
        pkt = resolver.resolve_room_context(
            project_id="proj-ctx-01",
            room_id="room-auditorium",
            revision=4,
            room_bounds={"width_m": 25.0, "length_m": 40.0, "ceiling_height_m": 4.5},
            existing_devices=[
                {"id": f"det-{i}", "type": "smoke", "x": i * 2, "y": i * 3}
                for i in range(10)
            ],
        )

        assert pkt.is_within_budget is True
        assert pkt.token_count <= 1500
        # Measured telemetry check
        assert pkt.telemetry["measured_tokens"] == pkt.token_count
        assert pkt.telemetry["budget_limit"] == 1500
        assert pkt.telemetry["raw_cad_excluded"] is True
        assert pkt.telemetry["whole_project_dump_excluded"] is True

    def test_raw_cad_bloat_excluded_and_budget_enforced(self):
        resolver = ContextResolver(token_budget=1500)
        # Pass a large simulated device list
        large_device_list = [
            {"id": f"det-dense-{i}", "type": "smoke", "x": i * 0.5, "y": i * 0.5, "raw_geom": "X" * 200}
            for i in range(100)
        ]
        pkt = resolver.resolve_room_context(
            project_id="proj-ctx-02",
            room_id="room-dense",
            revision=1,
            existing_devices=large_device_list,
        )
        assert pkt.is_within_budget is True
        assert pkt.token_count <= 1500


# ═══════════════════════════════════════════════════════════════════════════════
# 5. DYNAMIC CAPABILITY DISCOVERY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCapabilityDiscovery:
    def test_discover_exact_phase1_capabilities(self):
        registry = CapabilityRegistry()
        caps = registry.discover(categories=["spatial"])
        assert len(caps) == 1
        assert caps[0].capability_id == "spatial.place_devices"

        comp_caps = registry.discover(categories=["compliance"])
        assert len(comp_caps) == 1
        assert comp_caps[0].capability_id == "compliance.verify_detector_spacing"

    def test_unrelated_capabilities_excluded(self):
        registry = CapabilityRegistry()
        battery_caps = registry.discover(categories=["battery"])
        assert len(battery_caps) == 0

        hydraulics_caps = registry.discover(categories=["hydraulics"])
        assert len(hydraulics_caps) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 6. COMPLETE VERTICAL SLICE B INTEGRATION TEST
# ═══════════════════════════════════════════════════════════════════════════════


class TestVerticalSliceBIntegration:
    def test_end_to_end_vertical_slice_workflow(
        self, command_bus: CommandBus, test_principal: AuthenticatedPrincipal
    ):
        """Verifies the complete flow:
        User Intent -> Context Resolution -> Capability Discovery -> Deterministic Planning
        -> Dry-run DomainCommand -> Preview -> Approval -> Deterministic Commit -> Event & Audit.
        """
        project_id = "proj-e2e-vertical-slice"
        room_id = "room-server-hall"

        # 1. Context Resolution
        resolver = default_context_resolver
        context_pkt = resolver.resolve_room_context(
            project_id=project_id,
            room_id=room_id,
            revision=1,
            room_bounds={"width_m": 6.0, "length_m": 8.0, "ceiling_height_m": 3.0},
        )
        assert context_pkt.token_count <= 1500

        # 2. Capability Discovery
        registry = default_capability_registry
        caps = registry.discover(categories=["spatial"], scopes=test_principal.scopes)
        assert any(c.capability_id == "spatial.place_devices" for c in caps)

        # 3. Dry-Run Planning (Preview Phase)
        dry_run_cmd = DomainCommand(
            commandId="cmd-e2e-dryrun-01",
            correlationId="corr-e2e-01",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            riskClass="MEDIUM",
            isDryRun=True,
            payload={
                "room_id": room_id,
                "width_m": context_pkt.room_bounds["width_m"],
                "length_m": context_pkt.room_bounds["length_m"],
                "ceiling_height_m": context_pkt.room_bounds["ceiling_height_m"],
                "detector_type": "smoke",
            },
        )
        dry_run_result = command_bus.execute(dry_run_cmd)
        assert dry_run_result.success is True
        assert dry_run_result.isDryRun is True
        assert dry_run_result.resultData["device_count"] > 0
        assert dry_run_result.resultData["is_compliant"] is True

        # 4. User Approval & Commit
        commit_cmd = DomainCommand(
            commandId="cmd-e2e-commit-01",
            correlationId="corr-e2e-01",
            capabilityId="spatial.place_devices",
            projectId=project_id,
            expectedRevision=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            principal=test_principal,
            riskClass="MEDIUM",
            isDryRun=False,
            payload=dry_run_cmd.payload,
        )
        commit_result = command_bus.execute(commit_cmd)
        assert commit_result.success is True
        assert commit_result.isDryRun is False
        assert commit_result.revision == 2

        # 5. Event & Audit Verification
        event = commit_result.event
        assert event is not None
        assert event.eventType == "DEVICES_PLACED"
        assert event.actor == test_principal.user_id
        assert len(event.auditReference) == 64  # SHA-256 hex string
        assert event.verificationResult["is_compliant"] is True

        # 6. Canonical State Verification
        canonical_state = command_bus.get_canonical_state(project_id)
        assert len(canonical_state["devices"]) == dry_run_result.resultData["device_count"]
        assert canonical_state["revision"] == 2
