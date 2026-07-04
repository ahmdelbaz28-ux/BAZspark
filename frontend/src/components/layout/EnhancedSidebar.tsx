import React, { useState } from "react";
import { useLocation, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  FolderOpen,
  Layers2,
  GitFork,
  AlertTriangle,
  FlameKindling,
  Box,
  FileBarChart2,
  Cpu,
  Bolt,
  Building2,
  PenLine,
  ArrowLeftRight,
  History,
  SlidersHorizontal,
  Wind,
  ShieldAlert,
  Download,
  ClipboardList,
  Activity,
  BellRing,
  Settings,
  Settings2,
  ChevronRight,
  PanelLeftClose,
  PanelLeft,
  Bot,
  Thermometer,
  Cable,
} from "lucide-react";

/* ---------------------------------------------------------- */
/*  NAV DATA                                                    */
/* ---------------------------------------------------------- */

interface NavItem {
  labelKey: string;
  label: string;
  icon: React.ElementType;
  path: string;
  badge?: string;
  badgeVariant?: "danger" | "warning" | "accent" | "success";
  dataOnboarding?: string;
}

interface NavGroup {
  key: string;
  label: string;
  items: NavItem[];
  separator?: boolean;
}

const navGroups: NavGroup[] = [
  {
    key: "core",
    label: "Workspace",
    items: [
      { labelKey: "nav.dashboard",    label: "Dashboard",    icon: LayoutDashboard, path: "/dashboard",   dataOnboarding: "nav-dashboard" },
      { labelKey: "nav.projects",     label: "Projects",     icon: FolderOpen,      path: "/projects",    dataOnboarding: "nav-projects"  },
      { labelKey: "nav.elements",     label: "Elements",     icon: Layers2,         path: "/elements"   },
      { labelKey: "nav.connections",  label: "Connections",  icon: Cable,           path: "/connections" },
      { labelKey: "nav.conflicts",    label: "Conflicts",    icon: AlertTriangle,   path: "/conflicts",  badge: "3", badgeVariant: "danger" },
    ],
  },
  {
    key: "engineering",
    label: "Engineering",
    separator: true,
    items: [
      { labelKey: "nav.engineering",     label: "Console",       icon: Cpu,          path: "/engineering",       dataOnboarding: "nav-engineering" },
      { labelKey: "nav.qomn",            label: "QOMN Calc",     icon: Bolt,         path: "/engineering/qomn"  },
      { labelKey: "nav.facp",            label: "FACP Designer", icon: FlameKindling, path: "/engineering/facp" },
      { labelKey: "nav.physicsGuards",   label: "Physics Guards",icon: ShieldAlert,  path: "/engineering/guards", badge: "safe", badgeVariant: "success" },
      { labelKey: "nav.fireAlarmDesigner", label: "Fire Alarm", icon: BellRing,     path: "/fire-alarm/designer", dataOnboarding: "nav-fire-alarm-designer" },
    ],
  },
  {
    key: "cad",
    label: "BIM & CAD",
    separator: true,
    items: [
      { labelKey: "nav.revit",         label: "Revit",          icon: Building2,      path: "/revit"               },
      { labelKey: "nav.revitCreate",   label: "Revit · Create", icon: Building2,      path: "/revit/create"        },
      { labelKey: "nav.revitElements", label: "Revit · Items",  icon: Layers2,        path: "/revit/elements"      },
      { labelKey: "nav.autocad",       label: "AutoCAD",        icon: PenLine,        path: "/autocad"             },
      { labelKey: "nav.autocadDraw",   label: "AutoCAD · Draw", icon: PenLine,        path: "/autocad/draw"        },
      { labelKey: "nav.digitalTwin",   label: "Digital Twin",   icon: Box,            path: "/digital-twin"        },
      { labelKey: "nav.dtConvert",     label: "DT · Convert",   icon: ArrowLeftRight, path: "/digital-twin/convert"},
      { labelKey: "nav.dtConfig",      label: "DT · Config",    icon: SlidersHorizontal, path: "/digital-twin/config"},
      { labelKey: "nav.dtHistory",     label: "DT · History",   icon: History,        path: "/digital-twin/history"},
    ],
  },
  {
    key: "environment",
    label: "Environment",
    separator: true,
    items: [
      { labelKey: "nav.environmentContext", label: "Weather",   icon: Wind,         path: "/environment/context"   },
      { labelKey: "nav.airQuality",         label: "Air Quality",icon: Thermometer, path: "/environment/air-quality"},
      { labelKey: "nav.hazmat",             label: "HazMat DB", icon: AlertTriangle, path: "/environment/hazmat"   },
    ],
  },
  {
    key: "reporting",
    label: "Reports",
    separator: true,
    items: [
      { labelKey: "nav.reports",     label: "Reports",       icon: FileBarChart2,  path: "/reports",      dataOnboarding: "nav-reports" },
      { labelKey: "nav.exports",     label: "Export",        icon: Download,       path: "/exports"       },
      { labelKey: "nav.auditTrail",  label: "Audit Trail",   icon: ClipboardList,  path: "/audit-trail"   },
    ],
  },
  {
    key: "monitoring",
    label: "Monitoring",
    separator: true,
    items: [
      { labelKey: "nav.systemHealth",    label: "System Health", icon: Activity,   path: "/system-health"   },
      { labelKey: "nav.agentActivity",   label: "AI Agent",      icon: Bot,        path: "/agent-chat",     badge: "live", badgeVariant: "accent" },
      { labelKey: "nav.securityAlerts",  label: "Security",      icon: BellRing,   path: "/security-alerts" },
    ],
  },
  {
    key: "settings",
    label: "Settings",
    separator: true,
    items: [
      { labelKey: "nav.settings",         label: "Preferences",     icon: Settings,  path: "/settings",          dataOnboarding: "nav-settings" },
      { labelKey: "nav.advancedSettings", label: "Advanced",        icon: Settings2, path: "/settings/advanced" },
    ],
  },
];

