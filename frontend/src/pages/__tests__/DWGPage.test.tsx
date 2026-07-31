/**
 * DWGPage.test.tsx — Unit tests for DWG/DXF file upload & parser page.
 *
 * Tests: rendering title, upload zone, drag-drop, error states,
 * parse results display (room count, time, format, status),
 * warnings/errors display, reset form.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DWGPage } from "../DWGPage";

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

function createMockFile(name: string, ext: string, size = 1000): File {
  const content = new ArrayBuffer(size);
  return new File([content], name, { type: "application/octet-stream" });
}

function renderPage() {
  return render(<DWGPage />);
}

describe("DWGPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("DWG / DXF Parser")).toBeInTheDocument();
  });

  it("renders upload zone with drop message", () => {
    renderPage();
    expect(
      screen.getByText(/Drop a DWG or DXF file here/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Max file size: 50 MB/)).toBeInTheDocument();
  });

  it("shows error for unsupported file type", async () => {
    renderPage();
    const fileInputEl = document.querySelector('input[type="file"]')!;
    
    // Simulate file selection with a .pdf file
    const badFile = createMockFile("test.pdf", ".pdf");
    Object.defineProperty(fileInputEl, "files", { value: [badFile] });
    fileInputEl.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(
        screen.getByText("Only .dwg and .dxf files are supported")
      ).toBeInTheDocument();
    });
  });

  it("shows error for file too large", async () => {
    renderPage();
    const largeFile = createMockFile("test.dwg", ".dwg", 60 * 1024 * 1024);
    const fileInputEl = document.querySelector('input[type="file"]')!;
    Object.defineProperty(fileInputEl, "files", { value: [largeFile] });
    fileInputEl.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(
        screen.getByText("File too large (max 50 MB)")
      ).toBeInTheDocument();
    });
  });

  it("shows uploading state while parsing", async () => {
    mockFetch.mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    renderPage();
    const file = createMockFile("floorplan.dwg", ".dwg");
    const fileInputEl = document.querySelector('input[type="file"]')!;
    Object.defineProperty(fileInputEl, "files", { value: [file] });
    fileInputEl.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(screen.getByText(/Parsing floorplan.dwg/)).toBeInTheDocument();
    });
  });

  it("displays parse results on success", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          source: "building_a.dwg",
          room_count: 24,
          conversion_time_s: 3.45,
          errors: [],
          warnings: [],
        }),
    });

    renderPage();
    const file = createMockFile("building_a.dwg", ".dwg");
    const fileInputEl = document.querySelector('input[type="file"]')!;
    Object.defineProperty(fileInputEl, "files", { value: [file] });
    fileInputEl.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(
        screen.getByText("File parsed successfully")
      ).toBeInTheDocument();
      expect(screen.getByText("DWG")).toBeInTheDocument();
      expect(screen.getByText("24")).toBeInTheDocument();
      expect(screen.getByText("3.45s")).toBeInTheDocument();
      expect(screen.getByText("OK")).toBeInTheDocument();
    });
  });

  it("displays warnings when present", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: true,
          source: "test.dwg",
          room_count: 10,
          conversion_time_s: 1.2,
          errors: [],
          warnings: ["Layer '0' has no geometry", "Missing xref: furniture.dwg"],
        }),
    });

    renderPage();
    const file = createMockFile("test.dwg", ".dwg");
    const fileInputEl = document.querySelector('input[type="file"]')!;
    Object.defineProperty(fileInputEl, "files", { value: [file] });
    fileInputEl.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(screen.getByText("Warnings (2)")).toBeInTheDocument();
      expect(
        screen.getByText("Layer '0' has no geometry")
      ).toBeInTheDocument();
    });
  });

  it("displays errors when present", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          success: false,
          source: "broken.dxf",
          room_count: 0,
          conversion_time_s: 0.5,
          errors: ["Unsupported DXF version: AC1032"],
          warnings: [],
        }),
    });

    renderPage();
    const file = createMockFile("broken.dxf", ".dxf");
    const fileInputEl = document.querySelector('input[type="file"]')!;
    Object.defineProperty(fileInputEl, "files", { value: [file] });
    fileInputEl.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(screen.getByText("Errors (1)")).toBeInTheDocument();
      expect(
        screen.getByText("Unsupported DXF version: AC1032")
      ).toBeInTheDocument();
    });
  });

  it("shows error banner on API error", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 422,
      json: () =>
        Promise.resolve({
          detail: { error: "Empty file uploaded" },
        }),
    });

    renderPage();
    const file = createMockFile("empty.dwg", ".dwg");
    const fileInputEl = document.querySelector('input[type="file"]')!;
    Object.defineProperty(fileInputEl, "files", { value: [file] });
    fileInputEl.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(screen.getByText("Parse Error")).toBeInTheDocument();
      expect(screen.getByText("Empty file uploaded")).toBeInTheDocument();
    });
  });

  it("resets form when X button is clicked on error", async () => {
    renderPage();
    
    // First trigger an error
    const badFile = createMockFile("test.pdf", ".pdf");
    const fileInputEl = document.querySelector('input[type="file"]')!;
    Object.defineProperty(fileInputEl, "files", { value: [badFile] });
    fileInputEl.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() => {
      expect(
        screen.getByText("Only .dwg and .dxf files are supported")
      ).toBeInTheDocument();
    });

    // Click the X button to dismiss
    const xButtons = screen.getAllByRole("button");
    const closeBtn = xButtons.find((btn) =>
      btn.querySelector('[data-testid="icon-x"]')
    );
    if (closeBtn) await userEvent.click(closeBtn);

    await waitFor(() => {
      expect(
        screen.queryByText("Only .dwg and .dxf files are supported")
      ).not.toBeInTheDocument();
    });
  });

  it("shows info section at the bottom", () => {
    renderPage();
    expect(
      screen.getByText(/The DWG\/DXF parser extracts room layouts/)
    ).toBeInTheDocument();
  });
});
