/**
 * EngineeringCopilotPage.test.tsx — Unit tests for Engineering Copilot chat.
 *
 * Tests: rendering title, welcome message, input field, send button,
 * message display, clear chat, loading state, error state.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// JSDOM doesn't implement scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn();

vi.mock("react-i18next", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en", changeLanguage: vi.fn() },
  }),
  initReactI18next: { type: "3rdParty", init: vi.fn() },
}));

vi.mock("lucide-react", async (importOriginal) => {
	const actual = await importOriginal() as Record<string, unknown>;
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

import { EngineeringCopilotPage } from "../EngineeringCopilotPage";

// Mock the fullApi module so we control the chat function directly
// without going through the real apiCall/fetchWithRetry/CSRF pipeline.
const mockChat = vi.fn();
vi.mock("@/services/fullApi", () => ({
  copilotApi: {
    chat: (...args: unknown[]) => mockChat(...args),
    getCapabilities: vi.fn(() => Promise.resolve({})),
    getHealth: vi.fn(() => Promise.resolve({})),
    createEntity: vi.fn(() => Promise.resolve({})),
  },
  copilotExtendedApi: {
    translateModel: vi.fn(() => Promise.resolve({})),
    validateModel: vi.fn(() => Promise.resolve({})),
    generateReports: vi.fn(() => Promise.resolve({})),
  },
  llmExtendedApi: {
    getModels: vi.fn(() => Promise.resolve({})),
    complianceNarrative: vi.fn(() => Promise.resolve({})),
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
      <EngineeringCopilotPage />
    </QueryClientProvider>
  );
}

function findSendButton(): HTMLElement | undefined {
  return screen.queryByRole("button", { name: "Send" }) ?? undefined;
}

describe("EngineeringCopilotPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: keep the chat pending so send button tests work
    mockChat.mockImplementation(() => new Promise(() => {}));
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
    mockChat.mockResolvedValue({
      response: "NFPA 72 is the National Fire Alarm and Signaling Code.",
      model: "gpt-4",
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
    // When the API call fails, the mutation's error is an Error instance.
    // The component displays chatMutation.error.message if it's an Error,
    // otherwise "Failed to get response".
    mockChat.mockRejectedValue(new Error("Service unavailable"));

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
