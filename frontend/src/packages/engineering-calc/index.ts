import type {
	CalculationMode,
	EngineeringCalculationPort,
	EngineeringInputs,
	EngineeringResult,
	PhysicsGuards,
	ValidationResult,
} from "./port";
import { calculate, setAdapter, useServerMode, useTestMode, useClientMode, validate } from "./lib/calculator";

export { calculate, setAdapter, useServerMode, useTestMode, useClientMode, validate };
export type {
	CalculationMode,
	EngineeringCalculationPort,
	EngineeringInputs,
	EngineeringResult,
	PhysicsGuards,
	ValidationResult,
};
