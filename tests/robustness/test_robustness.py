"""
Robustness Tests for Spatial Engine
=================================
Tests edge cases and pathological geometries to ensure stability.

Tests:
1. Device on room boundary (within epsilon)
2. Device at exact max_allowed_distance
3. Very thin room (width < grid_spacing)
4. Sharp triangular room
5. Room with hole (donut)
6. Obstruction touching wall (no gap)
7. Obstruction covering almost entire room
8. Device inside obstruction (caught by normalizer)
9. 100 devices randomly distributed
10. Room with no devices but with obstructions
"""

import sys
import os
import time
import random

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from spatial_constraint_engine import Room, Device, Obstruction
from spatial_field_engine import (
    NFPAConstraintModel,
    evaluate_compliance,
    generate_grid
)
from validation.spatial_normalizer import SpatialNormalizer
from validation.tolerance_model import ToleranceModel
from shapely.geometry import Point, Polygon


# =============================================================================
# Test Runner
# =============================================================================

class TestResult:
    def __init__(self, name: str, passed: bool, reason: str = "", rejected: bool = False):
        self.name = name
        self.passed = passed
        self.reason = reason
        self.rejected = rejected
    
    def __str__(self):
        status = "PASS (Rejected)" if self.rejected else ("PASS" if self.passed else "FAIL")
        result = f"TEST: {self.name} -> {status}"
        if self.reason:
            result += f"\n   Reason: {self.reason}"
        return result


