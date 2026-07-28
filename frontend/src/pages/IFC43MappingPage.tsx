/**
 * IFC43MappingPage.tsx — IFC 4.3 ADD2 Mapping UI
 *
 * V2 API endpoints:
 *   POST /api/v2/ifc43/map-detector — Map a detector to IFC 4.3
 *   POST /api/v2/ifc43/map-project  — Map an entire project to IFC 4.3
 */

import {
        Building2,
        CheckCircle2,
        Globe,
        Loader2,
        Map as MapIcon,
        Target,
} from "lucide-react";
import { useState } from "react";
import { Textarea } from "@/components/ui/textarea";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { v2Api } from "@/services/fullApi";

export function IFC43MappingPage() {
        // Detector mapping form
        const [deviceId, setDeviceId] = useState("");
        const [detectorType, setDetectorType] = useState("smoke");
        const [posX, setPosX] = useState("0");
        const [posY, setPosY] = useState("0");
        const [posZ, setPosZ] = useState("0");
        const [roomId, setRoomId] = useState("UNASSIGNED");
        const [coverageRadius, setCoverageRadius] = useState("6.37");
        const [spacing, setSpacing] = useState("9.1");
        const [ceilingHeight, setCeilingHeight] = useState("3.0");
        const [occupancyType, setOccupancyType] = useState("office");

        // Project mapping
        const [projectJson, setProjectJson] = useState(
                JSON.stringify(
                        {
                                project_name: "Sample Project",
                                building_name: "Building A",
                                rooms: [
                                        {
                                                room_id: "RM-001",
                                                name: "Office 101",
                                                area_m2: 45.0,
                                                ceiling_height_m: 3.0,
                                        },
                                ],
                                detectors: [
                                        {
                                                device_id: "DET-001",
                                                type: "smoke",
                                                x: 5.0,
                                                y: 3.0,
                                                z: 2.8,
                                                room_id: "RM-001",
                                                coverage_radius_m: 6.37,
                                                spacing_m: 9.1,
                                        },
                                ],
                        },
                        null,
                        2,
                ),
        );

        // Results
        const [detectorResult, setDetectorResult] = useState<Record<string, unknown> | null>(null);
        const [projectResult, setProjectResult] = useState<Record<string, unknown> | null>(null);
        const [detectorLoading, setDetectorLoading] = useState(false);
        const [projectLoading, setProjectLoading] = useState(false);

        const roomsCount: string = String(projectResult?.rooms_count ?? "N/A");
        const detectorsCount: string = String(projectResult?.detectors_count ?? "N/A");
        const schemaVersion: string = (projectResult?.schema_version as string) || "N/A";
        const buildingGlobalId: string = (projectResult?.building_global_id as string) || "N/A";

        const handleMapDetector = async () => {
                setDetectorLoading(true);
                setDetectorResult(null);
                try {
                        const res = await v2Api.mapDetectorToIfc43({
                                device_id: deviceId || `DET-${Date.now()}`,
                                type: detectorType,
                                x: Number.parseFloat(posX) || 0,
                                y: Number.parseFloat(posY) || 0,
                                z: Number.parseFloat(posZ) || 0,
                                room_id: roomId,
                                coverage_radius_m: Number.parseFloat(coverageRadius) || 6.37,
                                spacing_m: Number.parseFloat(spacing) || 9.1,
                                ceiling_height_m: Number.parseFloat(ceilingHeight) || 3.0,
                                occupancy_type: occupancyType,
                        });
                        setDetectorResult(res as Record<string, unknown>);
                } catch (err: unknown) {
                        console.error("IFC 4.3 detector mapping failed:", err);
                } finally {
                        setDetectorLoading(false);
                }
        };

        const handleMapProject = async () => {
                setProjectLoading(true);
                setProjectResult(null);
                try {
                        let parsed: Record<string, unknown>;
                        try {
                                parsed = JSON.parse(projectJson) as Record<string, unknown>;
                        } catch {
                                console.error("Invalid project JSON");
                                return;
                        }
                        const res = await v2Api.mapProjectToIfc43(parsed);
                        setProjectResult(res as Record<string, unknown>);
                } catch (err: unknown) {
                        console.error("IFC 4.3 project mapping failed:", err);
                } finally {
                        setProjectLoading(false);
                }
        };

        return (
                <div className="flex-1 overflow-auto">
                        <div className="p-6 max-w-4xl mx-auto space-y-6">
                                {/* Header */}
                                <div className="flex items-center gap-3">
                                        <Globe aria-hidden="true" className="h-8 w-8 text-info" />
                                        <div>
                                                <h1 className="text-2xl font-bold text-foreground">
                                                        IFC 4.3 Mapping
                                                </h1>
                                                <p className="text-sm text-muted-foreground">
                                                        Map fire alarm devices and projects to IFC 4.3 ADD2 schema
                                                </p>
                                        </div>
                                </div>

                                <Tabs defaultValue="detector">
                                        <TabsList className="bg-card border border-border">
                                                <TabsTrigger
                                                        value="detector"
                                                        className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
                                                >
                                                        <Target aria-hidden="true" className="h-4 w-4 mr-1" />
                                                        Map Detector
                                                </TabsTrigger>
                                                <TabsTrigger
                                                        value="project"
                                                        className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
                                                >
                                                        <Building2 aria-hidden="true" className="h-4 w-4 mr-1" />
                                                        Map Project
                                                </TabsTrigger>
                                        </TabsList>

                                        {/* Map Detector Tab */}
                                        <TabsContent value="detector">
                                                <Card className="border-border bg-card">
                                                        <CardHeader className="pb-3">
                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                        <Target aria-hidden="true" className="h-5 w-5 text-info" />
                                                                        Detector to IFC 4.3
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        Map a single fire alarm detector to its IFC 4.3 ADD2 representation
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Device ID</Label>
                                                                                <Input
                                                                                        type="text"
                                                                                        placeholder="DET-001"
                                                                                        value={deviceId}
                                                                                        onChange={(e) => setDeviceId(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Detector Type</Label>
                                                                                <select
                                                                                        value={detectorType}
                                                                                        onChange={(e) => setDetectorType(e.target.value)}
                                                                                        className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                                                                                >
                                                                                        <option value="smoke">Smoke</option>
                                                                                        <option value="heat">Heat</option>
                                                                                        <option value="carbon_monoxide">Carbon Monoxide</option>
                                                                                        <option value="multi_criteria">Multi-Criteria</option>
                                                                                        <option value="beam">Beam</option>
                                                                                        <option value="duct">Duct</option>
                                                                                </select>
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">X (m)</Label>
                                                                                <Input
                                                                                        type="number"
                                                                                        step="0.1"
                                                                                        value={posX}
                                                                                        onChange={(e) => setPosX(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Y (m)</Label>
                                                                                <Input
                                                                                        type="number"
                                                                                        step="0.1"
                                                                                        value={posY}
                                                                                        onChange={(e) => setPosY(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Z (m)</Label>
                                                                                <Input
                                                                                        type="number"
                                                                                        step="0.1"
                                                                                        value={posZ}
                                                                                        onChange={(e) => setPosZ(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Room ID</Label>
                                                                                <Input
                                                                                        type="text"
                                                                                        placeholder="UNASSIGNED"
                                                                                        value={roomId}
                                                                                        onChange={(e) => setRoomId(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        Coverage Radius (m)
                                                                                </Label>
                                                                                <Input
                                                                                        type="number"
                                                                                        step="0.01"
                                                                                        value={coverageRadius}
                                                                                        onChange={(e) => setCoverageRadius(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">Spacing (m)</Label>
                                                                                <Input
                                                                                        type="number"
                                                                                        step="0.1"
                                                                                        value={spacing}
                                                                                        onChange={(e) => setSpacing(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        Ceiling Height (m)
                                                                                </Label>
                                                                                <Input
                                                                                        type="number"
                                                                                        step="0.1"
                                                                                        value={ceilingHeight}
                                                                                        onChange={(e) => setCeilingHeight(e.target.value)}
                                                                                        className="bg-card border-border text-foreground"
                                                                                />
                                                                        </div>
                                                                        <div className="space-y-2">
                                                                                <Label className="text-foreground/90">
                                                                                        Occupancy Type
                                                                                </Label>
                                                                                <select
                                                                                        value={occupancyType}
                                                                                        onChange={(e) => setOccupancyType(e.target.value)}
                                                                                        className="w-full bg-card border border-border rounded px-3 py-2 text-foreground"
                                                                                >
                                                                                        <option value="office">Office</option>
                                                                                        <option value="assembly">Assembly</option>
                                                                                        <option value="educational">Educational</option>
                                                                                        <option value="healthcare">Healthcare</option>
                                                                                        <option value="industrial">Industrial</option>
                                                                                        <option value="storage">Storage</option>
                                                                                </select>
                                                                        </div>
                                                                </div>

                                                                <div className="pt-4">
                                                                        <Button
                                                                                className="bg-primary hover:bg-primary/90 text-primary-foreground border-none"
                                                                                onClick={handleMapDetector}
                                                                                disabled={detectorLoading}
                                                                        >
                                                                                {detectorLoading ? (
                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 mr-1 animate-spin" />
                                                                                ) : (
                                                                                        <MapIcon aria-hidden="true" className="h-4 w-4 mr-1" />
                                                                                )}
                                                                                {detectorLoading ? "Mapping…" : "Map to IFC 4.3"}
                                                                        </Button>
                                                                </div>

                                                                {detectorResult && (
                                                                        <div className="p-4 rounded-lg bg-card border border-border">
                                                                                <div className="flex items-center gap-2 mb-2">
                                                                                        <CheckCircle2
                                                                                                aria-hidden="true"
                                                                                                className="h-5 w-5 text-success"
                                                                                        />
                                                                                        <span className="text-sm font-medium text-foreground">
                                                                                                Mapping Result
                                                                                        </span>
                                                                                </div>
                                                                                <pre className="text-xs text-muted-foreground overflow-auto max-h-64 font-mono">
                                                                                        {JSON.stringify(detectorResult, null, 2)}
                                                                                </pre>
                                                                        </div>
                                                                )}
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>

                                        {/* Map Project Tab */}
                                        <TabsContent value="project">
                                                <Card className="border-border bg-card">
                                                        <CardHeader className="pb-3">
                                                                <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                        <Building2 aria-hidden="true" className="h-5 w-5 text-info" />
                                                                        Project to IFC 4.3
                                                                </CardTitle>
                                                                <CardDescription className="text-muted-foreground">
                                                                        Map an entire FireAI project (rooms + detectors) to IFC 4.3 ADD2 schema
                                                                </CardDescription>
                                                        </CardHeader>
                                                        <CardContent className="space-y-4">
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                Project JSON
                                                                        </Label>
                                                                        <Textarea
                                                                                value={projectJson}
                                                                                onChange={(e) => setProjectJson(e.target.value)}
                                                                                className="min-h-[200px] bg-card border-border text-foreground font-mono text-xs"
                                                                                placeholder='{"project_name": "...", "building_name": "...", "rooms": [...], "detectors": [...]}'
                                                                        />
                                                                        <p className="text-xs text-muted-foreground">
                                                                                Define the project structure with rooms and detector arrays
                                                                        </p>
                                                                </div>

                                                                <div className="pt-4">
                                                                        <Button
                                                                                className="bg-primary hover:bg-primary/90 text-primary-foreground border-none"
                                                                                onClick={handleMapProject}
                                                                                disabled={projectLoading}
                                                                        >
                                                                                {projectLoading ? (
                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 mr-1 animate-spin" />
                                                                                ) : (
                                                                                        <Globe aria-hidden="true" className="h-4 w-4 mr-1" />
                                                                                )}
                                                                                {projectLoading ? "Mapping Project…" : "Map Project to IFC 4.3"}
                                                                        </Button>
                                                                </div>

                                                                {projectResult && (
                                                                        <div className="p-4 rounded-lg bg-card border border-border">
                                                                                <div className="flex items-center gap-2 mb-2">
                                                                                        <CheckCircle2
                                                                                                aria-hidden="true"
                                                                                                className="h-5 w-5 text-success"
                                                                                        />
                                                                                        <span className="text-sm font-medium text-foreground">
                                                                                                Project Mapping Result
                                                                                        </span>
                                                                                </div>
                                                                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                                                                                        {!!projectResult.header && (
                                                                                                <div className="p-2 rounded bg-secondary/30">
                                                                                                        <p className="text-xs text-muted-foreground">Schema</p>
                                                                                                        <p className="text-sm font-medium text-foreground">
                                                                                                                {schemaVersion}
                                                                                                        </p>
                                                                                                </div>
                                                                                        )}
                                                                                        <div className="p-2 rounded bg-secondary/30">
                                                                                                <p className="text-xs text-muted-foreground">Rooms</p>
                                                                                                <p className="text-sm font-medium text-foreground">
                                                                                                        {roomsCount}
                                                                                                </p>
                                                                                        </div>
                                                                                        <div className="p-2 rounded bg-secondary/30">
                                                                                                <p className="text-xs text-muted-foreground">Detectors</p>
                                                                                                <p className="text-sm font-medium text-foreground">
                                                                                                        {detectorsCount}
                                                                                                </p>
                                                                                        </div>
                                                                                        <div className="p-2 rounded bg-secondary/30">
                                                                                                <p className="text-xs text-muted-foreground">Building ID</p>
                                                                                                <p className="text-sm font-medium text-foreground font-mono text-xs truncate">
                                                                                                        {buildingGlobalId}
                                                                                                </p>
                                                                                        </div>
                                                                                </div>
                                                                                <pre className="text-xs text-muted-foreground overflow-auto max-h-64 font-mono">
                                                                                        {JSON.stringify(projectResult, null, 2)}
                                                                                </pre>
                                                                        </div>
                                                                )}
                                                        </CardContent>
                                                </Card>
                                        </TabsContent>
                                </Tabs>

                                <Separator className="bg-border" />

                                {/* Info card */}
                                <Card className="border-border bg-card">
                                        <CardHeader className="pb-3">
                                                <CardTitle className="text-lg text-foreground">
                                                        About IFC 4.3 ADD2
                                                </CardTitle>
                                                <CardDescription className="text-muted-foreground">
                                                        Industry Foundation Classes for fire alarm engineering
                                                </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                                <p className="text-sm text-muted-foreground">
                                                        IFC 4.3 ADD2 introduces dedicated fire alarm types including
                                                        <code className="text-cyan-400 mx-1">IfcFireSuppressionTerminal</code>
                                                        and predefined types for smoke detectors, heat detectors, and notification
                                                        devices. This mapping translates FireAI's internal device model into
                                                        standards-compliant IFC entities for interoperability with BIM
                                                        authoring tools (Revit, ArchiCAD, Solibri).
                                                </p>
                                        </CardContent>
                                </Card>
                        </div>
                </div>
        );
}
