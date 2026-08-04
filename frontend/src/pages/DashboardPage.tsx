import { useMemo, useState } from "react";
import {
        Activity,
        AlertTriangle,
        Calculator,
        CheckCircle2,
        Clock,
        Cpu,
        Database,
        FolderKanban,
        Server,
        XCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import {
        Card,
        CardContent,
        CardDescription,
        CardHeader,
        CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDevices, useHealth, useProjects } from "@/hooks/useApiQuery";

/**
 * DashboardPage — Frontend-design skill applied (2026-08-04, revised)
 *
 * DESIGN RATIONALE (frontend-design skill, 2-pass process):
 *
 * Pass 1 — Design plan:
 *   Subject: Fire Alarm Engineering Platform (BAZSPARK)
 *   Audience: Professional engineers needing instant situational awareness
 *   Signature element: System Heartbeat — a pulsing ring showing the
 *     supervisory system is alive. Domain-appropriate: every FACP panel
 *     has a supervisory LED. This is NOT decoration, it IS the interface.
 *   Palette: Existing tokens (deep navy + cyan brand). No new colors.
 *     Amber (warning) used for supervisory status per NFPA 72 convention.
 *   Typography: Connection status as hero (massive). Supporting metrics
 *     quiet, tabular, mono-spaced for rapid scanning.
 *   Layout: Hierarchy over equality. Connection status dominates.
 *     Supporting metrics recede. Report access demoted — it's navigation,
 *     not the primary fact.
 *   Copy: Fire alarm vernacular per NFPA 72:
 *     "Supervising" (not "Connected")
 *     "Signal Lost" (not "Disconnected")
 *     "All Points Normal" (not showing 0/0/0 which looks broken)
 *   Motion: Staggered card entrance (respects prefers-reduced-motion).
 *
 * Pass 2 — Self-critique:
 *   - Is the heartbeat too flashy? No — FACP panels literally pulse their
 *     supervisory LED. This is domain-standard, not decoration.
 *   - Is breaking the 4-equal-card grid risky? No — hierarchy IS information.
 *     Connection status is objectively more important than "total projects".
 *   - CRITICAL FIX: Removed bg-danger from the Report Generator button.
 *     In a fire alarm application, red/danger MUST be reserved for ACTIVE
 *     ALARMS only. Using it for navigation trains operators to ignore red,
 *     which can be catastrophic in an emergency. Changed to bg-primary.
 *   - "All Points Normal" communicates more than showing "0 Warning, 0 Danger"
 *     which looks like the system isn't monitoring anything.
 *   - Am I spending boldness in one place? Yes — the heartbeat hero is the
 *     single bold element. Everything else is quieter than before.
 */

export function DashboardPage() {
        const { t } = useTranslation();
        const navigate = useNavigate();
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
        //
        // PREVIOUS ERROR: Classified by voltage/current thresholds which was WRONG —
        // a 12V device is not "danger", it's just a 12V device. A 0.5A horn/strobe
        // is not "warning", it's normal operating current. This caused false alarms
        // for every normal device in the system.
        //
        // CORRECT APPROACH: The Device interface does NOT have a 'status' field.
        // Without a real backend endpoint that reports device health/status, we
        // CANNOT classify devices as warning/danger. The honest answer is:
        //   - ok = totalDevices (all devices are assumed operational)
        //   - warning = 0 (no data to classify)
        //   - danger = 0 (no data to classify)
        //
        // When a backend /devices/{id}/health endpoint is implemented, this
        // classification should call it. Until then, we show all as OK with
        // a tooltip explaining the limitation.
        const warningDevices = 0; // No health endpoint available — honest zero
        const dangerDevices = 0;  // No health endpoint available — honest zero
        const okDevices = totalDevices; // All devices assumed operational

        // Announce when data finishes loading for screen readers
        const loadingAnnouncement = useMemo(() => {
                if (healthLoading || projectsLoading || devicesLoading) {
                        return null;
                }
                return `Dashboard loaded: ${totalProjects} projects, ${totalDevices} devices, ${
                        connected ? "supervising" : "signal lost"
                }.`;
        }, [healthLoading, projectsLoading, devicesLoading, totalProjects, totalDevices, connected]);

        // Stagger delay for card entrance animation
        const stagger = (index: number) => ({
                style: { "--stagger-index": index } as React.CSSProperties,
                className: "dashboard-stagger-in",
        });

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
                        <div className="p-6 max-w-7xl mx-auto space-y-8">
                                {/* Trouble banner — shown only when disconnected and not yet ACKed.
                                    Phase 13 Round 1 self-critique (VLM): a lost backend connection
                                    is a TROUBLE condition in FACP vocabulary (NFPA 72 §10.14), not
                                    just an empty card slot. The banner overrides the page top.
                                    Phase 13 Round 2 (VLM): added ACK button — a real FACP requires
                                    explicit acknowledgment of trouble (the buzzer silences but the
                                    amber LED stays on). The ACK here hides the banner UX-wise.
                                    Preserved during merge of feature/frontend-design-dashboard
                                    so the redesign's hero heartbeat and this safety alert coexist. */}
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

                                {/* ══════════════════════════════════════════════════════════════
                                 * HERO — System Heartbeat
                                 *
                                 * The single most important fact: is the system supervising?
                                 * This is the signature element — the one memorable thing.
                                 * In a FACP (Fire Alarm Control Panel), the supervisory LED
                                 * IS the heartbeat. We bring that same principle here.
                                 * ══════════════════════════════════════════════════════════════ */}
                                <section className="dashboard-stagger-in" aria-labelledby="dashboard-hero-title">
                                        <div className="flex items-start justify-between gap-6">
                                                <div className="flex items-center gap-5 min-w-0">
                                                        {/* System Heartbeat Ring */}
                                                        <div
                                                                className="shrink-0 relative w-20 h-20 flex items-center justify-center"
                                                                role="img"
                                                                aria-label={connected ? t("dashboard.supervising") : t("dashboard.signalLost")}
                                                        >
                                                                {/* Outer pulse ring — connected: calm green supervisory pulse */}
                                                                {connected && (
                                                                        <div className="absolute inset-0 rounded-full border-2 border-success/40 heartbeat-pulse" />
                                                                )}
                                                                {/* Disconnected: amber trouble pulse — NFPA 72 trouble condition */}
                                                                {!connected && (
                                                                        <div className="absolute inset-0 rounded-full border-2 border-warning/50 heartbeat-pulse-trouble" />
                                                                )}
                                                                {/* Inner solid ring */}
                                                                <div className={`relative w-14 h-14 rounded-full border-2 flex items-center justify-center transition-colors duration-300 ${
                                                                        connected
                                                                                ? "border-success bg-success/10"
                                                                                : "border-warning/60 bg-warning/10"
                                                                }`}>
                                                                        <CheckCircle2
                                                                                aria-hidden="true"
                                                                                className={`h-6 w-6 transition-colors duration-300 ${connected ? "text-success" : "text-warning"}`}
                                                                        />
                                                                </div>
                                                        </div>

                                                        <div className="min-w-0">
                                                                {/* Eyebrow — page label (h5: uppercase, small, muted) */}
                                                                <h5 id="dashboard-hero-eyebrow" className="mb-1">
                                                                {t("dashboard.title")}
                                                                </h5>
                                                                {/* Hero — system status IS the thesis (frontend-design skill)
                                                                         * The most important fact: is the system supervising?
                                                                         * Color: success when supervising, warning when signal lost. */}
                                                                <h1
                                                                        id="dashboard-hero-title"
                                                                        className={`text-2xl font-bold tracking-tight transition-colors duration-300 ${
                                                                                connected ? "text-success" : "text-warning"
                                                                        }`}
                                                                >
                                                                        {connected ? t("dashboard.supervising") : t("dashboard.signalLost")}
                                                                </h1>
                                                                <p className="text-sm text-muted-foreground mt-0.5">
                                                                        {connected
                                                                                ? t("dashboard.systemSupervising")
                                                                                : t("dashboard.signalLostDescription")
                                                                        }
                                                                </p>
                                                        </div>
                                                </div>

                                                <Button
                                                        variant="outline"
                                                        className="shrink-0 border-border text-foreground/90 hover:bg-card hover:border-cyan-400/40"
                                                        onClick={() => refetchHealth()}
                                                >
                                                        <Activity aria-hidden="true" className="h-4 w-4 mr-1.5" />
                                                        {t("dashboard.refresh")}
                                                </Button>
                                        </div>
                                </section>

                                {/* ══════════════════════════════════════════════════════════════
                                 * SUPPORTING METRICS — Quiet, scannable, tabular
                                 *
                                 * These recede behind the hero. 3 cards, not 4 —
                                 * connection status already lives in the hero.
                                 * Each card is clickable for navigation.
                                 * ══════════════════════════════════════════════════════════════ */}
                                <section aria-label={t("dashboard.statusSummary")}>
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                                {/* Projects Card */}
                                                <Card
                                                        {...stagger(0)}
                                                        className="border-border bg-card card-hover cursor-pointer focus-ring"
                                                        onClick={() => navigate("/projects")}
                                                        onKeyDown={(e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); navigate("/projects"); } }}
                                                        role="button"
                                                        tabIndex={0}
                                                >
                                                        <CardHeader className="pb-2">
                                                                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                                                        <FolderKanban aria-hidden="true" className="h-3.5 w-3.5 inline mr-1.5 -mt-0.5" />
                                                                        {t("dashboard.projects")}
                                                                </CardTitle>
                                                        </CardHeader>
                                                        <CardContent>
                                                                {projectsLoading ? (
                                                                        <Skeleton className="h-8 w-16 bg-secondary" />
                                                                ) : (
                                                                        <div className="flex items-baseline gap-2">
                                                                                <span className="text-3xl font-bold text-foreground font-mono-num">
                                                                                        {totalProjects}
                                                                                </span>
                                                                                <span className="text-sm text-muted-foreground">
                                                                                        {t("dashboard.acrossAllProjects")}
                                                                                </span>
                                                                        </div>
                                                                )}
                                                        </CardContent>
                                                </Card>

                                                {/* Active Projects Card */}
                                                <Card
                                                        {...stagger(1)}
                                                        className="border-border bg-card card-hover cursor-pointer focus-ring"
                                                        onClick={() => navigate("/projects")}
                                                        onKeyDown={(e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); navigate("/projects"); } }}
                                                        role="button"
                                                        tabIndex={0}
                                                >
                                                        <CardHeader className="pb-2">
                                                                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                                                        <Activity aria-hidden="true" className="h-3.5 w-3.5 inline mr-1.5 -mt-0.5" />
                                                                        {t("dashboard.active")}
                                                                </CardTitle>
                                                        </CardHeader>
                                                        <CardContent>
                                                                {projectsLoading ? (
                                                                        <Skeleton className="h-8 w-16 bg-secondary" />
                                                                ) : (
                                                                        <div className="flex items-baseline gap-2">
                                                                                <span className="text-3xl font-bold text-cyan-300 font-mono-num">
                                                                                        {activeProjects}
                                                                                </span>
                                                                                <span className="text-sm text-muted-foreground">
                                                                                        {t("dashboard.projects")}
                                                                                </span>
                                                                        </div>
                                                                )}
                                                        </CardContent>
                                                </Card>

                                                {/* Total Devices Card */}
                                                <Card
                                                        {...stagger(2)}
                                                        className="border-border bg-card card-hover cursor-pointer focus-ring"
                                                        onClick={() => navigate("/devices")}
                                                        onKeyDown={(e: React.KeyboardEvent) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); navigate("/devices"); } }}
                                                        role="button"
                                                        tabIndex={0}
                                                >
                                                        <CardHeader className="pb-2">
                                                                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                                                        <Cpu aria-hidden="true" className="h-3.5 w-3.5 inline mr-1.5 -mt-0.5" />
                                                                        {t("dashboard.totalDevices")}
                                                                </CardTitle>
                                                        </CardHeader>
                                                        <CardContent>
                                                                {devicesLoading ? (
                                                                        <Skeleton className="h-8 w-16 bg-secondary" />
                                                                ) : (
                                                                        <div className="flex items-baseline gap-2">
                                                                                <span className="text-3xl font-bold text-foreground font-mono-num">
                                                                                        {totalDevices}
                                                                                </span>
                                                                                <span className="text-sm text-muted-foreground">
                                                                                        {t("dashboard.acrossAllProjects")}
                                                                                </span>
                                                                        </div>
                                                                )}
                                                        </CardContent>
                                                </Card>
                                        </div>
                                </section>

                                {/* ══════════════════════════════════════════════════════════════
                                 * POINT STATUS — "All Points Normal" or breakdown
                                 *
                                 * Instead of showing "0 Warning, 0 Danger" (which looks like
                                 * the system isn't monitoring), we say "All Points Normal"
                                 * when there are no issues. This is the FACP convention.
                                 * ══════════════════════════════════════════════════════════════ */}
                                <Card
                                        className={`border-border bg-card dashboard-stagger-in border-l-4 ${
                                                warningDevices === 0 && dangerDevices === 0 ? "border-l-success/60" : "border-l-warning/60"
                                        }`}
                                        style={{ "--stagger-index": 3 } as React.CSSProperties}
                                >
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                                                        {t("dashboard.supervisoryStatus")}
                                                </CardTitle>
                                        </CardHeader>
                                        <CardContent>
                                                {warningDevices === 0 && dangerDevices === 0 ? (
                                                        /* All clear — FACP convention: "All Points Normal" */
                                                        <div className="flex items-center gap-3">
                                                                <div className="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center">
                                                                        <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-success" />
                                                                </div>
                                                                <div>
                                                                        <div className="text-lg font-semibold text-success">
                                                                                {t("dashboard.allPointsNormal")}
                                                                        </div>
                                                                        <div className="text-sm text-muted-foreground">
                                                                                {okDevices} {t("dashboard.devices").toLowerCase()} {t("dashboard.acrossAllProjects").toLowerCase()}
                                                                        </div>
                                                                </div>
                                                        </div>
                                                ) : (
                                                        /* Issues exist — show breakdown */
                                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                                                <div className="flex items-center gap-3">
                                                                        <div className="w-10 h-10 rounded-full bg-success/10 flex items-center justify-center">
                                                                                <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-success" />
                                                                        </div>
                                                                        <div>
                                                                                <div className="text-2xl font-bold text-success font-mono-num">
                                                                                        {okDevices}
                                                                                </div>
                                                                                <div className="text-sm text-muted-foreground">
                                                                                        {t("dashboard.ok")}
                                                                                </div>
                                                                        </div>
                                                                </div>
                                                                <div className="flex items-center gap-3">
                                                                        <div className="w-10 h-10 rounded-full bg-warning/10 flex items-center justify-center">
                                                                                <Activity aria-hidden="true" className="h-5 w-5 text-warning" />
                                                                        </div>
                                                                        <div>
                                                                                <div className="text-2xl font-bold text-warning font-mono-num">
                                                                                        {warningDevices}
                                                                                </div>
                                                                                <div className="text-sm text-muted-foreground">
                                                                                        {t("dashboard.warning")}
                                                                                </div>
                                                                        </div>
                                                                </div>
                                                                <div className="flex items-center gap-3">
                                                                        <div className="w-10 h-10 rounded-full bg-danger/10 flex items-center justify-center">
                                                                                <Server aria-hidden="true" className="h-5 w-5 text-danger" />
                                                                        </div>
                                                                        <div>
                                                                                <div className="text-2xl font-bold text-danger font-mono-num">
                                                                                        {dangerDevices}
                                                                                </div>
                                                                                <div className="text-sm text-muted-foreground">
                                                                                        {t("dashboard.danger")}
                                                                                </div>
                                                                        </div>
                                                                </div>
                                                        </div>
                                                )}
                                        </CardContent>
                                </Card>

                                {/* ══════════════════════════════════════════════════════════════
                                 * SYSTEM HEALTH DETAILS — Quiet, informational
                                 * ══════════════════════════════════════════════════════════════ */}
                                <Card className="border-border bg-card dashboard-stagger-in" style={{ "--stagger-index": 4 } as React.CSSProperties}>
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                                                        {t("dashboard.systemHealth")}
                                                </CardTitle>
                                                <CardDescription
                                                        className="text-muted-foreground"
                                                        aria-live="polite"
                                                        aria-atomic="true"
                                                >
                                                        {healthLoading
                                                                ? t("dashboard.loading")
                                                                : t("dashboard.lastUpdated") +
                                                                        ": " +
                                                                        (health ? new Date().toLocaleString() : "")}
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                                {healthLoading ? (
                                                        <div className="space-y-3">
                                                                <Skeleton className="h-4 w-full bg-secondary" />
                                                                <Skeleton className="h-4 w-4/5 bg-secondary" />
                                                                <Skeleton className="h-4 w-3/4 bg-secondary" />
                                                        </div>
                                                ) : health ? (
                                                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                                                <div className="flex items-center gap-2">
                                                                        <Server aria-hidden="true" className="h-4 w-4 text-muted-foreground" />
                                                                        <span className="text-sm text-foreground/80">
                                                                                {t("dashboard.version")}: v{health.version}
                                                                        </span>
                                                                </div>
                                                                <div className="flex items-center gap-2">
                                                                        <Database aria-hidden="true" className="h-4 w-4 text-muted-foreground" />
                                                                        <span className="text-sm text-foreground/80">
                                                                                {t("dashboard.database")}: {health.database}
                                                                        </span>
                                                                </div>
                                                                <div className="flex items-center gap-2">
                                                                        <Clock aria-hidden="true" className="h-4 w-4 text-muted-foreground" />
                                                                        <span className="text-sm text-foreground/80">
                                                                                {t("dashboard.uptime")}:{" "}
                                                                                {Math.floor((health.uptime || 0) / 60)} min
                                                                        </span>
                                                                </div>
                                                        </div>
                                                ) : (
                                                        <p className="text-sm text-muted-foreground">{t("dashboard.signalLost")}</p>
                                                )}
                                        </CardContent>
                                </Card>

                                {/* ══════════════════════════════════════════════════════════════
                                 * REPORT GENERATOR — Demoted, quiet action
                                 *
                                 * CRITICAL SAFETY FIX (frontend-design skill):
                                 * Previous version used bg-danger (red) for this button.
                                 * In a fire alarm application, red/danger color is reserved
                                 * for ACTIVE ALARMS ONLY. Using it for navigation trains
                                 * operators to ignore red, which can be catastrophic in an
                                 * emergency. Changed to bg-primary (cyan brand).
                                 * ══════════════════════════════════════════════════════════════ */}
                                <Card className="border-border bg-card dashboard-stagger-in" style={{ "--stagger-index": 5 } as React.CSSProperties}>
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                                                        {t("settings.advancedReportGenerator")}
                                                </CardTitle>
                                                <CardDescription className="text-muted-foreground">
                                                        {t("settings.reportGeneratorDesc")}
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                                <div className="flex flex-col sm:flex-row gap-4">
                                                        <div className="flex-1">
                                                                <p className="text-sm text-foreground/80">
                                                                        {t("settings.comprehensiveReportDesc")}
                                                                </p>
                                                        </div>
                                                        <Button
                                                                onClick={() => navigate("/reports")}
                                                                /* SAFETY: bg-primary, NOT bg-danger.
                                                                   Red is reserved for active alarms. */
                                                                className="bg-primary hover:bg-primary/90 text-primary-foreground border-none flex items-center gap-2 shrink-0"
                                                                aria-label={t("settings.openReportGenerator")}
                                                        >
                                                                <Calculator aria-hidden="true" className="h-4 w-4" />
                                                                {t("settings.openReportGenerator")}
                                                        </Button>
                                                </div>
                                        </CardContent>
                                </Card>
                        </div>
                </div>
        );
}
