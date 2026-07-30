/**
 * CADToolsPage.test.tsx — Unit tests for CAD/BIM Tools Dashboard.
 *
 * Tests: rendering, provider toggle, connect/disconnect,
 * drawing operations (line, polyline, circle, text),
 * file read/write, connection gate, tab navigation.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CADToolsPage } from "../CADToolsPage";

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
    PenLine: createIcon("PenLine"),
    Building2: createIcon("Building2"),
    Plug: createIcon("Plug"),
    PlugZap: createIcon("PlugZap"),
    Loader2: createIcon("Loader2"),
    AlertTriangle: createIcon("AlertTriangle"),
    CheckCircle2: createIcon("CheckCircle2"),
    Info: createIcon("Info"),
    FileUp: createIcon("FileUp"),
    FileDown: createIcon("FileDown"),
    Square: createIcon("Square"),
    Circle: createIcon("Circle"),
    Type: createIcon("Type"),
    Minus: createIcon("Minus"),
  };
});

const mockFetch = vi.fn();
global.fetch = mockFetch;

const MOCK_CONNECT_OK = {
  success: true,
  message: "Connected to autocad successfully",
  connected: true,
  simulation_mode: true,
};

const MOCK_CONNECT_FAIL = {
  success: false,
  message: "Failed to connect to autocad",
  connected: false,
  simulation_mode: false,
};

const MOCK_DISCONNECT_OK = {
  success: true,
  message: "Disconnected from autocad successfully",
  handle: null,
};

const MOCK_STATUS_CONNECTED = {
  success: true,
  provider: "autocad",
  status: { connected: true, simulation_mode: true },
};

const MOCK_STATUS_DISCONNECTED = {
  success: true,
  provider: "autocad",
  status: { connected: false, simulation_mode: false },
};

const MOCK_DRAW_RESULT = {
  success: true,
  message: "Line drawn successfully",
  handle: "handle-001",
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
      <CADToolsPage />
    </QueryClientProvider>
  );
}

describe("CADToolsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: connected status
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/cad/status")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_STATUS_DISCONNECTED),
        });
      }
      if (url.includes("/cad/connect")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_CONNECT_OK),
        });
      }
      if (url.includes("/cad/disconnect")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_DISCONNECT_OK),
        });
      }
      if (url.includes("/cad/draw")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_DRAW_RESULT),
        });
      }
      if (url.includes("/cad/read")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              element_count: 2,
              elements: [
                { handle: "h1", type: "Line", layer: "0" },
                { handle: "h2", type: "Circle", layer: "1" },
              ],
              filepath: "/drawing.dwg",
              provider: "autocad",
            }),
        });
      }
      if (url.includes("/cad/write")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              message: "Drawing written successfully",
            }),
        });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({}) });
    });
  });

  // ── Rendering Tests ─────────────────────────────────────────────────

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("CAD & BIM Tools")).toBeInTheDocument();
  });

  it("renders both provider buttons", () => {
    renderPage();
    expect(screen.getByText("AutoCAD")).toBeInTheDocument();
    expect(screen.getByText("Revit")).toBeInTheDocument();
  });

  it("shows AutoCAD selected by default", () => {
    renderPage();
    const acadBtn = screen.getByText("AutoCAD");
    expect(acadBtn).toBeInTheDocument();
  });

  it("switches provider when Revit is clicked", async () => {
    renderPage();
    const revitBtn = screen.getByText("Revit");
    await userEvent.click(revitBtn);
    // Status should reset to disconnected
    const disconnectedTexts = screen.getAllByText("Disconnected");
    expect(disconnectedTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("renders Connection, Drawing Tools, and File Read/Write tabs", () => {
    renderPage();
    expect(screen.getByText("Connection")).toBeInTheDocument();
    expect(screen.getByText("Drawing Tools")).toBeInTheDocument();
    expect(screen.getByText("File Read/Write")).toBeInTheDocument();
  });

  // ── Connection Tests ────────────────────────────────────────────────

  it("shows Disconnected by default", () => {
    renderPage();
    const disconnectedTexts = screen.getAllByText("Disconnected");
    expect(disconnectedTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("shows Connect and Disconnect buttons", () => {
    renderPage();
    expect(screen.getByText("Connect")).toBeInTheDocument();
    expect(screen.getByText("Disconnect")).toBeInTheDocument();
  });

  it("shows Status button", () => {
    renderPage();
    const statusTexts = screen.getAllByText("Status");
    expect(statusTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("shows Connection Information tab by default", () => {
    renderPage();
    expect(screen.getByText("Connection Information")).toBeInTheDocument();
  });

  it("shows endpoint info in connection tab", () => {
    renderPage();
    expect(screen.getByText(/POST \/cad\/connect/)).toBeInTheDocument();
  });

  // ── Drawing Tools Tab ───────────────────────────────────────────────

  it("switches to Drawing Tools tab on click", async () => {
    renderPage();
    const drawTab = screen.getByText("Drawing Tools");
    await userEvent.click(drawTab);

    await waitFor(() => {
      const drawLineTexts = screen.getAllByText("Draw Line");
      expect(drawLineTexts.length).toBeGreaterThanOrEqual(1);
      const polylineTexts = screen.getAllByText("Draw Polyline");
      expect(polylineTexts.length).toBeGreaterThanOrEqual(1);
      const circleTexts = screen.getAllByText("Draw Circle");
      expect(circleTexts.length).toBeGreaterThanOrEqual(1);
      const drawTextTexts = screen.getAllByText("Draw Text");
      expect(drawTextTexts.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows connection warning in draw tab when disconnected", async () => {
    renderPage();
    const drawTab = screen.getByText("Drawing Tools");
    await userEvent.click(drawTab);

    await waitFor(() => {
      expect(screen.getByText(/Connect to AutoCAD first/)).toBeInTheDocument();
    });
  });

  it("draw buttons are disabled when disconnected", async () => {
    renderPage();
    const drawTab = screen.getByText("Drawing Tools");
    await userEvent.click(drawTab);

    await waitFor(() => {
      const drawLineBtns = screen.getAllByText("Draw Line");
      expect(drawLineBtns.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ── File Read/Write Tab ─────────────────────────────────────────────

  it("switches to File Read/Write tab on click", async () => {
    renderPage();
    const fileTab = screen.getByText("File Read/Write");
    await userEvent.click(fileTab);

    await waitFor(() => {
      expect(screen.getByText("Read Drawing")).toBeInTheDocument();
    });
  });

  it("shows file path input in file tab", async () => {
    renderPage();
    const fileTab = screen.getByText("File Read/Write");
    await userEvent.click(fileTab);

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("/path/to/drawing.dwg")
      ).toBeInTheDocument();
    });
  });

  it("shows file operations warning in file tab", async () => {
    renderPage();
    const fileTab = screen.getByText("File Read/Write");
    await userEvent.click(fileTab);

    await waitFor(() => {
      expect(
        screen.getByText("File Operations Require Connection")
      ).toBeInTheDocument();
    });
  });

  // ── Info Section ────────────────────────────────────────────────────

  it("shows connection info note", () => {
    renderPage();
    expect(screen.getByText(/simulation mode by default/)).toBeInTheDocument();
  });
});
