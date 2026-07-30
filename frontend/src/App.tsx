
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { RouteGuard } from "@/components/auth/RouteGuard";
import { PageErrorBoundary } from "@/components/core/PageErrorBoundary";
import { SmoothScroll } from "@/components/interaction/SmoothScroll";
// F-08 FIX (Engineering Review): visible banner when running on mock data.
import { DemoDataBanner } from "@/components/shared/DemoDataBanner";
import type { HelpTopicId } from "@/help/types";
import { ROUTE_HELP_MAP } from "@/help/types";
import { useHealth } from "@/hooks/useApiQuery";
import { AuthProvider } from "@/contexts/AuthContext";
import "./i18n";
import "./styles/globals.css";
import "./styles/typography.css";

// Vercel React Best Practices: Defer non-critical third-party and heavy overlay components
// bundle-defer-third-party + bundle-dynamic-imports
const AskAiButton = lazy(() =>
        import("@/components/ai/AskAiButton").then((m) => ({ default: m.AskAiButton })),
);
const AskAiSheet = lazy(() =>
        import("@/components/ai/AskAiSheet").then((m) => ({ default: m.AskAiSheet })),
);
const CommandPalette = lazy(() =>
        import("@/components/command/CommandPalette"),
);
const AppShell = lazy(() =>
        import("@/components/layout/AppShell").then((m) => ({ default: m.default })),
);
const OnboardingTour = lazy(() =>
        import("@/components/onboarding/OnboardingTour"),
);
const GlobalHelpDrawer = lazy(() =>
        import("@/components/shared/GlobalHelpDrawer").then((m) => ({ default: m.GlobalHelpDrawer })),
);
const MagneticCursor = lazy(() =>
        import("@/components/interaction/MagneticCursor").then((m) => ({ default: m.MagneticCursor })),
);
const LoginPage = lazy(() =>
        import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })),
);

// V242: Lazy-load all page components to enable code splitting.
// This reduces the initial bundle from ~705kB to ~250kB (vendor + app shell).
// Each page becomes its own chunk loaded on-demand when the user navigates.
// The Suspense fallback shows a minimal loader while the chunk downloads.
const PageLoader = () => (
        <div className="flex items-center justify-center min-h-[60vh]">
                <div
                        className="w-8 h-8 border-2 border-slate-700 border-t-cyan-400 rounded-full"
                        style={{ animation: "spin 0.8s linear infinite" }}
                        role="status"  // NOSONAR — S6819: role="status" is correct for live regions; <output> is semantically different
                        aria-label="Loading page"
                />
        </div>
);

