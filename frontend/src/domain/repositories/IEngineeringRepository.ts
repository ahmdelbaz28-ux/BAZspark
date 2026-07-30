/**
 * IEngineeringRepository.ts — Domain Repository Interface for QOMN Engineering Calculations.
 * Follows Clean Architecture (Domain Layer: Repository Abstraction).
 * Preserves 100% existing calculation data contracts.
 */

export interface QOMNCalculationRequest {
	room_length?: number;
	room_width?: number;
	ceiling_height?: number;
	ambient_temp?: number;
	hazards?: string[];
	ps_voltage?: number;
	ps_current?: number;
	wire_length?: number;
	wire_gauge?: string;
	battery_load_ah?: number;
	standby_hours?: number;
	alarm_minutes?: number;
}

export interface QOMNCalculationResult {
	success: boolean;
	detectors_required?: number;
	spacing_meters?: number;
	voltage_drop_volts?: number;
	voltage_drop_pct?: number;
	battery_capacity_ah?: number;
	compliance_status?: string;
	recommendations?: string[];
}

export interface IEngineeringRepository {
	calculateQOMN(params: QOMNCalculationRequest): Promise<QOMNCalculationResult>;
	calculateSmokeSpacing(length: number, width: number, height: number): Promise<QOMNCalculationResult>;
	calculateBatteryBackup(loadAh: number, standbyHours: number, alarmMinutes: number): Promise<QOMNCalculationResult>;
	calculateVoltageDrop(voltage: number, current: number, length: number, gauge: string): Promise<QOMNCalculationResult>;
}
