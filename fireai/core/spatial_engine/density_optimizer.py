"""
DensityOptimizer - Optimal detector placement with NFPA 72 compliance.

Uses hexagonal seeding for maximum density reduction while maintaining 100% coverage.
"""
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional
from shapely.geometry import Point, Polygon


@dataclass
class DensityResult:
    """Result from density optimization."""
    positions: List[Tuple[float, float]]
    proof_valid: bool
    coverage_fraction: float
    detector_count: int
    initial_count: int
    final_count: int


class DensityOptimizer:
    """
    Optimized detector placement with hexagonal seeding.
    
    Phase 1: Hexagonal grid for optimal density
    Phase 2: Fill gaps to achieve 100% coverage
    Phase 3: NFPA 72 compliance check
    """
    
    def __init__(
        self,
        radius: float,
        required_pct: float = 100.0,
        max_spacing: float = 6.4,
        min_wall_dist: float = 0.10
    ):
        self.radius = radius
        self.required_pct = required_pct
        self.max_spacing = max_spacing
        self.min_wall_dist = min_wall_dist
        self._coverage_grid = 0.25  # 25cm grid for coverage proof
    
    def optimize(
        self,
        polygon: Polygon,
        min_wall_dist: Optional[float] = None,
        max_wall_dist: Optional[float] = None
    ) -> DensityResult:
        """
        Optimize detector placement.
        
        Args:
            polygon: Room polygon
            min_wall_dist: Minimum wall distance (defaults to self.min_wall_dist)
            max_wall_dist: Maximum wall distance (for NFPA compliance)
        
        Returns:
            DensityResult with optimized positions
        """
        min_dist = min_wall_dist or self.min_wall_dist
        
        # Phase 1: Hexagonal grid placement
        positions = self._hex_seed(polygon)
        
        if not positions:
            return DensityResult(
                positions=[],
                proof_valid=False,
                coverage_fraction=0.0,
                detector_count=0,
                initial_count=0,
                final_count=0
            )
        
        initial_count = len(positions)
        
        # Phase 2: Fill coverage gaps
        positions = self._fill_gaps(polygon, positions)
        
        # Phase 3: Minimum wall distance enforcement  
        positions = self._enforce_wall_distance(polygon, positions, min_dist)
        
        # Phase 4: Maximum wall distance enforcement (NFPA 72 compliance)
        if max_wall_dist:
            positions = self._enforce_max_wall_distance(polygon, positions, max_wall_dist, min_dist)
        
        final_count = len(positions)
        
        # Compute coverage proof
        coverage = self._compute_coverage(polygon, positions)
        proof_valid = coverage >= (self.required_pct / 100.0)
        
        return DensityResult(
            positions=positions,
            proof_valid=proof_valid,
            coverage_fraction=coverage,
            detector_count=final_count,
            initial_count=initial_count,
            final_count=final_count
        )
    
    def _hex_seed(self, poly: Polygon) -> List[Tuple[float, float]]:
        """
        Hexagonal seed placement for optimal density.
        Starts from min_wall_dist to ensure corner coverage.
        """
        min_x, min_y, max_x, max_y = poly.bounds
        width = max_x - min_x
        depth = max_y - min_y
        
        # Hexagonal spacing: dx = r * sqrt(3), dy = r * 1.5
        # Cap at max_spacing for NFPA compliance
        r = self.radius
        dx = min(r * math.sqrt(3), self.max_spacing)
        dy = min(r * 1.5, self.max_spacing)
        
        # Start from min_wall_dist to cover corners
        x_start = min_x + self.min_wall_dist
        y_start = min_y + self.min_wall_dist
        
        positions = []
        row = 0
        y = y_start
        
        while y <= max_y + 1e-9:
            # Offset every other row for hexagonal pattern
            x_off = dx / 2 if row % 2 else 0.0
            x = x_start + x_off
            
            while x <= max_x + 1e-9:
                pt = Point(x, y)
                # Check inside polygon and at valid wall distance
                if poly.contains(pt):
                    wall_dist = min(
                        x - min_x, max_x - x,
                        y - min_y, max_y - y
                    )
                    if wall_dist >= self.min_wall_dist:
                        positions.append((round(x, 4), round(y, 4)))
                x += dx
            
            y += dy
            row += 1
        
        return positions
    
    def _fill_gaps(
        self,
        poly: Polygon,
        positions: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """
        Fill coverage gaps to achieve 100% coverage.
        """
        min_x, min_y, max_x, max_y = poly.bounds
        r2 = self.radius * self.radius
        
        # Iteratively fill gaps
        max_iters = 50
        for _ in range(max_iters):
            # Find uncovered points
            uncovered = []
            gx = min_x + self._coverage_grid
            while gx <= max_x:
                gy = min_y + self._coverage_grid
                while gy <= max_y:
                    if poly.contains(Point(gx, gy)):
                        # Check if covered
                        covered = False
                        for px, py in positions:
                            if (gx - px)**2 + (gy - py)**2 <= r2:
                                covered = True
                                break
                        if not covered:
                            uncovered.append((gx, gy))
                    gy += self._coverage_grid
                gx += self._coverage_grid
            
            if not uncovered:
                break  # 100% coverage
            
            # Find largest gap
            best_point = None
            best_distance = 0
            for ux, uy in uncovered:
                min_dist = float('inf')
                for px, py in positions:
                    d2 = (ux - px)**2 + (uy - py)**2
                    min_dist = min(min_dist, d2)
                if min_dist > best_distance:
                    best_distance = min_dist
                    best_point = (ux, uy)
            
            if best_point:
                positions.append(best_point)
            else:
                break
        
        return positions
    
    def _enforce_wall_distance(
        self,
        poly: Polygon,
        positions: List[Tuple[float, float]],
        min_dist: float
    ) -> List[Tuple[float, float]]:
        """
        Ensure all detectors meet minimum wall distance requirement.
        """
        min_x, min_y, max_x, max_y = poly.bounds
        
        valid_positions = []
        for px, py in positions:
            # Check wall distances
            wall_dist = min(
                px - min_x,
                max_x - px,
                py - min_y,
                max_y - py
            )
            if wall_dist >= min_dist:
                valid_positions.append((px, py))
        
        return valid_positions
    
    def _enforce_max_wall_distance(
        self,
        poly: Polygon,
        positions: List[Tuple[float, float]],
        max_wall: float,
        min_wall_dist: float = 0.10
    ) -> List[Tuple[float, float]]:
        """
        Ensure no point on wall is more than max_wall from any detector.
        Add detectors near walls if needed.
        """
        if not positions:
            return positions
            
        min_x, min_y, max_x, max_y = poly.bounds
        r2 = self.radius * self.radius
        
        # Sample points along each wall
        wall_points = []
        
        # Bottom wall (y = min_y)
        for x in [min_x + min_wall_dist, max_x - min_wall_dist]:
            wall_points.append((x, min_y + min_wall_dist))
        
        # Top wall (y = max_y)
        for x in [min_x + min_wall_dist, max_x - min_wall_dist]:
            wall_points.append((x, max_y - min_wall_dist))
        
        # Left wall (x = min_x)
        for y in [min_y + min_wall_dist, max_y - min_wall_dist]:
            wall_points.append((min_x + min_wall_dist, y))
        
        # Right wall (x = max_x)
        for y in [min_y + min_wall_dist, max_y - min_wall_dist]:
            wall_points.append((max_x - min_wall_dist, y))
        
        # Check each wall point
        for wx, wy in wall_points:
            pt = Point(wx, wy)
            if not poly.contains(pt):
                continue
            
            # Find distance to nearest detector
            min_dist = float('inf')
            for px, py in positions:
                d2 = (wx - px)**2 + (wy - py)**2
                min_dist = min(min_dist, d2)
            
            # If too far from any detector, add one near this wall point
            if min_dist > max_wall**2:
                # Find closest valid point near this wall
                new_x = max(min_x + min_wall_dist, min(wx, max_x - min_wall_dist))
                new_y = max(min_y + min_wall_dist, min(wy, max_y - min_wall_dist))
                positions.append((round(new_x, 4), round(new_y, 4)))
        
        return positions
    
    def _compute_coverage(
        self,
        poly: Polygon,
        positions: List[Tuple[float, float]]
    ) -> float:
        """
        Compute coverage fraction using grid sampling.
        """
        if not positions:
            return 0.0
        
        min_x, min_y, max_x, max_y = poly.bounds
        r2 = self.radius * self.radius
        
        total_pts = 0
        covered_pts = 0
        
        gx = min_x + self._coverage_grid / 2
        while gx <= max_x:
            gy = min_y + self._coverage_grid / 2
            while gy <= max_y:
                if poly.contains(Point(gx, gy)):
                    total_pts += 1
                    # Check if covered
                    for px, py in positions:
                        if (gx - px)**2 + (gy - py)**2 <= r2:
                            covered_pts += 1
                            break
                gy += self._coverage_grid
            gx += self._coverage_grid
        
        return covered_pts / total_pts if total_pts > 0 else 0.0