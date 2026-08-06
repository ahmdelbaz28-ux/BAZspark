/**
 * APSPage.test.tsx — Unit tests for Autodesk Platform Services page.
 *
 * Tests: rendering title, form fields, submit button disabled state,
 * status panel, success/error states, mutation calls.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

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

import { APSPage } from "../APSPage";

// Mock the fullApi module so we control apsApi directly
// without going through the real apiCall/fetchWithRetry/CSRF pipeline.
const mockApsProcess = vi.fn();
const mockApsGetStatus = vi.fn();
vi.mock("@/services/fullApi", () => ({
  apsApi: {
    process: (...args: unknown[]) => mockApsProcess(...args),
    getStatus: (...args: unknown[]) => mockApsGetStatus(...args),
  },
}));

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderPage() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <APSPage />
    </QueryClientProvider>
  );
}

function findSubmitButton(): HTMLElement | undefined {
  const buttons = screen.getAllByRole("button");
  return buttons.find(
    (btn) => btn.textContent?.includes("Submit WorkItem")
  );
}

describe("APSPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("Autodesk Platform Services")).toBeInTheDocument();
  });

  it("renders form fields", () => {
    renderPage();
    // "Submit WorkItem" appears as both an h3 heading and button text
    const submitHeadings = screen.getAllByText("Submit WorkItem");
    expect(submitHeadings.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Bucket Key")).toBeInTheDocument();
    expect(screen.getByText("Object Key *")).toBeInTheDocument();
    expect(screen.getByText("Activity ID *")).toBeInTheDocument();
    expect(screen.getByText("Parameters (JSON)")).toBeInTheDocument();
  });

  it("shows default bucket key value", () => {
    renderPage();
    const bucketInput = screen.getByDisplayValue("bazspark_bucket");
    expect(bucketInput).toBeInTheDocument();
  });

  it("submit button is disabled when required fields are empty", () => {
    renderPage();
    const submitBtn = findSubmitButton();
    expect(submitBtn).toBeDefined();
    expect(submitBtn).toBeDisabled();
  });

  it("submit button becomes enabled when fields are filled", async () => {
    renderPage();
    const objectInput = screen.getByPlaceholderText("filename.dwg");
    const activityInput = screen.getByPlaceholderText("your.activity.id");

    await userEvent.type(objectInput, "test.dwg");
    await userEvent.type(activityInput, "test.activity");

    const submitBtn = findSubmitButton();
    expect(submitBtn).toBeDefined();
    expect(submitBtn).not.toBeDisabled();
  });

  it("shows submitting state while mutation is pending", async () => {
    mockApsProcess.mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    renderPage();
    const objectInput = screen.getByPlaceholderText("filename.dwg");
    const activityInput = screen.getByPlaceholderText("your.activity.id");
    await userEvent.type(objectInput, "test.dwg");
    await userEvent.type(activityInput, "test.activity");

    const submitBtn = findSubmitButton();
    await userEvent.click(submitBtn!);

    expect(screen.getByText("Submitting...")).toBeInTheDocument();
  });

  it("shows success message after submission", async () => {
    mockApsProcess.mockResolvedValue({
      work_item_id: "wi-123",
      input_urn: "urn:test",
      output_urn: "urn:output",
      simulation_mode: false,
    });

    renderPage();
    const objectInput = screen.getByPlaceholderText("filename.dwg");
    const activityInput = screen.getByPlaceholderText("your.activity.id");
    await userEvent.type(objectInput, "test.dwg");
    await userEvent.type(activityInput, "test.activity");

    const submitBtn = findSubmitButton();
    await userEvent.click(submitBtn!);

    await waitFor(() => {
      expect(
        screen.getByText("WorkItem submitted successfully")
      ).toBeInTheDocument();
      expect(screen.getByText("ID: wi-123")).toBeInTheDocument();
      expect(screen.getByText("Check status →")).toBeInTheDocument();
    });
  });

  it("shows error message on submit failure", async () => {
    mockApsProcess.mockRejectedValue(new Error("Authentication failed"));

    renderPage();
    const objectInput = screen.getByPlaceholderText("filename.dwg");
    const activityInput = screen.getByPlaceholderText("your.activity.id");
    await userEvent.type(objectInput, "test.dwg");
    await userEvent.type(activityInput, "test.activity");

    const submitBtn = findSubmitButton();
    await userEvent.click(submitBtn!);

    await waitFor(() => {
      expect(
        screen.getByText("Authentication failed")
      ).toBeInTheDocument();
    });
  });

  it("shows status panel with no job selected message", () => {
    renderPage();
    expect(screen.getByText("Job Status")).toBeInTheDocument();
    expect(screen.getByText("No job selected")).toBeInTheDocument();
  });

  it("shows job ID in status panel after setting jobId", async () => {
    mockApsProcess.mockResolvedValue({
      work_item_id: "wi-456",
      input_urn: "urn:test",
      output_urn: "urn:output",
      simulation_mode: false,
    });
    mockApsGetStatus.mockResolvedValue({
      success: true,
      status: "completed",
    });

    renderPage();
    const objectInput = screen.getByPlaceholderText("filename.dwg");
    const activityInput = screen.getByPlaceholderText("your.activity.id");
    await userEvent.type(objectInput, "test.dwg");
    await userEvent.type(activityInput, "test.activity");

    const submitBtn = findSubmitButton();
    await userEvent.click(submitBtn!);

    await waitFor(() => {
      expect(screen.getByText("Check status →")).toBeInTheDocument();
    });

    const checkBtn = screen.getByText("Check status →");
    await userEvent.click(checkBtn);

    expect(screen.getByText("wi-456")).toBeInTheDocument();
    expect(screen.getByText("Refresh Status")).toBeInTheDocument();
  });

  it("shows info section at the bottom", () => {
    renderPage();
    expect(
      screen.getByText(/APS \(Autodesk Platform Services\)/)
    ).toBeInTheDocument();
  });
});
