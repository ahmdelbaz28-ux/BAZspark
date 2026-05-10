from core.risk_tensor.tensor_builder import build_risk_tensor
from core.risk_tensor.aggregator import aggregate_tensors
from core.monte_carlo.scenario_generator import generate_scenario


def run_composite_risk_analysis(rooms: list, devices: list, validation: dict, num_scenarios: int = 100) -> dict:
    all_tensors = []
    base_coverage = validation.get("coverage", validation.get("overall_coverage", 0.95))

    for scenario_id in range(num_scenarios):
        for room in rooms:
            room_devices = [d for d in devices if d.get("room_id") == room.get("id")]
            scenario = generate_scenario(room_devices, room)

            coverage_after = base_coverage
            if scenario.get("failed_count", 0) > 0:
                survival_ratio = (len(room_devices) - scenario["failed_count"]) / max(len(room_devices), 1)
                coverage_after = base_coverage * survival_ratio

            tensor = build_risk_tensor(
                scenario_id=scenario_id,
                room=room,
                devices=room_devices,
                failure_scenario=scenario,
                coverage_after_failure=coverage_after,
                base_coverage=base_coverage
            )

            all_tensors.append(tensor)

    composite_index = aggregate_tensors(all_tensors)

    return {
        "scenarios_evaluated": num_scenarios,
        "tensors_generated": len(all_tensors),
        "composite_risk_index": composite_index.scalar,
        "risk_level": composite_index.risk_level,
        "confidence_interval": {
            "lower": composite_index.confidence_interval[0],
            "upper": composite_index.confidence_interval[1]
        },
        "dimensions": composite_index.contributing_dimensions,
        "spatial_heatmap": composite_index.spatial_heatmap,
        "explainability": composite_index.explainability
    }