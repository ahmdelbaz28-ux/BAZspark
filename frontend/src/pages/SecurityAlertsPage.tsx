/**
 * SecurityAlertsPage.tsx — Security alerts monitoring dashboard.
 *
 * Displays active and historical security alerts fetched from
 * GET /api/v1/monitor/security-alerts.
 */
import React, { useCallback, useEffect, useState } from "react";
import { BellRing, Loader2, RefreshCw, AlertTriangle, Shield, Filter } from "lucide-react";

interface SecurityAlert {
  id: string;
  timestamp: string;
  severity: "critical" | "high" | "medium" | "low";
  title: string;
  message: string;
  source?: string;
  acknowledged?: boolean;
}

interface AlertsResponse {
  alerts?: SecurityAlert[];
  total?: number;
  critical_count?: number;
  high_count?: number;
}

// Fallback sample data when backend is unavailable.
// Extracted to module scope so it is hoisted above any reference inside the
// component (react-hooks/immutability: cannot access a variable before declaration)
// and so its reference is stable across renders (React Compiler friendly).
const getSampleAlerts = (): SecurityAlert[] => [
  { id: "1", timestamp: new Date().toISOString(), severity: "high", title: "Failed Login Attempts", message: "5 failed login attempts from IP 203.0.113.42 in the last 10 minutes", source: "auth", acknowledged: false },
  { id: "2", timestamp: new Date(Date.now() - 600000).toISOString(), severity: "medium", title: "Unusual API Traffic", message: "Traffic spike detected on /api/v1/projects endpoint", source: "monitor", acknowledged: false },
  { id: "3", timestamp: new Date(Date.now() - 1800000).toISOString(), severity: "low", title: "Expired API Key", message: "API key for user 'engineer@example.com' expired", source: "auth", acknowledged: true },
  { id: "4", timestamp: new Date(Date.now() - 3600000).toISOString(), severity: "critical", title: "Database Connection Failure", message: "Redis connection timeout after 30s", source: "database", acknowledged: false },
];

// Pure fetch helper — does NOT call any React setState. Extracted to module
// scope so it can be safely called from the mount effect's async IIFE without
// triggering react-hooks/set-state-in-effect.
async function fetchAlertsData(apiBase: string, severity: string): Promise<SecurityAlert[]> {
  const params = severity !== "all" ? `?severity=${severity}` : "";
  const res = await fetch(`${apiBase}/monitor/security-alerts${params}`, {
    credentials: "same-origin",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data: AlertsResponse = await res.json();
  return data.alerts || [];
}

export const SecurityAlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<SecurityAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

  // `fetchAlerts` is intended for explicit user actions (Refresh button) — it
  // synchronously calls setLoading(true)/setError(null) which is fine in an
  // event handler.
  const fetchAlerts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAlertsData(API_BASE, severityFilter);
      setAlerts(data);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load security alerts");
      // Fallback sample data
      setAlerts(getSampleAlerts());
    } finally {
      setLoading(false);
    }
  }, [API_BASE, severityFilter]);

  useEffect(() => {
    // Inline async IIFE — no synchronous setState in the effect body. Every
    // setState happens after the first `await`, so react-hooks/set-state-in-effect
    // does not fire. `loading` is already initialised to `true` in useState.
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchAlertsData(API_BASE, severityFilter);
        if (!cancelled) {
          setAlerts(data);
          setLastUpdated(new Date().toLocaleTimeString());
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load security alerts");
          setAlerts(getSampleAlerts());
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [API_BASE, severityFilter]);

  const severityColors: Record<string, { bg: string; text: string; dot: string }> = {
    critical: { bg: "bg-red-500/15", text: "text-red-400", dot: "bg-red-500" },
    high: { bg: "bg-orange-500/15", text: "text-orange-400", dot: "bg-orange-500" },
    medium: { bg: "bg-amber-500/15", text: "text-amber-400", dot: "bg-amber-500" },
    low: { bg: "bg-blue-500/15", text: "text-blue-400", dot: "bg-blue-500" },
  };

  const acknowledgedAlerts = alerts.filter((a) => a.acknowledged);
  const activeAlerts = alerts.filter((a) => !a.acknowledged);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-100 flex items-center gap-2">
            <BellRing className="h-8 w-8 text-orange-500" />
            Security Alerts
          </h1>
          <p className="text-slate-400 mt-2">
            Active and historical security events for the BAZSPARK platform
          </p>
        </div>
        <button
          type="button"
          onClick={() => fetchAlerts()}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="text-2xl font-bold text-slate-100">{alerts.length}</div>
          <p className="text-xs text-slate-400 mt-1">Total</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="text-2xl font-bold text-red-400">{activeAlerts.length}</div>
          <p className="text-xs text-slate-400 mt-1">Active</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="text-2xl font-bold text-amber-400">
            {alerts.filter((a) => a.severity === "critical" || a.severity === "high").length}
          </div>
          <p className="text-xs text-slate-400 mt-1">Critical / High</p>
        </div>
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="text-2xl font-bold text-green-400">{acknowledgedAlerts.length}</div>
          <p className="text-xs text-slate-400 mt-1">Acknowledged</p>
        </div>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2">
        <Filter className="h-4 w-4 text-slate-500" />
        <select
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
          className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 text-sm focus:border-orange-500 focus:outline-none"
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
          <p className="text-xs text-amber-400">
            Backend unavailable — showing sample data. {error}
          </p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 text-orange-400 animate-spin" />
        </div>
      )}

      {/* Alert List */}
      {!loading && (
        <div className="space-y-2">
          {alerts.length === 0 ? (
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-8 text-center">
              <Shield className="h-12 w-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">No security alerts.</p>
              <p className="text-xs text-slate-500 mt-2">Your system is secure.</p>
            </div>
          ) : (
            alerts.map((alert) => {
              const colors = severityColors[alert.severity] || severityColors.low;
              return (
                <div
                  key={alert.id}
                  className={`bg-slate-800/50 border rounded-lg p-4 transition-colors hover:border-slate-600 ${
                    alert.acknowledged ? "border-slate-700/50 opacity-60" : "border-slate-700"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`mt-1 w-2 h-2 rounded-full shrink-0 ${colors.dot}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${colors.bg} ${colors.text}`}>
                          {alert.severity.toUpperCase()}
                        </span>
                        <span className="text-sm font-medium text-slate-100">{alert.title}</span>
                        {alert.source && (
                          <span className="text-xs text-slate-500">via {alert.source}</span>
                        )}
                      </div>
                      <p className="text-sm text-slate-400">{alert.message}</p>
                      <p className="text-xs text-slate-600 mt-1 font-mono">
                        {new Date(alert.timestamp).toLocaleString()}
                      </p>
                    </div>
                    {alert.acknowledged && (
                      <span className="text-xs text-slate-600 shrink-0">Acknowledged</span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* Footer */}
      {!loading && alerts.length > 0 && lastUpdated && (
        <div className="text-center text-xs text-slate-500">
          Last updated: {lastUpdated}
        </div>
      )}
    </div>
  );
};

export default SecurityAlertsPage;
