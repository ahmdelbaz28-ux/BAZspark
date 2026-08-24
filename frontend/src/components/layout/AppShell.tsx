import type React from "react";
import { useLocation } from "react-router";
import { AgentWorkspaceBar } from "@/components/layout/AgentWorkspaceBar";
import { PageAnimator } from "@/components/layout/PageAnimator";
import TopBar from "@/components/layout/TopBar";
import Sidebar from "./Sidebar";
import StatusBar from "./StatusBar";
import "@/styles/shell.css";

interface AppShellProps {
	children: React.ReactNode;
	isConnected: boolean;
	backendUrl: string;
	environment: string;
	onHelpOpen: () => void;
	onSearchOpen?: () => void;
	currentLanguage: string;
	onLanguageChange: (lang: string) => void;
	/** Phase 3: optional docked AI Workflow drawer (380px, right side) */
	workflowDrawer?: React.ReactNode;
	workflowDrawerOpen?: boolean;
}

const AppShell: React.FC<AppShellProps> = ({
	children,
	isConnected,
	backendUrl,
	environment,
	onHelpOpen,
	onSearchOpen,
	currentLanguage,
	onLanguageChange,
	workflowDrawer,
	workflowDrawerOpen = false,
}) => {
	const isRTL = document.documentElement.dir === "rtl";
	const location = useLocation();
	const isAgentControlCenter =
		location.pathname === "/" ||
		location.pathname === "/agent" ||
		location.pathname === "/monitor/agent";

	return (
		<div
			// V177 UI FIX: Removed gradient + blur overlays that were destroying text contrast.
			// Root cause: AppShell had 3 stacked overlay layers (gradient background,
			// red/orange blur at opacity 30%, grid pattern at opacity 20%) all rendering
			// BEHIND the content but ABOVE the base bg-background. The combined effect
			// washed out text contrast to ~2/10 (per VLM audit), making every page look
			// "dimmed/empty" even when real data was loaded. The overlays may look subtle
			// in Figma but in production they make the UI unusable.
			//
			// Fix: Use a flat solid background (bg-background) with NO overlays. The
			// sidebar and topbar provide enough visual structure. Content area is now
			// clean and high-contrast.
			className="h-screen w-screen flex overflow-hidden bg-background relative"
			dir={isRTL ? "rtl" : "ltr"}
		>
			{/* UI/UX Pro Max audit (Phase 5.1): skip-link for keyboard users.
                            Visually hidden until focused, then floats top-left above everything.
                            Phase 13: switched from bg-cyan-400 to evac-green (FACP vocabulary). */}
			<a
				href="#main-content"
				className="shell-skip-link sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-[100] focus:px-4 focus:py-2 focus:font-medium focus:shadow-lg"
			>
				Skip to main content
			</a>

			<Sidebar />

			<div className="flex-1 flex flex-col min-w-0">
				<TopBar
					isConnected={isConnected}
					onHelpOpen={onHelpOpen}
					onSearchOpen={onSearchOpen}
					currentLanguage={currentLanguage}
					onLanguageChange={onLanguageChange}
				/>

				{!isAgentControlCenter && <AgentWorkspaceBar />}

				<main
					id="main-content"
					className="flex-1 overflow-auto bg-background relative min-w-0"
				>
					<div className="relative z-10">
						<PageAnimator>{children}</PageAnimator>
					</div>
				</main>

				{/* Phase 3: Docked AI Workflow Drawer (380px fixed, right side).
                             pointer-events:none on all ephemeral SVG overlays inside.
                             flex-shrink-0 keeps it from collapsing on narrow viewports. */}
				{workflowDrawer && workflowDrawerOpen && (
					<div
						className="w-[380px] shrink-0 flex flex-col border-l border-border bg-card overflow-y-auto"
						aria-label="AI Workflow Surface"
						role="complementary"
					>
						{workflowDrawer}
					</div>
				)}

				<StatusBar
					backendUrl={backendUrl}
					isConnected={isConnected}
					environment={environment}
				/>
			</div>
		</div>
	);
};

export default AppShell;
