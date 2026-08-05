/**
 * GuardsPage.test.tsx — Unit tests for Physics Guard Limits page.
 *
 * Tests: rendering, guard cards display, refresh, error state,
 * empty state, code references.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GuardsPage } from "../GuardsPage";

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

const MOCK_GUARDS = {
  guards: [
    {
      name: "max_cable_length",
      value: 1000,
      unit: "m",
      code_reference: "NEC 760.51",
      description: "Maximum SLC cable length per circuit",
    },
    {
      name: "max_voltage_drop",
      value: 5,
      unit: "%",
      code_reference: "NEC 210.19(A)",
      description: "Maximum allowable voltage drop from source",
    },
    {
      name: "min_detector_spacing",
      value: 9.1,
      unit: "m",
      code_reference: "NFPA 72 §17.7.4.3.3",
      description: "Maximum spacing for smoke detectors per NFPA 72",
    },
  ],
  total_count: 3,
};

function renderPage() {
  return render(<GuardsPage />);
}

describe("GuardsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_GUARDS),
    });
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("Physics Guards")).toBeInTheDocument();
  });

  it("shows loading initially", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/QOMN calculations/)).toBeInTheDocument();
  });

  it("displays guard cards after loading", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("max_cable_length")).toBeInTheDocument();
      expect(screen.getByText("max_voltage_drop")).toBeInTheDocument();
      expect(screen.getByText("min_detector_spacing")).toBeInTheDocument();
    });
  });

  it("displays guard values and units", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("1000 m")).toBeInTheDocument();
      expect(screen.getByText("5 %")).toBeInTheDocument();
      expect(screen.getByText("9.1 m")).toBeInTheDocument();
    });
  });

  it("displays code references", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("NEC 760.51")).toBeInTheDocument();
      expect(screen.getByText("NEC 210.19(A)")).toBeInTheDocument();
      expect(screen.getByText("NFPA 72 §17.7.4.3.3")).toBeInTheDocument();
    });
  });

  it("displays guard descriptions", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText(/Maximum SLC cable length/)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Maximum allowable voltage drop/)
      ).toBeInTheDocument();
    });
  });

  it("shows guard count summary", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/guard limit/)).toBeInTheDocument();
    });
  });

  it("shows Refresh button", () => {
    renderPage();
    expect(screen.getByText("Refresh")).toBeInTheDocument();
  });

  it("refreshes data on Refresh click", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("max_cable_length")).toBeInTheDocument();
    });

    const refreshBtn = screen.getByText("Refresh");
    await userEvent.click(refreshBtn);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });

  it("shows error message when fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("Connection refused"));
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("Failed to load physics guards")
      ).toBeInTheDocument();
    });
  });

  it("shows error detail when fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("Connection refused"));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Connection refused")).toBeInTheDocument();
    });
  });

  it("shows empty state when no guards", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ guards: [], total_count: 0 }),
    });
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("No physics guards configured.")
      ).toBeInTheDocument();
    });
  });

  it("shows last updated time after successful fetch", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
    });
  });
});
