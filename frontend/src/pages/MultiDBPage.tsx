/**
 * MultiDBPage.tsx — Multi-Database Administration Dashboard
 *
 * V273: Full UI for the backend /multi-db router covering:
 *   - PostgreSQL, Redis, Neo4j, Qdrant health monitoring
 *   - Redis key/value GET and SET operations
 *   - BIM element caching (cache + retrieve)
 *   - Qdrant embeddings storage and vector similarity search
 *   - Neo4j graph queries and relationship management
 *   - Qdrant collection listing
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
  Upload,
  XCircle,
  Zap,
  GitBranch,
  Link2,
  Unlink,
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

interface DbHealth {
  [key: string]: boolean;
}

const NEO4J_QUERIES = [
  { value: "get_element_count", label: "Element Count" },
  { value: "get_element_by_id", label: "Element by ID" },
  { value: "get_relationships", label: "All Relationships (limit 100)" },
];

const RELATIONSHIP_TYPES = [
  { value: "CONNECTED_TO", label: "Connected To" },
  { value: "CONTAINS", label: "Contains" },
  { value: "FEEDS", label: "Feeds" },
  { value: "PROTECTS", label: "Protects" },
  { value: "MONITORS", label: "Monitors" },
];

const VECTOR_DIMENSIONS = 128;

export function MultiDBPage() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("health");
  const [health, setHealth] = useState<DbHealth | null>(null);

  // Redis
  const [redisKey, setRedisKey] = useState("");
  const [redisResult, setRedisResult] = useState<string | null>(null);
  const [redisSetKey, setRedisSetKey] = useState("");
  const [redisSetValue, setRedisSetValue] = useState("");
  const [redisTtl, setRedisTtl] = useState(300);

  // BIM Cache
  const [cacheElementId, setCacheElementId] = useState("");
  const [cacheElementJson, setCacheElementJson] = useState("{\n  \n}");
  const [cacheResult, setCacheResult] = useState<string | null>(null);
  const [retrieveElementId, setRetrieveElementId] = useState("");
  const [retrievedData, setRetrievedData] = useState<string | null>(null);

  // Embeddings
  const [embedElementId, setEmbedElementId] = useState("");
  const [embedResult, setEmbedResult] = useState<string | null>(null);
  const [simElementId, setSimElementId] = useState("");
  const [simLimit, setSimLimit] = useState(5);
  const [simResults, setSimResults] = useState<string | null>(null);

  // Neo4j
  const [neo4jQueryType, setNeo4jQueryType] = useState("get_element_count");
  const [neo4jResults, setNeo4jResults] = useState<unknown[] | null>(null);
  const [relElementId, setRelElementId] = useState("");
  const [relTargetIds, setRelTargetIds] = useState("");
  const [relType, setRelType] = useState("CONNECTED_TO");
  const [relResult, setRelResult] = useState<string | null>(null);
  const [relFindElementId, setRelFindElementId] = useState("");
  const [relFindType, setRelFindType] = useState("CONNECTED_TO");
  const [relFindResult, setRelFindResult] = useState<string | null>(null);

  // Qdrant
  const [qdrantCollections, setQdrantCollections] = useState<string[]>([]);

  const handleCheckHealth = async () => {
    setLoading(true);
    try {
      const res = await v2Api.getMultiDbHealth();
      const data = (res as { data?: DbHealth }).data || {};
      setHealth(data);
      const allHealthy = Object.values(data).every(Boolean);
      toast({
        title: "Health check complete",
        description: allHealthy ? "All databases connected" : "Some databases are offline",
      });
    } catch (err) {
      toast({
        title: "Health check failed",
        description: err instanceof Error ? err.message : "Multi-db endpoint unavailable",
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
      const val = res.data?.value ?? "(empty)";
      setRedisResult(val);
      toast({ title: "Redis get complete" });
    } catch {
      setRedisResult("(key not found or Redis unavailable)");
      toast({ title: "Key not found in Redis", variant: "destructive" });
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
      toast({ title: "Redis set complete", description: `Key: ${redisSetKey} (TTL: ${redisTtl}s)` });
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

  const handleCacheBimElement = async () => {
    if (!cacheElementId) {
      toast({ title: "Element ID is required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      let elementData: Record<string, unknown>;
      try {
        elementData = JSON.parse(cacheElementJson);
      } catch {
        toast({ title: "Invalid JSON in element data", variant: "destructive" });
        setLoading(false);
        return;
      }
      await v2Api.cacheBimElement(cacheElementId, elementData);
      setCacheResult(`Element "${cacheElementId}" cached successfully`);
      toast({ title: "BIM element cached" });
    } catch (err) {
      setCacheResult(null);
      toast({
        title: "Cache failed",
        description: err instanceof Error ? err.message : "Failed",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleGetCachedBimElement = async () => {
    if (!retrieveElementId) {
      toast({ title: "Element ID is required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = await v2Api.getCachedBimElement(retrieveElementId);
      setRetrievedData(JSON.stringify(res, null, 2));
      toast({ title: "Cached element retrieved" });
    } catch {
      setRetrievedData("(element not found in cache)");
      toast({ title: "Element not found in cache", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const handleStoreEmbeddings = async () => {
    if (!embedElementId) {
      toast({ title: "Element ID is required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      // Generate a simple dummy embedding for demonstration
      const embedding = Array.from({ length: VECTOR_DIMENSIONS }, () => Math.random());
      await v2Api.storeElementEmbeddings(embedElementId, embedding);
      setEmbedResult(`Embeddings stored for element "${embedElementId}" (${VECTOR_DIMENSIONS} dimensions)`);
      toast({ title: "Embeddings stored in Qdrant" });
    } catch (err) {
      setEmbedResult(null);
      toast({
        title: "Store failed",
        description: err instanceof Error ? err.message : "Failed",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFindSimilar = async () => {
    if (!simElementId) {
      toast({ title: "Element ID is required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const embedding = Array.from({ length: VECTOR_DIMENSIONS }, () => Math.random());
      const res = (await v2Api.findSimilarElements(embedding, simLimit)) as {
        data?: { results?: unknown[] };
      };
      setSimResults(JSON.stringify(res.data?.results ?? [], null, 2));
      toast({ title: "Similar search complete" });
    } catch (err) {
      setSimResults(null);
      toast({
        title: "Similar search failed",
        description: err instanceof Error ? err.message : "Qdrant may not be configured",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleNeo4jQuery = async () => {
    setLoading(true);
    try {
      const params = neo4jQueryType === "get_element_by_id" && simElementId
        ? JSON.stringify({ element_id: simElementId })
        : undefined;
      const res = (await v2Api.executeNeo4jQuery(neo4jQueryType, params)) as {
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

  const handleCreateRelationships = async () => {
    if (!relElementId || !relTargetIds) {
      toast({ title: "Element ID and related IDs are required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const targets = relTargetIds.split(",").map((s) => s.trim()).filter(Boolean);
      await v2Api.createElementRelationships(relElementId, targets, relType);
      setRelResult(`Created ${targets.length} "${relType}" relationships from "${relElementId}"`);
      toast({ title: "Relationships created in Neo4j" });
    } catch (err) {
      setRelResult(null);
      toast({
        title: "Relationship creation failed",
        description: err instanceof Error ? err.message : "Neo4j may not be configured",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleFindRelated = async () => {
    if (!relFindElementId) {
      toast({ title: "Element ID is required", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = await v2Api.findRelatedElements(relFindElementId, relFindType);
      setRelFindResult(JSON.stringify(res, null, 2));
      toast({ title: "Related elements retrieved" });
    } catch (err) {
      setRelFindResult(null);
      toast({
        title: "Find related failed",
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

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
              <Database aria-hidden="true" className="h-5 w-5 text-primary" />
              Multi-Database Administration
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Manage PostgreSQL, Redis, Neo4j (graph), and Qdrant (vector) — health, cache, embeddings, and topology
            </p>
          </div>
          <Button onClick={handleCheckHealth} disabled={loading} variant="outline">
            {loading ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : (
              <Activity aria-hidden="true" className="h-4 w-4" />
            )}
            Check All Health
          </Button>
        </div>

        {/* Database Health Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { key: "postgresql", label: "PostgreSQL", desc: "Primary relational database", icon: Database, color: "text-primary" },
            { key: "redis", label: "Redis", desc: "Cache & temporary storage", icon: Server, color: "text-orange-400" },
            { key: "neo4j", label: "Neo4j", desc: "Graph database (topology)", icon: Share2, color: "text-emerald-400" },
            { key: "qdrant", label: "Qdrant", desc: "Vector database (embeddings)", icon: Layers, color: "text-violet-400" },
          ].map((db) => {
            const Icon = db.icon;
            const isHealthy = health?.[db.key] !== false;
            return (
              <Card key={db.key} className="border-border bg-card">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <Icon aria-hidden="true" className={`h-5 w-5 ${db.color}`} />
                    {health !== null && (
                      isHealthy ? (
                        <CheckCircle2 aria-hidden="true" className="h-5 w-5 text-success" />
                      ) : (
                        <XCircle aria-hidden="true" className="h-5 w-5 text-danger" />
                      )
                    )}
                  </div>
                  <CardTitle className="text-base text-foreground mt-2">{db.label}</CardTitle>
                  <CardDescription className="text-muted-foreground">{db.desc}</CardDescription>
                </CardHeader>
                <CardContent>
                  {health === null ? (
                    <p className="text-xs text-muted-foreground">Run health check</p>
                  ) : (
                    <Badge variant={isHealthy ? "default" : "destructive"} className="text-xs">
                      {isHealthy ? "Connected" : "Disconnected"}
                    </Badge>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>

        <Separator className="bg-border" />

        {/* Database Tools Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="bg-card border border-border flex-wrap">
            <TabsTrigger value="health" className="data-[state=active]:bg-secondary data-[state=active]:text-foreground">
              <Activity aria-hidden="true" className="h-4 w-4 mr-1" />
              Health
            </TabsTrigger>
            <TabsTrigger value="redis" className="data-[state=active]:bg-secondary data-[state=active]:text-foreground">
              <Server aria-hidden="true" className="h-4 w-4 mr-1" />
              Redis
            </TabsTrigger>
            <TabsTrigger value="bim-cache" className="data-[state=active]:bg-secondary data-[state=active]:text-foreground">
              <Database aria-hidden="true" className="h-4 w-4 mr-1" />
              BIM Cache
            </TabsTrigger>
            <TabsTrigger value="embeddings" className="data-[state=active]:bg-secondary data-[state=active]:text-foreground">
              <Layers aria-hidden="true" className="h-4 w-4 mr-1" />
              Embeddings
            </TabsTrigger>
            <TabsTrigger value="neo4j" className="data-[state=active]:bg-secondary data-[state=active]:text-foreground">
              <Share2 aria-hidden="true" className="h-4 w-4 mr-1" />
              Neo4j Graph
            </TabsTrigger>
            <TabsTrigger value="qdrant" className="data-[state=active]:bg-secondary data-[state=active]:text-foreground">
              <Layers aria-hidden="true" className="h-4 w-4 mr-1" />
              Qdrant
            </TabsTrigger>
          </TabsList>

          {/* Health Tab */}
          <TabsContent value="health">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity aria-hidden="true" className="h-4 w-4 text-primary" />
                  Database Health Overview
                </CardTitle>
                <CardDescription>
                  Click "Check All Health" above to verify all database connections
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-muted/30 border border-border">
                    <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                      <Zap aria-hidden="true" className="h-4 w-4 text-primary" />
                      Connection Summary
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {health === null
                        ? "No health data yet. Run a health check to see connection status."
                        : `${Object.values(health).filter(Boolean).length}/${Object.keys(health).length} databases connected`}
                    </p>
                  </div>
                  <div className="p-4 rounded-lg bg-muted/30 border border-border">
                    <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                      <Database aria-hidden="true" className="h-4 w-4 text-primary" />
                      Available Operations
                    </h3>
                    <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                      <li>Redis key/value GET/SET with optional TTL</li>
                      <li>BIM element caching in Redis</li>
                      <li>Qdrant vector embeddings store & search</li>
                      <li>Neo4j graph queries & relationship management</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Redis Tab */}
          <TabsContent value="redis">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FileSearch aria-hidden="true" className="h-4 w-4 text-primary" />
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
                      onKeyDown={(e) => e.key === "Enter" && handleRedisGet()}
                    />
                    <Button onClick={handleRedisGet} disabled={loading} variant="outline">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Key aria-hidden="true" className="h-4 w-4" />
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
                    <Upload aria-hidden="true" className="h-4 w-4 text-primary" />
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

          {/* BIM Cache Tab */}
          <TabsContent value="bim-cache">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Database aria-hidden="true" className="h-4 w-4 text-primary" />
                    Cache BIM Element
                  </CardTitle>
                  <CardDescription>
                    Store BIM element data in Redis for faster access
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <Input
                      autoComplete="off"
                      value={cacheElementId}
                      onChange={(e) => setCacheElementId(e.target.value)}
                      placeholder="Element ID (e.g. wall-001)"
                    />
                    <div>
                      <Label className="text-xs text-muted-foreground mb-1 block">Element Data (JSON)</Label>
                      <textarea
                        className="w-full h-28 px-3 py-2 rounded-lg border border-border bg-background text-xs font-mono text-foreground resize-y"
                        value={cacheElementJson}
                        onChange={(e) => setCacheElementJson(e.target.value)}
                        placeholder='{"type": "wall", "length_m": 5.0, "height_m": 3.0}'
                      />
                    </div>
                    <Button onClick={handleCacheBimElement} disabled={loading} className="w-full">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Database aria-hidden="true" className="h-4 w-4" />
                      )}
                      Cache Element
                    </Button>
                    {cacheResult && (
                      <p className="text-xs text-emerald-600 mt-2">{cacheResult}</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <FileSearch aria-hidden="true" className="h-4 w-4 text-primary" />
                    Retrieve Cached Element
                  </CardTitle>
                  <CardDescription>
                    Get cached BIM element data from Redis
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex gap-2 mb-3">
                    <Input
                      autoComplete="off"
                      value={retrieveElementId}
                      onChange={(e) => setRetrieveElementId(e.target.value)}
                      placeholder="Element ID to retrieve"
                      onKeyDown={(e) => e.key === "Enter" && handleGetCachedBimElement()}
                    />
                    <Button onClick={handleGetCachedBimElement} disabled={loading} variant="outline">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Search aria-hidden="true" className="h-4 w-4" />
                      )}
                      Get
                    </Button>
                  </div>
                  {retrievedData !== null && (
                    <div className="p-3 rounded-lg bg-muted/50 border border-border">
                      <span className="text-xs text-muted-foreground block mb-1">Cached Data:</span>
                      <pre className="text-xs font-mono text-foreground whitespace-pre-wrap break-all max-h-48 overflow-auto">
                        {retrievedData}
                      </pre>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Embeddings Tab */}
          <TabsContent value="embeddings">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Upload aria-hidden="true" className="h-4 w-4 text-primary" />
                    Store Embeddings
                  </CardTitle>
                  <CardDescription>
                    Store element embeddings in Qdrant for similarity search (±{VECTOR_DIMENSIONS} dims)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <Input
                      autoComplete="off"
                      value={embedElementId}
                      onChange={(e) => setEmbedElementId(e.target.value)}
                      placeholder="Element ID (e.g. door-042)"
                    />
                    <Button onClick={handleStoreEmbeddings} disabled={loading} className="w-full">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Layers aria-hidden="true" className="h-4 w-4" />
                      )}
                      Generate & Store Embedding
                    </Button>
                    {embedResult && (
                      <p className="text-xs text-emerald-600 mt-2">{embedResult}</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Search aria-hidden="true" className="h-4 w-4 text-primary" />
                    Find Similar Elements
                  </CardTitle>
                  <CardDescription>
                    Search for similar BIM elements using vector similarity
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <div className="flex gap-2">
                      <Input
                        autoComplete="off"
                        value={simElementId}
                        onChange={(e) => setSimElementId(e.target.value)}
                        placeholder="Reference element ID"
                        className="flex-1"
                      />
                      <Input
                        autoComplete="off"
                        type="number"
                        value={simLimit}
                        onChange={(e) => setSimLimit(Number(e.target.value))}
                        placeholder="Limit"
                        className="w-20"
                        min={1}
                        max={20}
                      />
                    </div>
                    <Button onClick={handleFindSimilar} disabled={loading} className="w-full">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Search aria-hidden="true" className="h-4 w-4" />
                      )}
                      Search Similar
                    </Button>
                    {simResults !== null && (
                      <div className="p-3 rounded-lg bg-muted/50 border border-border">
                        <span className="text-xs text-muted-foreground block mb-1">Similar Elements:</span>
                        <pre className="text-xs font-mono text-foreground whitespace-pre-wrap max-h-48 overflow-auto">
                          {simResults}
                        </pre>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Neo4j Tab */}
          <TabsContent value="neo4j">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Queries */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Share2 aria-hidden="true" className="h-4 w-4 text-primary" />
                    Graph Queries
                  </CardTitle>
                  <CardDescription>
                    Execute predefined, read-only Cypher queries against Neo4j
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
                            <SelectItem key={q.value} value={q.value}>{q.label}</SelectItem>
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
                  {neo4jQueryType === "get_element_by_id" && (
                    <Input
                      autoComplete="off"
                      value={simElementId}
                      onChange={(e) => setSimElementId(e.target.value)}
                      placeholder="Element ID for lookup"
                      className="mb-3"
                    />
                  )}
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
                    <p className="text-xs text-muted-foreground">Select a query type and click Execute</p>
                  )}
                </CardContent>
              </Card>

              {/* Relationships */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <GitBranch aria-hidden="true" className="h-4 w-4 text-primary" />
                    Create Relationships
                  </CardTitle>
                  <CardDescription>
                    Connect elements in the Neo4j topology graph
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    <Input
                      autoComplete="off"
                      value={relElementId}
                      onChange={(e) => setRelElementId(e.target.value)}
                      placeholder="Source element ID"
                    />
                    <Input
                      autoComplete="off"
                      value={relTargetIds}
                      onChange={(e) => setRelTargetIds(e.target.value)}
                      placeholder="Target element IDs (comma-separated)"
                    />
                    <Select value={relType} onValueChange={setRelType}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {RELATIONSHIP_TYPES.map((rt) => (
                          <SelectItem key={rt.value} value={rt.value}>{rt.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button onClick={handleCreateRelationships} disabled={loading} className="w-full">
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Link2 aria-hidden="true" className="h-4 w-4" />
                      )}
                      Create Relationships
                    </Button>
                    {relResult && (
                      <p className="text-xs text-emerald-600 mt-1">{relResult}</p>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Find Related */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Unlink aria-hidden="true" className="h-4 w-4 text-primary" />
                    Find Related Elements
                  </CardTitle>
                  <CardDescription>
                    Discover elements connected to a specific element in the graph
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap items-end gap-3 mb-4">
                    <div className="space-y-1.5 flex-1 min-w-[200px]">
                      <Label className="text-xs text-muted-foreground">Element ID</Label>
                      <Input
                        autoComplete="off"
                        value={relFindElementId}
                        onChange={(e) => setRelFindElementId(e.target.value)}
                        placeholder="Element ID to find relations for"
                      />
                    </div>
                    <div className="space-y-1.5 w-48">
                      <Label className="text-xs text-muted-foreground">Relationship Type</Label>
                      <Select value={relFindType} onValueChange={setRelFindType}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {RELATIONSHIP_TYPES.map((rt) => (
                            <SelectItem key={rt.value} value={rt.value}>{rt.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <Button onClick={handleFindRelated} disabled={loading}>
                      {loading ? (
                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                      ) : (
                        <Search aria-hidden="true" className="h-4 w-4" />
                      )}
                      Find Related
                    </Button>
                  </div>
                  {relFindResult !== null && (
                    <div className="p-3 rounded-lg bg-muted/50 border border-border">
                      <span className="text-xs text-muted-foreground block mb-1">Related Elements:</span>
                      <pre className="text-xs font-mono text-foreground whitespace-pre-wrap max-h-48 overflow-auto">
                        {relFindResult}
                      </pre>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
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
                  List and monitor Qdrant vector database collections used for semantic search and element embeddings
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

                {health && health["qdrant"] === false && (
                  <div className="mt-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30">
                    <p className="text-xs text-amber-600">
                      Qdrant is not connected. Configure Qdrant connection in settings or check the service status.
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* Empty state */}
        {health === null && neo4jResults === null && qdrantCollections.length === 0 && (
          <Card>
            <CardContent className="py-12">
              <div className="flex flex-col items-center text-center">
                <Database aria-hidden="true" className="h-12 w-12 text-muted-foreground/40 mb-4" />
                <p className="text-muted-foreground font-medium">Multi-Database Administration</p>
                <p className="text-sm text-muted-foreground/60 mt-1">
                  Click "Check All Health" to verify connections, then explore each tab for database-specific operations
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
