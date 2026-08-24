/**
 * ImportPreviewCard.test.tsx — Unit tests for ImportPreviewCard (Phase 3).
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ImportPreviewCard } from "@/components/chat/ImportPreviewCard";
import type { ImportPlan, StagedFileRecord } from "@/services/importApi";

describe("ImportPreviewCard", () => {
	const mockStagedFile: StagedFileRecord = {
		file_id: "imp-test-1234",
		original_filename: "floor_level_1.dxf",
		sanitized_filename: "floor_level_1.dxf",
		file_size_bytes: 102400,
		detected_format: "dxf",
		sha256_hash: "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef",
		staged_path: "/staging/imp-test-1234.dxf",
		uploaded_by: "eng-01",
		created_at: "2026-08-24T10:00:00Z",
		metadata: {},
		status: "staged",
	};

	const mockPlan: ImportPlan = {
		plan_id: "plan-5678",
		file_id: "imp-test-1234",
		project_id: "proj-alpha",
		expected_revision: 2,
		detected_format: "dxf",
		filename: "floor_level_1.dxf",
		estimated_rooms: 4,
		estimated_devices: 12,
		estimated_layers: 8,
		warnings: ["Layer ARCH_WALLS has 2 non-closed boundaries"],
		required_policy: "REQUIRES_APPROVAL",
		summary: "Import DXF drawing into Project proj-alpha (Revision 2 → 3).",
		created_at: "2026-08-24T10:00:05Z",
	};

	it("renders staged file info and detected format badge", () => {
		render(
			<ImportPreviewCard
				stagedFile={mockStagedFile}
				plan={mockPlan}
				onStartAgentRun={vi.fn()}
			/>,
		);

		expect(screen.getByTestId("import-preview-card")).toBeInTheDocument();
		expect(screen.getByText("floor_level_1.dxf")).toBeInTheDocument();
		expect(screen.getByText("dxf")).toBeInTheDocument();
		expect(screen.getByText("staged")).toBeInTheDocument();
		expect(screen.getByText(/100\.0 KB/)).toBeInTheDocument();
	});

	it("renders plan metrics and revision transition", () => {
		render(
			<ImportPreviewCard
				stagedFile={mockStagedFile}
				plan={mockPlan}
				onStartAgentRun={vi.fn()}
			/>,
		);

		expect(screen.getByText("4")).toBeInTheDocument(); // rooms
		expect(screen.getByText("12")).toBeInTheDocument(); // devices
		expect(screen.getByText("8")).toBeInTheDocument(); // layers
		expect(screen.getByText("Rev 2 → 3")).toBeInTheDocument();
		expect(screen.getByText(/Layer ARCH_WALLS has 2 non-closed boundaries/)).toBeInTheDocument();
	});

	it("calls onStartAgentRun when Start Agent Import Run button is clicked", () => {
		const handleStart = vi.fn();
		render(
			<ImportPreviewCard
				stagedFile={mockStagedFile}
				plan={mockPlan}
				onStartAgentRun={handleStart}
			/>,
		);

		const startBtn = screen.getByTestId("start-import-run-btn");
		fireEvent.click(startBtn);

		expect(handleStart).toHaveBeenCalledWith(mockStagedFile, "AUTO");
	});

	it("calls onDirectExecute when Direct Ingest button is clicked", () => {
		const handleDirect = vi.fn();
		render(
			<ImportPreviewCard
				stagedFile={mockStagedFile}
				plan={mockPlan}
				onStartAgentRun={vi.fn()}
				onDirectExecute={handleDirect}
			/>,
		);

		const directBtn = screen.getByTestId("direct-import-btn");
		fireEvent.click(directBtn);

		expect(handleDirect).toHaveBeenCalledWith(mockStagedFile);
	});

	it("calls onDismiss when Dismiss button is clicked", () => {
		const handleDismiss = vi.fn();
		render(
			<ImportPreviewCard
				stagedFile={mockStagedFile}
				plan={mockPlan}
				onStartAgentRun={vi.fn()}
				onDismiss={handleDismiss}
			/>,
		);

		const dismissBtn = screen.getByText("Dismiss");
		fireEvent.click(dismissBtn);

		expect(handleDismiss).toHaveBeenCalled();
	});
});
