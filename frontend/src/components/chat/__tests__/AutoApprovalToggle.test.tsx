/**
 * AutoApprovalToggle.test.tsx — Unit tests for AutoApprovalToggle (Phase 2).
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AutoApprovalToggle } from "@/components/chat/AutoApprovalToggle";

describe("AutoApprovalToggle", () => {
	it("renders AUTO mode button correctly", () => {
		render(<AutoApprovalToggle mode="AUTO" onChange={vi.fn()} />);

		const btn = screen.getByTestId("auto-approval-toggle-btn");
		expect(btn).toBeInTheDocument();
		expect(screen.getByText("AUTO")).toBeInTheDocument();
		expect(btn).toHaveAttribute("aria-expanded", "false");
	});

	it("renders STEP-BY-STEP mode button correctly", () => {
		render(<AutoApprovalToggle mode="STEP_BY_STEP" onChange={vi.fn()} />);

		expect(screen.getByText("STEP-BY-STEP")).toBeInTheDocument();
	});

	it("opens dropdown and selects new mode", () => {
		const handleChange = vi.fn();
		render(<AutoApprovalToggle mode="AUTO" onChange={handleChange} />);

		const btn = screen.getByTestId("auto-approval-toggle-btn");
		fireEvent.click(btn);

		expect(screen.getByTestId("auto-approval-dropdown")).toBeInTheDocument();
		expect(screen.getByTestId("step-by-step-option")).toBeInTheDocument();

		fireEvent.click(screen.getByTestId("step-by-step-option"));
		expect(handleChange).toHaveBeenCalledWith("STEP_BY_STEP");
	});
});
