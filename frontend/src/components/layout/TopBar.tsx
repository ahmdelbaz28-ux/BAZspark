import { Globe, HelpCircle, Menu, Search, Settings, Sun, Moon } from "lucide-react";
import type React from "react";
import { memo, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { UserMenu } from "@/components/auth/UserMenu";
import { ContextualHelpButton } from "@/components/shared/ContextualHelpButton";
import { useTheme } from "@/contexts/ThemeContext";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";

interface TopBarProps {
	isConnected: boolean;
	onHelpOpen: () => void;
	onSearchOpen?: () => void;
	currentLanguage: string;
	onLanguageChange: (lang: string) => void;
	/** NAV-003 FIX: Mobile sidebar toggle callback */
	onMobileSidebarToggle?: () => void;
}

const routeLabels: Record<string, string> = {
	"/": "Dashboard",
	"/projects": "Projects",
	"/engineering": "Engineering",
	"/fire-alarm-designer": "Fire Alarm Designer",
	"/fire-alarm/designer": "Fire Alarm Designer",
	"/digital-twin": "Digital Twin",
	"/reports": "Reports",
	"/elements": "Elements",
	"/connections": "Connections",
	"/conflicts": "Conflicts",
	"/settings": "Settings",
	"/autocad": "AutoCAD",
	"/autocad/draw": "ACAD Draw",
	"/revit": "Revit",
	"/revit/create": "Revit Create",
	"/revit/elements": "Revit Elements",
	"/digital-twin/convert": "DT Convert",
	"/digital-twin/config": "DT Config",
	"/digital-twin/history": "DT History",
};

const TopBar: React.FC<TopBarProps> = memo(
	({
		isConnected,
		onHelpOpen,
		onSearchOpen,
		currentLanguage,
		onLanguageChange,
		onMobileSidebarToggle,
	}) => {
		const location = useLocation();
		const { dark, toggle } = useTheme();
		const [langOpen, setLangOpen] = useState(false);
		const langRef = useRef<HTMLDivElement>(null);

		// Close language dropdown on outside click
		useEffect(() => {
			const handler = (e: MouseEvent) => {
				if (
					langRef.current &&
					!langRef.current.contains(e.target as Node)
				) {
					setLangOpen(false);
				}
			};
			document.addEventListener("mousedown", handler);
			return () => document.removeEventListener("mousedown", handler);
		}, []);

		// A11Y-003 FIX: Close language dropdown on Escape key
		useEffect(() => {
			const handler = (e: KeyboardEvent) => {
				if (e.key === "Escape" && langOpen) {
					setLangOpen(false);
				}
			};
			document.addEventListener("keydown", handler);
			return () => document.removeEventListener("keydown", handler);
		}, [langOpen]);

		const pageName = routeLabels[location.pathname] || "BAZSPARK";

		return (
			<TooltipProvider delayDuration={300}>
				<header
					className="h-16 glass flex items-center px-4 lg:px-6 gap-2 lg:gap-4 shrink-0 sticky top-0 z-40"
					style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}
					role="banner"
				>
					{/* NAV-003 FIX: Mobile hamburger menu button */}
					<Tooltip>
						<TooltipTrigger asChild>
							<button
								type="button"
								onClick={onMobileSidebarToggle}
								className="md:hidden p-2 text-muted-foreground hover:text-cyan-300 hover:bg-white/5 transition-[color,background-color,border-color,transform] duration-200 rounded-lg"
								aria-label="Toggle sidebar menu"
							>
								<Menu aria-hidden="true" className="h-5 w-5" />
							</button>
						</TooltipTrigger>
						<TooltipContent side="bottom">
							<p>Menu</p>
						</TooltipContent>
					</Tooltip>

					{/* Left — logo + page title */}
					<div className="flex items-center gap-3 min-w-0">
						<BazSparkLogo size={30} className="shrink-0" />
						<h1 className="text-foreground font-semibold text-[16px] tracking-tight truncate ml-1">
							{pageName}
						</h1>
					</div>

					<div className="flex-1" />

					{/* Connection status */}
					<div className="flex items-center gap-2">
						<span
							className={`h-2 w-2 rounded-full ${isConnected ? "bg-success" : "bg-slate-500"}`}
							title={isConnected ? "Connected" : "Disconnected"}
							role="status"
							aria-label={isConnected ? "Connected" : "Disconnected"}
						/>
						<span className="text-muted-foreground text-[13px] hidden md:inline">
							{isConnected ? "Online" : "Offline"}
						</span>
					</div>

					<div className="h-5 w-px bg-white/10" aria-hidden="true" />

					{/* SC-006 FIX: Tooltip support on icon-only buttons */}
					{/* Action buttons */}
					<Tooltip>
						<TooltipTrigger asChild>
							<button
								type="button"
								onClick={onSearchOpen}
								className="p-2 text-muted-foreground hover:text-cyan-300 hover:bg-white/5 transition-[color,background-color,border-color,transform] duration-200 rounded-lg"
								aria-label="Search"
							>
								<Search aria-hidden="true" className="h-[18px] w-[18px]" />
							</button>
						</TooltipTrigger>
						<TooltipContent side="bottom">
							<p>Search (Ctrl+K)</p>
						</TooltipContent>
					</Tooltip>

					<ContextualHelpButton />

					<Tooltip>
						<TooltipTrigger asChild>
							<button
								type="button"
								onClick={onHelpOpen}
								className="p-2 text-muted-foreground hover:text-cyan-300 hover:bg-white/5 transition-[color,background-color,border-color,transform] duration-200 rounded-lg"
								aria-label="Help"
								data-onboarding="help-button"
							>
								<HelpCircle
									aria-hidden="true"
									className="h-[18px] w-[18px]"
								/>
							</button>
						</TooltipTrigger>
						<TooltipContent side="bottom">
							<p>Global help (F1)</p>
						</TooltipContent>
					</Tooltip>

					<Tooltip>
						<TooltipTrigger asChild>
							<Link
								to="/settings"
								className="p-2 text-muted-foreground hover:text-cyan-300 hover:bg-white/5 transition-[color,background-color,border-color,transform] duration-200 rounded-lg inline-flex"
								aria-label="Settings"
							>
								<Settings
									aria-hidden="true"
									className="h-[18px] w-[18px]"
								/>
							</Link>
						</TooltipTrigger>
						<TooltipContent side="bottom">
							<p>Settings</p>
						</TooltipContent>
					</Tooltip>

					{/* Dark mode toggle with tooltip */}
					<Tooltip>
						<TooltipTrigger asChild>
							<button
								type="button"
								onClick={toggle}
								aria-label={
									dark ? "Switch to light mode" : "Switch to dark mode"
								}
								className="p-2 text-muted-foreground hover:text-cyan-300 hover:bg-white/5 transition-[color,background-color,border-color,transform] duration-200 rounded-lg"
							>
								{dark ? (
									<Moon
										aria-hidden="true"
										className="h-5 w-5"
									/>
								) : (
									<Sun
										aria-hidden="true"
										className="h-5 w-5"
									/>
								)}
							</button>
						</TooltipTrigger>
						<TooltipContent side="bottom">
							<p>{dark ? "Light mode" : "Dark mode"}</p>
						</TooltipContent>
					</Tooltip>

					{/* Language selector — I18N-001 FIX: RTL-aware dropdown */}
					<div className="relative" ref={langRef}>
						<Tooltip>
							<TooltipTrigger asChild>
								<button
									type="button"
									onClick={() => setLangOpen(!langOpen)}
									className="flex items-center gap-1.5 px-3 py-2 text-muted-foreground hover:text-cyan-300 hover:bg-white/5 transition-[color,background-color,border-color,transform] duration-200 text-[13px] rounded-lg border border-white/10 font-medium"
									aria-label="Change language"
									aria-expanded={langOpen}
									aria-haspopup="listbox"
								>
									<Globe aria-hidden="true" className="h-4 w-4" />
									{currentLanguage.toUpperCase()}
								</button>
							</TooltipTrigger>
							<TooltipContent side="bottom">
								<p>Language</p>
							</TooltipContent>
						</Tooltip>
						{langOpen && (
							<div
								className="lang-dropdown absolute right-0 top-full mt-2 glass rounded-lg shadow-xl z-50 min-w-[120px] overflow-hidden"
								role="listbox"
								aria-label="Select language"
							>
								{["en", "ar"].map((lang) => (
									<button
										type="button"
										key={lang}
										onClick={() => {
											onLanguageChange(lang);
											setLangOpen(false);
										}}
										className={`block w-full text-left px-3 py-2.5 text-[13px] transition-colors duration-200 ${
											currentLanguage === lang
												? "text-cyan-300 bg-cyan-400/10"
												: "text-foreground hover:bg-white/5"
										}`}
										role="option"
										aria-selected={currentLanguage === lang}
									>
										{lang === "en" ? "English" : "العربية"}
									</button>
								))}
							</div>
						)}
					</div>

					<div className="h-5 w-px bg-white/10" aria-hidden="true" />

					<UserMenu />
				</header>
			</TooltipProvider>
		);
	},
);

TopBar.displayName = "TopBar";

export default TopBar;
