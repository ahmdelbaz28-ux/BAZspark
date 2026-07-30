/**
 * ContextPage.test.tsx — Unit tests for Weather & Geocoding page.
 *
 * Tests: rendering, weather fetch, geocoding search, region display,
 * error states, loading states.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ContextPage } from "../ContextPage";

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
    Wind: createIcon("Wind"),
    Search: createIcon("Search"),
    MapPin: createIcon("MapPin"),
    Loader2: createIcon("Loader2"),
    Globe: createIcon("Globe"),
    Thermometer: createIcon("Thermometer"),
    Droplets: createIcon("Droplets"),
    Landmark: createIcon("Landmark"),
  };
});

const mockFetch = vi.fn();
global.fetch = mockFetch;

const MOCK_WEATHER = {
  data: {
    temperature_c: 25.3,
    wind_speed_m_s: 4.2,
    relative_humidity_pct: 60,
    air_density_kg_m3: 1.2,
    source: "Open-Meteo",
    is_default: false,
    location: { latitude: 30.0444, longitude: 31.2357 },
  },
};

const MOCK_GEOCODE = {
  success: true,
  data: {
    latitude: 30.0444,
    longitude: 31.2357,
    display_name: "Cairo, Egypt",
    country_code: "EG",
  },
};

const MOCK_REGION = {
  success: true,
  data: {
    country_code: "EG",
    country_name: "Egypt",
    regulatory_framework: "NFPA 72 / Egyptian Fire Code",
    electrical_code: "IEC 60364",
    is_gulf_state: false,
    is_eu: false,
  },
};

function renderPage() {
  return render(<ContextPage />);
}

describe("ContextPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/weather")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_WEATHER),
        });
      }
      if (url.includes("/geocode")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_GEOCODE),
        });
      }
      if (url.includes("/region")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_REGION),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("Weather & Geocoding")).toBeInTheDocument();
  });

  it("renders both panels: Current Weather and Geocoding & Region", () => {
    renderPage();
    expect(screen.getByText("Current Weather")).toBeInTheDocument();
    expect(screen.getByText("Geocoding & Region")).toBeInTheDocument();
  });

  it("shows default lat/lon values", () => {
    renderPage();
    const latInput = screen.getByDisplayValue("30.0444");
    const lonInput = screen.getByDisplayValue("31.2357");
    expect(latInput).toBeInTheDocument();
    expect(lonInput).toBeInTheDocument();
  });

  it("shows Get Weather button", () => {
    renderPage();
    expect(screen.getByText("Get Weather")).toBeInTheDocument();
  });

  it("fetches and displays weather data on button click", async () => {
    renderPage();
    const btn = screen.getByText("Get Weather");
    await userEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText("25.3°C")).toBeInTheDocument();
      expect(screen.getByText("4.2 m/s")).toBeInTheDocument();
      expect(screen.getByText("60%")).toBeInTheDocument();
      expect(screen.getByText("1.2 kg/m³")).toBeInTheDocument();
    });
  });

  it("shows weather source info after fetch", async () => {
    renderPage();
    const btn = screen.getByText("Get Weather");
    await userEvent.click(btn);

    await waitFor(() => {
      const sources = screen.getAllByText(/Open-Meteo/);
      expect(sources.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows error message when weather fetch fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/weather")) {
        return Promise.resolve({
          ok: false,
          status: 500,
          json: () => Promise.resolve({}),
        });
      }
      return Promise.resolve({ ok: false });
    });

    renderPage();
    const btn = screen.getByText("Get Weather");
    await userEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/HTTP 500/)).toBeInTheDocument();
    });
  });

  it("has address input and search button for geocoding", () => {
    renderPage();
    expect(
      screen.getByPlaceholderText(/Enter address/)
    ).toBeInTheDocument();
  });

  const enterAddress = async (address: string) => {
    const input = screen.getByPlaceholderText(/Enter address/);
    await userEvent.clear(input);
    await userEvent.type(input, `${address}{Enter}`);
  };

  it("fetches geocode on address search", async () => {
    renderPage();
    await enterAddress("Cairo, Egypt");

    await waitFor(() => {
      expect(screen.getByText("Cairo, Egypt")).toBeInTheDocument();
    });
  });

  it("displays latitude and longitude after geocode", async () => {
    renderPage();
    await enterAddress("Cairo, Egypt");

    await waitFor(() => {
      expect(screen.getByText("30.0444")).toBeInTheDocument();
      expect(screen.getByText("31.2357")).toBeInTheDocument();
    });
  });

  it("displays regulatory region after geocode", async () => {
    renderPage();
    await enterAddress("Cairo, Egypt");

    await waitFor(() => {
      expect(screen.getByText("Egypt")).toBeInTheDocument();
      expect(screen.getByText("NFPA 72 / Egyptian Fire Code")).toBeInTheDocument();
    });
  });

  it("shows geocoding error on failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/geocode")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: false,
              error: "Geocoding failed: address not found",
            }),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    renderPage();
    await enterAddress("Nowhere");

    await waitFor(() => {
      expect(
        screen.getByText(/Geocoding failed/)
      ).toBeInTheDocument();
    });
  });

  it("shows placeholder when no geocode data", () => {
    renderPage();
    expect(
      screen.getByText(/Search for an address/)
    ).toBeInTheDocument();
  });

  it("shows info section at the bottom", () => {
    renderPage();
    expect(screen.getByText(/Open-Meteo/)).toBeInTheDocument();
  });
});
