/**
 * DevicesPage.test.tsx — Unit tests for DevicesPage CRUD component.
 *
 * Tests: rendering, device listing, empty state, error state,
 * create/edit/delete modals, filters, pagination, fallback.
 */
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DevicesPage } from "../DevicesPage";

// ── Mocks ──────────────────────────────────────────────────────────────────

// Mock react-i18next (same pattern as DashboardPage.test.tsx)
vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en", changeLanguage: vi.fn() },
  }),
  initReactI18next: { type: "3rdParty", init: vi.fn() },
}));

// Mock lucide-react icons (prevent rendering issues in test)
vi.mock("lucide-react", () => {
  const createIcon = (name: string) => {
    const Icon = (props: Record<string, unknown>) => (
      <span data-testid={`icon-${name.toLowerCase()}`} {...props}>
        {name}
      </span>
    );
    Icon.displayName = name;
    return Icon;
  };
  return {
    Loader2: createIcon("Loader2"),
    Plus: createIcon("Plus"),
    Trash2: createIcon("Trash2"),
    Pencil: createIcon("Pencil"),
    Cpu: createIcon("Cpu"),
  };
});

// Mock digitalTwinApi (the device CRUD service)
const mockGetDevices = vi.fn();
const mockCreateDevice = vi.fn();
const mockUpdateDevice = vi.fn();
const mockDeleteDevice = vi.fn();

vi.mock("@/services/digitalTwinApi", () => ({
  default: {
    getDevices: (...args: unknown[]) => mockGetDevices(...args),
    createDevice: (...args: unknown[]) => mockCreateDevice(...args),
    updateDevice: (...args: unknown[]) => mockUpdateDevice(...args),
    deleteDevice: (...args: unknown[]) => mockDeleteDevice(...args),
  },
  __esModule: true,
}));

// Mock fetch for project ID resolution and fallback
const mockFetch = vi.fn();
global.fetch = mockFetch;

// ── Test Data ───────────────────────────────────────────────────────────────

const MOCK_PROJECT = { id: "proj-001", name: "Test Project" };

const MOCK_DEVICES = [
  {
    id: "dev-001",
    projectId: "proj-001",
    type: "smoke_detector",
    name: "SD-101",
    category: "detection",
    x: 10.5,
    y: 20.3,
    z: 3.0,
    rotation: 0,
    voltage: 24,
    current: 0.05,
    load: 0.05,
    properties: {},
    createdAt: "2026-01-15T10:00:00Z",
    updatedAt: "2026-01-15T10:00:00Z",
  },
  {
    id: "dev-002",
    projectId: "proj-001",
    type: "heat_detector",
    name: "HD-201",
    category: "detection",
    x: 15.0,
    y: 25.0,
    z: 3.0,
    rotation: 0,
    voltage: 24,
    current: 0.03,
    load: 0.03,
    properties: {},
    createdAt: "2026-01-16T10:00:00Z",
    updatedAt: "2026-01-16T10:00:00Z",
  },
  {
    id: "dev-003",
    projectId: "proj-001",
    type: "pull_station",
    name: "PS-301",
    category: "notification",
    x: 5.0,
    y: 10.0,
    z: 1.2,
    rotation: 90,
    voltage: 24,
    current: 0.02,
    load: 0.02,
    properties: {},
    createdAt: "2026-01-17T10:00:00Z",
    updatedAt: "2026-01-17T10:00:00Z",
  },
];

const PAGINATED_RESPONSE = {
  data: MOCK_DEVICES,
  total: 3,
  page: 1,
  limit: 20,
  totalPages: 1,
};

// ── Test Wrapper ────────────────────────────────────────────────────────────

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

// ── Test Suite ──────────────────────────────────────────────────────────────

