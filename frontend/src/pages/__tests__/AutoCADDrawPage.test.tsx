/**
 * AutoCADDrawPage.test.tsx â€” Unit tests for the B4 AutoCAD drawing page.
 *
 * Covers tab navigation and the four draw flows (line, polyline, circle,
 * text) including payload parsing and success/error toasts.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("sonner", () => ({
	toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("@/components/cad/RemoteCADSessionBar", () => ({
	RemoteCADSessionBar: () => (
		<div data-testid="remote-session-bar">session-bar</div>
	),
}));

vi.mock("lucide-react", async (importOriginal) => {
	const actual = (await importOriginal()) as Record<string, unknown>;
	const createIcon = (name: string) => {
		const Icon = (_props: Record<string, unknown>) => (
			<span data-testid={`icon-${name.toLowerCase()}`}>{name}</span>
		);
		Icon.displayName = name;
		return Icon;
	};
	const mocked: Record<string, unknown> = {};
	for (const [key, value] of Object.entries(actual)) {
		if (
			typeof value === "function" ||
			(typeof value === "object" &&
				value !== null &&
				"$$typeof" in (value as Record<string, unknown>))
		) {
			mocked[key] = createIcon(key);
		} else {
			mocked[key] = value;
		}
	}
	return mocked;
});

const mockDrawLine = vi.fn();
const mockDrawPolyline = vi.fn();
const mockDrawCircle = vi.fn();
const mockDrawText = vi.fn();

vi.mock("@/services/fullApi", () => ({
	autocadApi: {
		drawLine: (...args: unknown[]) => mockDrawLine(...args),
		drawPolyline: (...args: unknown[]) => mockDrawPolyline(...args),
		drawCircle: (...args: unknown[]) => mockDrawCircle(...args),
		drawText: (...args: unknown[]) => mockDrawText(...args),
	},
}));

import { toast } from "sonner";
import { AutoCADDrawPage } from "../AutoCADDrawPage";

describe("AutoCADDrawPage", () => {
	it("renders heading, session bar, and four tool tabs", () => {
		render(<AutoCADDrawPage />);
		expect(
			screen.getByRole("heading", { name: /AutoCAD Drawing Tools/i }),
		).toBeInTheDocument();
		expect(screen.getByTestId("remote-session-bar")).toBeInTheDocument();
		for (const tool of ["Line", "Polyline", "Circle", "Text"]) {
			expect(
				screen.getByRole("tab", {
					name: (_content, el) => (el?.textContent ?? "").trim().endsWith(tool),
				}),
			).toBeInTheDocument();
		}
	});

	it("draws a line with parsed coordinates and optional layer omitted", async () => {
		const user = userEvent.setup({ delay: null });
		mockDrawLine.mockResolvedValue({ success: true });
		render(<AutoCADDrawPage />);

		await user.type(screen.getByPlaceholderText("0,0,0"), "1,2,3");
		await user.type(screen.getByPlaceholderText("100,0,0"), "4,5,6");
		await user.click(screen.getByRole("button", { name: /Draw Line/i }));

		await waitFor(() =>
			expect(mockDrawLine).toHaveBeenCalledWith({
				start_point: [1, 2, 3],
				end_point: [4, 5, 6],
				layer: undefined,
			}),
		);
		expect(toast.success).toHaveBeenCalledWith("Line drawn");
	});

	it("shows an error toast when the draw call rejects", async () => {
		const user = userEvent.setup({ delay: null });
		mockDrawLine.mockRejectedValue(new Error("agent offline"));
		render(<AutoCADDrawPage />);

		await user.type(screen.getByPlaceholderText("0,0,0"), "0,0,0");
		await user.type(screen.getByPlaceholderText("100,0,0"), "1,0,0");
		await user.click(screen.getByRole("button", { name: /Draw Line/i }));

		await waitFor(() =>
			expect(toast.error).toHaveBeenCalledWith("Draw failed: agent offline"),
		);
	});

	it("switches to circle tab and draws with parsed radius", async () => {
		const user = userEvent.setup({ delay: null });
		mockDrawCircle.mockResolvedValue({ success: true });
		render(<AutoCADDrawPage />);

		await user.click(
			screen.getByRole("tab", {
				name: (_c, el) => (el?.textContent ?? "").trim().endsWith("Circle"),
			}),
		);
		await user.type(screen.getByPlaceholderText("50,50,0"), "10,20,0");
		await user.type(screen.getByPlaceholderText("25"), "7.5");
		await user.click(screen.getByRole("button", { name: /Draw Circle/i }));

		await waitFor(() =>
			expect(mockDrawCircle).toHaveBeenCalledWith({
				center: [10, 20, 0],
				radius: 7.5,
				layer: undefined,
			}),
		);
	});

	it("draws a polyline from semicolon-separated points", async () => {
		const user = userEvent.setup({ delay: null });
		mockDrawPolyline.mockResolvedValue({ success: true });
		render(<AutoCADDrawPage />);

		await user.click(
			screen.getByRole("tab", {
				name: (_c, el) => (el?.textContent ?? "").trim().endsWith("Polyline"),
			}),
		);
		await user.type(
			screen.getByPlaceholderText("0,0,0; 100,0,0; 100,50,0"),
			"0,0,0; 5,5,0",
		);
		await user.click(screen.getByRole("button", { name: /Draw Polyline/i }));

		await waitFor(() =>
			expect(mockDrawPolyline).toHaveBeenCalledWith({
				vertices: [
					[0, 0, 0],
					[5, 5, 0],
				],
				layer: undefined,
			}),
		);
		expect(toast.success).toHaveBeenCalledWith("Polyline drawn");
	});

	it("draws text with insertion point, height default, and layer", async () => {
		const user = userEvent.setup({ delay: null });
		mockDrawText.mockResolvedValue({ success: true });
		render(<AutoCADDrawPage />);

		await user.click(
			screen.getByRole("tab", {
				name: (_c, el) => (el?.textContent ?? "").trim().endsWith("Text"),
			}),
		);
		await user.type(screen.getByPlaceholderText("10,10,0"), "3,4,0");
		await user.type(screen.getByPlaceholderText("Room 101"), "Zone A");
		await user.clear(screen.getByPlaceholderText("2.5"));
		await user.type(screen.getByPlaceholderText("2.5"), "3.25");
		await user.click(screen.getByRole("button", { name: /Draw Text/i }));

		await waitFor(() =>
			expect(mockDrawText).toHaveBeenCalledWith({
				text: "Zone A",
				insertion_point: [3, 4, 0],
				height: 3.25,
				layer: undefined,
			}),
		);
		expect(toast.success).toHaveBeenCalledWith("Text drawn");
	});
});
