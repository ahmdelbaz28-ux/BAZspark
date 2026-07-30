/**
 * GenerativeDesignPage.tsx — Generative layout optimization UI.
 *
 * V270: New page for POST /api/v2/generative/design.
 * Generates 3 layout variants (Cost-Min, Standard, Safety-Max)
 * based on room parameters and occupancy type.
 */
import { useState } from "react";
import {
  Dumbbell,
  Layers,
  Loader2,
  Sparkles,
  TrendingDown,
  TrendingUp,
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
import { Separator } from "@/components/ui/separator";
import { v2Api } from "@/services/fullApi";
import { useToast } from "@/hooks/use-toast";

interface DesignVariant {
  variant_name: string;
  detector_count: number;
  pull_station_count: number;
  notification_count: number;
  total_cost_score: number;
  coverage_pct: number;
  spacing_m: number;
  total_wire_m: number;
  code_compliant: boolean;
  score: number;
}

interface DesignResult {
  variants: DesignVariant[];
  recommended_index: number;
  room_name: string;
  generation_time_s: number;
}

const OCCUPANCY_TYPES = [
  { value: "office", label: "Office" },
  { value: "assembly", label: "Assembly" },
  { value: "educational", label: "Educational" },
  { value: "health_care", label: "Health Care" },
  { value: "residential", label: "Residential" },
  { value: "mercantile", label: "Mercantile" },
  { value: "industrial", label: "Industrial" },
  { value: "storage", label: "Storage" },
  { value: "high_hazard", label: "High Hazard" },
];

const DETECTOR_TYPES = [
  { value: "smoke", label: "Smoke" },
  { value: "heat", label: "Heat" },
  { value: "multi", label: "Multi-Criteria" },
];

const VARIANT_COLORS: Record<string, string> = {
  "cost-min": "text-emerald-400",
  standard: "text-blue-400",
  "safety-max": "text-amber-400",
};

export function GenerativeDesignPage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DesignResult | null>(null);

  // Room parameters
  const [roomWidth, setRoomWidth] = useState(10);
  const [roomLength, setRoomLength] = useState(12);
  const [roomHeight, setRoomHeight] = useState(3);
  const [roomName, setRoomName] = useState("Main Office");
  const [occupancyType, setOccupancyType] = useState("office");
  const [detectorType, setDetectorType] = useState("smoke");
  const [useMultiprocessing, setUseMultiprocessing] = useState(true);

  const handleGenerate = async () => {
    if (roomWidth <= 0 || roomLength <= 0 || roomHeight <= 0) {
      toast({ title: "Dimensions must be greater than 0", variant: "destructive" });
      return;
    }
    if (roomWidth > 1000 || roomLength > 1000) {
      toast({ title: "Dimensions cannot exceed 1000m", variant: "destructive" });
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await v2Api.generativeDesign({
        room_width: roomWidth,
        room_length: roomLength,
        room_height: roomHeight,
        room_name: roomName || "API_Room",
        occupancy_type: occupancyType,
        detector_type: detectorType,
        use_multiprocessing: useMultiprocessing,
      });
      setResult(res as DesignResult);
      toast({
        title: "Design generated",
        description: `Created ${(res as DesignResult).variants?.length || 0} variants`,
      });
    } catch (err) {
      toast({
        title: "Generation failed",
        description: err instanceof Error ? err.message : "Generative layout engine may not be available",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Sparkles aria-hidden="true" className="h-5 w-5 text-primary" />
            Generative Design
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Generate optimized fire alarm layout variants using AI-powered spatial optimization
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Input Panel */}
          <Card className="lg:col-span-2 border-border bg-card">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Dumbbell aria-hidden="true" className="h-4 w-4 text-primary" />
                Room Parameters
              </CardTitle>
              <CardDescription>
                Define the room dimensions and occupancy for layout generation
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Width (m)</Label>
                  <Input
                    autoComplete="off"
                    type="number"
                    value={roomWidth}
                    onChange={(e) => setRoomWidth(Number(e.target.value))}
                    min={1}
                    max={1000}
                    step={0.5}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Length (m)</Label>
                  <Input
                    autoComplete="off"
                    type="number"
                    value={roomLength}
                    onChange={(e) => setRoomLength(Number(e.target.value))}
                    min={1}
                    max={1000}
                    step={0.5}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Ceiling Height (m)</Label>
                <Input
                  autoComplete="off"
                  type="number"
                  value={roomHeight}
                  onChange={(e) => setRoomHeight(Number(e.target.value))}
                  min={1}
                  max={30}
                  step={0.1}
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Room Name</Label>
                <Input
                  autoComplete="off"
                  value={roomName}
                  onChange={(e) => setRoomName(e.target.value)}
                  placeholder="Main Office"
                />
              </div>

              <Separator className="bg-border" />

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Occupancy Type</Label>
                <Select value={occupancyType} onValueChange={setOccupancyType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OCCUPANCY_TYPES.map((ot) => (
                      <SelectItem key={ot.value} value={ot.value}>
                        {ot.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs text-muted-foreground">Detector Type</Label>
                <Select value={detectorType} onValueChange={setDetectorType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DETECTOR_TYPES.map((dt) => (
                      <SelectItem key={dt.value} value={dt.value}>
                        {dt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between">
                <Label className="text-xs text-muted-foreground">Use Multiprocessing</Label>
                <Badge
                  variant={useMultiprocessing ? "default" : "secondary"}
                  className="cursor-pointer text-xs"
                  onClick={() => setUseMultiprocessing(!useMultiprocessing)}
                >
                  {useMultiprocessing ? "ON" : "OFF"}
                </Badge>
              </div>

              <Button
                onClick={handleGenerate}
                disabled={loading}
                className="w-full bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                {loading ? (
                  <>
                    <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin mr-2" />
                    Generating Variants…
                  </>
                ) : (
                  <>
                    <Sparkles aria-hidden="true" className="h-4 w-4 mr-2" />
                    Generate Layout Variants
                  </>
                )}
              </Button>
            </CardContent>
          </Card>

          {/* Results Panel */}
          <div className="lg:col-span-3 space-y-4">
            {!result && !loading && (
              <Card>
                <CardContent className="py-16">
                  <div className="flex flex-col items-center text-center">
                    <Layers
                      aria-hidden="true"
                      className="h-16 w-16 text-muted-foreground/30 mb-4"
                    />
                    <p className="text-muted-foreground font-medium">
                      Enter room parameters and generate design variants
                    </p>
                    <p className="text-sm text-muted-foreground/60 mt-1">
                      The engine will produce 3 optimized layouts: cost-minimized, standard, and safety-maximized
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {loading && (
              <Card>
                <CardContent className="py-16">
                  <div className="flex flex-col items-center text-center">
                    <Loader2
                      aria-hidden="true"
                      className="h-12 w-12 animate-spin text-primary mb-4"
                    />
                    <p className="text-muted-foreground font-medium">
                      Generating layout variants…
                    </p>
                    <p className="text-sm text-muted-foreground/60 mt-1">
                      Running spatial optimization engine
                    </p>
                  </div>
                </CardContent>
              </Card>
            )}

            {result && (
              <>
                {/* Recommendation */}
                <Card className="border-border bg-card">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Sparkles aria-hidden="true" className="h-5 w-5 text-primary" />
                      Recommended:{" "}
                      <span
                        className={
                          VARIANT_COLORS[
                            result.variants[result.recommended_index]?.variant_name || ""
                          ] || "text-foreground"
                        }
                      >
                        {result.variants[result.recommended_index]?.variant_name || "N/A"}
                      </span>
                    </CardTitle>
                    <CardDescription>
                      Room: {result.room_name} &middot; Generated in{" "}
                      {result.generation_time_s?.toFixed(2)}s
                    </CardDescription>
                  </CardHeader>
                </Card>

                {/* Variant Cards */}
                {result.variants?.map((variant, idx) => (
                  <Card
                    key={variant.variant_name}
                    className={`border-border bg-card ${
                      idx === result.recommended_index
                        ? "ring-1 ring-primary/30"
                        : ""
                    }`}
                  >
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2 text-base">
                          {(() => {
                            if (variant.variant_name === "cost-min") {
                              return <TrendingDown aria-hidden="true" className={`h-4 w-4 ${VARIANT_COLORS["cost-min"]}`} />;
                            }
                            if (variant.variant_name === "safety-max") {
                              return <TrendingUp aria-hidden="true" className={`h-4 w-4 ${VARIANT_COLORS["safety-max"]}`} />;
                            }
                            return <Layers aria-hidden="true" className={`h-4 w-4 ${VARIANT_COLORS["standard"]}`} />;
                          })()}
                          <span className="capitalize">
                            {variant.variant_name?.replace("-", " ")}
                          </span>
                          {idx === result.recommended_index && (
                            <Badge className="text-[10px] bg-primary/20 text-primary border-none">
                              Recommended
                            </Badge>
                          )}
                        </CardTitle>
                        <Badge
                          variant={variant.code_compliant ? "default" : "destructive"}
                          className="text-xs"
                        >
                          {variant.code_compliant ? "Compliant" : "Non-Compliant"}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <div>
                          <span className="text-xs text-muted-foreground block">Score</span>
                          <span className="text-lg font-bold text-foreground">
                            {(variant.score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground block">
                            Detectors
                          </span>
                          <span className="text-lg font-bold text-foreground">
                            {variant.detector_count}
                          </span>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground block">
                            Coverage
                          </span>
                          <span className="text-lg font-bold text-foreground">
                            {variant.coverage_pct?.toFixed(1)}%
                          </span>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground block">
                            Cost Score
                          </span>
                          <span className="text-lg font-bold text-foreground">
                            {variant.total_cost_score?.toFixed(2)}
                          </span>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground block">
                            Pull Stations
                          </span>
                          <span className="text-sm text-foreground">
                            {variant.pull_station_count}
                          </span>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground block">
                            Notification
                          </span>
                          <span className="text-sm text-foreground">
                            {variant.notification_count}
                          </span>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground block">
                            Spacing
                          </span>
                          <span className="text-sm text-foreground">
                            {variant.spacing_m?.toFixed(1)}m
                          </span>
                        </div>
                        <div>
                          <span className="text-xs text-muted-foreground block">
                            Total Wire
                          </span>
                          <span className="text-sm text-foreground">
                            {variant.total_wire_m?.toFixed(0)}m
                          </span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
