/** App navigation sidebar — routes and page links. Distinct from ProjectSidebar (project-scoped) and ui/sidebar (shadcn primitive). */
import {
	Activity,
	AlertTriangle,
	ArrowRightLeft,
	Box,
	Brain,
	Building2,
	Cable,
	Calculator,
	ChevronLeft,
	ChevronRight,
	CloudSun,
	Cog,
	Cpu,
	CreditCard,
	Database,
	Download,
	FilePlus,
	FileText,
	Flame,
	FlaskConical,
	FolderKanban,
	Globe,
	HeartPulse,
	History,
	Info,
	Key,
	Layers,
	LayoutDashboard,
	Link2,
	MessageSquare,
	Network,
	PencilRuler,
	PenLine,
	Pickaxe,
	RotateCcw,
	Server,
	Settings,
	Settings2,
	Shield,
	ShieldCheck,
	Ship,
	Smartphone,
	Sparkles,
} from "lucide-react";
import type React from "react";
import { memo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";
import { useAuth } from "@/contexts/AuthContext";
import "@/styles/sidebar.css";

// Vercel React Best Practices: network-prefetch — preload lazy chunks on hover
const routePrefetchMap: Record<string, () => Promise<unknown>> = {
	"/": () => import("@/pages/AgentChatPage"),
	"/agent": () => import("@/pages/AgentChatPage"),
	"/dashboard": () => import("@/pages/DashboardPage"),
	"/projects": () => import("@/pages/ProjectsPage"),
	"/engineering": () => import("@/pages/EngineeringPage"),
	"/facp": () => import("@/pages/FACPPage"),
	"/marine": () => import("@/pages/MarinePage"),
	"/mining": () => import("@/pages/MiningPage"),

	"/autocad": () => import("@/pages/AutoCADPage"),
	"/autocad/draw": () => import("@/pages/AutoCADDrawPage"),
	"/revit": () => import("@/pages/RevitPage"),
	"/revit/create": () => import("@/pages/RevitCreatePage"),
	"/revit/elements": () => import("@/pages/RevitElementsPage"),
	"/digital-twin": () => import("@/pages/DigitalTwinPage"),
	"/digital-twin/convert": () => import("@/pages/DigitalTwinConvertPage"),
	"/digital-twin/config": () => import("@/pages/DigitalTwinConfigPage"),
	"/digital-twin/history": () => import("@/pages/DigitalTwinHistoryPage"),
	"/simready": () => import("@/pages/SimReadyPage"),
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
	"/settings/cad": () => import("@/pages/CADSettingsPage"),
	"/settings/database": () => import("@/pages/DatabaseAdminPage"),
	"/api-keys": () => import("@/pages/ApiKeysPage"),
	"/fds-simulation": () => import("@/pages/FDSSimulationPage"),
	"/bim-providers": () => import("@/pages/BIMProvidersPage"),
	"/ifc43-mapping": () => import("@/pages/IFC43MappingPage"),
	"/ar-export": () => import("@/pages/ARExportPage"),
	"/dashboard/system-health": () => import("@/pages/SystemHealthPage"),
	"/engineering/generative": () => import("@/pages/GenerativeDesignPage"),
	"/engineering/fireai": () => import("@/pages/EngineeringFireAIPage"),
	"/engineering/pipeline": () => import("@/pages/PipelineLayersPage"),
	"/engineering/topology": () => import("@/pages/TopologyPage"),
	"/settings/rbac": () => import("@/pages/RbacPage"),
	"/settings/webhooks": () => import("@/pages/WebhookManagementPage"),
	"/settings/ai-agents": () => import("@/pages/AgentSettingsPage"),
	"/monitor/agent": () => import("@/pages/AgentChatPage"),
	"/engineering/qomn": () => import("@/pages/QOMNCalculatorPage"),
	"/reports/generate": () => import("@/pages/ReportGeneratorPage"),
	"/cad-tools": () => import("@/pages/CADToolsPage"),
	"/analysis": () => import("@/pages/AnalysisPage"),
	"/dwg": () => import("@/pages/DWGPage"),
	"/engineering-copilot": () => import("@/pages/EngineeringCopilotPage"),
	"/settings/advanced": () => import("@/pages/AdvancedSettingsPage"),
	"/settings/experimental": () => import("@/pages/ExperimentalServicesPage"),
	"/security-alerts": () => import("@/pages/SecurityAlertsPage"),
	"/multi-db": () => import("@/pages/MultiDBPage"),
	"/sync": () => import("@/pages/SyncPage"),
	"/aps": () => import("@/pages/APSPage"),
	"/devices": () => import("@/pages/DevicesPage"),
	"/bms": () => import("@/pages/BMSPage"),
	"/engineering/guards": () => import("@/pages/GuardsPage"),
	"/environment/air-quality": () => import("@/pages/AirQualityPage"),
	"/environment/context": () => import("@/pages/ContextPage"),
	"/environment/hazmat": () => import("@/pages/HazMatPage"),
	"/audit-trail": () => import("@/pages/AuditTrailPage"),
	"/fire-alarm": () => import("@/pages/FireAlarmPage"),
	"/billing": () => import("@/pages/BillingPage"),
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

interface NavGroup {
	id: string;
	labelKey: string;
	defaultLabel: string;
	items: NavItem[];
}

// ═══════════════════════════════════════════════════════════════════════════
// Phase 8: UI Surface Consolidation Architecture.
//
// The workstation navigation is consolidated around 6 Primary Workstation
// Surfaces, backed by organized domain module groups that preserve 100% of
// all existing engineering routes, capabilities, deep-links, and RBAC gates:
//   1. Primary Workstation Surfaces (6 Hubs)
//   2. Engineering & Physics Modules
//   3. Project & Digital Twin Context
//   4. Review, Audit & Governance
//   5. Deliverables & Artifacts
//   6. Administration & Infrastructure
// ═══════════════════════════════════════════════════════════════════════════
const navGroups: NavGroup[] = [
	{
		id: "primary-surfaces",
		labelKey: "nav.group.primarySurfaces",
		defaultLabel: "Workstation Surfaces",
		items: [
			{
				labelKey: "nav.aiControlCenter",
				defaultLabel: "AI Control Center",
				icon: Sparkles,
				path: "/",
				dataOnboarding: "nav-ai-control",
			},
			{
				labelKey: "nav.engineering",
				defaultLabel: "Engineering Workspace",
				icon: Calculator,
				path: "/engineering",
				dataOnboarding: "nav-engineering",
			},
			{
				labelKey: "nav.projects",
				defaultLabel: "Project & Models",
				icon: FolderKanban,
				path: "/projects",
				dataOnboarding: "nav-projects",
			},
			{
				labelKey: "nav.workflow",
				defaultLabel: "Review & Audit",
				icon: ShieldCheck,
				path: "/workflow",
				dataOnboarding: "nav-workflow",
			},
			{
				labelKey: "nav.reports",
				defaultLabel: "Reports & Artifacts",
				icon: FileText,
				path: "/reports",
				dataOnboarding: "nav-reports",
			},
			{
				labelKey: "nav.settings",
				defaultLabel: "Settings & Admin",
				icon: Settings,
				path: "/settings",
				dataOnboarding: "nav-settings",
			},
		],
	},
	{
		id: "engineering-modules",
		labelKey: "nav.group.engineeringModules",
		defaultLabel: "Engineering Modules",
		items: [
			{
				labelKey: "nav.engineeringFireAI",
				defaultLabel: "FireAI Analysis",
				icon: Flame,
				path: "/engineering/fireai",
			},
			{
				labelKey: "nav.generativeDesign",
				defaultLabel: "Generative Design",
				icon: Sparkles,
				path: "/engineering/generative",
			},
			{
				labelKey: "nav.topology",
				defaultLabel: "Topology & SLD",
				icon: Network,
				path: "/engineering/topology",
			},
			{
				labelKey: "nav.qomn",
				defaultLabel: "QOMN Kernel",
				icon: Calculator,
				path: "/engineering/qomn",
			},
			{
				labelKey: "nav.guards",
				defaultLabel: "Physics Guards",
				icon: Shield,
				path: "/engineering/guards",
			},
			{
				labelKey: "nav.pipelineLayers",
				defaultLabel: "Pipeline Layers",
				icon: Layers,
				path: "/engineering/pipeline",
			},
			{
				labelKey: "nav.autocad",
				defaultLabel: "AutoCAD",
				icon: PencilRuler,
				path: "/autocad",
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
				labelKey: "nav.etap",
				defaultLabel: "ETAP Bridge",
				icon: Server,
				path: "/etap",
			},
			{
				labelKey: "nav.facp",
				defaultLabel: "FACP Selector",
				icon: Cpu,
				path: "/facp",
			},
			{
				labelKey: "nav.fireAlarmDesigner",
				defaultLabel: "Fire Alarm Designer",
				icon: Flame,
				path: "/fire-alarm",
			},
			{
				labelKey: "nav.devices",
				defaultLabel: "Device Catalog",
				icon: Cpu,
				path: "/devices",
			},
			{
				labelKey: "nav.elements",
				defaultLabel: "Elements",
				icon: Layers,
				path: "/elements",
			},
			{
				labelKey: "nav.connections",
				defaultLabel: "Connections",
				icon: Cable,
				path: "/connections",
			},
			{
				labelKey: "nav.conflicts",
				defaultLabel: "Conflicts",
				icon: AlertTriangle,
				path: "/conflicts",
			},
			{
				labelKey: "nav.cadTools",
				defaultLabel: "CAD Tools",
				icon: PenLine,
				path: "/cad-tools",
			},
			{
				labelKey: "nav.dwg",
				defaultLabel: "DWG Parser",
				icon: FileText,
				path: "/dwg",
			},
			{
				labelKey: "nav.marine",
				defaultLabel: "Marine System",
				icon: Ship,
				path: "/marine",
			},
			{
				labelKey: "nav.mining",
				defaultLabel: "Mining System",
				icon: Pickaxe,
				path: "/mining",
				dataOnboarding: "nav-mining",
			},
			{
				labelKey: "nav.bms",
				defaultLabel: "BMS Telemetry",
				icon: Activity,
				path: "/bms",
			},
			{
				labelKey: "nav.analysis",
				defaultLabel: "Analysis Engine",
				icon: FlaskConical,
				path: "/analysis",
			},
			{
				labelKey: "nav.fdsSimulation",
				defaultLabel: "FDS Simulation",
				icon: Flame,
				path: "/fds-simulation",
				requiredRole: "admin",
			},
			{
				labelKey: "nav.engineeringCopilot",
				defaultLabel: "Eng. Copilot",
				icon: Brain,
				path: "/engineering-copilot",
			},
		],
	},
	{
		id: "project-context",
		labelKey: "nav.group.projectContext",
		defaultLabel: "Project & Digital Twin",
		items: [
			{
				labelKey: "nav.dashboard",
				defaultLabel: "Dashboard",
				icon: LayoutDashboard,
				path: "/dashboard",
				dataOnboarding: "nav-dashboard",
			},
			{
				labelKey: "nav.digitalTwin",
				defaultLabel: "Digital Twin 3D",
				icon: Box,
				path: "/digital-twin",
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
				labelKey: "nav.simready",
				defaultLabel: "SimReady Assets",
				icon: Sparkles,
				path: "/simready",
			},
			{
				labelKey: "nav.bimProviders",
				defaultLabel: "BIM Providers",
				icon: Building2,
				path: "/bim-providers",
			},
			{
				labelKey: "nav.ifc43Mapping",
				defaultLabel: "IFC 4.3 Mapping",
				icon: Globe,
				path: "/ifc43-mapping",
				requiredRole: "admin",
			},
			{
				labelKey: "nav.sync",
				defaultLabel: "Data Sync",
				icon: RotateCcw,
				path: "/sync",
			},
			{
				labelKey: "nav.aps",
				defaultLabel: "APS Cloud",
				icon: Globe,
				path: "/aps",
			},
			{
				labelKey: "nav.environment",
				defaultLabel: "Environment",
				icon: CloudSun,
				path: "/environment",
			},
			{
				labelKey: "nav.airQuality",
				defaultLabel: "Air Quality",
				icon: CloudSun,
				path: "/environment/air-quality",
			},
			{
				labelKey: "nav.context",
				defaultLabel: "Context Engine",
				icon: Globe,
				path: "/environment/context",
			},
			{
				labelKey: "nav.hazmat",
				defaultLabel: "HazMat Tracker",
				icon: AlertTriangle,
				path: "/environment/hazmat",
			},
		],
	},
	{
		id: "governance-audit",
		labelKey: "nav.group.governanceAudit",
		defaultLabel: "Review, Audit & Intel",
		items: [
			{
				labelKey: "nav.auditTrail",
				defaultLabel: "Audit Trail",
				icon: FileText,
				path: "/audit-trail",
			},
			{
				labelKey: "nav.systemHealth",
				defaultLabel: "System Health",
				icon: HeartPulse,
				path: "/dashboard/system-health",
			},
			{
				labelKey: "nav.monitor",
				defaultLabel: "Live Monitor",
				icon: Activity,
				path: "/monitor",
			},
			{
				labelKey: "nav.agentChat",
				defaultLabel: "Agent Monitor",
				icon: MessageSquare,
				path: "/monitor/agent",
			},
			{
				labelKey: "nav.securityAlerts",
				defaultLabel: "Security Alerts",
				icon: AlertTriangle,
				path: "/security-alerts",
				requiredRole: "admin",
			},
			{
				labelKey: "nav.selfHealing",
				defaultLabel: "Self-Healing",
				icon: Shield,
				path: "/self-healing",
				requiredRole: "admin",
			},
			{
				labelKey: "nav.memory",
				defaultLabel: "Agent Memory",
				icon: Brain,
				path: "/memory",
			},
			{
				labelKey: "nav.graphrag",
				defaultLabel: "GraphRAG Network",
				icon: Network,
				path: "/graphrag",
			},
		],
	},
	{
		id: "deliverables",
		labelKey: "nav.group.deliverables",
		defaultLabel: "Deliverables & Artifacts",
		items: [
			{
				labelKey: "nav.reportGenerator",
				defaultLabel: "Report Generator",
				icon: FilePlus,
				path: "/reports/generate",
			},
			{
				labelKey: "nav.exports",
				defaultLabel: "Deliverables Export",
				icon: Download,
				path: "/exports",
				dataOnboarding: "nav-exports",
				requiredRole: "admin",
			},
			{
				labelKey: "nav.arExport",
				defaultLabel: "AR Visual Export",
				icon: Smartphone,
				path: "/ar-export",
				requiredRole: "admin",
			},
		],
	},
	{
		id: "administration",
		labelKey: "nav.group.administration",
		defaultLabel: "System Administration",
		items: [
			{
				labelKey: "nav.aiAgentSettings",
				defaultLabel: "AI Agent Config",
				icon: Brain,
				path: "/settings/ai-agents",
			},
			{
				labelKey: "nav.cadSettings",
				defaultLabel: "CAD Defaults",
				icon: Settings2,
				path: "/settings/cad",
			},
			{
				labelKey: "nav.databaseAdmin",
				defaultLabel: "Database Admin",
				icon: Database,
				path: "/settings/database",
				requiredRole: "admin",
			},
			{
				labelKey: "nav.billing",
				defaultLabel: "Billing & Subscriptions",
				icon: CreditCard,
				path: "/billing",
			},
			{
				labelKey: "nav.rbac",
				defaultLabel: "RBAC Security",
				icon: Shield,
				path: "/settings/rbac",
				requiredRole: "admin",
			},
			{
				labelKey: "nav.webhooks",
				defaultLabel: "Webhooks",
				icon: Link2,
				path: "/settings/webhooks",
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
				labelKey: "nav.multiDb",
				defaultLabel: "Multi-DB Partitions",
				icon: Database,
				path: "/multi-db",
				requiredRole: "admin",
			},
			{
				labelKey: "nav.advancedSettings",
				defaultLabel: "Advanced Settings",
				icon: Cog,
				path: "/settings/advanced",
				requiredRole: "admin",
			},
			{
				labelKey: "nav.experimental",
				defaultLabel: "Experimental Services",
				icon: FlaskConical,
				path: "/settings/experimental",
				requiredRole: "admin",
			},
		],
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

	// Phase 8: increased from w-60 (240px) to w-64 (256px) for better
	// readability now that group headers are displayed.
	const width = collapsed ? "w-16" : "w-64";

	// Filter groups: hide a group entirely if ALL its items require a role
	// the current user doesn't have. Otherwise, show the group with only
	// the items the user can access.
	const visibleGroups = navGroups
		.map((group) => ({
			...group,
			items: group.items.filter(
				(item) => !item.requiredRole || item.requiredRole === role,
			),
		}))
		.filter((group) => group.items.length > 0);

	return (
		<aside
			className={`sidebar-root ${width} h-full flex flex-col transition-[width] duration-300 ${collapsed ? "collapsed" : ""} ${isRTL ? "order-last" : "order-first"}`}
		>
			{/* Brand header — BAZSPARK wordmark + FACP nameplate subtitle.
                            Phase 14: glass blur + white/10 border → solid graphite + steel hairline.
                            Wordmark switches to Space Grotesk (matches login hero / TopBar title).
                            Subtitle becomes IBM Plex Mono uppercase tracked (FACP nameplate style). */}
			<div className="sidebar-brand flex items-center gap-2.5 px-4 h-12 shrink-0 border-b border-border bg-card">
				<BazSparkLogo size={26} className="shrink-0" />
				{!collapsed && (
					<div className="flex flex-col leading-none">
						<span className="sidebar-brand-wordmark text-xs font-bold tracking-wider text-foreground">BAZSPARK</span>
						<span className="sidebar-brand-subtitle text-[10px] font-mono text-muted-foreground uppercase tracking-widest">Engineering Suite</span>
					</div>
				)}
			</div>

			<nav
				className="flex-1 py-2 overflow-y-auto overflow-x-hidden"
				aria-label="Primary navigation"
			>
				{visibleGroups.map((group, groupIndex) => (
					<div
						key={group.id}
						className={groupIndex > 0 ? "sidebar-group-divider" : ""}
					>
						{!collapsed && (
							<div className="sidebar-group-label px-5" aria-hidden="true">
								{t(group.labelKey, group.defaultLabel)}
							</div>
						)}
						{group.items.map((item) => {
							const isActive =
								location.pathname === item.path ||
								(item.path !== "/dashboard" &&
									location.pathname.startsWith(`${item.path}/`));
							const labelText = t(item.labelKey, item.defaultLabel);
							return (
								<div key={item.path} className="relative px-3 mb-0.5">
									<Link
										to={item.path}
										aria-current={isActive ? "page" : undefined}
										className={`sidebar-nav-item ${isActive ? "active" : ""}`}
										title={collapsed ? labelText : undefined}
										data-onboarding={item.dataOnboarding}
										onMouseEnter={() => routePrefetchMap[item.path]?.()}
									>
										<item.icon
											className="sidebar-nav-icon h-5 w-5" // NOSONAR: typescript:S3358
										/>
										{!collapsed && (
											<span className="sidebar-nav-label">{labelText}</span>
										)}
									</Link>
								</div>
							);
						})}
					</div>
				))}
			</nav>

			{/* Footer — About + collapse. Phase 14: matches the membrane-switch
                            affordance used on the dashboard refresh button (inset shadow on
                            hover = physical depression). Evac-green hover = "go" affordance. */}
			<div className="sidebar-footer shrink-0 p-3">
				{!collapsed && (
					<Link to="/settings" className="sidebar-about-link">
						<Info aria-hidden="true" className="sidebar-about-icon h-5 w-5" />
						<span className="text-sm font-medium">About BAZSPARK</span>
					</Link>
				)}
				<button
					type="button"
					onClick={() => setCollapsed(!collapsed)}
					className="sidebar-collapse-btn"
					aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
					aria-expanded={!collapsed}
					data-onboarding="sidebar-toggle"
				>
					{collapsed ? (
						isRTL ? (
							<ChevronLeft aria-hidden="true" className="h-4 w-4" />
						) : (
							<ChevronRight aria-hidden="true" className="h-4 w-4" />
						)
					) : isRTL ? (
						<ChevronRight aria-hidden="true" className="h-4 w-4" />
					) : (
						<ChevronLeft aria-hidden="true" className="h-4 w-4" />
					)}
				</button>
			</div>
		</aside>
	);
});

Sidebar.displayName = "Sidebar";

export default Sidebar;