const FireAlarmDesigner = lazy(() =>
        import("./components/mockups/engineering/FireAlarmDesigner").then((m) => ({
                default: m.FireAlarmDesigner,
        })),
);
const ApiKeysPage = lazy(() =>
        import("./pages/ApiKeysPage").then((m) => ({ default: m.ApiKeysPage })),
);
const AutoCADDrawPage = lazy(() =>
        import("./pages/AutoCADDrawPage").then((m) => ({ default: m.AutoCADDrawPage })),
);
const AutoCADPage = lazy(() =>
        import("./pages/AutoCADPage").then((m) => ({ default: m.AutoCADPage })),
);
const CADSettingsPage = lazy(() =>
        import("./pages/CADSettingsPage").then((m) => ({ default: m.CADSettingsPage })),
);
const Conflicts = lazy(() => import("./pages/Conflicts"));
const Connections = lazy(() => import("./pages/Connections"));
const DashboardPage = lazy(() =>
        import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })),
);
const DigitalTwinConfigPage = lazy(() =>
        import("./pages/DigitalTwinConfigPage").then((m) => ({
                default: m.DigitalTwinConfigPage,
        })),
);
const EnvironmentPage = lazy(() =>
        import("./pages/EnvironmentPage").then((m) => ({ default: m.EnvironmentPage })),
);
const DigitalTwinConvertPage = lazy(() =>
        import("./pages/DigitalTwinConvertPage").then((m) => ({
                default: m.DigitalTwinConvertPage,
        })),
);
const DigitalTwinHistoryPage = lazy(() =>
        import("./pages/DigitalTwinHistoryPage").then((m) => ({
                default: m.DigitalTwinHistoryPage,
        })),
);
const DigitalTwinPage = lazy(() =>
        import("./pages/DigitalTwinPage").then((m) => ({ default: m.DigitalTwinPage })),
);
const EtapPage = lazy(() =>
        import("./pages/EtapPage").then((m) => ({ default: m.EtapPage })),
);
const ElementDetail = lazy(() => import("./pages/ElementDetail"));
const Elements = lazy(() => import("./pages/Elements"));
const EngineeringPage = lazy(() =>
        import("./pages/EngineeringPage").then((m) => ({ default: m.EngineeringPage })),
);
const ExportsPage = lazy(() =>
        import("./pages/ExportsPage").then((m) => ({ default: m.ExportsPage })),
);
const FACPPage = lazy(() =>
        import("./pages/FACPPage").then((m) => ({ default: m.FACPPage })),
);
const FireAlarmPage = lazy(() =>
        import("./pages/FireAlarmPage").then((m) => ({ default: m.FireAlarmPage })),
);
const MarinePage = lazy(() =>
        import("./pages/MarinePage").then((m) => ({ default: m.MarinePage })),
);
const MiningPage = lazy(() =>
        import("./pages/MiningPage").then((m) => ({ default: m.MiningPage })),
);
const MemoryPage = lazy(() =>
        import("./pages/MemoryPage").then((m) => ({ default: m.MemoryPage })),
);
const MonitorPage = lazy(() =>
        import("./pages/MonitorPage").then((m) => ({ default: m.MonitorPage })),
);
const GraphRAGPage = lazy(() =>
        import("./pages/GraphRAGPage").then((m) => ({ default: m.GraphRAGPage })),
);
const NotFoundPage = lazy(() =>
        import("./pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })),
);
const ProjectsPage = lazy(() =>
        import("./pages/ProjectsPage").then((m) => ({ default: m.ProjectsPage })),
);
const ReportGeneratorPage = lazy(() =>
        import("./pages/ReportGeneratorPage").then((m) => ({
                default: m.ReportGeneratorPage,
        })),
);
const ReportsPage = lazy(() =>
        import("./pages/ReportsPage").then((m) => ({ default: m.ReportsPage })),
);
const RevitCreatePage = lazy(() =>
        import("./pages/RevitCreatePage").then((m) => ({ default: m.RevitCreatePage })),
);
const RevitElementsPage = lazy(() =>
        import("./pages/RevitElementsPage").then((m) => ({
                default: m.RevitElementsPage,
        })),
);
const RevitPage = lazy(() =>
        import("./pages/RevitPage").then((m) => ({ default: m.RevitPage })),
);
const SelfHealingPage = lazy(() =>
        import("./pages/SelfHealingPage").then((m) => ({ default: m.SelfHealingPage })),
);
const FDSSimulationPage = lazy(() =>
        import("./pages/FDSSimulationPage").then((m) => ({
                default: m.FDSSimulationPage,
        })),
);
const SettingsPage = lazy(() =>
        import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })),
);
const DatabaseAdminPage = lazy(() =>
        import("./pages/DatabaseAdminPage").then((m) => ({
                default: m.DatabaseAdminPage,
        })),
);
const BIMProvidersPage = lazy(() =>
        import("./pages/BIMProvidersPage").then((m) => ({
                default: m.BIMProvidersPage,
        })),
);
const IFC43MappingPage = lazy(() =>
        import("./pages/IFC43MappingPage").then((m) => ({
                default: m.IFC43MappingPage,
        })),
);
const ARExportPage = lazy(() =>
        import("./pages/ARExportPage").then((m) => ({
                default: m.ARExportPage,
        })),
);
const WorkflowPage = lazy(() =>
        import("./pages/WorkflowPage").then((m) => ({ default: m.WorkflowPage })),
);
const SystemHealthPage = lazy(() =>
    import("./pages/SystemHealthPage").then((m) => ({ default: m.SystemHealthPage })),
);
const GenerativeDesignPage = lazy(() =>
    import("./pages/GenerativeDesignPage").then((m) => ({ default: m.GenerativeDesignPage })),
);
const RbacPage = lazy(() =>
    import("./pages/RbacPage").then((m) => ({ default: m.RbacPage })),
);
const ExperimentalServicesPage = lazy(() =>
    import("./pages/ExperimentalServicesPage").then((m) => ({ default: m.ExperimentalServicesPage })),
);
const WebhookManagementPage = lazy(() =>
    import("./pages/WebhookManagementPage").then((m) => ({ default: m.WebhookManagementPage })),
);
const AgentChatPage = lazy(() =>
    import("./pages/AgentChatPage").then((m) => ({ default: m.AgentChatPage })),
);
const TopologyPage = lazy(() =>
    import("./pages/TopologyPage").then((m) => ({ default: m.TopologyPage })),
);
const EngineeringFireAIPage = lazy(() =>
    import("./pages/EngineeringFireAIPage").then((m) => ({ default: m.EngineeringFireAIPage })),
);
const PipelineLayersPage = lazy(() =>
    import("./pages/PipelineLayersPage").then((m) => ({ default: m.PipelineLayersPage })),
);
const QOMNCalculatorPage = lazy(() =>
    import("./pages/QOMNCalculatorPage").then((m) => ({ default: m.QOMNCalculatorPage })),
);
const MultiDBPage = lazy(() =>
    import("./pages/MultiDBPage").then((m) => ({ default: m.MultiDBPage })),
);
const AdvancedSettingsPage = lazy(() =>
    import("./pages/AdvancedSettingsPage").then((m) => ({ default: m.AdvancedSettingsPage })),
);
const AirQualityPage = lazy(() =>
    import("./pages/AirQualityPage").then((m) => ({ default: m.AirQualityPage })),
);
const AnalysisPage = lazy(() =>
    import("./pages/AnalysisPage").then((m) => ({ default: m.AnalysisPage })),
);
const APSPage = lazy(() =>
    import("./pages/APSPage").then((m) => ({ default: m.APSPage })),
);
const AuditTrailPage = lazy(() =>
    import("./pages/AuditTrailPage").then((m) => ({ default: m.AuditTrailPage })),
);
const BMSPage = lazy(() =>
    import("./pages/BMSPage").then((m) => ({ default: m.BMSPage })),
);
const CADToolsPage = lazy(() =>
    import("./pages/CADToolsPage").then((m) => ({ default: m.CADToolsPage })),
);
const ContextPage = lazy(() =>
    import("./pages/ContextPage").then((m) => ({ default: m.ContextPage })),
);
const DevicesPage = lazy(() =>
    import("./pages/DevicesPage").then((m) => ({ default: m.DevicesPage })),
);
const DWGPage = lazy(() =>
    import("./pages/DWGPage").then((m) => ({ default: m.DWGPage })),
);
const EngineeringCopilotPage = lazy(() =>
    import("./pages/EngineeringCopilotPage").then((m) => ({ default: m.EngineeringCopilotPage })),
);
const GuardsPage = lazy(() =>
    import("./pages/GuardsPage").then((m) => ({ default: m.GuardsPage })),
);
const HazMatPage = lazy(() =>
    import("./pages/HazMatPage").then((m) => ({ default: m.HazMatPage })),
);
const SecurityAlertsPage = lazy(() =>
    import("./pages/SecurityAlertsPage").then((m) => ({ default: m.SecurityAlertsPage })),
);
const SyncPage = lazy(() =>
    import("./pages/SyncPage").then((m) => ({ default: m.SyncPage })),
);

