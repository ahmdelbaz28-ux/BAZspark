/** Primary application top bar — connection status, search, help, settings, theme toggle, language, and user menu. (core/Header was removed in V235 cleanup — dead code.) */
import { Globe, HelpCircle, Moon, Search, Settings, Sun } from "lucide-react";
import type React from "react";
import { memo, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";
import { UserMenu } from "@/components/auth/UserMenu";
import { ContextualHelpButton } from "@/components/shared/ContextualHelpButton";
import { useTheme } from "@/contexts/ThemeContext";
import "@/styles/shell.css";

interface TopBarProps {
	isConnected: boolean;
	onHelpOpen: () => void;
	onSearchOpen?: () => void;
	currentLanguage: string;
	onLanguageChange: (lang: string) => void;
}

const routeLabels: Record<string, string> = {
	"/": "AI Control Center",
	"/agent": "AI Control Center",
	"/monitor/agent": "AI Control Center",
	"/dashboard": "Dashboard",
	"/projects": "Projects & Model Context",
	"/engineering": "Engineering Workspace",
	"/marine": "Marine System Engineering",
	"/mining": "Mining System Engineering",
	"/api-keys": "API Key Management",
	"/exports": "Deliverables Export",
	"/self-healing": "Self-Healing Resilience",
	"/facp": "FACP Panel Selector",
	"/environment": "Environmental Context",
	"/monitor": "Live Telemetry & Monitoring",
	"/memory": "Agent Memory & Knowledge",
	"/graphrag": "GraphRAG Knowledge Network",
	"/workflow": "Review & Governance",
	"/reports": "Reports & Deliverables",
	"/reports/generate": "Report Generator",
	"/settings": "Settings & Administration",
	"/settings/cad": "CAD Defaults & Settings",
	"/settings/database": "Database Administration",
	"/billing": "Billing & Subscriptions",
	"/digital-twin": "Digital Twin 3D",
	"/fire-alarm-designer": "Fire Alarm Designer",
	"/fire-alarm/designer": "Fire Alarm Designer",
	"/fire-alarm": "Fire Alarm Designer",
	"/elements": "Spatial Elements",
	"/connections": "Circuit Connections",
	"/conflicts": "Spatial Conflict Resolution",
	"/autocad": "AutoCAD Integration",
	"/autocad/draw": "AutoCAD Vector Draw",
	"/revit": "Revit BIM Integration",
	"/revit/create": "Revit Element Creator",
	"/revit/elements": "Revit BIM Hierarchy",
	"/digital-twin/convert": "DT Format Converter",
	"/digital-twin/config": "Digital Twin Config",
	"/digital-twin/history": "Digital Twin Revisions",
	"/simready": "SimReady Assets",
	"/etap": "ETAP Power Analysis Bridge",
	"/fds-simulation": "FDS Fire Simulation",
	"/bim-providers": "BIM Cloud Providers",
	"/ifc43-mapping": "IFC 4.3 Schema Mapping",
	"/ar-export": "AR / VR Visual Export",
	"/dashboard/system-health": "System Health Monitor",
	"/engineering/generative": "Generative Fire Design",
	"/engineering/fireai": "FireAI Engineering Analysis",
	"/engineering/pipeline": "Pipeline Layers",
	"/engineering/topology": "Topology & Single-Line Diagram",
	"/engineering/qomn": "QOMN Physics Kernel",
	"/settings/rbac": "RBAC Role Management",
	"/settings/experimental": "Experimental Services",
	"/settings/webhooks": "Webhook Management",
	"/analysis": "Engineering Analysis Engine",
	"/aps": "Autodesk Platform Services (APS)",
	"/audit-trail": "Audit Trail & Event Ledger",
	"/bms": "BMS Telemetry Integration",
	"/cad-tools": "CAD Engineering Tools",
	"/devices": "Fire Alarm Device Catalog",
	"/dwg": "DWG Vector Parser",
	"/engineering-copilot": "Engineering Copilot",
	"/engineering/guards": "Physics Rule Guards",
	"/environment/air-quality": "Air Quality Telemetry",
	"/environment/context": "Environmental Context Engine",
	"/environment/hazmat": "HazMat Hazard Tracker",
	"/security-alerts": "Security Alerts & Hardening",
	"/settings/advanced": "Advanced System Settings",
	"/sync": "Cross-System Data Sync",
	"/multi-db": "Multi-Database Partitions",
	"/settings/ai-agents": "AI Agent Configuration",
};

const TopBar: React.FC<TopBarProps> = memo(
	// NOSONAR - typescript:S9011: Intentionally complex demo UI with many interactive buttons
	({
		isConnected,
		onHelpOpen,
		onSearchOpen,
		currentLanguage,
		onLanguageChange,
	}) => {
		const location = useLocation();
		const { dark, toggle } = useTheme();
		const [langOpen, setLangOpen] = useState(false);
		const langRef = useRef<HTMLDivElement>(null);

		// Close language dropdown on outside click
		useEffect(() => {
			const handler = (e: MouseEvent) => {
				if (langRef.current && !langRef.current.contains(e.target as Node)) {
					setLangOpen(false);
				}
			};
			document.addEventListener("mousedown", handler);
			return () => document.removeEventListener("mousedown", handler);
		}, []);

		const pageName =
			routeLabels[location.pathname] ||
			(location.pathname.startsWith("/elements/")
				? "Element Details"
				: "BAZSPARK");
		const connState = isConnected ? "online" : "offline";

		return (
			<header className="shell-topbar h-12 flex items-center px-3 lg:px-4 gap-2 shrink-0 sticky top-0 z-40 border-b border-border bg-card">
				{/* Left — logo + page title / breadcrumb */}
				<div className="flex items-center gap-2.5 min-w-0">
					<BazSparkLogo size={26} className="shrink-0" />
					<nav aria-label="breadcrumb" className="breadcrumb-container flex items-center gap-1.5 min-w-0">
						<span className="text-xs text-muted-foreground font-mono hidden sm:inline">WORKSTATION ▸</span>
						<span className="shell-page-title truncate text-sm font-semibold tracking-tight text-foreground" title={pageName}>
							{pageName}
						</span>
					</nav>
				</div>

				<div className="flex-1" />

				{/* Quick Command Palette trigger */}
				<button
					type="button"
					onClick={onSearchOpen}
					className="hidden md:flex items-center gap-2 px-2.5 py-1 text-xs text-muted-foreground bg-popover hover:bg-muted border border-border rounded transition-colors"
					aria-label="Quick command search"
					title="Quick Command (Ctrl+K)"
				>
					<Search aria-hidden="true" className="h-3.5 w-3.5 text-primary" />
					<span>Commands & Tools...</span>
					<kbd className="font-mono text-[10px] bg-background px-1.5 py-0.5 rounded border border-border text-muted-foreground">Ctrl+K</kbd>
				</button>

				{/* Connection status — engineering online/offline telemetry */}
				<div
					className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-popover/80 border border-border text-xs"
					role="status"
					aria-live="polite"
					aria-label={
						isConnected ? "Connected to backend" : "Disconnected from backend"
					}
				>
					<span className={`shell-conn-dot ${connState}`} aria-hidden="true" />
					<span className={`shell-conn-label ${connState} font-mono text-[11px]`}>
						{isConnected ? "ONLINE" : "OFFLINE"}
					</span>
				</div>

				<hr className="shell-separator" aria-orientation="vertical" />

				{/* Action buttons */}
				<button
					type="button"
					onClick={onSearchOpen}
					className="shell-icon-btn p-1.5 md:hidden"
					aria-label="Search"
					title="Search (Ctrl+K)"
				>
					<Search aria-hidden="true" className="h-4 w-4" />
				</button>

				<ContextualHelpButton />

				<button
					type="button"
					onClick={onHelpOpen}
					className="shell-icon-btn p-1.5"
					aria-label="Help"
					data-onboarding="help-button"
					title="Global help (F1)"
				>
					<HelpCircle aria-hidden="true" className="h-4 w-4" />
				</button>

				<Link
					to="/settings"
					className="shell-icon-btn p-1.5 inline-flex"
					aria-label="Settings"
					title="Settings"
				>
					<Settings aria-hidden="true" className="h-4 w-4" />
				</Link>

				{/* Dark mode toggle */}
				<button
					type="button"
					onClick={toggle}
					aria-label="Toggle dark mode"
					className="shell-icon-btn p-1.5"
				>
					{dark ? (
						<Moon aria-hidden="true" className="h-4 w-4" />
					) : (
						<Sun aria-hidden="true" className="h-4 w-4" />
					)}
				</button>

				{/* Language selector */}
				<div className="relative" ref={langRef}>
					<button
						type="button"
						onClick={() => setLangOpen(!langOpen)}
						className="shell-lang-btn flex items-center gap-1 px-2 py-1 text-xs"
						aria-label="Change language"
						aria-expanded={langOpen}
						aria-haspopup="menu"
					>
						<Globe aria-hidden="true" className="h-3.5 w-3.5" />
						<span>{currentLanguage.toUpperCase()}</span>
					</button>
					{langOpen && (
						<div
							className="shell-lang-menu absolute right-0 top-full mt-1 shadow-xl z-50 min-w-[130px] overflow-hidden"
							role="menu"
							aria-label="Language selector"
						>
							{["en", "ar"].map((lang) => (
								<button
									type="button"
									key={lang}
									onClick={() => {
										onLanguageChange(lang);
										setLangOpen(false);
									}}
									role="menuitemradio"
									aria-checked={currentLanguage === lang}
									className={`shell-lang-item block w-full text-left px-3 py-2 text-xs ${
										currentLanguage === lang ? "active" : ""
									}`}
								>
									{lang === "en" ? "English" : "العربية"}
								</button>
							))}
						</div>
					)}
				</div>

				<hr className="shell-separator" aria-orientation="vertical" />

				<UserMenu />
			</header>
		);
	},
);

TopBar.displayName = "TopBar";

export default TopBar;
