/**
 * MonitorPage.tsx — System monitoring dashboard.
 *
 * V217: New page — 6 backend endpoints now have UI.
 * Health, metrics, engine status, agent activity, security alerts.
 *
 * V235: Real-time streaming via useWebSocketStream.
 * When the backend sends sequenced WebSocket messages on the "monitor" channel,
 * they are batched (50ms), validated by monotonic sequence lock, and applied
 * to the corresponding state slices. REST buttons remain as fallback
 * (stale-while-revalidate pattern).
 */
import { useCallback, useState } from "react";
import { Activity, AlertCircle, Clock, Cpu, Loader2, ShieldAlert, Bell, Wifi, WifiOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
        Card,
        CardContent,
        CardDescription,
        CardHeader,
        CardTitle,
} from "@/components/ui/card";
import { monitorApi } from "@/services/fullApi";
import { useToast } from "@/hooks/use-toast";
import { useWebSocketStream, type StreamMessage } from "@/hooks/useWebSocketStream";

/**
 * Derive the WebSocket URL from VITE_WS_URL or VITE_API_URL.
 * Mirrors the pattern used in dataService.ts and digitalTwinApi.ts.
 */
function getMonitorWsUrl(): string {
        const envWs = import.meta.env.VITE_WS_URL;
        if (envWs) return envWs;
        const apiBase = import.meta.env.VITE_API_URL || "/api/v1";
        // Replace http(s) with ws(s) and /api prefix with /ws
        return apiBase.replace(/^http/, "ws").replace(/\/api\/v\d+/, "/ws") + "/monitor";
}

