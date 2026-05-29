"""
fireai.version — Single source of truth for package versioning.

This module MUST exist because fireai/__init__.py imports from it
at the top level. If this file is missing, the entire package
fails to import — even `import fireai; fireai.__version__` crashes.

SAFETY: Version information is critical for audit trails. Every
engineering report must include the exact engine version for
reproducibility and regulatory compliance.
"""

# ─── Semantic Version (PEP 440) ─────────────────────────────────────────────
__package_version__ = "56.0.0"

# ─── Internal Version Strings ────────────────────────────────────────────────
FIREAI_VERSION = "V56"
FIREAI_VERSION_FULL = "V56.0.0"


def build_version_header() -> dict:
    """Build a version header dict for inclusion in audit reports.

    Returns:
        dict with keys: version, full_version, engine_name, nfpa_standard
    """
    return {
        "engine_name": "FireAI",
        "version": __package_version__,
        "full_version": FIREAI_VERSION_FULL,
        "nfpa_standard": "NFPA 72-2022",
    }


__all__ = [
    "__package_version__",
    "FIREAI_VERSION",
    "FIREAI_VERSION_FULL",
    "build_version_header",
]
