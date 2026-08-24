/**
 * importApi.test.ts — Unit tests for ImportApiClient (Phase 3).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { importApi } from "../importApi";

vi.mock("../csrf", () => ({
	getCachedCsrfToken: () => "mock-csrf-token",
	getCsrfToken: async () => "mock-csrf-token",
	invalidateCsrfToken: () => {},
	CSRF_HEADER_NAME: "X-CSRF-Token",
}));

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("ImportApiClient", () => {
	beforeEach(() => {
		mockFetch.mockReset();
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	it("uploads drawing file and returns staged file record", async () => {
		const fakeFileRecord = {
			file_id: "imp-test-1",
			original_filename: "test.dwg",
			sanitized_filename: "test.dwg",
			file_size_bytes: 1024,
			detected_format: "dwg",
			sha256_hash: "abcd1234efgh5678",
			staged_path: "/tmp/test.dwg",
			uploaded_by: "eng-01",
			created_at: "2026-08-24T10:00:00Z",
			metadata: {},
			status: "staged",
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, file: fakeFileRecord }),
			text: async () => JSON.stringify({ success: true, file: fakeFileRecord }),
		});

		const file = new File(["dummy drawing data"], "test.dwg", { type: "application/acad" });
		const result = await importApi.uploadDrawingFile(file);

		expect(mockFetch).toHaveBeenCalledWith(
			expect.stringContaining("/import/upload"),
			expect.objectContaining({
				method: "POST",
			}),
		);
		expect(result.file_id).toBe("imp-test-1");
		expect(result.detected_format).toBe("dwg");
	});

	it("inspects staged file and returns inspection metrics", async () => {
		const fakeInspection = {
			file_id: "imp-test-1",
			detected_format: "dxf",
			confidence_score: 0.95,
			rooms_count: 3,
			devices_count: 10,
			layers_count: 5,
			extracted_entities: {},
			warnings: [],
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, inspection: fakeInspection }),
			text: async () => JSON.stringify({ success: true, inspection: fakeInspection }),
		});

		const result = await importApi.inspectStagedFile("imp-test-1");

		expect(mockFetch).toHaveBeenCalledWith(
			expect.stringContaining("/import/inspect"),
			expect.objectContaining({
				method: "POST",
				body: JSON.stringify({ file_id: "imp-test-1" }),
			}),
		);
		expect(result.devices_count).toBe(10);
	});

	it("plans import and returns revision bound plan", async () => {
		const fakePlan = {
			plan_id: "plan-1",
			file_id: "imp-test-1",
			project_id: "proj-1",
			expected_revision: 2,
			detected_format: "dxf",
			filename: "test.dxf",
			estimated_rooms: 2,
			estimated_devices: 6,
			estimated_layers: 4,
			warnings: [],
			required_policy: "AUTO_APPROVED",
			summary: "Import DXF drawing",
			created_at: "2026-08-24T10:00:00Z",
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, plan: fakePlan }),
			text: async () => JSON.stringify({ success: true, plan: fakePlan }),
		});

		const result = await importApi.planImport("imp-test-1", "proj-1");

		expect(result.expected_revision).toBe(2);
		expect(result.estimated_devices).toBe(6);
	});

	it("executes import with OCC revision check", async () => {
		const fakeExecResult = {
			import_id: "imp-exec-1",
			file_id: "imp-test-1",
			project_id: "proj-1",
			previous_revision: 2,
			new_revision: 3,
			imported_rooms: 2,
			imported_devices: 6,
			imported_layers: 4,
			audit_hash: "sha256hashvalue",
			warnings: [],
			completed_at: "2026-08-24T10:00:10Z",
			success: true,
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, result: fakeExecResult }),
			text: async () => JSON.stringify({ success: true, result: fakeExecResult }),
		});

		const result = await importApi.executeImport("imp-test-1", "proj-1", 2);

		expect(result.success).toBe(true);
		expect(result.new_revision).toBe(3);
	});

	it("initiates durable multi-step agent run for import", async () => {
		const fakeRun = {
			runId: "run-import-1",
			status: "RUNNING",
			currentStep: "step-1-inspect",
			completedSteps: [],
			pendingApprovalId: null,
			projectId: "proj-1",
			approvalMode: "AUTO",
		};

		mockFetch.mockResolvedValueOnce({
			ok: true,
			status: 200,
			json: async () => ({ success: true, run: fakeRun }),
			text: async () => JSON.stringify({ success: true, run: fakeRun }),
		});

		const result = await importApi.createImportRun("imp-test-1", "proj-1", "AUTO");

		expect(result.runId).toBe("run-import-1");
		expect(result.status).toBe("RUNNING");
	});
});
