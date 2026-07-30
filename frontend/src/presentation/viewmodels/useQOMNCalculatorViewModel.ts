/**
 * useQOMNCalculatorViewModel.ts — ViewModel for QOMN Engineering Calculator Page.
 * Implements MVVM Architecture (Presentation Layer ViewModel).
 * Handles tab navigation, calculation state, and delegates calculation requests to EngineeringRepository.
 */

import { useState } from "react";
import { engineeringRepository } from "../../data/repositories/EngineeringRepository";
import { QOMNCalculationRequest, QOMNCalculationResult } from "../../domain/repositories/IEngineeringRepository";

export type QOMNTab = "smoke" | "heat" | "battery" | "voltage" | "detectors" | "duct";

export function useQOMNCalculatorViewModel() {
	const [activeTab, setActiveTab] = useState<QOMNTab>("smoke");
	const [calculating, setCalculating] = useState(false);
	const [lastResult, setLastResult] = useState<QOMNCalculationResult | null>(null);

	const runCalculation = async (params: QOMNCalculationRequest) => {
		setCalculating(true);
		try {
			const res = await engineeringRepository.calculateQOMN(params);
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
