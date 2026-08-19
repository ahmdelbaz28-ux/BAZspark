import { act, renderHook } from "@testing-library/react";
import type React from "react";
import { describe, expect, it } from "vitest";
import { AIControllerProvider, useAIController } from "../AIControllerContext";

describe("AIControllerContext — Phase 1 Vertical Slice Frontend Suite", () => {
	const wrapper = ({ children }: { children: React.ReactNode }) => (
		<AIControllerProvider>{children}</AIControllerProvider>
	);

	it("should initialize with clean default state", () => {
		const { result } = renderHook(() => useAIController(), { wrapper });
		expect(result.current.isAiActive).toBe(false);
		expect(result.current.isPlanning).toBe(false);
		expect(result.current.previewDevices).toHaveLength(0);
		expect(result.current.proposedCommand).toBeNull();
		expect(result.current.currentRevision).toBe(1);
		expect(result.current.concurrencyError).toBeNull();
	});

	it("should submit intent, plan dry-run preview, and report token telemetry", async () => {
		const { result } = renderHook(() => useAIController(), { wrapper });

		await act(async () => {
			await result.current.submitIntent("proj-frontend-01", "room-101", {
				width_m: 10.0,
				length_m: 15.0,
				ceiling_height_m: 3.0,
			});
		});

		expect(result.current.isAiActive).toBe(true);
		expect(result.current.previewDevices.length).toBeGreaterThan(0);
		expect(result.current.proposedCommand).not.toBeNull();
		expect(result.current.proposedCommand?.expectedRevision).toBe(1);
		expect(result.current.tokenTelemetry).not.toBeNull();
		expect(result.current.tokenTelemetry?.measured_tokens).toBeLessThanOrEqual(1500);
	});

	it("should successfully commit approved proposal and increment revision", async () => {
		const { result } = renderHook(() => useAIController(), { wrapper });

		await act(async () => {
			await result.current.submitIntent("proj-frontend-02", "room-102", {
				width_m: 8.0,
				length_m: 12.0,
				ceiling_height_m: 3.0,
			});
		});

		let committedDevicesCount = 0;
		let committedRevision = 0;

		await act(async () => {
			const success = await result.current.approveProposal((devices, rev) => {
				committedDevicesCount = devices.length;
				committedRevision = rev;
			});
			expect(success).toBe(true);
		});

		expect(result.current.currentRevision).toBe(2);
		expect(committedRevision).toBe(2);
		expect(committedDevicesCount).toBeGreaterThan(0);
		expect(result.current.previewDevices).toHaveLength(0);
		expect(result.current.proposedCommand).toBeNull();
		expect(result.current.isAiActive).toBe(false);
	});

	it("should reject approval on concurrency conflict (OCC test)", async () => {
		const { result } = renderHook(() => useAIController(), { wrapper });

		// 1. AI plans proposal at revision 1
		await act(async () => {
			await result.current.submitIntent("proj-frontend-03", "room-103", {
				width_m: 8.0,
				length_m: 12.0,
				ceiling_height_m: 3.0,
			});
		});

		// 2. Concurrently user modifies canvas -> revision becomes 2
		act(() => {
			result.current.simulateUserEdit("proj-frontend-03");
		});
		expect(result.current.currentRevision).toBe(2);

		// 3. Approving stale proposal (expectedRevision=1) must fail with CONCURRENCY_CONFLICT
		await act(async () => {
			const success = await result.current.approveProposal();
			expect(success).toBe(false);
		});

		expect(result.current.concurrencyError).toContain("CONCURRENCY_CONFLICT");
	});

	it("should replan after concurrency conflict and commit at updated revision", async () => {
		const { result } = renderHook(() => useAIController(), { wrapper });

		// 1. Plan at rev 1
		await act(async () => {
			await result.current.submitIntent("proj-frontend-04", "room-104", {
				width_m: 10.0,
				length_m: 10.0,
				ceiling_height_m: 3.0,
			});
		});

		// 2. User edits -> rev 2
		act(() => {
			result.current.simulateUserEdit("proj-frontend-04");
		});

		// 3. Replan refreshes proposal at rev 2
		await act(async () => {
			await result.current.replan();
		});

		expect(result.current.concurrencyError).toBeNull();
		expect(result.current.proposedCommand?.expectedRevision).toBe(2);

		// 4. Approval now succeeds and advances revision to 3
		await act(async () => {
			const success = await result.current.approveProposal();
			expect(success).toBe(true);
		});

		expect(result.current.currentRevision).toBe(3);
	});

	it("should reject proposal cleanly on user dismiss", async () => {
		const { result } = renderHook(() => useAIController(), { wrapper });

		await act(async () => {
			await result.current.submitIntent("proj-frontend-05", "room-105", {
				width_m: 6.0,
				length_m: 8.0,
				ceiling_height_m: 3.0,
			});
		});
		expect(result.current.previewDevices.length).toBeGreaterThan(0);

		act(() => {
			result.current.rejectProposal();
		});

		expect(result.current.previewDevices).toHaveLength(0);
		expect(result.current.proposedCommand).toBeNull();
		expect(result.current.isAiActive).toBe(false);
	});
});
