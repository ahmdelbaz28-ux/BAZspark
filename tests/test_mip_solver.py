"""
test_mip_solver.py
MIP Solver Tests - Optimal Placement
"""

import pytest
from spatial_engine.mip_solver import OptimalMIPEngine


def test_optimal_placement_4_devices():
    engine = OptimalMIPEngine(grid_size=10, radius=3.0)
    devices, count, feasible = engine.solve()
    
    assert feasible == True
    assert count == 4
    assert len(devices) == 4


def test_single_device_optimal():
    engine = OptimalMIPEngine(grid_size=4, radius=5.0)
    devices, count, feasible = engine.solve()
    
    assert feasible == True
    assert count == 1
    assert len(devices) == 1


def test_infeasible_case():
    engine = OptimalMIPEngine(grid_size=10, radius=0.1)
    devices, count, feasible = engine.solve()
    
    assert feasible == False
    assert count == 0