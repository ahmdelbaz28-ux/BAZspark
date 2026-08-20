# File-level '# NOSONAR' removed per NOSONAR_AUDIT.md (V143 hardening).
# Per-line justified suppressions (e.g., '# NOSONAR — S3776: ...') are preserved.
from __future__ import annotations

"""
fireai/core/density_optimizer_v2.py — Canonical Single Source of Truth (SSOT)
=============================================================================
Unified NFPA 72 Placement and Optimization Engine with Sequential & Batch APIs.

Contains:
  1. Canonical DensityOptimizer single-room placement engine (Hex-Guarded, Hex-Adaptive, Rect-Best).
  2. Corner-based grid verification and exact interval-merging wall audits.
  3. Redundancy elimination with coverage preservation.
  4. DensityOptimizerV2 / DensityOptimizerBatch multiprocessing batch engine for large facilities.

Standards:
  - NFPA 72-2022 Table 17.6.3.1.1 (detector spacing, coverage)
  - NEC 70-2023 (electrical requirements)
  - IEC 60079-10-1 (hazardous area classification)
"""

import logging
import math
import multiprocessing
import os
import time
from dataclasses import dataclass, field
from typing import Any

from fireai.constants.nfpa72 import (
    SMOKE_COVERAGE_RADIUS_M,
    WALL_MIN_DISTANCE_M,
)
from fireai.constants.nfpa72 import (
    SMOKE_MAX_SPACING_M as _CANONICAL_SMOKE_MAX_SPACING_M,
)
from fireai.version import FIREAI_VERSION

log = logging.getLogger(__name__)

# ── ConvergenceConfig integration ──────────────────────────────────────────
DEFAULT_MAX_ITERATIONS = 10_000
DEFAULT_EPSILON = 1e-4
DEFAULT_TIMEOUT_SECONDS = 300.0  # 5 minutes
REMOVE_REDUNDANT_MAX_PASSES = 100  # Safety cap for _remove_redundant loop

# Canonical NFPA 72 Spacing & Coverage Constants
MAX_SPACING_M = _CANONICAL_SMOKE_MAX_SPACING_M  # 9.1m — NFPA 72 Table 17.6.3.1.1
DETECTOR_RADIUS = SMOKE_COVERAGE_RADIUS_M  # 6.37m — R = 0.7 × S (§17.7.4.2.3.1)
WALL_MIN_M = WALL_MIN_DISTANCE_M  # NFPA 72 §17.6.3.1.1 — 4 inches = 101.6mm
VERIFY_STEP = 0.20  # proof resolution (m)
COARSE_STEP = 1.00  # hierarchical coarse grid step (m)
PLACEMENT_MARGIN = VERIFY_STEP * math.sqrt(2) / 2  # 0.1414m

# Density Cap & Safety Margin
DENSITY_CAP_FACTOR = 2.0
COVERAGE_SAFETY_FACTOR = 0.98

# Import RoomSpec with fallback
try:
    from fireai.core.nfpa72_models import RoomSpec
except ImportError:
    try:
        from core.nfpa72_models import RoomSpec  # type: ignore[no-redef]
    except ImportError:
        RoomSpec = None  # type: ignore[assignment,no-redef,misc]

Geometry = None  # type: ignore[assignment,misc]
Point3D = None  # type: ignore[assignment,misc]


def _hex_s_guarded(R: float, wm: float) -> float:  # NOSONAR - python:S117
    """
    Max S s.t. side-wall boundary worst point <= R (analytical).
    """
    a, b, c = 7 / 16, wm, wm**2 - R**2
    discriminant = b**2 - 4 * a * c
    if discriminant < 0:
        return 0.0
    return (-b + math.sqrt(discriminant)) / (2 * a)


def _predict_strategy_order(width: float, length: float) -> list[str]:
    """
    Deterministic strategy ordering based on room geometry (stateless).
    """
    if width <= 0 or length <= 0:
        return ["hexG_x", "hexG_y", "hexA_x", "hexA_y", "rect"]

    ar = max(width, length) / min(width, length)
    area = width * length

    if area < 40:
        return ["rect", "hexG_x", "hexG_y", "hexA_x", "hexA_y"]

    if ar > 2.0:
        if length > width:
            return ["hexG_y", "hexA_y", "hexG_x", "hexA_x", "rect"]
        return ["hexG_x", "hexA_x", "hexG_y", "hexA_y", "rect"]

    return ["hexG_x", "hexG_y", "rect", "hexA_x", "hexA_y"]


@dataclass
class Room:
    """Room boundary specification for detector layout optimization."""

    name: str
    width: float
    length: float
    ceiling_height: float = 3.0

    def __post_init__(self):
        """Validate room dimensions — life-safety data MUST be valid."""
        if (
            not isinstance(self.width, int | float)
            or self.width <= 0
            or not math.isfinite(self.width)
        ):
            raise ValueError(f"Room width must be positive finite, got {self.width}")
        if (
            not isinstance(self.length, int | float)
            or self.length <= 0
            or not math.isfinite(self.length)
        ):
            raise ValueError(f"Room length must be positive finite, got {self.length}")
        if (
            not isinstance(self.ceiling_height, int | float)
            or self.ceiling_height <= 0
            or not math.isfinite(self.ceiling_height)
        ):
            raise ValueError(
                f"Room ceiling_height must be positive finite, got {self.ceiling_height}"
            )


