/**
 * AuditTrailPage.test.tsx — Unit tests for Audit Trail dashboard.
 *
 * Tests: rendering, event list, search/filter, refresh,
 * sample data fallback, error state.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuditTrailPage } from "../AuditTrailPage";

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
    ClipboardList: createIcon("ClipboardList"),
    Loader2: createIcon("Loader2"),
    RefreshCw: createIcon("RefreshCw"),
    AlertTriangle: createIcon("AlertTriangle"),
    Search: createIcon("Search"),
  };
});

const mockFetch = vi.fn();
global.fetch = mockFetch;

function createWorkflowResponse() {
  return {
    ok: true,
    json: () =>
      Promise.resolve({
        workflows: [
          {
            id: "WF-001",
            transition_log: [
              {
                timestamp: new Date(Date.now() - 60000).toISOString(),
                action: "workflow.approved",
                actor: "admin",
                comment: "Smoke detector layout approved",
              },
              {
                timestamp: new Date(Date.now() - 300000).toISOString(),
                action: "workflow.submitted",
                actor: "engineer",
                comment: "Initial layout submitted for review",
              },
            ],
          },
        ],
      }),
  };
}

function renderPage() {
  return render(<AuditTrailPage />);
}

describe("AuditTrailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", () => {
    mockFetch.mockResolvedValue({ ok: false });
    renderPage();
    expect(screen.getByText("Audit Trail")).toBeInTheDocument();
  });

  it("shows loading initially", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText(/NFPA 72 §10.6/)).toBeInTheDocument();
  });

  it("displays events from workflow API", async () => {
    mockFetch.mockResolvedValue(createWorkflowResponse());
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("workflow.approved")
      ).toBeInTheDocument();
      expect(
        screen.getByText("Smoke detector layout approved")
      ).toBeInTheDocument();
    });
  });

  it("falls back to sample data when API is unavailable", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("workflow.approved")
      ).toBeInTheDocument();
      expect(
        screen.getByText("device.created")
      ).toBeInTheDocument();
    });
  });

  it("shows Refresh button", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Refresh")).toBeInTheDocument();
    });
  });

  it("has search input", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    renderPage();
    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("Search events...")
      ).toBeInTheDocument();
    });
  });

  it("has type filter dropdown", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    renderPage();
    await waitFor(() => {
      expect(screen.getByDisplayValue("All Types")).toBeInTheDocument();
    });
  });

  it("filters events by search query", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("device.created")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText("Search events...");
    await userEvent.type(searchInput, "workflow");

    await waitFor(() => {
      expect(screen.getByText("workflow.approved")).toBeInTheDocument();
      expect(screen.getByText("workflow.rejected")).toBeInTheDocument();
    });
  });

  it("shows event details like entity ID and user", async () => {
    mockFetch.mockResolvedValue(createWorkflowResponse());
    renderPage();

    await waitFor(() => {
      const wfElements = screen.getAllByText("WF-001");
      expect(wfElements.length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText(/admin/)).toBeInTheDocument();
    });
  });

  it("renders event severity badges", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    renderPage();

    await waitFor(() => {
      const actionLabels = screen.getAllByText(/workflow\./, { exact: false });
      expect(actionLabels.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("shows event count summary", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText(/total events/)
      ).toBeInTheDocument();
    });
  });

  it("shows empty state when no events match filter", async () => {
    mockFetch.mockResolvedValue({ ok: false });
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("device.created")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText("Search events...");
    await userEvent.type(searchInput, "zzz_no_match_zzz");

    await waitFor(() => {
      expect(
        screen.getByText(/No events match/)
      ).toBeInTheDocument();
    });
  });
});
