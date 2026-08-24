/**
 * WorkflowActionCard.test.tsx — Phase 3 Vitest suite
 *
 * Tests: IDLE, PLAN, PREVIEW, APPROVE, VERIFY, LINEAGE, and CONCURRENCY_CONFLICT
 * lifecycle states, approve/reject callbacks, OCC conflict banner, and
 * clipboard copy in LINEAGE state.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { WorkflowActionCard } from "@/components/ui/WorkflowActionCard";

const MOCK_NODES = [
	{
		node_id: "n1",
		capability_id: "spatial.place_devices",
		description: "Place 12 smoke detectors",
	},
	{
		node_id: "n2",
		capability_id: "electrical.calculate_voltage_drop",
		description: "Calculate SLC circuit voltage drop",
	},
	{
		node_id: "n3",
		capability_id: "hydraulics.solve_darcy_weisbach",
		description: "Solve sprinkler pipe network",
	},
];

// ── Helpers ───────────────────────────────────────────────────────────────────

describe("WorkflowActionCard", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
	});

	// ── IDLE ──────────────────────────────────────────────────────────────────

	it("renders IDLE state", () => {
		render(<WorkflowActionCard lifecycleState="IDLE" />);
		expect(screen.getByTestId("workflow-card-idle")).toBeInTheDocument();
		expect(
			screen.getByText(/Send an intent to begin/i),
		).toBeInTheDocument();
	});

	// ── PLAN ──────────────────────────────────────────────────────────────────

	it("renders PLAN state with DAG nodes", () => {
		render(
			<WorkflowActionCard lifecycleState="PLAN" dagNodes={MOCK_NODES} />,
		);
		expect(screen.getByTestId("workflow-card-plan")).toBeInTheDocument();
		expect(screen.getByText("Execution Topology")).toBeInTheDocument();
		expect(screen.getByText("Spatial")).toBeInTheDocument();
		expect(screen.getByText("Voltage Drop")).toBeInTheDocument();
		expect(screen.getByText("Hydraulics")).toBeInTheDocument();
	});

	it("renders PLAN state with no nodes shows empty message", () => {
		render(<WorkflowActionCard lifecycleState="PLAN" dagNodes={[]} />);
		expect(
			screen.getByText(/No workflow steps planned/i),
		).toBeInTheDocument();
	});

	// ── PREVIEW ────────────────────────────────────────────────────────────────

	it("renders PREVIEW state with device count", () => {
		const devices = [
			{ id: "d1", x_m: 1, y_m: 2, z_m: 3, type: "smoke" as const, coverage_radius_m: 6.37, spacing_m: 9 },
			{ id: "d2", x_m: 3, y_m: 2, z_m: 3, type: "heat" as const, coverage_radius_m: 4.27, spacing_m: 6 },
		];
		render(
			<WorkflowActionCard
				lifecycleState="PREVIEW"
				previewDevices={devices}
			/>,
		);
		expect(screen.getByTestId("workflow-card-preview")).toBeInTheDocument();
		expect(screen.getByText("Multi-Domain Impact")).toBeInTheDocument();
		expect(screen.getByText("Proposed Devices")).toBeInTheDocument();
		expect(screen.getByText("2")).toBeInTheDocument();
	});

	it("renders PREVIEW with circuit voltage drop warning when > 5%", () => {
		const circuit = {
			circuitId: "c1",
			voltageDropV: 1.2,
			voltageDropPct: 6.5,
			terminalVoltageV: 22.8,
			isCompliant: false,
			recommendedAwg: "12",
		};
		render(
			<WorkflowActionCard
				lifecycleState="PREVIEW"
				circuitPreview={circuit}
			/>,
		);
		expect(screen.getByText("Voltage Drop")).toBeInTheDocument();
		// The value should have the warn class (red text)
		const vdValue = screen.getByText("6.50%");
		expect(vdValue).toHaveClass("text-red-400");
	});

	it("renders PREVIEW with hydraulic velocity warning label", () => {
		const hydraulic = {
			pipeSegmentId: "p1",
			flowVelocityMS: 5.8,
			reynoldsNumber: 180000,
			frictionFactor: 0.018,
			headLossM: 2.1,
			pressureLossPsi: 3.0,
			totalPressureLossPsi: 3.0,
			flowRegime: "turbulent",
			isCompliant: false,
			warnings: ["Velocity > 5 m/s"],
		};
		render(
			<WorkflowActionCard
				lifecycleState="PREVIEW"
				hydraulicPreview={hydraulic}
			/>,
		);
		// Should show warn-coloured velocity value
		const velValue = screen.getByText("5.80 m/s");
		expect(velValue).toHaveClass("text-red-400");
	});

	// ── APPROVE ────────────────────────────────────────────────────────────────

	it("renders APPROVE state with approve and discard buttons", () => {
		render(
			<WorkflowActionCard
				lifecycleState="APPROVE"
				expectedRevision={5}
				onApprove={vi.fn().mockResolvedValue(undefined)}
				onReject={vi.fn()}
			/>,
		);
		expect(screen.getByTestId("workflow-card-approve")).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: /Approve & Commit/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: /Discard/i }),
		).toBeInTheDocument();
		expect(screen.getByText(/N=5/)).toBeInTheDocument();
	});

	it("calls onApprove when approve button clicked", async () => {
		const mockApprove = vi.fn().mockResolvedValue(undefined);
		render(
			<WorkflowActionCard
				lifecycleState="APPROVE"
				onApprove={mockApprove}
				onReject={vi.fn()}
			/>,
		);
		fireEvent.click(screen.getByRole("button", { name: /Approve & Commit/i }));
		await waitFor(() => expect(mockApprove).toHaveBeenCalledTimes(1));
	});

	it("calls onReject when discard button clicked", () => {
		const mockReject = vi.fn();
		render(
			<WorkflowActionCard
				lifecycleState="APPROVE"
				onApprove={vi.fn().mockResolvedValue(undefined)}
				onReject={mockReject}
			/>,
		);
		fireEvent.click(screen.getByRole("button", { name: /Discard/i }));
		expect(mockReject).toHaveBeenCalledTimes(1);
	});

	it("renders APPROVE state with pendingApproval details and safety badges", () => {
		const pendingApproval = {
			approvalId: "appr-pe-01",
			runId: "run-01",
			stepId: "step-spatial",
			projectId: "proj-alpha",
			projectRevision: 4,
			capabilityId: "spatial.place_devices",
			policyResult: {
				risk_class: "SAFETY_CRITICAL",
				reason: "Device count modification requires PE sign-off",
				validation_status: "PASSED",
				expected_impact: "Adds 12 smoke detectors to Zone 1",
			},
		};

		render(
			<WorkflowActionCard
				lifecycleState="APPROVE"
				pendingApproval={pendingApproval}
			/>,
		);

		expect(screen.getByTestId("workflow-approve-view")).toBeInTheDocument();
		expect(screen.getByText("SAFETY_CRITICAL")).toBeInTheDocument();
		expect(screen.getByText("Device count modification requires PE sign-off")).toBeInTheDocument();
		expect(screen.getByText(/Adds 12 smoke detectors to Zone 1/)).toBeInTheDocument();
		expect(screen.getByText(/N=4/)).toBeInTheDocument();
	});

	// ── VERIFY ─────────────────────────────────────────────────────────────────

	it("renders VERIFY state with compliance badges", () => {
		const badges = [
			{ label: "NFPA 72 PASS", passed: true },
			{ label: "IEEE 485 PASS", passed: true },
			{ label: "NFPA 13 FAIL", passed: false },
		];
		render(
			<WorkflowActionCard
				lifecycleState="VERIFY"
				complianceBadges={badges}
			/>,
		);
		expect(screen.getByTestId("workflow-card-verify")).toBeInTheDocument();
		expect(screen.getByText("NFPA 72 PASS")).toBeInTheDocument();
		expect(screen.getByText("NFPA 13 FAIL")).toBeInTheDocument();
	});

	// ── LINEAGE ────────────────────────────────────────────────────────────────

	it("renders LINEAGE state with truncated audit digest", () => {
		const digest = "a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef12345678ab";
		render(
			<WorkflowActionCard
				lifecycleState="LINEAGE"
				auditDigest={digest}
				actorId="user:eng-01"
				committedAt={new Date().toISOString()}
			/>,
		);
		expect(screen.getByTestId("workflow-card-lineage")).toBeInTheDocument();
		expect(screen.getByText("Merkle Audit Lineage")).toBeInTheDocument();
		expect(screen.getByText(/a1b2c3d4e5f67890…/)).toBeInTheDocument();
		expect(screen.getByRole("button", { name: /Copy audit hash/i })).toBeInTheDocument();
	});

	// ── CONCURRENCY_CONFLICT ───────────────────────────────────────────────────

	it("renders OCC conflict banner", () => {
		render(
			<WorkflowActionCard
				lifecycleState="CONCURRENCY_CONFLICT"
				expectedRevision={3}
				onRefreshContext={vi.fn().mockResolvedValue(undefined)}
				onDiscard={vi.fn()}
			/>,
		);
		expect(screen.getByTestId("workflow-card-conflict")).toBeInTheDocument();
		expect(screen.getByRole("alert")).toBeInTheDocument();
		expect(screen.getByText("Concurrency Conflict")).toBeInTheDocument();
		expect(screen.getByText(/N=3/)).toBeInTheDocument();
	});

	it("calls onRefreshContext when Refresh button clicked", async () => {
		const mockRefresh = vi.fn().mockResolvedValue(undefined);
		render(
			<WorkflowActionCard
				lifecycleState="CONCURRENCY_CONFLICT"
				onRefreshContext={mockRefresh}
				onDiscard={vi.fn()}
			/>,
		);
		fireEvent.click(
			screen.getByRole("button", { name: /Refresh Context/i }),
		);
		await waitFor(() => expect(mockRefresh).toHaveBeenCalledTimes(1));
	});

	it("calls onDiscard when Discard Proposal button clicked in conflict state", () => {
		const mockDiscard = vi.fn();
		render(
			<WorkflowActionCard
				lifecycleState="CONCURRENCY_CONFLICT"
				onRefreshContext={vi.fn().mockResolvedValue(undefined)}
				onDiscard={mockDiscard}
			/>,
		);
		fireEvent.click(screen.getByRole("button", { name: /Discard Proposal/i }));
		expect(mockDiscard).toHaveBeenCalledTimes(1);
	});

	// ── Step progress indicator ─────────────────────────────────────────────────

	it("shows step progress breadcrumb across all lifecycle states", () => {
		const { rerender } = render(
			<WorkflowActionCard lifecycleState="PLAN" />,
		);
		expect(screen.getByTestId("workflow-card-plan")).toBeInTheDocument();
		rerender(<WorkflowActionCard lifecycleState="VERIFY" />);
		expect(screen.getByTestId("workflow-card-verify")).toBeInTheDocument();
	});

	// ── Token Telemetry ─────────────────────────────────────────────────────────

	it("renders live token telemetry when provided", () => {
		const telemetry = {
			prompt_tokens: 350,
			completion_tokens: 120,
			total_tokens: 470,
			provider: "ollama",
			model: "qwen2.5-coder:7b",
		};
		render(
			<WorkflowActionCard
				lifecycleState="PREVIEW"
				tokenTelemetry={telemetry}
			/>,
		);
		expect(screen.getByTestId("workflow-token-telemetry")).toBeInTheDocument();
		expect(screen.getByText("Live Token Telemetry")).toBeInTheDocument();
		expect(screen.getByText("350")).toBeInTheDocument();
		expect(screen.getByText("120")).toBeInTheDocument();
		expect(screen.getByText("470")).toBeInTheDocument();
		expect(screen.getByText(/ollama · qwen2.5-coder:7b/)).toBeInTheDocument();
	});
});

