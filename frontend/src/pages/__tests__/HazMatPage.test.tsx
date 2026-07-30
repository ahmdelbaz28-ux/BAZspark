/**
 * HazMatPage.test.tsx — Unit tests for Hazardous Materials Database page.
 *
 * Tests: rendering, material search, known materials chips,
 * properties display, engineering notes, error state.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HazMatPage } from "../HazMatPage";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en", changeLanguage: vi.fn() },
  }),
  initReactI18next: { type: "3rdParty", init: vi.fn() },
}));

vi.mock("lucide-react", () => {
  const createIcon = (name: string) => {
    const Icon = (props: Record<string, unknown>) => (
      <span data-testid={`icon-${name.toLowerCase()}`}>{name}</span>
    );
    Icon.displayName = name;
    return Icon;
  };
  return {
    AlertTriangle: createIcon("AlertTriangle"),
    Search: createIcon("Search"),
    Loader2: createIcon("Loader2"),
    FlaskConical: createIcon("FlaskConical"),
    Thermometer: createIcon("Thermometer"),
    Beaker: createIcon("Beaker"),
    BookOpen: createIcon("BookOpen"),
  };
});

const mockFetch = vi.fn();
global.fetch = mockFetch;

const MOCK_KNOWN = {
  success: true,
  data: {
    materials: ["methane", "propane", "hydrogen", "acetylene", "carbon monoxide"],
  },
};

const MOCK_METHANE = {
  success: true,
  data: {
    name: "methane",
    cas_number: "74-82-8",
    lfl_vol_pct: 5.0,
    ufl_vol_pct: 15.0,
    flammable_range_vol_pct: "5.0% – 15.0%",
    flash_point_c: -188,
    auto_ignition_c: 537,
    material_group: "IIA",
    temperature_class: "T1",
    molecular_weight: 16.04,
    vapor_density: 0.55,
    source: "IEC 60079-10-1 Table B.1",
    is_default: false,
    is_conservative: false,
    engineering_notes: {
      hac: "Methane is lighter than air — HAC zone extends upward from release point.",
      equipment: "Group IIA, T1 — standard gas detection equipment suitable.",
    },
  },
};

function renderPage() {
  return render(<HazMatPage />);
}

describe("HazMatPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/hazmat/known")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_KNOWN),
        });
      }
      if (url.includes("/hazmat?material")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_METHANE),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });
  });

  it("renders the page title", async () => {
    renderPage();
    expect(
      screen.getByText("Hazardous Materials Database")
    ).toBeInTheDocument();
  });

  it("loads known materials on mount", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("methane")).toBeInTheDocument();
      expect(screen.getByText("propane")).toBeInTheDocument();
      expect(screen.getByText("hydrogen")).toBeInTheDocument();
    });
  });

  it("shows known materials label", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Known materials:")).toBeInTheDocument();
    });
  });

  it("has search input and search button", () => {
    renderPage();
    expect(
      screen.getByPlaceholderText(/Search material/)
    ).toBeInTheDocument();
    const searchButtons = screen.getAllByText("Search");
    expect(searchButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("searches material on Enter key", async () => {
    renderPage();
    const input = screen.getByPlaceholderText(/Search material/);
    await userEvent.type(input, "methane{Enter}");

    await waitFor(() => {
      expect(screen.getByText("CAS: 74-82-8")).toBeInTheDocument();
    });
  });

  it("displays material properties after search", async () => {
    renderPage();
    const input = screen.getByPlaceholderText(/Search material/);
    await userEvent.type(input, "methane{Enter}");

    await waitFor(() => {
      expect(screen.getByText("5% – 15%")).toBeInTheDocument();
      expect(screen.getByText("-188°C")).toBeInTheDocument();
      expect(screen.getByText("537°C")).toBeInTheDocument();
    });
  });

  it("displays material group and temperature class", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("methane")).toBeInTheDocument();
    });
    const chip = screen.getByText("methane");
    await userEvent.click(chip);

    await waitFor(() => {
      expect(screen.getByText("IIA")).toBeInTheDocument();
      expect(screen.getByText("T1")).toBeInTheDocument();
    });
  });

  it("displays engineering notes after search", async () => {
    renderPage();
    const input = screen.getByPlaceholderText(/Search material/);
    await userEvent.type(input, "methane{Enter}");

    await waitFor(() => {
      expect(screen.getByText(/lighter than air/)).toBeInTheDocument();
      expect(screen.getByText(/Group IIA, T1/)).toBeInTheDocument();
    });
  });

  it("clicking a known material chip triggers search", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("hydrogen")).toBeInTheDocument();
    });

    const hydrogenBtn = screen.getByText("hydrogen");
    await userEvent.click(hydrogenBtn);

    await waitFor(() => {
      // Should set the query and fetch the material
      expect(screen.getByDisplayValue("hydrogen")).toBeInTheDocument();
    });
  });

  it("shows error when material is not found", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/hazmat/known")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_KNOWN),
        });
      }
      if (url.includes("/hazmat?material")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: false,
              error: "Material not found in database",
            }),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    renderPage();
    const input = screen.getByPlaceholderText(/Search material/);
    await userEvent.type(input, "unknown_gas{Enter}");

    await waitFor(() => {
      expect(
        screen.getByText(/Material not found/)
      ).toBeInTheDocument();
    });
  });

  it("shows search on Enter key press", async () => {
    renderPage();
    const input = screen.getByPlaceholderText(/Search material/);
    await userEvent.type(input, "methane{Enter}");

    await waitFor(() => {
      expect(screen.getByText("CAS: 74-82-8")).toBeInTheDocument();
    });
  });

  it("shows info section at the bottom", () => {
    renderPage();
    const refs = screen.getAllByText(/IEC 60079/);
    expect(refs.length).toBeGreaterThanOrEqual(1);
  });
});
