import type { CalculationMode, EngineeringCalculationPort, EngineeringInputs, EngineeringResult } from "../port";
import { httpAdapter } from "../adapters/httpAdapter";
import { clientAdapter } from "../adapters/clientAdapter";
import { inMemoryAdapter } from "../adapters/inMemoryAdapter";
import { validate } from "./validator";

let currentAdapter: EngineeringCalculationPort = httpAdapter;

export function setAdapter(adapter: EngineeringCalculationPort): void {
	currentAdapter = adapter;
}

export function useServerMode(_apiUrl?: string): void {
	currentAdapter = httpAdapter;
}

export function useClientMode(): void {
	currentAdapter = clientAdapter;
}

export function useTestMode(): void {
	currentAdapter = inMemoryAdapter;
}

export function getCurrentMode(): CalculationMode {
	if (currentAdapter === httpAdapter) return "server";
	if (currentAdapter === clientAdapter) return "client";
	if (currentAdapter === inMemoryAdapter) return "test";
	return "server";
}

export async function calculate(
	inputs: EngineeringInputs,
	mode?: CalculationMode,
): Promise<EngineeringResult> {
	const effectiveMode = mode ?? getCurrentMode();

	switch (effectiveMode) {
	case "client":
			return clientAdapter.calculate(inputs);
	case "server":
			return httpAdapter.calculate(inputs);
	case "test":
			return inMemoryAdapter.calculate(inputs);
	case "auto":
		default:
			if (inputs.tab === "voltage") {
				return clientAdapter.calculate(inputs);
			}
			return httpAdapter.calculate(inputs);
	}
}

export { validate };
