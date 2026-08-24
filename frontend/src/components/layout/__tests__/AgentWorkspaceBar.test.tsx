import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { AgentWorkspaceBar } from "@/components/layout/AgentWorkspaceBar";

describe("AgentWorkspaceBar", () => {
	it("renders an accessible entry point to the existing AI Control Center", () => {
		render(
			<MemoryRouter>
				<AgentWorkspaceBar />
			</MemoryRouter>,
		);

		expect(screen.getByTestId("agent-workspace-bar")).toBeInTheDocument();
		expect(screen.getByText("AI Control Center")).toBeInTheDocument();
		expect(screen.getByRole("link", { name: "Open AI Control Center" })).toHaveAttribute(
			"href",
			"/agent",
		);
	});
});