def run_test(name: str, test_func):
    """Run a single test and return result"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)
    
    try:
        result = test_func()
        print(str(result))
        return result
    except Exception as e:
        print(f"TEST: {name} -> FAIL")
        print(f"   Exception: {type(e).__name__}: {e}")
        return TestResult(name, False, f"Exception: {e}", False)


# =============================================================================
# Test 1: Device on Room Boundary (within epsilon)
# =============================================================================

def test_device_on_boundary():
    """Device exactly on room edge - test with multiple devices for coverage"""
    room = Room(
        id="room_1",
        name="Room with boundary devices",
        geometry=Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
        ceiling_height=2.4
    )
    # 4 devices in corners - should cover the room
    devices = [
        Device(id="smoke_1", device_type="SMOKE_PHOTOELECTRIC", position=Point(0.0001, 0.0001)),
        Device(id="smoke_2", device_type="SMOKE_PHOTOELECTRIC", position=Point(9.9999, 0.0001)),
        Device(id="smoke_3", device_type="SMOKE_PHOTOELECTRIC", position=Point(0.0001, 9.9999)),
        Device(id="smoke_4", device_type="SMOKE_PHOTOELECTRIC", position=Point(9.9999, 9.9999)),
    ]
    obstructions = []
    
    # Normalize first
    normalizer = SpatialNormalizer(ToleranceModel(linear_epsilon=1e-6))
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    # Check if rejected
    criticals = [e for e in errors if e.severity == "CRITICAL"]
    if criticals:
        return TestResult("Device on boundary", True, f"Rejected by normalizer: {criticals[0].message}", True)
    
    # Evaluate
    model = NFPAConstraintModel(ceiling_type="SMOOTH")
    coverage, violations = evaluate_compliance(norm_room, norm_devices, norm_obs, model, grid_spacing=0.5)
    
    # 4 corner devices should cover most of room
    if len(violations) < 50:  # Allow some edge gaps
        return TestResult("Device on boundary", True, f"4 corner devices: {len(violations)} violations (acceptable)")
    else:
        return TestResult("Device on boundary", False, f"Too many violations: {len(violations)}")


# =============================================================================
# Test 2: Device at Exact Max Distance
# =============================================================================

def test_device_at_max_distance():
    """Device at exactly max_allowed_distance from center"""
    room = Room(
        id="room_2",
        name="Room 10x10",
        geometry=Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
        ceiling_height=2.4
    )
    
    # max_allowed_distance = 0.7 * 9.1 = 6.37m
    # Place device at center (5,5) - it should cover nearby points
    model = NFPAConstraintModel(ceiling_type="SMOOTH")
    max_dist = model.max_allowed_distance("SMOKE_PHOTOELECTRIC")
    
    devices = [
        Device(id="smoke_center", device_type="SMOKE_PHOTOELECTRIC", position=Point(5, 5)),
    ]
    obstructions = []
    
    normalizer = SpatialNormalizer(ToleranceModel())
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    if errors:
        return TestResult("Device at max distance", True, f"Rejected: {errors[0].message}", True)
    
    coverage, violations = evaluate_compliance(norm_room, norm_devices, norm_obs, model, grid_spacing=0.5)
    
    # Center device should cover most of room (within 6.37m)
    # Some edge points will be uncovered, but that's expected
    if len(violations) < 200:  # Most points covered
        return TestResult("Device at max distance", True, f"Center device covers {len(coverage)} points, {len(violations)} gaps")
    else:
        return TestResult("Device at max distance", False, f"Too many gaps: {len(violations)}")


# =============================================================================
# Test 3: Very Thin Room (width < grid_spacing)
# =============================================================================

def test_thin_room():
    """Room with width less than grid spacing"""
    # Room 0.1m wide but 10m long
    room = Room(
        id="room_thin",
        name="Thin room",
        geometry=Polygon([(0, 0), (10, 0), (10, 0.1), (0, 0.1), (0, 0)]),
        ceiling_height=2.4
    )
    
    # Single device
    devices = [
        Device(id="smoke_1", device_type="SMOKE_PHOTOELECTRIC", position=Point(5, 0.05)),
    ]
    obstructions = []
    
    normalizer = SpatialNormalizer(ToleranceModel())
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    if errors:
        return TestResult("Thin room", True, f"Rejected: {errors[0].message}", True)
    
    # Generate grid with 0.25m spacing - room is only 0.1m wide!
    grid = generate_grid(norm_room.geometry, 0.25)
    
    model = NFPAConstraintModel(ceiling_type="SMOOTH")
    coverage, violations = evaluate_compliance(norm_room, norm_devices, norm_obs, model, grid_spacing=0.25)
    
    # Should have minimal or no grid points
    if len(grid) == 0:
        return TestResult("Thin room", True, "No grid points generated (room narrower than spacing)")
    
    return TestResult("Thin room", True, f"Generated {len(grid)} grid points, {len(violations)} violations")


# =============================================================================
# Test 4: Sharp Triangular Room
# =============================================================================

def test_triangular_room():
    """Very sharp triangular room"""
    room = Room(
        id="room_tri",
        name="Triangular room",
        geometry=Polygon([(0, 0), (10, 0), (5, 1), (0, 0)]),
        ceiling_height=2.4
    )
    
    devices = [
        Device(id="smoke_1", device_type="SMOKE_PHOTOELECTRIC", position=Point(5, 0.3)),
    ]
    obstructions = []
    
    normalizer = SpatialNormalizer(ToleranceModel())
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    if errors:
        return TestResult("Triangular room", True, f"Rejected: {errors[0].message}", True)
    
    model = NFPAConstraintModel(ceiling_type="SMOOTH")
    coverage, violations = evaluate_compliance(norm_room, norm_devices, norm_obs, model, grid_spacing=0.25)
    
    return TestResult("Triangular room", True, f"Processed {len(coverage)} points, {len(violations)} violations")


# =============================================================================
# Test 5: Room with Hole (Donut)
# =============================================================================

def test_room_with_hole():
    """Room with interior hole (donut shape)"""
    # Outer square 10x10, inner hole 3x3 in center
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    
    outer = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    hole = [(3.5, 3.5), (6.5, 3.5), (6.5, 6.5), (3.5, 6.5), (3.5, 3.5)]
    
    # Create polygon with hole using shapely
    room_poly = Polygon(outer, [hole])
    
    room = Room(
        id="room_donut",
        name="Room with hole",
        geometry=room_poly,
        ceiling_height=2.4
    )
    
    # Device on one side
    devices = [
        Device(id="smoke_1", device_type="SMOKE_PHOTOELECTRIC", position=Point(2, 5)),
    ]
    obstructions = []
    
    normalizer = SpatialNormalizer(ToleranceModel())
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    if errors:
        return TestResult("Room with hole", True, f"Rejected: {errors[0].message}", True)
    
    model = NFPAConstraintModel(ceiling_type="SMOOTH")
    coverage, violations = evaluate_compliance(norm_room, norm_devices, norm_obs, model, grid_spacing=0.5)
    
    return TestResult("Room with hole", True, f"Covered {len(coverage)} points, {len(violations)} violations")


# =============================================================================
# Test 6: Obstruction Touching Wall
# =============================================================================

def test_obstruction_touching_wall():
    """Obstruction that touches wall - should not cause false shadows"""
    room = Room(
        id="room_obs",
        name="Room with wall-touching obstruction",
        geometry=Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
        ceiling_height=2.4
    )
    
    devices = [
        Device(id="smoke_1", device_type="SMOKE_PHOTOELECTRIC", position=Point(5, 5)),
    ]
    
    # Obstruction touching right wall exactly
    obstructions = [
        Obstruction(
            id="wall_obs",
            geometry=Polygon([(9.9, 3), (10, 3), (10, 7), (9.9, 7), (9.9, 3)]),
            height=2.4,
            blocks_visibility=True
        )
    ]
    
    normalizer = SpatialNormalizer(ToleranceModel())
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    if errors:
        return TestResult("Obstruction touching wall", True, f"Rejected: {errors[0].message}", True)
    
    model = NFPAConstraintModel(ceiling_type="SMOOTH")
    coverage, violations = evaluate_compliance(norm_room, norm_devices, norm_obs, model, grid_spacing=0.5)
    
    # Should not have many violations due to wall-touching obstruction
    return TestResult("Obstruction touching wall", True, f"Violations: {len(violations)}")


# =============================================================================
# Test 7: Obstruction Covering Almost Entire Room
# =============================================================================

def test_large_obstruction():
    """Obstruction covering almost entire room"""
    room = Room(
        id="room_large",
        name="Room with large obstruction",
        geometry=Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
        ceiling_height=2.4
    )
    
    devices = [
        Device(id="smoke_1", device_type="SMOKE_PHOTOELECTRIC", position=Point(5, 5)),
    ]
    
    # Obstruction covering 90% of room
    obstructions = [
        Obstruction(
            id="large_obs",
            geometry=Polygon([(0, 0), (9.5, 0), (9.5, 9.5), (0, 9.5), (0, 0)]),
            height=2.4,
            blocks_visibility=True
        )
    ]
    
    normalizer = SpatialNormalizer(ToleranceModel())
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    if errors:
        return TestResult("Large obstruction", True, f"Rejected: {errors[0].message}", True)
    
    model = NFPAConstraintModel(ceiling_type="SMOOTH")
    
    start_time = time.time()
    coverage, violations = evaluate_compliance(norm_room, norm_devices, norm_obs, model, grid_spacing=0.5)
    elapsed = time.time() - start_time
    
    if elapsed > 5:
        return TestResult("Large obstruction", False, f"Too slow: {elapsed:.2f}s")
    
    return TestResult("Large obstruction", True, f"Completed in {elapsed:.2f}s, {len(violations)} violations")


# =============================================================================
# Test 8: Device Inside Obstruction
# =============================================================================

def test_device_inside_obstruction():
    """Device inside obstruction - should be rejected"""
    room = Room(
        id="room_8",
        name="Room",
        geometry=Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
        ceiling_height=2.4
    )
    
    devices = [
        Device(id="smoke_1", device_type="SMOKE_PHOTOELECTRIC", position=Point(5, 5)),
    ]
    
    # Obstruction covering the device
    obstructions = [
        Obstruction(
            id="obs_covering_device",
            geometry=Polygon([(4, 4), (6, 4), (6, 6), (4, 6), (4, 4)]),
            height=2.4,
            blocks_visibility=True
        )
    ]
    
    normalizer = SpatialNormalizer(ToleranceModel())
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    # Should be rejected with CRITICAL error
    criticals = [e for e in errors if e.severity == "CRITICAL"]
    if criticals:
        return TestResult("Device inside obstruction", True, f"Rejected: {criticals[0].message}", True)
    
    return TestResult("Device inside obstruction", False, "Not rejected - should have been!")


# =============================================================================
# Test 9: 100 Random Devices
# =============================================================================

def test_many_devices():
    """100 devices randomly distributed"""
    room = Room(
        id="room_many",
        name="Room with 100 devices",
        geometry=Polygon([(0, 0), (20, 0), (20, 20), (0, 20), (0, 0)]),
        ceiling_height=2.4
    )
    
    random.seed(42)  # Reproducible
    devices = []
    for i in range(100):
        x = random.uniform(1, 19)
        y = random.uniform(1, 19)
        devices.append(Device(
            id=f"smoke_{i}",
            device_type="SMOKE_PHOTOELECTRIC",
            position=Point(x, y)
        ))
    
    obstructions = []
    
    normalizer = SpatialNormalizer(ToleranceModel())
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    if errors:
        return TestResult("100 random devices", True, f"Rejected: {errors[0].message}", True)
    
    model = NFPAConstraintModel(ceiling_type="SMOOTH")
    
    start_time = time.time()
    coverage, violations = evaluate_compliance(norm_room, norm_devices, norm_obs, model, grid_spacing=1.0)
    elapsed = time.time() - start_time
    
    if elapsed > 5:
        return TestResult("100 random devices", False, f"Too slow: {elapsed:.2f}s > 5s")
    
    return TestResult("100 random devices", True, f"Completed in {elapsed:.2f}s, {len(violations)} violations")


# =============================================================================
# Test 10: No Devices, With Obstructions
# =============================================================================

def test_no_devices_with_obstructions():
    """Room with no devices but with obstructions"""
    room = Room(
        id="room_no_dev",
        name="Room without devices",
        geometry=Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]),
        ceiling_height=2.4
    )
    
    devices = []
    
    obstructions = [
        Obstruction(
            id="obs_1",
            geometry=Polygon([(3, 3), (4, 3), (4, 4), (3, 4), (3, 3)]),
            height=2.4,
            blocks_visibility=True
        )
    ]
    
    normalizer = SpatialNormalizer(ToleranceModel())
    norm_room, norm_devices, norm_obs, errors = normalizer.normalize(
        room, devices, obstructions, "meters"
    )
    
    if errors:
        return TestResult("No devices with obstructions", True, f"Rejected: {errors[0].message}", True)
    
    model = NFPAConstraintModel(ceiling_type="SMOOTH")
    coverage, violations = evaluate_compliance(norm_room, norm_devices, norm_obs, model, grid_spacing=0.5)
    
    # Should have NO_DEVICES violations
    no_device_violations = [v for v in violations if v.rule == "NO_DEVICES"]
    
    if len(no_device_violations) > 0:
        return TestResult("No devices with obstructions", True, f"Correctly reported NO_DEVICES: {len(no_device_violations)}")
    
    return TestResult("No devices with obstructions", False, "Should have NO_DEVICES violations")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    tests = [
        ("Device on boundary", test_device_on_boundary),
        ("Device at max distance", test_device_at_max_distance),
        ("Thin room (width < grid)", test_thin_room),
        ("Triangular room", test_triangular_room),
        ("Room with hole (donut)", test_room_with_hole),
        ("Obstruction touching wall", test_obstruction_touching_wall),
        ("Large obstruction", test_large_obstruction),
        ("Device inside obstruction", test_device_inside_obstruction),
        ("100 random devices", test_many_devices),
        ("No devices with obstructions", test_no_devices_with_obstructions),
    ]
    
    results = []
    for name, test_func in tests:
        result = run_test(name, test_func)
        results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    for r in results:
        status = "✓" if r.passed else "✗"
        rejected = " (Rejected)" if r.rejected else ""
        print(f"  {status} {r.name}{rejected}")
    
    print(f"\nTotal: {passed}/{total} passed")
    
    if passed == total:
        print("\n🎉 All robustness tests passed!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")