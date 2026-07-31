/**
 * AnalysisPage.test.tsx — Unit tests for NFPA 72 / NEC Analysis page.
 *
 * Tests: rendering title, tab selector (battery, voltage, room),
 * battery form, voltage form, room analysis form, run analysis button,
 * results display, error state, project selector.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnalysisPage } from "../AnalysisPage";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en", changeLanguage: vi.fn() },
  }),
  initReactI18next: { type: "3rdParty", init: vi.fn() },
}));

vi.mock("lucide-react", async (importOriginal) => {
	const actual = await importOriginal() as Record<string, unknown>;
	// Create a simple mock component for each icon export
	const createIcon = (name: string) => {
		const Icon = (props: Record<string, unknown>) => (
			<span data-testid={`icon-${name.toLowerCase()}`}>{name}</span>
		);
		Icon.displayName = name;
		return Icon;
	};
	const mocked: Record<string, unknown> = {};
	for (const [key, value] of Object.entries(actual)) {
		if (typeof value === "function" || (typeof value === "object" && value !== null && "$$typeof" in (value as Record<string, unknown>))) {
			mocked[key] = createIcon(key);
		} else {
			mocked[key] = value;
		}
	}
	return mocked;
});

const mockFetch = vi.fn();
global.fetch = mockFetch;

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderPage() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <AnalysisPage />
    </QueryClientProvider>
  );
}

describe("AnalysisPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: projects fetch succeeds
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/projects")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: {
                data: [
                  { id: "proj-1", name: "Building A" },
                  { id: "proj-2", name: "Building B" },
                ],
                total: 2,
              },
            }),
        });
      }
      if (url.includes("/analyze")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({}),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("NFPA 72 / NEC Analysis")).toBeInTheDocument();
  });

  it("renders all 3 analysis tabs", () => {
    renderPage();
    expect(screen.getByText("Battery Capacity")).toBeInTheDocument();
    expect(screen.getByText("Voltage Drop")).toBeInTheDocument();
    expect(screen.getByText("Room Analysis")).toBeInTheDocument();
  });

  it("shows battery form by default", () => {
    renderPage();
    expect(screen.getByText("Total Load (A)")).toBeInTheDocument();
    expect(screen.getByText("Backup Duration (min)")).toBeInTheDocument();
    expect(
      screen.getByText("NFPA 72 standby battery sizing")
    ).toBeInTheDocument();
  });

  it("switches to voltage form when Voltage Drop tab is clicked", async () => {
    renderPage();
    const voltageTab = screen.getByText("Voltage Drop");
    await userEvent.click(voltageTab);

    expect(screen.getByText("Length (ft)")).toBeInTheDocument();
    expect(screen.getByText("Current (A)")).toBeInTheDocument();
    expect(screen.getByText("Wire (AWG)")).toBeInTheDocument();
    expect(
      screen.getByText("NEC Chapter 9 Table 8 voltage drop")
    ).toBeInTheDocument();
  });

  it("switches to room analysis form when Room Analysis tab is clicked", async () => {
    renderPage();
    const roomTab = screen.getByText("Room Analysis");
    await userEvent.click(roomTab);

    expect(screen.getByText("Project")).toBeInTheDocument();
    expect(
      screen.getByText("Full room coverage & detection analysis")
    ).toBeInTheDocument();
  });

  it("shows Run Analysis button", () => {
    renderPage();
    expect(screen.getByText("Run Analysis")).toBeInTheDocument();
  });

  it("renders projects in the room analysis dropdown", async () => {
    renderPage();
    const roomTab = screen.getByText("Room Analysis");
    await userEvent.click(roomTab);

    await waitFor(() => {
      expect(screen.getByText("Select a project...")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox");
    const options = select.querySelectorAll("option");
    expect(options.length).toBeGreaterThanOrEqual(3); // default + 2 projects
  });

  it("shows battery capacity results after successful battery analysis", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/projects")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { data: [{ id: "proj-1", name: "Building A" }], total: 1 },
            }),
        });
      }
      if (url.includes("/analyze/battery")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: {
                required_capacity_ah: 18.5,
                selected_battery_ah: 24,
                backup_minutes: 24,
                margin_percent: 29.7,
              },
            }),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    renderPage();
    const runBtn = screen.getByText("Run Analysis");
    await userEvent.click(runBtn);

    await waitFor(() => {
      expect(
        screen.getByText("Battery Capacity Results")
      ).toBeInTheDocument();
      expect(screen.getByText("18.5 Ah")).toBeInTheDocument();
      expect(screen.getByText("24 Ah")).toBeInTheDocument();
      expect(screen.getByText("24 min")).toBeInTheDocument();
      expect(screen.getByText("29.7%")).toBeInTheDocument();
    });
  });

  it("shows voltage drop results after successful voltage analysis", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/projects")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { data: [{ id: "proj-1", name: "Building A" }], total: 1 },
            }),
        });
      }
      if (url.includes("/analyze/voltage")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: {
                drop_percent: 2.34,
                drop_volts: 0.562,
                passes: true,
                recommended_wire: "12 AWG",
              },
            }),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    renderPage();
    const voltageTab = screen.getByText("Voltage Drop");
    await userEvent.click(voltageTab);

    const runBtn = screen.getByText("Run Analysis");
    await userEvent.click(runBtn);

    await waitFor(() => {
      expect(
        screen.getByText("Voltage Drop Results")
      ).toBeInTheDocument();
      expect(screen.getByText("2.34%")).toBeInTheDocument();
      expect(screen.getByText("0.562 V")).toBeInTheDocument();
      expect(screen.getByText("PASS")).toBeInTheDocument();
      expect(screen.getAllByText("12 AWG").length).toBeGreaterThanOrEqual(2);
    });
  });

  it("shows error message on analysis failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/projects")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { data: [], total: 0 },
            }),
        });
      }
      if (url.includes("/analyze/battery")) {
        return Promise.resolve({
          ok: false,
          status: 400,
          json: () =>
            Promise.resolve({ detail: "Invalid load value" }),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    renderPage();
    const runBtn = screen.getByText("Run Analysis");
    await userEvent.click(runBtn);

    await waitFor(() => {
      expect(
        screen.getByText("Invalid load value")
      ).toBeInTheDocument();
    });
  });

  it("shows Calculating... during pending analysis", async () => {
    mockFetch.mockImplementation(
      (url: string) => {
        if (url.includes("/projects")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                success: true,
                data: { data: [], total: 0 },
              }),
          });
        }
        return new Promise(() => {}); // Never resolves
      }
    );

    renderPage();
    const runBtn = screen.getByText("Run Analysis");
    await userEvent.click(runBtn);

    expect(screen.getByText("Calculating...")).toBeInTheDocument();
  });

  it("shows default input values for battery analysis", () => {
    renderPage();
    const loadInput = screen.getByDisplayValue("25");
    const minutesInput = screen.getByDisplayValue("24");
    expect(loadInput).toBeInTheDocument();
    expect(minutesInput).toBeInTheDocument();
  });

  it("shows wire gauge options for voltage analysis", async () => {
    renderPage();
    const voltageTab = screen.getByText("Voltage Drop");
    await userEvent.click(voltageTab);

    const wireSelect = screen.getByDisplayValue("14 AWG");
    expect(wireSelect).toBeInTheDocument();
  });
});
