
/**
 * SettingsPage.tsx - Application configuration and user preferences
 */

import {
        Activity,
        Calculator,
        CheckCircle2,
        Database,
        Settings,
        Shield,
        XCircle,
} from "lucide-react";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
        Card,
        CardContent,
        CardDescription,
        CardHeader,
        CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useHealth } from "@/hooks/useApiQuery";

export function SettingsPage() {
        const { t } = useTranslation();
        const navigate = useNavigate();
        const {
                data: health,
                loading: healthLoading,
                connected,
                refetch: refetchHealth,
        } = useHealth();

        const [activeTab, setActiveTab] = useState("general");

        // General settings
        const [theme, setTheme] = useState("dark");
        const [language, setLanguage] = useState("en");
        const [notifications, setNotifications] = useState(true);

        // Security settings
        const [twoFactorAuth, setTwoFactorAuth] = useState(false);
        const [passwordExpiry, setPasswordExpiry] = useState(90);

        // API settings
        const [apiTimeout, setApiTimeout] = useState(30);
        const [retryAttempts, setRetryAttempts] = useState(3);

        // Report settings
        const [autoSaveReports, setAutoSaveReports] = useState(true);
        const [reportFormat, setReportFormat] = useState("pdf");
        const [reportQuality, setReportQuality] = useState("high");

        // Feature flags
        const FEATURE_FLAG_DEFINITIONS = [
                { key: "SMOKE_SIMULATION", default: false, name: "CFD Smoke Simulation", description: "Enable CFD smoke simulation capabilities" },
                { key: "DIGITAL_TWIN_SYNC", default: true, name: "Digital Twin Sync", description: "Enable Digital Twin synchronization" },
                { key: "SELF_LEARNING", default: false, name: "Self-Learning", description: "Enable ML pattern learning" },
                { key: "RESILIENCE_CHECK", default: true, name: "Resilience Check", description: "Enable resilience checking" },
                { key: "PROOF_CERTIFICATE", default: true, name: "Proof Certificate", description: "Enable cryptographic proof certificates" },
                { key: "VORONOI_VERIFICATION", default: true, name: "Voronoi Verification", description: "Enable Voronoi-based verification" },
                { key: "AUTOCAD_BRIDGE", default: true, name: "AutoCAD Bridge", description: "Enable AutoCAD integration" },
                { key: "REVIT_BRIDGE", default: true, name: "Revit Bridge", description: "Enable Revit integration" },
                { key: "DIALUX_BRIDGE", default: true, name: "DIALux Bridge", description: "Enable DIALux integration" },
        ] as const;

        const backendFlags = health?.feature_flags ?? null;
        const isReadOnly = !backendFlags;

        const [localFlags, setLocalFlags] = useState<Record<string, boolean>>(
                () => Object.fromEntries(FEATURE_FLAG_DEFINITIONS.map((f) => [f.key, f.default])),
        );
        const [flagUpdateStatus, setFlagUpdateStatus] = useState<Record<string, "saving" | "saved" | "error">>({});

        const featureFlags: Record<string, boolean> = backendFlags
                ? { ...localFlags, ...backendFlags }
                : localFlags;

        const handleFlagToggle = useCallback(
                async (flagKey: string, newValue: boolean) => {
                        if (isReadOnly) return;

                        setLocalFlags((prev) => ({ ...prev, [flagKey]: newValue }));
                        setFlagUpdateStatus((prev) => ({ ...prev, [flagKey]: "saving" }));

                        try {
                                const res = await fetch("/api/v1/feature-flags", {
                                        method: "POST",
                                        headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify({ flag: flagKey, enabled: newValue }),
                                });
                                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                                setFlagUpdateStatus((prev) => ({ ...prev, [flagKey]: "saved" }));
                                refetchHealth();
                        } catch {
                                setLocalFlags((prev) => ({ ...prev, [flagKey]: !newValue }));
                                setFlagUpdateStatus((prev) => ({ ...prev, [flagKey]: "error" }));
                        } finally {
                                setTimeout(() => {
                                        setFlagUpdateStatus((prev) => {
                                                const next = { ...prev };
                                                delete next[flagKey];
                                                return next;
                                        });
                                }, 3000);
                        }
                },
                [isReadOnly, refetchHealth],
        );

        const [saveStatus, setSaveStatus] = useState<string | null>(null);

        const persistSettings = (key: string, value: Record<string, unknown>) => {
                try {
                        const safeValue: Record<string, unknown> = {};
                        const SENSITIVE_KEYS = [
                                "apiKey",
                                "api_key",
                                "password",
                                "token",
                                "secret",
                        ];
                        for (const [k, v] of Object.entries(value)) {
                                if (
                                        !SENSITIVE_KEYS.some((s) => k.toLowerCase().includes(s.toLowerCase()))
                                ) {
                                        safeValue[k] = v;
                                }
                        }
                        localStorage.setItem(`fireai_settings_${key}`, JSON.stringify(safeValue));
                        setSaveStatus("saved");
                        setTimeout(() => setSaveStatus(null), 2000);
                } catch {
                        setSaveStatus("error");
                        setTimeout(() => setSaveStatus(null), 3000);
                }
        };

        const handleSaveGeneral = () => {
                persistSettings("general", { theme, language, notifications });
        };

        const handleSaveSecurity = () => {
                persistSettings("security", { twoFactorAuth, passwordExpiry });
        };

        const handleSaveApi = () => {
                persistSettings("api", { apiTimeout, retryAttempts });
        };

        const handleSaveReports = () => {
                persistSettings("reports", {
                        autoSaveReports,
                        reportFormat,
                        reportQuality,
                });
        };

        return (
                <div className="flex-1 overflow-auto" aria-label={t("settings.title")}>
                        <div className="p-6 max-w-4xl mx-auto space-y-6">
                                {/* Header */}
                                <div className="flex items-center justify-between">
                                        <div>
                                                <h1 className="text-2xl font-bold text-foreground">
                                                        {t("settings.title")}
                                                </h1>
                                                <p className="text-sm text-muted-foreground mt-1">
                                                        {t("settings.subtitle")}
                                                </p>
                                        </div>
                                        <Button
                                                variant="outline"
                                                className="border-border text-foreground/90 hover:bg-card"
                                                onClick={() => refetchHealth()}
                                        >
                                                <Activity aria-hidden="true" className="h-4 w-4 mr-1" />
                                                {t("common.refresh")}
                                        </Button>
                                </div>

                                {/* System Health */}
                                <Card className="border-border bg-card">
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                        <Activity aria-hidden="true" className="h-5 w-5 text-info" />
                                                        {t("settings.systemHealth")}
                                                </CardTitle>
                                                <CardDescription
                                                        className="text-muted-foreground"
                                                        aria-live="polite"
                                                        aria-atomic="true"
                                                >
                                                        {healthLoading
                                                                ? "Checking system status…"
                                                                : "Current system status and performance metrics"}
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                                <div className="flex items-center gap-4 text-sm">
                                                        <div className="flex items-center gap-2">
                                                                {connected ? (
                                                                        <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-success" />
                                                                ) : (
                                                                        <XCircle aria-hidden="true" className="h-5 w-5 text-danger" />
                                                                )}
                                                                <span>{connected ? "Connected" : "Disconnected"}</span>
                                                        </div>
                                                        {health && (
                                                                <>
                                                                        <Separator
                                                                                orientation="vertical"
                                                                                className="h-5 bg-secondary"
                                                                        />
                                                                        <div className="flex items-center gap-2">
                                                                                <span>API v{health.version}</span>
                                                                        </div>
                                                                        <Separator
                                                                                orientation="vertical"
                                                                                className="h-5 bg-secondary"
                                                                        />
                                                                        <div className="flex items-center gap-2">
                                                                                <span>DB: {health.database}</span>
                                                                        </div>
                                                                        <Separator
                                                                                orientation="vertical"
                                                                                className="h-5 bg-secondary"
                                                                        />
                                                                        <div className="flex items-center gap-2">
                                                                                <span>
                                                                                        Uptime: {Math.floor((health.uptime || 0) / 60)} min
                                                                                </span>
                                                                        </div>
                                                                </>
                                                        )}
                                                </div>
                                        <div className="pt-4 flex items-center justify-between border-t border-border">
                                                <div>
                                                        <p className="text-sm font-medium text-foreground">Database Administration</p>
                                                        <p className="text-xs text-muted-foreground">Manage Redis, Neo4j, Qdrant connections</p>
                                                </div>
                                                <Button
                                                        variant="outline"
                                                        className="border-border text-foreground/90 hover:bg-card"
                                                        onClick={() => navigate("/settings/database")}
                                                >
                                                        <Database aria-hidden="true" className="h-4 w-4 mr-1" />
                                                        Manage Databases
                                                </Button>
                                        </div>
                                        </CardContent>
                                </Card>

                                {/* Report Generator Quick Access */}
                                <Card className="border-border bg-card">
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-lg text-foreground">
                                                        {t("settings.advancedReportGenerator")}
                                                </CardTitle>
                                                <CardDescription className="text-muted-foreground">
                                                        {t("settings.reportGeneratorDesc")}
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                                <div className="flex flex-col sm:flex-row gap-4">
                                                        <div className="flex-1">
                                                                <h3 className="font-medium text-foreground mb-2">
                                                                        {t("settings.comprehensiveReportGeneration")}
                                                                </h3>
                                                                <p className="text-sm text-muted-foreground">
                                                                        {t("settings.comprehensiveReportDesc")}
                                                                </p>
                                                        </div>
                                                                <Button
                                                                        onClick={() => navigate("/reports")}
                                                                        className="bg-primary hover:bg-primary/90 text-primary-foreground border-none flex items-center gap-2"
                                                                        aria-label={t("settings.openReportGenerator")}
                                                                >
                                                                        <Calculator aria-hidden="true" className="h-4 w-4" />
                                                                        {t("settings.openReportGenerator")}
                                                                </Button>
                                                </div>
                                        </CardContent>
                                </Card>

                                {/* Settings Tabs */}
                                <Tabs value={activeTab} onValueChange={setActiveTab}>
                                        <TabsList className="bg-card border border-border">
                                                <TabsTrigger
                                                        value="general"
                                                        className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
                                                >
                                                        <Settings aria-hidden="true" className="h-4 w-4 mr-1" /> {t("settings.general")}
                                                </TabsTrigger>
                                                <TabsTrigger
                                                        value="security"
                                                        className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
                                                >
                                                        <Shield aria-hidden="true" className="h-4 w-4 mr-1" /> {t("settings.security")}
                                                </TabsTrigger>
                                                <TabsTrigger
                                                        value="api"
                                                        className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
                                                >
                                                        <Database aria-hidden="true" className="h-4 w-4 mr-1" /> {t("settings.api")}
                                                </TabsTrigger>
                                                <TabsTrigger
                                                        value="reports"
                                                        className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
                                                >
                                                        <Calculator aria-hidden="true" className="h-4 w-4 mr-1" /> {t("settings.reports")}
                                                </TabsTrigger>
                                                <TabsTrigger
                                                        value="feature-flags"
                                                        className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
                                                >
                                                        <Settings aria-hidden="true" className="h-4 w-4 mr-1" /> {t("settings.featureFlags")}
                                                </TabsTrigger>
                                        </TabsList>

                                        {/* General Settings */}
                                        <TabsContent value="general">
                                                <Card className="border-border bg-card">
                                                        <CardHeader className="pb-3">
                                                                <CardTitle className="text-lg text-foreground">
                                                                        {t("settings.general")}
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        {t("settings.generalDescription")}
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        {t("settings.theme")}
                                                                                </Label>
                                                                                <select
                                                                                        value={theme}
                                                                                        onChange={(e) => setTheme(e.target.value)}
                                                                                        className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                                                                                >
                                                                                        <option value="light">{t("settings.light")}</option>
                                                                                        <option value="dark">{t("settings.dark")}</option>
                                                                                        <option value="system">{t("settings.system")}</option>
                                                                                </select>
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        {t("settings.language")}
                                                                                </Label>
                                                                                <select
                                                                                        value={language}
                                                                                        onChange={(e) => setLanguage(e.target.value)}
                                                                                        className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                                                                                >
                                                                                        <option value="en">English</option>
                                                                                        <option value="es">Español</option>
                                                                                        <option value="fr">Français</option>
                                                                                        <option value="de">Deutsch</option>
                                                                                </select>
                                                                        </div>
                                                                </div>
                                                                <div className="flex items-center justify-between py-3">
                                                                        <div>
                                                                                <Label className="text-foreground/90">
                                                                                        {t("settings.notifications")}
                                                                                </Label>
                                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                                        {t("settings.notificationsDescription")}
                                                                                </p>
                                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                                        Client-side only — does not affect server behavior
                                                                                </p>
                                                                        </div>
                                                                        <Switch
                                                                                checked={notifications}
                                                                                onCheckedChange={setNotifications}
                                                                                className="data-[state=checked]:bg-danger"
                                                                        />
                                                                </div>
                                                                                <div className="pt-4">
                                                                                        <Button
                                                                                                className="bg-primary hover:bg-primary/90 text-primary-foreground border-none"
                                                                                                onClick={handleSaveGeneral}
                                                                                        >
                                                                                                {t("settings.save")}
                                                                                        </Button>
                                                                                </div>
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>

                                        {/* Security Settings */}
                                        <TabsContent value="security">
                                                <Card className="border-border bg-card">
                                                        <CardHeader className="pb-3">
                                                                <CardTitle className="text-lg text-foreground">
                                                                        {t("settings.security")}
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        {t("settings.securityDescription")}
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="flex items-center justify-between py-3">
                                                                        <div>
                                                                                <Label className="text-foreground/90">
                                                                                        {t("settings.twoFactorAuth")}
                                                                                        <span className="ml-2 text-xs text-amber-500">(Coming Soon)</span>
                                                                                </Label>
                                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                                        {t("settings.twoFactorAuthDescription")}
                                                                                </p>
                                                                                <p className="text-xs text-amber-500 mt-1">
                                                                                        This feature is not yet functional — enabling it has no effect until backend support is implemented.
                                                                                </p>
                                                                        </div>
                                                                        {/* V253: 2FA toggle is disabled until backend enforcement
                                                                            is implemented. Currently only persists to localStorage
                                                                            with no server-side verification. */}
                                                                        <Switch
                                                                                checked={twoFactorAuth}
                                                                                onCheckedChange={setTwoFactorAuth}
                                                                                disabled
                                                                                className="data-[state=checked]:bg-danger opacity-50 cursor-not-allowed"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("settings.passwordExpiry")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={passwordExpiry}
                                                                                onChange={(e) =>
                                                                                        setPasswordExpiry(Number.parseInt(e.target.value, 10))
                                                                                }
                                                                                className="bg-card border-border text-foreground"
                                                                        />
                                                                        <p className="text-xs text-muted-foreground">
                                                                                {t("settings.passwordExpiryDescription")}
                                                                        </p>
                                                                        <p className="text-xs text-muted-foreground mt-1">
                                                                                Client-side only — does not affect server behavior
                                                                        </p>
                                                                </div>
                                                                                <div className="pt-4">
                                                                                        <Button
                                                                                                className="bg-primary hover:bg-primary/90 text-primary-foreground border-none"
                                                                                                onClick={handleSaveSecurity}
                                                                                        >
                                                                                                {t("settings.save")}
                                                                                        </Button>
                                                                                </div>
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>

                                        {/* API Settings */}
                                        <TabsContent value="api">
                                                <Card className="border-border bg-card">
                                                        <CardHeader className="pb-3">
                                                                <CardTitle className="text-lg text-foreground">
                                                                        {t("settings.api")}
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        {t("settings.apiDescription")}
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        {t("settings.apiTimeout")}
                                                                                </Label>
                                                                                <Input
                                                                                        type="number"
                                                                                        value={apiTimeout}
                                                                                        onChange={(e) =>
                                                                                                setApiTimeout(Number.parseInt(e.target.value, 10))
                                                                                        }
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                                <p className="text-xs text-muted-foreground">
                                                                                        {t("settings.apiTimeoutDescription")}
                                                                                </p>
                                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                                        Client-side only — does not affect server behavior
                                                                                </p>
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        {t("settings.retryAttempts")}
                                                                                </Label>
                                                                                <Input
                                                                                        type="number"
                                                                                        value={retryAttempts}
                                                                                        onChange={(e) =>
                                                                                                setRetryAttempts(Number.parseInt(e.target.value, 10))
                                                                                        }
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                                <p className="text-xs text-muted-foreground">
                                                                                        {t("settings.retryAttemptsDescription")}
                                                                                </p>
                                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                                        Client-side only — does not affect server behavior
                                                                                </p>
                                                                        </div>
                                                                </div>
                                                                                <div className="pt-4">
                                                                                        <Button
                                                                                                className="bg-primary hover:bg-primary/90 text-primary-foreground border-none"
                                                                                                onClick={handleSaveApi}
                                                                                        >
                                                                                                {t("settings.save")}
                                                                                        </Button>
                                                                                </div>
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>

                                        {/* Report Settings */}
                                        <TabsContent value="reports">
                                                <Card className="border-border bg-card">
                                                        <CardHeader className="pb-3">
                                                                <CardTitle className="text-lg text-foreground">
                                                                        {t("settings.reports")}
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        {t("settings.reportGeneratorDesc")}
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="flex items-center justify-between py-3">
                                                                        <div>
                                                                                <Label className="text-foreground/90">
                                                                                        {t("settings.autoSaveReports")}
                                                                                </Label>
                                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                                        {t("settings.autoSaveReportsDesc")}
                                                                                </p>
                                                                        </div>
                                                                        <Switch
                                                                                checked={autoSaveReports}
                                                                                onCheckedChange={setAutoSaveReports}
                                                                                className="data-[state=checked]:bg-danger"
                                                                        />
                                                                </div>
                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        {t("settings.reportFormat")}
                                                                                </Label>
                                                                                <select
                                                                                        value={reportFormat}
                                                                                        onChange={(e) => setReportFormat(e.target.value)}
                                                                                        className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                                                                                >
                                                                                        <option value="pdf">PDF</option>
                                                                                        <option value="json">JSON</option>
                                                                                        <option value="excel">Excel</option>
                                                                                        <option value="xml">XML</option>
                                                                                </select>
                                                                                <p className="text-xs text-muted-foreground">
                                                                                        {t("settings.reportFormatDesc")}
                                                                                </p>
                                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                                        Client-side only — does not affect server behavior
                                                                                </p>
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        {t("settings.reportQuality")}
                                                                                </Label>
                                                                                <select
                                                                                        value={reportQuality}
                                                                                        onChange={(e) => setReportQuality(e.target.value)}
                                                                                        className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                                                                                >
                                                                                        <option value="low">Low (Fast)</option>
                                                                                        <option value="medium">Medium</option>
                                                                                        <option value="high">High (Detailed)</option>
                                                                                </select>
                                                                                <p className="text-xs text-muted-foreground">
                                                                                        {t("settings.reportQualityDesc")}
                                                                                </p>
                                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                                        Client-side only — does not affect server behavior
                                                                                </p>
                                                                        </div>
                                                                </div>
                                                                                <div className="pt-4">
                                                                                        <Button
                                                                                                className="bg-primary hover:bg-primary/90 text-primary-foreground border-none"
                                                                                                onClick={handleSaveReports}
                                                                                        >
                                                                                                {t("settings.saveReportSettings")}
                                                                                        </Button>
                                                                                </div>
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>

                                        {/* Feature Flags */}
                                        <TabsContent value="feature-flags">
                                                <Card className="border-border bg-card">
                                                        <CardHeader className="pb-3">
                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                        <Activity aria-hidden="true" className="h-5 w-5 text-info" />
                                                                        {t("settings.featureFlags")}
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        {t("settings.featureFlagsDescription")}
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                {isReadOnly && (
                                                                        <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-400">
                                                                                {t("settings.featureFlagsReadOnly")}
                                                                        </div>
                                                                )}
                                                                {FEATURE_FLAG_DEFINITIONS.map((flagDef) => {
                                                                        const value = featureFlags[flagDef.key] ?? flagDef.default;
                                                                        const status = flagUpdateStatus[flagDef.key];
                                                                        return (
                                                                                <div
                                                                                        key={flagDef.key}
                                                                                        className="flex items-center justify-between py-3"
                                                                                >
                                                                                        <div className="flex-1 min-w-0">
                                                                                                <Label className="text-foreground/90">
                                                                                                        {flagDef.name}
                                                                                                        <code className="ml-2 text-xs text-muted-foreground bg-secondary px-1.5 py-0.5 rounded">
                                                                                                                {flagDef.key}
                                                                                                        </code>
                                                                                                </Label>
                                                                                                <p className="text-xs text-muted-foreground mt-1">
                                                                                                        {flagDef.description}
                                                                                                </p>
                                                                                                {status === "saving" && (
                                                                                                        <p className="text-xs text-info mt-1">{t("settings.saving")}</p>
                                                                                                )}
                                                                                                {status === "saved" && (
                                                                                                        <p className="text-xs text-success mt-1">{t("settings.saved")}</p>
                                                                                                )}
                                                                                                {status === "error" && (
                                                                                                        <p className="text-xs text-danger mt-1">{t("settings.saveError")}</p>
                                                                                                )}
                                                                                        </div>
                                                                                        <Switch
                                                                                                checked={value}
                                                                                                onCheckedChange={(checked: boolean) =>
                                                                                                        handleFlagToggle(flagDef.key, checked)
                                                                                                }
                                                                                                disabled={isReadOnly || status === "saving"}
                                                                                                className="data-[state=checked]:bg-primary"
                                                                                                aria-label={flagDef.name}
                                                                                        />
                                                                                </div>
                                                                        );
                                                                })}
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>
                                </Tabs>

                                {/* Save status announcement for screen readers */}
                                <div
                                        role="status"
                                        aria-live="polite"
                                        aria-atomic="true"
                                        className="text-sm text-center"
                                >
                                        {saveStatus === "saved" && (
                                                <span className="text-success">
                                                        <CheckCircle2 aria-hidden="true" className="h-4 w-4 inline mr-1" />
                                                        Settings saved successfully
                                                </span>
                                        )}
                                        {saveStatus === "error" && (
                                                <span className="text-danger">
                                                        <XCircle aria-hidden="true" className="h-4 w-4 inline mr-1" />
                                                        Failed to save settings
                                                </span>
                                        )}
                                </div>
                        </div>
                </div>
        );
}
