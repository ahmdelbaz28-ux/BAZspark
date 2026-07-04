import React from "react";
import { useLocation, Link } from "react-router-dom";
import { ChevronRight } from "lucide-react";

interface Crumb { label: string; path?: string; }

const CRUMB_MAP: Record<string, Crumb[]> = {
  "/dashboard":             [{ label: "Dashboard" }],
  "/projects":              [{ label: "Projects" }],
  "/engineering":           [{ label: "Engineering" }, { label: "Console" }],
  "/engineering/qomn":      [{ label: "Engineering", path: "/engineering" }, { label: "QOMN Calculator" }],
  "/engineering/facp":      [{ label: "Engineering", path: "/engineering" }, { label: "FACP Designer" }],
  "/engineering/guards":    [{ label: "Engineering", path: "/engineering" }, { label: "Physics Guards" }],
  "/fire-alarm/designer":   [{ label: "Fire Alarm" }, { label: "Designer" }],
  "/reports":               [{ label: "Reports" }],
  "/elements":              [{ label: "Elements" }],
  "/connections":           [{ label: "Connections" }],
  "/conflicts":             [{ label: "Conflicts" }],
  "/revit":                 [{ label: "BIM" }, { label: "Revit" }],
  "/revit/create":          [{ label: "BIM" }, { label: "Revit", path: "/revit" }, { label: "Create" }],
  "/revit/elements":        [{ label: "BIM" }, { label: "Revit", path: "/revit" }, { label: "Elements" }],
  "/autocad":               [{ label: "BIM" }, { label: "AutoCAD" }],
  "/autocad/draw":          [{ label: "BIM" }, { label: "AutoCAD", path: "/autocad" }, { label: "Draw" }],
  "/digital-twin":          [{ label: "Digital Twin" }],
  "/digital-twin/convert":  [{ label: "Digital Twin", path: "/digital-twin" }, { label: "Convert" }],
  "/digital-twin/config":   [{ label: "Digital Twin", path: "/digital-twin" }, { label: "Config" }],
  "/digital-twin/history":  [{ label: "Digital Twin", path: "/digital-twin" }, { label: "History" }],
  "/settings":              [{ label: "Settings" }],
  "/settings/advanced":     [{ label: "Settings", path: "/settings" }, { label: "Advanced" }],
  "/system-health":         [{ label: "Monitoring" }, { label: "System Health" }],
  "/agent-chat":            [{ label: "AI" }, { label: "Agent Chat" }],
  "/exports":               [{ label: "Reports" }, { label: "Export Manager" }],
  "/audit-trail":           [{ label: "Reports" }, { label: "Audit Trail" }],
  "/environment/context":   [{ label: "Environment" }, { label: "Weather & Geocoding" }],
  "/environment/air-quality":[{ label: "Environment" }, { label: "Air Quality" }],
  "/environment/hazmat":    [{ label: "Environment" }, { label: "HazMat Database" }],
};

const Breadcrumbs: React.FC = () => {
  const { pathname } = useLocation();
  const isRTL = document.documentElement.dir === "rtl";

  const crumbs = CRUMB_MAP[pathname];
  if (!crumbs || pathname === "/dashboard") return null;

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center h-8 px-4 gap-1 bg-[#0a0a0e] border-b border-[#131318]"
    >
      {crumbs.map((crumb, idx) => {
        const isLast = idx === crumbs.length - 1;
        return (
          <React.Fragment key={idx}>
            {idx > 0 && (
              <ChevronRight
                size={11}
                strokeWidth={1.5}
                className={`text-[#2a2a36] flex-shrink-0 ${isRTL ? "rtl-flip" : ""}`}
              />
            )}
            {crumb.path && !isLast ? (
              <Link
                to={crumb.path}
                className="text-[11px] font-medium text-[#4a4a5c] hover:text-[#8a8a9e] transition-colors duration-150 whitespace-nowrap"
              >
                {crumb.label}
              </Link>
            ) : (
              <span
                className={`text-[11px] font-medium whitespace-nowrap ${
                  isLast ? "text-[#9a9ab0]" : "text-[#4a4a5c]"
                }`}
              >
                {crumb.label}
              </span>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
};

export default Breadcrumbs;
