/**
 * GuardsPage.tsx — Physics Guard Limits dashboard.
 *
 * Displays all physics guard limits used by the QOMN engineering engine,
 * fetched from GET /api/qomn/physics-guards.
 */
import React, { useCallback, useEffect, useState } from "react";
import { ShieldAlert, Loader2, RefreshCw, AlertTriangle, CheckCircle2, FileCode } from "lucide-react";

interface PhysicsGuard {
  name: string;
  value: string | number;
  unit: string;
  code_reference?: string;
  description?: string;
}

interface GuardsResponse {
  guards?: PhysicsGuard[];
  total_count?: number;
}

export const GuardsPage: React.FC = () => {
  const [guards, setGuards] = useState<PhysicsGuard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

  const fetchGuards = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/qomn/physics-guards`, {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: GuardsResponse = await res.json();
      setGuards(data.guards || []);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load physics guards");
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    // Inline async IIFE — no synchronous setState in the effect body
    // (react-hooks/set-state-in-effect). `fetchGuards` is still defined above
    // for use by event handlers (refresh button).
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/qomn/physics-guards`, {
          credentials: "same-origin",
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: GuardsResponse = await res.json();
        if (cancelled) return;
        setGuards(data.guards || []);
        setLastUpdated(new Date().toLocaleTimeString());
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load physics guards");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [API_BASE]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-100 flex items-center gap-2">
            <ShieldAlert className="h-8 w-8 text-emerald-500" />
            Physics Guards
          </h1>
          <p className="text-slate-400 mt-2">
            Engineering guard limits and constraint boundaries for QOMN calculations
          </p>
        </div>
        <button
          type="button"
          onClick={fetchGuards}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-red-400">Failed to load physics guards</p>
            <p className="text-xs text-red-300/70 mt-1">{error}</p>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && !error && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 text-emerald-400 animate-spin" />
        </div>
      )}

      {/* Guard Cards */}
      {!loading && !error && guards.length === 0 && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-8 text-center">
          <ShieldAlert className="h-12 w-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">No physics guards configured.</p>
        </div>
      )}

      {guards.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {guards.map((guard, idx) => (
            <div
              key={guard.name || idx}
              className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 hover:border-slate-600 transition-colors"
            >
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-sm font-semibold text-slate-200 font-mono">
                  {guard.name}
                </h3>
                <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-400">Value</span>
                  <span className="text-slate-100 font-mono font-medium">
                    {guard.value} {guard.unit}
                  </span>
                </div>
                {guard.description && (
                  <p className="text-xs text-slate-500 mt-2">{guard.description}</p>
                )}
                {guard.code_reference && (
                  <div className="flex items-center gap-1.5 mt-2 text-xs text-slate-500">
                    <FileCode className="h-3 w-3" />
                    <span>{guard.code_reference}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Summary */}
      {guards.length > 0 && (
        <div className="bg-slate-800/30 border border-slate-700/50 rounded-lg p-4 text-center">
          <p className="text-xs text-slate-500">
            <span className="text-emerald-400 font-medium">{guards.length}</span> guard limit
            {guards.length !== 1 ? "s" : ""} active
            {lastUpdated && <> · Last updated: {lastUpdated}</>}
          </p>
        </div>
      )}
    </div>
  );
};

export default GuardsPage;
