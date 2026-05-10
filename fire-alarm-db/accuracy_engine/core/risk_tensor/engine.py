from core.risk_tensor.baseline_risk import calculate_baseline_risk_field, perturb_baseline
from core.risk_tensor.aggregator import aggregate_tensors
from core.risk_tensor.tensor_types import RiskTensor, ImpactVector
from core.monte_carlo.scenario_generator import generate_scenario


def run_composite_risk_analysis(rooms: list, devices: list, validation: dict, num_scenarios: int = 100) -> dict:
    all_tensors = []
    base_coverage = validation.get("coverage", validation.get("overall_coverage", 0.95))

    baseline_fields = {}
    for room in rooms:
        baseline = calculate_baseline_risk_field(room, devices)
        baseline_fields[room.get("id")] = baseline

    for scenario_id in range(num_scenarios):
        for room in rooms:
            room_devices = [d for d in devices if d.get("room_id") == room.get("id")]
            scenario = generate_scenario(room_devices, room)

            baseline = baseline_fields.get(room.get("id"))
            if baseline:
                perturbed_points = perturb_baseline(baseline, scenario)
                avg_perturbed_risk = sum(p.risk_value for p in perturbed_points) / len(perturbed_points) if perturbed_points else 0
                coverage_after = base_coverage * (1 - avg_perturbed_risk * 0.5)
            else:
                coverage_after = base_coverage
                avg_perturbed_risk = 0.0

            coverage_loss = max(0.0, base_coverage - coverage_after)
            detection_delay = coverage_loss * 30.0
            exit_blocked = scenario.get("exit_blocked", False)
            evacuation_risk = 0.6 if exit_blocked else coverage_loss * 0.8
            failed_count = scenario.get("failed_count", 0)
            redundancy_loss = failed_count / max(scenario.get("total_devices", 1), 1)

            impact = ImpactVector(
                coverage_loss=coverage_loss,
                detection_delay_seconds=detection_delay,
                evacuation_risk_increase=evacuation_risk,
                redundancy_loss=redundancy_loss
            )

            failure_prob = avg_perturbed_risk
            confidence = 0.85
            if scenario.get("power_failed"):
                confidence -= 0.10
            confidence = max(0.5, confidence)

            tensor = RiskTensor(
                scenario_id=scenario_id,
                failure_probability=failure_prob,
                impact_vector=impact,
                spatial_map=[],
                confidence=confidence,
                affected_zones=[room.get("id", "unknown")],
                contributing_rules=["NFPA72-17.6.3.1-COVERAGE", "NFPA72-17.7.1-REDUNDANCY"]
            )

            all_tensors.append(tensor)

    composite_index = aggregate_tensors(all_tensors)

    baseline_summary = {}
    for room_id, baseline in baseline_fields.items():
        baseline_summary[room_id] = {
            "overall_baseline_risk": baseline.overall_baseline_risk,
            "detector_count": len(baseline.detector_influence_zones),
            "geometry_risk_factor": baseline.geometry_risk_factor,
            "room_type_risk_factor": baseline.room_type_risk_factor,
            "sample_points": len(baseline.points)
        }

    return {
        "scenarios_evaluated": num_scenarios,
        "tensors_generated": len(all_tensors),
        "has_baseline": True,
        "baseline_fields": baseline_summary,
        "composite_risk_index": composite_index.scalar,
        "risk_level": composite_index.risk_level,
        "confidence_interval": {
            "lower": composite_index.confidence_interval[0],
            "upper": composite_index.confidence_interval[1]
        },
        "dimensions": composite_index.contributing_dimensions,
        "explainability": composite_index.explainability
    }