describe("DevicesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock: project fetch succeeds, device fetch succeeds
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/projects")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { data: [MOCK_PROJECT], total: 1 },
            }),
        });
      }
      if (url.includes("/devices")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(PAGINATED_RESPONSE),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });

    // Default mock for digitalTwinApi
    mockGetDevices.mockResolvedValue({
      success: true,
      data: PAGINATED_RESPONSE,
    });
    mockCreateDevice.mockResolvedValue({
      success: true,
      data: MOCK_DEVICES[0],
    });
    mockUpdateDevice.mockResolvedValue({
      success: true,
      data: MOCK_DEVICES[0],
    });
    mockDeleteDevice.mockResolvedValue({
      success: true,
      data: null,
    });
  });

  // ── Rendering Tests ───────────────────────────────────────────────────

  it("renders the page title", async () => {
    renderWithProviders(<DevicesPage />);
    expect(screen.getByText("Devices")).toBeInTheDocument();
  });

  it("shows the Add Device button", async () => {
    renderWithProviders(<DevicesPage />);
    const addButton = await screen.findByText("Add Device");
    expect(addButton).toBeInTheDocument();
  });

  it("renders device count after loading", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("3 fire alarm devices")).toBeInTheDocument();
    });
  });

  it("renders type and category filter dropdowns", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      // Native <select> elements have role "combobox"
      const selects = screen.getAllByRole("combobox");
      expect(selects.length).toBeGreaterThanOrEqual(2);
    });
  });

  // ── Device List Tests ─────────────────────────────────────────────────

  it("displays device names in the table", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
      expect(screen.getByText("HD-201")).toBeInTheDocument();
      expect(screen.getByText("PS-301")).toBeInTheDocument();
    });
  });

  it("displays device types correctly", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("smoke detector")).toBeInTheDocument();
      expect(screen.getByText("heat detector")).toBeInTheDocument();
      expect(screen.getByText("pull station")).toBeInTheDocument();
    });
  });

  it("displays electrical parameters", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      const voltageCells = screen.getAllByText("24 V");
      expect(voltageCells.length).toBeGreaterThanOrEqual(2);
    });
  });

  it("shows edit and delete buttons for each device", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      const editButtons = screen.getAllByTitle("Edit");
      const deleteButtons = screen.getAllByTitle("Delete");
      expect(editButtons).toHaveLength(3);
      expect(deleteButtons).toHaveLength(3);
    });
  });

  // ── Empty State Tests ─────────────────────────────────────────────────

  it("shows empty state when no devices exist", async () => {
    mockGetDevices.mockResolvedValue({
      success: true,
      data: { data: [], total: 0, page: 1, limit: 20, totalPages: 0 },
    });

    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("No devices found")).toBeInTheDocument();
      expect(
        screen.getByText("Add your first fire alarm device"),
      ).toBeInTheDocument();
    });
  });

  // ── Loading State Tests ───────────────────────────────────────────────

  it("shows loading text while fetching devices", () => {
    // Make the query never resolve so loading persists
    mockGetDevices.mockImplementation(
      () => new Promise(() => {}), // Never resolves
    );

    renderWithProviders(<DevicesPage />);
    expect(screen.getByText("Loading devices...")).toBeInTheDocument();
  });

  // ── Error State Tests ─────────────────────────────────────────────────

  it("shows error message when fetch fails", async () => {
    mockGetDevices.mockRejectedValue(new Error("Network error"));

    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("Failed to load devices")).toBeInTheDocument();
    });
  });

  // ── Filter Tests ──────────────────────────────────────────────────────

  it("applies type filter when user selects a device type", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
    });

    // Find the type filter select (first one)
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "heat_detector" } });

    await waitFor(() => {
      expect(mockGetDevices).toHaveBeenCalled();
    });
  });

  it("shows clear filters button when filter is active", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
    });

    // Apply a filter
    const selects = screen.getAllByRole("combobox");
    fireEvent.change(selects[0], { target: { value: "pull_station" } });

    await waitFor(() => {
      expect(screen.getByText("✕ Clear filters")).toBeInTheDocument();
    });
  });

  // ── Create Modal Tests ────────────────────────────────────────────────

  it("opens create modal on Add Device button click", async () => {
    renderWithProviders(<DevicesPage />);
    const addButton = await screen.findByText("Add Device");
    await userEvent.click(addButton);

    expect(screen.getByText("Add New Device")).toBeInTheDocument();
    expect(screen.getByText("Create Device")).toBeInTheDocument();
  });

  it("create modal has required form fields", async () => {
    renderWithProviders(<DevicesPage />);
    const addButton = await screen.findByText("Add Device");
    await userEvent.click(addButton);

    expect(screen.getByText("Name *")).toBeInTheDocument();
    expect(screen.getByText("Type *")).toBeInTheDocument();
    expect(screen.getByText("Voltage (V)")).toBeInTheDocument();
    expect(screen.getAllByText("Load").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Load Unit")).toBeInTheDocument();
  });

  it("create button is disabled when name is empty", async () => {
    renderWithProviders(<DevicesPage />);
    const addButton = await screen.findByText("Add Device");
    await userEvent.click(addButton);

    const createBtn = screen.getByText("Create Device");
    expect(createBtn.closest("button")).toBeDisabled();
  });

  it("close create modal on cancel", async () => {
    renderWithProviders(<DevicesPage />);
    const addButton = await screen.findByText("Add Device");
    await userEvent.click(addButton);

    expect(screen.getByText("Add New Device")).toBeInTheDocument();

    const cancelBtn = screen.getByText("Cancel");
    await userEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByText("Add New Device")).not.toBeInTheDocument();
    });
  });

  it("calls createDevice on form submit", async () => {
    mockCreateDevice.mockResolvedValue({
      success: true,
      data: MOCK_DEVICES[0],
    });

    renderWithProviders(<DevicesPage />);
    const addButton = await screen.findByText("Add Device");
    await userEvent.click(addButton);

    // Fill in name
    const nameInput = screen.getByPlaceholderText("e.g., SD-101");
    await userEvent.type(nameInput, "Test-Device");

    // Click Create Device
    const createBtn = screen.getByText("Create Device");
    await userEvent.click(createBtn);

    await waitFor(() => {
      expect(mockCreateDevice).toHaveBeenCalledWith(
        "proj-001",
        expect.objectContaining({
          name: "Test-Device",
          type: "smoke_detector",
          category: "detection",
        }),
      );
    });
  });

  it("shows error message in create modal on failure", async () => {
    mockCreateDevice.mockRejectedValue(new Error("Create failed: invalid data"));

    renderWithProviders(<DevicesPage />);
    const addButton = await screen.findByText("Add Device");
    await userEvent.click(addButton);

    // Fill in name so button is enabled
    const nameInput = screen.getByPlaceholderText("e.g., SD-101");
    await userEvent.type(nameInput, "Test-Device");

    const createBtn = screen.getByText("Create Device");
    await userEvent.click(createBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Create failed: invalid data/),
      ).toBeInTheDocument();
    });
  });

  // ── Edit Modal Tests ──────────────────────────────────────────────────

  it("opens edit modal on Edit button click", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTitle("Edit");
    await userEvent.click(editButtons[0]);

    expect(screen.getByText("Edit: SD-101")).toBeInTheDocument();
    expect(screen.getByText("Save Changes")).toBeInTheDocument();
  });

  it("calls updateDevice on edit form submit", async () => {
    mockUpdateDevice.mockResolvedValue({
      success: true,
      data: MOCK_DEVICES[0],
    });

    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTitle("Edit");
    await userEvent.click(editButtons[0]);

    // Change the name
    const nameInput = screen.getByDisplayValue("SD-101");
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "SD-101-Updated");

    const saveBtn = screen.getByText("Save Changes");
    await userEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockUpdateDevice).toHaveBeenCalledWith(
        "proj-001",
        "dev-001",
        expect.objectContaining({
          name: "SD-101-Updated",
        }),
      );
    });
  });

  it("shows error message in edit modal on failure", async () => {
    mockUpdateDevice.mockRejectedValue(new Error("Update failed: conflict"));

    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
    });

    const editButtons = screen.getAllByTitle("Edit");
    await userEvent.click(editButtons[0]);

    const saveBtn = screen.getByText("Save Changes");
    await userEvent.click(saveBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Update failed: conflict/),
      ).toBeInTheDocument();
    });
  });

  // ── Delete Tests ──────────────────────────────────────────────────────

  it("opens delete confirmation on Delete button click", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle("Delete");
    await userEvent.click(deleteButtons[0]);

    expect(screen.getByText("Delete Device")).toBeInTheDocument();
    // The modal text spans a <p> with a nested <span> for the device name;
    // use findByText with wait to ensure DOM settles after state update
    const confirmation = await screen.findByText(
      /Are you sure you want to delete/, { exact: false }
    );
    expect(confirmation).toBeInTheDocument();
  });

  it("calls deleteDevice on confirm delete", async () => {
    mockDeleteDevice.mockResolvedValue({
      success: true,
      data: null,
    });

    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle("Delete");
    await userEvent.click(deleteButtons[0]);

    const deleteBtn = screen.getByText("Delete");
    await userEvent.click(deleteBtn);

    await waitFor(() => {
      expect(mockDeleteDevice).toHaveBeenCalledWith("proj-001", "dev-001");
    });
  });

  it("close delete modal on cancel", async () => {
    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle("Delete");
    await userEvent.click(deleteButtons[0]);

    expect(screen.getByText("Delete Device")).toBeInTheDocument();

    const cancelBtn = screen.getByText("Cancel");
    await userEvent.click(cancelBtn);

    await waitFor(() => {
      expect(screen.queryByText("Delete Device")).not.toBeInTheDocument();
    });
  });

  it("shows delete error message on failure", async () => {
    mockDeleteDevice.mockRejectedValue(new Error("Server error"));

    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("SD-101")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByTitle("Delete");
    await userEvent.click(deleteButtons[0]);

    const deleteBtn = screen.getByText("Delete");
    await userEvent.click(deleteBtn);

    await waitFor(() => {
      expect(screen.getByText(/Server error/)).toBeInTheDocument();
    });
  });

  // ── Fallback to Global Endpoint ───────────────────────────────────────

  it("falls back to global /devices endpoint when project-scoped fails", async () => {
    // digitalTwinApi returns failure
    mockGetDevices.mockResolvedValue({
      success: false,
      error: "Failed",
    });
    // Fetch fallback succeeds with paginated data
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/projects")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              data: { data: [MOCK_PROJECT], total: 1 },
            }),
        });
      }
      if (url.includes("/devices")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(PAGINATED_RESPONSE),
        });
      }
      return Promise.resolve({ ok: false });
    });

    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("3 fire alarm devices")).toBeInTheDocument();
    });
  });

  // ── Pagination ────────────────────────────────────────────────────────

  it("shows pagination controls when total pages > 1", async () => {
    const manyDevices = Array.from({ length: 25 }, (_, i) => ({
      ...MOCK_DEVICES[0],
      id: `dev-${String(i + 1).padStart(3, "0")}`,
      name: `DEV-${String(i + 1).padStart(3, "0")}`,
    }));

    mockGetDevices.mockResolvedValue({
      success: true,
      data: {
        data: manyDevices.slice(0, 20),
        total: 25,
        page: 1,
        limit: 20,
        totalPages: 2,
      },
    });

    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      expect(screen.getByText("Previous")).toBeInTheDocument();
      expect(screen.getByText("Next")).toBeInTheDocument();
      expect(screen.getByText(/Page 1 of 2/)).toBeInTheDocument();
    });
  });

  it("previous button is disabled on first page", async () => {
    const manyDevices = Array.from({ length: 25 }, (_, i) => ({
      ...MOCK_DEVICES[0],
      id: `dev-${String(i + 1).padStart(3, "0")}`,
      name: `DEV-${String(i + 1).padStart(3, "0")}`,
    }));

    mockGetDevices.mockResolvedValue({
      success: true,
      data: {
        data: manyDevices.slice(0, 20),
        total: 25,
        page: 1,
        limit: 20,
        totalPages: 2,
      },
    });

    renderWithProviders(<DevicesPage />);
    await waitFor(() => {
      const prevBtn = screen.getByText("Previous");
      expect(prevBtn.closest("button")).toBeDisabled();
    });
  });
});
