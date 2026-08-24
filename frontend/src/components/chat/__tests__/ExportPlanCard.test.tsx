/**
 * ExportPlanCard.test.tsx — Unit tests for ExportPlanCard component (Phase 4).
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ExportPlanCard } from "../ExportPlanCard";
import type { ExportPlan } from "@/services/exportApi";

const mockPlan: ExportPlan = {
	plan_id: "exp-plan-test-01",
	project_id: "proj-alpha",
	expected_revision: 5,
	target_format: "dxf",
	mapping_status: "LOSSLESS",
	mapping_report: {
		target_format: "dxf",
		status: "LOSSLESS",
		mapped_entities: 8,
		dropped_attributes: [],
		transformed_entities: ["Entities structured as CAD layers"],
		warnings: [],
	},
	estimated_devices: 8,
	estimated_connections: 3,
	estimated_rooms: 2,
	required_policy: "AUTO_APPROVED",
	summary: "Export project proj-alpha (Rev 5) to DXF",
	options: {},
	created_at: new Date().toISOString(),
};

describe("ExportPlanCard", () => {
	it("renders export plan details and revision badge", () => {
		render(
			<ExportPlanCard
				plan={mockPlan}
				isExecuting={false}
				onStartAgentRun={vi.fn()}
				onDirectExecute={vi.fn()}
				onDismiss={vi.fn()}
			/>,
		);

		expect(screen.getByText("Engineering Export Plan")).toBeDefined();
		expect(screen.getByText("proj-alpha")).toBeDefined();
		expect(screen.getByText("5")).toBeDefined();
		expect(screen.getByText("LOSSLESS")).toBeDefined();
		expect(screen.getByText("8")).toBeDefined();
	});

	it("triggers onDirectExecute when Direct Export button is clicked", () => {
		const handleDirectExecute = vi.fn();
		render(
			<ExportPlanCard
				plan={mockPlan}
				isExecuting={false}
				onStartAgentRun={vi.fn()}
				onDirectExecute={handleDirectExecute}
				onDismiss={vi.fn()}
			/>,
		);

		const directBtn = screen.getByRole("button", { name: /Direct Export/i });
		fireEvent.click(directBtn);
		expect(handleDirectExecute).toHaveBeenCalledTimes(1);
	});

	it("triggers onStartAgentRun when Start Governed Run button is clicked", () => {
		const handleStartRun = vi.fn();
		render(
			<ExportPlanCard
				plan={mockPlan}
				isExecuting={false}
				onStartAgentRun={handleStartRun}
				onDirectExecute={vi.fn()}
				onDismiss={vi.fn()}
			/>,
		);

		const runBtn = screen.getByRole("button", { name: /Start Governed Run/i });
		fireEvent.click(runBtn);
		expect(handleStartRun).toHaveBeenCalledTimes(1);
	});

	it("renders warnings if mapping report has warnings", () => {
		const lossyPlan: ExportPlan = {
			...mockPlan,
			mapping_status: "LOSSY",
			mapping_report: {
				...mockPlan.mapping_report,
				status: "LOSSY",
				warnings: ["Spatial geometry is dropped in flat tabular CSV"],
			},
		};

		render(
			<ExportPlanCard
				plan={lossyPlan}
				isExecuting={false}
				onStartAgentRun={vi.fn()}
				onDirectExecute={vi.fn()}
				onDismiss={vi.fn()}
			/>,
		);

		expect(screen.getByText("Spatial geometry is dropped in flat tabular CSV")).toBeDefined();
	});
});
