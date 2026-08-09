import { render, screen } from "@testing-library/react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import { DemoDataBanner } from "../DemoDataBanner";
import { setState } from "@/store/simpleStore";

describe("DemoDataBanner", () => {
	beforeEach(() => {
		setState({
			dataMode: "demo",
			connectionStatus: "disconnected",
		});
		vi.unstubAllEnvs();
	});

	it("renders banner when dataMode is demo", () => {
		setState({ dataMode: "demo", connectionStatus: "connected" });
		render(<DemoDataBanner />);
		expect(screen.getByRole("alert")).toBeDefined();
		expect(screen.getByText("DEMO DATA")).toBeDefined();
	});

	it("hides banner when dataMode is live and connectionStatus is connected", () => {
		setState({ dataMode: "live", connectionStatus: "connected" });
		const { container } = render(<DemoDataBanner />);
		expect(container.firstChild).toBeNull();
	});

	it("still shows banner in demo mode even if VITE_DEMO_BANNER_DISABLED=true", () => {
		vi.stubEnv("VITE_DEMO_BANNER_DISABLED", "true");
		setState({ dataMode: "demo", connectionStatus: "connected" });
		render(<DemoDataBanner />);
		expect(screen.getByText("DEMO DATA")).toBeDefined();
	});

	it("hides banner when dataMode is live and VITE_DEMO_BANNER_DISABLED=true even if connectionStatus is connecting", () => {
		vi.stubEnv("VITE_DEMO_BANNER_DISABLED", "true");
		setState({ dataMode: "live", connectionStatus: "connecting" });
		const { container } = render(<DemoDataBanner />);
		expect(container.firstChild).toBeNull();
	});
});
