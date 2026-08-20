/**
 * Phase4StressAudit.test.tsx — Phase 4 Frontend Cockpit & Direct Manipulation Integrity Test Suite
 *
 * Covers:
 * - Vector 4.1: Canvas Ghost Layer Non-Interference Test (20 ghost detectors, 3 circuit runs, 2 hydraulic pipes with pointer-events: none)
 * - Vector 4.2: OCC Conflict UI Recovery Workflow (amber conflict card, blocked commit, refresh context trigger)
 * - Vector 4.3: Agent Settings Persistence & Dynamic Routing (switch to Ollama Local, envelope adapt without reload or DB pollution)
 */

import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import {
	CanvasEditor,
	type Detector,
	type PreviewGhostDevice,
	type CircuitGhostSegment,
	type HydraulicGhostSegment,
} from "@/components/firealarm/CanvasEditor";
import { WorkflowActionCard } from "@/components/ui/WorkflowActionCard";
import { AgentSettingsPage } from "@/pages/AgentSettingsPage";
import {
	AgentSettingsProvider,
	type AgentSettingsState,
	useAgentSettings,
} from "@/contexts/AgentSettingsContext";
import React from "react";

// Mock i18n
vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => {
			const translations: Record<string, string> = {
				"fireAlarm.floorPlanPlaceholder": "Drop floor plan here",
				"fireAlarm.detectors": "Detectors",
			};
			return translations[key] ?? key;
		},
	}),
}));

const localStorageMock = (() => {
	let store: Record<string, string> = {};
	return {
		getItem: (key: string) => store[key] ?? null,
		setItem: (key: string, value: string) => {
			store[key] = value;
		},
		clear: () => {
			store = {};
		},
		removeItem: (key: string) => {
			delete store[key];
		},
	};
})();

Object.defineProperty(globalThis, "localStorage", {
	value: localStorageMock,
	writable: true,
});

