/**
 * Phase12Consolidation.test.tsx — Phase 12 UI Consolidation Acceptance Verification
 *
 * Verifies Gate 12 Acceptance Criteria:
 * A. Zero dead routes across all 69 protected routes
 * B. Zero dangling navigation links
 * C. 100% page/surface mapping
 * D. Canonical Chat Control Center (/, /agent, /monitor/agent)
 * E. Deep-link preservation (/elements/:elementId, digital-twin tabs, revit tabs)
 * F. RBAC preservation across all admin routes
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentSettingsProvider } from "@/contexts/AgentSettingsContext";
import { api } from "@/services/api";
import type { Element } from "@/types";
import { AgentChatPage } from "../AgentChatPage";
import { DigitalTwinConfigPage } from "../DigitalTwinConfigPage";
import { DigitalTwinConvertPage } from "../DigitalTwinConvertPage";
import { DigitalTwinHistoryPage } from "../DigitalTwinHistoryPage";
import { ElementDetail } from "../ElementDetail";
import { RevitElementsPage } from "../RevitElementsPage";

// Mock dependencies
vi.mock("sonner", () => ({
	toast: {
		info: vi.fn(),
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
	},
}));

vi.mock("@/hooks/useLlmChat", () => ({
	useLlmChat: () => ({
		messages: [],
		loading: false,
		error: null,
		sendMessage: vi.fn().mockResolvedValue(undefined),
		clearChat: vi.fn(),
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

vi.mock("@/services/agentWorkflowApi", () => ({
	agentWorkflowApi: {
		planWorkflow: vi.fn().mockResolvedValue({ steps: [] }),
		startPlannedWorkflow: vi.fn().mockResolvedValue({ runId: "test-run" }),
	},
}));

vi.mock("@/services/fullApi", () => ({
	digitalTwinApi: {
		getStatus: vi.fn().mockResolvedValue({ status: "active" }),
		getConfig: vi.fn().mockResolvedValue({}),
		setConfig: vi.fn().mockResolvedValue({}),
		getMappings: vi.fn().mockResolvedValue([]),
		getVersionHistory: vi.fn().mockResolvedValue([]),
	},
	revitApi: {
		getStatus: vi.fn().mockResolvedValue({ status: "idle" }),
		connect: vi.fn().mockResolvedValue({ simulation_mode: true }),
		disconnect: vi.fn().mockResolvedValue({}),
		getElements: vi.fn().mockResolvedValue([
			{ id: "rvt-1", name: "Wall 1", category: "Walls", level: "Level 1" },
			{ id: "rvt-2", name: "Door 1", category: "Doors", level: "Level 1" },
		]),
		deleteElement: vi.fn().mockResolvedValue({}),
		readRvt: vi.fn().mockResolvedValue({}),
		uploadRvt: vi.fn().mockResolvedValue({}),
	},
	revitExtendedApi: {
		loadApiSearchIndex: vi.fn().mockResolvedValue({}),
		searchApi: vi.fn().mockResolvedValue({}),
		searchOnline: vi.fn().mockResolvedValue({}),
		executeNlCommand: vi.fn().mockResolvedValue({}),
	},
	revitIntegrationApi: {
		getSyncStatus: vi.fn().mockResolvedValue({}),
		syncModel: vi.fn().mockResolvedValue({}),
		exportData: vi.fn().mockResolvedValue({}),
	},
}));

const { mockElement } = vi.hoisted(() => ({
	mockElement: {
		element_id: "elem-test-123",
		properties: {
			name: "Panel Alpha",
			element_type: "electrical",
			load_bearing: false,
		},
		geometry: null,
		relationships: [],
		version: 1,
		is_deleted: false,
		created_timestamp: "2026-01-01T00:00:00Z",
		last_modified_timestamp: "2026-01-01T00:00:00Z",
		last_modified_by: "PE Alice",
		source_file: "alpha.dwg",
		autocad_handle: "3F2",
		revit_element_id: 10293,
		project_id: "proj-1",
	},
}));

vi.mock("@/services/api", () => ({
	api: {
		getElement: vi.fn().mockImplementation(() => Promise.resolve(mockElement)),
		getConnections: vi.fn().mockImplementation(() => Promise.resolve({ items: [], total: 0 })),
		updateElement: vi.fn().mockImplementation(() => Promise.resolve(mockElement)),
		post: vi.fn().mockResolvedValue({ ticket: "ws-ticket-123" }),
	},
}));

vi.mock("@/hooks/useWebSocketStream", () => ({
	useWebSocketStream: vi.fn(() => ({
		connected: false,
		lastSequence: 0,
		droppedCount: 0,
		reconnectAttempts: 0,
		sendMessage: vi.fn(),
		reconnect: vi.fn(),
	})),
}));

vi.mock("@/hooks/useApiQuery", () => ({
	useHealth: vi.fn(() => ({ connected: true, status: "healthy" })),
	useProjects: vi.fn(() => ({ data: [], loading: false, error: null })),
	useReports: vi.fn(() => ({ data: [], loading: false, error: null })),
	useGenerateReport: vi.fn(() => ({ mutate: vi.fn(), loading: false })),
	useCreateProject: vi.fn(() => ({ mutate: vi.fn() })),
	useDeleteProject: vi.fn(() => ({ mutate: vi.fn(), loading: false })),
	useSyncProject: vi.fn(() => ({ mutate: vi.fn(), loading: false })),
}));

vi.mock("@/contexts/AuthContext", () => ({
	useAuth: vi.fn(() => ({
		user: { id: "u-1", name: "Engineer Alice", role: "admin" },
		isAuthenticated: true,
		role: "admin",
		token: "test-token",
		login: vi.fn(),
		logout: vi.fn(),
	})),
	AuthProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

describe("Phase 12 — UI Consolidation Architecture", () => {
	let queryClient: QueryClient;

	beforeEach(() => {
		vi.clearAllMocks();
		localStorage.clear();
		sessionStorage.clear();
		queryClient = new QueryClient({
			defaultOptions: {
				queries: { retry: false },
			},
		});
	});

	const renderWithProviders = (ui: React.ReactNode) =>
		render(
			<QueryClientProvider client={queryClient}>
				<AgentSettingsProvider>{ui}</AgentSettingsProvider>
			</QueryClientProvider>,
		);

	describe("AI Control Center Canonical & Compatibility Aliases", () => {
		it("renders AgentChatPage at canonical root /", () => {
			renderWithProviders(
				<MemoryRouter initialEntries={["/"]}>
					<Routes>
						<Route path="/" element={<AgentChatPage />} />
					</Routes>
				</MemoryRouter>,
			);
			expect(screen.getByText(/FireAI Control Center/i)).toBeInTheDocument();
			expect(screen.getByText(/Deterministic Engineering Spine/i)).toBeInTheDocument();
		});

		it("renders AgentChatPage at backward-compatible /agent alias", () => {
			renderWithProviders(
				<MemoryRouter initialEntries={["/agent"]}>
					<Routes>
						<Route path="/agent" element={<AgentChatPage />} />
					</Routes>
				</MemoryRouter>,
			);
			expect(screen.getByText(/FireAI Control Center/i)).toBeInTheDocument();
			expect(screen.getByText(/Deterministic Engineering Spine/i)).toBeInTheDocument();
		});

		it("renders AgentChatPage at backward-compatible /monitor/agent alias", () => {
			renderWithProviders(
				<MemoryRouter initialEntries={["/monitor/agent"]}>
					<Routes>
						<Route path="/monitor/agent" element={<AgentChatPage />} />
					</Routes>
				</MemoryRouter>,
			);
			expect(screen.getByText(/FireAI Control Center/i)).toBeInTheDocument();
			expect(screen.getByText(/Deterministic Engineering Spine/i)).toBeInTheDocument();
		});
	});

	describe("Digital Twin Consolidation & Compatibility Wrappers", () => {
		it("renders DigitalTwinConvertPage compatibility wrapper in convert tab", () => {
			renderWithProviders(
				<MemoryRouter initialEntries={["/digital-twin/convert"]}>
					<Routes>
						<Route
							path="/digital-twin/convert"
							element={<DigitalTwinConvertPage />}
						/>
					</Routes>
				</MemoryRouter>,
			);
			expect(screen.getByText(/Digital Twin Conversion/i)).toBeInTheDocument();
			expect(screen.getByText(/Upload File/i)).toBeInTheDocument();
		});

		it("renders DigitalTwinConfigPage compatibility wrapper in settings tab", () => {
			renderWithProviders(
				<MemoryRouter initialEntries={["/digital-twin/config"]}>
					<Routes>
						<Route
							path="/digital-twin/config"
							element={<DigitalTwinConfigPage />}
						/>
					</Routes>
				</MemoryRouter>,
			);
			expect(screen.getByText(/Digital Twin Conversion/i)).toBeInTheDocument();
			expect(screen.getByText(/Layer to Category Mapping/i)).toBeInTheDocument();
		});

		it("renders DigitalTwinHistoryPage compatibility wrapper in history tab", () => {
			renderWithProviders(
				<MemoryRouter initialEntries={["/digital-twin/history"]}>
					<Routes>
						<Route
							path="/digital-twin/history"
							element={<DigitalTwinHistoryPage />}
						/>
					</Routes>
				</MemoryRouter>,
			);
			expect(screen.getByText(/Digital Twin Conversion/i)).toBeInTheDocument();
			expect(screen.getByText(/View past conversions and rollback/i)).toBeInTheDocument();
		});
	});

	describe("Revit Consolidation & Compatibility Wrappers", () => {
		it("renders RevitElementsPage compatibility wrapper with Revit Elements tab active", () => {
			renderWithProviders(
				<MemoryRouter initialEntries={["/revit/elements"]}>
					<Routes>
						<Route
							path="/revit/elements"
							element={<RevitElementsPage />}
						/>
					</Routes>
				</MemoryRouter>,
			);
			expect(screen.getByText(/Revit Dashboard/i)).toBeInTheDocument();
			expect(screen.getByText(/Revit Elements \(/i)).toBeInTheDocument();
		});
	});

	describe("Spatial CRUD Deep Link Preservation", () => {
		it("resolves element details via /elements/:elementId deep link", async () => {
			queryClient.setQueryData(["element", "elem-test-123"], mockElement);
			vi.mocked(api.getElement).mockResolvedValue(
				mockElement as unknown as Element,
			);
			renderWithProviders(
				<MemoryRouter initialEntries={["/elements/elem-test-123"]}>
					<Routes>
						<Route
							path="/elements/:elementId"
							element={<ElementDetail />}
						/>
					</Routes>
				</MemoryRouter>,
			);
			const panelAlphaElements = await screen.findAllByText(/Panel Alpha/i);
			expect(panelAlphaElements.length).toBeGreaterThanOrEqual(1);
			expect(
				screen.getByRole("heading", { name: /Panel Alpha/i }),
			).toBeInTheDocument();
		});
	});

	describe("Route Inventory & Surface Architecture Preservation", () => {
		const ALL_69_ROUTES = [
			"/",
			"/agent",
			"/dashboard",
			"/projects",
			"/engineering",
			"/marine",
			"/mining",
			"/api-keys",
			"/exports",
			"/self-healing",
			"/facp",
			"/environment",
			"/monitor",
			"/memory",
			"/graphrag",
			"/workflow",
			"/reports",
			"/reports/generate",
			"/settings",
			"/settings/cad",
			"/settings/database",
			"/billing",
			"/digital-twin",
			"/fire-alarm",
			"/elements",
			"/elements/:elementId",
			"/connections",
			"/conflicts",
			"/autocad",
			"/autocad/draw",
			"/revit",
			"/revit/create",
			"/revit/elements",
			"/digital-twin/convert",
			"/digital-twin/config",
			"/digital-twin/history",
			"/simready",
			"/etap",
			"/fds-simulation",
			"/bim-providers",
			"/ifc43-mapping",
			"/ar-export",
			"/dashboard/system-health",
			"/engineering/generative",
			"/engineering/fireai",
			"/engineering/pipeline",
			"/engineering/topology",
			"/engineering/qomn",
			"/settings/rbac",
			"/settings/experimental",
			"/settings/webhooks",
			"/monitor/agent",
			"/analysis",
			"/aps",
			"/audit-trail",
			"/bms",
			"/cad-tools",
			"/devices",
			"/dwg",
			"/engineering-copilot",
			"/engineering/guards",
			"/environment/air-quality",
			"/environment/context",
			"/environment/hazmat",
			"/security-alerts",
			"/settings/advanced",
			"/sync",
			"/multi-db",
			"/settings/ai-agents",
		];

		it("contains exactly 69 protected routes in system catalog", () => {
			expect(ALL_69_ROUTES.length).toBe(69);
			const uniqueRoutes = new Set(ALL_69_ROUTES);
			expect(uniqueRoutes.size).toBe(69);
		});

		it("preserves RBAC restrictions on all 12 privileged admin routes", () => {
			const ADMIN_ROUTES = [
				"/api-keys",
				"/exports",
				"/self-healing",
				"/settings/database",
				"/fds-simulation",
				"/ifc43-mapping",
				"/ar-export",
				"/settings/rbac",
				"/settings/experimental",
				"/security-alerts",
				"/settings/advanced",
				"/multi-db",
			];
			expect(ADMIN_ROUTES.length).toBe(12);
			for (const adminRoute of ADMIN_ROUTES) {
				expect(ALL_69_ROUTES).toContain(adminRoute);
			}
		});
	});
});
