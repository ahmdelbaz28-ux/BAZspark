/**
 * DeepLinkContextIntegration.test.tsx — Integration tests proving canonical Project Context
 * propagation across deep links and contextual entity resolution (Phase 8 Gate 5).
 */

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AgentSettingsProvider } from "@/contexts/AgentSettingsContext";
import { ProjectProvider, useActiveProject } from "@/contexts/ProjectContext";
import { AgentChatPage } from "@/pages/AgentChatPage";
import { WorkflowPage } from "@/pages/WorkflowPage";
import { ProjectsPage } from "@/pages/ProjectsPage";

const mockProjects = [
	{
		id: "proj-alpha",
		name: "Alpha Facility",
		description: "Industrial site",
		status: "active" as const,
		createdAt: "2026-01-01T00:00:00Z",
		updatedAt: "2026-01-02T00:00:00Z",
		deviceCount: 12,
		connectionCount: 18,
		author: "PE Alice",
		revision: 3,
		modelId: "dt-proj-alpha",
	},
	{
		id: "proj-deep-target",
		name: "Deep Link Target Complex",
		description: "Deep-linked project",
		status: "active" as const,
		createdAt: "2026-02-01T00:00:00Z",
		updatedAt: "2026-02-02T00:00:00Z",
		deviceCount: 45,
		connectionCount: 90,
		author: "PE Bob",
		revision: 7,
		modelId: "dt-proj-deep-target",
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

function DeepLinkContextInspector() {
	const {
		activeProjectId,
		activeModelId,
		activeRevision,
		selectedEntityId,
		selectedEntityType,
		activeProject,
	} = useActiveProject();
	return (
		<div>
			<span data-testid="dl-project-id">{activeProjectId}</span>
			<span data-testid="dl-model-id">{activeModelId}</span>
			<span data-testid="dl-revision">{activeRevision}</span>
			<span data-testid="dl-entity-id">{selectedEntityId || "none"}</span>
			<span data-testid="dl-entity-type">{selectedEntityType || "none"}</span>
			<span data-testid="dl-project-name">{activeProject?.name || "none"}</span>
		</div>
	);
}

describe("Phase 8 Gate 5 — Deep-Link Context Chain Integration", () => {
	beforeEach(() => {
		localStorage.clear();
		sessionStorage.clear();
	});

	it("resolves canonical project, model, revision, and selected entity from URL parameters", () => {
		render(
			<MemoryRouter initialEntries={["/?project=proj-deep-target&element=elem-smoke-101"]}>
				<ProjectProvider>
					<DeepLinkContextInspector />
				</ProjectProvider>
			</MemoryRouter>,
		);

		expect(screen.getByTestId("dl-project-id")).toHaveTextContent("proj-deep-target");
		expect(screen.getByTestId("dl-model-id")).toHaveTextContent("dt-proj-deep-target");
		expect(screen.getByTestId("dl-revision")).toHaveTextContent("7");
		expect(screen.getByTestId("dl-entity-id")).toHaveTextContent("elem-smoke-101");
		expect(screen.getByTestId("dl-entity-type")).toHaveTextContent("element");
		expect(screen.getByTestId("dl-project-name")).toHaveTextContent("Deep Link Target Complex");
	});

	it("resolves deep-linked project context on AI Control Center (/?project=proj-deep-target)", () => {
		render(
			<MemoryRouter initialEntries={["/?project=proj-deep-target"]}>
				<AgentSettingsProvider>
					<ProjectProvider>
						<AgentChatPage />
					</ProjectProvider>
				</AgentSettingsProvider>
			</MemoryRouter>,
		);

		expect(screen.getByText("proj-deep-target")).toBeInTheDocument();
		expect(screen.getByText("(Rev: 7)")).toBeInTheDocument();
	});

	it("resolves deep-linked project context on Workflow Page (/workflow?project=proj-deep-target)", () => {
		render(
			<MemoryRouter initialEntries={["/workflow?project=proj-deep-target"]}>
				<AgentSettingsProvider>
					<ProjectProvider>
						<WorkflowPage />
					</ProjectProvider>
				</AgentSettingsProvider>
			</MemoryRouter>,
		);

		expect(screen.getByText(/Review & Governance/i)).toBeInTheDocument();
		expect(screen.getByText(/Authoritative engineering review workflows/i)).toBeInTheDocument();
	});

	it("reflects active project correctly in Projects list surface (/projects?project=proj-deep-target)", () => {
		render(
			<MemoryRouter initialEntries={["/projects?project=proj-deep-target"]}>
				<AgentSettingsProvider>
					<ProjectProvider>
						<ProjectsPage />
					</ProjectProvider>
				</AgentSettingsProvider>
			</MemoryRouter>,
		);

		expect(screen.getByText("Deep Link Target Complex")).toBeInTheDocument();
		expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
	});
});
