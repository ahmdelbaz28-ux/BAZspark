# File-level suppression removed per audit (V143 hardening).
"""
tests/test_pdf_to_rooms_adapter.py — Adapter seam tests.

Cross the REAL call shape of ``adapters.pdf_to_rooms_adapter``:
the workflow pipeline hands the adapter room DICTS
``{name, occupancy_type, area_sqm}`` (and canonical Rooms), and the
adapter must return a TYPED ``DetectorType`` whose ``.name`` is the
canonical uppercase technology — never a bare string, never a silent
per-room AttributeError.

These tests run everywhere (no langgraph dependency) and prove the
adapter contract independently of the workflow graph.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from fireai.core.contracts import DetectorType, Room

from adapters.pdf_to_rooms_adapter import (
    extract_rooms_from_walls,
    select_safe_detector_type,
)


# ── select_safe_detector_type — REAL caller shape (dict) ──────────────────────

class TestSelectSafeDetectorTypeDictShape:
    """The workflow passes dicts {name, occupancy_type, area_sqm} — test that shape."""

    def test_kitchen_room_dict_returns_heat_with_uppercase_name(self):
        detector = select_safe_detector_type(
            {"name": "Kitchen", "occupancy_type": "kitchen", "area_sqm": 20.0}
        )
        assert isinstance(detector, DetectorType)
        assert detector is DetectorType.HEAT
        assert detector.name == "HEAT"

    def test_mechanical_room_dict_returns_heat(self):
        detector = select_safe_detector_type(
            {"name": "Plant Room", "occupancy_type": "mechanical", "area_sqm": 50.0}
        )
        assert detector is DetectorType.HEAT

    def test_utility_room_dict_returns_heat(self):
        detector = select_safe_detector_type(
            {"name": "Utility", "occupancy_type": "utility", "area_sqm": 10.0}
        )
        assert detector is DetectorType.HEAT

    def test_duct_room_dict_returns_duct(self):
        detector = select_safe_detector_type(
            {"name": "AHU Duct", "occupancy_type": "duct", "area_sqm": 30.0}
        )
        assert detector is DetectorType.DUCT

    def test_hvac_room_dict_returns_duct(self):
        detector = select_safe_detector_type(
            {"name": "HVAC", "occupancy_type": "hvac", "area_sqm": 30.0}
        )
        assert detector is DetectorType.DUCT

    def test_high_ceiling_returns_beam(self):
        detector = select_safe_detector_type(
            {"name": "Atrium", "occupancy_type": "business", "area_sqm": 400.0},
            ceiling_height=12.0,
        )
        assert detector is DetectorType.BEAM

    def test_default_office_returns_smoke(self):
        detector = select_safe_detector_type(
            {"name": "Office", "occupancy_type": "business", "area_sqm": 50.0}
        )
        assert detector is DetectorType.SMOKE
        assert detector.name == "SMOKE"

    def test_unknown_occupancy_returns_smoke_conservative_default(self):
        detector = select_safe_detector_type(
            {"name": "Room_1", "occupancy_type": "unknown", "area_sqm": 25.0}
        )
        assert detector is DetectorType.SMOKE

    def test_missing_occupancy_key_defaults_to_unknown(self):
        detector = select_safe_detector_type({"name": "Lobby", "area_sqm": 90.0})
        assert detector is DetectorType.SMOKE

    def test_missing_area_key_does_not_crash(self):
        detector = select_safe_detector_type(
            {"name": "Office", "occupancy_type": "business"}
        )
        assert detector is DetectorType.SMOKE

    def test_caller_uses_dot_name_not_dict_key(self):
        # The workflow does detector.name — prove the return type has it.
        detector = select_safe_detector_type(
            {"name": "Kitchen", "occupancy_type": "kitchen", "area_sqm": 20.0}
        )
        assert detector.name == "HEAT"
        assert detector.name.startswith("HEAT")


# ── select_safe_detector_type — canonical Room shape ──────────────────────────

class TestSelectSafeDetectorTypeCanonicalRoom:
    def test_canonical_room_kitchen_returns_heat(self):
        room = Room(name="Kitchen", occupancy_type="kitchen", area_sqm=20.0)
        detector = select_safe_detector_type(room)
        assert detector is DetectorType.HEAT

    def test_canonical_room_office_returns_smoke(self):
        room = Room(name="Office", occupancy_type="business", area_sqm=50.0)
        detector = select_safe_detector_type(room)
        assert detector is DetectorType.SMOKE

    def test_canonical_room_high_ceiling_returns_beam(self):
        room = Room(name="Atrium", occupancy_type="business", area_sqm=400.0)
        detector = select_safe_detector_type(room, ceiling_height=11.0)
        assert detector is DetectorType.BEAM


# ── Contract violations ───────────────────────────────────────────────────────

class TestSelectSafeDetectorTypeContractViolations:
    def test_bare_string_raises_type_error_not_attribute_error(self):
        # The old bug: calling with (room_name, occupancy_type) as positional
        # args hit AttributeError on the string — silently swallowed by the
        # workflow's broad except. The contract must now fail loudly and
        # explicitly.
        with pytest.raises(TypeError, match="Room or a dict"):
            select_safe_detector_type("Kitchen", "kitchen")  # type: ignore[arg-type]

    def test_none_raises_type_error(self):
        with pytest.raises(TypeError):
            select_safe_detector_type(None)  # type: ignore[arg-type]


# ── extract_rooms_from_walls — canonical Room output ─────────────────────────

class TestExtractRoomsFromWalls:
    def test_empty_walls_returns_no_rooms_and_status(self):
        rooms, report = extract_rooms_from_walls([])
        assert rooms == []
        assert report["status"] == "no_walls"

    def test_none_walls_returns_no_rooms(self):
        rooms, report = extract_rooms_from_walls(None)
        assert rooms == []
        assert report["status"] == "no_walls"

    def test_returns_canonical_room_instances(self):
        shapely = pytest.importorskip("shapely")
        from shapely.geometry import LineString

        # A closed square loop of wall segments.
        walls = [
            LineString([(0, 0), (10, 0)]),
            LineString([(10, 0), (10, 10)]),
            LineString([(10, 10), (0, 10)]),
            LineString([(0, 10), (0, 0)]),
        ]
        rooms, report = extract_rooms_from_walls(walls)
        assert len(rooms) >= 1
        room = rooms[0]
        assert isinstance(room, Room)
        assert room.name.startswith("Room_")
        assert room.area_sqm == pytest.approx(100.0)
        assert room.polygon is not None

    def test_open_loop_returns_no_closed_loops_status(self):
        shapely = pytest.importorskip("shapely")
        from shapely.geometry import LineString

        walls = [
            LineString([(0, 0), (10, 0)]),
            LineString([(10, 0), (10, 10)]),
        ]
        rooms, report = extract_rooms_from_walls(walls)
        assert rooms == []
        assert report["status"] == "no_closed_loops"
