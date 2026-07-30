/**
 * ARExportPage.tsx — Augmented Reality Export UI
 *
 * V2 API endpoints:
 *   POST /api/v2/ar/export — Export DigitalTwin to GLB/USDZ for AR visualization
 */

import {
        Camera,
        CheckCircle2,
        Download,
        FileBox,
        Globe,
        Loader2,
        Smartphone,
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

type ExportFormat = "glb" | "usdz" | "both";

export function ARExportPage() {
        const [buildingId, setBuildingId] = useState("Building_A");
        const [format, setFormat] = useState<ExportFormat>("both");
        const [exporting, setExporting] = useState(false);
        const [result, setResult] = useState<Record<string, unknown> | null>(null);

        const nodeCount = (result?.node_count as number) ?? 0;
        const behindWallCount = (result?.behind_wall_count as number) ?? 0;
        const behindWallText = behindWallCount > 0 ? ` (${behindWallCount} behind walls)` : "";

        const handleExport = async () => {
                setExporting(true);
                setResult(null);
                try {
                        const res = await v2Api.exportAr({
                                building_id: buildingId || "Building_A",
                                format,
                        });
                        setResult(res as Record<string, unknown>);
                } catch (err: unknown) {
                        console.error("AR export failed:", err);
                } finally {
                        setExporting(false);
                }
        };

        const handleDownload = (formatName: string, base64Content: string, sizeBytes: number) => {
                try {
                        const byteChars = atob(base64Content);
                        const byteArrays: Uint8Array[] = [];
                        for (let offset = 0; offset < byteChars.length; offset += 512) {
                                const slice = byteChars.slice(offset, offset + 512);
                                const byteNumbers = new Array(slice.length);
                                for (let i = 0; i < slice.length; i++) {
                                        byteNumbers[i] = slice.codePointAt(i)!;
                                }
                                byteArrays.push(new Uint8Array(byteNumbers));
                        }
                        const blob = new Blob(byteArrays as BlobPart[], {
                                type: formatName === "usdz" ? "model/usd" : "model/gltf-binary",
                        });
                        const ext = formatName === "usdz" ? "usdz" : "glb";
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `${buildingId || "building"}.${ext}`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                } catch {
                        console.error("Failed to decode and download AR export");
                }
        };

        const formatFileSize = (bytes: number): string => {
                if (bytes < 1024) return `${bytes} B`;
                if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
                return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
        };

        return (
                <div className="flex-1 overflow-auto">
                        <div className="p-6 max-w-4xl mx-auto space-y-6">
                                {/* Header */}
                                <div className="flex items-center gap-3">
                                        <Smartphone aria-hidden="true" className="h-8 w-8 text-info" />
                                        <div>
                                                <h1 className="text-2xl font-bold text-foreground">
                                                        AR Export
                                                </h1>
                                                <p className="text-sm text-muted-foreground">
                                                        Export DigitalTwin snapshots to GLB/USDZ for augmented reality
                                                        visualization
                                                </p>
                                        </div>
                                </div>

                                {/* Export Form */}
                                <Card className="border-border bg-card">
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                        <Camera aria-hidden="true" className="h-5 w-5 text-info" />
                                                        Export AR Snapshot
                                                </CardTitle>
                                                <CardDescription className="text-muted-foreground">
                                                        Configure and export your building model for AR viewing on mobile devices
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                        <div className="space-y-2">
                                                                <Label className="text-foreground/90">Building ID</Label>
                                                                <Input
                                                                        type="text"
                                                                        placeholder="Building_A"
                                                                        value={buildingId}
                                                                        onChange={(e) => setBuildingId(e.target.value)}
                                                                        className="bg-card border-border text-foreground"
                                                                />
                                                        </div>
                                                        <div className="space-y-2">
                                                                <Label className="text-foreground/90">Export Format</Label>
                                                                <select
                                                                        value={format}
                                                                        onChange={(e) => setFormat(e.target.value as ExportFormat)}
                                                                        className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                                                                >
                                                                        <option value="glb">GLB (glTF Binary)</option>
                                                                        <option value="usdz">USDZ (Apple AR Quick Look)</option>
                                                                        <option value="both">Both GLB + USDZ</option>
                                                                </select>
                                                                <p className="text-xs text-muted-foreground">
                                                                        {(() => {
                                                                                if (format === "glb") return "Compatible with WebXR, Three.js, and most AR platforms";
                                                                                if (format === "usdz") return "Native AR Quick Look on iOS/iPadOS devices";
                                                                                return "Both formats for maximum compatibility";
                                                                        })()}
                                                                </p>
                                                        </div>
                                                </div>

                                                <div className="pt-4">
                                                        <Button
                                                                className="bg-primary hover:bg-primary/90 text-primary-foreground border-none"
                                                                onClick={handleExport}
                                                                disabled={exporting}
                                                        >
                                                                {exporting ? (
                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 mr-1 animate-spin" />
                                                                ) : (
                                                                        <Globe aria-hidden="true" className="h-4 w-4 mr-1" />
                                                                )}
                                                                {exporting ? "Exporting…" : "Export AR Snapshot"}
                                                        </Button>
                                                </div>
                                        </CardContent>
                                </Card>

                                {/* Results */}
                                {result && (
                                        <Card className="border-border bg-card">
                                                <CardHeader className="pb-3">
                                                        <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                <CheckCircle2
                                                                        aria-hidden="true"
                                                                        className="h-5 w-5 text-success"
                                                                />
                                                                Export Complete
                                                        </CardTitle>
                                                        <CardDescription className="text-muted-foreground">
                                                                {nodeCount} node(s) exported{behindWallText}
                                                        </CardDescription>
                                                </CardHeader>
                                                <CardContent>
                                                        <div className="space-y-4">
                                                                {/* Format cards */}
                                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                                                        {!!result.formats &&
                                                                                Object.entries(
                                                                                        result.formats as Record<
                                                                                                string,
                                                                                                { size_bytes: number; content_base64: string }
                                                                                        >,
                                                                                ).map(([fmtName, fmtData]) => (
                                                                                        <div
                                                                                                key={fmtName}
                                                                                                className="p-4 rounded-lg bg-card border border-border"
                                                                                        >
                                                                                                <div className="flex items-center gap-2 mb-3">
                                                                                                        <FileBox
                                                                                                                aria-hidden="true"
                                                                                                                className="h-5 w-5 text-cyan-400"
                                                                                                        />
                                                                                                        <span className="font-medium text-foreground uppercase">
                                                                                                                {fmtName}
                                                                                                        </span>
                                                                                                </div>
                                                                                                <div className="flex items-center justify-between">
                                                                                                        <span className="text-sm text-muted-foreground">
                                                                                                                {formatFileSize(fmtData.size_bytes)}
                                                                                                        </span>
                                                                                                        <Button
                                                                                                                variant="outline"
                                                                                                                size="sm"
                                                                                                                className="border-border text-foreground/90 hover:bg-card"
                                                                                                                onClick={() =>
                                                                                                                        handleDownload(
                                                                                                                                fmtName,
                                                                                                                                fmtData.content_base64,
                                                                                                                                fmtData.size_bytes,
                                                                                                                        )
                                                                                                                }
                                                                                                        >
                                                                                                                <Download
                                                                                                                        aria-hidden="true"
                                                                                                                        className="h-4 w-4 mr-1"
                                                                                                                />
                                                                                                                Download
                                                                                                        </Button>
                                                                                                </div>
                                                                                        </div>
                                                                                ))}
                                                                </div>

                                                                {/* Raw result */}
                                                                <Separator className="bg-border" />
                                                                <details className="group">
                                                                        <summary className="text-sm font-medium text-muted-foreground cursor-pointer hover:text-foreground transition-colors duration-200">
                                                                                View raw response
                                                                        </summary>
                                                                        <pre className="mt-2 text-xs text-muted-foreground overflow-auto max-h-48 font-mono bg-card p-3 rounded-lg border border-border">
                                                                                {JSON.stringify(result, null, 2)}
                                                                        </pre>
                                                                </details>
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Empty state */}
                                {!exporting && !result && (
                                        <Card className="border-border bg-card">
                                                <CardContent>
                                                        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                                                                <Smartphone
                                                                        aria-hidden="true"
                                                                        className="h-16 w-16 mb-4 opacity-20"
                                                                />
                                                                <p className="text-lg font-medium text-foreground mb-1">
                                                                        No export yet
                                                                </p>
                                                                <p className="text-sm text-center max-w-md">
                                                                        Configure your building ID and format above, then click
                                                                        "Export AR Snapshot" to generate a GLB or USDZ file for
                                                                        augmented reality visualization on mobile devices.
                                                                </p>
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}
                        </div>
                </div>
        );
}
