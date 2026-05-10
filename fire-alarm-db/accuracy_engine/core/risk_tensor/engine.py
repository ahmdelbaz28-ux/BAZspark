from core.risk_tensor.system_topology import build_system_topology, apply_perturbation, calculate_risk_field
from core.risk_tensor.aggregator import aggregate_tensors
from core.risk_tensor.tensor_types import RiskTensor, ImpactVector
from core.monte_carlo.scenario_generator import generate_scenario


def run_composite_risk_analysis(rooms: list, devices: list, validation: dict, num_scenarios: int = 100) -> dict:
    all_tensors = []
    base_coverage = validation.get("coverage", validation.get("overall_coverage", 0.95))

    topologies = {}
    for room in rooms:
        topology = build_system_topology(room, devices)
        topologies[room.get("id")] = topology

    for scenario_id in range(num_scenarios):
        for room in rooms:
            room_devices = [d for d in devices if d.get("room_id") == room.get("id")]
            scenario = generate_scenario(room_devices, room)

            topology = topologies.get(room.get("id"))
            if not topology:
                continue

            perturbed = apply_perturbation(topology, scenario)

            risk_values = []
            for key in topology.spatial_index:
                for (x, y) in topology.spatial_index[key]:
                    risk = calculate_risk_field(perturbed, x, y)
                    risk_values.append(risk)

            avg_risk = sum(risk_values) / len(risk_values) if risk_values else 0.0
            coverage_after = base_coverage * (1 - avg_risk * 0.5)

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

            confidence = 0.85
            if scenario.get("power_failed"):
                confidence -= 0.10
            confidence = max(0.5, confidence)

            tensor = RiskTensor(
                scenario_id=scenario_id,
                failure_probability=avg_risk,
                impact_vector=impact,
                spatial_map=[],
                confidence=confidence,
                affected_zones=[room.get("id", "unknown")],
                contributing_rules=["NFPA72-17.6.3.1-COVERAGE", "NFPA72-17.7.1-REDUNDANCY"]
            )

            all_tensors.append(tensor)

    composite_index = aggregate_tensors(all_tensors)

    topology_summary = {}
    for room_id, topology in topologies.items():
        topology_summary[room_id] = {
            "room_type": topology.room_type,
            "nodes_count": len(topology.nodes),
            "edges_count": len(topology.edges),
            "influence_fields": len(topology.influence_fields),
            "room_type_risk_factor": topology.room_type_risk_factor,
            "geometry_risk_factor": topology.geometry_risk_factor
        }

    return {
        "scenarios_evaluated": num_scenarios,
        "tensors_generated": len(all_tensors),
        "has_system_topology": True,
        "topologies": topology_summary,
        "composite_risk_index": composite_index.scalar,
        "risk_level": composite_index.risk_level,
        "confidence_interval": {
            "lower": composite_index.confidence_interval[0],
            "upper": composite_index.confidence_interval[1]
        },
        "dimensions": composite_index.contributing_dimensions,
        "explainability": composite_index.explainability
    }