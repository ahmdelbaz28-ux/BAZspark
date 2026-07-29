
/**
 * CADSettingsPage.tsx — AutoCAD & Revit Connection Configuration
 *
 * Provides UI for:
 * - AutoCAD connection parameters (path, version, template)
 * - Revit connection parameters (path, version, template)
 * - Connection status monitoring
 * - File import/export preferences
 */

import {
        AlertCircle,
        Cable,
        CheckCircle2,
        ChevronDown,
        ChevronRight,
        FileText,
        FolderOpen,
        Loader2,
        Monitor,
        RefreshCw,
        Settings,
        Wrench,
        XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Separator } from "@/components/ui/separator";
import { cadGatewayApi, apsApi } from "@/services/fullApi";

// Module-level cache for cad_settings to avoid repeated synchronous localStorage I/O
let _cachedCadSettings: Record<string, unknown> | null = null;

interface CadSettingsShape {
        autocad?: {
                path?: string;
                version?: string;
                template?: string;
                units?: string;
        };
        revit?: {
                path?: string;
                version?: string;
                template?: string;
                units?: string;
        };
        cloud?: {
                speckleServer?: string;
                speckleStreamId?: string;
                apsClientId?: string;
                apsActivityId?: string;
        };
}

function getCadSettings(): Record<string, unknown> {
        if (_cachedCadSettings !== null) return _cachedCadSettings;
        try {
                const saved = localStorage.getItem("cad_settings");
                _cachedCadSettings = saved ? JSON.parse(saved) : {};
        } catch {
                _cachedCadSettings = {};
        }
        return _cachedCadSettings!;
}

function setCadSettings(settings: Record<string, unknown>): void {
        try {
                localStorage.setItem("cad_settings", JSON.stringify(settings));
        } catch {
                // Storage unavailable or quota exceeded
        }
        _cachedCadSettings = settings;
}

interface CADConnectionStatus {
        connected: boolean;
        version?: string;
        document?: string;
        lastChecked: string;
}

interface RevitConnectionStatus {
        connected: boolean;
        version?: string;
        document?: string;
        lastChecked: string;
}

