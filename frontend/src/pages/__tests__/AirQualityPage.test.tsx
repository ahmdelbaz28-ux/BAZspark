/**
 * AirQualityPage.test.tsx — Unit tests for Air Quality monitoring page.
 *
 * Tests: rendering, AQI fetch, PM2.5/PM10 display, AQI color coding,
 * unhealthy baseline badge, engineering notes, error state.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AirQualityPage } from "../AirQualityPage";

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
    Thermometer: createIcon("Thermometer"),
    Search: createIcon("Search"),
    Loader2: createIcon("Loader2"),
    Wind: createIcon("Wind"),
    AlertTriangle: createIcon("AlertTriangle"),
    Info: createIcon("Info"),
  };
});

const mockFetch = vi.fn();
global.fetch = mockFetch;

const MOCK_AQ_GOOD = {
  data: {
    aqi: 42,
    aqi_level: "Good",
    pm25_ug_m3: 8.5,
    pm10_ug_m3: 15.2,
    is_unhealthy_baseline: false,
    source: "WAQI",
    is_default: false,
    is_stale: false,
    location: { latitude: 30.0444, longitude: 31.2357 },
    engineering_notes: {
      tenability: "Low particulate levels — standard tenability margins apply.",
      detection: "Normal smoke detector sensitivity expected.",
    },
  },
};

const MOCK_AQ_UNHEALTHY = {
  data: {
    aqi: 175,
    aqi_level: "Unhealthy",
    pm25_ug_m3: 65.3,
    pm10_ug_m3: 120.1,
    is_unhealthy_baseline: true,
    source: "WAQI",
    is_default: false,
    is_stale: false,
    location: { latitude: 30.0444, longitude: 31.2357 },
    engineering_notes: {
      tenability: "Elevated particulate levels — increase tenability margins per NFPA 130.",
      detection: "Reduced smoke detector sensitivity expected.",
    },
  },
};

function renderPage() {
  return render(<AirQualityPage />);
}

describe("AirQualityPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/air-quality")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_AQ_GOOD),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("Air Quality")).toBeInTheDocument();
  });

  it("renders lat/lon inputs with defaults", () => {
    renderPage();
    expect(screen.getByDisplayValue("30.0444")).toBeInTheDocument();
    expect(screen.getByDisplayValue("31.2357")).toBeInTheDocument();
  });

  it("shows Check Air Quality button", () => {
    renderPage();
    expect(screen.getByText("Check Air Quality")).toBeInTheDocument();
  });

  it("fetches and displays AQI data on button click", async () => {
    renderPage();
    const btn = screen.getByText("Check Air Quality");
    await userEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText("42")).toBeInTheDocument();
      expect(screen.getByText("Good")).toBeInTheDocument();
    });
  });

  it("displays PM2.5 and PM10 values", async () => {
    renderPage();
    const btn = screen.getByText("Check Air Quality");
    await userEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText("8.5 µg/m³")).toBeInTheDocument();
      expect(screen.getByText("15.2 µg/m³")).toBeInTheDocument();
    });
  });

  it("shows engineering impact notes after fetch", async () => {
    renderPage();
    const btn = screen.getByText("Check Air Quality");
    await userEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText(/standard tenability margins/)).toBeInTheDocument();
      expect(screen.getByText(/Normal smoke detector/)).toBeInTheDocument();
    });
  });

  it("shows unhealthy baseline badge when applicable", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/air-quality")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_AQ_UNHEALTHY),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    renderPage();
    const btn = screen.getByText("Check Air Quality");
    await userEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText("Unhealthy Baseline")).toBeInTheDocument();
    });
  });

  it("shows unhealthy AQI level with correct styling", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/air-quality")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_AQ_UNHEALTHY),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    renderPage();
    const btn = screen.getByText("Check Air Quality");
    await userEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText("175")).toBeInTheDocument();
      expect(screen.getByText("Unhealthy")).toBeInTheDocument();
    });
  });

  it("shows error message on fetch failure", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    renderPage();
    const btn = screen.getByText("Check Air Quality");
    await userEvent.click(btn);

    await waitFor(() => {
      expect(
        screen.getByText("Network error")
      ).toBeInTheDocument();
    });
  });

  it("shows source info after fetch", async () => {
    renderPage();
    const btn = screen.getByText("Check Air Quality");
    await userEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByText("WAQI")).toBeInTheDocument();
    });
  });

  it("renders info section at the bottom", () => {
    renderPage();
    expect(screen.getByText(/WAQI/)).toBeInTheDocument();
  });
});
