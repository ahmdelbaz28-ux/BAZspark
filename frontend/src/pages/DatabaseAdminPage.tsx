/**
 * DatabaseAdminPage.tsx — Multi-Database Administration UI.
 *
 * V270: New page at /settings/database for managing:
 * - PostgreSQL, Redis, Neo4j, Qdrant connection health
 * - Redis key/value lookup and set
 * - Neo4j predefined Cypher queries
 * - Qdrant collection listing
 */
import { useState } from "react";
import {
  Activity,
  CheckCircle2,
  Database,
  FileSearch,
  Key,
  Layers,
  Loader2,
  RefreshCw,
  Search,
  Server,
  Share2,
  XCircle,
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
import { v2Api, multiDbApi } from "@/services/fullApi";
import { api } from "@/services/api";
import { useToast } from "@/hooks/use-toast";

interface DbHealth {
  [key: string]: boolean;
}

const NEO4J_QUERIES = [
  { value: "get_element_count", label: "Element Count" },
  { value: "get_relationships", label: "All Relationships (limit 100)" },
];

export function DatabaseAdminPage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("health");
  const [health, setHealth] = useState<DbHealth | null>(null);
  const [mainHealth, setMainHealth] = useState<Record<string, unknown> | null>(null);

  // Redis
  const [redisKey, setRedisKey] = useState("");
  const [redisValue, setRedisValue] = useState("");
  const [redisResult, setRedisResult] = useState<string | null>(null);
  const [redisSetKey, setRedisSetKey] = useState("");
  const [redisSetValue, setRedisSetValue] = useState("");
  const [redisTtl, setRedisTtl] = useState(300);

  // Neo4j
  const [neo4jQueryType, setNeo4jQueryType] = useState("get_element_count");
  const [neo4jResults, setNeo4jResults] = useState<unknown[] | null>(null);

  // Qdrant
  const [qdrantCollections, setQdrantCollections] = useState<string[]>([]);

  // BIM Operations
  const [bimElementId, setBimElementId] = useState("");
  const [bimTopK, setBimTopK] = useState(5);
  const [bimCachedResult, setBimCachedResult] = useState<unknown | null>(null);
  const [bimSimilarResults, setBimSimilarResults] = useState<unknown[] | null>(null);

  const handleCheckHealth = async () => {
    setLoading(true);
    try {
      const [multiRes, healthRes] = await Promise.all([
        v2Api.getMultiDbHealth().catch(() => null),
        api.healthCheck().catch(() => null),
      ]);
      if (multiRes) {
        const data = (multiRes as { data?: DbHealth }).data || {};
        setHealth(data);
      } else {
        setHealth(null);
      }        if (healthRes) {
        setMainHealth(healthRes as unknown as Record<string, unknown>);
      }
      toast({
        title: "Health check complete",
        description: multiRes ? "Multi-db status retrieved" : "Multi-db endpoint unavailable",
      });
    } catch (err) {
      toast({
        title: "Health check failed",
        description: err instanceof Error ? err.message : "Failed",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRedisGet = async () => {
    if (!redisKey) {
      toast({ title: "Enter a Redis key", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = (await v2Api.getRedisValue(redisKey)) as {
        data?: { value?: string };
      };
      const val = res.data?.value ?? "Key not found or empty";
      setRedisResult(val);
      toast({ title: "Redis get complete" });
    } catch (err) {
      setRedisResult("(key not found or Redis unavailable)");
      toast({
        title: "Redis get failed",
        description: err instanceof Error ? err.message : "Key not found",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleRedisSet = async () => {
    if (!redisSetKey || !redisSetValue) {
      toast({ title: "Key and value are required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      await v2Api.setRedisValue(redisSetKey, redisSetValue, redisTtl);
      toast({
        title: "Redis set complete",
        description: `Key: ${redisSetKey} (TTL: ${redisTtl}s)`,
      });
      setRedisSetKey("");
      setRedisSetValue("");
    } catch (err) {
      toast({
        title: "Redis set failed",
        description: err instanceof Error ? err.message : "Failed",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleNeo4jQuery = async () => {
    setLoading(true);
    try {
      const res = (await v2Api.executeNeo4jQuery(neo4jQueryType)) as {
        data?: { results?: unknown[] };
      };
      setNeo4jResults(res.data?.results ?? []);
      toast({ title: "Neo4j query executed" });
    } catch (err) {
      toast({
        title: "Neo4j query failed",
        description: err instanceof Error ? err.message : "Neo4j may not be configured",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleQdrantCollections = async () => {
    setLoading(true);
    try {
      const res = (await v2Api.getQdrantCollections()) as {
        data?: { collections?: string[] };
      };
      setQdrantCollections(res.data?.collections ?? []);
      toast({ title: "Qdrant collections loaded" });
    } catch (err) {
      toast({
        title: "Qdrant request failed",
        description: err instanceof Error ? err.message : "Qdrant may not be configured",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleGetCachedElement = async () => {
    if (!bimElementId) {
      toast({ title: "Enter an element ID", variant: "destructive" });
      return;
    }
    setLoading(true);
    setBimCachedResult(null);
    try {
      const res = (await multiDbApi.getCachedElement(bimElementId)) as {
        data?: unknown;
      };
      setBimCachedResult(res.data ?? null);
      toast({ title: "Cached element retrieved" });
    } catch (err) {
      toast({
        title: "Get cached element failed",
        description: err instanceof Error ? err.message : "Element not found or BIM API unavailable",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFindSimilar = async () => {
    if (!bimElementId) {
      toast({ title: "Enter an element ID", variant: "destructive" });
      return;
    }
    setLoading(true);
    setBimSimilarResults(null);
    try {
      const res = (await multiDbApi.findSimilar({ element_id: bimElementId, top_k: bimTopK })) as {
        data?: { results?: unknown[] };
      };
      setBimSimilarResults(res.data?.results ?? []);
      toast({ title: "Similar elements found" });
    } catch (err) {
      toast({
        title: "Find similar failed",
        description: err instanceof Error ? err.message : "BIM API unavailable",
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
            <Database aria-hidden="true" className="h-5 w-5 text-primary" />
            Database Administration
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Monitor and manage PostgreSQL, Redis, Neo4j, and Qdrant database connections
          </p>
        </div>

        {/* Health Check */}
        <div className="flex items-center gap-3">
          <Button onClick={handleCheckHealth} disabled={loading} variant="outline">
            {loading ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : (
              <Activity aria-hidden="true" className="h-4 w-4" />
            )}
            Refresh All Health
          </Button>
        </div>

        {/* Database Health Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* PostgreSQL */}
          <Card className="border-border bg-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Database aria-hidden="true" className="h-5 w-5 text-primary" />
                {health !== null && (
                  health["postgresql"] !== false ? (
                    <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-success" />
                  ) : (
                    <XCircle aria-hidden="true" className="h-5 w-5 text-danger" />
                  )
                )}
              </div>
              <CardTitle className="text-base text-foreground mt-2">PostgreSQL</CardTitle>
              <CardDescription className="text-muted-foreground">
                Primary relational database
              </CardDescription>
            </CardHeader>
            <CardContent>
              {health === null ? (
                <p className="text-xs text-muted-foreground">Run health check</p>
              ) : (
                <>
                  <Badge
                    variant={health["postgresql"] !== false ? "default" : "destructive"}
                    className="text-xs"
                  >
                    {health["postgresql"] !== false ? "Connected" : "Disconnected"}
                  </Badge>
                  {mainHealth?.database && (
                    <p className="text-xs text-muted-foreground mt-2">
                      DB: {mainHealth.database as string}
                    </p>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* Redis */}
          <Card className="border-border bg-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Server aria-hidden="true" className="h-5 w-5 text-orange-400" />
                {health !== null && (
                  health["redis"] !== false ? (
                    <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-success" />
                  ) : (
                    <XCircle aria-hidden="true" className="h-5 w-5 text-danger" />
                  )
                )}
              </div>
              <CardTitle className="text-base text-foreground mt-2">Redis</CardTitle>
              <CardDescription className="text-muted-foreground">
                Cache & temporary storage
              </CardDescription>
            </CardHeader>
            <CardContent>
              {health === null ? (
                <p className="text-xs text-muted-foreground">Run health check</p>
              ) : (
                <Badge
                  variant={health["redis"] !== false ? "default" : "destructive"}
                  className="text-xs"
                >
                  {health["redis"] !== false ? "Connected" : "Disconnected"}
                </Badge>
              )}
            </CardContent>
          </Card>

          {/* Neo4j */}
          <Card className="border-border bg-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Share2 aria-hidden="true" className="h-5 w-5 text-emerald-400" />
                {health !== null && (
                  health["neo4j"] !== false ? (
                    <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-success" />
                  ) : (
                    <XCircle aria-hidden="true" className="h-5 w-5 text-danger" />
                  )
                )}
              </div>
              <CardTitle className="text-base text-foreground mt-2">Neo4j</CardTitle>
              <CardDescription className="text-muted-foreground">
                Graph database (topology)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {health === null ? (
                <p className="text-xs text-muted-foreground">Run health check</p>
              ) : (
                <Badge
                  variant={health["neo4j"] !== false ? "default" : "destructive"}
                  className="text-xs"
                >
                  {health["neo4j"] !== false ? "Connected" : "Disconnected"}
                </Badge>
              )}
            </CardContent>
          </Card>

          {/* Qdrant */}
          <Card className="border-border bg-card">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <Layers aria-hidden="true" className="h-5 w-5 text-violet-400" />
                {health !== null && (
                  health["qdrant"] !== false ? (
                    <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-success" />
                  ) : (
                    <XCircle aria-hidden="true" className="h-5 w-5 text-danger" />
                  )
                )}
              </div>
              <CardTitle className="text-base text-foreground mt-2">Qdrant</CardTitle>
              <CardDescription className="text-muted-foreground">
                Vector database (embeddings)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {health === null ? (
                <p className="text-xs text-muted-foreground">Run health check</p>
              ) : (
                <Badge
                  variant={health["qdrant"] !== false ? "default" : "destructive"}
                  className="text-xs"
                >
                  {health["qdrant"] !== false ? "Connected" : "Disconnected"}
                </Badge>
              )}
            </CardContent>
          </Card>
        </div>

        <Separator className="bg-border" />

        {/* Database Tools Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-card border border-border">
            <TabsTrigger
              value="redis"
              className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
            >
              <Server aria-hidden="true" className="h-4 w-4 mr-1" />
              Redis
            </TabsTrigger>
            <TabsTrigger
              value="neo4j"
              className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
            >
              <Share2 aria-hidden="true" className="h-4 w-4 mr-1" />
              Neo4j
            </TabsTrigger>
            <TabsTrigger
              value="qdrant"
              className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
            >
              <Layers aria-hidden="true" className="h-4 w-4 mr-1" />
              Qdrant
            </TabsTrigger>
            <TabsTrigger
              value="bim-ops"
              className="data-[state=active]:bg-secondary data-[state=active]:text-foreground"
            >
              <Database aria-hidden="true" className="h-4 w-4 mr-1" />
              BIM Operations
            </TabsTrigger>
          </TabsList>

          {/* Redis Tab */}
          <TabsContent value="redis">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Key aria-hidden="true" className="h-4 w-4 text-primary" />
                    Get Value
                  </CardTitle>
                  <CardDescription>Retrieve a value from Redis by key</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2 mb-3">
                    <Input
                      autoComplete="off"
                      value={redisKey}
                      onChange={(e) => setRedisKey(e.target.value)}
                      placeholder="redis-key-name"
                    />
                    <Button onClick={handleRedisGet} disabled={loading} variant="outline">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <FileSearch aria-hidden="true" className="h-4 w-4" />
                      )}
                      Get
                    </Button>
                  </div>
                  {redisResult !== null && (
                    <div className="p-3 rounded-lg bg-muted/50 border border-border">
                      <span className="text-xs text-muted-foreground block mb-1">Value:</span>
                      <pre className="text-xs font-mono text-foreground whitespace-pre-wrap break-all max-h-32 overflow-auto">
                        {redisResult}
                      </pre>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <RefreshCw aria-hidden="true" className="h-4 w-4 text-primary" />
                    Set Value
                  </CardTitle>
                  <CardDescription>Store a value in Redis with optional TTL</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Input
                      autoComplete="off"
                      value={redisSetKey}
                      onChange={(e) => setRedisSetKey(e.target.value)}
                      placeholder="Key"
                    />
                    <Input
                      autoComplete="off"
                      value={redisSetValue}
                      onChange={(e) => setRedisSetValue(e.target.value)}
                      placeholder="Value"
                    />
                    <div className="flex items-center gap-2">
                      <Input
                        autoComplete="off"
                        type="number"
                        value={redisTtl}
                        onChange={(e) => setRedisTtl(Number(e.target.value))}
                        placeholder="TTL (seconds)"
                        className="w-32"
                      />
                      <span className="text-xs text-muted-foreground">TTL seconds</span>
                    </div>
                    <Button onClick={handleRedisSet} disabled={loading} className="w-full">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Server aria-hidden="true" className="h-4 w-4" />
                      )}
                      Set in Redis
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Neo4j Tab */}
          <TabsContent value="neo4j">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Share2 aria-hidden="true" className="h-4 w-4 text-primary" />
                  Neo4j Graph Queries
                </CardTitle>
                <CardDescription>
                  Execute predefined, read-only Cypher queries against the Neo4j topology graph
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-end gap-3 mb-4">
                  <div className="space-y-1.5 flex-1 max-w-xs">
                    <Label className="text-xs text-muted-foreground">Query Type</Label>
                    <Select value={neo4jQueryType} onValueChange={setNeo4jQueryType}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {NEO4J_QUERIES.map((q) => (
                          <SelectItem key={q.value} value={q.value}>
                            {q.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Button onClick={handleNeo4jQuery} disabled={loading}>
                    {loading ? (
                      <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                    ) : (
                      <Share2 aria-hidden="true" className="h-4 w-4" />
                    )}
                    Execute
                  </Button>
                </div>

                {neo4jResults !== null && (
                  <div className="p-3 rounded-lg bg-muted/50 border border-border">
                    <span className="text-xs text-muted-foreground block mb-2">
                      Results ({neo4jResults.length})
                    </span>
                    <pre className="text-xs font-mono whitespace-pre-wrap text-foreground max-h-48 overflow-auto">
                      {JSON.stringify(neo4jResults, null, 2)}
                    </pre>
                  </div>
                )}

                {neo4jResults === null && (
                  <p className="text-xs text-muted-foreground">
                    Select a query type and click Execute to run
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Qdrant Tab */}
          <TabsContent value="qdrant">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Layers aria-hidden="true" className="h-4 w-4 text-primary" />
                  Qdrant Vector Collections
                </CardTitle>
                <CardDescription>
                  List and monitor Qdrant vector database collections used for semantic search
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button onClick={handleQdrantCollections} disabled={loading} variant="outline">
                  {loading ? (
                    <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw aria-hidden="true" className="h-4 w-4" />
                  )}
                  List Collections
                </Button>

                {qdrantCollections.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <span className="text-xs text-muted-foreground block">
                      {qdrantCollections.length} collection(s)
                    </span>
                    {qdrantCollections.map((name) => (
                      <div
                        key={name}
                        className="flex items-center gap-2 p-2 rounded-lg bg-muted/30 border border-border"
                      >
                        <Layers aria-hidden="true" className="h-4 w-4 text-violet-400 shrink-0" />
                        <span className="text-sm font-mono text-foreground">{name}</span>
                      </div>
                    ))}
                  </div>
                )}

                {qdrantCollections.length === 0 && health && health["qdrant"] !== false && (
                  <p className="text-xs text-muted-foreground mt-4">
                    No collections found. Click "List Collections" to refresh.
                  </p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* BIM Operations Tab */}
          <TabsContent value="bim-ops">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FileSearch aria-hidden="true" className="h-4 w-4 text-primary" />
                    Retrieve Cached Element
                  </CardTitle>
                  <CardDescription>Fetch a cached BIM element from Redis by ID</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2 mb-3">
                    <Input
                      autoComplete="off"
                      value={bimElementId}
                      onChange={(e) => setBimElementId(e.target.value)}
                      placeholder="element-id"
                    />
                    <Button onClick={handleGetCachedElement} disabled={loading} variant="outline">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <FileSearch aria-hidden="true" className="h-4 w-4" />
                      )}
                      Fetch
                    </Button>
                  </div>
                  {bimCachedResult !== null && (
                    <div className="p-3 rounded-lg bg-muted/50 border border-border">
                      <span className="text-xs text-muted-foreground block mb-1">Result:</span>
                      <pre className="text-xs font-mono whitespace-pre-wrap break-all text-foreground max-h-48 overflow-auto">
                        {JSON.stringify(bimCachedResult, null, 2)}
                      </pre>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Search aria-hidden="true" className="h-4 w-4 text-primary" />
                    Find Similar Elements
                  </CardTitle>
                  <CardDescription>Search for similar BIM elements using vector similarity</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2 mb-3">
                    <Input
                      autoComplete="off"
                      value={bimElementId}
                      onChange={(e) => setBimElementId(e.target.value)}
                      placeholder="element-id"
                      className="flex-1"
                    />
                    <Input
                      autoComplete="off"
                      type="number"
                      value={bimTopK}
                      onChange={(e) => setBimTopK(Number(e.target.value))}
                      placeholder="top_k"
                      className="w-20"
                    />
                    <Button onClick={handleFindSimilar} disabled={loading} variant="outline">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Search aria-hidden="true" className="h-4 w-4" />
                      )}
                      Search
                    </Button>
                  </div>
                  {bimSimilarResults !== null && (
                    <div className="p-3 rounded-lg bg-muted/50 border border-border">
                      <span className="text-xs text-muted-foreground block mb-1">
                        Results ({bimSimilarResults.length})
                      </span>
                      <pre className="text-xs font-mono whitespace-pre-wrap break-all text-foreground max-h-48 overflow-auto">
                        {JSON.stringify(bimSimilarResults, null, 2)}
                      </pre>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>
        </Tabs>

        {/* Empty state when no health data */}
        {health === null && neo4jResults === null && qdrantCollections.length === 0 && (
          <Card>
            <CardContent className="py-12">
              <div className="flex flex-col items-center text-center">
                <Database
                  aria-hidden="true"
                  className="h-12 w-12 text-muted-foreground/40 mb-4"
                />
                <p className="text-muted-foreground font-medium">
                  Database Administration
                </p>
                <p className="text-sm text-muted-foreground/60 mt-1">
                  Click "Refresh All Health" to check connection status for all databases
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
