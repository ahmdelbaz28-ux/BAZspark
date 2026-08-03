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
        Sparkles,
        MessageSquare,
        Link2,
        HeartPulse,
        Workflow as WorkflowIcon,
        Settings2,
        Info,
        Pickaxe,
        Key,
        Download,
        Server,
        Globe,
        Smartphone,
        FilePlus,
        PenLine,
        FlaskConical,
        RotateCcw,
        Database,
        Cog,
    } from "lucide-react";
import type React from "react";
import { memo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "react-router";
import { useAuth } from "@/contexts/AuthContext";
import { BazSparkLogo } from "@/components/auth/BazSparkLogo";

// Vercel React Best Practices: network-prefetch — preload lazy chunks on hover
const routePrefetchMap: Record<string, () => Promise<unknown>> = {
        "/dashboard": () => import("@/pages/DashboardPage"),
        "/projects": () => import("@/pages/ProjectsPage"),
        "/engineering": () => import("@/pages/EngineeringPage"),
        "/facp": () => import("@/pages/FACPPage"),
        "/marine": () => import("@/pages/MarinePage"),
        "/mining": () => import("@/pages/MiningPage"),
        "/fire-alarm/designer": () => import("@/components/mockups/engineering/FireAlarmDesigner"),
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
        "/dashboard/system-health": () => import("@/pages/SystemHealthPage"),
        "/engineering/generative": () => import("@/pages/GenerativeDesignPage"),
        "/engineering/fireai": () => import("@/pages/EngineeringFireAIPage"),
        "/engineering/pipeline": () => import("@/pages/PipelineLayersPage"),
        "/engineering/topology": () => import("@/pages/TopologyPage"),
        "/settings/rbac": () => import("@/pages/RbacPage"),
        "/settings/webhooks": () => import("@/pages/WebhookManagementPage"),
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
// Phase 8 (2026-08-03): Sidebar reorganized into grouped sections.
//
// Previously, all 63 nav items were in a single flat list, making it hard
// to find anything. Now they are organized into 9 logical groups:
//   Core, Engineering, CAD & BIM, Domains, Monitoring, Environment,
//   Intelligence, Deliverables, Administration
//
// ALL 63 original paths are preserved — no routes were removed.
// (Verified by comparing the path list before/after the refactor.)
// ═══════════════════════════════════════════════════════════════════════════
const navGroups: NavGroup[] = [
        {
                id: "core",
                labelKey: "nav.group.core",
                defaultLabel: "Core",
                items: [
                        {
                                labelKey: "nav.dashboard",
                                defaultLabel: "Dashboard",
                                icon: LayoutDashboard,
                                path: "/dashboard",
                                dataOnboarding: "nav-dashboard",
                        },
                        {
                                labelKey: "nav.systemHealth",
                                defaultLabel: "System Health",
                                icon: HeartPulse,
                                path: "/dashboard/system-health",
                        },
                        {
                                labelKey: "nav.projects",
                                defaultLabel: "Projects",
                                icon: FolderKanban,
                                path: "/projects",
                                dataOnboarding: "nav-projects",
                        },
                ],
        },
        {
                id: "engineering",
                labelKey: "nav.group.engineering",
                defaultLabel: "Engineering",
                items: [
                        {
                                labelKey: "nav.engineering",
                                defaultLabel: "Engineering Hub",
                                icon: Calculator,
                                path: "/engineering",
                                dataOnboarding: "nav-engineering",
                        },
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
                                labelKey: "nav.pipelineLayers",
                                defaultLabel: "Pipeline Layers",
                                icon: Layers,
                                path: "/engineering/pipeline",
                        },
                        {
                                labelKey: "nav.topology",
                                defaultLabel: "Topology",
                                icon: Network,
                                path: "/engineering/topology",
                        },
                        {
                                labelKey: "nav.qomn",
                                defaultLabel: "QOMN Calculator",
                                icon: Calculator,
                                path: "/engineering/qomn",
                        },
                        {
                                labelKey: "nav.guards",
                                defaultLabel: "Physics Guards",
                                icon: Shield,
                                path: "/engineering/guards",
                        },
                ],
        },
        {
                id: "cad-bim",
                labelKey: "nav.group.cadBim",
                defaultLabel: "CAD & BIM",
                items: [
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
                                labelKey: "nav.fireAlarmDesigner",
                                defaultLabel: "Fire Alarm Designer",
                                icon: Siren,
                                path: "/fire-alarm/designer",
                                dataOnboarding: "nav-fire-alarm-designer",
                        },
                        {
                                labelKey: "nav.digitalTwin",
                                defaultLabel: "Digital Twin",
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
                                labelKey: "nav.etap",
                                defaultLabel: "ETAP Integration",
                                icon: Server,
                                path: "/etap",
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
                ],
        },
        {
                id: "domains",
                labelKey: "nav.group.domains",
                defaultLabel: "Domains",
                items: [
                        {
                                labelKey: "nav.marine",
                                defaultLabel: "Marine",
                                icon: Ship,
                                path: "/marine",
                        },
                        {
                                labelKey: "nav.mining",
                                defaultLabel: "Mining",
                                icon: Pickaxe,
                                path: "/mining",
                                dataOnboarding: "nav-mining",
                        },
                        {
                                labelKey: "nav.facp",
                                defaultLabel: "FACP Selector",
                                icon: Cpu,
                                path: "/facp",
                        },
                        {
                                labelKey: "nav.devices",
                                defaultLabel: "Devices",
                                icon: Cpu,
                                path: "/devices",
                        },
                        {
                                labelKey: "nav.bms",
                                defaultLabel: "BMS",
                                icon: Activity,
                                path: "/bms",
                        },
                ],
        },
        {
                id: "monitoring",
                labelKey: "nav.group.monitoring",
                defaultLabel: "Monitoring",
                items: [
                        {
                                labelKey: "nav.monitor",
                                defaultLabel: "Monitor",
                                icon: Activity,
                                path: "/monitor",
                        },
                        {
                                labelKey: "nav.agentChat",
                                defaultLabel: "Agent Chat",
                                icon: MessageSquare,
                                path: "/monitor/agent",
                        },
                        {
                                labelKey: "nav.auditTrail",
                                defaultLabel: "Audit Trail",
                                icon: FileText,
                                path: "/audit-trail",
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
                                labelKey: "nav.sync",
                                defaultLabel: "Sync",
                                icon: RotateCcw,
                                path: "/sync",
                        },
                ],
        },
        {
                id: "environment",
                labelKey: "nav.group.environment",
                defaultLabel: "Environment",
                items: [
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
                                defaultLabel: "Context",
                                icon: Globe,
                                path: "/environment/context",
                        },
                        {
                                labelKey: "nav.hazmat",
                                defaultLabel: "HazMat",
                                icon: AlertTriangle,
                                path: "/environment/hazmat",
                        },
                ],
        },
        {
                id: "intelligence",
                labelKey: "nav.group.intelligence",
                defaultLabel: "Intelligence",
                items: [
                        {
                                labelKey: "nav.memory",
                                defaultLabel: "Memory",
                                icon: Brain,
                                path: "/memory",
                        },
                        {
                                labelKey: "nav.graphrag",
                                defaultLabel: "GraphRAG",
                                icon: Network,
                                path: "/graphrag",
                        },
                        {
                                labelKey: "nav.workflow",
                                defaultLabel: "Workflows",
                                icon: WorkflowIcon,
                                path: "/workflow",
                        },
                        {
                                labelKey: "nav.engineeringCopilot",
                                defaultLabel: "Eng. Copilot",
                                icon: Brain,
                                path: "/engineering-copilot",
                        },
                        {
                                labelKey: "nav.fdsSimulation",
                                defaultLabel: "FDS Simulation",
                                icon: Flame,
                                path: "/fds-simulation",
                                requiredRole: "admin",
                        },
                ],
        },
        {
                id: "deliverables",
                labelKey: "nav.group.deliverables",
                defaultLabel: "Deliverables",
                items: [
                        {
                                labelKey: "nav.reports",
                                defaultLabel: "Reports",
                                icon: FileText,
                                path: "/reports",
                                dataOnboarding: "nav-reports",
                        },
                        {
                                labelKey: "nav.reportGenerator",
                                defaultLabel: "Report Generator",
                                icon: FilePlus,
                                path: "/reports/generate",
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
                                labelKey: "nav.arExport",
                                defaultLabel: "AR Export",
                                icon: Smartphone,
                                path: "/ar-export",
                                requiredRole: "admin",
                        },
                        {
                                labelKey: "nav.analysis",
                                defaultLabel: "Analysis",
                                icon: FlaskConical,
                                path: "/analysis",
                        },
                ],
        },
        {
                id: "administration",
                labelKey: "nav.group.administration",
                defaultLabel: "Administration",
                items: [
                        {
                                labelKey: "nav.settings",
                                defaultLabel: "Settings",
                                icon: Settings,
                                path: "/settings",
                                dataOnboarding: "nav-settings",
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
                                defaultLabel: "Experimental",
                                icon: FlaskConical,
                                path: "/settings/experimental",
                                requiredRole: "admin",
                        },
                        {
                                labelKey: "nav.rbac",
                                defaultLabel: "RBAC",
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
                                defaultLabel: "Multi-DB",
                                icon: Database,
                                path: "/multi-db",
                                requiredRole: "admin",
                        },
                        {
                                labelKey: "nav.aps",
                                defaultLabel: "APS Cloud",
                                icon: Globe,
                                path: "/aps",
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
                        className={`${width} h-full glass flex flex-col transition-[width] duration-300 ${isRTL ? "order-last" : "order-first"}`}
                        style={{
                                borderRight: isRTL ? "none" : "1px solid rgba(255,255,255,0.1)",
                                borderLeft: isRTL ? "1px solid rgba(255,255,255,0.1)" : "none",
                        }}
                >
                        {/* Brand header — BAZSPARK with official flame logo */}
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
                                className="flex-1 py-2 overflow-y-auto overflow-x-hidden"
                                aria-label="Primary navigation"
                        >
                                {visibleGroups.map((group, groupIndex) => (
                                        <div key={group.id} className={groupIndex > 0 ? "mt-4" : ""}>
                                                {!collapsed && (
                                                        <div
                                                                className="px-5 mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
                                                                aria-hidden="true"
                                                        >
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
                                                                                className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-[color,background-color,border-color] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background ${
                                                                                        isActive
                                                                                                ? "bg-cyan-400/10 text-cyan-300 border border-cyan-400/20"
                                                                                                : "text-muted-foreground hover:bg-white/5 hover:text-foreground border border-transparent"
                                                                                }`}
                                                                                title={collapsed ? labelText : undefined}
                                                                                data-onboarding={item.dataOnboarding}
                                                                                onMouseEnter={() => routePrefetchMap[item.path]?.()}
                                                                        >
                                                                                <item.icon
                                                                                        className={`shrink-0 h-5 w-5 ${isActive ? "text-cyan-300" : ""}`}  // NOSONAR: typescript:S3358
                                                                                />
                                                                                {!collapsed && (
                                                                                        <span className="truncate text-sm font-medium tracking-wide">
                                                                                                {labelText}
                                                                                        </span>
                                                                                )}
                                                                        </Link>
                                                                </div>
                                                        );
                                                })}
                                        </div>
                                ))}
                        </nav>

                        {/* Footer — About + collapse */}
                        <div className="border-t border-white/10 shrink-0 p-3">
                                {!collapsed && (
                                        <Link
                                                to="/settings"
                                                className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-muted-foreground hover:bg-white/5 hover:text-foreground cursor-pointer transition-[color,background-color,border-color] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                                        >
                                                <Info aria-hidden="true" className="h-5 w-5 shrink-0" />
                                                <span className="text-sm font-medium">About BAZSPARK</span>
                                        </Link>
                                )}
                                <button type="button"
                                        onClick={() => setCollapsed(!collapsed)}
                                        className="flex items-center justify-center w-full py-2.5 rounded-lg text-muted-foreground hover:text-cyan-400 hover:bg-white/5 cursor-pointer transition-[color,background-color,border-color] duration-200 mt-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
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
