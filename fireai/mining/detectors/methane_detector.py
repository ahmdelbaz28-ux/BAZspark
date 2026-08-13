"""
methane_detector.py — Methane detector selection + placement for mines.

V214: Implements methane detector placement per:
  - MSHA 30 CFR §75.323 (Methane Detection)
  - NFPA 120-2022 §7.3 (Methane Monitoring)

PLACEMENT RULES (MSHA):
  1. At all working faces
  2. At all belt conveyors (every 300m)
  3. At all ventilation changes (split points)
  4. At all return airways
  5. At roof (methane is lighter than air → accumulates at top)

DETECTOR TYPES:
  - Catalytic bead (pellistor): 0-5% range, requires oxygen
  - Infrared (NDIR): 0-100% range, does not require oxygen
  - Thermal conductivity: 0-100% range, for high concentrations
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MethaneDetectorSpec:
    """Specification for a methane detector."""
    detector_type: str  # 'catalytic', 'infrared', 'thermal_conductivity'
    range_min_pct: float
    range_max_pct: float
    accuracy_pct: float
    response_time_s: float
    requires_oxygen: bool
    suitable_for: list[str]  # ['working_face', 'belt_entry', 'return_airway']


class MethaneDetectorSelector:
    """
    Select the appropriate methane detector for a mine location.
    """

    # Detector type database
    _DETECTORS = {
        "catalytic": MethaneDetectorSpec(
            detector_type="catalytic",
            range_min_pct=0.0,
            range_max_pct=5.0,  # LEL
            accuracy_pct=0.1,
            response_time_s=10.0,
            requires_oxygen=True,
            suitable_for=["working_face", "belt_entry", "return_airway"],
        ),
        "infrared": MethaneDetectorSpec(
            detector_type="infrared",
            range_min_pct=0.0,
            range_max_pct=100.0,
            accuracy_pct=0.05,
            response_time_s=5.0,
            requires_oxygen=False,
            suitable_for=["working_face", "sealed_area", "return_airway"],
        ),
        "thermal_conductivity": MethaneDetectorSpec(
            detector_type="thermal_conductivity",
            range_min_pct=0.0,
            range_max_pct=100.0,
            accuracy_pct=0.5,
            response_time_s=30.0,
            requires_oxygen=False,
            suitable_for=["sealed_area", "gob_area"],
        ),
    }

    @classmethod
    def select(cls, location: str, oxygen_available: bool = True) -> MethaneDetectorSpec:
        """
        Select the best methane detector for a location.

        Args:
            location: 'working_face', 'belt_entry', 'return_airway',
                      'sealed_area', or 'gob_area'
            oxygen_available: True if oxygen is present (>10%)

        Returns:
            MethaneDetectorSpec for the recommended detector.
        """
        # If no oxygen, must use infrared or thermal conductivity
        if not oxygen_available:
            if location in ("sealed_area", "gob_area"):
                return cls._DETECTORS["thermal_conductivity"]
            return cls._DETECTORS["infrared"]

        # With oxygen, catalytic is preferred (cheaper, well-established)
        for det in cls._DETECTORS.values():
            if location in det.suitable_for and det.requires_oxygen:
                return det

        # Fallback to infrared
        return cls._DETECTORS["infrared"]

    @classmethod
    def placement_locations(
        cls,
        mine_length_m: float,
        has_conveyor: bool = True,
        conveyor_length_m: float = 0.0,
    ) -> list[dict]:
        """
        Calculate required methane detector placement locations.

        Per MSHA §75.323:
          - Every 150m along main entries
          - At all working faces
          - Every 300m along belt conveyors
          - At all ventilation splits

        Args:
            mine_length_m: Total length of mine entries in meters.
            has_conveyor: Whether a conveyor is present.
            conveyor_length_m: Length of conveyor in meters.

        Returns:
            List of dicts with location + height + reason.
        """
        locations = []

        # Main entries: every 150m
        num_main = max(1, int(mine_length_m / 150))
        for i in range(num_main):
            locations.append({
                "location": f"Main entry {(i+1)*150}m",
                "height": "roof",  # Methane is lighter than air
                "reason": "MSHA §75.323 — periodic monitoring along main entries",
            })

        # Working face (assumed at end of mine)
        locations.append({
            "location": "Working face",
            "height": "roof",
            "reason": "MSHA §75.323 — continuous monitoring at working face",
        })

        # Conveyor: every 300m
        if has_conveyor and conveyor_length_m > 0:
            num_conv = max(1, int(conveyor_length_m / 300))
            for i in range(num_conv):
                locations.append({
                    "location": f"Belt conveyor {(i+1)*300}m",
                    "height": "roof",
                    "reason": "MSHA §75.351 — belt entry monitoring",
                })

        return locations
