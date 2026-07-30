"""
generative_design_usecase.py — Generative Design Interactor (Clean Architecture).
Decouples layout generation algorithms from API controllers.
Preserves 100% existing generation logic and data schemas.
"""

from typing import Any, Dict


class GenerativeDesignUseCase:
    def generate_layout_variants(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates 3 layout variants (Optimal, Cost-Effective, High-Redundancy)
        based on room dimensions, ceiling height, and hazard classification.
        """
        length = float(params.get("room_length", 10.0))
        width = float(params.get("room_width", 10.0))
        height = float(params.get("ceiling_height", 3.0))
        hazard = str(params.get("hazard_type", "LIGHT")).upper()

        # Calculate base spacing according to NFPA 72 standard bounds
        base_spacing = 9.1 if hazard == "LIGHT" else 6.1
        if height > 3.0:
            reduction = min(0.4, (height - 3.0) * 0.05)
            base_spacing *= (1.0 - reduction)

        variant_optimal = {
            "variant_id": "var_optimal",
            "name": "Optimal NFPA 72 Coverage",
            "spacing_meters": round(base_spacing, 2),
            "total_detectors": max(1, int((length / base_spacing) * (width / base_spacing))),
            "estimated_cost_usd": 1200.0,
        }

        variant_cost = {
            "variant_id": "var_cost_effective",
            "name": "Cost-Effective Layout",
            "spacing_meters": round(base_spacing * 1.1, 2),
            "total_detectors": max(1, int((length / (base_spacing * 1.1)) * (width / (base_spacing * 1.1)))),
            "estimated_cost_usd": 950.0,
        }

        variant_redundant = {
            "variant_id": "var_high_redundancy",
            "name": "High Redundancy & Life-Safety",
            "spacing_meters": round(base_spacing * 0.85, 2),
            "total_detectors": max(1, int((length / (base_spacing * 0.85)) * (width / (base_spacing * 0.85)))),
            "estimated_cost_usd": 1650.0,
        }

        return {
            "success": True,
            "room_dimensions": {"length": length, "width": width, "height": height},
            "hazard_type": hazard,
            "variants": [variant_optimal, variant_cost, variant_redundant],
        }


generative_design_usecase = GenerativeDesignUseCase()
