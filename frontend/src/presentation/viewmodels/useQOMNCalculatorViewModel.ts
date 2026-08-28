import { useState } from "react";
import { calculate, type EngineeringInputs, type EngineeringResult } from "@/packages/engineering-calc";

export type QOMNTab =
	| "smoke"
	| "heat"
	| "battery"
	| "voltage"
	| "detectors"
	| "duct";

export function useQOMNCalculatorViewModel() {
	const [activeTab, setActiveTab] = useState<QOMNTab>("smoke");
	const [calculating, setCalculating] = useState(false);
	const [lastResult, setLastResult] = useState<EngineeringResult | null>(null);

	const runCalculation = async (inputs: EngineeringInputs) => {
		setCalculating(true);
		try {
			const res = await calculate(inputs);
			setLastResult(res);
			return res;
		} finally {
			setCalculating(false);
		}
	};

	return {
		activeTab,
		setActiveTab,
		calculating,
		lastResult,
		runCalculation,
	};
}
