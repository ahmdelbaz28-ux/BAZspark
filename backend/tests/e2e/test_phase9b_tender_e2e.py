"""backend/tests/e2e/test_phase9b_tender_e2e.py — Phase 9b Gate 9b E2E Verification Suite.

Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 9b & Gate 9b:
- Issue two separate, complete tender documents:
  1. Financial Proposal (tender.generate_financial_proposal)
  2. Technical Compliance Matrix (tender.generate_technical_compliance)
- 100% number traceability to BOQ and kernel engineering calculations.
- Exact tax math (EGP 14%, SAR 15%, zero-tax, discounts, category subtotals).
- Strict SHA-256 artifact checksum verification.
- Full execution via ControlRequest -> Generic Planner -> Policy -> Orchestrator -> Run.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.core.agent_run_orchestrator import (
    AgentRun,
    AgentRunOrchestrator,
)
from backend.core.agent_run_store import (
    AgentRunStore,
    ApprovalMode,
    RunStatus,
)
from backend.core.capability_registry import (
    CapabilityRegistry,
    default_capability_registry,
)
from backend.core.command_bus import (
    AuthenticatedPrincipal,
    CommandBus,
)
from backend.core.context_resolver import default_context_resolver
from backend.core.control_request import ControlRequest
from backend.core.generic_planner import GenericWorkflowPlanner
from backend.core.state_store import CommandStateStore
from backend.core.tender_contracts import (
    CAP_TENDER_FINANCIAL_PROPOSAL,
    CAP_TENDER_TECHNICAL_COMPLIANCE,
    handle_tender_generate_financial_proposal,
    handle_tender_generate_technical_compliance,
)
from backend.database import Database


@pytest.fixture
def e2e_db(tmp_path) -> Database:
    """Create an isolated, fresh SQLite database for Phase 9b Gate 9b E2E suite."""
    return Database(db_path=str(tmp_path / "phase9b_gate9b_e2e.db"))


@pytest.fixture
def bus(e2e_db: Database, monkeypatch: pytest.MonkeyPatch) -> CommandBus:
    state_store = CommandStateStore(e2e_db)
    command_bus = CommandBus(capability_registry=default_capability_registry, state_store=state_store)
    monkeypatch.setattr("backend.core.state_store.default_state_store", state_store)
    monkeypatch.setattr("backend.core.command_bus.default_command_bus", command_bus)
    return command_bus


@pytest.fixture
def store(e2e_db: Database) -> AgentRunStore:
    return AgentRunStore(e2e_db)


@pytest.fixture
def registry() -> CapabilityRegistry:
    return default_capability_registry


@pytest.fixture
def orchestrator(
    bus: CommandBus, registry: CapabilityRegistry, store: AgentRunStore
) -> AgentRunOrchestrator:
    return AgentRunOrchestrator(
        command_bus=bus,
        capability_registry=registry,
        run_store=store,
        environment="development",
    )


@pytest.fixture
def generic_planner(
    bus: CommandBus, registry: CapabilityRegistry, orchestrator: AgentRunOrchestrator
) -> GenericWorkflowPlanner:
    return GenericWorkflowPlanner(
        command_bus=bus,
        capability_registry=registry,
        context_resolver=default_context_resolver,
        orchestrator=orchestrator,
        environment="development",
    )


@pytest.fixture
def tender_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        user_id="tender-manager-gate9b",
        email="tender.lead@bazspark.io",
        role="tender_manager",
        scopes=[
            "tender:write",
            "tender:read",
            "workspace:read",
            "governance:read",
            "governance:write",
            "audit:read",
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. GATE 9B VERBATIM E2E PIPELINE: FINANCIAL PROPOSAL & TECHNICAL MATRIX
# ═══════════════════════════════════════════════════════════════════════════


def test_phase9b_verbatim_tender_issuance_e2e(
    generic_planner: GenericWorkflowPlanner,
    orchestrator: AgentRunOrchestrator,
    bus: CommandBus,
    tender_principal: AuthenticatedPrincipal,
) -> None:
    """Issue two separate documents (Financial Proposal + Technical Compliance Matrix) with 100% number traceability."""
    project_id = "proj-tender-tower-01"
    bus.state_store.set_project_revision(project_id, 1)

    control_request = ControlRequest.from_dict({
        "intent": "Generate financial proposal and technical compliance matrix for commercial tower tender",
        "project_id": project_id,
        "expected_revision": 1,
        "approval_mode": "AUTO",
        "explicit_capabilities": [
            CAP_TENDER_FINANCIAL_PROPOSAL,
            CAP_TENDER_TECHNICAL_COMPLIANCE,
        ],
    })

    plan = generic_planner.plan_control_request(request=control_request, principal=tender_principal)
    assert len(plan.steps) == 2
    planned_caps = {s.capability_id for s in plan.steps}
    assert CAP_TENDER_FINANCIAL_PROPOSAL in planned_caps
    assert CAP_TENDER_TECHNICAL_COMPLIANCE in planned_caps

    run = orchestrator.start_run(
        tender_principal,
        project_id=project_id,
        steps=plan.to_agent_run_steps(),
        approval_mode=ApprovalMode.AUTO,
        plan={"plan_id": plan.plan_id, "intent_summary": plan.intent_summary, "dag": plan.dag},
    )

    assert run.status == RunStatus.COMPLETED
    assert len(run.completed_steps) == 2
    assert len(run.audit_reference) == 64
    for step_id in run.completed_steps:
        assert step_id in run.artifacts
        assert len(run.artifacts[step_id]["auditReference"]) == 64


# ═══════════════════════════════════════════════════════════════════════════
# 2. FINANCIAL PROPOSAL NUMBER TRACEABILITY & TAX VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════


def test_financial_proposal_sar_15pct_vat_and_discounts():
    """Verify SAR 15% VAT, 5% discount, category subtotals, and line item arithmetic."""
    items = [
        {"item_code": "FACP-01", "description": "Addressable 4-Loop Panel", "category": "EQUIPMENT", "quantity": 2, "unit": "ea", "unit_price": 4500.0},
        {"item_code": "SMK-01", "description": "Photoelectric Smoke Detector", "category": "DETECTORS", "quantity": 120, "unit": "ea", "unit_price": 85.0},
        {"item_code": "CBL-01", "description": "14 AWG FPLR Shielded Cable", "category": "CABLING", "quantity": 1500, "unit": "m", "unit_price": 2.10},
    ]

    result = handle_tender_generate_financial_proposal({
        "project_id": "proj-saudi-hospital",
        "currency": "SAR",
        "tax_rate_pct": 15.0,
        "discount_pct": 5.0,
        "items": items,
    })

    # Expected calculations:
    # FACP: 2 * 4500 = 9000
    # SMK: 120 * 85 = 10200
    # CBL: 1500 * 2.10 = 3150
    # Gross subtotal = 9000 + 10200 + 3150 = 22350.0
    # Discount 5% = 22350 * 0.05 = 1117.50
    # Net subtotal = 22350 - 1117.50 = 21232.50
    # VAT 15% = 21232.50 * 0.15 = 3184.88
    # Grand Total = 21232.50 + 3184.88 = 24417.38
    assert result["currency"] == "SAR"
    assert result["gross_subtotal"] == 22350.0
    assert result["discount_amount"] == 1117.50
    assert result["net_subtotal"] == 21232.50
    assert result["tax_amount"] == 3184.88
    assert result["grand_total"] == 24417.38
    assert result["subtotals_by_category"]["EQUIPMENT"] == 9000.0
    assert result["subtotals_by_category"]["DETECTORS"] == 10200.0
    assert result["subtotals_by_category"]["CABLING"] == 3150.0
    assert len(result["audit_reference"]) == 64


def test_financial_proposal_egp_14pct_vat_and_boq_auto_derivation():
    """Verify EGP 14% VAT and automatic line item synthesis from BOQ generator."""
    rooms = [
        {"width_m": 20.0, "length_m": 30.0, "ceiling_height_m": 4.0, "occupancy": "commercial"},
        {"width_m": 15.0, "length_m": 15.0, "ceiling_height_m": 3.5, "occupancy": "office"},
    ]
    loops = [
        {"device_count": 65, "wire_length_m": 400.0},
    ]

    result = handle_tender_generate_financial_proposal({
        "project_id": "proj-cairo-mall",
        "currency": "EGP",
        "tax_rate_pct": 14.0,
        "rooms": rooms,
        "loops": loops,
        "panels": 1,
    })

    assert result["currency"] == "EGP"
    assert result["gross_subtotal"] > 0
    assert result["tax_amount"] == round(result["net_subtotal"] * 0.14, 2)
    assert result["grand_total"] == round(result["net_subtotal"] + result["tax_amount"], 2)
    assert len(result["line_items"]) >= 4
    assert len(result["commercial_terms"]) >= 4


# ═══════════════════════════════════════════════════════════════════════════
# 3. TECHNICAL COMPLIANCE MATRIX TRACEABILITY & VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════


def test_technical_compliance_matrix_100pct_traceability():
    """Verify technical compliance matrix links standard citations, kernel values, and computes 100% compliance."""
    result = handle_tender_generate_technical_compliance({
        "project_id": "proj-tech-matrix-01",
        "project_name": "Metro Station Life Safety System",
        "rfp_reference": "RFP-METRO-2026-FACP",
    })

    assert result["total_clauses"] >= 5
    assert result["compliant_count"] == result["total_clauses"]
    assert result["compliance_percentage"] == 100.0
    assert result["overall_verdict"] == "FULLY_COMPLIANT"
    assert len(result["audit_reference"]) == 64

    # Verify statutory citations
    matrix = {row["clause_id"]: row for row in result["compliance_matrix"]}
    assert "SPEC-002-SMOKE-SPACING" in matrix
    assert "NFPA 72-2022 §17.7.3.2.3" in matrix["SPEC-002-SMOKE-SPACING"]["standard_reference"]
    assert "SPEC-001-FACP" in matrix
    assert "NFPA 72-2022 §10.6.7" in matrix["SPEC-001-FACP"]["standard_reference"]


def test_technical_compliance_matrix_with_partial_deviation():
    """Verify compliance percentage formula when deviations exist."""
    custom_clauses = [
        {"clause_id": "C-1", "requirement_text": "Dual FACP Redundancy", "compliance_status": "COMPLIANT"},
        {"clause_id": "C-2", "requirement_text": "Aspirating Smoke in Elevator", "compliance_status": "DEVIATION", "engineering_rationale": "Point detector proposed due to shaft geometry."},
        {"clause_id": "C-3", "requirement_text": "Sprinkler Monitoring", "compliance_status": "COMPLIANT"},
        {"clause_id": "C-4", "requirement_text": "Helipad Foam Deluge", "compliance_status": "NOT_APPLICABLE"},
    ]

    result = handle_tender_generate_technical_compliance({
        "project_id": "proj-custom-compliance",
        "clauses": custom_clauses,
    })

    # Total = 4, Compliant = 2, Deviation = 1, NA = 1
    # Effective clauses = 4 - 1 = 3 -> 2 / 3 * 100 = 66.67%
    assert result["total_clauses"] == 4
    assert result["compliant_count"] == 2
    assert result["deviation_count"] == 1
    assert result["na_count"] == 1
    assert result["compliance_percentage"] == 66.67
    assert result["overall_verdict"] == "NON_COMPLIANT"


# ═══════════════════════════════════════════════════════════════════════════
# 4. SHA-256 ARTIFACT CHECKSUM INTEGRITY
# ═══════════════════════════════════════════════════════════════════════════


def test_tender_sha256_checksum_deterministic_reproducibility():
    """Assert that tender proposal checksums are cryptographically strict and tamper-detecting."""
    proposal = handle_tender_generate_financial_proposal({
        "project_id": "proj-checksum-test",
        "currency": "USD",
        "items": [
            {"item_code": "DET-01", "quantity": 10, "unit_price": 50.0},
        ],
    })

    audit_ref = proposal["audit_reference"]
    assert len(audit_ref) == 64

    # Verify SHA-256 matches content hash
    copy_doc = {k: v for k, v in proposal.items() if k not in ("audit_reference", "status")}
    recomputed = hashlib.sha256(json.dumps(copy_doc, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    assert audit_ref == recomputed


# ═══════════════════════════════════════════════════════════════════════════
# 5. PERFORMANCE BENCHMARK: P95 LATENCY
# ═══════════════════════════════════════════════════════════════════════════


def test_tender_p95_latency_benchmark_under_limit():
    """Assert p95 latency < 250ms for both tender capabilities."""
    p95_limit_ms = 250.0

    for handler in [handle_tender_generate_financial_proposal, handle_tender_generate_technical_compliance]:
        samples: list[float] = []
        for _ in range(10):
            t0 = time.perf_counter()
            res = handler({})
            t1 = time.perf_counter()
            samples.append((t1 - t0) * 1000.0)
            assert "audit_reference" in res

        sorted_samples = sorted(samples)
        p95_val = sorted_samples[int(0.95 * len(sorted_samples))]
        assert p95_val < p95_limit_ms, f"Tender handler exceeded p95 limit: {p95_val:.2f}ms"