export function MonitorPage() {
        const { toast } = useToast();
        const [loading, setLoading] = useState(false);
        const [health, setHealth] = useState<Record<string, unknown> | null>(null);
        const [engineStatus, setEngineStatus] = useState<Record<string, unknown> | null>(null);
        const [agentActivity, setAgentActivity] = useState<unknown[]>([]);
        const [securityAlerts, setSecurityAlerts] = useState<unknown[]>([]);
        const [metrics, setMetrics] = useState<string>("");
        const [alerts, setAlerts] = useState<unknown[]>([]);
        const [uptime, setUptime] = useState<Record<string, unknown> | null>(null);

        // ---- REST handlers (defined first so gap-resync can reference them) ----
        const handleHealth = async () => {
                setLoading(true);
                try {
                        const res = await monitorApi.getHealth();
                        setHealth(res as Record<string, unknown>);
                } catch (err) {
                        toast({
                                title: "Failed",
                                description: err instanceof Error ? err.message : "Failed",
                                variant: "destructive",
                        });
                } finally {
                        setLoading(false);
                }
        };

        const handleEngineStatus = async () => {
                setLoading(true);
                try {
                        const res = await monitorApi.getEngineStatus();
                        setEngineStatus(res as Record<string, unknown>);
                } catch (err) {
                        toast({
                                title: "Failed",
                                description: err instanceof Error ? err.message : "Failed",
                                variant: "destructive",
                        });
                } finally {
                        setLoading(false);
                }
        };

        // ---- Real-time WebSocket streaming ----
        // Batch handler: routes sequenced messages to the correct state slice
        // based on the message `type` field from the backend.
        const handleStreamBatch = useCallback((messages: StreamMessage[]) => {
                for (const msg of messages) {
                        switch (msg.type) {
                                case "health":
                                        setHealth(msg.data as Record<string, unknown>);
                                        break;
                                case "engine_status":
                                        setEngineStatus(msg.data as Record<string, unknown>);
                                        break;
                                case "agent_activity": {
                                        const activities = (msg.data as { activities?: unknown[] }).activities;
                                        if (activities) setAgentActivity(activities);
                                        break;
                                }
                                case "security_alerts": {
                                        const newAlerts = (msg.data as { alerts?: unknown[] }).alerts;
                                        if (newAlerts) setSecurityAlerts(newAlerts);
                                        break;
                                }
                                case "metrics":
                                        setMetrics(msg.data as string);
                                        break;
                                case "alerts": {
                                        const sysAlerts = (msg.data as { alerts?: unknown[] }).alerts;
                                        if (sysAlerts) setAlerts(sysAlerts);
                                        break;
                                }
                                case "uptime":
                                        setUptime(msg.data as Record<string, unknown>);
                                        break;
                                default:
                                        // Unknown message type — ignore gracefully
                                        break;
                        }
                }
        }, []);

        const handleStreamGap = useCallback(() => {
                // On gap detection, trigger a full REST resync (stale-while-revalidate)
                void handleHealth();
                void handleEngineStatus();
        // eslint-disable-next-line react-hooks/exhaustive-deps -- handleHealth/handleEngineStatus are stable async fns
        }, []);

        const { connected: wsConnected, discardedCount } = useWebSocketStream({
                url: getMonitorWsUrl(),
                onBatch: handleStreamBatch,
                onGap: handleStreamGap,
                onError: () => {
                        /* REST fallback remains available — no toast spam on WS failure */
                },
        });

        const handleAgentActivity = async () => {
                setLoading(true);
                try {
                        const res = await monitorApi.getAgentActivity({ limit: 20 });
                        setAgentActivity((res as { activities?: unknown[] }).activities || []);
                } catch (err) {
                        toast({
                                title: "Failed",
                                description: err instanceof Error ? err.message : "Failed",
                                variant: "destructive",
                        });
                } finally {
                        setLoading(false);
                }
        };

        const handleSecurityAlerts = async () => {
                setLoading(true);
                try {
                        const res = await monitorApi.getSecurityAlerts({ limit: 20 });
                        setSecurityAlerts((res as { alerts?: unknown[] }).alerts || []);
                } catch (err) {
                        toast({
                                title: "Failed",
                                description: err instanceof Error ? err.message : "Failed",
                                variant: "destructive",
                        });
                } finally {
                        setLoading(false);
                }
        };

        const handleMetrics = async () => {
                setLoading(true);
                try {
                        const res = await monitorApi.getMetrics();
                        setMetrics(res as string);
                } catch (err) {
                        toast({
                                title: "Failed",
                                description: err instanceof Error ? err.message : "Failed",
                                variant: "destructive",
                        });
                } finally {
                        setLoading(false);
                }
        };

        const handleAlerts = async () => {
                setLoading(true);
                try {
                        const res = await monitorApi.getAlerts({ limit: 20 });
                        setAlerts((res as { alerts?: unknown[] }).alerts || []);
                } catch (err) {
                        toast({
                                title: "Failed",
                                description: err instanceof Error ? err.message : "Failed",
                                variant: "destructive",
                        });
                } finally {
                        setLoading(false);
                }
        };

        const handleUptime = async () => {
                setLoading(true);
                try {
                        const res = await monitorApi.getUptime();
                        setUptime(res as Record<string, unknown>);
                } catch (err) {
                        toast({
                                title: "Failed",
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
                                <div className="flex items-center justify-between">
                                        <div>
                                                <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                                                        <Activity aria-hidden="true" className="h-5 w-5 text-primary" />
                                                        System Monitor
                                                </h1>
                                                <p className="text-sm text-muted-foreground mt-1">
                                                        Engine health · Agent activity · Security alerts · Prometheus metrics
                                                </p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                                {wsConnected ? (
                                                        <Badge variant="default" className="gap-1">
                                                                <Wifi aria-hidden="true" className="h-3 w-3" />
                                                                Live
                                                        </Badge>
                                                ) : (
                                                        <Badge variant="secondary" className="gap-1">
                                                                <WifiOff aria-hidden="true" className="h-3 w-3" />
                                                                Offline
                                                        </Badge>
                                                )}
                                                {discardedCount > 0 && (
                                                        <Badge variant="outline" className="text-xs">
                                                                {discardedCount} discarded
                                                        </Badge>
                                                )}
                                        </div>
                                </div>

                                {/* Quick Actions */}
                                <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
                                        <Button onClick={handleHealth} disabled={loading} variant="outline">
                                                {loading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Activity aria-hidden="true" className="h-4 w-4" />}
                                                Health
                                        </Button>
                                        <Button onClick={handleEngineStatus} disabled={loading} variant="outline">
                                                {loading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Cpu aria-hidden="true" className="h-4 w-4" />}
                                                Engine Status
                                        </Button>
                                        <Button onClick={handleAgentActivity} disabled={loading} variant="outline">
                                                {loading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Activity aria-hidden="true" className="h-4 w-4" />}
                                                Agent Activity
                                        </Button>
                                        <Button onClick={handleSecurityAlerts} disabled={loading} variant="outline">
                                                {loading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <ShieldAlert aria-hidden="true" className="h-4 w-4" />}
                                                Security Alerts
                                        </Button>
                                        <Button onClick={handleMetrics} disabled={loading} variant="outline">
                                                {loading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Activity aria-hidden="true" className="h-4 w-4" />}
                                                Prometheus
                                        </Button>
                                        <Button onClick={handleAlerts} disabled={loading} variant="outline">
                                                {loading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Bell aria-hidden="true" className="h-4 w-4" />}
                                                Alerts
                                        </Button>
                                        <Button onClick={handleUptime} disabled={loading} variant="outline">
                                                {loading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Clock aria-hidden="true" className="h-4 w-4" />}
                                                Uptime
                                        </Button>
                                </div>

                                {/* Health Status */}
                                {health && (
                                        <Card>
                                                <CardHeader>
                                                        <CardTitle className="flex items-center gap-2">
                                                                <Activity aria-hidden="true" className="h-4 w-4 text-success" />
                                                                System Health
                                                        </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                                                {Object.entries(health).map(([key, val]) => (
                                                                        <div key={key} className="space-y-1">
                                                                                <span className="text-xs text-muted-foreground uppercase tracking-wider">
                                                                                        {key}
                                                                                </span>
                                                                                <div className="text-sm font-mono text-foreground">
                                                                                        {typeof val === "boolean" ? (
                                                                                                <Badge variant={val ? "default" : "destructive"}>
                                                                                                        {val ? "OK" : "FAIL"}
                                                                                                </Badge>
                                                                                        ) : (
                                                                                                String(val)
                                                                                        )}
                                                                                </div>
                                                                        </div>
                                                                ))}
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Engine Status */}
                                {engineStatus && (
                                        <Card>
                                                <CardHeader>
                                                        <CardTitle className="flex items-center gap-2">
                                                                <Cpu aria-hidden="true" className="h-4 w-4 text-primary" />
                                                                Engine Status
                                                        </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                        <pre className="text-xs font-mono bg-muted p-3 rounded-md overflow-auto max-h-48">
                                                                {JSON.stringify(engineStatus, null, 2)}
                                                        </pre>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Agent Activity */}
                                {agentActivity.length > 0 && (
                                        <Card>
                                                <CardHeader>
                                                        <CardTitle>Agent Activity ({agentActivity.length})</CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                        <div className="space-y-2 max-h-60 overflow-auto">
                                                                {agentActivity.map((a, i) => {
                                                                        const activity = a as { timestamp: string; agent: string; action: string; status: string };
                                                                        return (
                                                                                <div
                                                                                        key={i}  // NOSONAR: typescript:S6479
                                                                                        className="flex items-center justify-between text-sm border-b border-border pb-2"
                                                                                >
                                                                                        <span className="font-mono text-xs text-muted-foreground">
                                                                                                {activity.timestamp}
                                                                                        </span>
                                                                                        <span className="text-foreground">{activity.agent}</span>
                                                                                        <span className="text-muted-foreground">{activity.action}</span>
                                                                                        <Badge
                                                                                                variant={
                                                                                                        activity.status === "success"
                                                                                                                ? "default"
                                                                                                                : activity.status === "error"  // NOSONAR: typescript:S3358
                                                                                                                        ? "destructive"
                                                                                                                        : "secondary"
                                                                                                }
                                                                                        >
                                                                                                {activity.status}
                                                                                        </Badge>
                                                                                </div>
                                                                        );
                                                                })}
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Security Alerts */}
                                {securityAlerts.length > 0 && (
                                        <Card>
                                                <CardHeader>
                                                        <CardTitle className="flex items-center gap-2">
                                                                <ShieldAlert aria-hidden="true" className="h-4 w-4 text-warning" />
                                                                Security Alerts ({securityAlerts.length})
                                                        </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                        <div className="space-y-2 max-h-60 overflow-auto">
                                                                {securityAlerts.map((a, i) => {
                                                                        const alert = a as {
                                                                                timestamp: string;
                                                                                severity: string;
                                                                                type: string;
                                                                                message: string;
                                                                        };
                                                                        return (
                                                                                <div
                                                                                        key={i}  // NOSONAR: typescript:S6479
                                                                                        className="flex items-center gap-3 text-sm border-b border-border pb-2"
                                                                                >
                                                                                        <AlertCircle aria-hidden="true"
                                                                                                className={`h-4 w-4 shrink-0 ${
                                                                                                        alert.severity === "critical"
                                                                                                                ? "text-danger"
                                                                                                                : alert.severity === "high"  // NOSONAR: typescript:S3358
                                                                                                                        ? "text-warning"
                                                                                                                        : "text-muted-foreground"
                                                                                                }`}
                                                                                        />
                                                                                        <span className="font-mono text-xs text-muted-foreground">
                                                                                                {alert.timestamp}
                                                                                        </span>
                                                                                        <span className="text-foreground flex-1">{alert.message}</span>
                                                                                        <Badge variant="outline" className="text-xs">
                                                                                                {alert.type}
                                                                                        </Badge>
                                                                                </div>
                                                                        );
                                                                })}
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Prometheus Metrics */}
                                {metrics && (
                                        <Card>
                                                <CardHeader>
                                                        <CardTitle>Prometheus Metrics</CardTitle>
                                                        <CardDescription>Raw /metrics endpoint output</CardDescription>
                                                </CardHeader>
                                                <CardContent>
                                                        <pre className="text-xs font-mono bg-muted p-3 rounded-md overflow-auto max-h-96 whitespace-pre-wrap">
                                                                {metrics}
                                                        </pre>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* System Alerts */}
                                {alerts.length > 0 && (
                                        <Card>
                                                <CardHeader>
                                                        <CardTitle className="flex items-center gap-2">
                                                                <Bell aria-hidden="true" className="h-4 w-4 text-warning" />
                                                                System Alerts ({alerts.length})
                                                        </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                        <div className="space-y-2 max-h-60 overflow-auto">
                                                                {alerts.map((a, i) => {
                                                                        const alrt = a as { timestamp: string; severity: string; type: string; message: string };
                                                                        return (
                                                                                <div key={i} className="flex items-center gap-3 text-sm border-b border-border pb-2">
                                                                                        <AlertCircle aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
                                                                                        <span className="font-mono text-xs text-muted-foreground">{alrt.timestamp}</span>
                                                                                        <span className="text-foreground flex-1">{alrt.message}</span>
                                                                                        <Badge variant="outline" className="text-xs">{alrt.type}</Badge>
                                                                                </div>
                                                                        );
                                                                })}
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Uptime */}
                                {uptime && (
                                        <Card>
                                                <CardHeader>
                                                        <CardTitle className="flex items-center gap-2">
                                                                <Clock aria-hidden="true" className="h-4 w-4 text-primary" />
                                                                Uptime Statistics
                                                        </CardTitle>
                                                </CardHeader>
                                                <CardContent>
                                                        <pre className="text-xs font-mono bg-muted p-3 rounded-md overflow-auto max-h-48">
                                                                {JSON.stringify(uptime, null, 2)}
                                                        </pre>
                                                </CardContent>
                                        </Card>
                                )}
                        </div>
                </div>
        );
}
