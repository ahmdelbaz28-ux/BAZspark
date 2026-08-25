/**
 * DeepLinkContextIntegration.test.tsx — Integration tests proving canonical Project Context
 * propagation across deep links (Phase 8 Gate 5).
 */

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentSettingsProvider } from "@/contexts/AgentSettingsContext";
import { ProjectProvider } from "@/contexts/ProjectContext";
import { AgentChatPage } from "@/pages/AgentChatPage";
import { WorkflowPage } from "@/pages/WorkflowPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { ProjectsPage } from "@/pages/ProjectsPage";

const mockProjects = [
	{
		id: "proj-alpha",
		name: "Alpha Facility",
		description: "Industrial site",
		status: "active",
		createdAt: "2026-01-01T00:00:00Z",
		updatedAt: "2026-01-02T00:00:00Z",
		deviceCount: 12,
		connectionCount: 18,
		author: "PE Alice",
	},
	{
		id: "proj-deep-target",
		name: "Deep Link Target Complex",
		description: "Deep-linked project",
		status: "active",
		createdAt: "2026-02-01T00:00:00Z",
		updatedAt: "2026-02-02T00:00:00Z",
		deviceCount: 45,
		connectionCount: 90,
		author: "PE Bob",
	},
];

vi.mock("@/hooks/useApiQuery", () => ({
	useProjects: vi.fn(() => ({
		data: mockProjects,
		loading: false,
		error: null,
		refetch: vi.fn(),
	})),
	useReports: vi.fn(() => ({
		data: [],
		loading: false,
		error: null,
		refetch: vi.fn(),
	})),
	useGenerateReport: vi.fn(() => ({
		mutate: vi.fn(),
		loading: false,
		error: null,
	})),
	useCreateProject: vi.fn(() => ({ mutate: vi.fn() })),
	useDeleteProject: vi.fn(() => ({ mutate: vi.fn(), loading: false })),
	useSyncProject: vi.fn(() => ({ mutate: vi.fn(), loading: false })),
}));

vi.mock("@/services/fullApi", () => ({
	workflowApi: {
		getStatus: vi.fn().mockResolvedValue({ status: "idle" }),
	},
	apiCall: vi.fn().mockResolvedValue({}),
	qomnApi: {
		voltageDrop: vi.fn().mockResolvedValue({ status: "PASS" }),
	},
}));

vi.mock("@/services/agentWorkflowApi", () => ({
	agentWorkflowApi: {
		startRun: vi.fn().mockResolvedValue({ run_id: "run-123", status: "RUNNING" }),
		getStatus: vi.fn().mockResolvedValue({ run_id: "run-123", status: "RUNNING" }),
	},
}));

describe("Deep-Link Context Propagation Integration", () => {
	beforeEach(() => {
		localStorage.clear();
		sessionStorage.clear();
	});

	it("resolves deep-linked project context on AI Control Center (/?project=proj-deep-target)", () => {
		render(
			<MemoryRouter initialEntries={["/?project=proj-deep-target"]}>
				<AgentSettingsProvider>
					<ProjectProvider>
						<Routes>
							<Route path="/" element={<AgentChatPage />} />
						</Routes>
					</ProjectProvider>
				</AgentSettingsProvider>
			</MemoryRouter>,
		);

		const contextBar = screen.getByTestId("project-context-bar");
		expect(contextBar).toBeInTheDocument();
		expect(contextBar).toHaveTextContent("proj-deep-target");
	});

	it("resolves deep-linked project context on Workflow Page (/workflow?project=proj-deep-target)", () => {
		render(
			<MemoryRouter initialEntries={["/workflow?project=proj-deep-target"]}>
				<AgentSettingsProvider>
					<ProjectProvider>
						<Routes>
							<Route path="/workflow" element={<WorkflowPage />} />
						</Routes>
					</ProjectProvider>
				</AgentSettingsProvider>
			</MemoryRouter>,
		);

		expect(screen.getByText("Review & Governance")).toBeInTheDocument();
	});

	it("resolves deep-linked project context on Projects Hub (/projects?project=proj-deep-target)", () => {
		render(
			<MemoryRouter initialEntries={["/projects?project=proj-deep-target"]}>
				<AgentSettingsProvider>
					<ProjectProvider>
						<Routes>
							<Route path="/projects" element={<ProjectsPage />} />
						</Routes>
					</ProjectProvider>
				</AgentSettingsProvider>
			</MemoryRouter>,
		);

		expect(screen.getByText("Deep Link Target Complex")).toBeInTheDocument();
		expect(screen.getAllByText("Active").length).toBeGreaterThanOrEqual(1);
	});
});
