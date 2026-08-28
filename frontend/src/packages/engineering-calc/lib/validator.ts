import type {
	BatteryInputs,
	EngineeringInputs,
	HeatSpacingInputs,
	PlaceDetectorsInputs,
	PlaceDuctInputs,
	SmokeSpacingInputs,
	ValidationResult,
	VoltageDropInputs,
} from "../port";

export function validate(inputs: EngineeringInputs): ValidationResult {
	const errors: Array<{ field: string; message: string; code?: string }> = [];

	switch (inputs.tab) {
		case "smoke": {
			const s = inputs as SmokeSpacingInputs;
			if (s.ceilingHeightM <= 0) {
				errors.push({
					field: "ceilingHeightM",
					message: "Ceiling height must be positive",
					code: "POSITIVE",
				});
			}
			if (s.ceilingHeightM > 50) {
				errors.push({
					field: "ceilingHeightM",
					message: "Ceiling height exceeds realistic maximum (50 m)",
					code: "RANGE",
				});
			}
			break;
		}
		case "heat": {
			const h = inputs as HeatSpacingInputs;
			if (h.ceilingHeightM <= 0) {
				errors.push({
					field: "ceilingHeightM",
					message: "Ceiling height must be positive",
					code: "POSITIVE",
				});
			}
			if (h.areaPerDetectorM2 <= 0) {
				errors.push({
					field: "areaPerDetectorM2",
					message: "Area per detector must be positive",
					code: "POSITIVE",
				});
			}
			break;
		}
		case "battery": {
			const b = inputs as BatteryInputs;
			if (b.standbyLoadA <= 0) {
				errors.push({
					field: "standbyLoadA",
					message: "Standby load must be positive",
					code: "POSITIVE",
				});
			}
			if (b.alarmLoadA <= 0) {
				errors.push({
					field: "alarmLoadA",
					message: "Alarm load must be positive",
					code: "POSITIVE",
				});
			}
			if (b.standbyHours !== undefined && b.standbyHours < 0) {
				errors.push({
					field: "standbyHours",
					message: "Standby hours cannot be negative",
					code: "NON_NEGATIVE",
				});
			}
			if (b.alarmMinutes !== undefined && b.alarmMinutes < 0) {
				errors.push({
					field: "alarmMinutes",
					message: "Alarm minutes cannot be negative",
					code: "NON_NEGATIVE",
				});
			}
			break;
		}
		case "voltage": {
			const v = inputs as VoltageDropInputs;
			if (v.currentA <= 0) {
				errors.push({
					field: "currentA",
					message: "Current must be positive",
					code: "POSITIVE",
				});
			}
			if (v.lengthM <= 0) {
				errors.push({
					field: "lengthM",
					message: "Length must be positive",
					code: "POSITIVE",
				});
			}
			if (!v.awgGauge || v.awgGauge.trim() === "") {
				errors.push({
					field: "awgGauge",
					message: "Wire gauge is required",
					code: "REQUIRED",
				});
			}
			break;
		}
		case "detectors": {
			const d = inputs as PlaceDetectorsInputs;
			if (d.roomAreaM2 <= 0) {
				errors.push({
					field: "roomAreaM2",
					message: "Room area must be positive",
					code: "POSITIVE",
				});
			}
			if (d.ceilingHeightM <= 0) {
				errors.push({
					field: "ceilingHeightM",
					message: "Ceiling height must be positive",
					code: "POSITIVE",
				});
			}
			break;
		}
		case "duct": {
			const d = inputs as PlaceDuctInputs;
			if (d.ductWidthM <= 0) {
				errors.push({
					field: "ductWidthM",
					message: "Duct width must be positive",
					code: "POSITIVE",
				});
			}
			break;
		}
	}

	return {
		valid: errors.length === 0,
		errors,
	};
}
