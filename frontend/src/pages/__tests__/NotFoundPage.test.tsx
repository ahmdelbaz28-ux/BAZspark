/**
 * NotFoundPage.test.tsx — Unit tests for the 404 page (V193 R13).
 */
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
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
                        <MemoryRouter initialEntries={["/missing"]}>
                                <Routes>
                                        <Route path="/missing" element={<NotFoundPage />} />
                                        <Route path="/dashboard" element={<div>Dashboard Page</div>} />
                                </Routes>
                        </MemoryRouter>,
                );
                const button = screen.getByRole("button", { name: /back to dashboard/i });
                fireEvent.click(button);
                expect(screen.getByText("Dashboard Page")).toBeInTheDocument();
        });
});
