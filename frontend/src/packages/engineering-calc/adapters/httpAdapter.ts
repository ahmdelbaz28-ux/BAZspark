import type { EngineeringCalculationPort, EngineeringInputs, EngineeringResult, PhysicsGuards } from "../port";
import { buildFailureResult, buildSuccessResult } from "../lib/resultBuilder";
import { qomnApi, qomnExtendedApi } from "@/services/fullApi";
import { validate } from "../lib/validator";

export const httpAdapter: EngineeringCalculationPort = {
	async calculate(inputs: EngineeringInputs): Promise<EngineeringResult> {
		const validation = validate(inputs);
		if (!validation.valid) {
			return buildFailureResult("Validation failed", { data: { errors: validation.errors } });
		}

		try {
			switch (inputs.tab) {
				case "smoke": {
					const res = await qomnApi.smokeSpacing({ ceiling_height_m: inputs.ceilingHeightM });
					return buildSuccessResult("smoke", {
						spacingMeters: (res as Record<string, unknown>)?.spacing_meters as number | undefined,
						data: res as Record<string, unknown>,
					});
				}
				case "heat": {
					const res = await qomnApi.heatSpacing({
						ceiling_height_m: inputs.ceilingHeightM,
						area_per_detector_m2: inputs.areaPerDetectorM2,
					});
					return buildSuccessResult("heat", {
						spacingMeters: (res as Record<string, unknown>)?.spacing_meters as number | undefined,
						data: res as Record<string, unknown>,
					});
				}
				case "battery": {
					const res = await qomnApi.battery({
						standby_load_a: inputs.standbyLoadA,
						alarm_load_a: inputs.alarmLoadA,
						standby_hours: inputs.standbyHours,
						alarm_minutes: inputs.alarmMinutes,
						safety_factor: inputs.safetyFactor,
						efficiency: inputs.efficiency,
					});
					return buildSuccessResult("battery", {
						batteryCapacityAh: (res as Record<string, unknown>)?.battery_capacity_ah as
							| number
							| undefined,
						data: res as Record<string, unknown>,
					});
				}
				case "voltage": {
					const res = await qomnApi.voltageDrop({
						current_a: inputs.currentA,
						length_m: inputs.lengthM,
						awg_gauge: inputs.awgGauge,
						supply_voltage_v: inputs.supplyVoltageV,
						max_drop_pct: inputs.maxDropPct,
					});
					return buildSuccessResult("voltage", {
						voltageDropVolts: (res as Record<string, unknown>)?.voltage_drop_volts as
							| number
							| undefined,
						voltageDropPct: (res as Record<string, unknown>)?.voltage_drop_pct as number | undefined,
						data: res as Record<string, unknown>,
					});
				}
				case "detectors": {
					const res = await qomnExtendedApi.placeDetectors({
						room_area_m2: inputs.roomAreaM2,
						ceiling_height_m: inputs.ceilingHeightM,
						detector_type: inputs.detectorType,
					});
					return buildSuccessResult("detectors", {
						detectorLayout: res as Record<string, unknown>,
						data: res as Record<string, unknown>,
					});
				}
				case "duct": {
					const res = await qomnExtendedApi.placeDuct({
						duct_width_m: inputs.ductWidthM,
						duct_velocity_mps: inputs.ductVelocityMps,
						airflow_direction: inputs.airflowDirection,
					});
					return buildSuccessResult("duct", {
						ductResults: res as Record<string, unknown>,
						data: res as Record<string, unknown>,
					});
				}
			}
		} catch (error) {
			return buildFailureResult(
				error instanceof Error ? error.message : "Server calculation failed",
			);
		}
	},

	async getPhysicsGuards(): Promise<PhysicsGuards> {
		const res = await qomnApi.getPhysicsGuards();
		return res as PhysicsGuards;
	},

	validate,
};
