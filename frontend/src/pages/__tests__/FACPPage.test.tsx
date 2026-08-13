/**
 * FACPPage.test.tsx — Unit tests for Fire Alarm Control Panel Selection page.
 *
 * Tests: rendering form inputs, panel selection, panel listing,
 * toast notifications, result display.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FACPPage } from "../FACPPage";

vi.mock("react-i18next", () => ({
	useTranslation: () => ({
		t: (key: string) => key,
		i18n: { language: "en", changeLanguage: vi.fn() },
	}),
	initReactI18next: { type: "3rdParty", init: vi.fn() },
}));

vi.mock("lucide-react", async (importOriginal) => {
	const actual = (await importOriginal()) as Record<string, unknown>;
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
		if (
			typeof value === "function" ||
			(typeof value === "object" &&
				value !== null &&
				"$$typeof" in (value as Record<string, unknown>))
		) {
			mocked[key] = createIcon(key);
		} else {
			mocked[key] = value;
		}
	}
	return mocked;
});

// Mock shadcn UI components
vi.mock("@/components/ui/badge", () => ({
	Badge: ({
		children,
		...props
	}: {
		children: React.ReactNode;
		variant?: string;
		className?: string;
	}) => (
		<span data-testid="badge" {...props}>
			{children}
		</span>
	),
}));

vi.mock("@/components/ui/button", () => ({
	Button: ({
		children,
		onClick,
		disabled,
		...props
	}: {
		children: React.ReactNode;
		onClick?: () => void;
		disabled?: boolean;
		variant?: string;
	}) => (
		<button type="button" onClick={onClick} disabled={disabled} {...props}>
			{children}
		</button>
	),
}));

vi.mock("@/components/ui/card", () => ({
	Card: ({ children }: { children: React.ReactNode }) => (
		<div data-testid="card">{children}</div>
	),
	CardContent: ({ children }: { children: React.ReactNode }) => (
		<div data-testid="card-content">{children}</div>
	),
	CardDescription: ({ children }: { children: React.ReactNode }) => (
		<div data-testid="card-desc">{children}</div>
	),
	CardHeader: ({ children }: { children: React.ReactNode }) => (
		<div data-testid="card-header">{children}</div>
	),
	CardTitle: ({ children }: { children: React.ReactNode }) => (
		<div data-testid="card-title">{children}</div>
	),
}));

vi.mock("@/components/ui/input", () => ({
	Input: (_props: Record<string, unknown>) => (
		<input data-testid="input" {..._props} />
	),
}));

vi.mock("@/components/ui/label", () => ({
	Label: ({
		children,
		htmlFor,
		...props
	}: {
		children: React.ReactNode;
		htmlFor?: string;
		className?: string;
	}) => (
		<label htmlFor={htmlFor} {...props}>
			{children}
		</label>
	),
}));

vi.mock("@/components/ui/checkbox", () => ({
	Checkbox: ({
		id,
		checked,
		onCheckedChange,
	}: {
		id: string;
		checked: boolean;
		onCheckedChange?: (v: boolean | string) => void;
	}) => (
		<input
			type="checkbox"
			id={id}
			checked={checked}
			onChange={(e) => onCheckedChange?.(e.target.checked)}
			data-testid="checkbox"
		/>
	),
}));

vi.mock("@/components/ui/select", () => ({
	Select: ({
		children,
		value,
		onValueChange,
	}: {
		children: React.ReactNode;
		value: string;
		onValueChange: (v: string) => void;
	}) => (
		<select
			value={value}
			onChange={(e) => onValueChange(e.target.value)}
			data-testid="select"
		>
			{children}
		</select>
	),
	SelectContent: ({ children }: { children: React.ReactNode }) => (
		<>{children}</>
	),
	SelectItem: ({
		children,
		value,
	}: {
		children: React.ReactNode;
		value: string;
	}) => <option value={value}>{children}</option>,
	SelectTrigger: ({ children }: { children: React.ReactNode }) => (
		<>{children}</>
	),
	SelectValue: () => <></>,
}));

// Mock facpApi service
const mockFacpSelect = vi.fn();
const mockFacpGetPanels = vi.fn();

vi.mock("@/services/fullApi", () => ({
	facpApi: {
		select: (...args: unknown[]) => mockFacpSelect(...args),
		getPanels: (...args: unknown[]) => mockFacpGetPanels(...args),
	},
}));

// Mock toast
const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
	useToast: () => ({ toast: mockToast }),
}));

const MOCK_SELECTION = {
	recommended_model: "FACP-5000",
	manufacturer: "Notifier",
	capacity_utilization: 0.65,
	nac_utilization: 0.5,
	battery_size_ah: 24,
	battery_derating_details: {
		method: "NFPA 72 Table B.1",
		temperature_derating: 0.95,
		aging_derating: 0.8,
		combined_safety_factor: 1.25,
	},
};

const MOCK_PANELS = [
	{
		model: "FACP-2000",
		manufacturer: "Notifier",
		device_capacity: 128,
		nac_capacity: 4,
	},
	{
		model: "FACP-5000",
		manufacturer: "Notifier",
		device_capacity: 256,
		nac_capacity: 8,
	},
	{
		model: "FACP-9000",
		manufacturer: "Honeywell",
		device_capacity: 512,
		nac_capacity: 16,
	},
];

function renderPage() {
	return render(<FACPPage />);
}

describe("FACPPage", () => {
	beforeEach(() => {
		vi.clearAllMocks();
		mockFacpSelect.mockResolvedValue(MOCK_SELECTION);
		mockFacpGetPanels.mockResolvedValue({ panels: MOCK_PANELS });
	});

	it("renders the page title", () => {
		renderPage();
		expect(screen.getByText("FACP Panel Selection")).toBeInTheDocument();
	});

	it("renders project requirements card", () => {
		renderPage();
		expect(screen.getByText("Project Requirements")).toBeInTheDocument();
	});

	it("renders form inputs with default values", () => {
		renderPage();
		expect(screen.getByDisplayValue("150")).toBeInTheDocument();
		expect(screen.getByDisplayValue("4")).toBeInTheDocument();
		expect(screen.getByDisplayValue("3000")).toBeInTheDocument();
		expect(screen.getByDisplayValue("3")).toBeInTheDocument();
	});

	it("renders jurisdiction select with UL default", () => {
		renderPage();
		const select = screen.getByTestId("select");
		expect(select).toHaveValue("UL");
	});

	it("renders checkbox options", () => {
		renderPage();
		const checkboxes = screen.getAllByTestId("checkbox");
		expect(checkboxes.length).toBe(3);
	});

	it("shows Select Panel and List All Panels buttons", () => {
		renderPage();
		expect(screen.getByText("Select Panel")).toBeInTheDocument();
		expect(screen.getByText("List All Panels")).toBeInTheDocument();
	});

	it("calls facpApi.select on Select Panel click", async () => {
		renderPage();
		const btn = screen.getByText("Select Panel");
		await userEvent.click(btn);

		await waitFor(() => {
			expect(mockFacpSelect).toHaveBeenCalledWith({
				device_count: 150,
				nac_circuit_count: 4,
				building_size_m2: 3000,
				building_floors: 3,
				requires_network: false,
				requires_voice: false,
				requires_releasing: false,
				jurisdiction: "UL",
				min_temperature_c: 0,
			});
		});
	});

	it("displays recommended panel after selection", async () => {
		renderPage();
		const btn = screen.getByText("Select Panel");
		await userEvent.click(btn);

		await waitFor(() => {
			expect(screen.getByText("FACP-5000")).toBeInTheDocument();
		});
	});

	it("displays manufacturer after selection", async () => {
		renderPage();
		const btn = screen.getByText("Select Panel");
		await userEvent.click(btn);

		await waitFor(() => {
			expect(screen.getByText("Notifier")).toBeInTheDocument();
		});
	});

	it("displays battery details after selection", async () => {
		renderPage();
		const btn = screen.getByText("Select Panel");
		await userEvent.click(btn);

		await waitFor(() => {
			expect(screen.getByText(/24 Ah/)).toBeInTheDocument();
			expect(screen.getByText(/NFPA 72 Table B.1/)).toBeInTheDocument();
		});
	});

	it("shows toast on selection failure", async () => {
		mockFacpSelect.mockRejectedValue(new Error("API unavailable"));

		renderPage();
		const btn = screen.getByText("Select Panel");
		await userEvent.click(btn);

		await waitFor(() => {
			expect(mockToast).toHaveBeenCalledWith(
				expect.objectContaining({
					title: "FACP Selection Failed",
					variant: "destructive",
				}),
			);
		});
	});

	it("calls facpApi.getPanels on List All Panels click", async () => {
		renderPage();
		const btn = screen.getByText("List All Panels");
		await userEvent.click(btn);

		await waitFor(() => {
			expect(mockFacpGetPanels).toHaveBeenCalled();
		});
	});

	it("displays panel database after listing", async () => {
		renderPage();
		const btn = screen.getByText("List All Panels");
		await userEvent.click(btn);

		await waitFor(() => {
			expect(screen.getByText("Panel Database (3)")).toBeInTheDocument();
			expect(screen.getByText("FACP-2000")).toBeInTheDocument();
			expect(screen.getByText("FACP-5000")).toBeInTheDocument();
			expect(screen.getByText("FACP-9000")).toBeInTheDocument();
		});
	});

	it("shows toast on listing failure", async () => {
		mockFacpGetPanels.mockRejectedValue(new Error("Network error"));

		renderPage();
		const btn = screen.getByText("List All Panels");
		await userEvent.click(btn);

		await waitFor(() => {
			expect(mockToast).toHaveBeenCalledWith(
				expect.objectContaining({
					title: "Failed to load panels",
					variant: "destructive",
				}),
			);
		});
	});
});
