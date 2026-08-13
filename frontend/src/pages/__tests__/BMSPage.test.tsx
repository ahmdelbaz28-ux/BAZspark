/**
 * BMSPage.test.tsx — Unit tests for Building Management Systems page.
 *
 * Tests: rendering title, system cards, refresh button, error state,
 * quick actions links, and health API fetch.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { BMSPage } from "../BMSPage";

vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "en", changeLanguage: vi.fn() },
	}),
	initReactI18next: { type: "3rdParty", init: vi.fn() },
}));

vi.mock("lucide-react", async (importOriginal) => {
	const actual = (await importOriginal()) as Record<string, unknown>;
	// Create a simple mock component for each icon export
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

const mockFetch = vi.fn();
global.fetch = mockFetch;

function renderPage() {
	return render(
		<MemoryRouter>
			<BMSPage />
		</MemoryRouter>,
	);
}

describe("BMSPage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockFetch.mockImplementation((url: string) => {
			if (url.includes("/health")) {
				return Promise.resolve({
					ok: true,
					json: () => Promise.resolve({ database: "connected", uptime: 3600 }),
				});
			}
			if (url.includes("/devices")) {
				return Promise.resolve({
					ok: true,
					json: () => Promise.resolve({ data: { total: 42 }, total: 42 }),
				});
			}
			return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
		});
	});

	it("renders the page title", () => {
		renderPage();
		expect(screen.getByText("Building Management Systems")).toBeInTheDocument();
	});

	it("renders all 4 system cards", async () => {
		renderPage();
		await waitFor(() => {
			// Use getAllByText for "System Health" as it appears in cards + Quick Actions
			expect(screen.getByText("Fire Alarm System")).toBeInTheDocument();
			expect(screen.getByText("Environmental Monitoring")).toBeInTheDocument();
			expect(screen.getByText("CAD & BIM Integration")).toBeInTheDocument();
			const systemHealthItems = screen.getAllByText("System Health");
			expect(systemHealthItems.length).toBeGreaterThanOrEqual(1);
		});
	});

	it("shows Refresh button", () => {
		renderPage();
		expect(screen.getByText("Refresh")).toBeInTheDocument();
	});

	it("shows loading text initially", () => {
		mockFetch.mockImplementation(() => new Promise(() => {}));
		renderPage();
		expect(screen.getByText("Loading system status...")).toBeInTheDocument();
	});

	it("shows last updated time after successful fetch", async () => {
		renderPage();
		await waitFor(() => {
			expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
		});
	});

	it("shows device count from API", async () => {
		renderPage();
		await waitFor(() => {
			const deviceMetrics = screen.getAllByText("42");
			expect(deviceMetrics.length).toBeGreaterThanOrEqual(1);
		});
	});

	it("shows error state on fetch failure", async () => {
		mockFetch.mockRejectedValue(new Error("Network error"));
		renderPage();
		await waitFor(() => {
			expect(
				screen.getByText("Failed to fetch system status"),
			).toBeInTheDocument();
		});
	});

	it("shows Quick Actions section", async () => {
		renderPage();
		expect(screen.getByText("Quick Actions")).toBeInTheDocument();
		expect(screen.getByText("FACP Designer")).toBeInTheDocument();
		// "Weather" appears in card descriptions too — use getAllByText
		const weatherItems = screen.getAllByText("Weather");
		expect(weatherItems.length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText("DWG/DXF Parse")).toBeInTheDocument();
		const systemHealthQA = screen.getAllByText("System Health");
		expect(systemHealthQA.length).toBeGreaterThanOrEqual(1);
	});

	it("renders View details links on system cards", async () => {
		renderPage();
		await waitFor(() => {
			const links = screen.getAllByText("View details →");
			expect(links.length).toBe(4);
		});
	});

	it("shows healthy status for fire alarm after fetch", async () => {
		renderPage();
		await waitFor(() => {
			expect(screen.getByText("Healthy")).toBeInTheDocument();
		});
	});
});
