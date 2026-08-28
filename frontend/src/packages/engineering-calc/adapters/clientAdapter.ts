import type { EngineeringCalculationPort, EngineeringInputs, EngineeringResult, PhysicsGuards } from "../port";
import { buildFailureResult, buildSuccessResult } from "../lib/resultBuilder";
import { validate } from "../lib/validator";

export const clientAdapter: EngineeringCalculationPort = {
	async calculate(inputs: EngineeringInputs): Promise<EngineeringResult> {
		const validation = validate(inputs);
		if (!validation.valid) {
			return buildFailureResult("Validation failed", { data: { errors: validation.errors } });
		}

		switch (inputs.tab) {
			case "voltage": {
				const v = inputs;
				try {
					const { calculateVoltageDrop } = await import("@/engine/CalculationEngine");
					const result = calculateVoltageDrop(
						v.currentA,
						v.lengthM,
						"Cu",
						2.5,
						0.85,
						v.supplyVoltageV ?? 24,
						"power",
						"single",
					);
					return buildSuccessResult("voltage", {
						voltageDropVolts: result.absoluteVoltage,
						voltageDropPct: result.percentage,
						data: {
							status: result.status,
							limit: result.limit,
							formula: result.formula,
						},
					});
				} catch {
					return buildFailureResult("Client-side voltage drop calculation failed");
				}
			}
			default:
				return buildFailureResult(
					`Client-side calculation for ${inputs.tab} is not yet implemented. Use server mode for authoritative results.`,
				);
		}
	},

	async getPhysicsGuards(): Promise<PhysicsGuards> {
		return {
			ceilingHeightM: { min: 0, max: 50, unit: "_M", description: "Ceiling height in meters" },
			areaPerDetectorM2: { min: 0, max: 500, unit: "_M2", description: "Area per detector in m²" },
			standbyLoadA: { min: 0, max: 100, unit: "_A", description: "Standby load in amperes" },
			alarmLoadA: { min: 0, max: 100, unit: "_A", description: "Alarm load in amperes" },
			currentA: { min: 0, max: 1000, unit: "_A", description: "Current in amperes" },
			lengthM: { min: 0, max: 10000, unit: "_M", description: "Length in meters" },
		};
	},

	validate,
};
