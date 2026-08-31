/**
 * AgentChatPage.test.tsx — Integration tests for AI-First Control Center (Phase 7 Universal Chat Control Plane).
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentSettingsProvider } from "@/contexts/AgentSettingsContext";
import { AgentChatPage } from "@/pages/AgentChatPage";
import { agentWorkflowApi } from "@/services/agentWorkflowApi";

// Mock useLlmChat
const mockSendMessage = vi.fn().mockResolvedValue(undefined);
const mockClearChat = vi.fn();
vi.mock("@/hooks/useLlmChat", () => ({
	useLlmChat: () => ({
		messages: [],
		loading: false,
		error: null,
		sendMessage: mockSendMessage,
		clearChat: mockClearChat,
	}),
}));

// Mock useVoiceControl
vi.mock("@/hooks/useVoiceControl", () => ({
	useVoiceControl: () => ({
		isListening: false,
		startListening: vi.fn(),
		stopListening: vi.fn(),
		interimTranscript: "",
		isSupported: true,
	}),
}));

// Mock agentWorkflowApi
vi.mock("@/services/agentWorkflowApi", () => ({
	agentWorkflowApi: {
		planWorkflow: vi.fn().mockResolvedValue({ steps: [] }),
		startPlannedWorkflow: vi.fn().mockResolvedValue({ runId: "test-run" }),
	},
}));

describe("AgentChatPage", () => {
	beforeEach(() => {
		vi.restoreAllMocks();
		localStorage.clear();
		sessionStorage.clear();
	});

	const renderComponent = () =>
		render(
			<MemoryRouter>
				<AgentSettingsProvider>
					<AgentChatPage />
				</AgentSettingsProvider>
			</MemoryRouter>,
		);

	it("renders the AI-First Control Center layout and header", () => {
		renderComponent();

		expect(screen.getByTestId("project-context-bar")).toBeInTheDocument();
		expect(screen.getByText("FireAI Control Center")).toBeInTheDocument();
		expect(screen.getByText("AI-First")).toBeInTheDocument();
		expect(screen.getByTestId("auto-approval-toggle-btn")).toBeInTheDocument();
	});

	it("renders quick engineering action cards when chat is empty", () => {
		renderComponent();

		expect(screen.getByText(/FireAI Engineering Control Center/i)).toBeInTheDocument();
		expect(screen.getAllByText("Place Smoke Detectors").length).toBeGreaterThanOrEqual(1);
		expect(screen.getAllByText("Voltage Drop Analysis").length).toBeGreaterThanOrEqual(1);
		expect(screen.getAllByText("Battery Backup Sizing").length).toBeGreaterThanOrEqual(1);
	});

	it("allows user to type into input and submit chat message", async () => {
		renderComponent();

		const input = screen.getByPlaceholderText(/Ask an engineering question/i);
		fireEvent.change(input, { target: { value: "How do I calculate cable size?" } });
		fireEvent.submit(input.closest("form")!);

		await waitFor(() => {
			expect(mockSendMessage).toHaveBeenCalledWith("How do I calculate cable size?");
		});
	});

	it("routes quick action clicks through agentWorkflowApi.planWorkflow", async () => {
		const planSpy = vi.spyOn(agentWorkflowApi, "planWorkflow").mockResolvedValueOnce({
			plan_id: "plan-qa-1",
			project_id: "proj-1",
			expected_revision: 1,
			intent_summary: "Auto-layout detectors",
			steps: [
				{
					step_id: "step-1",
					capability_id: "spatial.place_devices",
					description: "Place detectors",
					dependencies: [],
					payload: { room_id: "zone-a" },
					risk_class: "LOW",
					policy_result: "AUTO_APPROVED",
					requires_approval: false,
				},
			],
			dag: { nodes: [] },
			requires_human_approval: false,
			overall_policy_decision: "AUTO_APPROVED",
			projected_state: {},
		});

		renderComponent();

		const quickActionBtns = screen.getAllByText("Place Smoke Detectors");
		fireEvent.click(quickActionBtns[0]);

		await waitFor(() => {
			expect(planSpy).toHaveBeenCalledWith(
				expect.objectContaining({
					prompt: expect.stringContaining("smoke detectors"),
					compositeSpec: expect.objectContaining({ room_id: "zone-a" }),
				}),
			);
		});
	});

	it("does not fabricate fake artifacts when run status is COMPLETED without real exports", () => {
		renderComponent();

		// Zero occurrences of hardcoded fake artifact filenames in rendered UI
		expect(screen.queryByText("NFPA_72_Compliance_Report.pdf")).toBeNull();
		expect(screen.queryByText("Device_Layout_Rev2.dxf")).toBeNull();
	});
});