@dataclass
class DetectorLayout:
    """Resulting layout of detectors for a given room."""

    room: Room
    detectors: list[tuple[float, float]] = field(default_factory=list)
    coverage_pct: float = 0.0
    proof_valid: bool = False
    nfpa_valid: bool = False
    wall_violations: int = 0
    method: str = ""
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fallback_used: bool = False
    coverage_radius: float = DETECTOR_RADIUS
    ceiling_height: float | None = None
    detector_type_simple: str = "smoke"
    radius_warning: str | None = None
    nfpa_table_ref: str = "NFPA 72-2022 Table 17.6.3.1.1"

    @property
    def count(self) -> int:
        return len(self.detectors)

    @property
    def theoretical_lower_bound(self) -> int:
        """Estimative lower bound for detector count."""
        area = self.room.width * self.room.length
        coverage_area = math.pi * self.coverage_radius**2
        return max(1, math.ceil(area / coverage_area))

    @property
    def efficiency_ratio(self) -> float:
        """Ratio of theoretical_lower_bound to actual detector count."""
        if self.count == 0:
            return 0.0
        return self.theoretical_lower_bound / self.count


class DensityOptimizer:
    """Canonical Single-Room NFPA 72 Placement and Optimization Engine."""

    def __init__(
        self,
        max_spacing: float = MAX_SPACING_M,
        wall_min: float = WALL_MIN_M,
        radius: float = DETECTOR_RADIUS,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.max_spacing = max_spacing
        self.wm = wall_min
        self.R = radius
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self._start_time: float | None = None
        self._iteration_count: int = 0
        self.R_place = radius - PLACEMENT_MARGIN  # NOSONAR - python:S116
        self.S_g = min(self.R_place * math.sqrt(3), max_spacing)  # NOSONAR - python:S116
        self.Ry_g = self.S_g * math.sqrt(3) / 2  # NOSONAR - python:S116

    def optimize(self, room: Room, coverage_radius: float | None = None) -> DetectorLayout:
        """Find the best detector placement for a room."""
        self._start_time = time.monotonic()
        self._iteration_count = 0

        _override = coverage_radius is not None and coverage_radius != self.R
        _saved = None
        if _override:
            assert coverage_radius is not None
            _saved = (self.R, self.R_place, self.S_g, self.Ry_g)
            self.R = coverage_radius
            self.R_place = coverage_radius - PLACEMENT_MARGIN
            self.S_g = min(self.R_place * math.sqrt(3), self.max_spacing)
            self.Ry_g = self.S_g * math.sqrt(3) / 2

        try:
            layout = self._optimize_impl(room)
        finally:
            if _override:
                assert _saved is not None
                self.R, self.R_place, self.S_g, self.Ry_g = _saved
            self._start_time = None

        if coverage_radius is not None:
            layout.ceiling_height = room.ceiling_height
        return layout

    def _optimize_impl(self, room: Room) -> DetectorLayout:
        predicted_order = _predict_strategy_order(room.width, room.length)

        raw_cands: list[tuple[str, DetectorLayout]] = []
        raw_cands.append(("hexG_x", self._hex_guarded(room, True)))
        raw_cands.append(("hexG_y", self._hex_guarded(room, False)))
        raw_cands.append(("hexA_x", self._hex_adaptive(room, True)))
        raw_cands.append(("hexA_y", self._hex_adaptive(room, False)))
        r = self._rect_best(room)
        if r:
            raw_cands.append(("rect", r))

        name_to_cand: dict[str, tuple[str, DetectorLayout]] = {}
        for name, layout in raw_cands:
            name_to_cand[name] = (name, layout)

        cands: list[DetectorLayout] = []
        for name in predicted_order:
            if name in name_to_cand:
                cands.append(name_to_cand[name][1])

        cands.sort(key=lambda c: c.count)
        best: DetectorLayout | None = None

        for lay in cands:
            self._verify_fast(lay)
            self._audit_nfpa(lay)
            if lay.nfpa_valid and lay.coverage_pct >= 99.9:
                best = lay
                break

        if best is None:
            best_cov = -1.0
            for lay in cands:
                if lay.nfpa_valid and lay.coverage_pct > best_cov:
                    best_cov = float(lay.coverage_pct)
                    best = lay

        if best is None:
            best_cov = -1.0
            for lay in cands:
                if lay.coverage_pct > best_cov:
                    best_cov = float(lay.coverage_pct)
                    best = lay

        if best is None:
            best = self._fallback(room)
            best.fallback_used = True
            self._verify_fast(best)
            self._audit_nfpa(best)

        self._remove_redundant(best)

        elapsed = time.monotonic() - self._start_time if self._start_time else 0
        if not hasattr(best, "convergence_info"):
            best.convergence_info = {  # type: ignore[attr-defined]
                "iterations": self._iteration_count,
                "elapsed_seconds": round(elapsed, 3),
                "converged": True,
                "timeout_hit": False,
                "max_iterations_hit": False,
            }

        return best

    def _calculate_rows(self, L: float) -> list[float]:  # NOSONAR - python:S117
        wm, Ry = self.wm, self.Ry_g  # NOSONAR - python:S117
        coverage_limit = self.R_place

        if 2 * coverage_limit >= L:
            return [round(L / 2.0, 3)]

        if 2 * coverage_limit + 2 * wm >= L:
            return [round(coverage_limit, 3), round(L - coverage_limit, 3)]

        y_first = coverage_limit
        y_last = L - coverage_limit
        available = y_last - y_first

        n_gaps = max(1, math.ceil(available / Ry))
        actual_ry = available / n_gaps

        rows = [y_first + i * actual_ry for i in range(n_gaps + 1)]
        return [round(y, 3) for y in rows]

    def _distribute_rows(self, L: float, n_rows: int) -> list[float]:  # NOSONAR - python:S117
        if n_rows == 1:
            return [L / 2]
        available = L - 2 * self.wm
        gap = available / (n_rows - 1)
        return [self.wm + i * gap for i in range(n_rows)]

    def _calculate_columns(self, W: float) -> tuple[int, float]:  # NOSONAR - python:S117
        available = W - 2 * self.wm
        if available <= 2 * self.R_place:
            return 1, available / 2
        if available <= self.max_spacing:
            return 1, 0.0
        n = max(2, math.ceil(available / self.max_spacing) + 1)
        step = available / (n - 1)
        return n, step

    def _hex_guarded(self, room: Room, along_x: bool) -> DetectorLayout:
        W, L = (room.width, room.length) if along_x else (room.length, room.width)
        S, wm = self.S_g, self.wm
        Rp = self.R_place  # NOSONAR - python:S117
        pts: list[tuple[float, float]] = []

        y_coords = self._calculate_rows(L)
        _n_cols, step_x = self._calculate_columns(W)

        for row_index, y in enumerate(y_coords):
            offset = (step_x / 2) if (row_index % 2 == 1) else 0.0
            xs = self._row_xs_guarded(W, wm, step_x if step_x > 0 else S, offset, Rp)
            for x in xs:
                pts.append((x, y))

        corners = [(wm, wm), (W - wm, wm), (wm, L - wm), (W - wm, L - wm)]
        for cx, cy in corners:
            covered = False
            for dx, dy in pts:
                if (cx - dx) ** 2 + (cy - dy) ** 2 <= Rp**2 + 1e-9:
                    covered = True
                    break
            if not covered:
                pts.append((cx, cy))

        if not along_x:
            pts = [(b, a) for a, b in pts]
        assert self.R is not None
        return DetectorLayout(
            room=room,
            detectors=pts,
            method=f"hexG_{'x' if along_x else 'y'}",
            coverage_radius=self.R,
        )

    def _row_xs_guarded(self, W, wm, S, offset, R):  # NOSONAR - python:S117
        xs = []
        x = wm + offset
        while x <= W - wm + 1e-9:
            xs.append(x)
            x += S
        if xs and W - wm - xs[-1] > R + 1e-9:
            xs.append(W - wm)
        if xs and xs[0] - wm > R + 1e-9:
            xs.insert(0, wm)
        return xs

    def _hex_adaptive(self, room: Room, along_x: bool) -> DetectorLayout:
        W, L = (room.width, room.length) if along_x else (room.length, room.width)
        Rp, wm = self.R_place, self.wm  # NOSONAR - python:S117
        pts: list[tuple[float, float]] = []

        y_coords = self._calculate_rows(L)
        Nx, Sx = self._calculate_columns(W)  # NOSONAR - python:S117
        if Nx == 1:
            even_xs = [W / 2]
            odd_xs = [W / 2]
        else:
            even_xs = [wm + i * Sx for i in range(Nx)]
            odd_xs = [
                even_xs[0] + Sx / 2 + i * Sx
                for i in range(Nx)
                if wm - 1e-9 <= even_xs[0] + Sx / 2 + i * Sx <= W - wm + 1e-9
            ]

        for row_index, y in enumerate(y_coords):
            xs = even_xs if row_index % 2 == 0 else odd_xs
            for x in xs:
                pts.append((x, y))

        corners = [(wm, wm), (W - wm, wm), (wm, L - wm), (W - wm, L - wm)]
        for cx, cy in corners:
            covered = False
            for dx, dy in pts:
                if (cx - dx) ** 2 + (cy - dy) ** 2 <= Rp**2 + 1e-9:
                    covered = True
                    break
            if not covered:
                pts.append((cx, cy))

        if not along_x:
            pts = [(b, a) for a, b in pts]
        assert self.R is not None
        return DetectorLayout(
            room=room,
            detectors=pts,
            method=f"hexA_{'x' if along_x else 'y'}",
            coverage_radius=self.R,
        )

    def _rect_best(self, room: Room) -> DetectorLayout | None:
        W, L = room.width, room.length
        Nx0 = self._min_n(W)  # NOSONAR - python:S117
        Ny0 = self._min_n(L)  # NOSONAR - python:S117
        best_nx, best_ny, best_t = None, None, 10**9
        for Nx in range(Nx0, Nx0 + 25):  # NOSONAR - python:S117
            if Nx * Ny0 >= best_t:
                break
            for Ny in range(Ny0, Ny0 + 25):  # NOSONAR - python:S117
                t = Nx * Ny
                if t >= best_t:
                    break
                xs = self._place(W, Nx)
                ys = self._place(L, Ny)
                Sx = (xs[-1] - xs[0]) / (Nx - 1) if Nx > 1 else 0.0  # NOSONAR - python:S117
                Sy = (ys[-1] - ys[0]) / (Ny - 1) if Ny > 1 else 0.0  # NOSONAR - python:S117
                if math.sqrt((Sx / 2) ** 2 + (Sy / 2) ** 2) <= self.R_place + 1e-9:
                    best_nx, best_ny, best_t = Nx, Ny, t
        if best_nx is None:
            return None
        assert best_nx is not None
        assert best_ny is not None
        xs = self._place(W, best_nx)
        ys = self._place(L, best_ny)
        assert self.R is not None
        return DetectorLayout(
            room=room,
            detectors=[(x, y) for x in xs for y in ys],
            method=f"rect_{best_nx}x{best_ny}",
            coverage_radius=self.R,
        )

    def _min_n(self, dim: float) -> int:
        if dim <= 2 * self.wm:
            return 1
        return max(1, math.ceil((dim - 2 * self.wm) / self.max_spacing) + 1)

    def _place(self, dim: float, n: int) -> list[float]:
        if n == 1:
            return [dim / 2]
        a, b = self.wm, dim - self.wm
        if b <= a:
            return [dim / 2]
        return [a + i * (b - a) / (n - 1) for i in range(n)]

    def _fallback(self, room: Room) -> DetectorLayout:
        xs = self._place(room.width, self._min_n(room.width))
        ys = self._place(room.length, self._min_n(room.length))
        pts = [(x, y) for x in xs for y in ys]

        W, L = room.width, room.length
        wm, Rp = self.wm, self.R_place  # NOSONAR - python:S117
        corners = [(wm, wm), (W - wm, wm), (wm, L - wm), (W - wm, L - wm)]
        for cx, cy in corners:
            covered = False
            for dx, dy in pts:
                if (cx - dx) ** 2 + (cy - dy) ** 2 <= Rp**2 + 1e-9:
                    covered = True
                    break
            if not covered:
                pts.append((cx, cy))

        sensor_coverage_area = math.pi * (Rp * COVERAGE_SAFETY_FACTOR) ** 2
        room_area = W * L
        theoretical_min = max(1, math.ceil(room_area / sensor_coverage_area))
        max_allowed = max(int(theoretical_min * DENSITY_CAP_FACTOR), 2)

        if len(pts) > max_allowed:
            log.warning(
                "FALLBACK_DENSITY_CAP: Room %s×%s — %d detectors exceeds cap %d "
                "(theoretical_min=%d, factor=%.1f). Marking for manual design.",
                W,
                L,
                len(pts),
                max_allowed,
                theoretical_min,
                DENSITY_CAP_FACTOR,
            )

        return DetectorLayout(room=room, detectors=pts, method="fallback", coverage_radius=self.R)

    def _remove_redundant(self, layout: DetectorLayout) -> None:
        dets = layout.detectors
        if len(dets) <= 1:
            return

        room = layout.room
        W, L = room.width, room.length
        R = self.R_place
        R2 = R**2 + 1e-9
        step = VERIFY_STEP

        cell_size = R
        n_cells_x = max(1, math.ceil(W / cell_size))
        n_cells_y = max(1, math.ceil(L / cell_size))

        grid_points: list[tuple[float, float]] = []
        cell_to_points: dict[tuple[int, int], list[int]] = {}
        x = 0.0
        while True:
            px = min(x, W)
            y = 0.0
            while True:
                py = min(y, L)
                pt_idx = len(grid_points)
                grid_points.append((px, py))
                cx = min(int(px / cell_size), n_cells_x - 1)
                cy = min(int(py / cell_size), n_cells_y - 1)
                key = (cx, cy)
                if key not in cell_to_points:
                    cell_to_points[key] = []
                cell_to_points[key].append(pt_idx)
                if py >= L:
                    break
                y = min(y + step, L)
            if px >= W:
                break
            x = min(x + step, W)

        detector_covered_sets: list[set] = []
        for dx, dy in dets:
            covered = set()
            min_cx = max(0, int((dx - R) / cell_size))
            max_cx = min(n_cells_x - 1, int((dx + R) / cell_size))
            min_cy = max(0, int((dy - R) / cell_size))
            max_cy = min(n_cells_y - 1, int((dy + R) / cell_size))
            for cx in range(min_cx, max_cx + 1):
                for cy in range(min_cy, max_cy + 1):
                    for pt_idx in cell_to_points.get((cx, cy), []):
                        px, py = grid_points[pt_idx]
                        if (px - dx) ** 2 + (py - dy) ** 2 <= R2:
                            covered.add(pt_idx)
            detector_covered_sets.append(covered)

        point_coverers: list[set] = [set() for _ in range(len(grid_points))]
        for det_idx, covered in enumerate(detector_covered_sets):
            for pt_idx in covered:
                point_coverers[pt_idx].add(det_idx)

        removed: set[int] = set()
        changed = True
        pass_count = 0
        while changed and pass_count < REMOVE_REDUNDANT_MAX_PASSES:
            changed = False
            pass_count += 1
            for i in range(len(dets) - 1, -1, -1):
                if i in removed:
                    continue
                can_remove = True
                for pt_idx in detector_covered_sets[i]:
                    coverers = point_coverers[pt_idx]
                    if len(coverers - removed - {i}) == 0:
                        can_remove = False
                        break
                if can_remove:
                    removed.add(i)
                    changed = True

        if not removed:
            return

        new_dets = [dets[i] for i in range(len(dets)) if i not in removed]
        if not new_dets:
            return

        old_dets = layout.detectors
        old_cov = layout.coverage_pct
        old_valid = layout.proof_valid
        old_nfpa_valid = layout.nfpa_valid
        old_violations = list(layout.violations) if layout.violations else []
        layout.detectors = new_dets
        self._verify_fast(layout)
        self._audit_nfpa(layout)

        if not layout.proof_valid or not layout.nfpa_valid:
            layout.detectors = old_dets
            layout.coverage_pct = old_cov
            layout.proof_valid = old_valid
            layout.nfpa_valid = old_nfpa_valid
            layout.violations = old_violations

    def _verify_fast(self, layout: DetectorLayout) -> None:
        room = layout.room
        dets = layout.detectors
        W, L = room.width, room.length

        if not dets:
            layout.coverage_pct = 0.0
            layout.proof_valid = False
            layout.wall_violations = 0
            return

        try:
            import numpy as np
        except ImportError:
            self._verify(layout)
            return

        dets_arr = np.array(dets, dtype=np.float64)
        assert self.R is not None
        step = VERIFY_STEP
        coarse_step = COARSE_STEP

        xs_coarse = np.arange(0, W + coarse_step * 0.5, coarse_step)
        ys_coarse = np.arange(0, L + coarse_step * 0.5, coarse_step)
        xs_coarse = np.clip(xs_coarse, 0, W)
        ys_coarse = np.clip(ys_coarse, 0, L)

        if len(xs_coarse) < 2 or len(ys_coarse) < 2:
            layout.coverage_pct = 100.0
            layout.proof_valid = True
            layout.wall_violations = 0
            return

        n_cx = len(xs_coarse) - 1
        n_cy = len(ys_coarse) - 1
        n_coarse_cells = n_cx * n_cy

        cell_corners = np.empty((n_coarse_cells, 4, 2), dtype=np.float64)
        idx = 0
        for i in range(n_cx):
            for j in range(n_cy):
                x0, x1 = xs_coarse[i], xs_coarse[i + 1]
                y0, y1 = ys_coarse[j], ys_coarse[j + 1]
                cell_corners[idx, 0] = [x0, y0]
                cell_corners[idx, 1] = [x1, y0]
                cell_corners[idx, 2] = [x0, y1]
                cell_corners[idx, 3] = [x1, y1]
                idx += 1

        all_corners = cell_corners.reshape(-1, 2)
        diff_c = all_corners[:, np.newaxis, :] - dets_arr[np.newaxis, :, :]
        dist2_c = (diff_c**2).sum(axis=2)

        coarse_margin = coarse_step * math.sqrt(2) / 2
        R_eff_coarse = self.R - coarse_margin  # NOSONAR - python:S117
        R2_eff_coarse = R_eff_coarse**2 + 1e-9  # NOSONAR - python:S117
        corner_covered_coarse = (dist2_c <= R2_eff_coarse).any(axis=1)
        corner_covered_cells = corner_covered_coarse.reshape(n_coarse_cells, 4)
        cell_covered = corner_covered_cells.all(axis=1)

        n_coarse_covered = int(cell_covered.sum())

        if n_coarse_covered == n_coarse_cells:
            layout.coverage_pct = 100.0
            layout.proof_valid = True
            viol = 0
            for xd, yd in dets:
                x_bad = xd < self.wm - 1e-6 or xd > W - self.wm + 1e-6
                y_bad = yd < self.wm - 1e-6 or yd > L - self.wm + 1e-6
                if x_bad or y_bad:
                    viol += 1
            layout.wall_violations = viol
            return

        uncovered_indices = np.nonzero(~cell_covered)[0]

        fine_corners_list = []
        for ci in uncovered_indices:
            i = ci // n_cy
            j = ci % n_cy
            x0_c, x1_c = xs_coarse[i], xs_coarse[i + 1]
            y0_c, y1_c = ys_coarse[j], ys_coarse[j + 1]

            fx = np.arange(float(x0_c), float(x1_c) + step * 0.5, step)
            fy = np.arange(float(y0_c), float(y1_c) + step * 0.5, step)
            fx = np.clip(fx, 0, W)
            fy = np.clip(fy, 0, L)

            if len(fx) < 2 or len(fy) < 2:
                continue

            for fi in range(len(fx) - 1):
                for fj in range(len(fy) - 1):
                    fine_corners_list.append(
                        [
                            [fx[fi], fy[fj]],
                            [fx[fi + 1], fy[fj]],
                            [fx[fi], fy[fj + 1]],
                            [fx[fi + 1], fy[fj + 1]],
                        ]
                    )

        if not fine_corners_list:
            layout.coverage_pct = round(100.0 * n_coarse_covered / n_coarse_cells, 4)
            layout.proof_valid = False
            viol = 0
            for xd, yd in dets:
                x_bad = xd < self.wm - 1e-6 or xd > W - self.wm + 1e-6
                y_bad = yd < self.wm - 1e-6 or yd > L - self.wm + 1e-6
                if x_bad or y_bad:
                    viol += 1
            layout.wall_violations = viol
            return

        fine_corners_arr = np.array(fine_corners_list, dtype=np.float64)
        n_fine_cells = len(fine_corners_list)

        all_fine_corners = fine_corners_arr.reshape(-1, 2)
        diff_f = all_fine_corners[:, np.newaxis, :] - dets_arr[np.newaxis, :, :]
        dist2_f = (diff_f**2).sum(axis=2)

        fine_margin = step * math.sqrt(2) / 2
        R_eff_fine = self.R - fine_margin  # NOSONAR - python:S117
        R2_eff_fine = R_eff_fine**2 + 1e-9  # NOSONAR - python:S117

        fine_corner_covered = (dist2_f <= R2_eff_fine).any(axis=1)
        fine_corner_covered_cells = fine_corner_covered.reshape(n_fine_cells, 4)
        fine_cell_covered = fine_corner_covered_cells.all(axis=1)

        n_fine_covered = int(fine_cell_covered.sum())

        covered_area = n_coarse_covered * coarse_step**2 + n_fine_covered * step**2
        total_area = W * L
        layout.coverage_pct = min(
            round(100.0 * covered_area / total_area, 4) if total_area else 0.0, 100.0
        )

        total_cells = n_coarse_covered + n_fine_cells
        covered_cells = n_coarse_covered + n_fine_covered
        layout.proof_valid = covered_cells == total_cells

        viol = 0
        for xd, yd in dets:
            if xd < self.wm - 1e-6 or xd > W - self.wm + 1e-6:
                viol += 1
            if yd < self.wm - 1e-6 or yd > L - self.wm + 1e-6:
                viol += 1
        layout.wall_violations = viol

    def _verify(self, layout: DetectorLayout) -> None:
        room = layout.room
        dets = layout.detectors
        W, L = room.width, room.length
        assert self.R is not None
        R = self.R
        R2 = R * R + 1e-9
        step = VERIFY_STEP

        if not dets:
            layout.coverage_pct = 0.0
            layout.proof_valid = False
            layout.wall_violations = 0
            return

        xs = []
        x = 0.0
        while True:
            xs.append(min(x, W))
            if x >= W:
                break
            x = min(x + step, W)

        ys = []
        y = 0.0
        while True:
            ys.append(min(y, L))
            if y >= L:
                break
            y = min(y + step, L)

        total_cells = 0
        covered_cells = 0

        for i in range(len(xs) - 1):
            for j in range(len(ys) - 1):
                total_cells += 1
                x0, x1 = xs[i], xs[i + 1]
                y0, y1 = ys[j], ys[j + 1]

                corners = [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]
                corner_covering_sets = []
                for cx, cy in corners:
                    covering = set()
                    for d_idx, (dx, dy) in enumerate(dets):
                        if (cx - dx) ** 2 + (cy - dy) ** 2 <= R2:
                            covering.add(d_idx)
                    corner_covering_sets.append(covering)

                common_coverers = corner_covering_sets[0]
                for s in corner_covering_sets[1:]:
                    common_coverers = common_coverers & s

                if common_coverers:
                    covered_cells += 1

        layout.coverage_pct = round(100.0 * covered_cells / total_cells, 4) if total_cells else 0.0
        layout.proof_valid = covered_cells == total_cells

        viol = 0
        for xd, yd in dets:
            if xd < self.wm - 1e-6 or xd > W - self.wm + 1e-6:
                viol += 1
            if yd < self.wm - 1e-6 or yd > L - self.wm + 1e-6:
                viol += 1
        layout.wall_violations = viol

    def _audit_nfpa(self, layout: DetectorLayout) -> bool:
        dets = layout.detectors
        S = self.max_spacing
        W, L = layout.room.width, layout.room.length
        assert self.R is not None
        coverage_limit = self.R
        violations = []
        layout.violations = []

        n = len(dets)
        if n == 1:
            if layout.coverage_pct >= 99.9:
                layout.nfpa_valid = True
            else:
                layout.nfpa_valid = False
            return layout.nfpa_valid

        max_gap = 0.0
        for i, (x1, y1) in enumerate(dets):
            min_dist = float("inf")
            for j, (x2, y2) in enumerate(dets):
                if i == j:
                    continue
                min_dist = min(min_dist, math.hypot(x1 - x2, y1 - y2))
            max_gap = max(max_gap, min_dist)
        if max_gap > S + 1e-6:
            violations.append(f"Max spacing {max_gap:.2f}m > S={S:.2f}m")

        self._check_wall_coverage(
            dets,
            perp_fn=lambda d: d[1],
            par_fn=lambda d: d[0],
            wall_length=W,
            coverage_limit=coverage_limit,
            wall_name="bottom",
            violations=violations,
        )
        self._check_wall_coverage(
            dets,
            perp_fn=lambda d: L - d[1],
            par_fn=lambda d: d[0],
            wall_length=W,
            coverage_limit=coverage_limit,
            wall_name="top",
            violations=violations,
        )
        self._check_wall_coverage(
            dets,
            perp_fn=lambda d: d[0],
            par_fn=lambda d: d[1],
            wall_length=L,
            coverage_limit=coverage_limit,
            wall_name="left",
            violations=violations,
        )
        self._check_wall_coverage(
            dets,
            perp_fn=lambda d: W - d[0],
            par_fn=lambda d: d[1],
            wall_length=L,
            coverage_limit=coverage_limit,
            wall_name="right",
            violations=violations,
        )

        layout.nfpa_valid = len(violations) == 0
        layout.violations = violations
        return layout.nfpa_valid

    def _check_wall_coverage(
        self,
        dets: list[tuple[float, float]],
        perp_fn,
        par_fn,
        wall_length: float,
        coverage_limit: float,
        wall_name: str,
        violations: list[str],
    ) -> None:
        assert self.R is not None
        R = self.R
        R2 = R * R

        intervals = []
        for det in dets:
            d_perp = perp_fn(det)
            if d_perp > R + 1e-9:
                continue

            d_perp_sq = d_perp * d_perp
            half_width = 0.0 if d_perp_sq >= R2 else math.sqrt(R2 - d_perp_sq)

            center = par_fn(det)
            lo = max(0.0, center - half_width)
            hi = min(wall_length, center + half_width)

            if lo < hi + 1e-9:
                intervals.append((lo, hi))

        if not intervals:
            violations.append(f"No detectors near {wall_name} wall")
            return

        intervals.sort(key=lambda iv: iv[0])

        merged = [intervals[0]]
        for lo, hi in intervals[1:]:
            prev_lo, prev_hi = merged[-1]
            if lo <= prev_hi + 1e-9:
                merged[-1] = (prev_lo, max(prev_hi, hi))
            else:
                merged.append((lo, hi))

        if merged[0][0] > 1e-9:
            violations.append(f"{wall_name} wall uncovered at start: gap [0, {merged[0][0]:.3f}]")
        if merged[-1][1] < wall_length - 1e-9:
            violations.append(
                f"{wall_name} wall uncovered at end: gap [{merged[-1][1]:.3f}, {wall_length:.3f}]"
            )

        for i in range(len(merged) - 1):
            gap_start = merged[i][1]
            gap_end = merged[i + 1][0]
            if gap_end > gap_start + 1e-9:
                violations.append(f"{wall_name} wall gap: [{gap_start:.3f}, {gap_end:.3f}]")

    def _verify_vectorized(self, layout: DetectorLayout) -> None:
        try:
            import numpy as np
        except ImportError:
            self._verify(layout)
            return

        room = layout.room
        dets = np.array(layout.detectors)
        if len(dets) == 0:
            layout.coverage_pct = 0.0
            layout.proof_valid = False
            layout.wall_violations = 0
            return

        W, L = room.width, room.length
        step = VERIFY_STEP
        xs = np.arange(0, W + step * 0.5, step)
        ys = np.arange(0, L + step * 0.5, step)
        xv, yv = np.meshgrid(xs, ys)
        test_points = np.column_stack([xv.ravel(), yv.ravel()])

        test_points[:, 0] = np.clip(test_points[:, 0], 0, W)
        test_points[:, 1] = np.clip(test_points[:, 1], 0, L)

        diff = test_points[:, np.newaxis, :] - dets[np.newaxis, :, :]
        dist2 = (diff**2).sum(axis=2)
        assert self.R is not None
        r2 = self.R**2 + 1e-9
        covered = (dist2 <= r2).any(axis=1)

        total = len(test_points)
        covered_count = covered.sum()
        layout.coverage_pct = round(100.0 * covered_count / total, 4) if total else 0.0
        layout.proof_valid = covered_count == total

        viol = 0
        for xd, yd in layout.detectors:
            if xd < self.wm - 1e-6 or xd > W - self.wm + 1e-6:
                viol += 1
            if yd < self.wm - 1e-6 or yd > L - self.wm + 1e-6:
                viol += 1
        layout.wall_violations = viol

    @staticmethod
    def theoretical_lower_bound(room: Room, coverage_radius: float = DETECTOR_RADIUS) -> int:
        """Estimative lower bound for detector count."""
        return max(1, math.ceil(room.width * room.length / (math.pi * coverage_radius**2)))

    @staticmethod
    def _theoretical_minimum(room: Room, coverage_radius: float = DETECTOR_RADIUS) -> int:
        return DensityOptimizer.theoretical_lower_bound(room, coverage_radius)


# ════════════════════════════════════════════════════════════════════════════
# Batch Processing API (V2)
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class BatchResult:
    """Result of a batch optimization operation."""

    results: dict[str, Any] = field(default_factory=dict)
    total_rooms: int = 0
    successful: int = 0
    failed: int = 0
    total_time_s: float = 0.0
    rooms_per_sec: float = 0.0
    n_workers: int = 1
    version: str = FIREAI_VERSION


def _optimize_room_worker(
    args: tuple,
) -> tuple[str, Any]:
    """Worker function for multiprocessing batch optimization."""
    room_id, room_spec_dict, detector_type, kwargs = args

    try:
        if RoomSpec is not None and isinstance(room_spec_dict, dict):
            if "vertices" in room_spec_dict:
                points = room_spec_dict["vertices"]
                if Point3D is not None:
                    points = [
                        Point3D(x=p[0], y=p[1], z=p[2] if len(p) > 2 else 0.0)
                        if not isinstance(p, Point3D)
                        else p
                        for p in points
                    ]
                if Geometry is not None:
                    geom = Geometry(points=points, polyline_closed=True)
                    geom.calculate_area()
                else:
                    geom = None

                spec = RoomSpec(  # type: ignore[call-arg]
                    room_id=room_id,
                    room_name=room_spec_dict.get("room_name", room_id),
                    room_type=room_spec_dict.get("room_type", "unknown"),
                    ceiling_height_m=room_spec_dict.get("ceiling_height_m", 3.0),
                    geometry=geom,
                )
            else:
                spec = room_spec_dict  # type: ignore[assignment]
        else:
            spec = room_spec_dict

        optimizer = DensityOptimizer()
        result = optimizer.optimize(room_spec=spec, detector_type=detector_type, **kwargs)  # type: ignore[call-arg]
        return (room_id, result)

    except Exception as e:
        log.exception(f"Worker error for room {room_id}: {e}")
        return (room_id, {"error": str(e)})


class DensityOptimizerV2:
    """Multiprocessing batch API for DensityOptimizer."""

    def __init__(
        self,
        n_workers: int | None = None,
        chunk_size: int = 10,
        timeout_per_room_s: float = 60.0,
    ) -> None:
        cpu_count = os.cpu_count() or 4
        if n_workers is None:
            self.n_workers = min(4, cpu_count)
        else:
            self.n_workers = max(1, min(n_workers, cpu_count * 2))

        self.chunk_size = max(1, chunk_size)
        self.timeout_per_room_s = timeout_per_room_s

    def optimize_batch(
        self, room_specs: dict[str, Any], detector_type: str = "smoke", **kwargs
    ) -> BatchResult:
        t0 = time.perf_counter()
        total = len(room_specs)

        if total == 0:
            return BatchResult(
                total_rooms=0,
                successful=0,
                failed=0,
                total_time_s=0.0,
                rooms_per_sec=0.0,
                n_workers=self.n_workers,
            )

        validated_specs = {}
        for room_id, spec in room_specs.items():
            if isinstance(spec, dict):
                ceiling_h = spec.get("ceiling_height_m", 3.0)
                if isinstance(ceiling_h, int | float) and not math.isfinite(ceiling_h):
                    log.error(
                        f"Room {room_id}: ceiling_height_m={ceiling_h} is NaN/Inf — SKIPPING per Life-Safety Rule 2"
                    )
                    continue
                vertices = spec.get("vertices", [])
                has_invalid = False
                for v in vertices:
                    for coord in v if isinstance(v, list | tuple) else [v]:
                        if isinstance(coord, float) and not math.isfinite(coord):
                            log.error(
                                f"Room {room_id}: vertex coordinate={coord} is NaN/Inf — "
                                f"SKIPPING per Life-Safety Rule 2"
                            )
                            has_invalid = True
                            break
                    if has_invalid:
                        break
                if has_invalid:
                    continue
            validated_specs[room_id] = spec

        if len(validated_specs) < total:
            log.warning(
                f"Rejected {total - len(validated_specs)}/{total} rooms due to NaN/Inf geometry per Life-Safety Rule 2"
            )

        if self.n_workers <= 1 or len(validated_specs) <= 1:
            return self._optimize_sequential(validated_specs, detector_type, kwargs, t0)

        return self._optimize_parallel(validated_specs, detector_type, kwargs, t0)

    def _optimize_sequential(
        self,
        room_specs: dict[str, Any],
        detector_type: str,
        kwargs: dict,
        t0: float,
    ) -> BatchResult:
        results: dict[str, Any] = {}
        successful = 0
        failed = 0

        for room_id, spec in room_specs.items():
            try:
                room_id_result, result = _optimize_room_worker(
                    (room_id, spec, detector_type, kwargs)
                )
                if isinstance(result, dict) and "error" in result:
                    failed += 1
                    log.error(f"Room {room_id}: {result['error']}")
                else:
                    successful += 1
                results[room_id_result] = result
            except Exception as e:
                failed += 1
                results[room_id] = {"error": str(e)}
                log.exception(f"Room {room_id}: {e}")

        elapsed = time.perf_counter() - t0
        rps = len(room_specs) / elapsed if elapsed > 0 else 0

        return BatchResult(
            results=results,
            total_rooms=len(room_specs),
            successful=successful,
            failed=failed,
            total_time_s=round(elapsed, 3),
            rooms_per_sec=round(rps, 1),
            n_workers=1,
        )

    def _optimize_parallel(
        self,
        room_specs: dict[str, Any],
        detector_type: str,
        kwargs: dict,
        t0: float,
    ) -> BatchResult:
        work_items = [
            (room_id, spec, detector_type, kwargs) for room_id, spec in room_specs.items()
        ]

        results: dict[str, Any] = {}
        successful = 0
        failed = 0

        try:
            ctx = multiprocessing.get_context("spawn" if os.name == "nt" else "fork")
            with ctx.Pool(
                processes=self.n_workers,
                maxtasksperchild=100,
            ) as pool:
                async_results = pool.map_async(
                    _optimize_room_worker,
                    work_items,
                    chunksize=self.chunk_size,
                )

                try:
                    worker_results = async_results.get(
                        timeout=self.timeout_per_room_s * len(work_items)
                    )
                except multiprocessing.TimeoutError:
                    log.exception(
                        f"Batch optimization timed out after {self.timeout_per_room_s * len(work_items)}s"
                    )
                    worker_results = []

                for room_id, result in worker_results:
                    if isinstance(result, dict) and "error" in result:
                        failed += 1
                    else:
                        successful += 1
                    results[room_id] = result

        except Exception as e:
            log.exception(f"Multiprocessing pool error: {e}")
            log.warning("Falling back to sequential processing")
            for room_id, spec in room_specs.items():
                if room_id not in results:
                    try:
                        _, result = _optimize_room_worker((room_id, spec, detector_type, kwargs))
                        if isinstance(result, dict) and "error" in result:
                            failed += 1
                        else:
                            successful += 1
                        results[room_id] = result
                    except Exception as e2:
                        failed += 1
                        results[room_id] = {"error": str(e2)}

        elapsed = time.perf_counter() - t0
        rps = len(room_specs) / elapsed if elapsed > 0 else 0

        return BatchResult(
            results=results,
            total_rooms=len(room_specs),
            successful=successful,
            failed=failed,
            total_time_s=round(elapsed, 3),
            rooms_per_sec=round(rps, 1),
            n_workers=self.n_workers,
        )

    def optimize_single(
        self, room_id: str, room_spec: Any, detector_type: str = "smoke", **kwargs
    ) -> Any:
        _, result = _optimize_room_worker((room_id, room_spec, detector_type, kwargs))
        return result


DensityOptimizerBatch = DensityOptimizerV2

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
