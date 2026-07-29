
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";

export interface TourStep {
        id: string;
        target: string;
        title: string;
        content: string;
        position?: "top" | "bottom" | "left" | "right";
}

const TOUR_STEPS: TourStep[] = [
        {
                id: "sidebar-toggle",
                target: "[data-onboarding='sidebar-toggle']",
                title: "Navigation Sidebar",
                content:
                        "Toggle the sidebar to expand or collapse the navigation menu. This gives you more screen space for your work.",
                position: "bottom",
        },
        {
                id: "nav-dashboard",
                target: "[data-onboarding='nav-dashboard']",
                title: "Dashboard",
                content:
                        "The dashboard provides an overview of your projects and recent activity. This is your starting point for all projects.",
                position: "right",
        },
        {
                id: "nav-projects",
                target: "[data-onboarding='nav-projects']",
                title: "Projects",
                content:
                        "Manage all your fire alarm engineering projects from here. Create, edit, and organize your work. Export to DXF, Revit, or IFC formats.",
                position: "right",
        },
        {
                id: "nav-engineering",
                target: "[data-onboarding='nav-engineering']",
                title: "Engineering",
                content:
                        "Access engineering tools and calculations for fire alarm system design and analysis. Includes smoke/heat spacing, detector placement, voltage drop, and battery calculations per NFPA 72-2022.",
                position: "right",
        },
        {
                id: "nav-fire-alarm-designer",
                target: "[data-onboarding='nav-fire-alarm-designer']",
                title: "Fire Alarm Designer",
                content:
                        "Design fire alarm systems visually with our interactive designer tool. Place devices, define zones, and create alarm layouts.",
                position: "right",
        },
        {
                id: "nav-facp",
                target: "[data-onboarding='nav-facp']",
                title: "FACP Selection",
                content:
                        "Select, verify, and generate schedules/specifications for Fire Alarm Control Panels per NFPA 72 Section 10.6.10. Includes compliance verification and DXF schedule generation.",
                position: "right",
        },
        {
                id: "nav-marine",
                target: "[data-onboarding='nav-marine']",
                title: "Marine Fire Safety",
                content:
                        "SOLAS/IEC 60092/NFPA 302 marine fire protection design. Ship zone design, extinguishing systems, alarm logic, and LR rule compliance.",
                position: "right",
        },
        {
                id: "nav-mining",
                target: "[data-onboarding='nav-mining']",
                title: "Mining Safety",
                content:
                        "MSHA/NFPA 120 mining fire safety compliance. Underground mine design, ventilation calculations, and compliance reporting.",
                position: "right",
        },
        {
                id: "nav-autocad",
                target: "[data-onboarding='nav-autocad']",
                title: "AutoCAD Integration",
                content:
                        "Connect to AutoCAD for live drawing operations. Read/write entities, draw lines, circles, and text directly in your CAD drawings.",
                position: "right",
        },
        {
                id: "nav-revit",
                target: "[data-onboarding='nav-revit']",
                title: "Revit Integration",
                content:
                        "Connect to Revit for BIM data exchange. Read/write RVT files, manage elements, search the Revit API, and execute natural language commands.",
                position: "right",
        },
        {
                id: "nav-digital-twin",
                target: "[data-onboarding='nav-digital-twin']",
                title: "Digital Twin",
                content:
                        "Convert and synchronize BIM models between AutoCAD and Revit formats with version control. Configure mappings and view conversion history.",
                position: "right",
        },
        {
                id: "nav-elements",
                target: "[data-onboarding='nav-elements']",
                title: "BIM Elements",
                content:
                        "Manage Universal Data Model (UDM) elements: walls, doors, windows, rooms, equipment, and more. Full CRUD with conflict detection.",
                position: "right",
        },
        {
                id: "nav-connections",
                target: "[data-onboarding='nav-connections']",
                title: "Connections",
                content:
                        "Manage connections between BIM elements. Define power, signal, data, fire alarm loop, and NAC circuit relationships.",
                position: "right",
        },
        {
                id: "nav-etap",
                target: "[data-onboarding='nav-etap']",
                title: "ETAP Integration",
                content:
                        "Integrate with ETAP for electrical engineering analysis. Sync data, manage settings, and run load flow calculations.",
                position: "right",
        },
        {
                id: "nav-environment",
                target: "[data-onboarding='nav-environment']",
                title: "Environment",
                content:
                        "Check weather, geocode, air quality, hazardous materials, regulatory region, and full environmental context for your project site.",
                position: "right",
        },
        {
                id: "nav-monitor",
                target: "[data-onboarding='nav-monitor']",
                title: "System Monitor",
                content:
                        "Monitor system health, engine status, agent activity, security alerts, and Prometheus metrics in real-time.",
                position: "right",
        },
        {
                id: "nav-workflow",
                target: "[data-onboarding='nav-workflow']",
                title: "Workflow",
                content:
                        "Manage LangGraph-based engineering workflows. Start, approve, reject, and audit workflow steps for fire protection design review.",
                position: "right",
        },
        {
                id: "nav-reports",
                target: "[data-onboarding='nav-reports']",
                title: "Reports",
                content:
                        "Generate and view reports for your projects including compliance and system analysis reports. Use AI-powered compliance narrative drafting.",
                position: "right",
        },
        {
                id: "nav-conflicts",
                target: "[data-onboarding='nav-conflicts']",
                title: "Conflicts",
                content:
                        "Detect and resolve BIM element conflicts including geometry mismatches, property conflicts, and deletion conflicts between AutoCAD and Revit models.",
                position: "right",
        },
        {
                id: "nav-memory",
                target: "[data-onboarding='nav-memory']",
                title: "Memory Store",
                content:
                        "Vector memory store for storing and searching engineering knowledge. Save design decisions, compliance notes, and project context for AI-powered retrieval.",
                position: "right",
        },
        {
                id: "nav-graphrag",
                target: "[data-onboarding='nav-graphrag']",
                title: "GraphRAG",
                content:
                        "Graph-based Retrieval-Augmented Generation. Query your BIM knowledge graph using natural language to find relationships between building elements.",
                position: "right",
        },
        {
                id: "nav-fds-simulation",
                target: "[data-onboarding='nav-fds-simulation']",
                title: "FDS Simulation",
                content:
                        "Submit and track Fire Dynamics Simulator (FDS) jobs. Run CFD smoke and fire spread simulations for advanced fire protection analysis.",
                position: "right",
        },
        {
                id: "nav-self-healing",
                target: "[data-onboarding='nav-self-healing']",
                title: "Self-Healing",
                content:
                        "Monitor circuit breaker health, LRU cache performance, and audit logs. Reset circuit breakers and view self-healing system diagnostics.",
                position: "right",
        },
        {
                id: "nav-bim-providers",
                target: "[data-onboarding='nav-bim-providers']",
                title: "BIM Providers",
                content:
                        "Browse and manage BIM data providers including Speckle, Autodesk Platform Services, and local file sources for building information models.",
                position: "right",
        },
        {
                id: "nav-ifc43-mapping",
                target: "[data-onboarding='nav-ifc43-mapping']",
                title: "IFC 4.3 Mapping",
                content:
                        "Map BIM elements to IFC 4.3 schema for infrastructure projects. Configure entity mappings, property sets, and classification references.",
                position: "right",
        },
        {
                id: "nav-ar-export",
                target: "[data-onboarding='nav-ar-export']",
                title: "AR Export",
                content:
                        "Export fire alarm system layouts as augmented reality models. View detector placement and zone layouts in real-world context using AR devices.",
                position: "right",
        },
        {
                id: "nav-webhook-management",
                target: "[data-onboarding='nav-webhook-management']",
                title: "Webhook Management",
                content:
                        "Configure webhooks for real-time notifications. Subscribe to project events, workflow transitions, and system alerts via HTTP callbacks.",
                position: "right",
        },
        {
                id: "nav-generative-design",
                target: "[data-onboarding='nav-generative-design']",
                title: "Generative Design",
                content:
                        "Run AI-powered generative design optimization. Explore multiple design variants for detector placement, cable routing, and panel selection.",
                position: "right",
        },
        {
                id: "nav-topology",
                target: "[data-onboarding='nav-topology']",
                title: "Topology Graph",
                content:
                        "Visualize and query the BIM topology graph. Explore spatial relationships, connectivity, and adjacency between building elements.",
                position: "right",
        },
        {
                id: "nav-rbac",
                target: "[data-onboarding='nav-rbac']",
                title: "RBAC Permissions",
                content:
                        "Manage Role-Based Access Control permissions. View and edit the permission matrix for admin, engineer, and viewer roles across all resource categories.",
                position: "right",
        },
        {
                id: "nav-settings",
                target: "[data-onboarding='nav-settings']",
                title: "Settings",
                content:
                        "Configure application preferences, feature flags, LLM provider, Akamai security, Langfuse observability, and pipeline tuning.",
                position: "right",
        },
        {
                id: "nav-api-keys",
                target: "[data-onboarding='nav-api-keys']",
                title: "API Keys",
                content:
                        "Manage API keys for programmatic access. Create, edit roles, and delete keys with admin, engineer, or viewer permissions.",
                position: "right",
        },
        {
                id: "help-button",
                target: "[data-onboarding='help-button']",
                title: "Help & Support",
                content:
                        "Access help documentation and support. Press F1 or Ctrl+H for quick access anytime. Use Ctrl+K for the command palette.",
                position: "bottom",
        },
        {
                id: "status-bar",
                target: "[data-onboarding='status-bar']",
                title: "Status Bar",
                content: "View connection status and application information at a glance.",
                position: "top",
        },
];

