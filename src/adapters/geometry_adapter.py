"""
Geometry Adapter — Infrastructure Layer
====================================
Converts JSON/List polygons to Shapely geometries for ComplianceOracle.

This adapter is the bridge between:
- Layer 2 (Application): JSON polygons from generate_report.py
- Layer 4 (Validation): ComplianceOracle expecting Shapely objects
"""

from shapely.geometry import Polygon, Point
from typing import List, Tuple


def json_polygon_to_shapely(polygon_json: List[List[float]]) -> Polygon:
    """
    Convert JSON polygon [[x1,y1], [x2,y2], ...] to Shapely Polygon.
    Fixes self-intersecting polygons automatically.
    """
    if len(polygon_json) < 3:
        raise ValueError(f"Polygon must have >= 3 points, got {len(polygon_json)}")

    coords = [(float(p[0]), float(p[1])) for p in polygon_json]
    if coords[0] == coords[-1]:
        coords = coords[:-1]

    poly = Polygon(coords)

    if not poly.is_valid:
        poly = poly.buffer(0)

    if not poly.is_valid:
        raise ValueError(f"Polygon invalid even after buffer(0): {polygon_json}")

    return poly


def coordinate_to_shapely_point(x: float, y: float, z: float = 0.0) -> Point:
    """Convert x,y,z coordinates to Shapely Point (2D for Oracle)."""
    return Point(float(x), float(y))


def calculate_polygon_area(polygon_json: List[List[float]]) -> float:
    """Calculate area in square meters from JSON polygon."""
    poly = json_polygon_to_shapely(polygon_json)
    return poly.area


def calculate_polygon_perimeter(polygon_json: List[List[float]]) -> float:
    """Calculate perimeter in meters from JSON polygon."""
    poly = json_polygon_to_shapely(polygon_json)
    return poly.length


def calculate_area(polygon_json: List[List[float]]) -> float:
    """Calculate area (alias for compatibility)."""
    return calculate_polygon_area(polygon_json)


def is_point_inside_polygon(x: float, y: float, polygon_json: List[List[float]]) -> bool:
    """Check if a point is inside the polygon."""
    poly = json_polygon_to_shapely(polygon_json)
    point = Point(float(x), float(y))
    return poly.contains(point) or poly.touches(point)


def apply_obstructions(room_polygon: Polygon, obstructions) -> Polygon:
    """
    Subtract obstructions from room polygon to get effective coverage area.
    
    Handles multiple input types:
    - dict with 'polygon' key
    - Shapely Polygon
    - List of either
    """
    if not obstructions:
        return room_polygon

    # Normalize input to list
    if isinstance(obstructions, Polygon):
        obstructions = [obstructions]
    elif isinstance(obstructions, dict):
        obstructions = [obstructions]
    elif not isinstance(obstructions, list):
        return room_polygon

    effective_polygon = room_polygon
    for obs in obstructions:
        # Handle different types
        if isinstance(obs, Polygon):
            obs_polygon = obs
        elif isinstance(obs, dict) and 'polygon' in obs:
            obs_polygon = obs['polygon']
            if not isinstance(obs_polygon, Polygon):
                obs_polygon = json_polygon_to_shapely(obs_polygon)
        else:
            continue

        if not obs_polygon or not obs_polygon.is_valid:
            continue

        effective_polygon = effective_polygon.difference(obs_polygon)
        if not effective_polygon.is_valid:
            effective_polygon = effective_polygon.buffer(0)

    return effective_polygon
