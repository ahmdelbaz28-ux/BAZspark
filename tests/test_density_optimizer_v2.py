"""tests/test_density_optimizer_v2.py — Unit tests for DensityOptimizerV2 batch optimization."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from fireai.core.density_optimizer_v2 import (
    BatchResult,
    DensityOptimizerBatch,
    DensityOptimizerV2,
    _optimize_room_worker,
)
from fireai.version import FIREAI_VERSION


class TestDensityOptimizerV2:
    """Test suite for DensityOptimizerV2 batch engine."""

    def test_initialization_and_clamping(self):
        # Default
        opt = DensityOptimizerV2()
        assert opt.n_workers >= 1
        assert opt.chunk_size == 10
        assert opt.timeout_per_room_s == 60.0

        # Clamped negative
        opt_neg = DensityOptimizerV2(n_workers=-5, chunk_size=0)
        assert opt_neg.n_workers == 1
        assert opt_neg.chunk_size == 1

        # Clamped huge
        opt_huge = DensityOptimizerV2(n_workers=9999)
        cpu_count = os.cpu_count() or 4
        assert opt_huge.n_workers <= cpu_count * 2

    def test_batch_result_dataclass(self):
        res = BatchResult(
            results={"r1": {"coverage": 100.0}},
            total_rooms=1,
            successful=1,
            failed=0,
            total_time_s=0.05,
            rooms_per_sec=20.0,
            n_workers=2,
            version=FIREAI_VERSION,
        )
        assert res.total_rooms == 1
        assert res.successful == 1
        assert res.version == FIREAI_VERSION

    def test_empty_batch(self):
        opt = DensityOptimizerV2(n_workers=1)
        res = opt.optimize_batch({})
        assert res.total_rooms == 0
        assert res.successful == 0
        assert res.failed == 0
        assert res.results == {}

    def test_nan_inf_rejection_per_life_safety_rule_2(self):
        opt = DensityOptimizerV2(n_workers=1)
        bad_rooms = {
            "nan_ceiling": {"ceiling_height_m": float("nan"), "vertices": []},
            "inf_ceiling": {"ceiling_height_m": float("inf"), "vertices": []},
            "nan_coord": {"ceiling_height_m": 3.0, "vertices": [[0.0, float("nan")]]},
            "inf_coord": {"ceiling_height_m": 3.0, "vertices": [[0.0, float("inf")]]},
        }
        res = opt.optimize_batch(bad_rooms)
        assert res.total_rooms == 0

    def test_sequential_optimization_flow(self):
        opt = DensityOptimizerV2(n_workers=1)
        # Mock _optimize_room_worker
        with patch("fireai.core.density_optimizer_v2._optimize_room_worker") as mock_worker:
            mock_worker.side_effect = [
                ("r1", {"coverage": 95.0}),
                ("r2", {"error": "Invalid polygon"}),
            ]
            res = opt.optimize_batch({
                "r1": {"ceiling_height_m": 3.0, "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]]},
                "r2": {"ceiling_height_m": 3.0, "vertices": [[0, 0], [5, 0], [5, 5], [0, 5]]},
            })
            assert res.total_rooms == 2
            assert res.successful == 1
            assert res.failed == 1
            assert "r1" in res.results
            assert "r2" in res.results

    def test_optimize_single_convenience(self):
        opt = DensityOptimizerV2(n_workers=1)
        with patch("fireai.core.density_optimizer_v2._optimize_room_worker") as mock_worker:
            mock_worker.return_value = ("room_101", {"coverage_pct": 100.0})
            res = opt.optimize_single("room_101", {"ceiling_height_m": 3.0})
            assert res["coverage_pct"] == 100.0

    def test_worker_function_handles_missing_optimizer(self):
        with patch("fireai.core.density_optimizer_v2.DensityOptimizer", None):
            room_id, res = _optimize_room_worker(("r1", {}, "smoke", {}))
            assert room_id == "r1"
            assert "error" in res

    def test_worker_function_handles_exception(self):
        with patch("fireai.core.density_optimizer_v2.DensityOptimizer") as mock_opt:
            mock_inst = MagicMock()
            mock_inst.optimize.side_effect = RuntimeError("Optimization failed")
            mock_opt.return_value = mock_inst
            room_id, res = _optimize_room_worker(("r1", {"vertices": [[0, 0], [1, 1]]}, "smoke", {}))
            assert room_id == "r1"
            assert "error" in res

    def test_alias_density_optimizer_batch(self):
        assert DensityOptimizerBatch is DensityOptimizerV2
