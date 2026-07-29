import {
	AlertTriangle,
	ArrowRightLeft,
	Activity,
	Box,
	Ship,
	Building2,
	Cable,
	Calculator,
	Cpu,
	ChevronLeft,
	ChevronRight,
	FileText,
	Siren,
	FolderKanban,
	History,
	Layers,
	LayoutDashboard,
	PencilRuler,
	Settings,
	Shield,
	CloudSun,
	Brain,
	Network,
	Flame,
	Workflow as WorkflowIcon,
	Settings2,
	Info,
	Pickaxe,
	Key,
	Download,
	Server,
	Globe,
	Smartphone,
} from "lucide-react";
import type React from "react";
import { memo, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";

// Vercel React Best Practices: network-prefetch — preload lazy chunks on hover
const routePrefetchMap: Record<string, () => Promise<unknown>> = {
	"/dashboard": () => import("@/pages/DashboardPage"),
	"/projects": () => import("@/pages/ProjectsPage"),
	"/engineering": () => import("@/pages/EngineeringPage"),
	"/facp": () => import("@/pages/FACPPage"),
	"/marine": () => import("@/pages/MarinePage"),
	"/mining": () => import("@/pages/MiningPage"),
	"/fire-alarm/designer": () =>
		import("@/components/mockups/engineering/FireAlarmDesigner"),
	"/autocad": () => import("@/pages/AutoCADPage"),
	"/autocad/draw": () => import("@/pages/AutoCADDrawPage"),
	"/revit": () => import("@/pages/RevitPage"),
	"/revit/create": () => import("@/pages/RevitCreatePage"),
	"/revit/elements": () => import("@/pages/RevitElementsPage"),
	"/digital-twin": () => import("@/pages/DigitalTwinPage"),
	"/digital-twin/convert": () => import("@/pages/DigitalTwinConvertPage"),
	"/digital-twin/config": () => import("@/pages/DigitalTwinConfigPage"),
	"/digital-twin/history": () => import("@/pages/DigitalTwinHistoryPage"),
	"/reports": () => import("@/pages/ReportsPage"),
	"/exports": () => import("@/pages/ExportsPage"),
	"/etap": () => import("@/pages/EtapPage"),
	"/environment": () => import("@/pages/EnvironmentPage"),
	"/monitor": () => import("@/pages/MonitorPage"),
	"/self-healing": () => import("@/pages/SelfHealingPage"),
	"/memory": () => import("@/pages/MemoryPage"),
	"/graphrag": () => import("@/pages/GraphRAGPage"),
	"/workflow": () => import("@/pages/WorkflowPage"),
	"/elements": () => import("@/pages/Elements"),
	"/connections": () => import("@/pages/Connections"),
	"/conflicts": () => import("@/pages/Conflicts"),
	"/settings": () => import("@/pages/SettingsPage"),
	"/api-keys": () => import("@/pages/ApiKeysPage"),
	"/fds-simulation": () => import("@/pages/FDSSimulationPage"),
	"/bim-providers": () => import("@/pages/BIMProvidersPage"),
	"/ifc43-mapping": () => import("@/pages/IFC43MappingPage"),
	"/ar-export": () => import("@/pages/ARExportPage"),
	"/webhook-management": () => import("@/pages/WebhookManagementPage"),
	"/generative-design": () => import("@/pages/GenerativeDesignPage"),
	"/topology": () => import("@/pages/TopologyPage"),
};

interface NavItem {
	labelKey: string;
	defaultLabel: string;
	icon: React.ElementType;
	path: string;
	dataOnboarding?: string;
	/** If set, only users with this role can see this nav item. */
	requiredRole?: string;
}

const navItems: NavItem[] = [
	{
		labelKey: "nav.dashboard",
		defaultLabel: "Dashboard",
		icon: LayoutDashboard,
		path: "/dashboard",
		dataOnboarding: "nav-dashboard",
	},
	{
		labelKey: "nav.projects",
		defaultLabel: "Projects",
		icon: FolderKanban,
		path: "/projects",
		dataOnboarding: "nav-projects",
	},
	{
		labelKey: "nav.engineering",
		defaultLabel: "Engineering",
		icon: Calculator,
		path: "/engineering",
		dataOnboarding: "nav-engineering",
	},
	{
		labelKey: "nav.facp",
		defaultLabel: "FACP Selector",
		icon: Cpu,
		path: "/facp",
		dataOnboarding: "nav-facp",
	},
	{
		labelKey: "nav.marine",
		defaultLabel: "Marine",
		icon: Ship,
		path: "/marine",
		dataOnboarding: "nav-marine",
	},
	{
		labelKey: "nav.mining",
		defaultLabel: "Mining",
		icon: Pickaxe,
		path: "/mining",
		dataOnboarding: "nav-mining",
	},
	{
		labelKey: "nav.fireAlarmDesigner",
		defaultLabel: "Fire Alarm Designer",
		icon: Siren,
		path: "/fire-alarm/designer",
		dataOnboarding: "nav-fire-alarm-designer",
	},
	{
		labelKey: "nav.autocad",
		defaultLabel: "AutoCAD",
		icon: PencilRuler,
		path: "/autocad",
		dataOnboarding: "nav-autocad",
	},
	{
		labelKey: "nav.autocadDraw",
		defaultLabel: "ACAD Draw",
		icon: PencilRuler,
		path: "/autocad/draw",
	},
	{
		labelKey: "nav.revit",
		defaultLabel: "Revit",
		icon: Building2,
		path: "/revit",
		dataOnboarding: "nav-revit",
	},
	{
		labelKey: "nav.revitCreate",
		defaultLabel: "Revit Create",
		icon: Building2,
		path: "/revit/create",
	},
	{
		labelKey: "nav.revitElements",
		defaultLabel: "Revit Elements",
		icon: Layers,
		path: "/revit/elements",
	},
	{
		labelKey: "nav.digitalTwin",
		defaultLabel: "Digital Twin",
		icon: Box,
		path: "/digital-twin",
		dataOnboarding: "nav-digital-twin",
	},
	{
		labelKey: "nav.dtConvert",
		defaultLabel: "DT Convert",
		icon: ArrowRightLeft,
		path: "/digital-twin/convert",
	},
	{
		labelKey: "nav.dtConfig",
		defaultLabel: "DT Config",
		icon: Settings2,
		path: "/digital-twin/config",
	},
	{
		labelKey: "nav.dtHistory",
		defaultLabel: "DT History",
		icon: History,
		path: "/digital-twin/history",
	},
	{
		labelKey: "nav.reports",
		defaultLabel: "Reports",
		icon: FileText,
		path: "/reports",
		dataOnboarding: "nav-reports",
	},
	{
		labelKey: "nav.exports",
		defaultLabel: "Exports",
		icon: Download,
		path: "/exports",
		dataOnboarding: "nav-exports",
		requiredRole: "admin",
	},
	{
		labelKey: "nav.etap",
		defaultLabel: "ETAP",
		icon: Server,
		path: "/etap",
		dataOnboarding: "nav-etap",
	},
	{
		labelKey: "nav.environment",
		defaultLabel: "Environment",
		icon: CloudSun,
		path: "/environment",
		dataOnboarding: "nav-environment",
	},
	{
		labelKey: "nav.monitor",
		defaultLabel: "Monitor",
		icon: Activity,
		path: "/monitor",
		dataOnboarding: "nav-monitor",
	},
	{
		labelKey: "nav.fdsSimulation",
		defaultLabel: "FDS Simulation",
		icon: Flame,
		path: "/fds-simulation",
		dataOnboarding: "nav-fds-simulation",
		requiredRole: "admin",
	},
	{
		labelKey: "nav.selfHealing",
		defaultLabel: "Self-Healing",
		icon: Shield,
		path: "/self-healing",
		dataOnboarding: "nav-self-healing",
		requiredRole: "admin",
	},
	{
		labelKey: "nav.memory",
		defaultLabel: "Memory",
		icon: Brain,
		path: "/memory",
		dataOnboarding: "nav-memory",
	},
	{
		labelKey: "nav.graphrag",
		defaultLabel: "GraphRAG",
		icon: Network,
		path: "/graphrag",
		dataOnboarding: "nav-graphrag",
	},
	{
		labelKey: "nav.workflow",
		defaultLabel: "Workflows",
		icon: WorkflowIcon,
		path: "/workflow",
		dataOnboarding: "nav-workflow",
	},
	{
		labelKey: "nav.elements",
		defaultLabel: "Elements",
		icon: Layers,
		path: "/elements",
		dataOnboarding: "nav-elements",
	},
	{
		labelKey: "nav.connections",
		defaultLabel: "Connections",
		icon: Cable,
		path: "/connections",
		dataOnboarding: "nav-connections",
	},
	{
		labelKey: "nav.conflicts",
		defaultLabel: "Conflicts",
		icon: AlertTriangle,
		path: "/conflicts",
		dataOnboarding: "nav-conflicts",
	},
	{
		labelKey: "nav.settings",
		defaultLabel: "Settings",
		icon: Settings,
		path: "/settings",
		dataOnboarding: "nav-settings",
	},
	{
		labelKey: "nav.apiKeys",
		defaultLabel: "API Keys",
		icon: Key,
		path: "/api-keys",
		dataOnboarding: "nav-api-keys",
		requiredRole: "admin",
	},
	{
		labelKey: "nav.bimProviders",
		defaultLabel: "BIM Providers",
		icon: Building2,
		path: "/bim-providers",
		dataOnboarding: "nav-bim-providers",
	},
	{
		labelKey: "nav.ifc43Mapping",
		defaultLabel: "IFC 4.3 Mapping",
		icon: Globe,
		path: "/ifc43-mapping",
		dataOnboarding: "nav-ifc43-mapping",
		requiredRole: "admin",
	},
	{
		labelKey: "nav.arExport",
		defaultLabel: "AR Export",
		icon: Smartphone,
		path: "/ar-export",
		dataOnboarding: "nav-ar-export",
		requiredRole: "admin",
	},
	{
		labelKey: "nav.webhookManagement",
		defaultLabel: "Webhook Management",
		icon: Globe,
		path: "/webhook-management",
		dataOnboarding: "nav-webhook-management",
		requiredRole: "admin",
	},
	{
		labelKey: "nav.generativeDesign",
		defaultLabel: "Generative Design",
		icon: WorkflowIcon,
		path: "/generative-design",
		dataOnboarding: "nav-generative-design",
		requiredRole: "admin",
	},
	{
		labelKey: "nav.topology",
		defaultLabel: "Topology",
		icon: Network,
		path: "/topology",
		dataOnboarding: "nav-topology",
		requiredRole: "admin",
	},
	{
		labelKey: "nav.rbac",
		defaultLabel: "RBAC Permissions",
		icon: Shield,
		path: "/rbac",
		dataOnboarding: "nav-rbac",
		requiredRole: "admin",
	},
];

interface SidebarProps {
	compact?: boolean;
}

const Sidebar: React.FC<SidebarProps> = memo(() => {
	const [collapsed, setCollapsed] = useState(false);
	const location = useLocation();
	const { t } = useTranslation();
	const { role } = useAuth();
	const isRTL = document.documentElement.dir === "rtl";

	const width = collapsed ? "w-16" : "w-60";

	return (
		<TooltipProvider delayDuration={300}>
			<aside
				className={`${width} h-full glass flex flex-col transition-[width] duration-300 ${isRTL ? "order-last" : "order-first"}`}
				style={{
					borderRight: isRTL
						? "none"
						: "1px solid rgba(255,255,255,0.1)",
					borderLeft: isRTL
						? "1px solid rgba(255,255,255,0.1)"
						: "none",
				}}
				role="navigation"
				aria-label="Primary navigation"
			>
				{/* Brand header */}
				<div className="flex items-center gap-3 px-5 h-16 shrink-0 border-b border-white/10">
					<BazSparkLogo size={32} className="shrink-0" />
					{!collapsed && (
						<div className="flex flex-col leading-relaxed">
							<span className="text-foreground font-semibold text-[15px] tracking-tight">
								BAZSPARK
							</span>
							<span className="text-[11px] text-muted-foreground uppercase tracking-wider mt-0.5">
								FireAI Digital Twin
							</span>
						</div>
					)}
				</div>

				<nav
					className="flex-1 py-3 overflow-y-auto overflow-x-hidden"
					aria-label="Primary navigation"
				>
					{navItems
						.filter(
							(item) =>
								!item.requiredRole || item.requiredRole === role,
						)
						.map((item) => {
							const isActive =
								location.pathname === item.path ||
								(item.path !== "/dashboard" &&
									location.pathname.startsWith(
										`${item.path}/`,
									));
							const labelText = t(
								item.labelKey,
								item.defaultLabel,
							);

							// SC-006 FIX: When sidebar is collapsed, show tooltip on nav items
							if (collapsed) {
								return (
									<div
										key={item.path}
										className="relative px-3 mb-1"
									>
										<Tooltip>
											<TooltipTrigger asChild>
												<Link
													to={item.path}
													className={`sidebar-nav-item flex items-center justify-center gap-3 px-3 py-2.5 rounded-lg transition-[color,background-color,border-color,transform] duration-200 ${
														isActive
															? "bg-cyan-400/10 text-cyan-300 border border-cyan-400/20"
															: "text-muted-foreground hover:bg-white/5 hover:text-foreground border border-transparent"
													}`}
													aria-current={
														isActive
															? "page"
															: undefined
													}
													data-onboarding={
														item.dataOnboarding
													}
													onMouseEnter={() =>
														routePrefetchMap[
															item.path
														]?.()
													}
												>
													<item.icon
														className={`shrink-0 h-[18px] w-[18px] ${isActive ? "text-cyan-300" : ""}`}
														aria-hidden="true"
													/>
												</Link>
											</TooltipTrigger>
											<TooltipContent side="right">
												<p>{labelText}</p>
											</TooltipContent>
										</Tooltip>
									</div>
								);
							}

							return (
								<div
									key={item.path}
									className="relative px-3 mb-1"
								>
									<Link
										to={item.path}
										className={`sidebar-nav-item flex items-center gap-3 px-3 py-2.5 rounded-lg transition-[color,background-color,border-color,transform] duration-200 ${
											isActive
												? "bg-cyan-400/10 text-cyan-300 border border-cyan-400/20"
												: "text-muted-foreground hover:bg-white/5 hover:text-foreground border border-transparent"
										}`}
										aria-current={
											isActive ? "page" : undefined
										}
										title={collapsed ? labelText : undefined}
										data-onboarding={item.dataOnboarding}
										onMouseEnter={() =>
											routePrefetchMap[item.path]?.()
										}
									>
										<item.icon
											className={`shrink-0 h-[18px] w-[18px] ${isActive ? "text-cyan-300" : ""}`}
											aria-hidden="true"
										/>
										{!collapsed && (
											<span className="truncate text-[13px] font-medium tracking-wide">
												{labelText}
											</span>
										)}
									</Link>
								</div>
							);
						})}
				</nav>

				{/* Footer — About + collapse */}
				<div className="border-t border-white/10 shrink-0 p-3">
					{!collapsed && (
						<Link
							to="/settings"
							className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-muted-foreground hover:bg-white/5 hover:text-foreground transition-[color,background-color,border-color,transform] duration-200"
						>
							<Info
								aria-hidden="true"
								className="h-[18px] w-[18px] shrink-0"
							/>
							<span className="text-[13px] font-medium">
								About BAZSPARK
							</span>
						</Link>
					)}
					<button
						type="button"
						onClick={() => setCollapsed(!collapsed)}
						className="flex items-center justify-center w-full py-2.5 rounded-lg text-muted-foreground hover:text-cyan-400 hover:bg-white/5 transition-[color,background-color,border-color] duration-200 mt-1"
						aria-label={
							collapsed ? "Expand sidebar" : "Collapse sidebar"
						}
						data-onboarding="sidebar-toggle"
					>
						{collapsed ? (
							isRTL ? (
								<ChevronLeft
									aria-hidden="true"
									className="h-4 w-4"
								/>
							) : (
								<ChevronRight
									aria-hidden="true"
									className="h-4 w-4"
								/>
							)
						) : isRTL ? (
							<ChevronRight
								aria-hidden="true"
								className="h-4 w-4"
							/>
						) : (
							<ChevronLeft
								aria-hidden="true"
								className="h-4 w-4"
							/>
						)}
					</button>
				</div>
			</aside>
		</TooltipProvider>
	);
});

Sidebar.displayName = "Sidebar";

export default Sidebar;
