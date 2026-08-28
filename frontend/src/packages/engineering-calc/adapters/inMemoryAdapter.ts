import type { EngineeringCalculationPort, EngineeringInputs, EngineeringResult, PhysicsGuards } from "../port";
import { buildFailureResult, buildSuccessResult } from "../lib/resultBuilder";
import { validate } from "../lib/validator";

const DETERMINISTIC_RESULTS: Record<string, Partial<EngineeringResult>> = {
	smoke: { spacingMeters: 9.2, detectorsRequired: 12, complianceStatus: "COMPLIANT" },
	heat: { spacingMeters: 6.5, detectorsRequired: 18, complianceStatus: "COMPLIANT" },
	battery: { batteryCapacityAh: 24.5, complianceStatus: "COMPLIANT" },
	voltage: { voltageDropVolts: 0.8, voltageDropPct: 3.3, complianceStatus: "COMPLIANT" },
	detectors: { detectorsRequired: 8, complianceStatus: "COMPLIANT" },
	duct: { ductResults: { placed: 3, compliant: true }, complianceStatus: "COMPLIANT" },
};

export const inMemoryAdapter: EngineeringCalculationPort = {
	async calculate(inputs: EngineeringInputs): Promise<EngineeringResult> {
		const validation = validate(inputs);
		if (!validation.valid) {
			return buildFailureResult("Validation failed", { data: { errors: validation.errors } });
		}

		const base = DETERMINISTIC_RESULTS[inputs.tab] ?? {};
		return buildSuccessResult(inputs.tab, {
			...base,
			data: {
				...base,
				_source: "inMemoryAdapter",
				_tab: inputs.tab,
			},
		});
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
