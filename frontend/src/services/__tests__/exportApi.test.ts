/**
 * exportApi.test.ts — Unit tests for exportApi client (Phase 4).
 */

import { describe, expect, it, vi } from "vitest";
import { exportApi, type ExportPlan } from "../exportApi";

describe("exportApi client", () => {
	it("plans export and returns mapping report", async () => {
		const mockPlan: ExportPlan = {
			plan_id: "exp-plan-001",
			project_id: "proj-101",
			expected_revision: 3,
			target_format: "dxf",
			mapping_status: "LOSSLESS",
			mapping_report: {
				target_format: "dxf",
				status: "LOSSLESS",
				mapped_entities: 10,
				dropped_attributes: [],
				transformed_entities: ["3D BIM entities converted to 2D CAD"],
				warnings: [],
			},
			estimated_devices: 10,
			estimated_connections: 4,
			estimated_rooms: 2,
			required_policy: "AUTO_APPROVED",
			summary: "Export project proj-101 to DXF",
			options: {},
			created_at: new Date().toISOString(),
		};

		vi.spyOn(
			exportApi as unknown as { fetchWithRetry: (...args: unknown[]) => Promise<unknown> },
			"fetchWithRetry",
		).mockResolvedValue({
			success: true,
			plan: mockPlan,
		});

		const plan = await exportApi.planExport("proj-101", "dxf");
		expect(plan.plan_id).toBe("exp-plan-001");
		expect(plan.target_format).toBe("dxf");
		expect(plan.mapping_status).toBe("LOSSLESS");
		expect(plan.estimated_devices).toBe(10);
	});

	it("executes export directly with OCC check", async () => {
		const mockResult = {
			export_id: "exp-exec-001",
			artifact: {
				artifact_id: "art-001",
				project_id: "proj-101",
				revision: 3,
				target_format: "xlsx" as const,
				filename: "proj_101_export.xlsx",
				file_size_bytes: 45000,
				sha256_hash: "abc123def456",
				mapping_status: "LOSSLESS",
				validation_status: "VALID" as const,
				created_by: "eng-01",
				created_at: new Date().toISOString(),
				download_url: "/api/v2/export/artifacts/art-001/download",
				metadata: {},
			},
			mapping_report: {
				target_format: "xlsx",
				status: "LOSSLESS" as const,
				mapped_entities: 12,
				dropped_attributes: [],
				transformed_entities: [],
				warnings: [],
			},
			audit_hash: "audit-hash-001",
			completed_at: new Date().toISOString(),
			success: true,
		};

		vi.spyOn(
			exportApi as unknown as { fetchWithRetry: (...args: unknown[]) => Promise<unknown> },
			"fetchWithRetry",
		).mockResolvedValue({
			success: true,
			result: mockResult,
		});

		const res = await exportApi.executeExport("proj-101", 3, "xlsx");
		expect(res.success).toBe(true);
		expect(res.artifact.artifact_id).toBe("art-001");
		expect(res.artifact.filename).toBe("proj_101_export.xlsx");
		expect(res.artifact.sha256_hash).toBe("abc123def456");
	});

	it("constructs correct artifact download URL", () => {
		const url = exportApi.getDownloadUrl("art-12345");
		expect(url).toContain("/export/artifacts/art-12345/download");
	});
});