// C-07 FIX: Typed route structure with optional requiredRole for role-based access
interface ProtectedRoute {
        path: string;
        element: ReactNode;
        requiredRole?: string;
}        // V193 (R10): Skip-link for keyboard users to bypass the sidebar.
        // First focusable element on every page. WCAG 2.4.1 (Level A) requirement.
        // Wrapped in <nav> landmark so axe-core 'region' rule passes.
        const SkipLink = (
                <nav aria-label="Skip links">
                        <a
                                href="#main-content"
                                className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:bg-primary focus:text-primary-foreground focus:px-4 focus:py-2 focus:rounded focus:shadow-lg focus:outline-none"
                        >
                                Skip to main content
                        </a>
                </nav>
        );

/**
 * V193 (R1): Wrap the entire app in AuthProvider so any component can read
 * the authentication state via useAuth(). The provider performs an initial
 * GET /auth/me check on mount and exposes login/logout actions.
 *
 * V193 (R1): Routes are split into two groups:
 *   1. PUBLIC routes — /login (and future /signup, /forgot-key). These render
 *      WITHOUT the AppShell (full-screen, no sidebar).
 *   2. PROTECTED routes — everything else. Each is wrapped in <RouteGuard>
 *      which redirects to /login?from=<path> if the user is not authenticated.
 *
 * V193 (R13): A catch-all "*" route renders <NotFoundPage/> for unknown paths  // NOSONAR: typescript:S1854
 * (previously the SPA silently returned 200 with empty content).
 */
