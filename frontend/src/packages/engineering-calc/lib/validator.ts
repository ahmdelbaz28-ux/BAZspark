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

function isFiniteNumber(value: unknown): value is number {
	return typeof value === "number" && Number.isFinite(value);
}

export function validate(inputs: EngineeringInputs): ValidationResult {
	const errors: Array<{ field: string; message: string; code?: string }> = [];

	switch (inputs.tab) {
		case "smoke": {
			const s = inputs as SmokeSpacingInputs;
			if (!isFiniteNumber(s.ceilingHeightM) || s.ceilingHeightM <= 0) {
				errors.push({
					field: "ceilingHeightM",
					message: "Ceiling height must be positive",
					code: "POSITIVE",
				});
			} else if (s.ceilingHeightM > 50) {
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
			if (!isFiniteNumber(h.ceilingHeightM) || h.ceilingHeightM <= 0) {
				errors.push({
					field: "ceilingHeightM",
					message: "Ceiling height must be positive",
					code: "POSITIVE",
				});
			} else if (h.ceilingHeightM > 50) {
				errors.push({
					field: "ceilingHeightM",
					message: "Ceiling height exceeds realistic maximum (50 m)",
					code: "RANGE",
				});
			}

			if (!isFiniteNumber(h.areaPerDetectorM2) || h.areaPerDetectorM2 <= 0) {
				errors.push({
					field: "areaPerDetectorM2",
					message: "Area per detector must be positive",
					code: "POSITIVE",
				});
			} else if (h.areaPerDetectorM2 > 500) {
				errors.push({
					field: "areaPerDetectorM2",
					message: "Area per detector exceeds realistic maximum (500 m²)",
					code: "RANGE",
				});
			}
			break;
		}
		case "battery": {
			const b = inputs as BatteryInputs;
			if (!isFiniteNumber(b.standbyLoadA) || b.standbyLoadA <= 0) {
				errors.push({
					field: "standbyLoadA",
					message: "Standby load must be positive",
					code: "POSITIVE",
				});
			}

			if (!isFiniteNumber(b.alarmLoadA) || b.alarmLoadA <= 0) {
				errors.push({
					field: "alarmLoadA",
					message: "Alarm load must be positive",
					code: "POSITIVE",
				});
			}

			if (b.safetyFactor !== undefined) {
				if (!isFiniteNumber(b.safetyFactor) || b.safetyFactor <= 0) {
					errors.push({
						field: "safetyFactor",
						message: "Safety factor must be positive",
						code: "POSITIVE",
					});
				}
			}

			if (b.standbyHours !== undefined) {
				if (!isFiniteNumber(b.standbyHours) || b.standbyHours < 0) {
					errors.push({
						field: "standbyHours",
						message: "Standby hours cannot be negative",
						code: "NON_NEGATIVE",
					});
				}
			}

			if (b.alarmMinutes !== undefined) {
				if (!isFiniteNumber(b.alarmMinutes) || b.alarmMinutes < 0) {
					errors.push({
						field: "alarmMinutes",
						message: "Alarm minutes cannot be negative",
						code: "NON_NEGATIVE",
					});
				}
			}

			if (b.efficiency !== undefined) {
				if (!isFiniteNumber(b.efficiency) || b.efficiency <= 0 || b.efficiency > 1) {
					errors.push({
						field: "efficiency",
						message: "Efficiency must be between 0 and 1",
						code: "RANGE",
					});
				}
			}
			break;
		}
		case "voltage": {
			const v = inputs as VoltageDropInputs;
			if (!isFiniteNumber(v.currentA) || v.currentA <= 0) {
				errors.push({
					field: "currentA",
					message: "Current must be positive",
					code: "POSITIVE",
				});
			}

			if (!isFiniteNumber(v.lengthM) || v.lengthM <= 0) {
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
			if (!isFiniteNumber(d.roomAreaM2) || d.roomAreaM2 <= 0) {
				errors.push({
					field: "roomAreaM2",
					message: "Room area must be positive",
					code: "POSITIVE",
				});
			}

			if (!isFiniteNumber(d.ceilingHeightM) || d.ceilingHeightM <= 0) {
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
			if (!isFiniteNumber(d.ductWidthM) || d.ductWidthM <= 0) {
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
