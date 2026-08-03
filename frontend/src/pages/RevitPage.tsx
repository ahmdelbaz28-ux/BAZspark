
/**
 * RevitPage.tsx — Revit Dashboard
 */

import {
        Activity,
        AlertTriangle,
        BookOpen,
        Building2,
        FileText,
        Globe,
        Loader2,
        Power,
        PowerOff,
        RefreshCw,
        Search,
        Terminal,
        Wifi,
        WifiOff,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { FileUploader } from "@/components/shared/FileUploader";
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
import { Switch } from "@/components/ui/switch";
import { revitApi, revitExtendedApi, revitIntegrationApi } from "@/services/fullApi";
import { checkCadStatus } from "@/lib/cadStatus";

export function RevitPage() {
        const [connected, setConnected] = useState(false);
        const [connecting, setConnecting] = useState(false);
        const [simulationMode, setSimulationMode] = useState(false);
        const [status, setStatus] = useState<Record<string, unknown> | null>(null);
        const [visible, setVisible] = useState(true);
        const [filepath, setFilepath] = useState("");
        const [apiSearchQuery, setApiSearchQuery] = useState("");
        const [apiSearchResult, setApiSearchResult] = useState<Record<string, unknown> | null>(null);
        const [nlCommand, setNlCommand] = useState("");
        const [nlResult, setNlResult] = useState<Record<string, unknown> | null>(null);

        // Revit Integration state
        const [integrationProjectId, setIntegrationProjectId] = useState("");
        const [integrationResult, setIntegrationResult] = useState<Record<string, unknown> | null>(null);
        const [integrationLoading, setIntegrationLoading] = useState(false);

        const checkStatus = useCallback(async () => {
                await checkCadStatus(() => revitApi.getStatus(), {
                        setStatus,
                        setConnected,
                        setSimulationMode,
                });
        }, []);

        useEffect(() => {
                // Mount fetch via the shared checkCadStatus helper — no synchronous
                // setState in the effect body (react-hooks/set-state-in-effect).
                let cancelled = false;
                checkCadStatus(
                        () => revitApi.getStatus(),
                        { setStatus, setConnected, setSimulationMode },
                        () => cancelled,
                );
                return () => {
                        cancelled = true;
                };
        }, []);

        const handleConnect = async () => {
                setConnecting(true);
                try {
                        const result = await revitApi.connect("auto");
                        // V214: Check simulation_mode from connect response
                        const sim = (result as Record<string, unknown>)?.simulation_mode;
                        if (sim) {
                                setSimulationMode(true);
                                toast.warning(
                                        "SIMULATION MODE: No real Revit instance is connected. " +
                                        "create_wall/floor/door will return None. read_rvt will " +
                                        "return empty results. Use method='api' on Windows with " +
                                        "Revit running for real operations, or export to IFC."
                                );
                        } else {
                                setSimulationMode(false);
                                toast.success("Connected to Revit");
                        }
                        setConnected(true);
                        checkStatus();
                } catch (err) {
                        toast.error(
                                `Connection failed: ${err instanceof Error ? err.message : "Unknown error"}`,
                        );
                } finally {
                        setConnecting(false);
                }
        };

        const handleDisconnect = async () => {
                try {
                        await revitApi.disconnect();
                        toast.success("Disconnected");
                        setConnected(false);
                        setSimulationMode(false);
                        setStatus(null);
                } catch (err) {
                        toast.error(
                                `Failed: ${err instanceof Error ? err.message : "Unknown error"}`,
                        );
                }
        };

        const handleReadRvt = async () => {
                if (!filepath.trim()) {
                        toast.error("Enter file path");
                        return;
                }
                try {
                        await revitApi.readRvt({ filepath });
                        toast.success(`Read ${filepath}`);
                } catch (err) {
                        toast.error(
                                `Read failed: ${err instanceof Error ? err.message : "Unknown error"}`,
                        );
                }
        };

        const handleUpload = async (file: File) => {
                await revitApi.uploadRvt(file);
                toast.success(`Uploaded ${file.name}`);
        };

        return (
                <div className="flex-1 overflow-auto p-6 max-w-6xl mx-auto space-y-6">
                        <div className="flex items-center justify-between">
                                <div>
                                        <h1 className="text-2xl font-bold text-foreground">Revit Dashboard</h1>
                                        <p className="text-sm text-muted-foreground mt-1">
                                                Connect, read, and manage RVT files
                                        </p>
                                </div>
                                <Badge
                                        variant={connected ? "default" : "outline"}
                                        className={
                                                connected ? "bg-emerald-600" : "border-border text-muted-foreground"
                                        }
                                >
                                        {connected ? (
                                                <>
                                                        <Wifi aria-hidden="true" className="h-3 w-3 mr-1" /> Connected
                                                </>
                                        ) : (
                                                <>
                                                        <WifiOff aria-hidden="true" className="h-3 w-3 mr-1" /> Disconnected
                                                </>
                                        )}
                                </Badge>
                        </div>

                        {/* V214: Simulation mode warning banner */}
                        {connected && simulationMode && (
                                <div
                                        className="flex items-start gap-3 p-4 rounded-lg border border-amber-500/50 bg-amber-500/10"
                                        role="alert"
                                        aria-live="polite"
                                >
                                        <AlertTriangle aria-hidden="true" className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
                                        <div className="space-y-1">
                                                <p className="text-sm font-semibold text-amber-600 dark:text-amber-400">
                                                        SIMULATION MODE — No real Revit instance is connected
                                                </p>
                                                <p className="text-xs text-amber-200">
                                                        create_wall/create_floor/create_door will return None.
                                                        read_rvt will return empty results (RVT is a closed
                                                        format requiring Revit API). write_rvt will write a
                                                        real IFC4 file instead (Revit can import via File →
                                                        Open → IFC). For real Revit integration, use
                                                        method='api' on Windows with Revit running.
                                                </p>
                                        </div>
                                </div>
                        )}

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <Card className="border-border bg-card">
                                        <CardHeader>
                                                <CardTitle className="flex items-center gap-2 text-foreground">
                                                        <Power aria-hidden="true" className="h-5 w-5 text-primary" /> Connection
                                                </CardTitle>
                                                <CardDescription className="text-muted-foreground">
                                                        Connect to Revit instance
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                                <div className="flex items-center gap-3">
                                                        <Switch
                                                                checked={visible}
                                                                onCheckedChange={setVisible}
                                                                id="revit-visible"
                                                        />
                                                        <Label htmlFor="revit-visible" className="text-foreground/90">
                                                                Visible window
                                                        </Label>
                                                </div>
                                                <div className="flex gap-2">
                                                        <Button
                                                                onClick={handleConnect}
                                                                disabled={connecting || connected}
                                                                data-testid="connect-revit-btn"
                                                                className="bg-emerald-600 hover:bg-emerald-700 text-white"
                                                        >
                                                                {connecting ? (
                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 mr-2 animate-spin" />
                                                                ) : (
                                                                        <Power aria-hidden="true" className="h-4 w-4 mr-2" />
                                                                )}
                                                                Connect
                                                        </Button>
                                                        <Button
                                                                onClick={handleDisconnect}
                                                                disabled={!connected}
                                                                variant="destructive"
                                                        >
                                                                <PowerOff aria-hidden="true" className="h-4 w-4 mr-2" /> Disconnect
                                                        </Button>
                                                </div>
                                        </CardContent>
                                </Card>

                                <Card className="border-border bg-card">
                                        <CardHeader>
                                                <CardTitle className="flex items-center gap-2 text-foreground">
                                                        <Activity aria-hidden="true" className="h-5 w-5 text-primary" /> Status
                                                </CardTitle>
                                                <CardDescription className="text-muted-foreground">
                                                        Current Revit status
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                                {status ? (
                                                        <pre className="text-xs text-muted-foreground bg-card p-3 rounded overflow-auto max-h-48">
                                                                {JSON.stringify(status, null, 2)}
                                                        </pre>
                                                ) : (
                                                        <p className="text-muted-foreground text-sm">Not connected</p>
                                                )}
                                        </CardContent>
                                </Card>
                        </div>

                        <Card className="border-border bg-card">
                                <CardHeader>
                                        <CardTitle className="flex items-center gap-2 text-foreground">
                                                <FileText aria-hidden="true" className="h-5 w-5 text-primary" /> Read RVT File
                                        </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                        <div className="flex gap-2">
                                                <Input
                                                        placeholder="/path/to/file.rvt"
                                                        value={filepath}
                                                        onChange={(e) => setFilepath(e.target.value)}
                                                        className="bg-card border-border text-foreground"
                                                />
                                                <Button
                                                        onClick={handleReadRvt}
                                                        disabled={!connected}
                                                        className="bg-primary hover:bg-cyan-400 text-slate-950 font-semibold"
                                                >
                                                        Read
                                                </Button>
                                        </div>
                                        <div className="pt-2">
                                                <FileUploader
                                                        accept=".rvt"
                                                        label="Or upload an RVT file"
                                                        onUpload={handleUpload}
                                                />
                                        </div>
                                </CardContent>
                                </Card>

                        {/* Revit API Search & NL Execute */}
                        <Card className="border-border bg-card">
                                <CardHeader>
                                        <CardTitle className="flex items-center gap-2 text-foreground">
                                                <BookOpen aria-hidden="true" className="h-5 w-5 text-primary" /> API Search & Natural Language
                                        </CardTitle>
                                        <CardDescription className="text-muted-foreground">
                                                Search Revit API docs and execute natural language commands
                                        </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                        <div className="flex flex-wrap gap-2">
                                                <Button
                                                        onClick={async () => {
                                                                try {
                                                                        await revitExtendedApi.loadApiSearchIndex();
                                                                        toast.success("API index loaded");
                                                                } catch (err) {
                                                                        toast.error(`Load failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                }
                                                        }}
                                                        variant="outline"
                                                >
                                                        <BookOpen aria-hidden="true" className="h-4 w-4" />
                                                        Load API Index
                                                </Button>
                                        </div>
                                        <div className="flex gap-2">
                                                <Input
                                                        placeholder="Search API docs..."
                                                        value={apiSearchQuery}
                                                        onChange={(e) => setApiSearchQuery(e.target.value)}
                                                        className="bg-card border-border text-foreground"
                                                />
                                                <Button
                                                        onClick={async () => {
                                                                if (!apiSearchQuery) return;
                                                                try {
                                                                        const res = await revitExtendedApi.searchApi({ query: apiSearchQuery });
                                                                        setApiSearchResult(res as Record<string, unknown>);
                                                                        toast.success("Search complete");
                                                                } catch (err) {
                                                                        toast.error(`Search failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                }
                                                        }}
                                                        disabled={!apiSearchQuery}
                                                >
                                                        <Search aria-hidden="true" className="h-4 w-4" />
                                                        Search API
                                                </Button>
                                                <Button
                                                        onClick={async () => {
                                                                if (!apiSearchQuery) return;
                                                                try {
                                                                        const res = await revitExtendedApi.searchOnline(apiSearchQuery);
                                                                        setApiSearchResult(res as Record<string, unknown>);
                                                                        toast.success("Online search complete");
                                                                } catch (err) {
                                                                        toast.error(`Online search failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                }
                                                        }}
                                                        disabled={!apiSearchQuery}
                                                        variant="outline"
                                                >
                                                        <Globe aria-hidden="true" className="h-4 w-4" />
                                                        Search Online
                                                </Button>
                                        </div>
                                        {apiSearchResult && (
                                                <pre className="text-xs text-muted-foreground bg-card p-3 rounded overflow-auto max-h-48">
                                                        {JSON.stringify(apiSearchResult, null, 2)}
                                                </pre>
                                        )}
                                        <div className="flex gap-2">
                                                <Input
                                                        placeholder="Natural language command..."
                                                        value={nlCommand}
                                                        onChange={(e) => setNlCommand(e.target.value)}
                                                        className="bg-card border-border text-foreground"
                                                />
                                                <Button
                                                        onClick={async () => {
                                                                if (!nlCommand) return;
                                                                try {
                                                                        const res = await revitExtendedApi.executeNlCommand({ command: nlCommand });
                                                                        setNlResult(res as Record<string, unknown>);
                                                                        toast.success("Command executed");
                                                                } catch (err) {
                                                                        toast.error(`Execute failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                }
                                                        }}
                                                        disabled={!nlCommand}
                                                >
                                                        <Terminal aria-hidden="true" className="h-4 w-4" />
                                                        Execute NL Command
                                                </Button>
                                        </div>
                                        {nlResult && (
                                                <pre className="text-xs text-muted-foreground bg-card p-3 rounded overflow-auto max-h-48">
                                                        {JSON.stringify(nlResult, null, 2)}
                                                </pre>
                                        )}
                                </CardContent>
                        </Card>

                        {/* Revit Integration (revit_api.py) */}
                        <Card className="border-border bg-card">
                                <CardHeader>
                                        <CardTitle className="flex items-center gap-2 text-foreground">
                                                <Building2 aria-hidden="true" className="h-5 w-5 text-primary" /> Revit Integration (Cloud Sync)
                                        </CardTitle>
                                        <CardDescription className="text-muted-foreground">
                                                Upload, sync, and export Revit models via APS cloud integration
                                        </CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                        <div className="flex gap-2">
                                                <Input
                                                        placeholder="Project ID"
                                                        value={integrationProjectId}
                                                        onChange={(e) => setIntegrationProjectId(e.target.value)}
                                                        className="bg-card border-border text-foreground"
                                                />
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                                <Button
                                                        onClick={async () => {
                                                                if (!integrationProjectId) { toast.error("Enter a project ID"); return; }
                                                                setIntegrationLoading(true);
                                                                try {
                                                                        const res = await revitIntegrationApi.getSyncStatus(integrationProjectId);
                                                                        setIntegrationResult(res as Record<string, unknown>);
                                                                        toast.success("Sync status retrieved");
                                                                } catch (err) {
                                                                        toast.error(`Failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                } finally { setIntegrationLoading(false); }
                                                        }}
                                                        disabled={integrationLoading || !integrationProjectId}
                                                        variant="outline"
                                                >
                                                        {integrationLoading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Activity aria-hidden="true" className="h-4 w-4" />}
                                                        Sync Status
                                                </Button>
                                                <Button
                                                        onClick={async () => {
                                                                if (!integrationProjectId) { toast.error("Enter a project ID"); return; }
                                                                setIntegrationLoading(true);
                                                                try {
                                                                        const res = await revitIntegrationApi.syncModel({ project_id: integrationProjectId });
                                                                        setIntegrationResult(res as Record<string, unknown>);
                                                                        toast.success("Sync initiated");
                                                                } catch (err) {
                                                                        toast.error(`Sync failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                } finally { setIntegrationLoading(false); }
                                                        }}
                                                        disabled={integrationLoading || !integrationProjectId}
                                                >
                                                        {integrationLoading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <RefreshCw aria-hidden="true" className="h-4 w-4" />}
                                                        Sync Model
                                                </Button>
                                                <Button
                                                        onClick={async () => {
                                                                if (!integrationProjectId) { toast.error("Enter a project ID"); return; }
                                                                setIntegrationLoading(true);
                                                                try {
                                                                        const res = await revitIntegrationApi.exportData({ project_id: integrationProjectId, format: "ifc" });
                                                                        setIntegrationResult(res as Record<string, unknown>);
                                                                        toast.success("Export initiated");
                                                                } catch (err) {
                                                                        toast.error(`Export failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                } finally { setIntegrationLoading(false); }
                                                        }}
                                                        disabled={integrationLoading || !integrationProjectId}
                                                        variant="outline"
                                                >
                                                        {integrationLoading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <FileText aria-hidden="true" className="h-4 w-4" />}
                                                        Export (IFC)
                                                </Button>
                                        </div>
                                        {integrationResult && (
                                                <pre className="text-xs text-muted-foreground bg-card p-3 rounded overflow-auto max-h-48">
                                                        {JSON.stringify(integrationResult, null, 2)}
                                                </pre>
                                        )}
                                </CardContent>
                        </Card>
                </div>
        );
}
