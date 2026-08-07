/**
 * SyncPage.test.tsx — Unit tests for Project Synchronization Dashboard.
 *
 * Tests: rendering, project selector, sync status display,
 * sync trigger, loading/error states, info section.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SyncPage } from "../SyncPage";

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
                const Icon = (_props: Record<string, unknown>) => (
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

// Mock the fullApi module so we control syncApi.getSyncStatus/syncProject
// directly without going through the real apiCall/fetchWithRetry/CSRF pipeline.
const mockGetSyncStatus = vi.fn();
const mockSyncProject = vi.fn();

vi.mock("@/services/fullApi", () => ({
  syncApi: {
    getSyncStatus: (...args: unknown[]) => mockGetSyncStatus(...args),
    syncProject: (...args: unknown[]) => mockSyncProject(...args),
  },
}));

const mockFetch = vi.fn();
global.fetch = mockFetch;

const MOCK_PROJECTS = {
  success: true,
  data: {
    data: [
      { id: "proj-1", name: "Building A" },
      { id: "proj-2", name: "Building B" },
      { id: "proj-3", name: "Warehouse C" },
    ],
    total: 3,
  },
};

const MOCK_SYNC_STATUS_SYNCED = {
  status: "synced",
  lastSync: "2026-07-30T12:00:00Z",
  pendingChanges: 0,
  deviceCount: 24,
  connectionCount: 8,
};

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderPage() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <SyncPage />
    </QueryClientProvider>
  );
}

describe("SyncPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/projects?limit=50")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_PROJECTS),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });
    // The real syncApi methods go through apiCall, which ALREADY unwraps the
    // backend's { data, success } envelope (see apiClient.fetchWithRetry), so
    // the mocked syncApi resolves the payload shape directly.
    mockGetSyncStatus.mockResolvedValue(MOCK_SYNC_STATUS_SYNCED);
    mockSyncProject.mockResolvedValue(MOCK_SYNC_STATUS_SYNCED);
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("Project Sync")).toBeInTheDocument();
  });

  it("shows the project selector label", () => {
    renderPage();
    expect(screen.getByText("Select Project")).toBeInTheDocument();
  });

  it("loads projects into the dropdown", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Building A")).toBeInTheDocument();
      expect(screen.getByText("Building B")).toBeInTheDocument();
      expect(screen.getByText("Warehouse C")).toBeInTheDocument();
    });
  });

  it("shows sync status panel after selecting a project", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Building A")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "proj-1");

    await waitFor(() => {
      expect(screen.getByText("Sync Status")).toBeInTheDocument();
    });
  });

  it("displays sync status metrics after project selection", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Building A")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "proj-1");

    await waitFor(() => {
      expect(screen.getByText("Synced")).toBeInTheDocument();
      expect(screen.getByText("24")).toBeInTheDocument();
      expect(screen.getByText("8")).toBeInTheDocument();
    });
  });

  it("shows Refresh and Sync Now buttons after selecting a project", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Building A")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "proj-1");

    await waitFor(() => {
      expect(screen.getByText("Refresh")).toBeInTheDocument();
      expect(screen.getByText("Sync Now")).toBeInTheDocument();
    });
  });

  it("triggers sync mutation on Sync Now click", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Building A")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "proj-1");

    await waitFor(() => {
      expect(screen.getByText("Sync Now")).toBeInTheDocument();
    });

    const syncBtn = screen.getByText("Sync Now");
    await userEvent.click(syncBtn);

    await waitFor(() => {
      expect(mockSyncProject).toHaveBeenCalledWith("proj-1");
    });
  });

  it("shows Syncing... text during sync", async () => {
    mockSyncProject.mockImplementation(() => new Promise(() => {})); // Never resolves

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Building A")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "proj-1");

    await waitFor(() => {
      expect(screen.getByText("Sync Now")).toBeInTheDocument();
    });

    const syncBtn = screen.getByText("Sync Now");
    await userEvent.click(syncBtn);

    await waitFor(() => {
      expect(screen.getByText("Syncing...")).toBeInTheDocument();
    });
  });

  it("shows error on sync failure", async () => {
    mockSyncProject.mockRejectedValue(new Error("Sync failed: DB unavailable"));

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Building A")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "proj-1");

    await waitFor(() => {
      expect(screen.getByText("Sync Now")).toBeInTheDocument();
    });

    const syncBtn = screen.getByText("Sync Now");
    await userEvent.click(syncBtn);

    await waitFor(() => {
      expect(screen.getByText("Sync failed: DB unavailable")).toBeInTheDocument();
    });
  });

  it("shows error when sync status fetch fails", async () => {
    mockGetSyncStatus.mockRejectedValue(new Error("HTTP 404: Not Found"));

    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Building A")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox");
    await userEvent.selectOptions(select, "proj-1");

    await waitFor(() => {
      expect(
        screen.getByText("Failed to load sync status")
      ).toBeInTheDocument();
    });
  });

  it("shows About Project Sync info section", () => {
    renderPage();
    expect(screen.getByText("About Project Sync")).toBeInTheDocument();
  });

  it("shows no sync data prompt when no project selected", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByDisplayValue("Select a project...")).toBeInTheDocument();
    });
  });

  it("shows projects loading text", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    renderPage();
    expect(screen.getByText("Loading projects...")).toBeInTheDocument();
  });
});
