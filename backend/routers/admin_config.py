"""
backend/routers/admin_config.py — Admin Configuration & Engineering Settings Endpoints.
========================================================================================

Provides unified, authenticated, and RBAC-guarded endpoints for:
  • /env-config                          → GET (categorized UI config), PUT (update overrides)
  • /feature-flags, /settings/feature-flags → GET / POST (toggle flags, single & batch)
  • /settings/runtime                    → GET / POST (runtime feature flags for UI registry)
  • /settings/bootstrap                  → GET (system bootstrap properties)
  • /settings/config                     → GET (read-only environment variables dictionary)
  • /settings/engineering-config         → GET / PUT (Acoustic, Hydraulic, Battery, Integrations)
  • /settings/cad-config                 → GET / PUT (AutoCAD, Revit, Speckle, APS configurations)
  • /settings/secret-rotation/rotate     → POST (hot-rotate secrets with grace period)
  • /settings/admin-token/rotate         → POST (rotate BAZSPARK_MASTER_ADMIN_TOKEN)

🔒 SECURITY & RBAC:
-------------------
• All configuration management endpoints require Permission.SYSTEM_CONFIG (admin role).
• Sensitive values (API tokens, private keys, database connection strings) are masked on retrieval.
• All incoming request bodies are validated with strict Pydantic schemas enforcing physical
  bounds, unit consistency, and non-empty values.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
from typing import Any

try:
    from typing import Annotated
except ImportError:  # Python < 3.9
    from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth import require_permission
from backend.rbac import Permission, Role
from backend.response import success

# ── Annotated dependency alias (S8410) ─────────────────────────────────────
SystemConfigRole = Annotated[Role, Depends(require_permission(Permission.SYSTEM_CONFIG))]
# ────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# Router has NO prefix at the APIRouter() level.
# Mounted at /api/v1 by app.py's _safe_include_router loop.
router = APIRouter(tags=["admin-config"])


# ═══════════════════════════════════════════════════════════════════════════════
# IN-MEMORY STATE & OVERRIDES
# ═══════════════════════════════════════════════════════════════════════════════

# Feature flag overrides applied on top of DEFAULT_FEATURE_FLAGS.
_FEATURE_FLAG_OVERRIDES: dict[str, bool] = {}

# Environment config overrides (safe subset — never secrets).
_ENV_CONFIG_OVERRIDES: dict[str, dict[str, Any]] = {}


# ═══════════════════════════════════════════════════════════════════════════════
# ENGINEERING & CALCULATION CONFIGURATION STATE & SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class AcousticConfig(BaseModel):
    """Acoustic & Notification Appliance Parameters (NFPA 72 Chapter 18)."""

    ambient_noise_db: float = Field(
        default=65.0,
        ge=30.0,
        le=120.0,
        description="Average ambient sound level in dBA (NFPA 72 §18.4.3)",
    )
    spl_drop_per_doubling_db: float = Field(
        default=6.0,
        ge=3.0,
        le=12.0,
        description="Sound pressure level attenuation per distance doubling (dB/DD)",
    )
    min_snr_dba: float = Field(
        default=15.0,
        ge=10.0,
        le=30.0,
        description="Minimum sound level above ambient required for audibility (NFPA 72 §18.4.3.1)",
    )
    strobe_sync_enabled: bool = Field(
        default=True,
        description="Enforce synchronized strobe flashing across notification zones (NFPA 72 §18.5.5.4)",
    )
    strobe_flash_rate_hz: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Strobe flash rate in Hertz (NFPA 72 §18.5.3: 1 to 2 Hz)",
    )


class HydraulicConfig(BaseModel):
    """Hydraulic & Darcy-Weisbach / Hazen-Williams Solver Options (NFPA 13, NFPA 12, NFPA 2001)."""

    default_fluid_density_kg_m3: float = Field(
        default=1000.0,
        ge=0.1,
        le=20000.0,
        description="Default fluid density in kg/m³ (1000 for water, 1.98 for gaseous CO2)",
    )
    default_fluid_viscosity_pa_s: float = Field(
        default=0.001,
        ge=1e-7,
        le=1000.0,
        description="Default dynamic viscosity in Pa·s (0.001 for water at 20°C)",
    )
    default_pipe_roughness_mm: float = Field(
        default=0.045,
        ge=0.001,
        le=10.0,
        description="Default pipe absolute roughness for Darcy-Weisbach in mm (0.045 for commercial steel)",
    )
    default_c_factor: float = Field(
        default=120.0,
        ge=50.0,
        le=180.0,
        description="Default Hazen-Williams roughness coefficient C (120 for wet steel)",
    )
    colebrook_tolerance: float = Field(
        default=1e-8,
        ge=1e-12,
        le=1e-3,
        description="Newton-Raphson Colebrook-White friction factor convergence tolerance",
    )
    max_solver_iterations: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Maximum iterations for hydraulic loops & nonlinear solvers",
    )


class BatteryConfig(BaseModel):
    """Secondary Power Supply & Battery Sizing Parameters (NFPA 72 §10.6.7, IEEE 485)."""

    ambient_temperature_c: float = Field(
        default=25.0,
        ge=-20.0,
        le=60.0,
        description="Ambient operating temperature in °C for IEEE 485 battery derating",
    )
    standby_duration_hours: float = Field(
        default=24.0,
        ge=1.0,
        le=168.0,
        description="Required standby duration in hours (24h standard, 60h central station per NFPA 72 §10.6.7.2.1)",
    )
    alarm_duration_minutes: float = Field(
        default=5.0,
        ge=1.0,
        le=120.0,
        description="Required full alarm duration in minutes (5 min standard, 15 min EVACS per NFPA 72 §10.6.7.2.1)",
    )
    aging_safety_margin_pct: float = Field(
        default=20.0,
        ge=0.0,
        le=100.0,
        description="Safety factor margin for end-of-life battery aging (% over calculated Ah)",
    )
    battery_derating_factor: float = Field(
        default=0.85,
        ge=0.5,
        le=1.0,
        description="Lead-acid Peukert derating factor at alarm discharge rates",
    )


class IntegrationConfig(BaseModel):
    """External BIM, CAD, and Simulation Queue Integration Parameters."""

    speckle_server_url: str = Field(
        default="https://speckle.xyz",
        max_length=256,
        description="Speckle BIM server connector URL",
    )
    revit_bridge_url: str = Field(
        default="http://localhost:8002",
        max_length=256,
        description="Revit Local Add-in bridge API URL",
    )
    autocad_bridge_port: int = Field(
        default=8001,
        ge=1024,
        le=65535,
        description="AutoCAD local IPC connector port",
    )
    fds_max_concurrent_simulations: int = Field(
        default=2,
        ge=1,
        le=16,
        description="Max concurrent FDS fire dynamics simulation jobs",
    )
    fds_queue_timeout_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="FDS simulation job queue timeout in seconds",
    )


class EngineeringConfig(BaseModel):
    """Complete Engineering Configuration Model."""

    acoustic: AcousticConfig = Field(default_factory=AcousticConfig)
    hydraulic: HydraulicConfig = Field(default_factory=HydraulicConfig)
    battery: BatteryConfig = Field(default_factory=BatteryConfig)
    integration: IntegrationConfig = Field(default_factory=IntegrationConfig)


class EngineeringConfigUpdate(BaseModel):
    """Partial or full update model for engineering configuration."""

    acoustic: AcousticConfig | None = None
    hydraulic: HydraulicConfig | None = None
    battery: BatteryConfig | None = None
    integration: IntegrationConfig | None = None


# Module-level live engineering configuration
_LIVE_ENGINEERING_CONFIG: EngineeringConfig = EngineeringConfig()


# ═══════════════════════════════════════════════════════════════════════════════
# CAD & CLOUD BRIDGE CONFIGURATION SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class CadAutoCADConfig(BaseModel):
    path: str = Field(default="", max_length=512)
    version: str = Field(default="2024", max_length=32)
    template: str = Field(default="", max_length=512)
    units: str = Field(default="Millimeters", max_length=32)
    bridge_port: int = Field(default=8001, ge=1024, le=65535)


class CadRevitConfig(BaseModel):
    path: str = Field(default="", max_length=512)
    version: str = Field(default="2024", max_length=32)
    template: str = Field(default="", max_length=512)
    units: str = Field(default="Millimeters", max_length=32)
    bridge_url: str = Field(default="http://localhost:8002", max_length=256)


class CadCloudConfig(BaseModel):
    speckle_server: str = Field(default="https://speckle.xyz", max_length=256)
    speckle_stream_id: str = Field(default="", max_length=128)
    speckle_token: str | None = Field(default=None, max_length=512)
    aps_client_id: str = Field(default="", max_length=128)
    aps_client_secret: str | None = Field(default=None, max_length=512)
    aps_activity_id: str = Field(default="BazSparkAutoCADBridge.DrawLayout", max_length=128)


class CadConfig(BaseModel):
    autocad: CadAutoCADConfig = Field(default_factory=CadAutoCADConfig)
    revit: CadRevitConfig = Field(default_factory=CadRevitConfig)
    cloud: CadCloudConfig = Field(default_factory=CadCloudConfig)


class CadConfigUpdate(BaseModel):
    autocad: CadAutoCADConfig | None = None
    revit: CadRevitConfig | None = None
    cloud: CadCloudConfig | None = None


# Module-level live CAD configuration
_LIVE_CAD_CONFIG: CadConfig = CadConfig()


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE FLAGS & ENV CONFIG SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════


class FeatureFlagUpdate(BaseModel):
    """Request body for POST /feature-flags — toggle a single flag."""

    flag: str = Field(..., min_length=1, description="Feature flag name (e.g. 'SMOKE_SIMULATION')")
    enabled: bool = Field(..., description="New state for the flag")


class EnvConfigUpdate(BaseModel):
    """Request body for PUT /env-config — apply overrides to env config."""

    overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Category → {key: value} overrides or direct key-value mapping.",
    )


class SecretRotationRequest(BaseModel):
    """Optional body for POST /settings/secret-rotation/rotate."""

    key_name: str = Field(
        default="FIREAI_API_KEY",
        min_length=1,
        description="Name of the secret to rotate (env var name)",
    )
    new_secret: str | None = Field(
        default=None,
        min_length=32,
        description="Optional new secret (>=32 chars). If omitted, a 256-bit random secret is generated.",
    )


_ROTATABLE_SECRETS = frozenset(
    {
        "FIREAI_API_KEY",
        "FIREAI_SESSION_SECRET",
        "FIREAI_VISION_KEY_ENCRYPTION_KEY",
        "DATABASE_URL",
        "QOMN_AUDIT_SECRET_KEY",
        "REDIS_URL",
        "APS_CLIENT_SECRET",
        "HF_TOKEN",
        "OPENAI_API_KEY",
    }
)

_TEST_SECRET_PREFIX = "FIREAI_TEST_"
_SAFE_SECRET_VALUE_RE = re.compile(r"^[\x20-\x7e]{32,4096}$")


def _validate_rotatable_secret_name(key_name: str) -> str:
    """Return the validated secret name or raise 400 for non-allowlisted names."""
    if key_name not in _ROTATABLE_SECRETS and not key_name.startswith(_TEST_SECRET_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Secret name '{key_name}' is not in the rotatable allowlist.",
        )
    return key_name


def _set_rotated_secret(key_name: str, new_secret: str) -> None:
    """Apply a rotated secret to the process environment."""
    if key_name not in _ROTATABLE_SECRETS and not key_name.startswith(_TEST_SECRET_PREFIX):
        raise RuntimeError(
            f"Internal invariant violated: non-allowlisted env var '{key_name}' reached os.environ assignment."
        )
    os.environ[key_name] = new_secret


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE FLAGS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/feature-flags")
@router.get("/settings/feature-flags")
async def get_feature_flags_endpoint(_role: SystemConfigRole) -> dict[str, Any]:
    """Return the current feature flag states."""
    from fireai.core.contracts import get_feature_flags

    flags = get_feature_flags()
    flags.update(_FEATURE_FLAG_OVERRIDES)
    return success(
        {
            "flags": flags,
            "overridden": list(_FEATURE_FLAG_OVERRIDES.keys()),
            "note": "Overrides are in-memory and will be lost on restart. Set FIREAI_FEATURE_FLAGS env var for persistence.",
        }
    )


@router.post("/feature-flags")
async def update_feature_flag(
    body: FeatureFlagUpdate,
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """Toggle a single feature flag in-memory."""
    from fireai.core.contracts import DEFAULT_FEATURE_FLAGS

    valid_flags = set(DEFAULT_FEATURE_FLAGS.keys())
    if body.flag not in valid_flags:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown feature flag '{body.flag}'. Valid flags: {sorted(valid_flags)}",
        )

    _FEATURE_FLAG_OVERRIDES[body.flag] = body.enabled
    logger.info("Feature flag '%s' set to %s by admin", body.flag[:50], body.enabled)
    return success(
        {
            "flag": body.flag,
            "enabled": body.enabled,
            "persisted": False,
            "note": "Override is in-memory. Restart will revert to env/defaults.",
        }
    )


@router.post("/settings/feature-flags")
async def update_feature_flags_batch(
    body: dict[str, Any],
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """Toggle one or multiple feature flags (supports batch dict updates)."""
    from fireai.core.contracts import DEFAULT_FEATURE_FLAGS

    valid_flags = set(DEFAULT_FEATURE_FLAGS.keys())

    # Support single {flag, enabled} or batch {FLAG_NAME: bool}
    if "flag" in body and "enabled" in body:
        flag_name = str(body["flag"])
        flag_val = bool(body["enabled"])
        if flag_name not in valid_flags:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown feature flag '{flag_name}'. Valid flags: {sorted(valid_flags)}",
            )
        _FEATURE_FLAG_OVERRIDES[flag_name] = flag_val
    else:
        for k, v in body.items():
            if k in valid_flags and isinstance(v, bool):
                _FEATURE_FLAG_OVERRIDES[k] = v

    return success(
        {
            "updated": list(_FEATURE_FLAG_OVERRIDES.keys()),
            "flags": {**DEFAULT_FEATURE_FLAGS, **_FEATURE_FLAG_OVERRIDES},
            "persisted": False,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RUNTIME & BOOTSTRAP REGISTRIES (for UI SettingsRegistry components)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/settings/runtime")
async def get_runtime_settings(_role: SystemConfigRole) -> dict[str, bool]:
    """Return runtime-editable boolean toggles."""
    from fireai.core.contracts import get_feature_flags

    flags = get_feature_flags()
    flags.update(_FEATURE_FLAG_OVERRIDES)
    return flags


@router.post("/settings/runtime")
async def update_runtime_settings(
    body: dict[str, bool],
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """Update runtime feature flags from the UI SettingsRegistry."""
    from fireai.core.contracts import DEFAULT_FEATURE_FLAGS

    valid_flags = set(DEFAULT_FEATURE_FLAGS.keys())
    for k, v in body.items():
        if k in valid_flags:
            _FEATURE_FLAG_OVERRIDES[k] = bool(v)
    return success({"updated": True, "flags": {**DEFAULT_FEATURE_FLAGS, **_FEATURE_FLAG_OVERRIDES}})


@router.get("/settings/bootstrap")
async def get_bootstrap_settings(_role: SystemConfigRole) -> dict[str, str]:
    """Return bootstrap/system configuration metadata."""
    return {
        "FIREAI_ENV": os.environ.get("FIREAI_ENV", "production"),
        "LOG_LEVEL": os.environ.get("FIREAI_LOG_LEVEL", "INFO"),
        "DATABASE_ENGINE": "PostgreSQL"
        if "postgres" in os.environ.get("DATABASE_URL", "").lower()
        else "SQLite",
        "SECURITY_PROFILE": "STRICT_RBAC_ENABLED",
        "MEEZA_GATEWAY": "ISOLATED_PRIMARY",
    }


@router.get("/settings/config")
async def get_settings_config(_role: SystemConfigRole) -> dict[str, str]:
    """Return a safe dictionary of environment variable names and values for read-only view."""
    safe_dict: dict[str, str] = {}
    for cat_vars in _SAFE_ENV_CATEGORIES.values():
        for var in cat_vars:
            val = os.environ.get(var)
            display = _resolve_env_var_value(var, val)
            safe_dict[var] = str(display) if display is not None else "Not set"
    return safe_dict


# ═══════════════════════════════════════════════════════════════════════════════
# ENV CONFIG CATEGORIES & RESOLVERS
# ═══════════════════════════════════════════════════════════════════════════════

_SAFE_ENV_CATEGORIES: dict[str, list[str]] = {
    "api": [
        "API_TIMEOUT",
        "RETRY_ATTEMPTS",
        "OPENAI_API_URL",
        "NVIDIA_BASE_URL",
    ],
    "database": [
        "DATABASE_URL",
        "DATABASE_POOL_SIZE",
        "DATABASE_TIMEOUT",
        "REDIS_URL",
        "REDIS_HOST",
        "REDIS_PORT",
        "REDIS_DB",
        "QDRANT_HOST",
        "QDRANT_PORT",
        "QDRANT_URL",
        "NEO4J_URI",
        "NEO4J_USERNAME",
        "NEO4J_DATABASE",
    ],
    "integration": [
        "SPECKLE_SERVER_URL",
        "LANGFUSE_HOST",
    ],
    "security": [
        "SESSION_COOKIE_SECURE",
        "AKAMAI_ENABLED",
        "AKAMAI_RATE_LIMIT_HEADER",
        "CORS_ORIGINS",
    ],
    "nvidia": [
        "NVIDIA_API_KEY",
        "NVIDIA_BASE_URL",
        "NVIDIA_MODEL",
    ],
    "langfuse": [
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_HOST",
    ],
    "akamai": [
        "AKAMAI_ENABLED",
        "AKAMAI_BLOCKED_COUNTRIES",
        "AKAMAI_ALLOWED_BOT_SCORE",
        "AKAMAI_RATE_LIMIT_HEADER",
    ],
    "pipeline": [
        "FIREAI_MAX_BATCH_SIZE",
        "FIREAI_LOG_LEVEL",
        "FIREAI_ENABLE_WAL",
        "FIREAI_COVERAGE_THRESHOLD_PCT",
        "AUTO_SAVE_REPORTS",
        "REPORT_FORMAT",
        "REPORT_QUALITY",
    ],
    "integrations": [
        "OPENAI_API_URL",
        "SPECKLE_SERVER_URL",
        "LANGFUSE_HOST",
        "LANGFUSE_PUBLIC_KEY",
    ],
    "cors": [
        "CORS_ORIGINS",
    ],
    "acoustic": [
        "AMBIENT_NOISE_DB",
        "SPL_DROP_PER_DOUBLING_DB",
        "MIN_SNR_DBA",
        "STROBE_SYNC_ENABLED",
        "STROBE_FLASH_RATE_HZ",
    ],
    "hydraulic": [
        "DEFAULT_FLUID_DENSITY_KG_M3",
        "DEFAULT_FLUID_VISCOSITY_PA_S",
        "DEFAULT_PIPE_ROUGHNESS_MM",
        "DEFAULT_C_FACTOR",
        "COLEBROOK_TOLERANCE",
        "MAX_SOLVER_ITERATIONS",
    ],
    "battery": [
        "AMBIENT_TEMPERATURE_C",
        "STANDBY_DURATION_HOURS",
        "ALARM_DURATION_MINUTES",
        "AGING_SAFETY_MARGIN_PCT",
        "BATTERY_DERATING_FACTOR",
    ],
    "cad": [
        "AUTOCAD_VERSION",
        "AUTOCAD_UNITS",
        "REVIT_VERSION",
        "REVIT_UNITS",
        "SPECKLE_SERVER_URL",
        "APS_ACTIVITY_ID",
    ],
}

_CATEGORY_LABELS: dict[str, str] = {
    "api": "API & Networking",
    "database": "Databases & Storage",
    "integration": "Integrations & Bridges",
    "security": "Security & Headers",
    "nvidia": "NVIDIA AI Engine",
    "langfuse": "Langfuse Observability",
    "akamai": "Akamai Edge Security",
    "pipeline": "Pipeline & Performance",
    "integrations": "Third-Party Integrations",
    "cors": "CORS & Allowed Origins",
    "acoustic": "Acoustic & Notification",
    "hydraulic": "Hydraulic & Darcy-Weisbach",
    "battery": "Battery Sizing & Derating",
    "cad": "CAD & Cloud Bridges",
}

_ENV_SETTING_METADATA: dict[str, dict[str, Any]] = {
    "API_TIMEOUT": {"label": "API Request Timeout (sec)", "type": "number", "default": "30"},
    "RETRY_ATTEMPTS": {"label": "API Retry Attempts", "type": "number", "default": "3"},
    "SESSION_COOKIE_SECURE": {
        "label": "Session Cookie Secure",
        "type": "boolean",
        "default": "true",
    },
    "NVIDIA_API_KEY": {"label": "NVIDIA API Key", "type": "secret", "default": ""},
    "NVIDIA_BASE_URL": {
        "label": "NVIDIA Base URL",
        "type": "url",
        "default": "https://integrate.api.nvidia.com/v1",
    },
    "NVIDIA_MODEL": {
        "label": "NVIDIA Model",
        "type": "string",
        "default": "nvidia/llama-3.1-nemotron-70b-instruct",
    },
    "LANGFUSE_SECRET_KEY": {"label": "Langfuse Secret Key", "type": "secret", "default": ""},
    "LANGFUSE_PUBLIC_KEY": {"label": "Langfuse Public Key", "type": "string", "default": ""},
    "LANGFUSE_HOST": {
        "label": "Langfuse Host URL",
        "type": "url",
        "default": "https://cloud.langfuse.com",
    },
    "AKAMAI_ENABLED": {"label": "Enable Akamai Headers", "type": "boolean", "default": "false"},
    "AKAMAI_BLOCKED_COUNTRIES": {
        "label": "Blocked Countries (ISO-2)",
        "type": "string",
        "default": "",
    },
    "AKAMAI_ALLOWED_BOT_SCORE": {
        "label": "Max Allowed Bot Score",
        "type": "number",
        "default": "30",
    },
    "AKAMAI_RATE_LIMIT_HEADER": {
        "label": "Forward Rate Limit Headers",
        "type": "boolean",
        "default": "true",
    },
    "DATABASE_URL": {
        "label": "Primary Database URL",
        "type": "string",
        "default": "sqlite:////app/data/digital_twin.db",
    },
    "DATABASE_POOL_SIZE": {"label": "Database Pool Size", "type": "number", "default": "20"},
    "DATABASE_TIMEOUT": {"label": "Database Timeout (sec)", "type": "number", "default": "30"},
    "REDIS_URL": {"label": "Redis Cache URL", "type": "string", "default": ""},
    "REDIS_HOST": {"label": "Redis Host", "type": "string", "default": "localhost"},
    "REDIS_PORT": {"label": "Redis Port", "type": "number", "default": "6379"},
    "REDIS_DB": {"label": "Redis DB Index", "type": "number", "default": "0"},
    "QDRANT_HOST": {"label": "Qdrant Vector DB Host", "type": "string", "default": ""},
    "QDRANT_PORT": {"label": "Qdrant Port", "type": "number", "default": "6333"},
    "QDRANT_URL": {"label": "Qdrant Cloud URL", "type": "url", "default": ""},
    "NEO4J_URI": {"label": "Neo4j Graph DB URI", "type": "url", "default": ""},
    "NEO4J_USERNAME": {"label": "Neo4j Username", "type": "string", "default": "neo4j"},
    "NEO4J_DATABASE": {"label": "Neo4j Database Name", "type": "string", "default": "neo4j"},
    "FIREAI_MAX_BATCH_SIZE": {"label": "Max Batch Size", "type": "number", "default": "500"},
    "FIREAI_LOG_LEVEL": {"label": "System Log Level", "type": "string", "default": "INFO"},
    "FIREAI_ENABLE_WAL": {"label": "Enable SQLite WAL Mode", "type": "boolean", "default": "true"},
    "FIREAI_COVERAGE_THRESHOLD_PCT": {
        "label": "NFPA 72 Coverage Threshold (%)",
        "type": "number",
        "default": "100.0",
    },
    "AUTO_SAVE_REPORTS": {
        "label": "Auto-Save Engineering Reports",
        "type": "boolean",
        "default": "true",
    },
    "REPORT_FORMAT": {"label": "Default Report Format", "type": "string", "default": "PDF"},
    "REPORT_QUALITY": {"label": "Report Resolution / Quality", "type": "string", "default": "HIGH"},
    "OPENAI_API_URL": {
        "label": "OpenAI Compatible API URL",
        "type": "url",
        "default": "https://api.openai.com/v1",
    },
    "SPECKLE_SERVER_URL": {
        "label": "Speckle Server URL",
        "type": "url",
        "default": "https://speckle.xyz",
    },
    # A10 FIX: REVIT_BRIDGE_URL / AUTOCAD_BRIDGE_PORT removed — these settings
    # had no consumers (the desktop bridge uses named pipes via the local
    # agent, not HTTP endpoints) and only misled operators into thinking a
    # direct bridge port existed.
    "CORS_ORIGINS": {
        "label": "Allowed CORS Origins",
        "type": "string",
        "default": "http://localhost:3000,http://localhost:5173",
    },
    "AMBIENT_NOISE_DB": {"label": "Ambient Noise Level (dBA)", "type": "number", "default": "65.0"},
    "SPL_DROP_PER_DOUBLING_DB": {
        "label": "SPL Drop Per Doubling (dB)",
        "type": "number",
        "default": "6.0",
    },
    "MIN_SNR_DBA": {
        "label": "Min Signal-to-Noise Ratio (dBA)",
        "type": "number",
        "default": "15.0",
    },
    "STROBE_SYNC_ENABLED": {"label": "Strobe Sync Enabled", "type": "boolean", "default": "true"},
    "STROBE_FLASH_RATE_HZ": {"label": "Strobe Flash Rate (Hz)", "type": "number", "default": "1.0"},
    "DEFAULT_FLUID_DENSITY_KG_M3": {
        "label": "Fluid Density (kg/m³)",
        "type": "number",
        "default": "1000.0",
    },
    "DEFAULT_FLUID_VISCOSITY_PA_S": {
        "label": "Fluid Viscosity (Pa·s)",
        "type": "number",
        "default": "0.001",
    },
    "DEFAULT_PIPE_ROUGHNESS_MM": {
        "label": "Pipe Roughness (mm)",
        "type": "number",
        "default": "0.045",
    },
    "DEFAULT_C_FACTOR": {"label": "Hazen-Williams C Factor", "type": "number", "default": "120.0"},
    "COLEBROOK_TOLERANCE": {
        "label": "Colebrook Solver Tolerance",
        "type": "number",
        "default": "1e-8",
    },
    "MAX_SOLVER_ITERATIONS": {"label": "Max Solver Iterations", "type": "number", "default": "100"},
    "AMBIENT_TEMPERATURE_C": {
        "label": "Battery Ambient Temp (°C)",
        "type": "number",
        "default": "25.0",
    },
    "STANDBY_DURATION_HOURS": {
        "label": "Standby Duration (Hours)",
        "type": "number",
        "default": "24.0",
    },
    "ALARM_DURATION_MINUTES": {
        "label": "Alarm Duration (Minutes)",
        "type": "number",
        "default": "5.0",
    },
    "AGING_SAFETY_MARGIN_PCT": {
        "label": "Battery Aging Margin (%)",
        "type": "number",
        "default": "20.0",
    },
    "BATTERY_DERATING_FACTOR": {
        "label": "Battery Derating Factor",
        "type": "number",
        "default": "0.85",
    },
    "AUTOCAD_VERSION": {"label": "AutoCAD Version", "type": "string", "default": "2024"},
    "AUTOCAD_UNITS": {"label": "AutoCAD Drawing Units", "type": "string", "default": "Millimeters"},
    "REVIT_VERSION": {"label": "Revit Version", "type": "string", "default": "2024"},
    "REVIT_UNITS": {"label": "Revit Drawing Units", "type": "string", "default": "Millimeters"},
    "APS_ACTIVITY_ID": {
        "label": "APS WorkItem Activity ID",
        "type": "string",
        "default": "BazSparkAutoCADBridge.DrawLayout",
    },
}

_BOOLEAN_LIKE = {
    "AUTO_SAVE_REPORTS",
    "SESSION_COOKIE_SECURE",
    "AKAMAI_ENABLED",
    "AKAMAI_RATE_LIMIT_HEADER",
    "FIREAI_ENABLE_WAL",
    "STROBE_SYNC_ENABLED",
}


def _resolve_env_var_value(var: str, value: str | None) -> Any:
    """Resolve safe display value with credential masking."""
    if var == "BAZSPARK_MASTER_ADMIN_TOKEN_SET":
        return bool(os.environ.get("BAZSPARK_MASTER_ADMIN_TOKEN"))

    if var.endswith("_URL") or var in {"DATABASE_URL", "REDIS_URL"}:
        if not value:
            return None
        if "@" in value:
            host_part = value.rsplit("@", 1)[-1]
            return f"***@{host_part}"
        return value

    if var in {
        "OPENAI_API_URL",
        "LANGFUSE_HOST",
        "LANGFUSE_PUBLIC_KEY",
        "SPECKLE_SERVER_URL",
    }:
        return value

    if var in _BOOLEAN_LIKE:
        return value.lower() in {"1", "true", "yes"} if value else False

    if re.search(r"(?i)(_KEY|_SECRET|_TOKEN|_PASSWORD)$", var) and var != "LANGFUSE_PUBLIC_KEY":
        if not value:
            return None
        return f"{value[:4]}***"

    return value


@router.get("/env-config")
async def get_env_config(_role: SystemConfigRole) -> dict[str, Any]:
    """Return categorized and structured environment configuration for the UI."""
    categories: dict[str, Any] = {}
    config_dict: dict[str, dict[str, Any]] = {}

    for cat_key, var_names in _SAFE_ENV_CATEGORIES.items():
        settings_list = []
        cat_config: dict[str, Any] = {}

        # Merge in any overridden variables for this category
        all_vars = list(var_names)
        if cat_key in _ENV_CONFIG_OVERRIDES:
            for ov_var in _ENV_CONFIG_OVERRIDES[cat_key]:
                if ov_var not in all_vars:
                    all_vars.append(ov_var)

        for var in all_vars:
            meta = _ENV_SETTING_METADATA.get(var, {})
            raw_env = os.environ.get(var)
            source = "env" if raw_env is not None else "default"
            val = raw_env if raw_env is not None else meta.get("default", "")

            # Check in-memory overrides
            if cat_key in _ENV_CONFIG_OVERRIDES and var in _ENV_CONFIG_OVERRIDES[cat_key]:
                val = _ENV_CONFIG_OVERRIDES[cat_key][var]
                source = "override"

            is_secret = meta.get("type") == "secret" or bool(
                re.search(r"(?i)(_KEY|_SECRET|_TOKEN|_PASSWORD)$", var)
                and var != "LANGFUSE_PUBLIC_KEY"
            )

            if isinstance(val, int | float | bool):
                resolved_display = val
            else:
                resolved_display = _resolve_env_var_value(var, str(val) if val != "" else None)
            display_str = str(resolved_display) if resolved_display is not None else ""

            cat_config[var] = resolved_display
            settings_list.append(
                {
                    "key": var,
                    "label": meta.get("label", var.replace("_", " ").title()),
                    "type": meta.get("type", "string"),
                    "value": display_str,
                    "is_set": raw_env is not None
                    or (cat_key in _ENV_CONFIG_OVERRIDES and var in _ENV_CONFIG_OVERRIDES[cat_key]),
                    "is_secret": is_secret,
                    "source": source,
                }
            )

        categories[cat_key] = {
            "label": _CATEGORY_LABELS.get(cat_key, cat_key.title()),
            "settings": settings_list,
        }
        config_dict[cat_key] = cat_config

    return success(
        {
            "categories": categories,
            "config": config_dict,
            "overridden_categories": list(_ENV_CONFIG_OVERRIDES.keys()),
            "note": "Overrides are in-memory. Restart reverts to env vars. Secrets are never exposed in plaintext.",
        }
    )


@router.put("/env-config")
async def update_env_config(
    body: EnvConfigUpdate,
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """Apply overrides to the environment configuration (in-memory)."""
    applied: dict[str, list[str]] = {}

    for category, overrides in body.overrides.items():
        if not re.match(r"^[a-zA-Z0-9_-]+$", category):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category name '{category}'. Only alphanumeric, hyphen, and underscore characters are permitted.",
            )

        if isinstance(overrides, dict):
            # Nested: { "database": { "DATABASE_POOL_SIZE": "30" } }
            if category not in _ENV_CONFIG_OVERRIDES:
                _ENV_CONFIG_OVERRIDES[category] = {}
            _ENV_CONFIG_OVERRIDES[category].update(overrides)
            applied[category] = list(overrides.keys())
        else:
            # Flat: { "DATABASE_POOL_SIZE": "30" } → locate category
            target_cat = "pipeline"
            for cat_k, vars_k in _SAFE_ENV_CATEGORIES.items():
                if category in vars_k:
                    target_cat = cat_k
                    break
            if target_cat not in _ENV_CONFIG_OVERRIDES:
                _ENV_CONFIG_OVERRIDES[target_cat] = {}
            _ENV_CONFIG_OVERRIDES[target_cat][category] = overrides
            applied.setdefault(target_cat, []).append(category)

    logger.info("Env config overrides applied: %s", applied)
    return success(
        {
            "applied": applied,
            "persisted": False,
            "note": "Overrides applied in-memory. Set deployment environment variables for permanent persistence.",
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DEDICATED ENGINEERING CALCULATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/settings/engineering-config")
async def get_engineering_config(_role: SystemConfigRole) -> dict[str, Any]:
    """Return all engineering calculation parameters, standards, and active thresholds."""
    return success(
        {
            "config": _LIVE_ENGINEERING_CONFIG.model_dump(),
            "metadata": {
                "acoustic": {
                    "standard": "NFPA 72-2022 Chapter 18",
                    "units": {
                        "ambient_noise_db": "dBA",
                        "spl_drop_per_doubling_db": "dB",
                        "min_snr_dba": "dBA",
                        "strobe_flash_rate_hz": "Hz",
                    },
                },
                "hydraulic": {
                    "standard": "NFPA 13-2022 / NFPA 12-2022 / NFPA 2001-2022",
                    "units": {
                        "default_fluid_density_kg_m3": "kg/m³",
                        "default_fluid_viscosity_pa_s": "Pa·s",
                        "default_pipe_roughness_mm": "mm",
                        "default_c_factor": "dimensionless",
                    },
                },
                "battery": {
                    "standard": "NFPA 72-2022 §10.6.7 / IEEE 485",
                    "units": {
                        "ambient_temperature_c": "°C",
                        "standby_duration_hours": "Hours",
                        "alarm_duration_minutes": "Minutes",
                        "aging_safety_margin_pct": "%",
                    },
                },
                "integration": {
                    "standard": "BIM / CAD Local IPC Bridge & FDS v6.8",
                    "units": {
                        "autocad_bridge_port": "TCP Port",
                        "fds_queue_timeout_seconds": "Seconds",
                    },
                },
            },
        }
    )


@router.put("/settings/engineering-config")
async def update_engineering_config(
    body: EngineeringConfigUpdate,
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """Validate and update engineering calculation and solver settings."""
    if body.acoustic is not None:
        _LIVE_ENGINEERING_CONFIG.acoustic = body.acoustic
    if body.hydraulic is not None:
        _LIVE_ENGINEERING_CONFIG.hydraulic = body.hydraulic
    if body.battery is not None:
        _LIVE_ENGINEERING_CONFIG.battery = body.battery
    if body.integration is not None:
        _LIVE_ENGINEERING_CONFIG.integration = body.integration

    logger.info("Engineering configuration updated by admin")
    return success(
        {
            "config": _LIVE_ENGINEERING_CONFIG.model_dump(),
            "message": "Engineering calculation parameters updated successfully.",
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DEDICATED CAD & CLOUD BRIDGE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/settings/cad-config")
async def get_cad_config(_role: SystemConfigRole) -> dict[str, Any]:
    """Return AutoCAD, Revit, and Cloud connector parameters with masked tokens."""
    masked_cloud = _LIVE_CAD_CONFIG.cloud.model_dump()
    if masked_cloud.get("speckle_token"):
        masked_cloud["speckle_token"] = f"{masked_cloud['speckle_token'][:4]}***"
    if masked_cloud.get("aps_client_secret"):
        masked_cloud["aps_client_secret"] = f"{masked_cloud['aps_client_secret'][:4]}***"

    return success(
        {
            "autocad": _LIVE_CAD_CONFIG.autocad.model_dump(),
            "revit": _LIVE_CAD_CONFIG.revit.model_dump(),
            "cloud": masked_cloud,
        }
    )


@router.put("/settings/cad-config")
async def update_cad_config(
    body: CadConfigUpdate,
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """Update CAD and Cloud bridge configuration."""
    if body.autocad is not None:
        _LIVE_CAD_CONFIG.autocad = body.autocad
    if body.revit is not None:
        _LIVE_CAD_CONFIG.revit = body.revit
    if body.cloud is not None:
        # Preserve existing secrets if new secret is omitted or masked
        if body.cloud.speckle_token and not body.cloud.speckle_token.endswith("***"):
            _LIVE_CAD_CONFIG.cloud.speckle_token = body.cloud.speckle_token
        if body.cloud.aps_client_secret and not body.cloud.aps_client_secret.endswith("***"):
            _LIVE_CAD_CONFIG.cloud.aps_client_secret = body.cloud.aps_client_secret

        _LIVE_CAD_CONFIG.cloud.speckle_server = body.cloud.speckle_server
        _LIVE_CAD_CONFIG.cloud.speckle_stream_id = body.cloud.speckle_stream_id
        _LIVE_CAD_CONFIG.cloud.aps_client_id = body.cloud.aps_client_id
        _LIVE_CAD_CONFIG.cloud.aps_activity_id = body.cloud.aps_activity_id

    logger.info("CAD and Cloud bridge configuration updated by admin")
    return success(
        {
            "message": "CAD & Cloud bridge configuration saved successfully.",
            "autocad": _LIVE_CAD_CONFIG.autocad.model_dump(),
            "revit": _LIVE_CAD_CONFIG.revit.model_dump(),
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# SECRET ROTATION & ADMIN TOKEN ROTATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/settings/secret-rotation/rotate")
async def rotate_secret(
    body: SecretRotationRequest,
    _role: SystemConfigRole,
) -> dict[str, Any]:
    """Rotate a security-sensitive secret (hot rotation with grace period)."""
    from fireai.core.secret_rotation import KeyRotator

    rotator = KeyRotator()
    key_name = _validate_rotatable_secret_name(body.key_name)

    if body.new_secret:
        if not body.new_secret.isalnum():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="new_secret must be alphanumeric (letters and digits only).",
            )
        new_secret = body.new_secret
        if _SAFE_SECRET_VALUE_RE.fullmatch(new_secret) is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="new_secret must be 32-4096 printable ASCII characters.",
            )
    else:
        new_secret = secrets.token_urlsafe(32)

    previous_secret = os.environ.get(key_name)
    if previous_secret:
        rotator.register(key_name, previous_secret)
        rotated, rotate_msg = rotator.rotate(key_name, previous_secret, new_secret)
    else:
        rotator.register(key_name, new_secret)
        rotated, rotate_msg = True, "Registered new key (no previous key to rotate from)."

    if not rotated:
        logger.error("Secret rotation FAILED for '%s': %s", key_name, rotate_msg)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Secret rotation rejected: {rotate_msg}",
        )

    _set_rotated_secret(key_name, new_secret)
    logger.info("Secret '%s' rotated successfully (hot rotation, grace period active)", key_name)

    return success(
        {
            "key_name": key_name,
            "rotated": True,
            "new_secret": new_secret,
            "warning": "Store this new secret securely. Update your deployment environment to persist across restarts.",
            "grace_period_seconds": 300,
        }
    )


@router.post("/settings/admin-token/rotate")
async def rotate_admin_token(_role: SystemConfigRole) -> dict[str, Any]:
    """Rotate the BAZSPARK_MASTER_ADMIN_TOKEN."""
    from fireai.core.secret_rotation import KeyRotator

    new_token = secrets.token_urlsafe(32)
    previous_token = os.environ.get("BAZSPARK_MASTER_ADMIN_TOKEN")

    rotator = KeyRotator()
    if previous_token:
        rotator.register("BAZSPARK_MASTER_ADMIN_TOKEN", previous_token)
        rotated, rotate_msg = rotator.rotate(
            "BAZSPARK_MASTER_ADMIN_TOKEN", previous_token, new_token
        )
    else:
        rotator.register("BAZSPARK_MASTER_ADMIN_TOKEN", new_token)
        rotated, rotate_msg = True, "Registered new admin token (no previous token to rotate from)."

    if not rotated:
        logger.error("Admin token rotation FAILED: %s", rotate_msg)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Admin token rotation rejected: {rotate_msg}",
        )

    _ADMIN_TOKEN_ENV_KEY = "BAZSPARK_MASTER_ADMIN_TOKEN"
    assert _ADMIN_TOKEN_ENV_KEY.isidentifier() and _ADMIN_TOKEN_ENV_KEY.isupper()
    os.environ[_ADMIN_TOKEN_ENV_KEY] = new_token

    logger.info("Admin token rotated successfully (hot rotation, grace period active)")
    return success(
        {
            "rotated": True,
            "new_token": new_token,
            "warning": "Store this token securely. Update your deployment environment to persist across restarts.",
            "grace_period_seconds": 300,
        }
    )
