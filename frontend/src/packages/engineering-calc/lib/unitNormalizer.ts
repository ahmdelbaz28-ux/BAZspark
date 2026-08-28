import type { BatteryInputs, CalculationTab, EngineeringInputs, VoltageDropInputs } from "../port";

export function normalizeEngineeringInputs(inputs: EngineeringInputs): EngineeringInputs {
	if (inputs.tab === "voltage") {
		const v = inputs as VoltageDropInputs;
		return {
			...v,
			supplyVoltageV: v.supplyVoltageV ?? 24,
			maxDropPct: v.maxDropPct ?? 5,
		};
	}
	if (inputs.tab === "battery") {
		const b = inputs as BatteryInputs;
		return {
			...b,
			standbyHours: b.standbyHours ?? 24,
			alarmMinutes: b.alarmMinutes ?? 5,
			safetyFactor: b.safetyFactor ?? 1.2,
			efficiency: b.efficiency ?? 0.85,
		};
	}
	return inputs;
}

export function suffixForTab(tab: CalculationTab): string {
	switch (tab) {
		case "smoke":
			return "_M";
		case "heat":
			return "_M";
		case "battery":
			return "_A";
		case "voltage":
			return "_M";
		case "detectors":
			return "_M";
		case "duct":
			return "_M";
		default:
			return "_M";
	}
}

export function assertSuffix(value: number, suffix: string, fieldName: string): void {
	const valid = ["_M", "_FT", "_A", "_AH"].includes(suffix);
	if (!valid) {
		throw new Error(`Invalid unit suffix ${suffix} for field ${fieldName}`);
	}
}
