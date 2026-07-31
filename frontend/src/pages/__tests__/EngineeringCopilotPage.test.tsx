/**
 * EngineeringCopilotPage.test.tsx — Unit tests for Engineering Copilot chat.
 *
 * Tests: rendering title, welcome message, input field, send button,
 * message display, clear chat, loading state, error state.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EngineeringCopilotPage } from "../EngineeringCopilotPage";

// JSDOM doesn't implement scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

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
    Bot: createIcon("Bot"),
    Send: createIcon("Send"),
    Loader2: createIcon("Loader2"),
    User: createIcon("User"),
    AlertTriangle: createIcon("AlertTriangle"),
    Trash2: createIcon("Trash2"),
    List: createIcon("List"),
    FileText: createIcon("FileText"),
    ArrowRightLeft: createIcon("ArrowRightLeft"),
    ShieldCheck: createIcon("ShieldCheck"),
    FileOutput: createIcon("FileOutput"),
    Info: createIcon("Info"),
    PlusCircle: createIcon("PlusCircle"),
    Heart: createIcon("Heart"),
  };
});

const mockFetch = vi.fn();
global.fetch = mockFetch;

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderPage() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <EngineeringCopilotPage />
    </QueryClientProvider>
  );
}

function findSendButton(): HTMLElement | undefined {
  const buttons = screen.getAllByRole("button");
  return buttons.find(
    (btn) => btn.querySelector('[data-testid="icon-send"]')
  );
}

describe("EngineeringCopilotPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("Engineering Copilot")).toBeInTheDocument();
  });

  it("shows welcome message on load", () => {
    renderPage();
    expect(
      screen.getByText(/Hello! I'm the Engineering Copilot/)
    ).toBeInTheDocument();
  });

  it("renders input field with placeholder", () => {
    renderPage();
    expect(
      screen.getByPlaceholderText(
        "Ask about NFPA 72, NEC, fire safety design..."
      )
    ).toBeInTheDocument();
  });

  it("send button is disabled when input is empty", () => {
    renderPage();
    const sendButton = findSendButton();
    expect(sendButton).toBeDefined();
    expect(sendButton).toBeDisabled();
  });

  it("send button is enabled when text is entered", async () => {
    renderPage();
    const input = screen.getByPlaceholderText(
      "Ask about NFPA 72, NEC, fire safety design..."
    );
    await userEvent.type(input, "What is NFPA 72?");

    const sendButton = findSendButton();
    expect(sendButton).toBeDefined();
    expect(sendButton).not.toBeDisabled();
  });

  it("adds user message on send", async () => {
    mockFetch.mockImplementation(
      () => new Promise(() => {}) // Keep pending
    );

    renderPage();
    const input = screen.getByPlaceholderText(
      "Ask about NFPA 72, NEC, fire safety design..."
    );
    await userEvent.type(input, "What is NFPA 72?");

    const sendButton = findSendButton();
    await userEvent.click(sendButton!);

    expect(screen.getByText("What is NFPA 72?")).toBeInTheDocument();
  });

  it("shows thinking indicator while waiting for response", async () => {
    mockFetch.mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    renderPage();
    const input = screen.getByPlaceholderText(
      "Ask about NFPA 72, NEC, fire safety design..."
    );
    await userEvent.type(input, "What is NFPA 72?");

    const sendButton = findSendButton();
    await userEvent.click(sendButton!);

    expect(screen.getByText("Thinking...")).toBeInTheDocument();
  });

  it("shows assistant response after successful API call", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          response:
            "NFPA 72 is the National Fire Alarm and Signaling Code.",
          model: "gpt-4",
        }),
    });

    renderPage();
    const input = screen.getByPlaceholderText(
      "Ask about NFPA 72, NEC, fire safety design..."
    );
    await userEvent.type(input, "What is NFPA 72?");

    const sendButton = findSendButton();
    await userEvent.click(sendButton!);

    await waitFor(() => {
      expect(
        screen.getByText("NFPA 72 is the National Fire Alarm and Signaling Code.")
      ).toBeInTheDocument();
    });
  });

  it("shows error message on API failure", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Service unavailable" }),
    });

    renderPage();
    const input = screen.getByPlaceholderText(
      "Ask about NFPA 72, NEC, fire safety design..."
    );
    await userEvent.type(input, "What is NFPA 72?");

    const sendButton = findSendButton();
    await userEvent.click(sendButton!);

    await waitFor(() => {
      expect(
        screen.getByText("Service unavailable")
      ).toBeInTheDocument();
    });
  });

  it("clear chat button resets to welcome message", async () => {
    renderPage();

    // Add a user message first
    mockFetch.mockImplementation(
      () => new Promise(() => {})
    );
    const input = screen.getByPlaceholderText(
      "Ask about NFPA 72, NEC, fire safety design..."
    );
    await userEvent.type(input, "Test message");

    const sendButton = findSendButton();
    await userEvent.click(sendButton!);

    expect(screen.getByText("Test message")).toBeInTheDocument();

    // Clear chat
    const clearBtn = screen.getByText("Clear Chat");
    await userEvent.click(clearBtn);

    expect(screen.queryByText("Test message")).not.toBeInTheDocument();
    expect(
      screen.getByText(/Hello! I'm the Engineering Copilot/)
    ).toBeInTheDocument();
  });

  it("shows disclaimer text below input", () => {
    renderPage();
    expect(
      screen.getByText(/Responses are AI-generated/)
    ).toBeInTheDocument();
  });
});
