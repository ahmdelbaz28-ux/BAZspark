/**
 * TopologyPage.tsx — Network Topology Graph Analysis UI.
 *
 * V270: New page for v2 topology endpoints.
 * - Health check (GET /topology/health)
 * - Add element (POST /topology/element)
 * - Add connection (POST /topology/connection)
 * - Impact analysis (POST /topology/impact)
 */
import { useState } from "react";
import {
  Activity,
  GitBranch,
  Loader2,
  Network,
  Plus,
  Search,
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
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { v2Api } from "@/services/fullApi";
import { useToast } from "@/hooks/use-toast";

const ELEMENT_TYPES = [
  { value: "Bus", label: "Bus" },
  { value: "Line", label: "Line" },
  { value: "Transformer", label: "Transformer" },
  { value: "Load", label: "Load" },
  { value: "Breaker", label: "Breaker" },
  { value: "Generator", label: "Generator" },
];

const RELATIONSHIP_TYPES = [
  { value: "CONNECTED_TO", label: "Connected To" },
  { value: "FEEDS", label: "Feeds" },
  { value: "PROTECTED_BY", label: "Protected By" },
  { value: "CONTROLS", label: "Controls" },
];

export function TopologyPage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("elements");
  const [healthStatus, setHealthStatus] = useState<Record<string, unknown> | null>(null);
  const [impactResult, setImpactResult] = useState<Record<string, unknown> | null>(null);

  // Add element form
  const [elementId, setElementId] = useState("");
  const [elementType, setElementType] = useState("Bus");
  const [elementName, setElementName] = useState("");

  // Add connection form
  const [fromElement, setFromElement] = useState("");
  const [toElement, setToElement] = useState("");
  const [relType, setRelType] = useState("CONNECTED_TO");

  // Impact analysis form
  const [breakerId, setBreakerId] = useState("");

  const handleHealth = async () => {
    setLoading(true);
    try {
      const res = await v2Api.getTopologyHealth();
      setHealthStatus(res as Record<string, unknown>);
      toast({ title: "Health check complete", description: "Topology service status retrieved" });
    } catch (err) {
      toast({
        title: "Health check failed",
        description: err instanceof Error ? err.message : "Topology service may not be configured",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAddElement = async () => {
    if (!elementId) {
      toast({ title: "Element ID is required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = await v2Api.addTopologyElement({
        element_id: elementId,
        element_type: elementType,
        name: elementName || elementId,
        properties: {},
      });
      const data = res as { added?: boolean };
      toast({
        title: data.added ? "Element added" : "Element may already exist",
        description: `ID: ${elementId}`,
        variant: "default",
      });
      setElementId("");
      setElementName("");
    } catch (err) {
      toast({
        title: "Failed to add element",
        description: err instanceof Error ? err.message : "Failed",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAddConnection = async () => {
    if (!fromElement || !toElement) {
      toast({ title: "Both source and target elements are required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = await v2Api.addTopologyConnection({
        from_element: fromElement,
        to_element: toElement,
        relationship_type: relType,
        properties: {},
      });
      const data = res as { added?: boolean };
      toast({
        title: data.added ? "Connection added" : "Connection may already exist",
        description: `${fromElement} → ${toElement}`,
      });
      setFromElement("");
      setToElement("");
    } catch (err) {
      toast({
        title: "Failed to add connection",
        description: err instanceof Error ? err.message : "Failed",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleImpactAnalysis = async () => {
    if (!breakerId) {
      toast({ title: "Breaker ID is required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = await v2Api.analyzeTopologyImpact({ breaker_id: breakerId });
      setImpactResult(res as Record<string, unknown>);
      toast({ title: "Impact analysis complete", description: `Breaker: ${breakerId}` });
    } catch (err) {
      toast({
        title: "Impact analysis failed",
        description: err instanceof Error ? err.message : "Failed",
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
            <Network aria-hidden="true" className="h-5 w-5 text-primary" />
            Network Topology
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Manage power system topology graph and analyze fault impacts
          </p>
        </div>

        {/* Health Check */}
        <div className="flex items-center gap-3">
          <Button onClick={handleHealth} disabled={loading} variant="outline">
            {loading ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : (
              <Activity aria-hidden="true" className="h-4 w-4" />
            )}
            Check Topology Health
          </Button>
          {healthStatus && (
            <div className="flex items-center gap-2">
              {Object.entries(healthStatus).map(([key, val]) => (
                <Badge
                  key={key}
                  variant={val === true || val === "ok" || val === "healthy" ? "default" : "secondary"}
                  className="text-xs"
                >
                  {key}: {String(val)}
                </Badge>
              ))}
            </div>
          )}
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-card border border-border">
            <TabsTrigger
              value="elements"
              className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
            >
              <Plus aria-hidden="true" className="h-4 w-4 mr-1" />
              Add Elements
            </TabsTrigger>
            <TabsTrigger
              value="connections"
              className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
            >
              <GitBranch aria-hidden="true" className="h-4 w-4 mr-1" />
              Add Connections
            </TabsTrigger>
            <TabsTrigger
              value="impact"
              className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
            >
              <Zap aria-hidden="true" className="h-4 w-4 mr-1" />
              Impact Analysis
            </TabsTrigger>
          </TabsList>

          {/* Elements Tab */}
          <TabsContent value="elements">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Plus aria-hidden="true" className="h-4 w-4 text-primary" />
                  Add Network Element
                </CardTitle>
                <CardDescription>
                  Add a bus, line, transformer, load, breaker, or generator to the topology graph
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">Element ID</Label>
                    <Input
                      autoComplete="off"
                      value={elementId}
                      onChange={(e) => setElementId(e.target.value)}
                      placeholder="bus-001"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">Element Type</Label>
                    <Select value={elementType} onValueChange={setElementType}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {ELEMENT_TYPES.map((et) => (
                          <SelectItem key={et.value} value={et.value}>
                            {et.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5 md:col-span-2">
                    <Label className="text-xs text-muted-foreground">Element Name (optional)</Label>
                    <Input
                      autoComplete="off"
                      value={elementName}
                      onChange={(e) => setElementName(e.target.value)}
                      placeholder="Main Bus 1"
                    />
                  </div>
                </div>
                <Button
                  onClick={handleAddElement}
                  disabled={loading}
                  className="mt-4 bg-primary hover:bg-primary/90 text-primary-foreground"
                >
                  {loading ? (
                    <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                  ) : (
                    <Plus aria-hidden="true" className="h-4 w-4" />
                  )}
                  Add Element
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Connections Tab */}
          <TabsContent value="connections">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <GitBranch aria-hidden="true" className="h-4 w-4 text-primary" />
                  Add Network Connection
                </CardTitle>
                <CardDescription>
                  Define relationships between network elements in the Neo4j topology graph
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">From Element</Label>
                    <Input
                      autoComplete="off"
                      value={fromElement}
                      onChange={(e) => setFromElement(e.target.value)}
                      placeholder="bus-001"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs text-muted-foreground">To Element</Label>
                    <Input
                      autoComplete="off"
                      value={toElement}
                      onChange={(e) => setToElement(e.target.value)}
                      placeholder="load-042"
                    />
                  </div>
                  <div className="space-y-1.5 md:col-span-2">
                    <Label className="text-xs text-muted-foreground">Relationship Type</Label>
                    <Select value={relType} onValueChange={setRelType}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {RELATIONSHIP_TYPES.map((rt) => (
                          <SelectItem key={rt.value} value={rt.value}>
                            {rt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button
                  onClick={handleAddConnection}
                  disabled={loading}
                  className="mt-4 bg-primary hover:bg-primary/90 text-primary-foreground"
                >
                  {loading ? (
                    <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                  ) : (
                    <GitBranch aria-hidden="true" className="h-4 w-4" />
                  )}
                  Add Connection
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Impact Analysis Tab */}
          <TabsContent value="impact">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Zap aria-hidden="true" className="h-4 w-4 text-primary" />
                  Breaker Impact Analysis
                </CardTitle>
                <CardDescription>
                  Analyze which loads and buses are affected when a specific breaker trips
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-1.5">
                  <Label className="text-xs text-muted-foreground">Breaker ID</Label>
                  <div className="flex gap-2">
                    <Input
                      autoComplete="off"
                      value={breakerId}
                      onChange={(e) => setBreakerId(e.target.value)}
                      placeholder="breaker-001"
                      className="max-w-xs"
                    />
                    <Button
                      onClick={handleImpactAnalysis}
                      disabled={loading || !breakerId}
                    >
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Search aria-hidden="true" className="h-4 w-4" />
                      )}
                      Analyze
                    </Button>
                  </div>
                </div>

                {impactResult && (
                  <div className="mt-4 p-3 rounded-lg bg-muted/50 border border-border">
                    <pre className="text-xs font-mono whitespace-pre-wrap text-foreground max-h-64 overflow-auto">
                      {JSON.stringify(impactResult, null, 2)}
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Empty state */}
        {!healthStatus && !impactResult && (
          <Card>
            <CardContent className="py-12">
              <div className="flex flex-col items-center text-center">
                <Network
                  aria-hidden="true"
                  className="h-12 w-12 text-muted-foreground/40 mb-4"
                />
                <p className="text-muted-foreground font-medium">
                  Neo4j Topology Graph Manager
                </p>
                <p className="text-sm text-muted-foreground/60 mt-1">
                  Add power system elements and connections, then analyze breaker trip impacts
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
