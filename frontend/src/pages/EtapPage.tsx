/**
 * EtapPage.tsx — ETAP Power System Integration.
 *
 * Professional engineering interface inspired by electrical power system
 * HMI displays and switchgear control panels. Amber accent references
 * warning indicators, arc-flash labels, and power system instrumentation.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
        Activity,
        AlertTriangle,
        CheckCircle2,
        Download,
        Globe,
        Import,
        Loader2,
        Play,
        RefreshCw,
        Save,
        Server,
        Settings2,
        ShieldAlert,
        Trash2,
        Upload,
        XCircle,
        Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
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
import {
        Select,
        SelectContent,
        SelectItem,
        SelectTrigger,
        SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { etapApi, type EtapConnectionSettings, type EtapExportRequest, type EtapImportRequest, type EtapProjectInfo, type EtapSettingsResponse, type EtapSyncLog } from "@/services/fullApi";
import "./../styles/etap-theme.css";

const DEFAULT_PROJECT_ID = "default";

type TabValue = "connection" | "projects" | "sync" | "logs";

export function EtapPage() {
        const { t } = useTranslation();
        const { toast } = useToast();

        // Connection state
        const [connectionStatus, setConnectionStatus] = useState<"disconnected" | "connecting" | "connected" | "error">("disconnected");
        const [connectionMessage, setConnectionMessage] = useState<string>("");
        const [serverVersion, setServerVersion] = useState<string>("");

        // Settings form
        const [settings, setSettings] = useState<EtapConnectionSettings>({
                host: "",
                port: 9876,
                username: "",
                password: "",
                timeout_seconds: 30,
        });
        const [savedSettings, setSavedSettings] = useState<EtapSettingsResponse | null>(null);
        const [settingsLoaded, setSettingsLoaded] = useState(false);

        // Projects
        const [etapProjects, setEtapProjects] = useState<EtapProjectInfo[]>([]);
        const [localProjects, setLocalProjects] = useState<{ id: string; name: string }[]>([]);
        const [selectedLocalProject, setSelectedLocalProject] = useState<string>(DEFAULT_PROJECT_ID);
        const [selectedEtapProject, setSelectedEtapProject] = useState<string>("");

        // Export/Import forms
        const [exportFormat, setExportFormat] = useState<"csv" | "ort">("csv");
        const [includeLoads, setIncludeLoads] = useState(true);
        const [includeSources, setIncludeSources] = useState(true);
        const [includeTopology, setIncludeTopology] = useState(false);
        const [importLoads, setImportLoads] = useState(true);
        const [importSources, setImportSources] = useState(true);
        const [conflictResolution, setConflictResolution] = useState<"skip" | "overwrite" | "merge">("skip");

        // Logs
        const [logs, setLogs] = useState<EtapSyncLog[]>([]);
        const [logsPage, setLogsPage] = useState(1);

        // UI state
        const [loading, setLoading] = useState<string | null>(null);
        const [showPassword, setShowPassword] = useState(false);
        const [syncEnabled, setSyncEnabled] = useState(false);
        const [activeTab, setActiveTab] = useState<TabValue>("connection");

        const loadSettings = async () => {
                setLoading("loading-settings");
                try {
                        const data = await etapApi.getSettings(selectedLocalProject);
                        if (data) {
                                setSavedSettings(data);
                                setSettings({
                                        host: data.host,
                                        port: data.port,
                                        username: data.username,
                                        password: "",
                                        timeout_seconds: 30,
                                });
                                setSyncEnabled(data.enabled);
                        }
                        setSettingsLoaded(true);
                } catch (error) {
                        console.error("Failed to load ETAP settings", error);
                } finally {
                        setLoading(null);
                }
        };

        const loadProjects = async () => {
                setLoading("loading-projects");
                try {
                        const [etap, local] = await Promise.all([
                                etapApi.listEtapProjects(selectedLocalProject),
                                etapApi.listLocalProjects(),
                        ]);
                        setEtapProjects(etap);
                        setLocalProjects(local.map((p: any) => ({ id: p.id, name: p.name })));
                } catch (error) {
                        console.error("Failed to load projects", error);
                } finally {
                        setLoading(null);
                }
        };

        const loadLogs = async () => {
                setLoading("loading-logs");
                try {
                        const data = await etapApi.getLogs(selectedLocalProject, logsPage, 20);
                        setLogs(data.items || []);
                } catch (error) {
                        console.error("Failed to load logs", error);
                } finally {
                        setLoading(null);
                }
        };

        const handleTestConnection = async () => {
                if (!settings.host || !settings.port || !settings.username || !settings.password) {
                        toast({
                                title: t("etap.missingFields"),
                                description: t("etap.fillAllFields"),
                                variant: "destructive",
                        });
                        return;
                }

                setConnectionStatus("connecting");
                setConnectionMessage("");
                setServerVersion("");

                try {
                        const response = await etapApi.testConnection(settings, selectedLocalProject);
                        if (response.success) {
                                setConnectionStatus("connected");
                                setConnectionMessage(response.message || "Connected");
                                setServerVersion(response.server_version || "");
                                toast({
                                        title: t("etap.connectionSuccess"),
                                        description: response.message,
                                });
                        } else {
                                setConnectionStatus("error");
                                setConnectionMessage(response.message);
                                toast({
                                        title: t("etap.connectionFailed"),
                                        description: response.message,
                                        variant: "destructive",
                                });
                        }
                } catch (error: any) {
                        setConnectionStatus("error");
                        setConnectionMessage(error.message || "Connection failed");
                        toast({
                                title: t("etap.connectionError"),
                                description: error.message,
                                variant: "destructive",
                        });
                }
        };

        const handleSaveSettings = async () => {
                setLoading("saving-settings");
                try {
                        if (savedSettings) {
                                await etapApi.updateSettings(selectedLocalProject, {
                                        host: settings.host,
                                        port: settings.port,
                                        username: settings.username,
                                        password: settings.password || undefined,
                                        timeout_seconds: settings.timeout_seconds,
                                        enabled: syncEnabled,
                                });
                        } else {
                                await etapApi.createSettings(selectedLocalProject, settings);
                        }
                        await loadSettings();
                        toast({
                                title: t("etap.settingsSaved"),
                                description: t("etap.settingsSavedDesc"),
                        });
                } catch (error: any) {
                        toast({
                                title: t("etap.saveFailed"),
                                description: error.message,
                                variant: "destructive",
                        });
                } finally {
                        setLoading(null);
                }
        };

        const handleDeleteSettings = async () => {
                setLoading("deleting-settings");
                try {
                        await etapApi.deleteSettings(selectedLocalProject);
                        setSavedSettings(null);
                        setSettings({
                                host: "",
                                port: 9876,
                                username: "",
                                password: "",
                                timeout_seconds: 30,
                        });
                        setSyncEnabled(false);
                        setConnectionStatus("disconnected");
                        toast({
                                title: t("etap.settingsDeleted"),
                                description: t("etap.settingsDeletedDesc"),
                        });
                } catch (error: any) {
                        toast({
                                title: t("etap.deleteFailed"),
                                description: error.message,
                                variant: "destructive",
                        });
                } finally {
                        setLoading(null);
                }
        };

        const handleExport = async () => {
                setLoading("exporting");
                try {
                        const request: EtapExportRequest = {
                                project_id: selectedLocalProject,
                                include_loads: includeLoads,
                                include_sources: includeSources,
                                include_topology: includeTopology,
                                format: exportFormat,
                        };
                        const response = await etapApi.exportToEtap(request);
                        toast({
                                title: t("etap.exportSuccess"),
                                description: `${t("etap.exportedRecords")}: ${response.records_exported}`,
                        });
                        await loadLogs();
                } catch (error: any) {
                        toast({
                                title: t("etap.exportFailed"),
                                description: error.message,
                                variant: "destructive",
                        });
                } finally {
                        setLoading(null);
                }
        };

        const handleImport = async () => {
                if (!selectedEtapProject) {
                        toast({
                                title: t("etap.selectEtapProject"),
                                description: t("etap.selectEtapProjectDesc"),
                                variant: "destructive",
                        });
                        return;
                }

                setLoading("importing");
                try {
                        const request: EtapImportRequest = {
                                project_id: selectedLocalProject,
                                etap_project_id: selectedEtapProject,
                                import_loads: importLoads,
                                import_sources: importSources,
                                conflict_resolution: conflictResolution,
                        };
                        const response = await etapApi.importFromEtap(request);
                        toast({
                                title: t("etap.importSuccess"),
                                description: response.message,
                        });
                        await loadLogs();
                } catch (error: any) {
                        toast({
                                title: t("etap.importFailed"),
                                description: error.message,
                                variant: "destructive",
                        });
                } finally {
                        setLoading(null);
                }
        };

        const handleTabChange = (value: string) => {
                const tab = value as TabValue;
                setActiveTab(tab);
                if (tab === "projects") {
                        loadProjects();
                } else if (tab === "logs") {
                        loadLogs();
                } else if (tab === "connection" && !settingsLoaded) {
                        loadSettings();
                }
        };

        const getStatusBadge = () => {
                const label = {
                        connected: t("etap.connected", "Connected"),
                        connecting: t("etap.connecting", "Connecting"),
                        error: t("etap.error", "Error"),
                        disconnected: t("etap.disconnected", "Disconnected"),
                }[connectionStatus];

                return (
                        <span className="etap-status-pill" data-status={connectionStatus}>
                                <span className="etap-status-dot" />
                                {label}
                        </span>
                );
        };

        return (
                <div className="etap-page">
                        <div className="relative">
                                {/* Circuit decoration — signature element */}
                                <div className="etap-circuit-bg" aria-hidden="true">
                                        <div className="etap-circuit-line" />
                                        <div className="etap-circuit-line" />
                                        <div className="etap-circuit-line" />
                                </div>

                                {/* Header */}
                                <header className="etap-header relative z-10">
                                        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex items-center justify-between">
                                                <div className="flex items-center gap-3">
                                                        <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30">
                                                                <Zap className="h-6 w-6 text-amber-400" />
                                                        </div>
                                                        <div>
                                                                <h1 className="etap-title">ETAP Integration</h1>
                                                                <p className="etap-subtitle">
                                                                        Power system analysis interconnect — host, sync, and transfer
                                                                        load and source data between ETAP and BAZSPARK.
                                                                </p>
                                                        </div>
                                                </div>
                                                <div className="flex items-center gap-3">
                                                        {getStatusBadge()}
                                                </div>
                                        </div>
                                </header>

                                {/* Main content */}
                                <main className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
                                        <Tabs value={activeTab} onValueChange={handleTabChange} className="space-y-4">
                                                <TabsList className="etap-tabs w-full justify-start rounded-none bg-transparent border-b border-white/10 p-0">
                                                        <TabsTrigger value="connection" className="etap-tab rounded-none border-b-2 border-transparent">
                                                                <Settings2 className="h-4 w-4 mr-2" />
                                                                Connection
                                                        </TabsTrigger>
                                                        <TabsTrigger value="projects" className="etap-tab rounded-none border-b-2 border-transparent">
                                                                <Globe className="h-4 w-4 mr-2" />
                                                                Projects
                                                        </TabsTrigger>
                                                        <TabsTrigger value="sync" className="etap-tab rounded-none border-b-2 border-transparent">
                                                                <RefreshCw className="h-4 w-4 mr-2" />
                                                                Synchronization
                                                        </TabsTrigger>
                                                        <TabsTrigger value="logs" className="etap-tab rounded-none border-b-2 border-transparent">
                                                                <Activity className="h-4 w-4 mr-2" />
                                                                Sync Logs
                                                        </TabsTrigger>
                                                </TabsList>

                                                {/* Connection Tab */}
                                                <TabsContent value="connection" className="space-y-4 mt-4">
                                                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                                                                <Card className="etap-panel lg:col-span-2">
                                                                        <CardHeader className="etap-panel-header">
                                                                                <CardTitle className="etap-panel-title">
                                                                                        <Server className="h-5 w-5 etap-panel-title-icon" />
                                                                                        Host Configuration
                                                                                </CardTitle>
                                                                                <CardDescription className="etap-panel-description">
                                                                                        Define the ETAP server endpoint, credentials, and network timeout for this integration.
                                                                                </CardDescription>
                                                                        </CardHeader>
                                                                        <CardContent className="etap-panel-body">
                                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                                        <div className="etap-field">
                                                                                                <Label htmlFor="host" className="etap-label">Host</Label>
                                                                                                <Input
                                                                                                        id="host"
                                                                                                        value={settings.host}
                                                                                                        onChange={(e) => setSettings({ ...settings, host: e.target.value })}
                                                                                                        placeholder="etap.example.com"
                                                                                                        className="etap-input"
                                                                                                />
                                                                                        </div>
                                                                                        <div className="etap-field">
                                                                                                <Label htmlFor="port" className="etap-label">Port</Label>
                                                                                                <Input
                                                                                                        id="port"
                                                                                                        type="number"
                                                                                                        value={settings.port}
                                                                                                        onChange={(e) => setSettings({ ...settings, port: parseInt(e.target.value) || 0 })}
                                                                                                        className="etap-input"
                                                                                                />
                                                                                        </div>
                                                                                        <div className="etap-field">
                                                                                                <Label htmlFor="username" className="etap-label">Username</Label>
                                                                                                <Input
                                                                                                        id="username"
                                                                                                        value={settings.username}
                                                                                                        onChange={(e) => setSettings({ ...settings, username: e.target.value })}
                                                                                                        className="etap-input"
                                                                                                />
                                                                                        </div>
                                                                                        <div className="etap-field">
                                                                                                <Label htmlFor="password" className="etap-label">Password</Label>
                                                                                                <div className="relative">
                                                                                                        <Input
                                                                                                                id="password"
                                                                                                                type={showPassword ? "text" : "password"}
                                                                                                                value={settings.password}
                                                                                                                onChange={(e) => setSettings({ ...settings, password: e.target.value })}
                                                                                                                className="etap-input pr-10"
                                                                                                        />
                                                                                                        <Button
                                                                                                                type="button"
                                                                                                                variant="ghost"
                                                                                                                size="sm"
                                                                                                                className="absolute right-0 top-0 h-full px-3 text-slate-400 hover:text-white"
                                                                                                                onClick={() => setShowPassword(!showPassword)}
                                                                                                        >
                                                                                                                {showPassword ? <EyeOffIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                                                                                                        </Button>
                                                                                                </div>
                                                                                        </div>
                                                                                        <div className="etap-field">
                                                                                                <Label htmlFor="timeout" className="etap-label">Timeout (seconds)</Label>
                                                                                                <Input
                                                                                                        id="timeout"
                                                                                                        type="number"
                                                                                                        value={settings.timeout_seconds}
                                                                                                        onChange={(e) => setSettings({ ...settings, timeout_seconds: parseInt(e.target.value) || 30 })}
                                                                                                        className="etap-input"
                                                                                                />
                                                                                        </div>
                                                                                </div>

                                                                                <div className="flex flex-wrap items-center gap-2 mt-6">
                                                                                        <Button onClick={handleTestConnection} disabled={connectionStatus === "connecting"} className="etap-btn etap-btn-primary">
                                                                                                {connectionStatus === "connecting" ? (
                                                                                                        <Loader2 className="h-4 w-4 animate-spin" />
                                                                                                ) : (
                                                                                                        <Play className="h-4 w-4" />
                                                                                                )}
                                                                                                Test Connection
                                                                                        </Button>
                                                                                        <Button onClick={handleSaveSettings} disabled={loading === "saving-settings"} className="etap-btn etap-btn-primary">
                                                                                                {loading === "saving-settings" ? (
                                                                                                        <Loader2 className="h-4 w-4 animate-spin" />
                                                                                                ) : (
                                                                                                        <Save className="h-4 w-4" />
                                                                                                )}
                                                                                                Save Configuration
                                                                                        </Button>
                                                                                        {savedSettings && (
                                                                                                <Button onClick={handleDeleteSettings} disabled={loading === "deleting-settings"} className="etap-btn etap-btn-danger">
                                                                                                        {loading === "deleting-settings" ? (
                                                                                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                                                                        ) : (
                                                                                                                <Trash2 className="h-4 w-4" />
                                                                                                        )}
                                                                                                        Remove Configuration
                                                                                                </Button>
                                                                                        )}
                                                                                </div>

                                                                                {connectionMessage && (
                                                                                        <div className={`etap-alert mt-4 ${connectionStatus === "connected" ? "etap-alert-success" : connectionStatus === "error" ? "etap-alert-error" : ""}`}>
                                                                                                {connectionStatus === "connected" ? <CheckCircle2 className="h-5 w-5 mt-0.5" /> :
                                                                                                 connectionStatus === "error" ? <AlertTriangle className="h-5 w-5 mt-0.5" /> :
                                                                                                 <Activity className="h-5 w-5 mt-0.5" />}
                                                                                                <div>
                                                                                                        <p className="font-medium">{connectionMessage}</p>
                                                                                                        {serverVersion && <p className="text-sm mt-1 opacity-80 font-mono">{serverVersion}</p>}
                                                                                                </div>
                                                                                        </div>
                                                                                )}

                                                                                <hr className="etap-divider" />

                                                                                <div className="flex items-center justify-between p-4 rounded-lg border border-white/10 bg-black/20">
                                                                                        <div className="flex items-center gap-3">
                                                                                                <RefreshCw className="h-5 w-5 text-amber-400" />
                                                                                                <div>
                                                                                                        <Label className="etap-label" style={{ marginBottom: 0 }}>Auto Synchronization</Label>
                                                                                                        <p className="text-sm text-slate-400 mt-1">Enable scheduled sync between ETAP and local project store.</p>
                                                                                                </div>
                                                                                        </div>
                                                                                        <Switch checked={syncEnabled} onCheckedChange={setSyncEnabled} className="etap-toggle" />
                                                                                </div>
                                                                        </CardContent>
                                                                </Card>

                                                                <div className="space-y-4">
                                                                        <Card className="etap-panel">
                                                                                <CardHeader className="etap-panel-header">
                                                                                        <CardTitle className="etap-panel-title">
                                                                                                <ShieldAlert className="h-5 w-5 etap-panel-title-icon" />
                                                                                                Security Notice
                                                                                        </CardTitle>
                                                                                </CardHeader>
                                                                                <CardContent className="etap-panel-body text-sm text-slate-400 space-y-2">
                                                                                        <p>Credentials are encrypted at rest using Fernet AES-128. The password field is never returned by the API after creation.</p>
                                                                                        <p className="font-mono text-xs text-slate-500">RBAC: INTEGRATION_READ / INTEGRATION_MANAGE</p>
                                                                                </CardContent>
                                                                        </Card>
                                                                </div>
                                                        </div>
                                                </TabsContent>

                                                {/* Projects Tab */}
                                                <TabsContent value="projects" className="space-y-4 mt-4">
                                                        <Card className="etap-panel">
                                                                        <CardHeader className="etap-panel-header">
                                                                                <CardTitle className="etap-panel-title">
                                                                                        <Globe className="h-5 w-5 etap-panel-title-icon" />
                                                                                        Project Mapping
                                                                                </CardTitle>
                                                                                <CardDescription className="etap-panel-description">
                                                                                        Map a local BAZSPARK project to an ETAP remote project for import and export operations.
                                                                                </CardDescription>
                                                                        </CardHeader>
                                                                        <CardContent className="etap-panel-body">
                                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                                        <div className="etap-field">
                                                                                                <Label className="etap-label">Local Project</Label>
                                                                                                <Select value={selectedLocalProject} onValueChange={setSelectedLocalProject}>
                                                                                                        <SelectTrigger className="etap-input">
                                                                                                                <SelectValue placeholder={t("etap.selectLocalProject")} />
                                                                                                        </SelectTrigger>
                                                                                                        <SelectContent>
                                                                                                                {localProjects.map((p) => (
                                                                                                                        <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                                                                                                                ))}
                                                                                                        </SelectContent>
                                                                                                </Select>
                                                                                        </div>
                                                                                        <div className="etap-field">
                                                                                                <Label className="etap-label">ETAP Remote Project</Label>
                                                                                                <Select value={selectedEtapProject} onValueChange={setSelectedEtapProject}>
                                                                                                        <SelectTrigger className="etap-input">
                                                                                                                <SelectValue placeholder={t("etap.selectEtapProject")} />
                                                                                                        </SelectTrigger>
                                                                                                        <SelectContent>
                                                                                                                {etapProjects.map((p) => (
                                                                                                                        <SelectItem key={p.project_id} value={p.project_id}>
                                                                                                                                {p.name} {p.size_mb ? `(${p.size_mb} MB)` : ""}
                                                                                                                        </SelectItem>
                                                                                                                ))}
                                                                                                        </SelectContent>
                                                                                                </Select>
                                                                                        </div>
                                                                                </div>
                                                                        </CardContent>
                                                        </Card>
                                                </TabsContent>

                                                {/* Sync Tab */}
                                                <TabsContent value="sync" className="space-y-4 mt-4">
                                                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                                                                <Card className="etap-panel">
                                                                        <CardHeader className="etap-panel-header">
                                                                                <CardTitle className="etap-panel-title">
                                                                                        <Download className="h-5 w-5 etap-panel-title-icon" />
                                                                                        Export to ETAP
                                                                                </CardTitle>
                                                                                <CardDescription className="etap-panel-description">
                                                                                        Transfer local load, source, and topology data to the selected ETAP project.
                                                                                </CardDescription>
                                                                        </CardHeader>
                                                                        <CardContent className="etap-panel-body space-y-4">
                                                                                <div className="flex items-center justify-between">
                                                                                        <Label className="etap-label" style={{ marginBottom: 0 }}>Include Loads</Label>
                                                                                        <Switch id="includeLoads" checked={includeLoads} onCheckedChange={setIncludeLoads} className="etap-toggle" />
                                                                                </div>
                                                                                <div className="flex items-center justify-between">
                                                                                        <Label className="etap-label" style={{ marginBottom: 0 }}>Include Sources</Label>
                                                                                        <Switch id="includeSources" checked={includeSources} onCheckedChange={setIncludeSources} className="etap-toggle" />
                                                                                </div>
                                                                                <div className="flex items-center justify-between">
                                                                                        <Label className="etap-label" style={{ marginBottom: 0 }}>Include Topology</Label>
                                                                                        <Switch id="includeTopology" checked={includeTopology} onCheckedChange={setIncludeTopology} className="etap-toggle" />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">Format</Label>
                                                                                        <Select value={exportFormat} onValueChange={(v) => setExportFormat(v as "csv" | "ort")}>
                                                                                                <SelectTrigger className="etap-input">
                                                                                                        <SelectValue />
                                                                                                </SelectTrigger>
                                                                                                <SelectContent>
                                                                                                        <SelectItem value="csv">CSV</SelectItem>
                                                                                                        <SelectItem value="ort">ORT (ETAP Native)</SelectItem>
                                                                                                </SelectContent>
                                                                                        </Select>
                                                                                </div>
                                                                                <Button onClick={handleExport} disabled={loading === "exporting"} className="etap-btn etap-btn-primary w-full">
                                                                                        {loading === "exporting" ? (
                                                                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                                                        ) : (
                                                                                                <Download className="h-4 w-4" />
                                                                                        )}
                                                                                        Execute Export
                                                                                </Button>
                                                                        </CardContent>
                                                                </Card>

                                                                <Card className="etap-panel">
                                                                        <CardHeader className="etap-panel-header">
                                                                                <CardTitle className="etap-panel-title">
                                                                                        <Import className="h-5 w-5 etap-panel-title-icon" />
                                                                                        Import from ETAP
                                                                                </CardTitle>
                                                                                <CardDescription className="etap-panel-description">
                                                                                        Pull remote project data into the local BAZSPARK project store.
                                                                                </CardDescription>
                                                                        </CardHeader>
                                                                        <CardContent className="etap-panel-body space-y-4">
                                                                                <div className="flex items-center justify-between">
                                                                                        <Label className="etap-label" style={{ marginBottom: 0 }}>Import Loads</Label>
                                                                                        <Switch id="importLoads" checked={importLoads} onCheckedChange={setImportLoads} className="etap-toggle" />
                                                                                </div>
                                                                                <div className="flex items-center justify-between">
                                                                                        <Label className="etap-label" style={{ marginBottom: 0 }}>Import Sources</Label>
                                                                                        <Switch id="importSources" checked={importSources} onCheckedChange={setImportSources} className="etap-toggle" />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">Conflict Resolution</Label>
                                                                                        <Select value={conflictResolution} onValueChange={(v) => setConflictResolution(v as any)}>
                                                                                                <SelectTrigger className="etap-input">
                                                                                                        <SelectValue />
                                                                                                </SelectTrigger>
                                                                                                <SelectContent>
                                                                                                        <SelectItem value="skip">Skip</SelectItem>
                                                                                                        <SelectItem value="overwrite">Overwrite</SelectItem>
                                                                                                        <SelectItem value="merge">Merge</SelectItem>
                                                                                                </SelectContent>
                                                                                        </Select>
                                                                                </div>
                                                                                <Button onClick={handleImport} disabled={loading === "importing" || !selectedEtapProject} className="etap-btn etap-btn-primary w-full">
                                                                                        {loading === "importing" ? (
                                                                                                <Loader2 className="h-4 w-4 animate-spin" />
                                                                                        ) : (
                                                                                                <Upload className="h-4 w-4" />
                                                                                        )}
                                                                                        Execute Import
                                                                                </Button>
                                                                        </CardContent>
                                                                </Card>
                                                        </div>
                                                </TabsContent>

                                                {/* Logs Tab */}
                                                <TabsContent value="logs" className="space-y-4 mt-4">
                                                        <Card className="etap-panel">
                                                                        <CardHeader className="etap-panel-header">
                                                                                <CardTitle className="etap-panel-title">
                                                                                        <Activity className="h-5 w-5 etap-panel-title-icon" />
                                                                                        Synchronization Log
                                                                                </CardTitle>
                                                                                <CardDescription className="etap-panel-description">
                                                                                        Operational history of import and export transactions.
                                                                                </CardDescription>
                                                                        </CardHeader>
                                                                        <CardContent>
                                                                                <div className="overflow-x-auto">
                                                                                        <table className="etap-table">
                                                                                                <thead>
                                                                                                        <tr>
                                                                                                                <th>Direction</th>
                                                                                                                <th>Status</th>
                                                                                                                <th>Records</th>
                                                                                                                <th>Error</th>
                                                                                                                <th>Timestamp</th>
                                                                                                        </tr>
                                                                                                </thead>
                                                                                                <tbody>
                                                                                                        {logs.length === 0 ? (
                                                                                                                <tr>
                                                                                                                        <td colSpan={5} className="text-center py-10 text-slate-500">
                                                                                                                                No sync logs available.
                                                                                                                        </td>
                                                                                                                </tr>
                                                                                                        ) : (
                                                                                                                logs.map((log) => (
                                                                                                                        <tr key={log.id}>
                                                                                                                                <td>
                                                                                                                                        <span className={`etap-badge ${log.direction === "export" ? "etap-badge-success" : "etap-badge-warning"}`}>
                                                                                                                                                {log.direction === "export" ? <Download className="h-3 w-3" /> : <Upload className="h-3 w-3" />}
                                                                                                                                                {log.direction}
                                                                                                                                        </span>
                                                                                                                                </td>
                                                                                                                                <td>
                                                                                                                                        <span className={
                                                                                                                                                log.status === "success" ? "etap-badge etap-badge-success" :
                                                                                                                                                log.status === "error" ? "etap-badge etap-badge-danger" :
                                                                                                                                                "etap-badge etap-badge-warning"
                                                                                                                                        }>
                                                                                                                                                {log.status}
                                                                                                                                        </span>
                                                                                                                                </td>
                                                                                                                                <td>{log.records_synced}</td>
                                                                                                                                <td>{log.error_message || "—"}</td>
                                                                                                                                <td>{new Date(log.created_at).toLocaleString()}</td>
                                                                                                                        </tr>
                                                                                                                ))
                                                                                                        )}
                                                                                                </tbody>
                                                                                        </table>
                                                                                </div>
                                                                        </CardContent>
                                                        </Card>
                                                </TabsContent>
                                        </Tabs>
                                </main>
                        </div>
                </div>
        );
}

function EyeIcon({ className }: { readonly className: string }) {
        return (
                <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
        );
}

function EyeOffIcon({ className }: { readonly className: string }) {
        return (
                <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.542-7a10.059 10.059 0 013.999-5.398M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l18 18" />
                </svg>
        );
}
