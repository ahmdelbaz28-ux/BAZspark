/**
 * EngineeringRepository.ts — Concrete implementation of IEngineeringRepository.
 * Delegates engineering calculations to fullApi while maintaining clean domain interface contract.
 * Preserves 100% calculation accuracy and inputs/outputs.
 */

import type {
	IEngineeringRepository,
	QOMNCalculationRequest,
	QOMNCalculationResult,
} from "../../domain/repositories/IEngineeringRepository";
import { fullApi } from "../../services/fullApi";

export class EngineeringRepository implements IEngineeringRepository {
	async calculateQOMN(
		params: QOMNCalculationRequest,
	): Promise<QOMNCalculationResult> {
		try {
			const res = await fullApi.qomnCalculate(
				params as Record<string, unknown>,
			);
			if (res?.success) {
				return {
					success: true,
					detectors_required: res.data?.detectors_required as
						| number
						| undefined,
					spacing_meters: res.data?.spacing_meters as number | undefined,
					voltage_drop_volts: res.data?.voltage_drop_volts as
						| number
						| undefined,
					voltage_drop_pct: res.data?.voltage_drop_pct as number | undefined,
					battery_capacity_ah: res.data?.battery_capacity_ah as
						| number
						| undefined,
					compliance_status:
						(res.data?.compliance_status as string) || "COMPLIANT",
					recommendations: (res.data?.recommendations as string[]) || [],
				};
			}
			return {
				success: false,
				compliance_status: "CALCULATION_FAILED",
				recommendations: [res?.message || "Calculation failed"],
			};
		} catch (error) {
			return {
				success: false,
				compliance_status: "ERROR",
				recommendations: [
					error instanceof Error
						? error.message
						: "Network error during calculation",
				],
			};
		}
	}

	async calculateSmokeSpacing(
		length: number,
		width: number,
		height: number,
	): Promise<QOMNCalculationResult> {
		return this.calculateQOMN({
			room_length: length,
			room_width: width,
			ceiling_height: height,
		});
	}

	async calculateBatteryBackup(
		loadAh: number,
		standbyHours: number,
		alarmMinutes: number,
	): Promise<QOMNCalculationResult> {
		return this.calculateQOMN({
			battery_load_ah: loadAh,
			standby_hours: standbyHours,
			alarm_minutes: alarmMinutes,
		});
	}

	async calculateVoltageDrop(
		voltage: number,
		current: number,
		length: number,
		gauge: string,
	): Promise<QOMNCalculationResult> {
		return this.calculateQOMN({
			ps_voltage: voltage,
			ps_current: current,
			wire_length: length,
			wire_gauge: gauge,
		});
	}
}

export const engineeringRepository = new EngineeringRepository();
