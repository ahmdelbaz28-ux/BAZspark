export type CalculationTab = "smoke" | "heat" | "battery" | "voltage" | "detectors" | "duct";

export interface SmokeSpacingInputs {
	tab: "smoke";
	ceilingHeightM: number;
}

export interface HeatSpacingInputs {
	tab: "heat";
	ceilingHeightM: number;
	areaPerDetectorM2: number;
}

export interface BatteryInputs {
	tab: "battery";
	standbyLoadA: number;
	alarmLoadA: number;
	standbyHours?: number;
	alarmMinutes?: number;
	safetyFactor?: number;
	efficiency?: number;
}

export interface VoltageDropInputs {
	tab: "voltage";
	currentA: number;
	lengthM: number;
	awgGauge: string;
	supplyVoltageV?: number;
	maxDropPct?: number;
}

export interface PlaceDetectorsInputs {
	tab: "detectors";
	roomAreaM2: number;
	ceilingHeightM: number;
	detectorType?: string;
}

export interface PlaceDuctInputs {
	tab: "duct";
	ductWidthM: number;
	ductVelocityMps?: number;
	airflowDirection?: string;
}

export type EngineeringInputs =
	| SmokeSpacingInputs
	| HeatSpacingInputs
	| BatteryInputs
	| VoltageDropInputs
	| PlaceDetectorsInputs
	| PlaceDuctInputs;

export interface EngineeringResult {
	success: boolean;
	message?: string;
	complianceStatus?: string;
	recommendations?: string[];
	data?: Record<string, unknown>;
	detectorsRequired?: number;
	spacingMeters?: number;
	batteryCapacityAh?: number;
	voltageDropVolts?: number;
	voltageDropPct?: number;
	ductResults?: Record<string, unknown>;
	detectorLayout?: Record<string, unknown>;
}

export interface ValidationResult {
	valid: boolean;
	errors: Array<{ field: string; message: string; code?: string }>;
}

export interface PhysicsGuards {
	[key: string]: {
		min?: number;
		max?: number;
		unit: string;
		description: string;
	};
}

export type CalculationMode = "client" | "server" | "auto" | "test";

export interface EngineeringCalculationPort {
	calculate(inputs: EngineeringInputs): Promise<EngineeringResult>;
	getPhysicsGuards(): Promise<PhysicsGuards>;
	validate(inputs: EngineeringInputs): ValidationResult;
}
