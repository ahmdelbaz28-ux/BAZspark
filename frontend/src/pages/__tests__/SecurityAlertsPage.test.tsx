/**
 * SecurityAlertsPage.test.tsx — Unit tests for Security Alerts dashboard.
 *
 * Tests: rendering, alert list, severity filter, summary cards,
 * error fallback, refresh.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SecurityAlertsPage } from "../SecurityAlertsPage";

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

const MOCK_ALERTS = {
  alerts: [
    {
      id: "1",
      timestamp: new Date().toISOString(),
      severity: "critical",
      title: "Database Connection Failure",
      message: "Redis connection timeout after 30s",
      source: "database",
      acknowledged: false,
    },
    {
      id: "2",
      timestamp: new Date(Date.now() - 600000).toISOString(),
      severity: "high",
      title: "Failed Login Attempts",
      message: "5 failed login attempts from IP 203.0.113.42",
      source: "auth",
      acknowledged: false,
    },
    {
      id: "3",
      timestamp: new Date(Date.now() - 1800000).toISOString(),
      severity: "medium",
      title: "Unusual API Traffic",
      message: "Traffic spike detected on /api/v1/projects",
      source: "monitor",
      acknowledged: true,
    },
    {
      id: "4",
      timestamp: new Date(Date.now() - 3600000).toISOString(),
      severity: "low",
      title: "Expired API Key",
      message: "API key for user engineer@example.com expired",
      source: "auth",
      acknowledged: false,
    },
  ],
  total: 4,
  critical_count: 1,
  high_count: 1,
};

function renderPage() {
  return render(<SecurityAlertsPage />);
}

describe("SecurityAlertsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_ALERTS),
    });
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("Security Alerts")).toBeInTheDocument();
  });

  it("shows loading initially", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/BAZSPARK platform/)).toBeInTheDocument();
  });

  it("displays alerts after loading", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText("Database Connection Failure")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Failed Login Attempts")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Unusual API Traffic")
      ).toBeInTheDocument();
    });
  });

  it("displays alert messages", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText(/Redis connection timeout/)
      ).toBeInTheDocument();
      expect(
        screen.getByText(/failed login attempts/)
      ).toBeInTheDocument();
    });
  });

  it("shows severity labels as uppercase", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("CRITICAL")).toBeInTheDocument();
      expect(screen.getByText("HIGH")).toBeInTheDocument();
      expect(screen.getByText("MEDIUM")).toBeInTheDocument();
      expect(screen.getByText("LOW")).toBeInTheDocument();
    });
  });

  it("shows summary cards with counts", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("4")).toBeInTheDocument(); // Total
      expect(screen.getByText("3")).toBeInTheDocument(); // Active (not acknowledged)
    });
  });

  it("shows Refresh button", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Refresh")).toBeInTheDocument();
    });
  });

  it("has severity filter dropdown", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByDisplayValue("All Severities")).toBeInTheDocument();
    });
  });

  it("shows acknowledged alert with reduced opacity indicator", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Acknowledged")).toBeInTheDocument();
    });
  });

  it("falls back to sample data on fetch failure", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    renderPage();

    await waitFor(() => {
      // Should show fallback sample data
      expect(
        screen.getByText("Failed Login Attempts")
      ).toBeInTheDocument();
    });
  });

  it("shows error banner when backend unavailable", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText(/Backend unavailable/)
      ).toBeInTheDocument();
    });
  });

  it("shows source info for alerts", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("via database")).toBeInTheDocument();
      const authSources = screen.getAllByText("via auth");
      expect(authSources.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows empty state when no alerts", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ alerts: [], total: 0 }),
    });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("No security alerts.")).toBeInTheDocument();
    });
  });

  it("shows last updated timestamp", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
    });
  });

  it("filters alerts by severity", async () => {
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByText("CRITICAL")
      ).toBeInTheDocument();
    });

    const select = screen.getByDisplayValue("All Severities");
    await userEvent.selectOptions(select, "critical");

    await waitFor(() => {
      expect(screen.getByText("CRITICAL")).toBeInTheDocument();
      // Wait for re-fetch with severity param
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("severity=critical"),
        expect.anything()
      );
    });
  });
});
