"""
OptimalMIPEngine - Mixed Integer Programming Solver
Spatial device placement optimization using PuLP
"""

from typing import List, Tuple, Dict, Set
from pulp import LpProblem, LpMinimize, LpVariable, LpBinary, lpSum, LpStatus, value
import math


class OptimalMIPEngine:
    def __init__(self, grid_size: int, radius: float):
        self.n = grid_size
        self.r = radius
        self.grid_points: List[Tuple[int, int]] = []
        self.test_points: List[Tuple[int, int]] = []
        self._build_points()
    
    def _build_points(self):
        self.grid_points = [(x, y) for x in range(self.n) for y in range(self.n)]
        self.test_points = [(x + 0.5, y + 0.5) for x in range(self.n - 1) for y in range(self.n - 1)]
    
    def _distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
    
    def _coverage_pairs(self) -> Dict[int, List[int]]:
        coverage = {}
        for ti, tp in enumerate(self.test_points):
            coverage[ti] = []
            for gi, gp in enumerate(self.grid_points):
                if self._distance(tp, gp) <= self.r:
                    coverage[ti].append(gi)
        return coverage
    
    def _spacing_pairs(self) -> List[Tuple[int, int]]:
        pairs = []
        for i, p1 in enumerate(self.grid_points):
            for j, p2 in enumerate(self.grid_points):
                if i < j and self._distance(p1, p2) < self.r:
                    pairs.append((i, j))
        return pairs
    
    def solve(self) -> Tuple[List[Tuple[int, int]], int, bool]:
        coverage = self._coverage_pairs()
        spacing = self._spacing_pairs()
        
        if not coverage:
            return [], 0, False
        
        prob = LpProblem("OptimalPlacement", LpMinimize)
        
        x = {i: LpVariable(f"x_{i}", cat=LpBinary) for i in range(len(self.grid_points))}
        
        prob += lpSum(x.values()), "TotalDevices"
        
        for ti in coverage:
            prob += lpSum(x[gi] for gi in coverage[ti]) >= 1, f"Coverage_{ti}"
        
        for i, j in spacing:
            prob += x[i] + x[j] <= 1, f"Spacing_{i}_{j}"
        
        prob.solve()
        
        if LpStatus[prob.status] != "Optimal":
            return [], 0, False
        
        devices = []
        for gi, var in x.items():
            if value(var) > 0.5:
                devices.append(self.grid_points[gi])
        
        return devices, len(devices), True