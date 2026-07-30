import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Layers, Loader2, CheckCircle2, Circle, AlertCircle } from "lucide-react";
import { apiCall } from "@/services/fullApi";

interface LayerResult {
    name: string;
    status: "pending" | "running" | "completed" | "failed";
    result?: Record<string, unknown>;
}

const LAYER_NAMES = ["layer1", "layer2", "layer3", "layer4", "layer5", "layer6"] as const;

export function PipelineLayersPage() {
    const { t } = useTranslation();
    const [framework, setFramework] = useState("nfpa72");
    const [layers, setLayers] = useState<LayerResult[]>(
        LAYER_NAMES.map((name) => ({ name, status: "pending" }))
    );
    const [running, setRunning] = useState(false);
    const [finalResult, setFinalResult] = useState<Record<string, unknown> | null>(null);

    const runPipeline = async () => {
        setRunning(true);
        setFinalResult(null);
        const updatedLayers = LAYER_NAMES.map((name) => ({ name, status: "pending" as const }));
        setLayers(updatedLayers);

        for (let i = 0; i < LAYER_NAMES.length; i++) {
            setLayers((prev) =>
                prev.map((l, idx) => (idx === i ? { ...l, status: "running" as const } : l))
            );
            try {
                const result = await apiCall("/fireai/pipeline/run", {
                    method: "POST",
                    body: JSON.stringify({ layer: i + 1, framework }),
                });
                setLayers((prev) =>
                    prev.map((l, idx) =>
                        idx === i ? { ...l, status: "completed" as const, result: result as Record<string, unknown> } : l
                    )
                );
            } catch {
                setLayers((prev) =>
                    prev.map((l, idx) => (idx === i ? { ...l, status: "failed" as const } : l))
                );
                break;
            }
        }
        setRunning(false);
    };

    const statusIcon = (status: LayerResult["status"]) => {
        switch (status) {
            case "completed": return <CheckCircle2 className="h-5 w-5 text-green-500" />;
            case "running": return <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />;
            case "failed": return <AlertCircle className="h-5 w-5 text-red-500" />;
            default: return <Circle className="h-5 w-5 text-muted-foreground" />;
        }
    };

    return (
        <div className="space-y-6 p-6">
            <div className="flex items-center gap-3">
                <Layers className="h-8 w-8 text-cyan-500" />
                <div>
                    <h1 className="text-2xl font-bold">{t("fireai.pipeline.title")}</h1>
                    <p className="text-muted-foreground">5+1 layer NFPA 72 compliance pipeline</p>
                </div>
            </div>

            <div className="flex gap-4 items-end">
                <div className="space-y-2">
                    <label className="text-sm font-medium">{t("fireai.pipeline.regulatoryFramework")}</label>
                    <Select value={framework} onValueChange={setFramework}>
                        <SelectTrigger className="w-48">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="nfpa72">{t("fireai.pipeline.nfpa72")}</SelectItem>
                            <SelectItem value="nec2023">{t("fireai.pipeline.nec2023")}</SelectItem>
                            <SelectItem value="ibc2021">{t("fireai.pipeline.ibc2021")}</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
                <Button onClick={runPipeline} disabled={running}>
                    {running ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Layers className="h-4 w-4 mr-2" />}
                    {t("fireai.pipeline.runPipeline")}
                </Button>
            </div>

            <div className="space-y-3">
                {layers.map((layer, idx) => (
                    <Card key={layer.name}>
                        <CardHeader className="py-3">
                            <CardTitle className="text-base flex items-center gap-2">
                                {statusIcon(layer.status)}
                                {t(`fireai.pipeline.layer${idx + 1}`)}
                                {layer.status === "completed" && (
                                    <Badge variant="default" className="ml-2">Completed</Badge>
                                )}
                                {layer.status === "failed" && (
                                    <Badge variant="destructive" className="ml-2">Failed</Badge>
                                )}
                            </CardTitle>
                        </CardHeader>
                        {layer.result && (
                            <CardContent>
                                <pre className="bg-muted p-3 rounded text-xs overflow-auto">
                                    {JSON.stringify(layer.result, null, 2)}
                                </pre>
                            </CardContent>
                        )}
                    </Card>
                ))}
            </div>

            {finalResult && (
                <Card>
                    <CardHeader>
                        <CardTitle>{t("fireai.pipeline.pipelineResults")}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <pre className="bg-muted p-4 rounded-lg overflow-auto text-sm">
                            {JSON.stringify(finalResult, null, 2)}
                        </pre>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