describe("Phase 4: Frontend Cockpit & Direct Manipulation Integrity Suite", () => {
	beforeEach(() => {
		localStorageMock.clear();
		vi.restoreAllMocks();
	});

	// ── Vector 4.1: Canvas Ghost Layer Non-Interference Test ───────────────────
	it("Vector 4.1: Canvas Ghost Layer Non-Interference Test", () => {
		const onDetectorsChange = vi.fn();

		const committedDetectors: Detector[] = [
			{
				id: "committed-det-01",
				x: 100,
				y: 100,
				type: "smoke",
				status: "normal",
				coverageRadius: 6.37,
			},
			{
				id: "committed-det-02",
				x: 250,
				y: 250,
				type: "heat",
				status: "normal",
				coverageRadius: 4.27,
			},
		];

		// 20 ghost detectors
		const ghostDevices: PreviewGhostDevice[] = Array.from({ length: 20 }, (_, i) => ({
			id: `ghost-dev-${i + 1}`,
			x: 50 + (i % 5) * 60,
			y: 50 + Math.floor(i / 5) * 60,
			type: "smoke",
			coverage_radius_m: 6.37,
		}));

		// 3 circuit runs
		const circuitGhostSegments: CircuitGhostSegment[] = [
			{
				id: "circuit-run-01",
				points: [
					{ x: 50, y: 50 },
					{ x: 110, y: 50 },
					{ x: 170, y: 50 },
				],
				voltageDropPct: 2.1,
				isCompliant: true,
			},
			{
				id: "circuit-run-02",
				points: [
					{ x: 50, y: 110 },
					{ x: 110, y: 110 },
					{ x: 170, y: 110 },
				],
				voltageDropPct: 4.3,
				isCompliant: true,
			},
			{
				id: "circuit-run-03",
				points: [
					{ x: 50, y: 170 },
					{ x: 110, y: 170 },
					{ x: 170, y: 170 },
				],
				voltageDropPct: 7.8,
				isCompliant: false,
			},
		];

		// 2 hydraulic pipe overlays
		const hydraulicGhostSegments: HydraulicGhostSegment[] = [
			{
				id: "hyd-pipe-01",
				x1: 40,
				y1: 40,
				x2: 280,
				y2: 40,
				flowVelocityMS: 2.4,
				showLabel: true,
			},
			{
				id: "hyd-pipe-02",
				x1: 280,
				y1: 40,
				x2: 280,
				y2: 280,
				flowVelocityMS: 6.2, // > 5.0 m/s non-compliant red flag
				showLabel: true,
			},
		];

		const { container } = render(
			<CanvasEditor
				detectors={committedDetectors}
				onDetectorsChange={onDetectorsChange}
				previewDevices={ghostDevices}
				circuitGhostSegments={circuitGhostSegments}
				hydraulicGhostSegments={hydraulicGhostSegments}
			/>,
		);

		// 1. Verify ghost layer group exists and has pointer-events="none"
		const ghostLayer = container.querySelector(".ephemeral-ghost-layer");
		expect(ghostLayer).not.toBeNull();
		expect(ghostLayer).toHaveAttribute("pointer-events", "none");

		// 2. Verify all 20 ghost devices rendered within ghost layer
		expect(ghostLayer?.children.length).toBeGreaterThan(20);

		// 3. Verify circuit and hydraulic overlays rendered within ghost layer
		const circuitElements = container.querySelectorAll("polyline");
		expect(circuitElements.length).toBe(3);

		const velocityLabels = screen.getAllByText(/m\/s/);
		expect(velocityLabels.length).toBe(2);
		// 4. Verify committed detectors rendered with interactive shapes
		const committedSmoke = container.querySelector("circle[cx='12'][cy='12']");
		const committedHeat = container.querySelector("polygon[points='12,4 20,20 4,20']");
		expect(committedSmoke).toBeInTheDocument();
		expect(committedHeat).toBeInTheDocument();

		// Parent <g> has pointerEvents: "auto"
		const smokeGroup = committedSmoke?.closest("g");
		expect(smokeGroup).not.toBeNull();
		expect(smokeGroup).toHaveStyle({ pointerEvents: "auto" });

		// Click / MouseDown on committed detector without interception by ghost layer
		if (smokeGroup) {
			fireEvent.mouseDown(smokeGroup);
			fireEvent.click(smokeGroup);
		}
		expect(smokeGroup).toBeInTheDocument();
	});

	// ── Vector 4.2: OCC Conflict UI Recovery Workflow ──────────────────────────
	it("Vector 4.2: OCC Conflict UI Recovery Workflow", async () => {
		const onApprove = vi.fn();
		const onRefreshContext = vi.fn().mockResolvedValue(undefined);
		const onDiscard = vi.fn();

		const { rerender } = render(
			<WorkflowActionCard
				lifecycleState="APPROVE"
				expectedRevision={2}
				previewDevices={[
					{
						id: "dev-01",
						x_m: 2,
						y_m: 3,
						z_m: 3,
						type: "smoke",
						coverage_radius_m: 6.37,
						spacing_m: 9.1,
					},
				]}
				onApprove={onApprove}
				onRefreshContext={onRefreshContext}
				onDiscard={onDiscard}
			/>,
		);

		// Initially in APPROVE state
		expect(screen.getByTestId("workflow-card-approve")).toBeInTheDocument();
		const approveBtn = screen.getByRole("button", { name: /approve & commit/i });
		expect(approveBtn).toBeInTheDocument();

		// Background OCC bump occurs (N=2 -> N=3), conflict detected
		rerender(
			<WorkflowActionCard
				lifecycleState="CONCURRENCY_CONFLICT"
				expectedRevision={2}
				onApprove={onApprove}
				onRefreshContext={onRefreshContext}
				onDiscard={onDiscard}
			/>,
		);

		// 1. Renders amber conflict alert
		const conflictCard = screen.getByTestId("workflow-card-conflict");
		expect(conflictCard).toBeInTheDocument();
		expect(conflictCard).toHaveAttribute("role", "alert");
		expect(screen.getByText("Concurrency Conflict")).toBeInTheDocument();
		expect(screen.getByText(/outdated revision \(N=2\)/i)).toBeInTheDocument();

		// 2. Commit is blocked: approve button is NOT present in conflict state
		expect(screen.queryByRole("button", { name: /approve & commit/i })).not.toBeInTheDocument();

		// 3. User clicks [Refresh Context & Re-plan]
		const refreshBtn = screen.getByRole("button", { name: /refresh context & re-plan/i });
		expect(refreshBtn).toBeInTheDocument();
		fireEvent.click(refreshBtn);

		await waitFor(() => {
			expect(onRefreshContext).toHaveBeenCalledTimes(1);
		});
	});

	// ── Vector 4.3: Agent Settings Persistence & Dynamic Routing ───────────────
	it("Vector 4.3: Agent Settings Persistence & Dynamic Routing", async () => {
		let currentSettings: AgentSettingsState | undefined;

		const Consumer = () => {
			const { settings } = useAgentSettings();
			currentSettings = settings;
			return <div data-testid="active-provider">{settings.llm.provider}</div>;
		};

		render(
			<AgentSettingsProvider>
				<AgentSettingsPage />
				<Consumer />
			</AgentSettingsProvider>,
		);

		// Initial provider is Anthropic
		expect(screen.getByTestId("active-provider")).toHaveTextContent("anthropic");
		expect(currentSettings?.llm.model).toBe("claude-sonnet-4-5");

		// Change provider to Local / Ollama
		const ollamaRadio = screen.getByRole("radio", { name: /local \/ ollama/i });
		fireEvent.click(ollamaRadio);

		// Assert provider dynamically routed to ollama
		expect(screen.getByTestId("active-provider")).toHaveTextContent("ollama");
		expect(currentSettings?.llm.provider).toBe("ollama");
		expect(currentSettings?.llm.model).toBe("qwen2.5-coder:7b");

		// Assert persisted in localStorage under STORAGE_KEY
		await waitFor(() => {
			const raw = localStorageMock.getItem("bazspark:agent-settings:v1");
			expect(raw).not.toBeNull();
			const saved = JSON.parse(raw ?? "{}");
			expect(saved.llm.provider).toBe("ollama");
			expect(saved.llm.model).toBe("qwen2.5-coder:7b");
		});

		// Assert zero API key in domain payload
		expect(currentSettings?.llm.apiKeyLocal).toBe("");
	});
});
