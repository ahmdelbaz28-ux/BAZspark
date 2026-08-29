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
			case "battery": {
				const b = inputs;
				try {
					const { calculateBatteryRequirements } = await import("@/engine/BatteryCalculator");
					const standbyHours = b.standbyHours ?? 24;
					const alarmMinutes = b.alarmMinutes ?? 5;
					const safetyFactor = b.safetyFactor ?? 1.25;
					const efficiency = b.efficiency ?? 1.0;

					const result = calculateBatteryRequirements({
						devices: [
							{ type: "Standby Load", standbyCurrent: b.standbyLoadA * 1000, alarmCurrent: 0, count: 1 },
							{ type: "Alarm Load", standbyCurrent: 0, alarmCurrent: b.alarmLoadA * 1000, count: 1 },
						],
						standbyHours,
						alarmMinutes,
						agingFactor: safetyFactor,
					});

					const adjustedCapacity = Number.parseFloat((result.requiredCapacity / efficiency).toFixed(2));

					return buildSuccessResult("battery", {
						batteryCapacityAh: adjustedCapacity,
						data: {
							...result,
							efficiency,
							finalRequiredCapacityAh: adjustedCapacity,
						},
					});
				} catch {
					return buildFailureResult("Client-side battery calculation failed");
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
			standbyHours: { min: 0, max: 168, unit: "_HOURS", description: "Standby duration in hours" },
			alarmMinutes: { min: 0, max: 120, unit: "_MINUTES", description: "Alarm duration in minutes" },
			safetyFactor: { min: 1.0, max: 3.0, unit: "_RATIO", description: "Battery safety/aging factor" },
			efficiency: { min: 0.01, max: 1.0, unit: "_RATIO", description: "Battery efficiency factor (0 to 1)" },
			currentA: { min: 0, max: 1000, unit: "_A", description: "Current in amperes" },
			lengthM: { min: 0, max: 10000, unit: "_M", description: "Length in meters" },
		};
	},

	validate,
};
