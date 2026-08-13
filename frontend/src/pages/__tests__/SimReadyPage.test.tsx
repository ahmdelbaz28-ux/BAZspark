/**
 * SimReadyPage.test.tsx — Unit tests for SimReady CAD-to-USD conversion page.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SimReadyPage } from "../SimReadyPage";
import * as apiModule from "../../services/apiSimReady";

vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "en", changeLanguage: vi.fn() },
	}),
	initReactI18next: { type: "3rdParty", init: vi.fn() },
}));

vi.mock("../../services/apiSimReady", () => ({
	convertSimReady: vi.fn(),
}));

describe("SimReadyPage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it("renders heading and input form elements with default values", () => {
		render(<SimReadyPage />);

		expect(screen.getByRole("heading", { name: /SimReady Converter/i })).toBeInTheDocument();
		expect(screen.getByLabelText(/Source File Path/i)).toBeInTheDocument();
		expect(screen.getByLabelText(/SimReady Profile/i)).toHaveValue("Prop-Robotics-Neutral");
		expect(screen.getByRole("button", { name: /Convert to SimReady USD/i })).toBeInTheDocument();
	});

	it("shows validation error if source file path is empty", async () => {
		render(<SimReadyPage />);

		const convertBtn = screen.getByRole("button", { name: /Convert to SimReady USD/i });
		await userEvent.click(convertBtn);

		expect(apiModule.convertSimReady).not.toHaveBeenCalled();
	});

	it("submits form and displays success panel with output paths", async () => {
		const mockResponse = {
			success: true,
			source_asset_path: "/tmp/sample.gltf",
			source_format: "gltf",
			output_root: "C:/deliverables/SimReady/sample",
			output_usd_path: "C:/deliverables/SimReady/sample/sample.usd",
			conformed_usd_path: "C:/deliverables/SimReady/sample/sample_simready.usd",
			simready_profile: "Prop-Robotics-Neutral",
			property_assignment_status: "conformed",
			render_preview_path: "C:/deliverables/SimReady/sample/preview.png",
			deliverable_root: "C:/deliverables/SimReady/sample",
			errors: [],
			warnings: [],
			stage_reports: { conversion: { status: "success" } },
		};

		vi.mocked(apiModule.convertSimReady).mockResolvedValueOnce(mockResponse);

		render(<SimReadyPage />);

		const input = screen.getByLabelText(/Source File Path/i);
		await userEvent.type(input, "/tmp/sample.gltf");

		const convertBtn = screen.getByRole("button", { name: /Convert to SimReady USD/i });
		await userEvent.click(convertBtn);

		await waitFor(() => {
			expect(apiModule.convertSimReady).toHaveBeenCalledWith({
				source_filepath: "/tmp/sample.gltf",
				simready_profile: "Prop-Robotics-Neutral",
				property_assignment: "run",
				output_root: undefined,
			});
		});

		expect(await screen.findByText(/SimReady Asset Conformed Successfully/i)).toBeInTheDocument();
		expect(screen.getByText("C:/deliverables/SimReady/sample/sample_simready.usd")).toBeInTheDocument();
	});

	it("displays error banner when conversion fails", async () => {
		vi.mocked(apiModule.convertSimReady).mockRejectedValueOnce(new Error("CAD conversion engine error"));

		render(<SimReadyPage />);

		const input = screen.getByLabelText(/Source File Path/i);
		await userEvent.type(input, "/invalid/path.xyz");

		const convertBtn = screen.getByRole("button", { name: /Convert to SimReady USD/i });
		await userEvent.click(convertBtn);

		expect(await screen.findByText(/CAD conversion engine error/i)).toBeInTheDocument();
	});
});
