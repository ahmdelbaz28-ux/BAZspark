# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
from __future__ import annotations

"""
fireai/core/spatial_engine/density_optimizer.py — Backward-Compatibility Shim.
=============================================================================
Re-exports canonical single-room and batch placement classes and constants
from `fireai.core.density_optimizer_v2` (SSOT).
"""

from fireai.core.density_optimizer_v2 import (
    COARSE_STEP,
    COVERAGE_SAFETY_FACTOR,
    DEFAULT_EPSILON,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_TIMEOUT_SECONDS,
    DENSITY_CAP_FACTOR,
    DETECTOR_RADIUS,
    MAX_SPACING_M,
    PLACEMENT_MARGIN,
    REMOVE_REDUNDANT_MAX_PASSES,
    VERIFY_STEP,
    WALL_MIN_M,
    BatchResult,
    DensityOptimizer,
    DensityOptimizerBatch,
    DensityOptimizerV2,
    DetectorLayout,
    Room,
    _hex_s_guarded,
    _optimize_room_worker,
    _predict_strategy_order,
)

__all__ = [
    "COARSE_STEP",
    "COVERAGE_SAFETY_FACTOR",
    "DEFAULT_EPSILON",
    "DEFAULT_MAX_ITERATIONS",
    "DEFAULT_TIMEOUT_SECONDS",
    "DENSITY_CAP_FACTOR",
    "DETECTOR_RADIUS",
    "MAX_SPACING_M",
    "PLACEMENT_MARGIN",
    "REMOVE_REDUNDANT_MAX_PASSES",
    "VERIFY_STEP",
    "WALL_MIN_M",
    "BatchResult",
    "DensityOptimizer",
    "DensityOptimizerBatch",
    "DensityOptimizerV2",
    "DetectorLayout",
    "Room",
    "_hex_s_guarded",
    "_optimize_room_worker",
    "_predict_strategy_order",
]
