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
		status: "active",
		createdAt: "2026-01-01T00:00:00Z",
		updatedAt: "2026-01-02T00:00:00Z",
		deviceCount: 14,
		connectionCount: 22,
		author: "Lead PE",
	},
	{
		id: "proj-beta",
		name: "Beta High-Rise Tower",
		description: "Commercial high rise",
		status: "active",
		createdAt: "2026-02-01T00:00:00Z",
		updatedAt: "2026-02-02T00:00:00Z",
		deviceCount: 48,
		connectionCount: 96,
		author: "Design Engineer",
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
	const { activeProjectId, activeProject, setActiveProjectId } = useActiveProject();
	return (
		<div>
			<span data-testid="active-id">{activeProjectId}</span>
			<span data-testid="active-name">{activeProject?.name || "none"}</span>
			<button
				type="button"
				onClick={() => setActiveProjectId("proj-beta")}
				data-testid="switch-btn"
			>
				Switch to Beta
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
	});

	it("allows switching active project and persists to localStorage", () => {
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
		});

		expect(screen.getByTestId("active-id")).toHaveTextContent("proj-beta");
		expect(screen.getByTestId("active-name")).toHaveTextContent("Beta High-Rise Tower");
		expect(localStorage.getItem("bazspark_active_project_id")).toBe("proj-beta");
	});

	it("provides a graceful fallback when consumed outside ProjectProvider", () => {
		render(
			<MemoryRouter initialEntries={["/"]}>
				<ConsumerComponent />
			</MemoryRouter>,
		);

		expect(screen.getByTestId("active-id")).toHaveTextContent("default_project");
		expect(screen.getByTestId("active-name")).toHaveTextContent("none");
	});
});
