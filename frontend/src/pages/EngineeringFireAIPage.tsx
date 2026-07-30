import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Flame, Building2, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { apiCall } from "@/services/fullApi";

export function EngineeringFireAIPage() {
    const { t } = useTranslation();
    const [activeTab, setActiveTab] = useState("room-analysis");
    const [loading, setLoading] = useState(false);
    const [roomResults, setRoomResults] = useState<Record<string, unknown> | null>(null);
    const [floorResults, setFloorResults] = useState<Record<string, unknown> | null>(null);
    const [roomId, setRoomId] = useState("");
    const [floorId, setFloorId] = useState("");

    const handleRoomAnalysis = async () => {
        setLoading(true);
        try {
            const result = await apiCall("/analyse", {
                method: "POST",
                body: JSON.stringify({ room_id: roomId }),
            });
            setRoomResults(result as Record<string, unknown>);
        } catch {
            setRoomResults({ error: "Analysis failed" });
        } finally {
            setLoading(false);
        }
    };

    const handleFloorAnalysis = async () => {
        setLoading(true);
        try {
            const result = await apiCall("/analyse/floor", {
                method: "POST",
                body: JSON.stringify({ floor_id: floorId }),
            });
            setFloorResults(result as Record<string, unknown>);
        } catch {
            setFloorResults({ error: "Analysis failed" });
        } finally {
            setLoading(false);
        }
    };

    const renderComplianceBadge = (compliant: boolean) => (
        <Badge variant={compliant ? "default" : "destructive"} className="flex items-center gap-1 w-fit">
            {compliant ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
            {compliant ? t("fireai.compliant") : t("fireai.nonCompliant")}
        </Badge>
    );

    return (
        <div className="space-y-6 p-6">
            <div className="flex items-center gap-3">
                <Flame className="h-8 w-8 text-orange-500" />
                <div>
                    <h1 className="text-2xl font-bold">{t("fireai.title")}</h1>
                    <p className="text-muted-foreground">NFPA 72 Fire Protection Analysis</p>
                </div>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList>
                    <TabsTrigger value="room-analysis">{t("fireai.roomAnalysis")}</TabsTrigger>
                    <TabsTrigger value="floor-analysis">{t("fireai.floorAnalysis")}</TabsTrigger>
                </TabsList>

                <TabsContent value="room-analysis" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t("fireai.roomAnalysis")}</CardTitle>
                            <CardDescription>{t("fireai.selectRoom")}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex gap-4 items-end">
                                <div className="flex-1 space-y-2">
                                    <Label htmlFor="room-id">Room ID</Label>
                                    <Input
                                        id="room-id"
                                        value={roomId}
                                        onChange={(e) => setRoomId(e.target.value)}
                                        placeholder="e.g., room-101"
                                    />
                                </div>
                                <Button onClick={handleRoomAnalysis} disabled={loading || !roomId}>
                                    {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Flame className="h-4 w-4 mr-2" />}
                                    {t("fireai.analyzeRoom")}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {roomResults && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    {t("fireai.results")}
                                    {roomResults.compliant !== undefined && renderComplianceBadge(roomResults.compliant as boolean)}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <pre className="bg-muted p-4 rounded-lg overflow-auto text-sm">
                                    {JSON.stringify(roomResults, null, 2)}
                                </pre>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>

                <TabsContent value="floor-analysis" className="space-y-4">
                    <Card>
                        <CardHeader>
                            <CardTitle>{t("fireai.floorAnalysis")}</CardTitle>
                            <CardDescription>{t("fireai.selectFloor")}</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex gap-4 items-end">
                                <div className="flex-1 space-y-2">
                                    <Label htmlFor="floor-id">Floor ID</Label>
                                    <Input
                                        id="floor-id"
                                        value={floorId}
                                        onChange={(e) => setFloorId(e.target.value)}
                                        placeholder="e.g., floor-1"
                                    />
                                </div>
                                <Button onClick={handleFloorAnalysis} disabled={loading || !floorId}>
                                    {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Building2 className="h-4 w-4 mr-2" />}
                                    {t("fireai.analyzeFloor")}
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {floorResults && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    {t("fireai.results")}
                                    {floorResults.compliant !== undefined && renderComplianceBadge(floorResults.compliant as boolean)}
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <pre className="bg-muted p-4 rounded-lg overflow-auto text-sm">
                                    {JSON.stringify(floorResults, null, 2)}
                                </pre>
                            </CardContent>
                        </Card>
                    )}
                </TabsContent>
            </Tabs>
        </div>
    );
}