const STORAGE_KEY = "onboarding-completed";

export const OnboardingTour: React.FC = () => {
        const [currentStep, setCurrentStep] = useState(0);
        const [isVisible, setIsVisible] = useState(false);
        const [targetElement, setTargetElement] = useState<DOMRect | null>(null);
        const overlayRef = useRef<HTMLDivElement>(null);

        const _location = useLocation();

        // V181 FIX: Do NOT auto-start the onboarding tour after 1 second.
        // The previous behavior (setTimeout 1000ms → setIsVisible(true)) caused
        // a full-screen bg-background/80 overlay to appear over EVERY new visitor's
        // first session, making the entire UI look "dimmed/empty" (the overlay
        // sat at z-[9998] above all content). This was the ROOT CAUSE of the
        // 'pages look dim' issue reported by the operator — not the CSS vars,
        // not the overlays in AppShell (V177), not the card transparency (V178).
        //
        // The tour is still available via the help menu / F1 / Ctrl+H, but it no
        // longer ambushes new users with a dark overlay.
        //
        // To re-enable auto-tour in the future, gate it behind an explicit
        // user opt-in (e.g. a "Take Tour" button in the help drawer) rather
        // than auto-firing on first visit.

        const getTargetPosition = useCallback(() => {
                const selector = TOUR_STEPS[currentStep].target;
                const element = document.querySelector(selector) as HTMLElement;
                if (element) {
                        const rect = element.getBoundingClientRect();
                        setTargetElement(rect);
                } else {
                        setTargetElement(null);
                }
        }, [currentStep]);

        useEffect(() => {
                if (!isVisible) return;
                getTargetPosition();
                const handleResize = () => getTargetPosition();
                globalThis.addEventListener("resize", handleResize);
                return () => globalThis.removeEventListener("resize", handleResize);
        }, [isVisible, getTargetPosition]);

        const completeTour = useCallback(() => {
                try {
                        localStorage.setItem(STORAGE_KEY, "true");
                } catch {
                        // Storage unavailable
                }
                setIsVisible(false);
        }, []);

        const skipTour = useCallback(() => {
                completeTour();
        }, [completeTour]);

        const nextStep = useCallback(() => {
                if (currentStep < TOUR_STEPS.length - 1) {
                        setCurrentStep(currentStep + 1);
                } else {
                        completeTour();
                }
        }, [currentStep, completeTour]);

        const prevStep = useCallback(() => {
                if (currentStep > 0) {
                        setCurrentStep(currentStep - 1);
                }
        }, [currentStep]);

        if (!isVisible || !targetElement) return null;

        const step = TOUR_STEPS[currentStep];
        const isFirst = currentStep === 0;
        const isLast = currentStep === TOUR_STEPS.length - 1;

        const tooltipStyle = {
                top:
                        step.position === "top"
                                ? `${targetElement.top - 160}px`
                                : step.position === "bottom"  // NOSONAR: typescript:S3358
                                        ? `${targetElement.bottom + 16}px`
                                        : `${targetElement.top + targetElement.height / 2 - 80}px`,
                left:
                        step.position === "left"
                                ? `${targetElement.left - 280}px`
                                : step.position === "right"  // NOSONAR: typescript:S3358
                                        ? `${targetElement.right + 16}px`
                                        : `${targetElement.left + targetElement.width / 2 - 140}px`,
        };

        const arrowClasses = cn(
                "absolute w-0 h-0 border-8",
                step.position === "top" &&
                        "bottom-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-b-0 border-t-slate-900",
                step.position === "bottom" &&
                        "top-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-t-0 border-b-slate-900",
                step.position === "left" &&
                        "right-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-r-0 border-l-slate-900",
                step.position === "right" &&
                        "left-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-l-0 border-r-slate-900",
        );

        return (
                <>
                        <div
                                ref={overlayRef}
                                className="fixed inset-0 z-[9998] bg-background/80"
                                aria-hidden="true"
                        />

                        <div
                                className="fixed z-[9998] pointer-events-none"
                                aria-hidden="true"
                                style={{
                                        top: `${targetElement.top}px`,
                                        left: `${targetElement.left}px`,
                                        width: `${targetElement.width}px`,
                                        height: `${targetElement.height}px`,
                                        boxShadow: `0 0 0 9999px rgba(17, 24, 39, 0.8)`,
                                }}
                        />

                        <div
                                className="fixed z-[9999] w-72 bg-card border border-border rounded-lg shadow-2xl"
                                style={tooltipStyle}
                        >
                                <div className="p-4">
                                        <div className="flex items-start justify-between mb-2">
                                                <h3 className="text-primary font-semibold text-sm">
                                                        {step.title}
                                                </h3>
                                                <button
                                                        type="button" onClick={skipTour}
                                                        className="text-muted-foreground hover:text-foreground/90 text-xs"
                                                >
                                                        Skip
                                                </button>
                                        </div>

                                        <p className="text-foreground/90 text-sm mb-4">{step.content}</p>

                                        <div className="flex items-center justify-between">
                                                <span className="text-muted-foreground text-xs">
                                                        Step {currentStep + 1} of {TOUR_STEPS.length}
                                                </span>

                                                <div className="flex gap-2">
                                                        {!isFirst && (
                                                                <button
                                                                        type="button" onClick={prevStep}
                                                                        className="px-3 py-1 text-muted-foreground hover:text-foreground text-xs border border-border rounded"
                                                                >
                                                                        ← Previous
                                                                </button>
                                                        )}
                                                        <button
                                                                type="button" onClick={nextStep}
                                                                className="px-3 py-1 bg-primary hover:bg-primary text-white text-xs rounded"
                                                        >
                                                                {isLast ? "Done" : "Next"} →
                                                        </button>
                                                </div>
                                        </div>
                                </div>

                                <div className={arrowClasses} />
                        </div>
                </>
        );
};

export const useOnboarding = () => {
        // Vercel React Best Practices: rerender-derived-state-no-effect
        // Derive state during render instead of setting in useEffect
        const [hasCompleted, setHasCompleted] = useState(() => {
                try {
                        return !!localStorage.getItem(STORAGE_KEY);
                } catch {
                        return false;
                }
        });

        const resetOnboarding = useCallback(() => {
                try {
                        localStorage.removeItem(STORAGE_KEY);
                } catch {
                        // Storage unavailable
                }
                setHasCompleted(false);
        }, []);

        return { hasCompleted, resetOnboarding };
};

export default OnboardingTour;
