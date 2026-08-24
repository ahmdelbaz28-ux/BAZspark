/**
 * ExecutionTimeline.test.tsx — Unit tests for ExecutionTimeline (Phase 2).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExecutionTimeline } from "@/components/chat/ExecutionTimeline";
import type { AgentRunStep } from "@/hooks/useAgentRun";

const MOCK_STEPS: AgentRunStep[] = [
	{
		step_id: "s1",
		capability_id: "spatial.place_devices",
		description: "Device Layout",
		status: "completed",
	},
	{
		step_id: "s2",
		capability_id: "electrical.calculate_voltage_drop",
		description: "Voltage Drop Verification",
		status: "waiting_approval",
	},
	{
		step_id: "s3",
		capability_id: "electrical.calculate_battery",
		description: "Battery Sizing",
		status: "pending",
	},
];

describe("ExecutionTimeline", () => {
	it("does not render when status is null", () => {
		const { container } = render(
			<ExecutionTimeline
				status={null}
				currentStep={0}
				completedSteps={[]}
				failedSteps={[]}
				steps={[]}
				elapsedSeconds={0}
			/>,
		);
		expect(container.firstChild).toBeNull();
	});

	it("renders active timeline with steps and lifecycle breadcrumbs", () => {
		render(
			<ExecutionTimeline
				status="WAITING_APPROVAL"
				currentStep={1}
				completedSteps={[0]}
				failedSteps={[]}
				steps={MOCK_STEPS}
				elapsedSeconds={45}
				runId="run-test-123"
			/>,
		);

		expect(screen.getByTestId("execution-timeline")).toBeInTheDocument();
		expect(screen.getByText("Agent Execution Spine")).toBeInTheDocument();
		expect(screen.getByText("WAITING_APPROVAL")).toBeInTheDocument();
		expect(screen.getByText(/ID: run-test-123/)).toBeInTheDocument();
		expect(screen.getByText("00:45")).toBeInTheDocument();

		// Check steps
		expect(screen.getByText("Device Layout")).toBeInTheDocument();
		expect(screen.getByText("Voltage Drop Verification")).toBeInTheDocument();
		expect(screen.getByText("Battery Sizing")).toBeInTheDocument();
		expect(screen.getByText("✓ Done")).toBeInTheDocument();
		expect(screen.getByText("Paused for PE")).toBeInTheDocument();
	});
});
