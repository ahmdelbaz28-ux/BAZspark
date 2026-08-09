import { render, screen } from "@testing-library/react";
import { PageErrorBoundary } from "../PageErrorBoundary";

describe("PageErrorBoundary", () => {
	it("renders children when no error", () => {
		render(
			<PageErrorBoundary>
				<div>Test content</div>
			</PageErrorBoundary>,
		);
		expect(screen.getByText("Test content")).toBeInTheDocument();
	});

	it("renders ErrorRecoveryView when child throws", () => {
		const ThrowError = () => {
			throw new Error("Test error");
		};

		// Suppress console.error for expected errors
		const spy = vi.spyOn(console, "error").mockImplementation(() => {});

		render(
			<PageErrorBoundary pageName="TestPage">
				<ThrowError />
			</PageErrorBoundary>,
		);

		// ErrorRecoveryView shows "Retry Component" when reload is provided
		expect(screen.getByText(/retry component/i)).toBeInTheDocument();
		// ErrorRecoveryView shows the standard heading
		expect(
			screen.getByText(/a component failed to render/i),
		).toBeInTheDocument();
		spy.mockRestore();
	});

	it("logs page name in componentDidCatch when provided", () => {
		const ThrowError = () => {
			throw new Error("Oops");
		};
		const spy = vi.spyOn(console, "error").mockImplementation(() => {});

		render(
			<PageErrorBoundary pageName="Dashboard">
				<ThrowError />
			</PageErrorBoundary>,
		);

		// pageName is logged in componentDidCatch
		expect(spy).toHaveBeenCalledWith(
			expect.stringContaining("Dashboard"),
			expect.any(Error),
			expect.any(Object),
		);
		// ErrorRecoveryView still renders the standard UI
		expect(
			screen.getByText(/a component failed to render/i),
		).toBeInTheDocument();
		spy.mockRestore();
	});

	it("logs 'unknown' page name when no pageName prop", () => {
		const ThrowError = () => {
			throw new Error("Oops");
		};
		const spy = vi.spyOn(console, "error").mockImplementation(() => {});

		render(
			<PageErrorBoundary>
				<ThrowError />
			</PageErrorBoundary>,
		);

		// Falls back to "unknown" in the log message
		expect(spy).toHaveBeenCalledWith(
			expect.stringContaining("unknown"),
			expect.any(Error),
			expect.any(Object),
		);
		// ErrorRecoveryView still renders the standard UI
		expect(
			screen.getByText(/a component failed to render/i),
		).toBeInTheDocument();
		spy.mockRestore();
	});
});
