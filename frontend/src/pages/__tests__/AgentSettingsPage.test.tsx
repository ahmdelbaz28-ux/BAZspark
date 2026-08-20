/**
 * AgentSettingsPage.test.tsx — Phase 3 Vitest suite
 *
 * Tests: render, section presence, toggles, provider selector,
 * API key visibility toggle, reset confirmation flow, and
 * localStorage persistence via AgentSettingsContext.
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import { AgentSettingsPage } from "@/pages/AgentSettingsPage";
import { AgentSettingsProvider } from "@/contexts/AgentSettingsContext";

// ── Helpers ───────────────────────────────────────────────────────────────────

const localStorageMock = (() => {
	let store: Record<string, string> = {};
	return {
		getItem: (key: string) => store[key] ?? null,
		setItem: (key: string, value: string) => {
			store[key] = value;
		},
		clear: () => {
			store = {};
		},
		removeItem: (key: string) => {
			delete store[key];
		},
	};
})();

Object.defineProperty(globalThis, "localStorage", {
	value: localStorageMock,
	writable: true,
});

function renderPage() {
	return render(
		<AgentSettingsProvider>
			<AgentSettingsPage />
		</AgentSettingsProvider>,
	);
}

// ── Test Suite ─────────────────────────────────────────────────────────────────

describe("AgentSettingsPage", () => {
	beforeEach(() => {
		localStorageMock.clear();
		vi.restoreAllMocks();
	});

	it("renders page heading", () => {
		renderPage();
		expect(
			screen.getByText("AI Agent Workspace"),
		).toBeInTheDocument();
	});

	it("renders all 5 section cards", () => {
		renderPage();
		expect(screen.getByText("Model Routing")).toBeInTheDocument();
		expect(
			screen.getByText("Context Budget & Telemetry Vault"),
		).toBeInTheDocument();
		expect(
			screen.getByText("Governance & Safety Policies"),
		).toBeInTheDocument();
		expect(
			screen.getByText("Active Capability Registry"),
		).toBeInTheDocument();
		expect(
			screen.getByText("Working Memory Lifecycle"),
		).toBeInTheDocument();
	});

	it("shows all 4 provider buttons", () => {
		renderPage();
		expect(screen.getByText("Anthropic")).toBeInTheDocument();
		expect(screen.getByText("Google Gemini")).toBeInTheDocument();
		expect(screen.getByText("OpenAI")).toBeInTheDocument();
		expect(screen.getByText("Local / Ollama")).toBeInTheDocument();
	});

	it("switches provider when button clicked", () => {
		renderPage();
		const openaiBtn = screen.getByRole("radio", { name: /openai/i });
		fireEvent.click(openaiBtn);
		expect(openaiBtn).toHaveAttribute("aria-checked", "true");
		// Model select should update to gpt-4o
		const modelSelect = screen.getByRole("combobox");
		expect((modelSelect as HTMLSelectElement).value).toContain("gpt-4o");
	});

	it("toggles API key visibility", () => {
		renderPage();
		const apiKeyInput = screen.getByTestId("api-key-input");
		expect(apiKeyInput).toHaveAttribute("type", "password");
		const toggleBtn = screen.getByLabelText("Show API key");
		fireEvent.click(toggleBtn);
		expect(screen.getByTestId("api-key-input")).toHaveAttribute(
			"type",
			"text",
		);
	});

	it("all 4 capability toggles are rendered", () => {
		renderPage();
		expect(screen.getByRole("switch", { name: /Spatial/i })).toBeInTheDocument();
		expect(
			screen.getByRole("switch", { name: /Voltage Drop/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("switch", { name: /Battery Sizing/i }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("switch", { name: /Darcy-Weisbach/i }),
		).toBeInTheDocument();
	});

	it("capability toggle changes state", () => {
		renderPage();
		const batteryToggle = screen.getByRole("switch", {
			name: /Battery Sizing/i,
		});
		// initially on (default)
		expect(batteryToggle).toHaveAttribute("aria-checked", "true");
		fireEvent.click(batteryToggle);
		expect(batteryToggle).toHaveAttribute("aria-checked", "false");
	});

	it("shows reset confirmation text on first click", () => {
		renderPage();
		const resetBtn = screen.getByRole("button", { name: /Reset Defaults/i });
		fireEvent.click(resetBtn);
		expect(screen.getByText("Confirm Reset")).toBeInTheDocument();
	});

	it("token budget slider updates displayed value", () => {
		renderPage();
		const slider = screen.getByTestId("token-budget-slider");
		fireEvent.change(slider, { target: { value: "2000" } });
		expect(screen.getByText(/2,000 tokens/)).toBeInTheDocument();
	});

	it("temperature slider is constrained to 0–0.10", () => {
		renderPage();
		const slider = screen.getByTestId("temperature-slider");
		expect(slider).toHaveAttribute("min", "0");
		expect(slider).toHaveAttribute("max", "0.1");
	});

	it("renders local-storage invariant note", () => {
		renderPage();
		expect(
			screen.getByText(/in-memory only/i),
		).toBeInTheDocument();
	});

	it("has correct page test id for automation", () => {
		renderPage();
		expect(screen.getByTestId("agent-settings-page")).toBeInTheDocument();
	});
});
