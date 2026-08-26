/**
 * RemoteCADSessionBar.test.tsx — coverage for the B4 remote session strip.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RemoteCADSessionBar } from "../RemoteCADSessionBar";
import { cadRemoteApi } from "@/services/cadRemoteApi";

vi.mock("sonner", () => ({
	toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));

vi.mock("@/services/cadRemoteApi", () => ({
	cadRemoteApi: {
		getRemoteStatus: vi.fn(),
		sendNativeCommand: vi.fn(),
		captureScreen: vi.fn(),
	},
}));

import { toast } from "sonner";
const mockedApi = vi.mocked(cadRemoteApi);

describe("RemoteCADSessionBar", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("shows connected state with enabled controls", async () => {
		mockedApi.getRemoteStatus.mockResolvedValue({
			success: true,
			agent_connected: true,
			session: { filename: "plan.dwg" },
		});

		render(<RemoteCADSessionBar />);

		expect(await screen.findByText("Desktop agent connected")).toBeInTheDocument();
		expect(screen.getByPlaceholderText(/_.LINE/)).toBeEnabled();
		expect(screen.getByText("Queue")).toBeEnabled();
	});

	it("shows disconnected state and disables the command input", async () => {
		mockedApi.getRemoteStatus.mockResolvedValue({
			success: true,
			agent_connected: false,
			message: "Start scripts/local_agent.py",
		});

		render(<RemoteCADSessionBar />);

		expect(await screen.findByText("No desktop agent")).toBeInTheDocument();
		expect(screen.getByText("Start scripts/local_agent.py")).toBeInTheDocument();
		expect(screen.getByPlaceholderText(/local_agent\.py/)).toBeDisabled();
	});

	it("queues a native command on Enter", async () => {
		mockedApi.getRemoteStatus.mockResolvedValue({ success: true, agent_connected: true });
		mockedApi.sendNativeCommand.mockResolvedValue({ success: true, queued: true });

		render(<RemoteCADSessionBar />);
		const input = await screen.findByPlaceholderText(/_.LINE/);
		fireEvent.change(input, { target: { value: "_.ZOOM _E" } });
		fireEvent.keyDown(input, { key: "Enter" });

		await waitFor(() => {
			expect(mockedApi.sendNativeCommand).toHaveBeenCalledWith("_.ZOOM _E");
		});
		// Input clears after successful queue.
		await waitFor(() => {
			expect((screen.getByPlaceholderText(/_.LINE/) as HTMLInputElement).value).toBe("");
		});
	});

	it("renders a screenshot preview after capture", async () => {
		mockedApi.getRemoteStatus.mockResolvedValue({ success: true, agent_connected: true });
		mockedApi.captureScreen.mockResolvedValue({
			success: true,
			image_base64: "aGVsbG8=",
			format: "png",
		});

		render(<RemoteCADSessionBar />);
		await screen.findByText("Desktop agent connected");

		fireEvent.click(screen.getByText("Screenshot"));

		await waitFor(() => {
			expect(mockedApi.captureScreen).toHaveBeenCalled();
		});
		const img = await screen.findByRole("img", { name: /AutoCAD window capture/i });
		expect(img).toHaveAttribute("src", "data:image/png;base64,aGVsbG8=");
	});

	it("resets status to null when the status probe rejects", async () => {
		mockedApi.getRemoteStatus.mockRejectedValue(new Error("network down"));
		render(<RemoteCADSessionBar />);
		await waitFor(() => {
			expect(toast.error).not.toHaveBeenCalled(); // silent polling failure
			expect(screen.queryByText("Desktop agent connected")).toBeNull();
		});
	});

	it("shows an error toast when queueing a command fails", async () => {
		mockedApi.getRemoteStatus.mockResolvedValue({ success: true, agent_connected: true });
		mockedApi.sendNativeCommand.mockRejectedValue(new Error("pipe broken"));
		render(<RemoteCADSessionBar />);

		const input = await screen.findByPlaceholderText(/_.LINE/);
		fireEvent.change(input, { target: { value: "_.REGEN" } });
		fireEvent.click(screen.getByText("Queue"));

		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith("Send failed: pipe broken");
		});
	});

	it("warns when a capture succeeds but carries no image", async () => {
		mockedApi.getRemoteStatus.mockResolvedValue({ success: true, agent_connected: true });
		mockedApi.captureScreen.mockResolvedValue({
			success: false,
			image_base64: null,
			message: "No active drawing",
		});
		render(<RemoteCADSessionBar />);
		await screen.findByText("Desktop agent connected");

		fireEvent.click(screen.getByText("Screenshot"));
		await waitFor(() => {
			expect(toast.warning).toHaveBeenCalledWith("No active drawing");
		});
	});

	it("shows an error toast when capture rejects", async () => {
		mockedApi.getRemoteStatus.mockResolvedValue({ success: true, agent_connected: true });
		mockedApi.captureScreen.mockRejectedValue(new Error("capture blew up"));
		render(<RemoteCADSessionBar />);
		await screen.findByText("Desktop agent connected");

		fireEvent.click(screen.getByText("Screenshot"));
		await waitFor(() => {
			expect(toast.error).toHaveBeenCalledWith("Capture failed: capture blew up");
		});
	});

	it("Queue button triggers sendCommand on click", async () => {
		mockedApi.getRemoteStatus.mockResolvedValue({ success: true, agent_connected: true });
		mockedApi.sendNativeCommand.mockResolvedValue({ success: true, queued: true });
		render(<RemoteCADSessionBar />);

		const input = await screen.findByPlaceholderText(/_.LINE/);
		fireEvent.change(input, { target: { value: "_.QSAVE" } });
		fireEvent.click(screen.getByText("Queue"));

		await waitFor(() => {
			expect(mockedApi.sendNativeCommand).toHaveBeenCalledWith("_.QSAVE");
			expect(toast.success).toHaveBeenCalledWith("Command queued: _.QSAVE");
		});
	});
});
