import React, { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import { Home } from "lucide-react";
import Sidebar from "./Sidebar";
import StatusBar from "@/components/layout/StatusBar";
import TopBar from "@/components/layout/TopBar";
import {
        Breadcrumb,
        BreadcrumbItem,
        BreadcrumbLink,
        BreadcrumbList,
        BreadcrumbPage,
        BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

interface AppShellProps {
        children: React.ReactNode;
        isConnected: boolean;
        backendUrl: string;
        environment: string;
        onHelpOpen: () => void;
        onSearchOpen?: () => void;
        currentLanguage: string;
        onLanguageChange: (lang: string) => void;
}

// NAV-004 FIX: Route label map for breadcrumb navigation
const routeLabelMap: Record<string, string> = {
        "/dashboard": "nav.dashboard",
        "/projects": "nav.projects",
        "/engineering": "nav.engineering",
        "/facp": "nav.facp",
        "/marine": "nav.marine",
        "/mining": "nav.mining",
        "/fire-alarm/designer": "nav.fireAlarmDesigner",
        "/autocad": "nav.autocad",
        "/autocad/draw": "nav.autocadDraw",
        "/revit": "nav.revit",
        "/revit/create": "nav.revitCreate",
        "/revit/elements": "nav.revitElements",
        "/digital-twin": "nav.digitalTwin",
        "/digital-twin/convert": "nav.dtConvert",
        "/digital-twin/config": "nav.dtConfig",
        "/digital-twin/history": "nav.dtHistory",
        "/reports": "nav.reports",
        "/exports": "nav.exports",
        "/etap": "nav.etap",
        "/environment": "nav.environment",
        "/monitor": "nav.monitor",
        "/self-healing": "nav.selfHealing",
        "/memory": "nav.memory",
        "/graphrag": "nav.graphrag",
        "/workflow": "nav.workflow",
        "/elements": "nav.elements",
        "/connections": "nav.connections",
        "/conflicts": "nav.conflicts",
        "/settings": "nav.settings",
        "/api-keys": "nav.apiKeys",
        "/fds-simulation": "nav.fdsSimulation",
        "/bim-providers": "nav.bimProviders",
        "/ifc43-mapping": "nav.ifc43Mapping",
        "/ar-export": "nav.arExport",
        "/webhook-management": "nav.webhookManagement",
        "/generative-design": "nav.generativeDesign",
        "/topology": "nav.topology",
        "/rbac": "nav.rbac",
};

// NAV-004 FIX: Build breadcrumb segments from path
function buildBreadcrumbSegments(
        pathname: string,
): Array<{ label: string; path: string; isLast: boolean }> {
        const segments: Array<{ label: string; path: string; isLast: boolean }> = [];

        // Always add Home as first item
        segments.push({ label: "nav.dashboard", path: "/dashboard", isLast: false });

        // Check for exact route match first
        const exactMatch = routeLabelMap[pathname];
        if (exactMatch && pathname !== "/dashboard") {
                segments.push({ label: exactMatch, path: pathname, isLast: true });
        } else if (pathname === "/dashboard") {
                segments[0].isLast = true;
        } else {
                // Build from path segments
                const parts = pathname.split("/").filter(Boolean);
                let currentPath = "";
                for (let i = 0; i < parts.length; i++) {
                        currentPath += `/${parts[i]}`;
                        const label = routeLabelMap[currentPath] || parts[i];
                        segments.push({
                                label,
                                path: currentPath,
                                isLast: i === parts.length - 1,
                        });
                }
        }

        return segments;
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
}) => {
        const isRTL = document.documentElement.dir === "rtl";
        const location = useLocation();
        const { t } = useTranslation();

        // NAV-003 FIX: Mobile sidebar toggle state
        const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

        // Close mobile sidebar on route change
        useEffect(() => {
                setMobileSidebarOpen(false);
        }, [location.pathname]);

        // Close mobile sidebar on Escape key
        useEffect(() => {
                const handleKeyDown = (e: KeyboardEvent) => {
                        if (e.key === "Escape" && mobileSidebarOpen) {
                                setMobileSidebarOpen(false);
                        }
                };
                document.addEventListener("keydown", handleKeyDown);
                return () => document.removeEventListener("keydown", handleKeyDown);
        }, [mobileSidebarOpen]);

        const handleMobileSidebarToggle = useCallback(() => {
                setMobileSidebarOpen((prev) => !prev);
        }, []);

        // NAV-004 FIX: Build breadcrumb from current route
        const breadcrumbSegments = buildBreadcrumbSegments(location.pathname);

        return (
                <div
                        className="h-screen w-screen flex overflow-hidden bg-background relative"
                        dir={isRTL ? "rtl" : "ltr"}
                >
                        {/* NAV-003 FIX: Mobile sidebar overlay */}
                        {mobileSidebarOpen && (
                                <div
                                        className="sidebar-mobile-overlay md:hidden"
                                        onClick={() => setMobileSidebarOpen(false)}
                                        aria-hidden="true"
                                />
                        )}

                        {/* NAV-003 FIX: Sidebar with mobile responsive support */}
                        <div
                                className={`${
                                        mobileSidebarOpen
                                                ? "sidebar-mobile open md:!static md:!transform-none"
                                                : "sidebar-mobile md:!static md:!transform-none"
                                }`}
                        >
                                <Sidebar />
                        </div>

                        <div className="flex-1 flex flex-col min-w-0">
                                <TopBar
                                        isConnected={isConnected}
                                        onHelpOpen={onHelpOpen}
                                        onSearchOpen={onSearchOpen}
                                        currentLanguage={currentLanguage}
                                        onLanguageChange={onLanguageChange}
                                        onMobileSidebarToggle={handleMobileSidebarToggle}
                                />

                                {/* NAV-004 FIX: Breadcrumb navigation */}
                                {/* SC-008 FIX: Breadcrumb with overflow handling */}
                                <div className="breadcrumb-container px-4 lg:px-6 py-2 border-b border-white/5">
                                        <Breadcrumb>
                                                <BreadcrumbList>
                                                        {breadcrumbSegments.map((segment, index) => (
                                                                <React.Fragment key={segment.path}>
                                                                        <BreadcrumbItem>
                                                                                {segment.isLast ? (
                                                                                        <BreadcrumbPage className="text-[13px] text-foreground">
                                                                                                {t(segment.label, segment.label.replace("nav.", ""))}
                                                                                        </BreadcrumbPage>
                                                                                ) : (
                                                                                        <BreadcrumbLink
                                                                                                href={segment.path}
                                                                                                className="text-[13px] text-muted-foreground hover:text-foreground transition-colors"
                                                                                        >
                                                                                                {index === 0 ? (
                                                                                                        <span className="flex items-center gap-1">
                                                                                                                <Home
                                                                                                                        className="h-3 w-3"
                                                                                                                        aria-hidden="true"
                                                                                                                />
                                                                                                                {t(segment.label, "Home")}
                                                                                                        </span>
                                                                                                ) : (
                                                                                                        t(
                                                                                                                segment.label,
                                                                                                                segment.label.replace("nav.", ""),
                                                                                                        )
                                                                                                )}
                                                                                        </BreadcrumbLink>
                                                                                )}
                                                                        </BreadcrumbItem>
                                                                        {!segment.isLast && (
                                                                                <BreadcrumbSeparator className="breadcrumb-separator" />
                                                                        )}
                                                                </React.Fragment>
                                                        ))}
                                                </BreadcrumbList>
                                        </Breadcrumb>
                                </div>

                                <main className="flex-1 overflow-auto bg-background relative">
                                        <div className="relative z-10">{children}</div>
                                </main>

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
