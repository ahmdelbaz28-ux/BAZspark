/**
 * BIMProvidersPage.tsx — BIM Provider abstraction UI
 *
 * V2 API endpoints:
 *   GET  /api/v2/bim/providers   — List registered BIM providers
 *   GET  /api/v2/bim/health      — Active provider health check
 *   POST /api/v2/bim/extract-rooms — Extract rooms from BIM model
 */

import {
        Building2,
        CheckCircle2,
        Download,
        HeartPulse,
        List,
        Loader2,
        RefreshCw,
        XCircle,
} from "lucide-react";
import { useState } from "react";
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
import { v2Api } from "@/services/fullApi";

export function BIMProvidersPage() {
        const [providers, setProviders] = useState<string[] | null>(null);
        const [activeProvider, setActiveProvider] = useState<string | null>(null);
        const [healthData, setHealthData] = useState<Record<string, unknown> | null>(null);
        const [rooms, setRooms] = useState<Record<string, unknown>[] | null>(null);
        const [loading, setLoading] = useState(false);
        const [healthLoading, setHealthLoading] = useState(false);
        const [extractLoading, setExtractLoading] = useState(false);
        const [extractSource, setExtractSource] = useState("");

        const handleListProviders = async () => {
                setLoading(true);
                try {
                        const res = await v2Api.getBimProviders();
                        const data = res as Record<string, unknown>;
                        setProviders((data.providers as string[]) || []);
                        setActiveProvider((data.active as string) || null);
                } catch (err: unknown) {
                        console.error("Failed to list BIM providers:", err);
                } finally {
                        setLoading(false);
                }
        };

        const handleHealthCheck = async () => {
                setHealthLoading(true);
                try {
                        const res = await v2Api.getBimHealth();
                        setHealthData(res as Record<string, unknown>);
                } catch (err: unknown) {
                        console.error("BIM health check failed:", err);
                        setHealthData({ healthy: false, error: "Health check failed" });
                } finally {
                        setHealthLoading(false);
                }
        };

        const handleExtractRooms = async () => {
                setExtractLoading(true);
                try {
                        const res = await v2Api.extractBimRooms({
                                source: extractSource || undefined,
                        });
                        const data = res as Record<string, unknown>;
                        setRooms((data.rooms as Record<string, unknown>[]) || []);
                } catch (err: unknown) {
                        console.error("Room extraction failed:", err);
                } finally {
                        setExtractLoading(false);
                }
        };

        return (
                <div className="flex-1 overflow-auto">
                        <div className="p-6 max-w-4xl mx-auto space-y-6">
                                {/* Header */}
                                <div className="flex items-center justify-between">
                                        <div>
                                                <h1 className="text-2xl font-bold text-foreground">
                                                        BIM Providers
                                                </h1>
                                                <p className="text-sm text-muted-foreground mt-1">
                                                        Manage Building Information Model providers and extract room data
                                                </p>
                                        </div>
                                        <Button
                                                variant="outline"
                                                className="border-border text-foreground/90 hover:bg-card"
                                                onClick={handleListProviders}
                                                disabled={loading}
                                        >
                                                {loading ? (
                                                        <Loader2 aria-hidden="true" className="h-4 w-4 mr-1 animate-spin" />
                                                ) : (
                                                        <RefreshCw aria-hidden="true" className="h-4 w-4 mr-1" />
                                                )}
                                                {loading ? "Loading…" : "Refresh Providers"}
                                        </Button>
                                </div>

                                {/* Provider List */}
                                <Card className="border-border bg-card">
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                        <Building2 aria-hidden="true" className="h-5 w-5 text-info" />
                                                        Registered Providers
                                                </CardTitle>
                                                <CardDescription className="text-muted-foreground">
                                                        {providers === null
                                                                ? 'Click "Refresh Providers" to load available BIM providers'
                                                                : `${providers.length} provider(s) registered`}
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                                {(() => {
                                                        if (providers === null) {
                                                                return (
                                                                        <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                                                                                <Building2 aria-hidden="true" className="h-12 w-12 mb-3 opacity-30" />
                                                                                <p className="text-sm">No providers loaded yet</p>
                                                                                <p className="text-xs mt-1">
                                                                                        Click the refresh button above to discover available BIM providers
                                                                                </p>
                                                                        </div>
                                                                );
                                                        }
                                                        if (providers.length === 0) {
                                                                return (
                                                                        <p className="text-sm text-muted-foreground">
                                                                                No BIM providers are currently registered. Set the FIREAI_BIM_PROVIDER
                                                                                environment variable and ensure at least one provider is configured.
                                                                        </p>
                                                                );
                                                        }
                                                        return (
                                                                <div className="space-y-3">
                                                                {providers.map((provider) => (
                                                                        <div
                                                                                key={provider}
                                                                                className="flex items-center justify-between px-4 py-3 rounded-lg bg-card border border-border"
                                                                        >
                                                                                <div className="flex items-center gap-3">
                                                                                        <Building2
                                                                                                aria-hidden="true"
                                                                                                className={`h-5 w-5 ${
                                                                                                        provider === activeProvider
                                                                                                                ? "text-success"
                                                                                                                : "text-muted-foreground"
                                                                                                }`}
                                                                                        />
                                                                                        <span className="font-mono text-sm text-foreground">
                                                                                                {provider}
                                                                                        </span>
                                                                                </div>
                                                                                {provider === activeProvider && (
                                                                                        <span className="flex items-center gap-1 text-xs text-success">
                                                                                                <CheckCircle2 aria-hidden="true" className="h-3.5 w-3.5" />
                                                                                                Active
                                                                                        </span>
                                                                                )}
                                                                        </div>
                                                                ))}
                                                        </div>
                                                        );
                                                })()}
                                        </CardContent>
                                </Card>

                                {/* Provider Health */}
                                <Card className="border-border bg-card">
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                        <HeartPulse aria-hidden="true" className="h-5 w-5 text-info" />
                                                        Provider Health
                                                </CardTitle>
                                                <CardDescription className="text-muted-foreground">
                                                        Check the status of the active BIM provider
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                                <div className="flex items-center gap-4 mb-4">
                                                        <Button
                                                                variant="outline"
                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                onClick={handleHealthCheck}
                                                                disabled={healthLoading}
                                                        >
                                                                {healthLoading ? (
                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 mr-1 animate-spin" />
                                                                ) : (
                                                                        <HeartPulse aria-hidden="true" className="h-4 w-4 mr-1" />
                                                                )}
                                                                Check Health
                                                        </Button>
                                                </div>
                                                {healthData && (
                                                        <div className="p-4 rounded-lg bg-card border border-border">
                                                                <div className="flex items-center gap-2 mb-2">
                                                                        {healthData.healthy ? (
                                                                                <>
                                                                                        <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-success" />
                                                                                        <span className="text-sm font-medium text-foreground">Healthy</span>
                                                                                </>
                                                                        ) : (
                                                                                <>
                                                                                        <XCircle aria-hidden="true" className="h-5 w-5 text-danger" />
                                                                                        <span className="text-sm font-medium text-foreground">Unhealthy</span>
                                                                                </>
                                                                        )}
                                                                </div>
                                                                <pre className="text-xs text-muted-foreground overflow-auto max-h-48 font-mono">
                                                                        {JSON.stringify(healthData, null, 2)}
                                                                </pre>
                                                        </div>
                                                )}
                                        </CardContent>
                                </Card>

                                <Separator className="bg-border" />

                                {/* Extract Rooms */}
                                <Card className="border-border bg-card">
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                        <Download aria-hidden="true" className="h-5 w-5 text-info" />
                                                        Extract Rooms
                                                </CardTitle>
                                                <CardDescription className="text-muted-foreground">
                                                        Extract room data from a BIM model via the active provider
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                                <div className="space-y-2">
                                                        <Label className="text-foreground/90">
                                                                Source File (optional)
                                                        </Label>
                                                        <Input
                                                                type="text"
                                                                placeholder="Path or URL to BIM model (IFC, DXF, DWG, RVT)"
                                                                value={extractSource}
                                                                onChange={(e) => setExtractSource(e.target.value)}
                                                                className="bg-card border-border text-foreground"
                                                        />
                                                        <p className="text-xs text-muted-foreground">
                                                                Leave empty to use the provider's default source. Supported formats:
                                                                .ifc, .dxf, .dwg, .rvt, .rfa, .json
                                                        </p>
                                                </div>
                                                <Button
                                                        variant="outline"
                                                        className="border-border text-foreground/90 hover:bg-card"
                                                        onClick={handleExtractRooms}
                                                        disabled={extractLoading}
                                                >
                                                        {extractLoading ? (
                                                                <Loader2 aria-hidden="true" className="h-4 w-4 mr-1 animate-spin" />
                                                        ) : (
                                                                <List aria-hidden="true" className="h-4 w-4 mr-1" />
                                                        )}
                                                        {extractLoading ? "Extracting…" : "Extract Rooms"}
                                                </Button>

                                                {rooms && (
                                                        <div className="space-y-2">
                                                                <p className="text-sm font-medium text-foreground">
                                                                        Extracted Rooms ({rooms.length})
                                                                </p>
                                                                {rooms.length === 0 ? (
                                                                        <p className="text-sm text-muted-foreground">
                                                                                No rooms extracted. Check the provider configuration.
                                                                        </p>
                                                                ) : (
                                                                        <div className="space-y-2 max-h-80 overflow-auto">
                                                                                {rooms.map((room, idx) => (
                                                                                        <div
                                                                                                key={(room.room_id as string) || `room-${idx}`}
                                                                                                className="p-3 rounded-lg bg-card border border-border text-sm"
                                                                                        >
                                                                                                <div className="flex items-center justify-between mb-1">
                                                                                                        <span className="font-medium text-foreground">
                                                                                                                {room.name as string || `Room ${idx + 1}`}
                                                                                                        </span>
                                                                                                        <span className="text-xs text-muted-foreground font-mono">
                                                                                                                {room.room_id as string}
                                                                                                        </span>
                                                                                                </div>
                                                                                                <div className="flex gap-4 text-xs text-muted-foreground">
                                                                                                        <span>Area: {(room.area_m2 as number)?.toFixed(1)} m²</span>
                                                                                                        <span>Height: {(room.ceiling_height_m as number)?.toFixed(2)} m</span>
                                                                                                </div>
                                                                                        </div>
                                                                                ))}
                                                                        </div>
                                                                )}
                                                        </div>
                                                )}
                                        </CardContent>
                                </Card>
                        </div>
                </div>
        );
}
