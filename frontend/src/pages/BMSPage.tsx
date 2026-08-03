/**
 * BMSPage.tsx — Building Management Systems Overview Dashboard.
 *
 * Shows system status cards for fire panels, environment, CAD imports,
 * and other building subsystems. Pulls from various backend endpoints
 * to give a unified building health view.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router";
import {
  Building2,
  FlameKindling,
  Wind,
  PenLine,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  RefreshCw,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

interface SystemCard {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  status: "healthy" | "warning" | "error" | "unknown";
  metrics: { label: string; value: string }[];
  link?: string;
}

export const BMSPage: React.FC = () => {
  const [systems, setSystems] = useState<SystemCard[]>([
    {
      id: "fire-alarm",
      title: "Fire Alarm System",
      description: "Fire detection, notification, and suppression control panels",
      icon: FlameKindling,
      status: "healthy",
      metrics: [
        { label: "Panels", value: "—" },
        { label: "Devices", value: "—" },
        { label: "Zones", value: "—" },
      ],
      link: "/engineering/facp",
    },
    {
      id: "environment",
      title: "Environmental Monitoring",
      description: "Weather, air quality, and hazmat sensors",
      icon: Wind,
      status: "unknown",
      metrics: [
        { label: "Sensors", value: "—" },
        { label: "Air Quality", value: "—" },
        { label: "Weather", value: "—" },
      ],
      link: "/environment/context",
    },
    {
      id: "cad-bim",
      title: "CAD & BIM Integration",
      description: "Building drawings, Revit models, and digital twins",
      icon: PenLine,
      status: "unknown",
      metrics: [
        { label: "Drawings", value: "—" },
        { label: "Models", value: "—" },
        { label: "DWG Files", value: "—" },
      ],
      link: "/dwg",
    },
    {
      id: "system-health",
      title: "System Health",
      description: "Backend services, databases, and API status",
      icon: Activity,
      status: "unknown",
      metrics: [
        { label: "API", value: "—" },
        { label: "Database", value: "—" },
        { label: "Uptime", value: "—" },
      ],
      link: "/system-health",
    },
  ]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchSystemStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      // Try to fetch health info
      const healthRes = await fetch(`${API_BASE}/health`, {
        credentials: "same-origin",
      });
      const healthJson = healthRes.ok ? await healthRes.json() : {};

      // Try to fetch project info for device count
      let deviceCount = "—";
      try {
        const devRes = await fetch(`${API_BASE}/devices?limit=1`, {
          credentials: "same-origin",
        });
        if (devRes.ok) {
          const devJson = await devRes.json();
          const total = devJson?.data?.total ?? devJson?.total;
          if (total != null) deviceCount = String(total);
        }
      } catch { /* ignore */ }

      setSystems((prev) =>
        prev.map((s) => {
          if (s.id === "fire-alarm") {
            return {
              ...s,
              status: healthRes.ok ? "healthy" : "warning",
              metrics: s.metrics.map((m) =>
                m.label === "Devices" ? { ...m, value: deviceCount } : m
              ),
            };
          }
          if (s.id === "system-health") {
            const apiStatus = healthRes.ok ? "Online" : "Offline";
            return {
              ...s,
              status: healthRes.ok ? "healthy" : "error",
              metrics: [
                { label: "API", value: apiStatus },
                { label: "Database", value: healthJson?.database ?? "—" },
                {
                  label: "Uptime",
                  value:
                    healthJson?.uptime != null
                      ? `${Math.round(healthJson.uptime / 60)}m`
                      : "—",
                },
              ],
            };
          }
          return s;
        })
      );
      setLastUpdated(new Date());
    } catch {
      setError("Failed to fetch system status");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Inline async IIFE — no synchronous setState in the effect body
    // (react-hooks/set-state-in-effect). `fetchSystemStatus` is still defined
    // above for use by event handlers (refresh button).
    let cancelled = false;
    (async () => {
      try {
        const healthRes = await fetch(`${API_BASE}/health`, {
          credentials: "same-origin",
        });
        const healthJson = healthRes.ok ? await healthRes.json() : {};

        let deviceCount = "—";
        try {
          const devRes = await fetch(`${API_BASE}/devices?limit=1`, {
            credentials: "same-origin",
          });
          if (devRes.ok) {
            const devJson = await devRes.json();
            const total = devJson?.data?.total ?? devJson?.total;
            if (total != null) deviceCount = String(total);
          }
        } catch { /* ignore */ }

        if (cancelled) return;
        setSystems((prev) =>
          prev.map((s) => {
            if (s.id === "fire-alarm") {
              return {
                ...s,
                status: healthRes.ok ? "healthy" : "warning",
                metrics: s.metrics.map((m) =>
                  m.label === "Devices" ? { ...m, value: deviceCount } : m
                ),
              };
            }
            if (s.id === "system-health") {
              const apiStatus = healthRes.ok ? "Online" : "Offline";
              return {
                ...s,
                status: healthRes.ok ? "healthy" : "error",
                metrics: [
                  { label: "API", value: apiStatus },
                  { label: "Database", value: healthJson?.database ?? "—" },
                  {
                    label: "Uptime",
                    value:
                      healthJson?.uptime != null
                        ? `${Math.round(healthJson.uptime / 60)}m`
                        : "—",
                  },
                ],
              };
            }
            return s;
          })
        );
        setLastUpdated(new Date());
      } catch {
        if (!cancelled) setError("Failed to fetch system status");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const statusColors: Record<string, string> = {
    healthy: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    warning: "text-amber-400 bg-amber-500/10 border-amber-500/30",
    error: "text-red-400 bg-red-500/10 border-red-500/30",
    unknown: "text-slate-400 bg-slate-500/10 border-slate-500/30",
  };

  const statusIcons: Record<string, React.ElementType> = {
    healthy: CheckCircle2,
    warning: AlertTriangle,
    error: AlertTriangle,
    unknown: Clock,
  };

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <Building2 className="h-6 w-6 text-cyan-400" />
              Building Management Systems
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              {loading
                ? "Loading system status..."
                : lastUpdated
                  ? `Last updated: ${lastUpdated.toLocaleTimeString()}`
                  : "Overview of connected building subsystems"}
            </p>
          </div>
          <button
            type="button"
            onClick={fetchSystemStatus}
            disabled={loading}
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <p className="text-red-400 text-sm">{error}</p>
          </div>
        )}

        {/* System Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {systems.map((system) => {
            const StatusIcon = statusIcons[system.status];
            return (
              <div
                key={system.id}
                className="bg-slate-800/50 border border-slate-700 rounded-xl overflow-hidden hover:border-slate-600 transition-colors"
              >
                {/* Card Header */}
                <div className="p-5 flex items-start gap-4">
                  <div className="p-2.5 rounded-lg bg-slate-700/50 text-cyan-400 flex-shrink-0">
                    <system.icon className="h-5 w-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-semibold text-slate-100">
                      {system.title}
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {system.description}
                    </p>
                  </div>
                  <div
                    className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${statusColors[system.status]}`}
                  >
                    <StatusIcon className="h-3 w-3" />
                    {system.status.charAt(0).toUpperCase() + system.status.slice(1)}
                  </div>
                </div>

                {/* Metrics */}
                <div className="px-5 pb-4">
                  <div className="grid grid-cols-3 gap-3">
                    {system.metrics.map((metric) => (
                      <div
                        key={metric.label}
                        className="bg-slate-800 rounded-lg p-2.5 text-center border border-slate-700/50"
                      >
                        <div className="text-xs text-slate-500 mb-1">
                          {metric.label}
                        </div>
                        <div className="text-sm font-semibold text-slate-200 font-mono">
                          {metric.value}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Card Footer */}
                {system.link && (
                  <Link
                    to={system.link}
                    className="block px-5 py-2.5 text-xs text-cyan-500 hover:text-cyan-400 bg-slate-800/30 hover:bg-slate-700/30 border-t border-slate-700/50 transition-colors"
                  >
                    View details →
                  </Link>
                )}
              </div>
            );
          })}
        </div>

        {/* Quick Actions */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-3">
            Quick Actions
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Link
              to="/engineering/facp"
              className="flex flex-col items-center gap-2 p-3 rounded-lg bg-slate-700/30 hover:bg-slate-700/50 border border-slate-700/50 hover:border-cyan-500/30 transition-colors"
            >
              <FlameKindling className="h-5 w-5 text-cyan-400" />
              <span className="text-xs text-slate-400">FACP Designer</span>
            </Link>
            <Link
              to="/environment/context"
              className="flex flex-col items-center gap-2 p-3 rounded-lg bg-slate-700/30 hover:bg-slate-700/50 border border-slate-700/50 hover:border-cyan-500/30 transition-colors"
            >
              <Wind className="h-5 w-5 text-cyan-400" />
              <span className="text-xs text-slate-400">Weather</span>
            </Link>
            <Link
              to="/dwg"
              className="flex flex-col items-center gap-2 p-3 rounded-lg bg-slate-700/30 hover:bg-slate-700/50 border border-slate-700/50 hover:border-cyan-500/30 transition-colors"
            >
              <PenLine className="h-5 w-5 text-cyan-400" />
              <span className="text-xs text-slate-400">DWG/DXF Parse</span>
            </Link>
            <Link
              to="/system-health"
              className="flex flex-col items-center gap-2 p-3 rounded-lg bg-slate-700/30 hover:bg-slate-700/50 border border-slate-700/50 hover:border-cyan-500/30 transition-colors"
            >
              <Activity className="h-5 w-5 text-cyan-400" />
              <span className="text-xs text-slate-400">System Health</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BMSPage;
