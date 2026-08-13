"""backend/env_validator.py — Runtime Environment Validation Gate.

PURPOSE
    On FastAPI startup (lifespan), fail-fast verify that every REQUIRED
    environment variable needed for production operation is present and not
    left as a placeholder. This prevents the app from booting with silently
    missing integrations (the same class of bug that produced the auth router
    silent-drop in V193).

DESIGN
    - Pure function `validate_environment() -> list[Issue]` returning a list
      of issues. An empty list means "fully configured". Called once from
      `backend/app.py::lifespan` — if `FIREAI_ENV=production` (EXPLICITLY —
      see `assert_environment`) AND any hard issue exists, the app calls
      `raise RuntimeError(...)` and refuses to start. Otherwise (development,
      testing, CI runners that never declare an environment, e.g. the
      Playwright uvicorn job in ci.yml), only warnings are logged.
    - Variables are categorised:
        REQUIRED_HARD  → missing/placeholder = launch blocker (prod).
        REQUIRED_SOFT  → missing = warning only (works in dev / partial).
      This matches the live BAZspark deployment matrix where the HF Space
      runs the FastAPI backend while Vercel only serves the static frontend
      and proxies /api → HF Space.
    - Placeholder detection: treat the value as placeholder if it is empty OR
      it matches `<...>` / contains the literal "YOUR_" / "PLACEHOLDER".
    - NO secrets are ever logged in full — only the variable NAME and a
      truncated-masking summary (first 4 chars + "***").

USAGE
    from backend.env_validator import validate_environment, ValidationIssue
    issues = validate_environment()
    for issue in issues:
        logger.log(issue.level, "%s", issue)

PLACEHOLDER-LIST SOURCE OF TRUTH
    Keep the REQUIRED_HARD set in sync with `.env.production.example`. The
    number after each service is the section in the template.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Tuple

logger = logging.getLogger(__name__)

# ─── Placeholder detection ───────────────────────────────────────────────────
# A value is considered "still a placeholder" if any of these match.
_PLACEHOLDER_PATTERNS = (
    re.compile(r"^\s*$"),
    re.compile(r"^<[^>]+>\s*$"),                 # <PLACEHOLDER>
    re.compile(r"YOUR_[A-Z_]+"),                  # YOUR_FIREAI_API_KEY
    re.compile(r"\bPLACEHOLDER\b", re.IGNORECASE),
    re.compile(r"^\.\.\.+$"),                     # ".........."
)

# Known real-but-placeholder-looking prefixes inside the template that should
# ALSO count as placeholders (so an operator doesn't accidentally ship the
# template literal `<pk-lf-...>` as a real key).
_TEMPLATE_LITERAL_HINTS = (
    # Legacy defaults that shipped in older .env.example files (C-02/C-03/C-04)
    # — production must refuse to boot with any of these.
    "dev-fireai-key-local",
    "dev-session-secret-please-replace",
    "change-me-please",
    # Public test-only key from backend/tests/conftest.py (L-18) — must never
    # be used as a production credential.
    "test-api-key-for-testing-only",
    "pk-lf-...",
    "sk-lf-...",
    "napi_...",
    "re_...",
    "vcp_...",
    "github_pat_...",
    "hf_...",
    "cfut_...",
    "dtn_...",
    "csb_v1_...",
    "sb_secret_...",
    "sbp_...",
    "u1234567-...",
    "m1234567-...",
)


def _is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    v = value.strip()
    for pat in _PLACEHOLDER_PATTERNS:
        if pat.search(v):
            return True
    return any(hint in v for hint in _TEMPLATE_LITERAL_HINTS)


def _mask(value: str | None) -> str:
    """Return a safe masked preview of a value for diagnostic logs."""
    if value is None:
        return "<unset>"
    v = value.strip()
    if not v:
        return "<empty>"
    if _is_placeholder(v):
        return f"<placeholder:{v[:8] if len(v) > 8 else v}...>"
    if len(v) <= 6:
        return f"{v[:2]}***"
    return f"{v[:4]}*** (len={len(v)})"


class Severity(str, Enum):
    HARD = "HARD"   # launch blocker in production
    SOFT = "SOFT"   # warning only (degraded mode acceptable in dev)


@dataclass(frozen=True)
class ValidationIssue:
    name: str           # env var name
    severity: Severity
    message: str        # human readable diagnostic
    value_preview: str  # masked preview

    @property
    def level(self) -> int:
        return logging.ERROR if self.severity is Severity.HARD else logging.WARNING

    def __str__(self) -> str:  # for logs
        return f"[{self.severity}] {self.name}: {self.message} (value={self.value_preview})"


# ─── Variable registry ──────────────────────────────────────────────────────
# Each entry: (env_var_name, severity, validator)
# `validator` returns (ok: bool, message: str). A value of None is passed in
# for unset variables so validators can tailor the message.
_EnvValidator = Callable[[Optional[str]], Tuple[bool, str]]


def _present(value: str | None) -> tuple[bool, str]:
    """Default validator: presence + not-placeholder."""
    if _is_placeholder(value):
        return False, "missing or still a placeholder in .env.production"
    return True, "present"

def _cors_origins_present(value: str | None) -> tuple[bool, str]:
    """Presence validator for CORS_ORIGINS that also accepts the legacy
    CORS_ALLOWED_ORIGINS alias — mirrors backend/app.py backward-compat.
    """
    effective = value or os.environ.get("CORS_ALLOWED_ORIGINS")
    return _present(effective)


def _min_len(n: int) -> _EnvValidator:
    def _v(value: str | None) -> tuple[bool, str]:
        ok, msg = _present(value)
        if not ok:
            return ok, msg
        v = (value or "").strip()  # _present() guarantees non-empty when ok
        if len(v) < n:
            return False, f"too short (min {n} chars, got {len(v)})"
        return True, f"present, length={len(v)}"
    return _v


def _is_https(value: str | None) -> tuple[bool, str]:
    ok, msg = _present(value)
    if not ok:
        return ok, msg
    v = (value or "").strip()  # _present() guarantees non-empty when ok
    if not v.startswith("https://"):
        return False, "must start with https://"
    return True, "valid HTTPS URL"


def _bool_like(value: str | None) -> tuple[bool, str]:
    ok, msg = _present(value)
    if not ok:
        return ok, msg
    if (value or "").strip().lower() not in {"true", "false", "1", "0", "yes", "no"}:
        return False, "must be a boolean (true/false/1/0/yes/no)"
    return True, "boolean"


# Registry — single source of truth. Mirrors .env.production.example sections.
_REQUIRED_VARS: list[tuple[str, Severity, _EnvValidator]] = [
    # ── 0. Runtime ──
    ("FIREAI_ENV",            Severity.SOFT, _present),
    ("FIREAI_API_KEY",        Severity.HARD, _present),
    ("FIREAI_SESSION_SECRET", Severity.HARD, _min_len(43)),

    # ── 1. Database ──
    ("DATABASE_URL",          Severity.HARD, _present),

    # ── 2. Supabase Auth + REST ──
    # NOTE (audit P0-2 fix + self-critique M2): The backend currently uses
    # Supabase ONLY as a PostgreSQL connection pooler via DATABASE_URL (section 1).
    # The Supabase Python SDK (create_client) is NOT imported anywhere — none of
    # SUPABASE_URL, SUPABASE_ANON_KEY, or SUPABASE_SERVICE_ROLE_KEY are consumed
    # at runtime. All three downgraded from HARD to SOFT to prevent unnecessary
    # launch blockers. When Supabase Auth/REST SDK is implemented, upgrade all
    # back to HARD.
    ("SUPABASE_URL",              Severity.SOFT, _is_https),
    ("SUPABASE_ANON_KEY",         Severity.SOFT, _present),
    ("SUPABASE_SERVICE_ROLE_KEY", Severity.SOFT, _present),

    # ── 3. Langfuse ──
    ("LANGFUSE_PUBLIC_KEY", Severity.HARD, _present),
    ("LANGFUSE_SECRET_KEY", Severity.HARD, _present),
    ("LANGFUSE_HOST",       Severity.HARD, _is_https),

    # ── 4. NVIDIA LLM ──
    ("NVIDIA_API_KEY",  Severity.SOFT, _present),
    ("NVIDIA_BASE_URL", Severity.SOFT, _is_https),

    # ── 5. Resend ──
    # SOFT: email is a feature — the API serves fine without it.
    # NOTE (audit P1-1): Resend Python SDK is not yet imported in backend.
    # RESEND_API_KEY is validated here but no code sends emails yet.
    # When email sending is implemented, add "from resend import Resend" and
    # document the integration in ARCHITECTURE.md.
    ("RESEND_API_KEY", Severity.SOFT, _present),

    # ── 7. Autodesk APS ──
    ("APS_CLIENT_ID",     Severity.SOFT, _present),
    ("APS_CLIENT_SECRET", Severity.SOFT, _present),

    # ── 8. Vercel ──
    ("VERCEL_DEPLOY_TOKEN", Severity.SOFT, _present),
    ("VERCEL_PROJECT_ID",   Severity.SOFT, _present),

    # ── 9. Hugging Face ──
    # SOFT: only needed for HF sync from CI, not for the API runtime.
    ("HF_TOKEN", Severity.SOFT, _present),

    # ── 10. GitHub ──
    # SOFT: only needed for CI/deploy automation, not for the API runtime.
    ("GH_PAT",        Severity.SOFT, _present),
    ("GH_REPO",       Severity.SOFT, _present),
    ("SONAR_TOKEN",   Severity.SOFT, _present),

    # ── 11. SonarCloud ──
    ("SONAR_HOST_URL",    Severity.SOFT, _is_https),
    ("SONAR_PROJECT_KEY", Severity.SOFT, _present),

    # ── 12. Cloudflare ──
    ("CLOUDFLARE_API_TOKEN", Severity.SOFT, _present),

    # ── 13. Daytona ──
    ("DAYTONA_API_TOKEN", Severity.SOFT, _present),

    # ── 14. CodeSandbox ──
    ("CODESANDBOX_TOKEN", Severity.SOFT, _present),

    # ── 16. CORS / Security ──
    ("CORS_ORIGINS", Severity.HARD, _cors_origins_present),

    # ── 17. HMAC / Webhook / Admin secrets (P0-4 launch blockers) ──
    # All HARD: a missing value means silent security downgrade (see
    # fireai/core/qomn_kernel.py P0-1) or an unauthenticated webhook/
    # admin path. Mirrors .env.production.example section 17/20.
    ("AUDIT_HMAC_KEY",                    Severity.HARD, _min_len(32)),
    ("FIREAI_QOMN_HMAC_KEY",              Severity.HARD, _min_len(32)),
    ("QOMN_AUDIT_SECRET_KEY",             Severity.HARD, _min_len(32)),
    ("FDS_WEBHOOK_SECRET",                Severity.HARD, _present),
    ("BAZSPARK_MASTER_ADMIN_TOKEN",       Severity.HARD, _present),
    ("FIREAI_VISION_KEY_ENCRYPTION_KEY",  Severity.HARD, _min_len(32)),
    ("MEEZA_WEBHOOK_HMAC_SECRET",         Severity.HARD, _present),
    ("TRUSTED_PROXIES",                   Severity.HARD, _present),

    # ── Additional SOFT checks (audit P1-7 fix) ──
    # These variables from .env.production.example were not previously validated.
    # Added as SOFT so operators get startup warnings without blocking launch.
    ("NEON_DATABASE_URL",         Severity.SOFT, _present),       # fallback DB
    ("GEMINI_API_KEY",            Severity.SOFT, _present),       # LLM fallback embeddings
    ("OPENAI_API_KEY",            Severity.SOFT, _present),       # Mem0 embeddings
    ("ZENMUX_API_KEY",            Severity.SOFT, _present),       # primary LLM provider
    ("RESEND_FROM_EMAIL",         Severity.SOFT, _present),       # email from address
    ("QOMN_AUDIT_LOG_PATH",       Severity.SOFT, _present),       # audit log file path
    ("APS_WEBHOOK_URL",           Severity.SOFT, _is_https),      # APS webhook callback
    ("VERCEL_DEPLOY_HOOK_URL",    Severity.SOFT, _is_https),      # Vercel auto-deploy
    ("UPTIMEROBOT_USER_KEY",      Severity.SOFT, _present),       # keep-awake heartbeat
    ("UPTIMEROBOT_MONITOR_KEY",   Severity.SOFT, _present),       # keep-awake monitor

    # ── Security / Feature Flags (self-critique M1) ──
    # These flags affect security posture. SOFT validation warns operators if
    # they are misconfigured (e.g. CSRF disabled in prod) without blocking launch.
    ("FIREAI_ENV_VALIDATION",  Severity.SOFT, _present),       # strict/warn escape hatch
    ("FIREAI_CSRF_DISABLED",   Severity.SOFT, _bool_like),     # CSRF double-submit toggle
    ("AKAMAI_ENABLED",         Severity.SOFT, _bool_like),     # Akamai edge middleware
    ("CF_ENABLED",             Severity.SOFT, _bool_like),     # Cloudflare middleware
    ("LANGFUSE_ENABLED",       Severity.SOFT, _bool_like),     # LLM observability toggle
]


def validate_environment() -> list[ValidationIssue]:
    """Validate the current process environment against the required registry.

    Returns:
        list of ValidationIssue. Empty list ⇒ fully configured.
        HARD issues are launch blockers in production.
    """
    issues: list[ValidationIssue] = []

    for name, severity, validator in _REQUIRED_VARS:
        value = os.environ.get(name)
        ok, message = validator(value)
        if not ok:
            issues.append(
                ValidationIssue(
                    name=name,
                    severity=severity,
                    message=message,
                    value_preview=_mask(value),
                )
            )

    # Extra policy check: no wildcard CORS in production.
    cors = os.environ.get("CORS_ORIGINS", "") or os.environ.get("CORS_ALLOWED_ORIGINS", "")
    if "*" in (cors.split(",") if cors else []):
        issues.append(
            ValidationIssue(
                name="CORS_ORIGINS",
                severity=Severity.HARD,
                message="wildcard '*' is forbidden in production — list explicit origins",
                value_preview=_mask(cors),
            )
        )

    return issues


def _detect_production_indicators() -> list[str]:
    """Detect environment indicators suggesting production deployment.

    When FIREAI_ENV is unset and defaults to "production" (V246 fail-safe),
    this function checks for heuristics that confirm or contradict that
    assumption. Used by assert_environment() to log a warning when the
    default may not match the actual deployment context.
    """
    indicators = []
    db_url = os.environ.get("DATABASE_URL", "")
    cors = os.environ.get("CORS_ORIGINS", "") or os.environ.get("CORS_ALLOWED_ORIGINS", "")

    # Production database indicators
    prod_db_markers = ("supabase.com", "neon.tech", "aws-0", "pooler.")
    if any(m in db_url for m in prod_db_markers):
        indicators.append(f"DATABASE_URL contains production host ({next(m for m in prod_db_markers if m in db_url)})")

    # Production CORS indicators
    prod_cors_markers = ("vercel.app", "hf.space", "huggingface.co")
    if any(m in cors for m in prod_cors_markers):
        indicators.append(f"CORS_ORIGINS contains production origin ({next(m for m in prod_cors_markers if m in cors)})")

    return indicators


def assert_environment(prod_mode: bool | None = None) -> None:
    """Run validation and react.

    - Logs EVERY issue (HARD at ERROR, SOFT at WARNING).
    - In production (or when prod_mode=True), HARD issues raise RuntimeError
      → app refuses to start. SOFT issues only warn.
    - In development, both HARD and SOFT only warn.
    - V246 FAIL-SAFE: default is "production" — a safety-critical fire alarm
      system MUST fail closed. If FIREAI_ENV is unset, assume production
      (strictest posture). This is consistent with 12+ other files across
      the codebase (security_middleware, csp, session_secret, akamai,
      cloudflare, webhook_service, qomn_self_healing_engine, etc.) that
      all use default="production" per the V246 hardening.
    - CI COMPATIBILITY: tests set FIREAI_ENV=development in conftest.py,
      so this default does NOT block CI. For CI jobs that run uvicorn
      without conftest (e.g. Playwright E2E), set FIREAI_ENV=development
      or FIREAI_ENV_VALIDATION=warn.
    - OPERATIONS ESCAPE HATCH: set FIREAI_ENV_VALIDATION=warn to demote HARD
      issues to warnings instead of a launch blocker. Default is "strict"
      (fail-closed). This protects a live deployment from an outage while
      missing secrets are being rotated — the missing variables are still
      logged loudly, and the integration-diagnostic CI job still gates them.
    """
    if prod_mode is None:
        # V246 fail-safe: default "production" — mirrors config.py, app.py,
        # and all 12+ V246-hardened files across the codebase.
        fireai_env = os.getenv("FIREAI_ENV")
        if fireai_env is None:
            # FIREAI_ENV is UNSET — we're using the default. Log which default.
            prod_indicators = _detect_production_indicators()
            dev_indicators = []
            db_url = os.environ.get("DATABASE_URL", "")
            if "localhost" in db_url or "sqlite" in db_url.lower():
                dev_indicators.append("DATABASE_URL points to localhost/sqlite")

            if prod_indicators and not dev_indicators:
                logger.info(
                    "env_validator: FIREAI_ENV unset → defaulting to production "
                    "(V246 fail-safe). Production indicators detected: %s",
                    ", ".join(prod_indicators),
                )
            elif dev_indicators and not prod_indicators:
                logger.warning(
                    "env_validator: FIREAI_ENV unset → defaulting to production "
                    "(V246 fail-safe), BUT development indicators detected: %s. "
                    "Set FIREAI_ENV=development explicitly to avoid this warning.",
                    ", ".join(dev_indicators),
                )
            else:
                logger.info(
                    "env_validator: FIREAI_ENV unset → defaulting to production "
                    "(V246 fail-safe). Set FIREAI_ENV=development for dev mode.",
                )
        prod_mode = (fireai_env or "production").lower() in ("production", "prod")

    issues = validate_environment()
    if not issues:
        logger.info("env_validator: all %d required variables present ✓",
                    len(_REQUIRED_VARS))
        return

    hard = [i for i in issues if i.severity is Severity.HARD]
    soft = [i for i in issues if i.severity is Severity.SOFT]

    for issue in soft:
        logger.warning("env_validator %s", issue)
    for issue in hard:
        logger.error("env_validator %s", issue)

    logger.info("env_validator: %d HARD, %d SOFT issues", len(hard), len(soft))

    validation_mode = os.getenv("FIREAI_ENV_VALIDATION", "strict").strip().lower()
    if prod_mode and hard and validation_mode not in ("warn", "soft", "false", "0"):
        preview = "\n  - ".join(str(i) for i in hard)
        raise RuntimeError(
            f"BAZspark environment validation FAILED in production mode — "
            f"{len(hard)} required variable(s) missing/invalid:\n  - {preview}\n"
            "Set them in Vercel/HF Space/GitHub Secrets (see "
            ".env.production.example). The app will NOT start until fixed."
            "To start anyway while rotating secrets, set "
            "FIREAI_ENV_VALIDATION=warn (degraded mode — HARD vars become "
            "warnings only)."
        )
    if prod_mode and hard and validation_mode in ("warn", "soft", "false", "0"):
        logger.warning(
            "env_validator: FIREAI_ENV_VALIDATION=%s — starting in DEGRADED "
            "mode with %d HARD issue(s); integrations affected will not work "
            "until the missing variables are provided.", validation_mode, len(hard)
        )