export function CADSettingsPage() {
        const [activeTab, setActiveTab] = useState("autocad");

        // AutoCAD settings
        const [acadPath, setAcadPath] = useState("");
        const [acadVersion, setAcadVersion] = useState("2024");
        const [acadTemplate, setAcadTemplate] = useState("");
        const [acadUnits, setAcadUnits] = useState("Millimeters");
        const [acadStatus, setAcadStatus] = useState<CADConnectionStatus | null>(
                null,
        );
        const [checkingAcad, setCheckingAcad] = useState(false);

        // Revit settings
        const [revitPath, setRevitPath] = useState("");
        const [revitVersion, setRevitVersion] = useState("2024");
        const [revitTemplate, setRevitTemplate] = useState("");
        const [revitUnits, setRevitUnits] = useState("Millimeters");
        const [revitStatus, setRevitStatus] = useState<RevitConnectionStatus | null>(
                null,
        );
        const [checkingRevit, setCheckingRevit] = useState(false);

        // Speckle settings
        const [speckleServer, setSpeckleServer] = useState("https://speckle.xyz");
        const [speckleToken, setSpeckleToken] = useState("");
        const [speckleStreamId, setSpeckleStreamId] = useState("");

        // APS settings
        const [apsClientId, setApsClientId] = useState("");
        const [apsClientSecret, setApsClientSecret] = useState("");
        const [apsActivityId, setApsActivityId] = useState("BazSparkAutoCADBridge.DrawLayout");

        // Gateway settings
        const { t } = useTranslation();
        const [gwEngine, setGwEngine] = useState("auto");
        const [gwConnecting, setGwConnecting] = useState(false);
        const [gwDisconnecting, setGwDisconnecting] = useState(false);
        const [gwStatus, setGwStatus] = useState<Record<string, unknown> | null>(null);
        const [gwCheckingStatus, setGwCheckingStatus] = useState(false);
        // Draw operations state
        const [drawOpsOpen, setDrawOpsOpen] = useState(false);
        const [lineStart, setLineStart] = useState("0,0,0");
        const [lineEnd, setLineEnd] = useState("100,0,0");
        const [polyPoints, setPolyPoints] = useState("0,0,0 100,0,0 100,100,0");
        const [circleCenter, setCircleCenter] = useState("0,0,0");
        const [circleRadius, setCircleRadius] = useState("50");
        const [textPosition, setTextPosition] = useState("0,0,0");
        const [textContent, setTextContent] = useState("Hello CAD");
        const [drawLoading, setDrawLoading] = useState(false);
        // Read/Write state
        const [rwOpen, setRwOpen] = useState(false);
        const [readFilter, setReadFilter] = useState("{}");
        const [writeEntities, setWriteEntities] = useState("{}");
        const [rwLoading, setRwLoading] = useState(false);

        // Load saved settings on mount
        useEffect(() => {
                const raw = getCadSettings();
                const settings = raw as unknown as CadSettingsShape;
                if (Object.keys(settings).length > 0) {
                        if (settings.autocad) {
                                setAcadPath(settings.autocad.path || "");
                                setAcadVersion(settings.autocad.version || "2024");
                                setAcadTemplate(settings.autocad.template || "");
                                setAcadUnits(settings.autocad.units || "Millimeters");
                        }
                        if (settings.revit) {
                                setRevitPath(settings.revit.path || "");
                                setRevitVersion(settings.revit.version || "2024");
                                setRevitTemplate(settings.revit.template || "");
                                setRevitUnits(settings.revit.units || "Millimeters");
                        }
                        if (settings.cloud) {
                                setSpeckleServer(settings.cloud.speckleServer || "https://speckle.xyz");
                                // V284 SECURITY: speckleToken / apsClientSecret are NO LONGER
                                // loaded from localStorage — they were readable by any XSS
                                // payload. A backend credential vault is in development
                                // (POST /api/v1/integrations/credentials, encrypted at rest).
                                // Until then, the token fields stay empty on page load and
                                // are never persisted to localStorage by saveCloudSettings().
                                setSpeckleStreamId(settings.cloud.speckleStreamId || "");
                                setApsClientId(settings.cloud.apsClientId || "");
                                setApsActivityId(settings.cloud.apsActivityId || "BazSparkAutoCADBridge.DrawLayout");
                        }
                }
        }, []);

        const checkAutoCADConnection = async () => {
                setCheckingAcad(true);
                try {
                        // V194 (TD-2) FIX: Wire to real backend status endpoint.
                        // Was previously a 1-second setTimeout that always reported success.
                        // Now calls GET /api/v1/autocad/status which returns the real
                        // AutoCAD connection state (connected, version, active document).
                        // Falls back to "disconnected" with the error message if the
                        // backend is unreachable.
                        const apiUrl = import.meta.env.VITE_API_URL || "/api/v1";
                        const resp = await fetch(`${apiUrl}/autocad/status`, {
                                credentials: "same-origin",
                        });
                        if (!resp.ok) {
                                throw new Error(`HTTP ${resp.status}`);
                        }
                        const body = await resp.json();
                        const data = body.data || body;
                        setAcadStatus({
                                connected: data.connected ?? false,
                                version: data.version || "Unknown",
                                document: data.document || data.active_document || "",
                                lastChecked: new Date().toISOString(),
                        });
                        if (data.connected) {
                                toast.success("AutoCAD connection verified");
                        } else {
                                toast.warning("AutoCAD is not connected");
                        }
                } catch (error) {
                        setAcadStatus({
                                connected: false,
                                lastChecked: new Date().toISOString(),
                        });
                        toast.error(
                                `AutoCAD connection check failed: ${error instanceof Error ? error.message : "Unknown error"}`,
                        );
                } finally {
                        setCheckingAcad(false);
                }
        };

        const checkRevitConnection = async () => {
                setCheckingRevit(true);
                try {
                        // V194 (TD-2) FIX: Wire to real backend status endpoint.
                        // Was previously a 1-second setTimeout that always reported success.
                        // Now calls GET /api/v1/revit/status which returns the real
                        // Revit connection state.
                        const apiUrl = import.meta.env.VITE_API_URL || "/api/v1";
                        const resp = await fetch(`${apiUrl}/revit/status`, {
                                credentials: "same-origin",
                        });
                        if (!resp.ok) {
                                throw new Error(`HTTP ${resp.status}`);
                        }
                        const body = await resp.json();
                        const data = body.data || body;
                        setRevitStatus({
                                connected: data.connected ?? false,
                                version: data.version || "Unknown",
                                document: data.document || data.active_document || "",
                                lastChecked: new Date().toISOString(),
                        });
                        if (data.connected) {
                                toast.success("Revit connection verified");
                        } else {
                                toast.warning("Revit is not connected");
                        }
                } catch (error) {
                        setRevitStatus({
                                connected: false,
                                lastChecked: new Date().toISOString(),
                        });
                        toast.error(
                                `Revit connection check failed: ${error instanceof Error ? error.message : "Unknown error"}`,
                        );
                } finally {
                        setCheckingRevit(false);
                }
        };

        const saveAutoCADSettings = () => {
                try {
                        const settings = getCadSettings();
                        settings.autocad = {
                                path: acadPath,
                                version: acadVersion,
                                template: acadTemplate,
                                units: acadUnits,
                        };
                        setCadSettings(settings);
                        toast.success("AutoCAD settings saved");
                } catch {
                        toast.error("Failed to save settings");
                }
        };

        const saveRevitSettings = () => {
                try {
                        const settings = getCadSettings();
                        settings.revit = {
                                path: revitPath,
                                version: revitVersion,
                                template: revitTemplate,
                                units: revitUnits,
                        };
                        setCadSettings(settings);
                        toast.success("Revit settings saved");
                } catch {
                        toast.error("Failed to save settings");
                }
        };

        const saveCloudSettings = () => {
                try {
                        const settings = getCadSettings();
                        // V284 SECURITY: speckleToken and apsClientSecret are NEVER written
                        // to localStorage. They are session-only state — the user must
                        // re-enter them each session until the backend credential vault
                        // (POST /api/v1/integrations/credentials, encrypted at rest) is
                        // implemented in a follow-up PR. This eliminates the XSS-readable
                        // credential exposure flagged in P0-8 of the critical audit.
                        settings.cloud = {
                                speckleServer,
                                speckleStreamId,
                                apsClientId,
                                apsActivityId,
                        };
                        setCadSettings(settings);
                        if (speckleToken || apsClientSecret) {
                                toast.info(
                                        "Non-secret cloud settings saved. Speckle/APS tokens are session-only — re-enter them each session until the backend credential vault ships (P0-8 follow-up).",
                                );
                        } else {
                                toast.success("Cloud settings saved");
                        }
                } catch {
                        toast.error("Failed to save settings");
                }
        };

        // ─── Gateway handlers ──────────────────────────────────────────────────────
        const parsePoint = (s: string): number[] =>
                s.split(",").map((v) => parseFloat(v.trim()) || 0);

        const parsePointsArray = (s: string): number[][] =>
                s.trim().split(/\s+/).map(parsePoint);

        const handleGatewayConnect = async () => {
                setGwConnecting(true);
                try {
                        const result = await cadGatewayApi.connect({ engine: gwEngine });
                        const data = (result as { data?: Record<string, unknown> })?.data || result;
                        toast.success(t("cadGateway.connected", "Connected to CAD gateway") as string);
                        setGwStatus(data as Record<string, unknown>);
                } catch (error) {
                        toast.error(
                                t("cadGateway.connectFailed", "CAD gateway connect failed") +
                                        `: ${error instanceof Error ? error.message : "Unknown error"}`,
                        );
                } finally {
                        setGwConnecting(false);
                }
        };

        const handleGatewayDisconnect = async () => {
                setGwDisconnecting(true);
                try {
                        await cadGatewayApi.disconnect();
                        setGwStatus(null);
                        toast.success(t("cadGateway.disconnected", "Disconnected from CAD gateway") as string);
                } catch (error) {
                        toast.error(
                                t("cadGateway.disconnectFailed", "CAD gateway disconnect failed") +
                                        `: ${error instanceof Error ? error.message : "Unknown error"}`,
                        );
                } finally {
                        setGwDisconnecting(false);
                }
        };

        const handleGatewayStatus = async () => {
                setGwCheckingStatus(true);
                try {
                        const result = await cadGatewayApi.getStatus();
                        const data = (result as { data?: Record<string, unknown> })?.data || result;
                        setGwStatus(data as Record<string, unknown>);
                } catch (error) {
                        toast.error(
                                t("cadGateway.statusFailed", "Failed to get gateway status") +
                                        `: ${error instanceof Error ? error.message : "Unknown error"}`,
                        );
                } finally {
                        setGwCheckingStatus(false);
                }
        };

        const handleDrawLine = async () => {
                setDrawLoading(true);
                try {
                        await cadGatewayApi.drawLine({
                                start: parsePoint(lineStart),
                                end: parsePoint(lineEnd),
                        });
                        toast.success(t("cadGateway.lineDrawn", "Line drawn successfully") as string);
                } catch (error) {
                        toast.error(
                                t("cadGateway.drawLineFailed", "Draw line failed") +
                                        `: ${error instanceof Error ? error.message : "Unknown error"}`,
                        );
                } finally {
                        setDrawLoading(false);
                }
        };

        const handleDrawPolyline = async () => {
                setDrawLoading(true);
                try {
                        await cadGatewayApi.drawPolyline({
                                points: parsePointsArray(polyPoints),
                        });
                        toast.success(t("cadGateway.polylineDrawn", "Polyline drawn successfully") as string);
                } catch (error) {
                        toast.error(
                                t("cadGateway.drawPolylineFailed", "Draw polyline failed") +
                                        `: ${error instanceof Error ? error.message : "Unknown error"}`,
                        );
                } finally {
                        setDrawLoading(false);
                }
        };

        const handleDrawCircle = async () => {
                setDrawLoading(true);
                try {
                        await cadGatewayApi.drawCircle({
                                center: parsePoint(circleCenter),
                                radius: parseFloat(circleRadius) || 50,
                        });
                        toast.success(t("cadGateway.circleDrawn", "Circle drawn successfully") as string);
                } catch (error) {
                        toast.error(
                                t("cadGateway.drawCircleFailed", "Draw circle failed") +
                                        `: ${error instanceof Error ? error.message : "Unknown error"}`,
                        );
                } finally {
                        setDrawLoading(false);
                }
        };

        const handleDrawText = async () => {
                setDrawLoading(true);
                try {
                        await cadGatewayApi.drawText({
                                position: parsePoint(textPosition),
                                text: textContent,
                        });
                        toast.success(t("cadGateway.textDrawn", "Text drawn successfully") as string);
                } catch (error) {
                        toast.error(
                                t("cadGateway.drawTextFailed", "Draw text failed") +
                                        `: ${error instanceof Error ? error.message : "Unknown error"}`,
                        );
                } finally {
                        setDrawLoading(false);
                }
        };

        const handleReadDrawing = async () => {
                setRwLoading(true);
                try {
                        const filter = JSON.parse(readFilter);
                        const result = await cadGatewayApi.read(filter);
                        const data = (result as { data?: unknown })?.data || result;
                        toast.success(t("cadGateway.readSuccess", "Drawing read successfully") as string);
                        setGwStatus((prev) => ({ ...prev, _lastRead: data } as Record<string, unknown>));
                } catch (error) {
                        if (error instanceof SyntaxError) {
                                toast.error(t("cadGateway.invalidJson", "Invalid JSON in filter") as string);
                        } else {
                                toast.error(
                                        t("cadGateway.readFailed", "Read drawing failed") +
                                                `: ${error instanceof Error ? error.message : "Unknown error"}`,
                                );
                        }
                } finally {
                        setRwLoading(false);
                }
        };

        const handleWriteEntities = async () => {
                setRwLoading(true);
                try {
                        const entities = JSON.parse(writeEntities);
                        await cadGatewayApi.write(entities);
                        toast.success(t("cadGateway.writeSuccess", "Entities written successfully") as string);
                } catch (error) {
                        if (error instanceof SyntaxError) {
                                toast.error(t("cadGateway.invalidJson", "Invalid JSON in entities") as string);
                        } else {
                                toast.error(
                                        t("cadGateway.writeFailed", "Write entities failed") +
                                                `: ${error instanceof Error ? error.message : "Unknown error"}`,
                                );
                        }
                } finally {
                        setRwLoading(false);
                }
        };

        return (
                <div className="flex-1 overflow-auto">
                        <div className="p-6 max-w-5xl mx-auto space-y-6">
                                {/* Header */}
                                <div>
                                        <h1 className="text-2xl font-bold text-foreground">
                                                CAD/BIM Connection Settings
                                        </h1>
                                        <p className="text-sm text-muted-foreground mt-1">
                                                Configure AutoCAD and Revit connections for file operations
                                        </p>
                                </div>

                                {/* Main Tabs */}
                                <Tabs value={activeTab} onValueChange={setActiveTab}>
                                        <TabsList className="bg-card border border-border">
                                                <TabsTrigger
                                                        value="autocad"
                                                        className="data-[state=active]:bg-secondary"
                                                >
                                                        <Monitor aria-hidden="true" className="h-4 w-4 mr-2" />
                                                        AutoCAD
                                                </TabsTrigger>
                                                <TabsTrigger
                                                        value="revit"
                                                        className="data-[state=active]:bg-secondary"
                                                >
                                                        <FileText aria-hidden="true" className="h-4 w-4 mr-2" />
                                                        Revit
                                                </TabsTrigger>
                                                <TabsTrigger
                                                        value="cloud"
                                                        className="data-[state=active]:bg-secondary"
                                                >
                                                        <Settings aria-hidden="true" className="h-4 w-4 mr-2" />
                                                        Cloud Integration
                                                </TabsTrigger>
                                                <TabsTrigger
                                                        value="gateway"
                                                        className="data-[state=active]:bg-secondary"
                                                >
                                                        <Cable aria-hidden="true" className="h-4 w-4 mr-2" />
                                                        Gateway
                                                </TabsTrigger>
                                                <TabsTrigger
                                                        value="aps"
                                                        className="data-[state=active]:bg-secondary"
                                                >
                                                        <Settings aria-hidden="true" className="h-4 w-4 mr-2" />
                                                        APS Cloud
                                                </TabsTrigger>
                                        </TabsList>

                                        {/* AutoCAD Tab */}
                                        <TabsContent value="autocad" className="space-y-6">
                                                {/* Connection Status */}
                                                <Card className="border-border bg-card">
                                                        <CardHeader>
                                                                <CardTitle className="text-lg text-foreground flex items-center justify-between">
                                                                        <span className="flex items-center gap-2">
                                                                                <Monitor aria-hidden="true" className="h-5 w-5 text-info" />
                                                                                AutoCAD Connection Status
                                                                        </span>
                                                                        <Button
                                                                                variant="outline"
                                                                                size="sm"
                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                onClick={checkAutoCADConnection}
                                                                                disabled={checkingAcad}
                                                                        >
                                                                                {checkingAcad ? (
                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                                                                                ) : (
                                                                                        <RefreshCw aria-hidden="true" className="h-4 w-4" />
                                                                                )}
                                                                        </Button>
                                                                </CardTitle>
                                                        </CardHeader>
                                                        <CardContent>
                                                                {acadStatus ? (
                                                                        <div className="flex items-center gap-4">
                                                                                {acadStatus.connected ? (
                                                                                        <CheckCircle2 aria-hidden="true" className="h-8 w-8 text-success" />
                                                                                ) : (
                                                                                        <XCircle aria-hidden="true" className="h-8 w-8 text-danger" />
                                                                                )}
                                                                                <div className="flex-1">
                                                                                        <p className="text-sm font-medium text-foreground">
                                                                                                {acadStatus.connected ? "Connected" : "Disconnected"}
                                                                                        </p>
                                                                                        {acadStatus.connected && (
                                                                                                <div className="text-xs text-muted-foreground mt-1 space-y-1">
                                                                                                        <p>Version: {acadStatus.version}</p>
                                                                                                        <p>Document: {acadStatus.document}</p>
                                                                                                        <p>
                                                                                                                Last checked:{" "}
                                                                                                                {new Date(acadStatus.lastChecked).toLocaleString()}
                                                                                                        </p>
                                                                                                </div>
                                                                                        )}
                                                                                </div>
                                                                                <Badge
                                                                                        variant={acadStatus.connected ? "default" : "destructive"}
                                                                                >
                                                                                        {acadStatus.connected ? "Active" : "Inactive"}
                                                                                </Badge>
                                                                        </div>
                                                                ) : (
                                                                        <div className="text-center py-6 text-muted-foreground">
                                                                                <AlertCircle aria-hidden="true" className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                                                                <p>Connection status unknown</p>
                                                                                <p className="text-xs mt-1">Click refresh to check</p>
                                                                        </div>
                                                                )}
                                                        </CardContent>
                                                </Card>

                                                {/* AutoCAD Configuration */}
                                                <Card className="border-border bg-card">
                                                        <CardHeader>
                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                        <Settings aria-hidden="true" className="h-5 w-5 text-info" />
                                                                        AutoCAD Configuration
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        Configure AutoCAD installation and default settings
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">Installation Path</Label>
                                                                        <div className="flex gap-2">
                                                                                <Input
                                                                                        value={acadPath}
                                                                                        onChange={(e) => setAcadPath(e.target.value)}
                                                                                        placeholder="C:\Program Files\Autodesk\AutoCAD 2024"
                                                                                        className="bg-card border-border text-foreground flex-1"
                                                                                />
                                                                                <Button
                                                                                        variant="outline"
                                                                                        className="border-border text-foreground/90 hover:bg-card"
                                                                                        onClick={() => {
                                                                                                        // V194 (TD-3) FIX: Use hidden file input to let the user select the
                                                                                                        // AutoCAD executable. Browsers cannot return full paths for
                                                                                                        // security reasons, so we use the file's name and prompt the
                                                                                                        // user to confirm the directory. This is the standard web pattern.
                                                                                                        const input = document.createElement("input");
                                                                                                        input.type = "file";
                                                                                                        input.accept = ".exe,application/x-msdownload";
                                                                                                        input.onchange = (e: Event) => {
                                                                                                                const file = (e.target as HTMLInputElement).files?.[0];
                                                                                                                if (file) {
                                                                                                                        setAcadPath(file.name);
                                                                                                                        toast.info(
                                                                                                                                `Selected: ${file.name}. Please verify the full installation path is correct above.`,
                                                                                                                        );
                                                                                                                }
                                                                                                        };
                                                                                                        input.click();
                                                                                                }}
                                                                                >
                                                                                        <FolderOpen aria-hidden="true" className="h-4 w-4" />
                                                                                </Button>
                                                                        </div>
                                                                        <p className="text-xs text-muted-foreground">
                                                                                Path to AutoCAD executable (acad.exe)
                                                                        </p>
                                                                </div>

                                                                <div className="grid grid-cols-2 gap-4">
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Version</Label>
                                                                                <Select value={acadVersion} onValueChange={setAcadVersion}>
                                                                                        <SelectTrigger className="bg-card border-border text-foreground">
                                                                                                <SelectValue />
                                                                                        </SelectTrigger>
                                                                                        <SelectContent>
                                                                                                <SelectItem value="2024">AutoCAD 2024</SelectItem>
                                                                                                <SelectItem value="2023">AutoCAD 2023</SelectItem>
                                                                                                <SelectItem value="2022">AutoCAD 2022</SelectItem>
                                                                                                <SelectItem value="2021">AutoCAD 2021</SelectItem>
                                                                                                <SelectItem value="2020">AutoCAD 2020</SelectItem>
                                                                                        </SelectContent>
                                                                                </Select>
                                                                        </div>

                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Default Units</Label>
                                                                                <Select value={acadUnits} onValueChange={setAcadUnits}>
                                                                                        <SelectTrigger className="bg-card border-border text-foreground">
                                                                                                <SelectValue />
                                                                                        </SelectTrigger>
                                                                                        <SelectContent>
                                                                                                <SelectItem value="Millimeters">Millimeters</SelectItem>
                                                                                                <SelectItem value="Meters">Meters</SelectItem>
                                                                                                <SelectItem value="Inches">Inches</SelectItem>
                                                                                                <SelectItem value="Feet">Feet</SelectItem>
                                                                                        </SelectContent>
                                                                                </Select>
                                                                        </div>
                                                                </div>

                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">Default Template</Label>
                                                                        <div className="flex gap-2">
                                                                                <Input
                                                                                        value={acadTemplate}
                                                                                        onChange={(e) => setAcadTemplate(e.target.value)}
                                                                                        placeholder="C:\Templates\architectural.dwt"
                                                                                        className="bg-card border-border text-foreground flex-1"
                                                                                />
                                                                                <Button
                                                                                        variant="outline"
                                                                                        className="border-border text-foreground/90 hover:bg-card"
                                                                                        onClick={() => {
                                                                                                // V247 FIX: Use hidden file input (was "not implemented")
                                                                                                const input = document.createElement("input");
                                                                                                input.type = "file";
                                                                                                input.accept = ".dwt";
                                                                                                input.onchange = (e: Event) => {
                                                                                                        const file = (e.target as HTMLInputElement).files?.[0];
                                                                                                        if (file) {
                                                                                                                setAcadTemplate(file.name);
                                                                                                                toast.info(`Selected: ${file.name}`);
                                                                                                        }
                                                                                                };
                                                                                                input.click();
                                                                                        }}
                                                                                >
                                                                                        <FolderOpen aria-hidden="true" className="h-4 w-4" />
                                                                                </Button>
                                                                        </div>
                                                                        <p className="text-xs text-muted-foreground">
                                                                                Default .dwt template file for new drawings
                                                                        </p>
                                                                </div>

                                                                <Button
                                                                        className="w-full bg-danger hover:bg-danger/90 text-white border-none"
                                                                        onClick={saveAutoCADSettings}
                                                                >
                                                                        Save AutoCAD Settings
                                                                </Button>
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>

                                        {/* Revit Tab */}
                                        <TabsContent value="revit" className="space-y-6">
                                                {/* Connection Status */}
                                                <Card className="border-border bg-card">
                                                        <CardHeader>
                                                                <CardTitle className="text-lg text-foreground flex items-center justify-between">
                                                                        <span className="flex items-center gap-2">
                                                                                <FileText aria-hidden="true" className="h-5 w-5 text-info" />
                                                                                Revit Connection Status
                                                                        </span>
                                                                        <Button
                                                                                variant="outline"
                                                                                size="sm"
                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                onClick={checkRevitConnection}
                                                                                disabled={checkingRevit}
                                                                        >
                                                                                {checkingRevit ? (
                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                                                                                ) : (
                                                                                        <RefreshCw aria-hidden="true" className="h-4 w-4" />
                                                                                )}
                                                                        </Button>
                                                                </CardTitle>
                                                        </CardHeader>
                                                        <CardContent>
                                                                {revitStatus ? (
                                                                        <div className="flex items-center gap-4">
                                                                                {revitStatus.connected ? (
                                                                                        <CheckCircle2 aria-hidden="true" className="h-8 w-8 text-success" />
                                                                                ) : (
                                                                                        <XCircle aria-hidden="true" className="h-8 w-8 text-danger" />
                                                                                )}
                                                                                <div className="flex-1">
                                                                                        <p className="text-sm font-medium text-foreground">
                                                                                                {revitStatus.connected ? "Connected" : "Disconnected"}
                                                                                        </p>
                                                                                        {revitStatus.connected && (
                                                                                                <div className="text-xs text-muted-foreground mt-1 space-y-1">
                                                                                                        <p>Version: {revitStatus.version}</p>
                                                                                                        <p>Document: {revitStatus.document}</p>
                                                                                                        <p>
                                                                                                                Last checked:{" "}
                                                                                                                {new Date(revitStatus.lastChecked).toLocaleString()}
                                                                                                        </p>
                                                                                                </div>
                                                                                        )}
                                                                                </div>
                                                                                <Badge
                                                                                        variant={
                                                                                                revitStatus.connected ? "default" : "destructive"
                                                                                        }
                                                                                >
                                                                                        {revitStatus.connected ? "Active" : "Inactive"}
                                                                                </Badge>
                                                                        </div>
                                                                ) : (
                                                                        <div className="text-center py-6 text-muted-foreground">
                                                                                <AlertCircle aria-hidden="true" className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                                                                <p>Connection status unknown</p>
                                                                                <p className="text-xs mt-1">Click refresh to check</p>
                                                                        </div>
                                                                )}
                                                        </CardContent>
                                                </Card>

                                                {/* Revit Configuration */}
                                                <Card className="border-border bg-card">
                                                        <CardHeader>
                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                        <Wrench aria-hidden="true" className="h-5 w-5 text-info" />
                                                                        Revit Configuration
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        Configure Revit installation and default settings
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">Installation Path</Label>
                                                                        <div className="flex gap-2">
                                                                                <Input
                                                                                        value={revitPath}
                                                                                        onChange={(e) => setRevitPath(e.target.value)}
                                                                                        placeholder="C:\Program Files\Autodesk\Revit 2024"
                                                                                        className="bg-card border-border text-foreground flex-1"
                                                                                />
                                                                                <Button
                                                                                        variant="outline"
                                                                                        className="border-border text-foreground/90 hover:bg-card"
                                                                                        onClick={() => {
                                                                                                // V247 FIX: Use hidden file input (was "not implemented")
                                                                                                const input = document.createElement("input");
                                                                                                input.type = "file";
                                                                                                input.accept = ".exe,application/x-msdownload";
                                                                                                input.onchange = (e: Event) => {
                                                                                                        const file = (e.target as HTMLInputElement).files?.[0];
                                                                                                        if (file) {
                                                                                                                setRevitPath(file.name);
                                                                                                                toast.info(`Selected: ${file.name}. Please verify the full installation path.`);
                                                                                                        }
                                                                                                };
                                                                                                input.click();
                                                                                        }}
                                                                                >
                                                                                        <FolderOpen aria-hidden="true" className="h-4 w-4" />
                                                                                </Button>
                                                                        </div>
                                                                        <p className="text-xs text-muted-foreground">
                                                                                Path to Revit executable (Revit.exe)
                                                                        </p>
                                                                </div>

                                                                <div className="grid grid-cols-2 gap-4">
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Version</Label>
                                                                                <Select
                                                                                        value={revitVersion}
                                                                                        onValueChange={setRevitVersion}
                                                                                >
                                                                                        <SelectTrigger className="bg-card border-border text-foreground">
                                                                                                <SelectValue />
                                                                                        </SelectTrigger>
                                                                                        <SelectContent>
                                                                                                <SelectItem value="2024">Revit 2024</SelectItem>
                                                                                                <SelectItem value="2023">Revit 2023</SelectItem>
                                                                                                <SelectItem value="2022">Revit 2022</SelectItem>
                                                                                                <SelectItem value="2021">Revit 2021</SelectItem>
                                                                                                <SelectItem value="2020">Revit 2020</SelectItem>
                                                                                        </SelectContent>
                                                                                </Select>
                                                                        </div>

                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Default Units</Label>
                                                                                <Select value={revitUnits} onValueChange={setRevitUnits}>
                                                                                        <SelectTrigger className="bg-card border-border text-foreground">
                                                                                                <SelectValue />
                                                                                        </SelectTrigger>
                                                                                        <SelectContent>
                                                                                                <SelectItem value="Millimeters">Millimeters</SelectItem>
                                                                                                <SelectItem value="Meters">Meters</SelectItem>
                                                                                                <SelectItem value="Inches">Inches</SelectItem>
                                                                                                <SelectItem value="Feet">Feet</SelectItem>
                                                                                        </SelectContent>
                                                                                </Select>
                                                                        </div>
                                                                </div>

                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">Default Template</Label>
                                                                        <div className="flex gap-2">
                                                                                <Input
                                                                                        value={revitTemplate}
                                                                                        onChange={(e) => setRevitTemplate(e.target.value)}
                                                                                        placeholder="C:\Templates\Architectural-Template.rte"
                                                                                        className="bg-card border-border text-foreground flex-1"
                                                                                />
                                                                                <Button
                                                                                        variant="outline"
                                                                                        className="border-border text-foreground/90 hover:bg-card"
                                                                                        onClick={() => {
                                                                                                // V247 FIX: Use hidden file input (was "not implemented")
                                                                                                const input = document.createElement("input");
                                                                                                input.type = "file";
                                                                                                input.accept = ".rte";
                                                                                                input.onchange = (e: Event) => {
                                                                                                        const file = (e.target as HTMLInputElement).files?.[0];
                                                                                                        if (file) {
                                                                                                                setRevitTemplate(file.name);
                                                                                                                toast.info(`Selected: ${file.name}`);
                                                                                                        }
                                                                                                };
                                                                                                input.click();
                                                                                        }}
                                                                                >
                                                                                        <FolderOpen aria-hidden="true" className="h-4 w-4" />
                                                                                </Button>
                                                                        </div>
                                                                        <p className="text-xs text-muted-foreground">
                                                                                Default .rte template file for new projects
                                                                        </p>
                                                                </div>

                                                                <Button
                                                                        className="w-full bg-danger hover:bg-danger/90 text-white border-none"
                                                                        onClick={saveRevitSettings}
                                                                >
                                                                        Save Revit Settings
                                                                </Button>
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>

                                        {/* Cloud Integration Tab */}
                                        <TabsContent value="cloud" className="space-y-6">
                                                {/* Speckle Configuration */}
                                                <Card className="border-border bg-card">
                                                        <CardHeader>
                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                        <Settings aria-hidden="true" className="h-5 w-5 text-info" />
                                                                        Speckle Live Synchronization
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        Configure Speckle live synchronization server and target stream
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">Speckle Server URL</Label>
                                                                        <Input
                                                                                value={speckleServer}
                                                                                onChange={(e) => setSpeckleServer(e.target.value)}
                                                                                placeholder="https://speckle.xyz"
                                                                                className="bg-card border-border text-foreground"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">Personal Access Token</Label>
                                                                        <Input
                                                                                type="password"
                                                                                value={speckleToken}
                                                                                onChange={(e) => setSpeckleToken(e.target.value)}
                                                                                placeholder="Paste your Speckle access token here (session-only — NOT saved)"
                                                                                className="bg-card border-border text-foreground"
                                                                        />
                                                                        <p className="text-xs text-amber-500">
                                                                                V284 SECURITY: Token is session-only and never written to
                                                                                localStorage. Re-enter each session. Backend credential
                                                                                vault (encrypted at rest) is in development (P0-8 follow-up).
                                                                        </p>
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">Default Stream/Project ID</Label>
                                                                        <Input
                                                                                value={speckleStreamId}
                                                                                onChange={(e) => setSpeckleStreamId(e.target.value)}
                                                                                placeholder="e.g. 7a92cfb38f"
                                                                                className="bg-card border-border text-foreground"
                                                                        />
                                                                </div>
                                                        </CardContent>
                                                </Card>

                                                {/* Autodesk Platform Services Configuration */}
                                                <Card className="border-border bg-card">
                                                        <CardHeader>
                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                        <Wrench aria-hidden="true" className="h-5 w-5 text-info" />
                                                                        Autodesk Platform Services (APS)
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        Configure headless cloud processing credentials and activities
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">APS Client ID</Label>
                                                                        <Input
                                                                                value={apsClientId}
                                                                                onChange={(e) => setApsClientId(e.target.value)}
                                                                                placeholder="Your APS Client ID"
                                                                                className="bg-card border-border text-foreground"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">APS Client Secret</Label>
                                                                        <Input
                                                                                type="password"
                                                                                value={apsClientSecret}
                                                                                onChange={(e) => setApsClientSecret(e.target.value)}
                                                                                placeholder="Your APS Client Secret (session-only — NOT saved)"
                                                                                className="bg-card border-border text-foreground"
                                                                        />
                                                                        <p className="text-xs text-amber-500">
                                                                                V284 SECURITY: Secret is session-only and never written to
                                                                                localStorage. Re-enter each session. Backend credential
                                                                                vault (encrypted at rest) is in development (P0-8 follow-up).
                                                                        </p>
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">APS Activity ID</Label>
                                                                        <Input
                                                                                value={apsActivityId}
                                                                                onChange={(e) => setApsActivityId(e.target.value)}
                                                                                placeholder="e.g. BazSparkAutoCADBridge.DrawLayout"
                                                                                className="bg-card border-border text-foreground"
                                                                        />
                                                                </div>

                                                                <Button
                                                                        className="w-full bg-danger hover:bg-danger/90 text-white border-none"
                                                                        onClick={saveCloudSettings}
                                                                >
                                                                        Save Cloud Settings
                                                                </Button>
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>

                                        {/* CAD Gateway Tab */}
                                        <TabsContent value="gateway" className="space-y-6">
                                                {/* Connection Control */}
                                                <Card className="border-border bg-card">
                                                        <CardHeader>
                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                        <Cable aria-hidden="true" className="h-5 w-5 text-info" />
                                                                        {t("cadGateway.title", "CAD Gateway")}
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        {t("cadGateway.description", "Unified gateway for AutoCAD and Revit connections")}
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="grid grid-cols-2 gap-4">
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        {t("cadGateway.engineType", "Engine Type")}
                                                                                </Label>
                                                                                <Select value={gwEngine} onValueChange={setGwEngine}>
                                                                                        <SelectTrigger className="bg-card border-border text-foreground">
                                                                                                <SelectValue />
                                                                                        </SelectTrigger>
                                                                                        <SelectContent>
                                                                                                <SelectItem value="auto">Auto</SelectItem>
                                                                                                <SelectItem value="autocad">AutoCAD</SelectItem>
                                                                                                <SelectItem value="revit">Revit</SelectItem>
                                                                                        </SelectContent>
                                                                                </Select>
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        {t("cadGateway.actions", "Actions")}
                                                                                </Label>
                                                                                <div className="flex gap-2">
                                                                                        <Button
                                                                                                variant="outline"
                                                                                                className="border-border text-foreground/90 hover:bg-card flex-1"
                                                                                                onClick={handleGatewayConnect}
                                                                                                disabled={gwConnecting || gwDisconnecting}
                                                                                        >
                                                                                                {gwConnecting ? (
                                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-1" />
                                                                                                ) : null}
                                                                                                {t("cadGateway.connect", "Connect")}
                                                                                        </Button>
                                                                                        <Button
                                                                                                variant="outline"
                                                                                                className="border-border text-foreground/90 hover:bg-card flex-1"
                                                                                                onClick={handleGatewayDisconnect}
                                                                                                disabled={gwConnecting || gwDisconnecting}
                                                                                        >
                                                                                                {gwDisconnecting ? (
                                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-1" />
                                                                                                ) : null}
                                                                                                {t("cadGateway.disconnect", "Disconnect")}
                                                                                        </Button>
                                                                                </div>
                                                                        </div>
                                                                </div>
                                                        </CardContent>
                                                </Card>

                                                {/* Gateway Status */}
                                                <Card className="border-border bg-card">
                                                        <CardHeader>
                                                                <CardTitle className="text-lg text-foreground flex items-center justify-between">
                                                                        <span className="flex items-center gap-2">
                                                                                <Monitor aria-hidden="true" className="h-5 w-5 text-info" />
                                                                                {t("cadGateway.statusTitle", "Gateway Status")}
                                                                        </span>
                                                                        <Button
                                                                                variant="outline"
                                                                                size="sm"
                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                onClick={handleGatewayStatus}
                                                                                disabled={gwCheckingStatus}
                                                                        >
                                                                                {gwCheckingStatus ? (
                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                                                                                ) : (
                                                                                        <RefreshCw aria-hidden="true" className="h-4 w-4" />
                                                                                )}
                                                                        </Button>
                                                                </CardTitle>
                                                        </CardHeader>
                                                        <CardContent>
                                                                {gwStatus ? (
                                                                        <div className="flex items-center gap-4">
                                                                                {gwStatus.connected ? (
                                                                                        <CheckCircle2 aria-hidden="true" className="h-8 w-8 text-success" />
                                                                                ) : (
                                                                                        <XCircle aria-hidden="true" className="h-8 w-8 text-danger" />
                                                                                )}
                                                                                <div className="flex-1">
                                                                                        <p className="text-sm font-medium text-foreground">
                                                                                                {gwStatus.connected
                                                                                                        ? t("cadGateway.connected", "Connected")
                                                                                                        : t("cadGateway.disconnected", "Disconnected")}
                                                                                        </p>
                                                                                        <div className="text-xs text-muted-foreground mt-1 space-y-1">
                                                                                                {gwStatus.engine != null && (
                                                                                                        <p>{t("cadGateway.engineLabel", "Engine")}: {String(gwStatus.engine)}</p>
                                                                                                )}
                                                                                                {gwStatus.connected_since != null && (
                                                                                                        <p>{t("cadGateway.connectedSince", "Connected since")}: {String(gwStatus.connected_since)}</p>
                                                                                                )}
                                                                                                {gwStatus.version != null && (
                                                                                                        <p>{t("cadGateway.version", "Version")}: {String(gwStatus.version)}</p>
                                                                                                )}
                                                                                        </div>
                                                                                </div>
                                                                                <Badge
                                                                                        variant={gwStatus.connected ? "default" : "destructive"}
                                                                                >
                                                                                        {gwStatus.connected
                                                                                                ? t("cadGateway.active", "Active")
                                                                                                : t("cadGateway.inactive", "Inactive")}
                                                                                </Badge>
                                                                        </div>
                                                                ) : (
                                                                        <div className="text-center py-6 text-muted-foreground">
                                                                                <AlertCircle aria-hidden="true" className="h-12 w-12 mx-auto mb-3 opacity-50" />
                                                                                <p>{t("cadGateway.statusUnknown", "Gateway status unknown")}</p>
                                                                                <p className="text-xs mt-1">{t("cadGateway.clickRefresh", "Click refresh to check")}</p>
                                                                        </div>
                                                                )}
                                                        </CardContent>
                                                </Card>

                                                {/* Draw Operations (collapsible) */}
                                                <Collapsible open={drawOpsOpen} onOpenChange={setDrawOpsOpen}>
                                                        <Card className="border-border bg-card">
                                                                <CardHeader>
                                                                        <CollapsibleTrigger asChild>
                                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2 cursor-pointer select-none">
                                                                                        <Wrench aria-hidden="true" className="h-5 w-5 text-info" />
                                                                                        {t("cadGateway.drawOperations", "Draw Operations")}
                                                                                        {drawOpsOpen ? (
                                                                                                <ChevronDown aria-hidden="true" className="h-4 w-4 ml-auto" />
                                                                                        ) : (
                                                                                                <ChevronRight aria-hidden="true" className="h-4 w-4 ml-auto" />
                                                                                        )}
                                                                                </CardTitle>
                                                                        </CollapsibleTrigger>
                                                                </CardHeader>
                                                                <CollapsibleContent>
                                                                        <CardContent className="space-y-4">
                                                                                {/* Draw Line */}
                                                                                <div className="space-y-2 border border-border rounded-md p-3">
                                                                                        <Label className="text-foreground/90 font-medium">
                                                                                                {t("cadGateway.drawLine", "Draw Line")}
                                                                                        </Label>
                                                                                        <div className="grid grid-cols-2 gap-4">
                                                                                                <div className="space-y-1">
                                                                                                        <Label className="text-xs text-muted-foreground">
                                                                                                                {t("cadGateway.start", "Start (x,y,z)")}
                                                                                                        </Label>
                                                                                                        <Input
                                                                                                                value={lineStart}
                                                                                                                onChange={(e) => setLineStart(e.target.value)}
                                                                                                                placeholder="0,0,0"
                                                                                                                className="bg-card border-border text-foreground"
                                                                                                        />
                                                                                                </div>
                                                                                                <div className="space-y-1">
                                                                                                        <Label className="text-xs text-muted-foreground">
                                                                                                                {t("cadGateway.end", "End (x,y,z)")}
                                                                                                        </Label>
                                                                                                        <Input
                                                                                                                value={lineEnd}
                                                                                                                onChange={(e) => setLineEnd(e.target.value)}
                                                                                                                placeholder="100,0,0"
                                                                                                                className="bg-card border-border text-foreground"
                                                                                                        />
                                                                                                </div>
                                                                                        </div>
                                                                                        <Button
                                                                                                variant="outline"
                                                                                                size="sm"
                                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                                onClick={handleDrawLine}
                                                                                                disabled={drawLoading}
                                                                                        >
                                                                                                {drawLoading ? (
                                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-1" />
                                                                                                ) : null}
                                                                                                {t("cadGateway.drawLineBtn", "Draw Line")}
                                                                                        </Button>
                                                                                </div>

                                                                                {/* Draw Polyline */}
                                                                                <div className="space-y-2 border border-border rounded-md p-3">
                                                                                        <Label className="text-foreground/90 font-medium">
                                                                                                {t("cadGateway.drawPolyline", "Draw Polyline")}
                                                                                        </Label>
                                                                                        <div className="space-y-1">
                                                                                                <Label className="text-xs text-muted-foreground">
                                                                                                        {t("cadGateway.points", "Points (space-separated x,y,z)")}
                                                                                                </Label>
                                                                                                <Input
                                                                                                        value={polyPoints}
                                                                                                        onChange={(e) => setPolyPoints(e.target.value)}
                                                                                                        placeholder="0,0,0 100,0,0 100,100,0"
                                                                                                        className="bg-card border-border text-foreground"
                                                                                                />
                                                                                        </div>
                                                                                        <Button
                                                                                                variant="outline"
                                                                                                size="sm"
                                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                                onClick={handleDrawPolyline}
                                                                                                disabled={drawLoading}
                                                                                        >
                                                                                                {drawLoading ? (
                                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-1" />
                                                                                                ) : null}
                                                                                                {t("cadGateway.drawPolylineBtn", "Draw Polyline")}
                                                                                        </Button>
                                                                                </div>

                                                                                {/* Draw Circle */}
                                                                                <div className="space-y-2 border border-border rounded-md p-3">
                                                                                        <Label className="text-foreground/90 font-medium">
                                                                                                {t("cadGateway.drawCircle", "Draw Circle")}
                                                                                        </Label>
                                                                                        <div className="grid grid-cols-2 gap-4">
                                                                                                <div className="space-y-1">
                                                                                                        <Label className="text-xs text-muted-foreground">
                                                                                                                {t("cadGateway.center", "Center (x,y,z)")}
                                                                                                        </Label>
                                                                                                        <Input
                                                                                                                value={circleCenter}
                                                                                                                onChange={(e) => setCircleCenter(e.target.value)}
                                                                                                                placeholder="0,0,0"
                                                                                                                className="bg-card border-border text-foreground"
                                                                                                        />
                                                                                                </div>
                                                                                                <div className="space-y-1">
                                                                                                        <Label className="text-xs text-muted-foreground">
                                                                                                                {t("cadGateway.radius", "Radius")}
                                                                                                        </Label>
                                                                                                        <Input
                                                                                                                value={circleRadius}
                                                                                                                onChange={(e) => setCircleRadius(e.target.value)}
                                                                                                                placeholder="50"
                                                                                                                className="bg-card border-border text-foreground"
                                                                                                        />
                                                                                                </div>
                                                                                        </div>
                                                                                        <Button
                                                                                                variant="outline"
                                                                                                size="sm"
                                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                                onClick={handleDrawCircle}
                                                                                                disabled={drawLoading}
                                                                                        >
                                                                                                {drawLoading ? (
                                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-1" />
                                                                                                ) : null}
                                                                                                {t("cadGateway.drawCircleBtn", "Draw Circle")}
                                                                                        </Button>
                                                                                </div>

                                                                                {/* Draw Text */}
                                                                                <div className="space-y-2 border border-border rounded-md p-3">
                                                                                        <Label className="text-foreground/90 font-medium">
                                                                                                {t("cadGateway.drawText", "Draw Text")}
                                                                                        </Label>
                                                                                        <div className="grid grid-cols-2 gap-4">
                                                                                                <div className="space-y-1">
                                                                                                        <Label className="text-xs text-muted-foreground">
                                                                                                                {t("cadGateway.position", "Position (x,y,z)")}
                                                                                                        </Label>
                                                                                                        <Input
                                                                                                                value={textPosition}
                                                                                                                onChange={(e) => setTextPosition(e.target.value)}
                                                                                                                placeholder="0,0,0"
                                                                                                                className="bg-card border-border text-foreground"
                                                                                                        />
                                                                                                </div>
                                                                                                <div className="space-y-1">
                                                                                                        <Label className="text-xs text-muted-foreground">
                                                                                                                {t("cadGateway.text", "Text")}
                                                                                                        </Label>
                                                                                                        <Input
                                                                                                                value={textContent}
                                                                                                                onChange={(e) => setTextContent(e.target.value)}
                                                                                                                placeholder="Hello CAD"
                                                                                                                className="bg-card border-border text-foreground"
                                                                                                        />
                                                                                                </div>
                                                                                        </div>
                                                                                        <Button
                                                                                                variant="outline"
                                                                                                size="sm"
                                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                                onClick={handleDrawText}
                                                                                                disabled={drawLoading}
                                                                                        >
                                                                                                {drawLoading ? (
                                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-1" />
                                                                                                ) : null}
                                                                                                {t("cadGateway.drawTextBtn", "Draw Text")}
                                                                                        </Button>
                                                                                </div>
                                                                        </CardContent>
                                                                </CollapsibleContent>
                                                        </Card>
                                                </Collapsible>

                                                {/* Read / Write (collapsible) */}
                                                <Collapsible open={rwOpen} onOpenChange={setRwOpen}>
                                                        <Card className="border-border bg-card">
                                                                <CardHeader>
                                                                        <CollapsibleTrigger asChild>
                                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2 cursor-pointer select-none">
                                                                                        <FileText aria-hidden="true" className="h-5 w-5 text-info" />
                                                                                        {t("cadGateway.readWrite", "Read / Write")}
                                                                                        {rwOpen ? (
                                                                                                <ChevronDown aria-hidden="true" className="h-4 w-4 ml-auto" />
                                                                                        ) : (
                                                                                                <ChevronRight aria-hidden="true" className="h-4 w-4 ml-auto" />
                                                                                        )}
                                                                                </CardTitle>
                                                                        </CollapsibleTrigger>
                                                                </CardHeader>
                                                                <CollapsibleContent>
                                                                        <CardContent className="space-y-4">
                                                                                {/* Read Drawing */}
                                                                                <div className="space-y-2 border border-border rounded-md p-3">
                                                                                        <Label className="text-foreground/90 font-medium">
                                                                                                {t("cadGateway.readDrawing", "Read Drawing")}
                                                                                        </Label>
                                                                                        <Label className="text-xs text-muted-foreground">
                                                                                                {t("cadGateway.filterParams", "Filter parameters (JSON)")}
                                                                                        </Label>
                                                                                        <Textarea
                                                                                                value={readFilter}
                                                                                                onChange={(e) => setReadFilter(e.target.value)}
                                                                                                placeholder='{"layer": "0"}'
                                                                                                className="bg-card border-border text-foreground font-mono text-sm"
                                                                                                rows={3}
                                                                                        />
                                                                                        <Button
                                                                                                variant="outline"
                                                                                                size="sm"
                                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                                onClick={handleReadDrawing}
                                                                                                disabled={rwLoading}
                                                                                        >
                                                                                                {rwLoading ? (
                                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-1" />
                                                                                                ) : null}
                                                                                                {t("cadGateway.readBtn", "Read Drawing")}
                                                                                        </Button>
                                                                                </div>

                                                                                {/* Write Entities */}
                                                                                <div className="space-y-2 border border-border rounded-md p-3">
                                                                                        <Label className="text-foreground/90 font-medium">
                                                                                                {t("cadGateway.writeEntities", "Write Entities")}
                                                                                        </Label>
                                                                                        <Label className="text-xs text-muted-foreground">
                                                                                                {t("cadGateway.entityData", "Entity data (JSON)")}
                                                                                        </Label>
                                                                                        <Textarea
                                                                                                value={writeEntities}
                                                                                                onChange={(e) => setWriteEntities(e.target.value)}
                                                                                                placeholder='{"entities": [{"type": "line", "start": [0,0,0], "end": [100,0,0]}]}'
                                                                                                className="bg-card border-border text-foreground font-mono text-sm"
                                                                                                rows={3}
                                                                                        />
                                                                                        <Button
                                                                                                variant="outline"
                                                                                                size="sm"
                                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                                onClick={handleWriteEntities}
                                                                                                disabled={rwLoading}
                                                                                        >
                                                                                                {rwLoading ? (
                                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-1" />
                                                                                                ) : null}
                                                                                                {t("cadGateway.writeBtn", "Write Entities")}
                                                                                        </Button>
                                                                                </div>
                                                                        </CardContent>
                                                                </CollapsibleContent>
                                                        </Card>
                                                </Collapsible>
                                        </TabsContent>

                                        {/* APS Cloud Processing Tab */}
                                        <TabsContent value="aps" className="space-y-6">
                                                <Card className="border-border bg-card">
                                                        <CardHeader>
                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                        <Settings aria-hidden="true" className="h-5 w-5" />
                                                                        Autodesk Platform Services (APS)
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        Submit and track APS cloud processing work items for BIM file conversion and analysis.
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">APS Client ID</Label>
                                                                                <Input
                                                                                        value={apsClientId}
                                                                                        onChange={(e) => setApsClientId(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                        placeholder="Your APS Client ID"
                                                                                />
                                                                                <p className="text-xs text-muted-foreground">Autodesk Platform Services client identifier</p>
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">APS Activity ID</Label>
                                                                                <Input
                                                                                        value={apsActivityId}
                                                                                        onChange={(e) => setApsActivityId(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                        placeholder="BazSparkAutoCADBridge.DrawLayout"
                                                                                />
                                                                                <p className="text-xs text-muted-foreground">Design automation activity to execute</p>
                                                                        </div>
                                                                </div>

                                                                <Separator />

                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90 font-medium">Process Work Item</Label>
                                                                        <p className="text-xs text-muted-foreground">
                                                                                Submit a work item to the APS cloud processing engine. The activity will process the specified file using the configured APS activity.
                                                                        </p>
                                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                                                                                <div className="space-y-2">
                                                                                        <Label className="text-xs text-muted-foreground">Input File URL</Label>
                                                                                        <Input
                                                                                                id="aps-input-url"
                                                                                                className="bg-card border-border text-foreground"
                                                                                                placeholder="https://storage.example.com/input.dwg"
                                                                                        />
                                                                                </div>
                                                                                <div className="space-y-2">
                                                                                        <Label className="text-xs text-muted-foreground">Output Filename</Label>
                                                                                        <Input
                                                                                                id="aps-output-filename"
                                                                                                className="bg-card border-border text-foreground"
                                                                                                placeholder="output.rvt"
                                                                                        />
                                                                                </div>
                                                                        </div>
                                                                        <Button
                                                                                variant="outline"
                                                                                size="sm"
                                                                                className="border-border text-foreground/90 hover:bg-card mt-2"
                                                                                onClick={async () => {
                                                                                        try {
                                                                                                const result = await apsApi.process({
                                                                                                        activityId: apsActivityId,
                                                                                                        inputUrl: (document.getElementById("aps-input-url") as HTMLInputElement)?.value || "",
                                                                                                        outputFilename: (document.getElementById("aps-output-filename") as HTMLInputElement)?.value || "output.rvt",
                                                                                                });
                                                                                                toast.success("APS work item submitted successfully");
                                                                                        } catch (err) {
                                                                                                toast.error(`APS process failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                                        }
                                                                                }}
                                                                        >
                                                                                <Settings aria-hidden="true" className="h-4 w-4 mr-1" />
                                                                                Submit Work Item
                                                                        </Button>
                                                                </div>

                                                                <Separator />

                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90 font-medium">Check Work Item Status</Label>
                                                                        <p className="text-xs text-muted-foreground">
                                                                                Check the status of a previously submitted APS work item by its ID.
                                                                        </p>
                                                                        <div className="flex gap-2 mt-2">
                                                                                <Input
                                                                                        id="aps-work-item-id"
                                                                                        className="bg-card border-border text-foreground flex-1"
                                                                                        placeholder="Work item ID"
                                                                                />
                                                                                <Button
                                                                                        variant="outline"
                                                                                        size="sm"
                                                                                        className="border-border text-foreground/90 hover:bg-card"
                                                                                        onClick={async () => {
                                                                                                try {
                                                                                                        const workItemId = (document.getElementById("aps-work-item-id") as HTMLInputElement)?.value;
                                                                                                        if (!workItemId) {
                                                                                                                toast.error("Please enter a work item ID");
                                                                                                                return;
                                                                                                        }
                                                                                                        const result = await apsApi.getStatus(workItemId);
                                                                                                        toast.info(`Work item status: ${JSON.stringify(result)}`);
                                                                                                } catch (err) {
                                                                                                        toast.error(`Status check failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                                                }
                                                                                        }}
                                                                                >
                                                                                        <RefreshCw aria-hidden="true" className="h-4 w-4 mr-1" />
                                                                                        Check Status
                                                                                </Button>
                                                                        </div>
                                                                </div>
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>
                                </Tabs>
                        </div>
                </div>
        );
}
