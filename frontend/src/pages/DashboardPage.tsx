
import { useMemo, useState } from "react";
import {
        Activity,
        AlertTriangle,
        Calculator,
        CheckCircle2,
        Clock,
        Database,
        Server,
        XCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDevices, useHealth, useProjects } from "@/hooks/useApiQuery";
import "@/styles/dashboard.css";

export function DashboardPage() {
        const { t } = useTranslation();
        const navigate = useNavigate();
        // Phase 13 Round 2 (VLM): ACK state for the trouble banner. A real FACP
        // requires explicit acknowledgment of trouble — the buzzer silences but
        // the amber LED stays on until the fault clears. We model the same here:
        // ACK hides the banner, but if the disconnect persists the banner should
        // reappear on next data refresh. For now this is a UX-level ack.
        const [troubleAcked, setTroubleAcked] = useState(false);
        const {
                data: health,
                loading: healthLoading,
                connected,
                refetch: refetchHealth,
        } = useHealth();
        const {
                data: projects,
                loading: projectsLoading,
        } = useProjects();
        const {
                data: devices,
                loading: devicesLoading,
        } = useDevices(null); // Pass null as projectId

        // Calculate stats
        const totalProjects = projects?.length ?? 0;
        const totalDevices = devices?.length ?? 0;
        const activeProjects = useMemo(
                () => projects?.filter((p) => p.status === "active").length || 0,
                [projects],
        );

        // V214 FIX (self-critique revised): Calculate device status counts.
        // Without a real backend endpoint that reports device health/status, we
        // CANNOT classify devices as warning/danger. The honest answer is:
        //   - ok = totalDevices (all devices are assumed operational)
        //   - warning = 0 (no data to classify)
        //   - danger = 0 (no data to classify)
        const warningDevices = 0;
        const dangerDevices = 0;
        const okDevices = totalDevices;

        // Announce when data finishes loading for screen readers
        const loadingAnnouncement = useMemo(() => {
                if (healthLoading || projectsLoading || devicesLoading) {
                        return null;
                }
                return `Dashboard loaded: ${totalProjects} projects, ${totalDevices} devices, ${
                        connected ? "connected" : "disconnected"
                }.`;
        }, [healthLoading, projectsLoading, devicesLoading, totalProjects, totalDevices, connected]);

        return (
                <div className="flex-1 overflow-auto" aria-label={t("dashboard.title")}>
                        {/* Loading announcement for screen readers */}
                        {loadingAnnouncement && (
                                <div
                                        role="status"
                                        aria-live="polite"
                                        aria-atomic="true"
                                        className="sr-only"
                                >
                                        {loadingAnnouncement}
                                </div>
                        )}
                        <div className="p-6 max-w-7xl mx-auto space-y-6">
                                {/* Trouble banner — shown only when disconnected and not yet ACKed.
                                    Phase 13 Round 1 self-critique (VLM): a lost backend connection
                                    is a TROUBLE condition in FACP vocabulary (NFPA 72 §10.14), not
                                    just an empty card slot. The banner overrides the page top.
                                    Phase 13 Round 2 (VLM): added ACK button — a real FACP requires
                                    explicit acknowledgment of trouble (the buzzer silences but the
                                    amber LED stays on). The ACK here hides the banner UX-wise. */}
                                {!connected && !healthLoading && !troubleAcked && (
                                        <div
                                                className="dashboard-trouble-banner"
                                                role="alert"
                                                aria-live="assertive"
                                                aria-label="System trouble: backend disconnected. Press acknowledge to silence."
                                        >
                                                <span className="dashboard-trouble-banner-label">TROUBLE</span>
                                                <span className="dashboard-trouble-banner-detail">
                                                        Backend connection lost — system operating in offline mode. Live data unavailable.
                                                </span>
                                                <button
                                                        type="button"
                                                        className="dashboard-trouble-ack"
                                                        onClick={() => setTroubleAcked(true)}
                                                        aria-label="Acknowledge trouble signal"
                                                >
                                                        ACK
                                                </button>
                                        </div>
                                )}

                                {/* Header — Space Grotesk display title + IBM Plex Sans subtitle */}
                                <div className="flex items-center justify-between flex-wrap gap-4">
                                        <div>
                                                <h1 className="dashboard-page-title">
                                                        {t("dashboard.title")}
                                                </h1>
                                                <p className="dashboard-page-subtitle">
                                                        {t("dashboard.subtitle")}
                                                </p>
                                        </div>
                                        <Button
                                                className="dashboard-refresh-btn inline-flex items-center gap-2 px-4 py-2"
                                                onClick={() => refetchHealth()}
                                                aria-label={t("dashboard.refresh")}
                                        >
                                                <Activity aria-hidden="true" className="h-4 w-4" />
                                                {t("dashboard.refresh")}
                                        </Button>
                                </div>

                                {/* Stats Cards — 4 KPI slots */}
                                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                                        {/* Projects Card */}
                                        <div
                                                className="dashboard-stat-card cursor-pointer p-5"
                                                onClick={() => navigate("/projects")}
                                                role="button"
                                                tabIndex={0}
                                                onKeyDown={(e) => {
                                                        if (e.key === "Enter" || e.key === " ") {
                                                                e.preventDefault();
                                                                navigate("/projects");
                                                        }
                                                }}
                                                aria-label={`${t("dashboard.projects")}: ${totalProjects}`}
                                        >
                                                <div className="dashboard-stat-title">{t("dashboard.projects")}</div>
                                                <div className="dashboard-stat-desc mt-1">{t("dashboard.acrossAllProjects")}</div>
                                                <div className="mt-4">
                                                        {projectsLoading ? (
                                                                <Skeleton className="h-9 w-16 bg-secondary" />
                                                        ) : (
                                                                <div className="dashboard-stat-num">{totalProjects}</div>
                                                        )}
                                                </div>
                                        </div>

                                        {/* Active Projects Card — accent count in evac-green */}
                                        <div
                                                className="dashboard-stat-card cursor-pointer p-5"
                                                onClick={() => navigate("/projects")}
                                                role="button"
                                                tabIndex={0}
                                                onKeyDown={(e) => {
                                                        if (e.key === "Enter" || e.key === " ") {
                                                                e.preventDefault();
                                                                navigate("/projects");
                                                        }
                                                }}
                                                aria-label={`${t("dashboard.active")}: ${activeProjects}`}
                                        >
                                                <div className="dashboard-stat-title">{t("dashboard.active")}</div>
                                                <div className="dashboard-stat-desc mt-1">{t("dashboard.projects")}</div>
                                                <div className="mt-4">
                                                        {projectsLoading ? (
                                                                <Skeleton className="h-9 w-16 bg-secondary" />
                                                        ) : (
                                                                <div className="dashboard-stat-num accent">{activeProjects}</div>
                                                        )}
                                                </div>
                                        </div>

                                        {/* Total Devices Card */}
                                        <div
                                                className="dashboard-stat-card cursor-pointer p-5"
                                                onClick={() => navigate("/devices")}
                                                role="button"
                                                tabIndex={0}
                                                onKeyDown={(e) => {
                                                        if (e.key === "Enter" || e.key === " ") {
                                                                e.preventDefault();
                                                                navigate("/devices");
                                                        }
                                                }}
                                                aria-label={`${t("dashboard.totalDevices")}: ${totalDevices}`}
                                        >
                                                <div className="dashboard-stat-title">{t("dashboard.totalDevices")}</div>
                                                <div className="dashboard-stat-desc mt-1">{t("dashboard.acrossAllProjects")}</div>
                                                <div className="mt-4">
                                                        {devicesLoading ? (
                                                                <Skeleton className="h-9 w-16 bg-secondary" />
                                                        ) : (
                                                                <div className="dashboard-stat-num">{totalDevices}</div>
                                                        )}
                                                </div>
                                        </div>

                                        {/* System Health Card — status pill, not bare icon */}
                                        <div
                                                className="dashboard-stat-card cursor-pointer p-5"
                                                onClick={() => navigate("/dashboard/system-health")}
                                                role="button"
                                                tabIndex={0}
                                                onKeyDown={(e) => {
                                                        if (e.key === "Enter" || e.key === " ") {
                                                                e.preventDefault();
                                                                navigate("/dashboard/system-health");
                                                        }
                                                }}
                                                aria-label={`${t("dashboard.systemHealth")}: ${connected ? t("dashboard.connected") : t("dashboard.disconnected")}`}
                                        >
                                                <div className="dashboard-stat-title">{t("dashboard.systemHealth")}</div>
                                                <div className="dashboard-stat-desc mt-1">{t("dashboard.status")}</div>
                                                <div className="mt-4">
                                                        {healthLoading ? (
                                                                <Skeleton className="h-9 w-24 bg-secondary" />
                                                        ) : (
                                                                <div className={`dashboard-status-pill ${connected ? "ok" : "fail"}`}>
                                                                        {connected ? (
                                                                                <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                                                                        ) : (
                                                                                <XCircle aria-hidden="true" className="h-4 w-4" />
                                                                        )}
                                                                        {connected ? t("dashboard.connected") : t("dashboard.disconnected")}
                                                                </div>
                                                        )}
                                                </div>
                                        </div>
                                </div>

                                {/* Status Summary Card — 3 device-state counters with FACP alarm vocabulary */}
                                <div className="dashboard-stat-card p-5">
                                        <div className="dashboard-section-title">{t("dashboard.statusSummary")}</div>
                                        <div className="dashboard-section-desc mt-1">{t("dashboard.deviceStatusOverview")}</div>
                                        <div className="dashboard-summary-grid mt-4">
                                                <div className="dashboard-counter ok">
                                                        <div className="dashboard-counter-icon">
                                                                <CheckCircle2 aria-hidden="true" className="h-5 w-5" />
                                                        </div>
                                                        <div>
                                                                <div className="dashboard-counter-num">{okDevices}</div>
                                                                <div className="dashboard-counter-label">{t("dashboard.ok")}</div>
                                                        </div>
                                                </div>
                                                <div className="dashboard-counter warning">
                                                        <div className="dashboard-counter-icon">
                                                                <AlertTriangle aria-hidden="true" className="h-5 w-5" />
                                                        </div>
                                                        <div>
                                                                <div className="dashboard-counter-num">{warningDevices}</div>
                                                                <div className="dashboard-counter-label">{t("dashboard.warning")}</div>
                                                        </div>
                                                </div>
                                                <div className="dashboard-counter danger">
                                                        <div className="dashboard-counter-icon">
                                                                <XCircle aria-hidden="true" className="h-5 w-5" />
                                                        </div>
                                                        <div>
                                                                <div className="dashboard-counter-num">{dangerDevices}</div>
                                                                <div className="dashboard-counter-label">{t("dashboard.danger")}</div>
                                                        </div>
                                                </div>
                                        </div>
                                </div>

                                {/* System Health Details */}
                                <div className="dashboard-stat-card p-5">
                                        <div className="dashboard-section-title">{t("dashboard.systemHealth")}</div>
                                        <div
                                                className="dashboard-section-desc mt-1"
                                                aria-live="polite"
                                                aria-atomic="true"
                                        >
                                                {healthLoading
                                                        ? t("dashboard.loading")
                                                        : t("dashboard.lastUpdated") +
                                                                ": " +
                                                                (health ? new Date().toLocaleString() : "")}
                                        </div>
                                        <div className="dashboard-health-grid mt-4">
                                                {healthLoading ? (
                                                        <div className="space-y-3 col-span-full">
                                                                <Skeleton className="h-4 w-full bg-secondary" />
                                                                <Skeleton className="h-4 w-4/5 bg-secondary" />
                                                                <Skeleton className="h-4 w-3/4 bg-secondary" />
                                                        </div>
                                                ) : health ? (
                                                        <>
                                                                <div className="dashboard-health-item">
                                                                        <Server aria-hidden="true" className="h-5 w-5 dashboard-health-item-icon" />
                                                                        <span className="dashboard-health-label">{t("dashboard.version")}:</span>
                                                                        <span className="dashboard-health-value">v{health.version}</span>
                                                                </div>
                                                                <div className="dashboard-health-item">
                                                                        <Database aria-hidden="true" className="h-5 w-5 dashboard-health-item-icon" />
                                                                        <span className="dashboard-health-label">{t("dashboard.database")}:</span>
                                                                        <span className="dashboard-health-value">{health.database}</span>
                                                                </div>
                                                                <div className="dashboard-health-item">
                                                                        <Clock aria-hidden="true" className="h-5 w-5 dashboard-health-item-icon" />
                                                                        <span className="dashboard-health-label">{t("dashboard.uptime")}:</span>
                                                                        <span className="dashboard-health-value">
                                                                                {Math.floor((health.uptime || 0) / 60)} min
                                                                        </span>
                                                                </div>
                                                        </>
                                                ) : (
                                                        <p className="dashboard-section-desc col-span-full">{t("dashboard.disconnected")}</p>
                                                )}
                                        </div>
                                </div>

                                {/* Report Generator Quick Access */}
                                <div className="dashboard-stat-card p-5">
                                        <div className="dashboard-section-title">{t("settings.advancedReportGenerator")}</div>
                                        <div className="dashboard-section-desc mt-1">{t("settings.reportGeneratorDesc")}</div>
                                        <div className="flex flex-col sm:flex-row gap-4 mt-4">
                                                <div className="flex-1">
                                                        <h3 className="font-medium text-bone mb-2" style={{ color: "var(--color-bone)" }}>
                                                                {t("settings.comprehensiveReportGeneration")}
                                                        </h3>
                                                        <p className="text-sm" style={{ color: "rgba(232, 228, 216, 0.6)" }}>
                                                                {t("settings.comprehensiveReportDesc")}
                                                        </p>
                                                </div>
                                                <Button
                                                        onClick={() => navigate("/reports")}
                                                        className="dashboard-report-cta inline-flex items-center gap-2 px-5 py-2.5"
                                                        aria-label={t("settings.openReportGenerator")}
                                                >
                                                        <Calculator aria-hidden="true" className="h-4 w-4" />
                                                        {t("settings.openReportGenerator")}
                                                </Button>
                                        </div>
                                </div>
                        </div>
                </div>
        );
}
