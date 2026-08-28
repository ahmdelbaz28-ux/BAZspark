import { describe, expect, it } from "vitest";
import { validate } from "../index";

describe("engineering-calc package — validator", () => {
	it("should pass valid smoke inputs", () => {
		const result = validate({ tab: "smoke", ceilingHeightM: 3 });
		expect(result.valid).toBe(true);
		expect(result.errors).toHaveLength(0);
	});

	it("should reject negative smoke ceiling height", () => {
		const result = validate({ tab: "smoke", ceilingHeightM: -1 });
		expect(result.valid).toBe(false);
		expect(result.errors.some((e) => e.field === "ceilingHeightM")).toBe(true);
	});

	it("should reject smoke ceiling height over 50m", () => {
		const result = validate({ tab: "smoke", ceilingHeightM: 100 });
		expect(result.valid).toBe(false);
		expect(result.errors.some((e) => e.code === "RANGE")).toBe(true);
	});

	it("should pass valid battery inputs", () => {
		const result = validate({
			tab: "battery",
			standbyLoadA: 0.5,
			alarmLoadA: 1.0,
		});
		expect(result.valid).toBe(true);
	});

	it("should reject negative battery loads", () => {
		const result = validate({
			tab: "battery",
			standbyLoadA: -0.5,
			alarmLoadA: 1.0,
		});
		expect(result.valid).toBe(false);
	});

	it("should pass valid voltage drop inputs", () => {
		const result = validate({
			tab: "voltage",
			currentA: 10,
			lengthM: 50,
			awgGauge: "12",
		});
		expect(result.valid).toBe(true);
	});

	it("should reject missing voltage drop gauge", () => {
		const result = validate({
			tab: "voltage",
			currentA: 10,
			lengthM: 50,
			awgGauge: "",
		});
		expect(result.valid).toBe(false);
		expect(result.errors.some((e) => e.code === "REQUIRED")).toBe(true);
	});

	it("should pass valid detector inputs", () => {
		const result = validate({
			tab: "detectors",
			roomAreaM2: 100,
			ceilingHeightM: 3,
		});
		expect(result.valid).toBe(true);
	});

	it("should pass valid duct inputs", () => {
		const result = validate({ tab: "duct", ductWidthM: 0.3 });
		expect(result.valid).toBe(true);
	});
});
