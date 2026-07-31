/**
 * NotFoundPage.test.tsx — Unit tests for the 404 page (V193 R13).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";
import { NotFoundPage } from "../NotFoundPage";

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

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router", async () => {
        const actual = await vi.importActual<typeof import("react-router")>("react-router");
        return {
                ...actual,
                useNavigate: () => mockNavigate,
        };
});

describe("NotFoundPage", () => {
        it("renders the 404 heading", () => {
                render(
                        <MemoryRouter>
                                <NotFoundPage />
                        </MemoryRouter>,
                );
                expect(screen.getByText("404")).toBeInTheDocument();
        });

        it("renders 'Page not found' subtitle", () => {
                render(
                        <MemoryRouter>
                                <NotFoundPage />
                        </MemoryRouter>,
                );
                expect(screen.getByText(/page not found/i)).toBeInTheDocument();
        });

        it("renders a back-to-dashboard button", () => {
                render(
                        <MemoryRouter>
                                <NotFoundPage />
                        </MemoryRouter>,
                );
                expect(
                        screen.getByRole("button", { name: /back to dashboard/i }),
                ).toBeInTheDocument();
        });

        it("renders a go-back button", () => {
                render(
                        <MemoryRouter>
                                <NotFoundPage />
                        </MemoryRouter>,
                );
                expect(screen.getByRole("button", { name: /go back/i })).toBeInTheDocument();
        });

        it("navigates to dashboard when the button is clicked", () => {
                render(
                        <MemoryRouter>
                                <NotFoundPage />
                        </MemoryRouter>,
                );
                screen.getByRole("button", { name: /back to dashboard/i }).click();
                expect(mockNavigate).toHaveBeenCalledWith("/dashboard");
        });
});