/* ---------------------------------------------------------- */
/*  BADGE COMPONENT                                            */
/* ---------------------------------------------------------- */

const NavBadge: React.FC<{ text: string; variant?: NavItem["badgeVariant"] }> = ({
  text, variant = "accent"
}) => {
  const colors: Record<string, string> = {
    danger:  "bg-red-500/15 text-red-400",
    warning: "bg-amber-500/15 text-amber-400",
    accent:  "bg-cyan-500/15 text-cyan-400",
    success: "bg-emerald-500/15 text-emerald-400",
  };
  return (
    <span className={`ml-auto text-[10px] font-semibold tracking-wider uppercase px-1.5 py-0.5 rounded ${colors[variant]}`}>
      {text}
    </span>
  );
};

/* ---------------------------------------------------------- */
/*  NAV GROUP COMPONENT                                        */
/* ---------------------------------------------------------- */

interface GroupProps {
  group: NavGroup;
  expanded: boolean;
  collapsed: boolean; // sidebar icon-only mode
  onToggle: () => void;
  currentPath: string;
}

const NavGroupSection: React.FC<GroupProps> = ({ group, expanded, collapsed, onToggle, currentPath }) => {
  const { t } = useTranslation();
  const isAnyActive = group.items.some(i => currentPath === i.path || currentPath.startsWith(i.path + "/"));

  return (
    <div className={group.separator ? "mt-2 pt-2 border-t border-[#141418]" : ""}>
      {/* Group header — hidden in icon-only mode */}
      {!collapsed && (
        <button
          onClick={onToggle}
          className={`w-full flex items-center gap-2 px-3 py-1 mb-0.5 rounded text-[10px] font-semibold tracking-widest uppercase
            transition-colors duration-150 cursor-pointer select-none
            ${isAnyActive ? "text-[#6a6a80]" : "text-[#2e2e3a] hover:text-[#4e4e62]"}`}
          aria-expanded={expanded}
        >
          <span className="flex-1 text-left">{group.label}</span>
          <ChevronRight
            size={10}
            className={`transition-transform duration-200 ${expanded ? "rotate-90" : ""} opacity-50`}
          />
        </button>
      )}

      {/* Nav items */}
      {(expanded || collapsed) && (
        <div className={`${collapsed ? "py-1" : "pb-1"} space-y-px`}>
          {group.items.map(item => {
            const Icon = item.icon;
            const isActive = currentPath === item.path || currentPath.startsWith(item.path + "/");
            const label = t(item.labelKey, item.label);

            return (
              <Link
                key={item.path}
                to={item.path}
                data-onboarding={item.dataOnboarding}
                title={collapsed ? label : undefined}
                className={`
                  group relative flex items-center gap-2.5 rounded select-none
                  transition-all duration-150
                  ${collapsed
                    ? "justify-center w-9 h-9 mx-auto"
                    : "px-3 py-[7px] mx-1"}
                  ${isActive
                    ? "bg-[#1a1a24] text-[#f0f0f2]"
                    : "text-[#6a6a80] hover:bg-[#141418] hover:text-[#c0c0cc]"}
                `}
              >
                {/* Active indicator bar */}
                {isActive && !collapsed && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-5 bg-[#00d4ff] rounded-r" />
                )}

                {/* Icon container */}
                <span className={`flex items-center justify-center flex-shrink-0 transition-transform duration-150 group-hover:scale-110 ${isActive ? "text-[#00d4ff]" : ""}`}>
                  <Icon size={15} strokeWidth={isActive ? 2.5 : 1.8} />
                </span>

                {/* Label */}
                {!collapsed && (
                  <span className="flex-1 text-[12.5px] font-medium leading-none truncate">
                    {label}
                  </span>
                )}

                {/* Badge */}
                {!collapsed && item.badge && (
                  <NavBadge text={item.badge} variant={item.badgeVariant} />
                )}

                {/* Tooltip in collapsed mode */}
                {collapsed && (
                  <span className="
                    pointer-events-none absolute left-full ml-2 z-50
                    bg-[#1e1e28] border border-[#2a2a36] text-[#f0f0f2]
                    text-[11px] font-medium whitespace-nowrap
                    px-2.5 py-1.5 rounded shadow-lg
                    opacity-0 group-hover:opacity-100
                    translate-x-1 group-hover:translate-x-0
                    transition-all duration-150
                  ">
                    {label}
                    {item.badge && (
                      <NavBadge text={item.badge} variant={item.badgeVariant} />
                    )}
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
};

/* ---------------------------------------------------------- */
/*  MAIN SIDEBAR                                               */
/* ---------------------------------------------------------- */

const EnhancedSidebar: React.FC = () => {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({
    core: true,
    engineering: true,
    cad: false,
    environment: false,
    reporting: false,
    monitoring: true,
    settings: false,
  });

  const toggle = (key: string) =>
    setExpandedGroups(prev => ({ ...prev, [key]: !prev[key] }));

  return (
    <aside
      className={`
        relative flex flex-col shrink-0 h-screen
        bg-[#0c0c10] border-r border-[#1a1a20]
        transition-all duration-250
        ${collapsed ? "w-[52px]" : "w-[220px]"}
      `}
      style={{ transition: "width 250ms cubic-bezier(0.16,1,0.3,1)" }}
    >
      {/* ---- Logo bar ---- */}
      <div className={`
        flex items-center shrink-0 h-12 border-b border-[#1a1a20]
        ${collapsed ? "justify-center px-0" : "px-4 gap-2.5"}
      `}>
        {/* Logo mark */}
        <span className="flex items-center justify-center w-7 h-7 rounded bg-[#00d4ff] flex-shrink-0">
          <FlameKindling size={15} strokeWidth={2.5} className="text-[#0a0a0b]" />
        </span>

        {!collapsed && (
          <div className="flex-1 min-w-0">
            <div className="text-[13px] font-semibold tracking-tight text-[#f0f0f2]">BAZSPARK</div>
            <div className="text-[10px] text-[#3a3a50] font-medium tracking-wider uppercase leading-none mt-0.5">Fire Safety</div>
          </div>
        )}
      </div>

      {/* ---- Scrollable nav ---- */}
      <nav className="flex-1 overflow-y-auto overflow-x-hidden py-2 space-y-0">
        {navGroups.map(group => (
          <NavGroupSection
            key={group.key}
            group={group}
            expanded={expandedGroups[group.key] ?? false}
            collapsed={collapsed}
            onToggle={() => toggle(group.key)}
            currentPath={location.pathname}
          />
        ))}
      </nav>

      {/* ---- Collapse toggle ---- */}
      <div className="shrink-0 border-t border-[#1a1a20] p-2">
        <button
          onClick={() => setCollapsed(v => !v)}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="
            w-full flex items-center justify-center gap-2 h-8 rounded
            text-[#3a3a50] hover:text-[#8a8a9a] hover:bg-[#141418]
            transition-all duration-150 text-[11px] font-medium
          "
        >
          {collapsed
            ? <PanelLeft size={14} />
            : <><PanelLeftClose size={14} /><span>Collapse</span></>
          }
        </button>
      </div>
    </aside>
  );
};

export default EnhancedSidebar;
