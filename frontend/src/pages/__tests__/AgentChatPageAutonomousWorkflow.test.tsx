/**
 * AgentChatPageAutonomousWorkflow.test.tsx — Phase 6 Autonomous Engineering Workflows Integration Tests.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentSettingsProvider } from "@/contexts/AgentSettingsContext";
import { AgentChatPage } from "@/pages/AgentChatPage";
import { agentWorkflowApi } from "@/services/agentWorkflowApi";

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

vi.mock("@/hooks/useVoiceControl", () => ({
	useVoiceControl: () => ({
		isListening: false,
		startListening: vi.fn(),
		stopListening: vi.fn(),
		interimTranscript: "",
		isSupported: true,
	}),
}));

describe("AgentChatPage — Phase 6 Autonomous Engineering Workflows", () => {
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

	it("plans and initiates an autonomous workflow when an engineering intent is detected", async () => {
		const planWorkflowSpy = vi.spyOn(agentWorkflowApi, "planWorkflow").mockResolvedValueOnce({
			plan_id: "plan-test-123",
			project_id: "proj-1",
			intent_summary: "Layout smoke detectors & calculate voltage drop",
			overall_policy_decision: "AUTO_APPROVED",
			requires_human_approval: false,
			steps: [
				{
					step_id: "step-1-spatial-layout",
					capability_id: "spatial.place_devices",
					description: "Auto-layout NFPA 72 compliant smoke detectors",
					dependencies: [],
					payload: { room_id: "room-1", width_m: 10, length_m: 15 },
					risk_class: "MEDIUM",
					policy_result: "AUTO_APPROVED",
					requires_approval: false,
				},
				{
					step_id: "step-2-electrical-drop",
					capability_id: "electrical.calculate_voltage_drop",
					description: "Calculate end-of-line voltage drop",
					dependencies: ["step-1-spatial-layout"],
					payload: { circuit_id: "nac-1", current_a: 2.0, one_way_length_m: 30.0, awg: "14" },
					risk_class: "LOW",
					policy_result: "AUTO_APPROVED",
					requires_approval: false,
				},
			],
			projected_state: { devices: [] },
			expected_revision: 1,
			dag: { nodes: [] },
			token_telemetry: {},
		});

		renderComponent();

		const input = screen.getByPlaceholderText(/Ask an engineering question/i);
		fireEvent.change(input, {
			target: { value: "Layout smoke detectors in room A and calculate voltage drop" },
		});
		fireEvent.submit(input.closest("form")!);

		await waitFor(() => {
			expect(planWorkflowSpy).toHaveBeenCalledWith(
				expect.objectContaining({
					prompt: "Layout smoke detectors in room A and calculate voltage drop",
				}),
			);
			expect(mockSendMessage).toHaveBeenCalledWith(
				expect.stringContaining("Autonomous Engineering Workflow Initiated"),
			);
		});
	});

	it("falls back to standard conversational LLM stream when autonomous planning returns empty or fails", async () => {
		vi.spyOn(agentWorkflowApi, "planWorkflow").mockRejectedValueOnce(
			new Error("Planner unavailable"),
		);

		renderComponent();

		const input = screen.getByPlaceholderText(/Ask an engineering question/i);
		fireEvent.change(input, {
			target: { value: "Can you explain the voltage drop formula in NFPA 72?" },
		});
		fireEvent.submit(input.closest("form")!);

		await waitFor(() => {
			expect(mockSendMessage).toHaveBeenCalledWith(
				"Can you explain the voltage drop formula in NFPA 72?",
			);
		});
	});
});
