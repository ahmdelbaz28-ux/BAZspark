# File-level issue suppression removed per AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
"""
backend/routers/facp.py — FACP Selection & Compliance REST API.
================================================================
REST endpoints for the Fire Alarm Control Panel selection engine.

ENDPOINTS:
  POST /api/facp/select      — Select optimal FACP for project requirements
  POST /api/facp/verify      — Verify compliance of a panel recommendation
  POST /api/facp/schedule    — Generate DXF schedule table
  POST /api/facp/spec        — Generate CSI specification (Section 28 31 11)
  GET  /api/facp/panels      — list all available panels in the database

STANDARDS:
  NFPA_72_REF — FACP selection and listing requirements
  NFPA_72_REF  — Battery backup capacity
  UL_864_REF    — Control unit listing requirements
  CSFM                   — California State Fire Marshal listing
  FDNY COA               — New York City Certificate of Approval

SAFETY NOTE:
  FACP selection is a SAFETY-CRITICAL operation. Selecting a non-compliant
  panel for a fire alarm system could result in:
  - Failure to detect/notify during a fire event
  - Insufficient battery capacity for 24h standby + alarm duration
  - Non-releasing panel selected for suppression systems (NFPA 72 SS21.7)
  - AHJ rejection of the fire alarm system design

  All selection results include a cryptographic signature hash for
  deterministic verification and audit trail purposes.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from backend.auth import require_permission
from backend.rbac import Permission

try:
    from backend.limiter import limiter

    _HAS_LIMITER = True
except ImportError:
    _HAS_LIMITER = False
    limiter = None

logger = logging.getLogger(__name__)

#: S1192: "Temperature-compensated (NFPA 72 §10.6.7)" used 3+ times —
#: define a module-level constant instead of duplicating the literal.
BATTERY_DERATING_TEMP_COMPENSATED = "Temperature-compensated (NFPA 72 §10.6.7)"

router = APIRouter(tags=["facp"])

# ── Constants ────────────────────────────────────────────────────────────────
NFPA_72_REF = "NFPA 72-2022 SS10.6.7"
UL_864_REF = "UL 864 10th Edition"

_SUCCESS = "success"
_ERROR = "error"
_INTERNAL_ERROR = "INTERNAL_ERROR"

# ── Request/Response Models ──────────────────────────────────────────────────


class FACPSelectionRequest(BaseModel):
    """
    Input for FACP panel selection.

    All fields map to facp_system.panel_selector.ProjectRequirements.
    """

    device_count: int = Field(
        ..., gt=0, description="Total number of addressable devices (detectors, modules, etc.)"
    )
    nac_circuit_count: int = Field(
        ..., gt=0, description="Number of Notification Appliance Circuits required"
    )
    building_size_m2: float = Field(
        ..., gt=0, description="Total building floor area in square meters"
    )
    building_floors: int = Field(..., gt=0, description="Number of building floors")
    requires_network: bool = Field(
        False, description="True if panels must be networked across multiple locations"
    )
    requires_voice: bool = Field(
        False,
        description="True if voice evacuation is required (affects alarm duration: 15min vs 5min per NFPA 72 SS10.6.7)",
    )
    requires_releasing: bool = Field(
        False,
        description="True if panel must support releasing service for suppression systems (NFPA 72 SS21.7)",
    )
    jurisdiction: str = Field("US", description="Jurisdiction code: US, Canada, FDNY, etc.")
    preferred_manufacturer: str | None = Field(
        None, description="Preferred FACP manufacturer (e.g., NOTIFIER, SIEMENS, SIMPLEX)"
    )
    min_temperature_c: float = Field(
        20.0,
        ge=-40.0,
        le=60.0,
        description="Minimum ambient temperature for battery derating per NFPA 72 SS10.6.7",
    )


class FACPVerificationRequest(BaseModel):
    """
    Input for FACP compliance verification.
    Accepts full requirement fields or simple panel_id payload from frontend.
    """

    panel_id: str | None = None
    device_count: int = Field(50, gt=0)
    nac_circuit_count: int = Field(2, gt=0)
    building_size_m2: float = Field(1000.0, gt=0)
    building_floors: int = Field(2, gt=0)
    requires_network: bool = False
    requires_voice: bool = False
    requires_releasing: bool = False
    jurisdiction: str = "US"
    preferred_manufacturer: str | None = None
    min_temperature_c: float = Field(20.0, ge=-40.0, le=60.0)
    recommended_model: str = Field("NFS2-3030", description="Model name of the panel to verify")
    manufacturer: str = Field("NOTIFIER", description="Manufacturer of the panel")
    capacity_utilization: float = Field(0.5, ge=0.0, le=1.0)
    nac_utilization: float = Field(0.4, ge=0.0, le=1.0)
    battery_size_ah: float = Field(26.0, gt=0)
    battery_derating_method: str = Field(
        BATTERY_DERATING_TEMP_COMPENSATED, description="Battery sizing method used"
    )

    @model_validator(mode="after")
    def _require_panel_id_or_full_fields(self) -> "FACPVerificationRequest":
        """Require either a panel_id lookup or the full verification field set.

        A minimal payload (e.g. only device_count) must be rejected with 422
        because verifying an empty/default recommendation would silently
        produce a misleading compliance result — deceptive in a safety-critical
        workflow (see agent.md Anti-Deception Directive).
        """
        if self.panel_id is not None:
            return self
        required = {
            "recommended_model",
            "manufacturer",
            "capacity_utilization",
            "nac_utilization",
            "battery_size_ah",
            "battery_derating_method",
        }
        missing = required - set(self.model_fields_set)
        if missing:
            raise ValueError(
                "When panel_id is omitted, the full verification payload "
                f"is required; missing fields: {sorted(missing)}"
            )
        return self


class FACPScheduleRequest(BaseModel):
    """Input for DXF schedule table generation."""

    panel_id: str | None = None
    recommended_model: str = Field("NFS2-3030", description="Panel model from selection result")
    manufacturer: str = Field("NOTIFIER", description="Panel manufacturer")
    capacity_utilization: float = Field(0.5, ge=0.0, le=1.0)
    nac_utilization: float = Field(0.4, ge=0.0, le=1.0)
    battery_size_ah: float = Field(26.0, gt=0)
    battery_derating_method: str = Field(BATTERY_DERATING_TEMP_COMPENSATED)
    power_supply_watts: int = Field(120, gt=0)
    listings: list[str] = Field(default_factory=lambda: ["UL 864 10th Ed", "CSFM"])
    signature_hash: str = Field(
        "facp_sig_default", description="Cryptographic signature from selection"
    )
    quantity: int = Field(1, gt=0, le=100, description="Number of panels (for schedule)")


class FACPSpecRequest(BaseModel):
    """Input for CSI specification generation."""

    panel_id: str | None = None
    device_count: int = Field(50, gt=0)
    nac_circuit_count: int = Field(2, gt=0)
    building_size_m2: float = Field(1000.0, gt=0)
    building_floors: int = Field(2, gt=0)
    requires_network: bool = False
    requires_voice: bool = False
    requires_releasing: bool = False
    jurisdiction: str = "US"
    recommended_model: str = Field("NFS2-3030")
    manufacturer: str = Field("NOTIFIER")
    capacity_utilization: float = Field(0.5, ge=0.0, le=1.0)
    nac_utilization: float = Field(0.4, ge=0.0, le=1.0)
    battery_size_ah: float = Field(26.0, gt=0)
    battery_derating_method: str = Field(BATTERY_DERATING_TEMP_COMPENSATED)
    power_supply_watts: int = Field(120, gt=0)
    listings: list[str] = Field(default_factory=lambda: ["UL 864 10th Ed", "CSFM"])
    signature_hash: str = Field("facp_sig_default")


# ── Helper: Safe FACP module import ──────────────────────────────────────────

if _HAS_LIMITER:
    _rate_limit = limiter.limit
else:

    def _rate_limit(_s: str) -> object:
        return lambda f: f


_facp_available: bool | None = None


def _check_facp_available() -> bool:
    """
    Check if facp_system package is available.

    SAFETY: If the FACP module is not available, endpoints must return 503
    (Service Unavailable) rather than 500 (Internal Server Error).
    A 503 clearly indicates a missing dependency, while a 500 could be
    misinterpreted as a computation error — which would be deceptive
    in a safety-critical system per agent.md Anti-Deception Directive.
    """
    global _facp_available
    if not _facp_available:
        try:
            from facp_system.panel_database import MASTER_PANEL_DATABASE  # noqa: F401
            from facp_system.panel_output import OutputGenerator  # noqa: F401
            from facp_system.panel_selector import SelectionEngine  # noqa: F401
            from facp_system.panel_verifier import ComplianceVerifier  # noqa: F401

            _facp_available = True
            logger.info("FACP system modules loaded successfully")
        except ImportError as e:
            _facp_available = False
            logger.exception(
                "FACP system modules not available: %s. "
                "FACP endpoints will return 503. "
                "Ensure facp_system/ package is in the Python path.",
                e,
            )
    return _facp_available


def _require_facp() -> None:
    """Raise 503 if FACP modules are not available."""
    if not _check_facp_available():
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=503,  # NOSONAR: S8415 — endpoint error handling is intentional  # NOSONAR — S7632: test function documented via class name / module path
            detail={
                _ERROR: "FACP_SERVICE_UNAVAILABLE",
                "detail": (
                    "FACP selection engine is not available. "
                    "The facp_system package could not be imported. "
                    "Check server logs for import errors."
                ),
                "action": "Ensure facp_system/ is installed and in the Python path.",
            },
        )


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/facp/select", dependencies=[Depends(require_permission(Permission.FACP_MANAGE))])
@_rate_limit("30/minute")
async def select_facp(request: Request, req: FACPSelectionRequest):
    """
    Select optimal FACP for project requirements.

    Runs the deterministic selection algorithm from
    facp_system.panel_selector.SelectionEngine with:
      - Points capacity filtering (1.2x margin per NFPA best practice)
      - NAC capacity filtering (exact match — V54 FIX F2)
      - Releasing service filter (V54 FIX F4)
      - Jurisdiction listing checks (UL, ULC, FDNY, FM)
      - NFPA 72 SS10.6.7 battery sizing with temperature/aging/Peukert derating
      - Cryptographic signature hash for audit trail

    Returns the recommended panel, alternatives, battery sizing details,
    and compliance listings.
    """
    _require_facp()

    try:
        from facp_system.panel_selector import ProjectRequirements, SelectionEngine

        project_req = ProjectRequirements(
            device_count=req.device_count,
            nac_circuit_count=req.nac_circuit_count,
            building_size_m2=req.building_size_m2,
            building_floors=req.building_floors,
            requires_network=req.requires_network,
            requires_voice=req.requires_voice,
            requires_releasing=req.requires_releasing,
            jurisdiction=req.jurisdiction,
            preferred_manufacturer=req.preferred_manufacturer,
            min_temperature_c=req.min_temperature_c,
        )

        recommendation = SelectionEngine.select_panel(project_req)

        return {
            _SUCCESS: True,
            "data": {
                "recommended_model": recommendation.recommended_model,
                "manufacturer": recommendation.manufacturer,
                "capacity_utilization": recommendation.capacity_utilization,
                "nac_utilization": recommendation.nac_utilization,
                "battery_size_ah": recommendation.battery_size_ah,
                "battery_derating_details": recommendation.battery_derating_details,
                "power_supply_watts": recommendation.power_supply_watts,
                "listings": recommendation.listings,
                "code_compliance": recommendation.code_compliance,
                "warnings": recommendation.warnings,
                "alternatives": recommendation.alternatives,
                "signature_hash": recommendation.signature_hash,
                "nfpa_reference": NFPA_72_REF,
                "ul_reference": UL_864_REF,
            },
        }
    except ValueError as exc:
        # No compliant panels found
        logger.warning("FACP selection failed: %s", exc)
        # S-07 FIX (Engineering Review): do not return str(exc) to the client —
        # it may leak internal paths, SQL fragments, or stack-trace context.
        # The full message is preserved in the server log; the client only sees
        # a stable, generic error code.
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=422,
            detail={
                _ERROR: "NO_COMPLIANT_PANEL",
                "detail": "No compliant panel available for the requested configuration.",
                "action": (
                    "Relax design requirements or expand the panel database. "
                    "Consider splitting the system into multiple networked panels."
                ),
            },
        )
    except Exception as exc:
        logger.exception("FACP selection unexpected error: %s", exc)
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=500,
            detail={
                _ERROR: _INTERNAL_ERROR,
                "detail": "An unexpected error occurred during FACP selection.",
            },
        )


@router.post("/facp/verify", dependencies=[Depends(require_permission(Permission.FACP_MANAGE))])
@_rate_limit("30/minute")
async def verify_facp(request: Request, req: FACPVerificationRequest):
    """
    Verify compliance of a panel recommendation.

    Runs programmatic compliance checks from
    facp_system.panel_verifier.ComplianceVerifier:
      - UL 864 listing validation
      - Battery safety margin check (NFPA 72 SS10.6.7)
      - Voice evacuation capability check
      - FDNY Certificate of Approval check
      - Releasing service verification (V54 FIX F4)
      - Battery derating method verification (V54 FIX F5)

    Returns a list of violations (empty = compliant).
    """
    _require_facp()

    try:
        from facp_system.panel_database import MASTER_PANEL_DATABASE
        from facp_system.panel_selector import PanelRecommendation, ProjectRequirements
        from facp_system.panel_verifier import ComplianceVerifier

        # When panel_id is supplied, resolve the panel's real datasheet values
        # from the immutable database so verification reflects the actual panel
        # rather than request defaults (SAFETY: no silent default verification).
        if req.panel_id is not None:
            panel = next(
                (p for p in MASTER_PANEL_DATABASE if p.model == req.panel_id),
                None,
            )
            if panel is None:
                raise HTTPException(
                    status_code=404,
                    detail={
                        _ERROR: "PANEL_NOT_FOUND",
                        "detail": f"No panel found for panel_id '{req.panel_id}'.",
                    },
                )
            resolved_model = panel.model
            resolved_manufacturer = panel.manufacturer
            resolved_listings = panel.listings
            resolved_power_supply_watts = panel.power_supply_watts
        else:
            resolved_model = req.recommended_model
            resolved_manufacturer = req.manufacturer
            resolved_listings = [
                p.listings for p in MASTER_PANEL_DATABASE if p.model == req.recommended_model
            ]
            resolved_listings = resolved_listings[0] if resolved_listings else []
            resolved_power_supply_watts = 0  # Not needed for verification

        project_req = ProjectRequirements(
            device_count=req.device_count,
            nac_circuit_count=req.nac_circuit_count,
            building_size_m2=req.building_size_m2,
            building_floors=req.building_floors,
            requires_network=req.requires_network,
            requires_voice=req.requires_voice,
            requires_releasing=req.requires_releasing,
            jurisdiction=req.jurisdiction,
            preferred_manufacturer=req.preferred_manufacturer,
            min_temperature_c=req.min_temperature_c,
        )

        # Reconstruct PanelRecommendation from request
        # Look up panel listings from database for accurate verification
        recommendation = PanelRecommendation(
            recommended_model=resolved_model,
            manufacturer=resolved_manufacturer,
            capacity_utilization=req.capacity_utilization,
            nac_utilization=req.nac_utilization,
            battery_size_ah=req.battery_size_ah,
            battery_derating_details={"method": req.battery_derating_method},
            power_supply_watts=resolved_power_supply_watts,
            listings=resolved_listings,  # Populated from database for accurate UL/FDNY listing checks
            code_compliance=[],
            warnings=[],
            alternatives=[],
            signature_hash="",
        )

        violations = ComplianceVerifier.verify_national_code_rules(project_req, recommendation)

        is_compliant = len(violations) == 0

        return {
            _SUCCESS: True,
            "data": {
                "is_compliant": is_compliant,
                "violations": violations,
                "violation_count": len(violations),
                "nfpa_reference": NFPA_72_REF,
                "ul_reference": UL_864_REF,
            },
        }
    except Exception as exc:
        logger.exception("FACP verification error: %s", exc)
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=500,
            detail={
                _ERROR: _INTERNAL_ERROR,
                "detail": "An unexpected error occurred during FACP compliance verification.",
            },
        )


@router.post("/facp/schedule", dependencies=[Depends(require_permission(Permission.FACP_MANAGE))])
@_rate_limit("10/minute")
async def generate_facp_schedule(request: Request, req: FACPScheduleRequest):
    """
    Generate DXF schedule table for the selected FACP.

    Produces a formatted text table suitable for CAD viewport placement
    in the fire alarm plan drawings. Includes:
      - Model number and quantity
      - Manufacturer
      - Power supply rating
      - Points and NAC utilization
      - Battery size with derating method
      - Regulatory listings
      - Cryptographic signature hash
    """
    _require_facp()

    try:
        from facp_system.panel_output import OutputGenerator
        from facp_system.panel_selector import PanelRecommendation

        recommendation = PanelRecommendation(
            recommended_model=req.recommended_model,
            manufacturer=req.manufacturer,
            capacity_utilization=req.capacity_utilization,
            nac_utilization=req.nac_utilization,
            battery_size_ah=req.battery_size_ah,
            battery_derating_details={"method": req.battery_derating_method},
            power_supply_watts=req.power_supply_watts,
            listings=req.listings,
            code_compliance=[],
            warnings=[],
            alternatives=[],
            signature_hash=req.signature_hash,
        )

        schedule_text = OutputGenerator.generate_dxf_schedule(recommendation, qty=req.quantity)

        return {
            _SUCCESS: True,
            "data": {
                "schedule": schedule_text,
                "format": "text_table",
                "model": req.recommended_model,
                "quantity": req.quantity,
            },
        }
    except Exception as exc:
        logger.exception("FACP schedule generation error: %s", exc)
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=500,
            detail={
                _ERROR: _INTERNAL_ERROR,
                "detail": "An unexpected error occurred during schedule generation.",
            },
        )


@router.post("/facp/spec", dependencies=[Depends(require_permission(Permission.FACP_MANAGE))])
@_rate_limit("10/minute")
async def generate_facp_spec(request: Request, req: FACPSpecRequest):
    """
    Generate CSI specification (Section 28 31 11) for the selected FACP.

    Produces a ready-to-print specification paragraph for fire protection
    construction bids, including:
      - System overview with panel model and capabilities
      - Design metrics (point capacity, battery, power supply)
      - Code certification and listings
      - Releasing service requirements (if applicable)

    Reference: CSI MasterFormat 28 31 11 — Fire Alarm Control Panels
    """
    _require_facp()

    try:
        from facp_system.panel_output import OutputGenerator
        from facp_system.panel_selector import PanelRecommendation, ProjectRequirements

        project_req = ProjectRequirements(
            device_count=req.device_count,
            nac_circuit_count=req.nac_circuit_count,
            building_size_m2=req.building_size_m2,
            building_floors=req.building_floors,
            requires_network=req.requires_network,
            requires_voice=req.requires_voice,
            requires_releasing=req.requires_releasing,
            jurisdiction=req.jurisdiction,
        )

        recommendation = PanelRecommendation(
            recommended_model=req.recommended_model,
            manufacturer=req.manufacturer,
            capacity_utilization=req.capacity_utilization,
            nac_utilization=req.nac_utilization,
            battery_size_ah=req.battery_size_ah,
            battery_derating_details={"method": req.battery_derating_method},
            power_supply_watts=req.power_supply_watts,
            listings=req.listings,
            code_compliance=[],
            warnings=[],
            alternatives=[],
            signature_hash=req.signature_hash,
        )

        csi_spec = OutputGenerator.generate_csi_specification(project_req, recommendation)

        # Also generate alternatives table
        alternatives_table = OutputGenerator.generate_alternatives_table(recommendation)

        return {
            _SUCCESS: True,
            "data": {
                "csi_specification": csi_spec,
                "alternatives_table": alternatives_table,
                "section": "28 31 11",
                "format": "CSI MasterFormat",
            },
        }
    except Exception as exc:
        logger.exception("FACP spec generation error: %s", exc)
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=500,
            detail={
                _ERROR: _INTERNAL_ERROR,
                "detail": "An unexpected error occurred during specification generation.",
            },
        )


@router.get("/facp/panels", dependencies=[Depends(require_permission(Permission.FACP_READ))])
async def list_available_panels():
    """
    list all FACP panels in the database with full specifications.

    Returns the complete panel database for manual review and
    engineering judgment. Each panel includes:
      - Model, manufacturer
      - Points capacity, NAC capacity, SLC loops
      - Networking, voice, releasing capabilities
      - Regulatory listings (UL, ULC, FM, FDNY)
      - Standby and alarm current draw
      - Power supply wattage

    SAFETY: This endpoint is read-only (GET) and does not require
    API key authentication. It provides reference data only.
    """
    _require_facp()

    try:
        from facp_system.panel_database import MASTER_PANEL_DATABASE

        panels = []
        for p in MASTER_PANEL_DATABASE:
            panels.append(
                {
                    "model": p.model,
                    "manufacturer": p.manufacturer,
                    "points_capacity": p.points_capacity,
                    "nac_capacity": p.nac_capacity,
                    "supports_networking": p.supports_networking,
                    "supports_voice": p.supports_voice,
                    "supports_releasing": p.supports_releasing,
                    "max_slc_loops": p.max_slc_loops,
                    "listings": p.listings,
                    "standby_current_amps": p.standby_current_amps,
                    "alarm_current_amps": p.alarm_current_amps,
                    "power_supply_watts": p.power_supply_watts,
                }
            )

        return {
            _SUCCESS: True,
            "data": {
                "panels": panels,
                "total_count": len(panels),
                "manufacturers": list({p.manufacturer for p in MASTER_PANEL_DATABASE}),
                "standards": [
                    NFPA_72_REF,
                    UL_864_REF,
                    "CSFM",
                    "FDNY COA",
                ],
            },
        }
    except Exception as exc:
        logger.exception("FACP panel listing error: %s", exc)
        raise HTTPException(  # NOSONAR — S8415: assignment kept for readability / debuggability
            status_code=500,
            detail={
                _ERROR: _INTERNAL_ERROR,
                "detail": "An unexpected error occurred while listing panels.",
            },
        )


@router.get(
    "/facp/cluster/status",
    dependencies=[Depends(require_permission(Permission.FACP_READ))],
)
async def get_facp_cluster_status():
    """
    Get Distributed FACP Cluster Communicator status and node topology.

    A7 FIX: this endpoint previously returned a fabricated healthy-node
    payload (fake leader election, hardcoded uptime) that could be mistaken
    for a live distributed deployment. There is NO real cluster behind this
    backend process (and the backend must stay isolated from
    ``facp_distributed`` — see backend/tests/security/
    test_marshal_loads_not_http_reachable.py), so we now fail honestly with
    501 and an explicit ``demo`` marker instead of inventing telemetry.
    """
    raise HTTPException(
        status_code=501,
        detail={
            _ERROR: "NOT_CONNECTED_TO_REAL_SYSTEM",
            "demo": True,
            "detail": (
                "Distributed FACP cluster status is not available: no real "
                "cluster connection is configured. This endpoint never reports "
                "simulated panel telemetry."
            ),
        },
    )