function App() {
        const { i18n } = useTranslation();
        const { connected } = useHealth();
        const location = useLocation();
        const [helpOpen, setHelpOpen] = useState(false);
        const [magicHelpTopic, setMagicHelpTopic] = useState<HelpTopicId | null>(
                null,
        );
        const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
        const [aiOpen, setAiOpen] = useState(false);

        const handleAiOpen = useCallback(() => setAiOpen(true), []);

        useEffect(() => {
                // Set document direction based on language for RTL support
                if (i18n.language === "ar") {
                        document.documentElement.dir = "rtl";
                        document.documentElement.lang = "ar";
                } else {
                        document.documentElement.dir = "ltr";
                        document.documentElement.lang = "en";
                }
        }, [i18n.language]);

        // V140 Phase 7: Magic Help — F1 opens help for current page
        // V207.3: Ctrl+J opens AI Copilot
        const pathnameRef = useRef(location.pathname);
        pathnameRef.current = location.pathname;
        useEffect(() => {
                const handleKeyDown = (e: KeyboardEvent) => {
                        if (e.key === "F1" || (e.ctrlKey && e.key === "h")) {
                                e.preventDefault();
                                // Find help topic for current route
                                const routeTopic = ROUTE_HELP_MAP[pathnameRef.current];
                                setMagicHelpTopic(routeTopic || null);
                                setHelpOpen(true);
                        } else if (e.ctrlKey && e.key === "k") {
                                e.preventDefault();
                                setCommandPaletteOpen(true);
                        } else if ((e.ctrlKey || e.metaKey) && e.key === "j") {
                                // V215 self-critique: support Cmd+J on macOS in addition to Ctrl+J on Windows/Linux
                                e.preventDefault();
                                setAiOpen((prev) => !prev);
                        }
                };
                globalThis.addEventListener("keydown", handleKeyDown);
                return () => globalThis.removeEventListener("keydown", handleKeyDown);
        }, []);

const handleHelpOpen = useCallback(() => {
    setMagicHelpTopic(null);
    setHelpOpen(true);
}, []);

const handleSearchOpen = useCallback(() => {
    setCommandPaletteOpen(true);
}, []);

        // PUBLIC routes — rendered without the AppShell (full-screen)
        const publicRoutes = useMemo(() => (
                <Routes>
                        <Route path="/login" element={<LoginPage />} />
                </Routes>
        ), []);

        // PROTECTED routes — wrapped in RouteGuard, rendered inside AppShell
        const protectedRoutes: ProtectedRoute[] = useMemo(() => [
                { path: "/", element: <Navigate to="/dashboard" /> },
                { path: "/dashboard", element: <DashboardPage /> },
                { path: "/projects", element: <ProjectsPage /> },
                { path: "/engineering", element: <EngineeringPage /> },
                { path: "/marine", element: <MarinePage /> },
                { path: "/mining", element: <MiningPage /> },
                // C-07 FIX: Admin-only pages — RouteGuard checks role
                { path: "/api-keys", element: <ApiKeysPage />, requiredRole: "admin" },
                { path: "/exports", element: <ExportsPage />, requiredRole: "admin" },
                { path: "/self-healing", element: <SelfHealingPage />, requiredRole: "admin" },
                { path: "/facp", element: <FACPPage /> },
                { path: "/environment", element: <EnvironmentPage /> },
                { path: "/monitor", element: <MonitorPage /> },
                { path: "/memory", element: <MemoryPage /> },
                { path: "/graphrag", element: <GraphRAGPage /> },
                { path: "/workflow", element: <WorkflowPage /> },
                { path: "/reports", element: <ReportsPage /> },
                { path: "/reports/generate", element: <ReportGeneratorPage /> },
                { path: "/settings", element: <SettingsPage /> },
                { path: "/settings/cad", element: <CADSettingsPage /> },
                { path: "/settings/database", element: <DatabaseAdminPage />, requiredRole: "admin" },
                { path: "/digital-twin", element: <DigitalTwinPage /> },
                { path: "/fire-alarm", element: <FireAlarmPage /> },
                { path: "/fire-alarm/designer", element: <FireAlarmDesigner /> },
                // V140 FIX: Add missing routes that Sidebar links to
                {
                        path: "/fire-alarm-designer",
                        element: <Navigate to="/fire-alarm/designer" />,
                },
                { path: "/elements", element: <Elements /> },
                { path: "/elements/:elementId", element: <ElementDetail /> },
                { path: "/connections", element: <Connections /> },
                { path: "/conflicts", element: <Conflicts /> },
                // V140 Phase 6: New routes for comprehensive API coverage
                { path: "/autocad", element: <AutoCADPage /> },
                { path: "/autocad/draw", element: <AutoCADDrawPage /> },
                { path: "/revit", element: <RevitPage /> },
                { path: "/revit/create", element: <RevitCreatePage /> },
                { path: "/revit/elements", element: <RevitElementsPage /> },
                { path: "/digital-twin/convert", element: <DigitalTwinConvertPage /> },
                { path: "/digital-twin/config", element: <DigitalTwinConfigPage /> },
                { path: "/digital-twin/history", element: <DigitalTwinHistoryPage /> },
                { path: "/etap", element: <EtapPage /> },
                // V270: FDS Simulation — smoke simulation job submission and tracking
                { path: "/fds-simulation", element: <FDSSimulationPage />, requiredRole: "admin" },
                { path: "/bim-providers", element: <BIMProvidersPage /> },
                { path: "/ifc43-mapping", element: <IFC43MappingPage />, requiredRole: "admin" },
                { path: "/ar-export", element: <ARExportPage />, requiredRole: "admin" },
                // V272: Route previously unrouted pages
                { path: "/dashboard/system-health", element: <SystemHealthPage /> },
                { path: "/engineering/generative", element: <GenerativeDesignPage /> },
                { path: "/engineering/fireai", element: <EngineeringFireAIPage /> },
                { path: "/engineering/pipeline", element: <PipelineLayersPage /> },
                { path: "/engineering/topology", element: <TopologyPage /> },
                { path: "/engineering/qomn", element: <QOMNCalculatorPage /> },
                { path: "/settings/rbac", element: <RbacPage />, requiredRole: "admin" },
                { path: "/settings/experimental", element: <ExperimentalServicesPage />, requiredRole: "admin" },
                { path: "/settings/webhooks", element: <WebhookManagementPage /> },
                { path: "/monitor/agent", element: <AgentChatPage /> },
                // V273: Add routes for previously unrouted orphaned pages
                { path: "/analysis", element: <AnalysisPage /> },
                { path: "/aps", element: <APSPage /> },
                { path: "/audit-trail", element: <AuditTrailPage /> },
                { path: "/bms", element: <BMSPage /> },
                { path: "/cad-tools", element: <CADToolsPage /> },
                { path: "/devices", element: <DevicesPage /> },
                { path: "/dwg", element: <DWGPage /> },
                { path: "/engineering-copilot", element: <EngineeringCopilotPage /> },
                { path: "/engineering/guards", element: <GuardsPage /> },
                { path: "/environment/air-quality", element: <AirQualityPage /> },
                { path: "/environment/context", element: <ContextPage /> },
                { path: "/environment/hazmat", element: <HazMatPage /> },
                { path: "/security-alerts", element: <SecurityAlertsPage /> },
                { path: "/settings/advanced", element: <AdvancedSettingsPage /> },
                { path: "/sync", element: <SyncPage /> },
                { path: "/multi-db", element: <MultiDBPage /> },
        ], []);

        // Determine if we're on a public route (no AppShell)
        const isPublicRoute = location.pathname === "/login";

        return (
                <AuthProvider>
                        <SmoothScroll>
                                <Suspense fallback={null}>
                                <MagneticCursor />
                                </Suspense>
                                <div className="h-screen bg-background text-foreground">
                                        {SkipLink}
                                        {/* F-08 FIX: show the demo-data banner whenever we're not
                                            on a live connection. Renders above AppShell so it is
                                            always visible regardless of which page is loaded. */}
                                        {!isPublicRoute && <DemoDataBanner />}
                                        {isPublicRoute ? (
                                        publicRoutes
                                ) : (
                                        <Suspense fallback={<PageLoader />}>
                                        <AppShell
                                                isConnected={connected}
                                                backendUrl={import.meta.env.VITE_API_URL || "/api/v1"}
                                                environment={import.meta.env.MODE || "development"}
                                                currentLanguage={i18n.language}
                                                onLanguageChange={(lng: string) => i18n.changeLanguage(lng)}
                                                onHelpOpen={handleHelpOpen}
                                                onSearchOpen={handleSearchOpen}
                                        >
                                                <main
                                                        id="main-content"
                                                        className="flex-1 overflow-auto relative"
                                                        tabIndex={-1}
                                                >
                                                        <Suspense fallback={<PageLoader />}>
                                                                {/* V250 FIX: Wrap each route in PageErrorBoundary so a single
                                                                    page error doesn't crash the entire app. The boundary shows
                                                                    a page-level error view with a Retry button. */}
                                                                <PageErrorBoundary pageName="current page">
                                                                        <Routes>
                                                                                {protectedRoutes.map((route) => (
                                                                                        <Route
                                                                                                key={route.path}
                                                                                                path={route.path}
                                                                                                element={
                                                                                                        <RouteGuard requiredRole={route.requiredRole}>{route.element}</RouteGuard>
                                                                                                }
                                                                                        />
                                                                                ))}
                                                                                {/* V193 (R13): 404 catch-all */}
                                                                                <Route
                                                                                        path="*"
                                                                                        element={
                                                                                                <RouteGuard>
                                                                                                        <NotFoundPage />
                                                                                                </RouteGuard>
                                                                                        }
                                                                                />
                                                                        </Routes>
                                                                </PageErrorBoundary>
                                                        </Suspense>
                                                </main>
                                        </AppShell>
                                        </Suspense>
                                )}
                                {/* V140 Phase 7: Global Help Drawer with full tree + user guide */}
                                <Suspense fallback={null}>
                                <GlobalHelpDrawer
                                        open={helpOpen}
                                        onOpenChange={setHelpOpen}
                                        initialTopicId={magicHelpTopic}
                                />
                                <CommandPalette
                                        open={commandPaletteOpen}
                                        onOpenChange={setCommandPaletteOpen}
                                />
                                {/* V207.3: Global AI Copilot — visible on all protected routes (Ctrl+J) */}
                                {!isPublicRoute && (
                                        <>
                                                <AskAiButton onClick={handleAiOpen} />
                                                <AskAiSheet open={aiOpen} onOpenChange={setAiOpen} />
                                        </>
                                )}
                                <OnboardingTour />
                                </Suspense>
                                {/* V215: Move toaster to top-right to avoid overlapping
                                     the new floating Ask AI button (bottom-right). */}
                                <Toaster position="top-right" />
                                </div>
                        </SmoothScroll>
                </AuthProvider>
        );
}

export default App;
