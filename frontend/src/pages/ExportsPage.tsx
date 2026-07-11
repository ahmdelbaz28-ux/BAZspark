/**
 * ExportsPage.tsx — Project data export page.
 *
 * V214: Exposes the backend export endpoints:
 *   GET  /api/v1/projects/{id}/export/dxf    — DXF (ezdxf)
 *   GET  /api/v1/projects/{id}/export/revit  — Revit JSON
 *   GET  /api/v1/projects/{id}/export/ifc    — IFC4 (ifcopenshell)
 *   POST /api/v1/exports                      — Excel (openpyxl, 4 sheets)
 */

import { Download, FileText, Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
        Card,
        CardContent,
        CardDescription,
        CardHeader,
        CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
        Select,
        SelectContent,
        SelectItem,
        SelectTrigger,
        SelectValue,
} from "@/components/ui/select";
import { useProjects } from "@/hooks/useApi";
import { getApiKey } from "@/services/apiKey";

export function ExportsPage() {
        const { data: projects } = useProjects();
        const [selectedProject, setSelectedProject] = useState<string>("");
        const [loading, setLoading] = useState(false);

        const projectId = selectedProject || (projects && projects.length > 0 ? projects[0].id : "");

        const downloadFile = async (endpoint: string, filename: string) => {
                if (!projectId) {
                        toast.error("No project selected. Create a project first.");
                        return;
                }
                setLoading(true);
                try {
                        const headers: Record<string, string> = {};
                        const apiKey = getApiKey();
                        if (apiKey) headers["X-API-Key"] = apiKey;

                        const resp = await fetch(endpoint, { headers });
                        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

                        const blob = await resp.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = filename;
                        a.click();
                        URL.revokeObjectURL(url);
                        toast.success(`Downloaded ${filename}`);
                } catch (err) {
                        toast.error(`Export failed: ${err instanceof Error ? err.message : "Unknown"}`);
                } finally {
                        setLoading(false);
                }
        };

        const handleExportDxf = () => {
                downloadFile(`/api/v1/projects/${projectId}/export/dxf`, `${projectId}_export.dxf`);
        };
        const handleExportRevit = () => {
                downloadFile(`/api/v1/projects/${projectId}/export/revit`, `${projectId}_revit.json`);
        };
        const handleExportIfc = () => {
                downloadFile(`/api/v1/projects/${projectId}/export/ifc`, `${projectId}_export.ifc`);
        };
        const handleExportExcel = async () => {
                if (!projectId) {
                        toast.error("No project selected.");
                        return;
                }
                setLoading(true);
                try {
                        const headers: Record<string, string> = { "Content-Type": "application/json" };
                        const apiKey = getApiKey();
                        if (apiKey) headers["X-API-Key"] = apiKey;
                        // V214 self-critique fix: POST with body, not GET
                        const resp = await fetch(`/api/v1/exports`, {
                                method: "POST",
                                headers,
                                body: JSON.stringify({ exportType: "excel" }),
                        });
                        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                        const blob = await resp.blob();
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `${projectId}_export.xlsx`;
                        a.click();
                        URL.revokeObjectURL(url);
                        toast.success("Downloaded Excel export");
                } catch (err) {
                        toast.error(`Export failed: ${err instanceof Error ? err.message : "Unknown"}`);
                } finally {
                        setLoading(false);
                }
        };

        return (
                <div className="flex-1 overflow-auto p-6 max-w-3xl mx-auto space-y-6">
                        <div>
                                <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                                        <Download className="h-6 w-6 text-primary" />
                                        Data Exports
                                </h1>
                                <p className="text-sm text-muted-foreground mt-1">
                                        Export project data in standard BIM/CAD formats
                                </p>
                        </div>

                        <Card className="border-border bg-card">
                                <CardHeader>
                                        <CardTitle>Select Project</CardTitle>
                                        <CardDescription>Choose which project to export</CardDescription>
                                </CardHeader>
                                <CardContent>
                                        <Label>Project</Label>
                                        <Select value={projectId} onValueChange={setSelectedProject}>
                                                <SelectTrigger>
                                                        <SelectValue placeholder="Select a project" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                        {projects?.map((p) => (
                                                                <SelectItem key={p.id} value={p.id}>
                                                                        {p.name}
                                                                </SelectItem>
                                                        )) || (
                                                                <SelectItem value="" disabled>No projects available</SelectItem>
                                                        )}
                                                </SelectContent>
                                        </Select>
                                </CardContent>
                        </Card>

                        <Card className="border-border bg-card">
                                <CardHeader>
                                        <CardTitle>Export Formats</CardTitle>
                                        <CardDescription>Each format produces a real file with project data</CardDescription>
                                </CardHeader>
                                <CardContent className="space-y-3">
                                        <Button
                                                onClick={handleExportDxf}
                                                disabled={loading || !projectId}
                                                variant="outline"
                                                className="w-full justify-start"
                                        >
                                                <FileText className="h-4 w-4 mr-2" />
                                                DXF (AutoCAD Drawing Exchange) — ezdxf
                                        </Button>
                                        <Button
                                                onClick={handleExportRevit}
                                                disabled={loading || !projectId}
                                                variant="outline"
                                                className="w-full justify-start"
                                        >
                                                <FileText className="h-4 w-4 mr-2" />
                                                Revit JSON — structured Revit API format
                                        </Button>
                                        <Button
                                                onClick={handleExportIfc}
                                                disabled={loading || !projectId}
                                                variant="outline"
                                                className="w-full justify-start"
                                        >
                                                <FileText className="h-4 w-4 mr-2" />
                                                IFC4 (Industry Foundation Classes) — ifcopenshell
                                        </Button>
                                        <Button
                                                onClick={handleExportExcel}
                                                disabled={loading || !projectId}
                                                variant="outline"
                                                className="w-full justify-start"
                                        >
                                                <FileText className="h-4 w-4 mr-2" />
                                                Excel (.xlsx) — 4 sheets: Project, Devices, Connections, BOQ
                                        </Button>
                                        {loading && (
                                                <div className="flex items-center justify-center py-4">
                                                        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                                                </div>
                                        )}
                                </CardContent>
                        </Card>
                </div>
        );
}
