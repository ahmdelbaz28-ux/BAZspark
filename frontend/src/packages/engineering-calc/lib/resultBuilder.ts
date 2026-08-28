import type { CalculationTab, EngineeringResult } from "../port";

export function buildSuccessResult(
	tab: CalculationTab,
	overrides: Partial<EngineeringResult> = {},
): EngineeringResult {
	return {
		success: true,
		complianceStatus: "COMPLIANT",
		recommendations: [],
		data: {},
		...overrides,
	};
}

export function buildFailureResult(
	message: string,
	overrides: Partial<EngineeringResult> = {},
): EngineeringResult {
	return {
		success: false,
		message,
		complianceStatus: "CALCULATION_FAILED",
		recommendations: [message],
		data: {},
		...overrides,
	};
}

export function mergePhysicsGuards(
	base: Record<string, unknown>,
	guards: Record<string, unknown>,
): Record<string, unknown> {
	return { ...base, physicsGuards: guards };
}
