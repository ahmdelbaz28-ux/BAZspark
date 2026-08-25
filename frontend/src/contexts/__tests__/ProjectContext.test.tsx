/**
 * ProjectContext.test.tsx — Unit tests for canonical ProjectContext (Phase 8 Gate 5).
 */

import { act, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProjectProvider, useActiveProject } from "../ProjectContext";

const mockProjects = [
	{
		id: "proj-alpha",
		name: "Alpha Fire Alarm Facility",
		description: "Industrial facility",
		status: "active" as const,
		createdAt: "2026-01-01T00:00:00Z",
		updatedAt: "2026-01-02T00:00:00Z",
		deviceCount: 14,
		connectionCount: 22,
		author: "Lead PE",
		revision: 3,
		modelId: "dt-proj-alpha",
	},
	{
		id: "proj-beta",
		name: "Beta High-Rise Tower",
		description: "Commercial high rise",
		status: "active" as const,
		createdAt: "2026-02-01T00:00:00Z",
		updatedAt: "2026-02-02T00:00:00Z",
		deviceCount: 48,
		connectionCount: 96,
		author: "Design Engineer",
		revision: 8,
		modelId: "dt-proj-beta",
	},
];

vi.mock("@/hooks/useApiQuery", () => ({
	useProjects: vi.fn(() => ({
		data: mockProjects,
		loading: false,
		error: null,
		refetch: vi.fn(),
	})),
}));

function ConsumerComponent() {
	const {
		activeProjectId,
		activeProject,
		activeModelId,
		activeRevision,
		selectedEntityId,
		selectedEntityType,
		setActiveProjectId,
		setSelectedEntity,
	} = useActiveProject();
	return (
		<div>
			<span data-testid="active-id">{activeProjectId}</span>
			<span data-testid="active-name">{activeProject?.name || "none"}</span>
			<span data-testid="active-model">{activeModelId}</span>
			<span data-testid="active-rev">{activeRevision}</span>
			<span data-testid="selected-entity">{selectedEntityId || "none"}</span>
			<span data-testid="selected-type">{selectedEntityType || "none"}</span>
			<button
				type="button"
				onClick={() => setActiveProjectId("proj-beta")}
				data-testid="switch-btn"
			>
				Switch to Beta
			</button>
			<button
				type="button"
				onClick={() => setSelectedEntity("dev-101", "device")}
				data-testid="select-dev-btn"
			>
				Select Device
			</button>
		</div>
	);
}

describe("ProjectContext", () => {
	beforeEach(() => {
		localStorage.clear();
		sessionStorage.clear();
	});

	it("resolves the first available backend project when no selection is stored", () => {
		render(
			<MemoryRouter initialEntries={["/"]}>
				<ProjectProvider>
					<ConsumerComponent />
				</ProjectProvider>
			</MemoryRouter>,
		);

		expect(screen.getByTestId("active-id")).toHaveTextContent("proj-alpha");
		expect(screen.getByTestId("active-name")).toHaveTextContent("Alpha Fire Alarm Facility");
		expect(screen.getByTestId("active-model")).toHaveTextContent("dt-proj-alpha");
		expect(screen.getByTestId("active-rev")).toHaveTextContent("3");
	});

	it("respects URL search param ?project=proj-beta with top priority", () => {
		render(
			<MemoryRouter initialEntries={["/?project=proj-beta"]}>
				<ProjectProvider>
					<ConsumerComponent />
				</ProjectProvider>
			</MemoryRouter>,
		);

		expect(screen.getByTestId("active-id")).toHaveTextContent("proj-beta");
		expect(screen.getByTestId("active-name")).toHaveTextContent("Beta High-Rise Tower");
		expect(screen.getByTestId("active-model")).toHaveTextContent("dt-proj-beta");
		expect(screen.getByTestId("active-rev")).toHaveTextContent("8");
	});

	it("resolves selected entity context from URL query params (?project=proj-alpha&element=elem-404)", () => {
		render(
			<MemoryRouter initialEntries={["/?project=proj-alpha&element=elem-404"]}>
				<ProjectProvider>
					<ConsumerComponent />
				</ProjectProvider>
			</MemoryRouter>,
		);

		expect(screen.getByTestId("active-id")).toHaveTextContent("proj-alpha");
		expect(screen.getByTestId("active-model")).toHaveTextContent("dt-proj-alpha");
		expect(screen.getByTestId("active-rev")).toHaveTextContent("3");
		expect(screen.getByTestId("selected-entity")).toHaveTextContent("elem-404");
		expect(screen.getByTestId("selected-type")).toHaveTextContent("element");
	});

	it("allows switching active project and selected entity, persisting project to localStorage", () => {
		render(
			<MemoryRouter initialEntries={["/"]}>
				<ProjectProvider>
					<ConsumerComponent />
				</ProjectProvider>
			</MemoryRouter>,
		);

		expect(screen.getByTestId("active-id")).toHaveTextContent("proj-alpha");

		act(() => {
			screen.getByTestId("switch-btn").click();
			screen.getByTestId("select-dev-btn").click();
		});

		expect(screen.getByTestId("active-id")).toHaveTextContent("proj-beta");
		expect(screen.getByTestId("active-name")).toHaveTextContent("Beta High-Rise Tower");
		expect(screen.getByTestId("active-model")).toHaveTextContent("dt-proj-beta");
		expect(screen.getByTestId("active-rev")).toHaveTextContent("8");
		expect(screen.getByTestId("selected-entity")).toHaveTextContent("dev-101");
		expect(screen.getByTestId("selected-type")).toHaveTextContent("device");
		expect(localStorage.getItem("bazspark_active_project_id")).toBe("proj-beta");
	});

	it("provides a graceful fallback when consumed outside ProjectProvider", () => {
		render(
			<MemoryRouter initialEntries={["/"]}>
				<ConsumerComponent />
			</MemoryRouter>,
		);

		expect(screen.getByTestId("active-id")).toHaveTextContent("");
		expect(screen.getByTestId("active-name")).toHaveTextContent("none");
		expect(screen.getByTestId("active-model")).toHaveTextContent("");
		expect(screen.getByTestId("active-rev")).toHaveTextContent("1");
		expect(screen.getByTestId("selected-entity")).toHaveTextContent("none");
	});
});
