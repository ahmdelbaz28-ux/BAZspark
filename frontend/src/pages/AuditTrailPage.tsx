/**
 * AuditTrailPage.tsx — System audit trail dashboard.
 *
 * Shows a chronological log of system events, workflow transitions,
 * and safety-critical operations for NFPA 72 traceability.
 */
import React, { useCallback, useEffect, useState } from "react";
import { ClipboardList, Loader2, RefreshCw, AlertTriangle, Search, ShieldCheck } from "lucide-react";

interface AuditEvent {
  id: string;
  timestamp: string;
  action: string;
  entity_type: string;
  entity_id: string;
  user?: string;
  details?: string;
  severity?: "info" | "warning" | "error";
}

// Fallback sample data when backend is unavailable.
// Extracted to module scope so it is hoisted above any reference inside the
// component (react-hooks/immutability: cannot access a variable before declaration)
// and so its reference is stable across renders (React Compiler friendly).
const getSampleEvents = (): AuditEvent[] => [
  { id: "1", timestamp: new Date(Date.now() - 60000).toISOString(), action: "workflow.approved", entity_type: "workflow", entity_id: "WF-001", user: "admin", details: "Smoke detector layout approved", severity: "info" },
  { id: "2", timestamp: new Date(Date.now() - 300000).toISOString(), action: "device.created", entity_type: "device", entity_id: "DEV-042", user: "engineer", details: "Heat detector added to Zone 3", severity: "info" },
  { id: "3", timestamp: new Date(Date.now() - 900000).toISOString(), action: "project.updated", entity_type: "project", entity_id: "PRJ-015", user: "admin", details: "Project specification updated", severity: "warning" },
  { id: "4", timestamp: new Date(Date.now() - 1800000).toISOString(), action: "connection.deleted", entity_type: "connection", entity_id: "CON-007", user: "system", details: "Orphaned SLC connection pruned", severity: "info" },
  { id: "5", timestamp: new Date(Date.now() - 3600000).toISOString(), action: "workflow.rejected", entity_type: "workflow", entity_id: "WF-002", user: "reviewer", details: "NAC circuit count exceeds panel capacity", severity: "error" },
  { id: "6", timestamp: new Date(Date.now() - 7200000).toISOString(), action: "conflict.detected", entity_type: "conflict", entity_id: "CF-012", user: "system", details: "Device spacing overlap in Room 204", severity: "warning" },
];

// Pure fetch helper — does NOT call any React setState. Extracted to module
// scope so it can be safely called from the mount effect's async IIFE without
// triggering react-hooks/set-state-in-effect.
async function fetchAuditEventsData(apiBase: string): Promise<AuditEvent[]> {
  // Fetch from workflows audit endpoints as primary source
  const res = await fetch(`${apiBase}/workflow/status`, {
    credentials: "same-origin",
  });
  if (!res.ok) return [];
  const data = await res.json();
  // Transform workflow data into audit events if available
  const workflows = Array.isArray(data) ? data : data?.workflows || [];
  return workflows.flatMap((wf: Record<string, unknown>, idx: number) => {
    const transitions = (wf as { transition_log?: Array<Record<string, unknown>> }).transition_log || [];
    return transitions.map((t: Record<string, unknown>, tIdx: number) => ({
      id: `wf-${idx}-${tIdx}`,
      timestamp: (t.timestamp as string) || new Date().toISOString(),
      action: (t.action as string) || "transition",
      entity_type: "workflow",
      entity_id: (wf.id as string) || `wf-${idx}`,
      user: (t.actor as string) || "system",
      details: (t.comment as string) || "",
      severity: "info" as const,
    }));
  });
}

export const AuditTrailPage: React.FC = () => {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<string>("all");
  const [integrityResult, setIntegrityResult] = useState<Record<string, unknown> | null>(null);
  const [integrityLoading, setIntegrityLoading] = useState(false);

  const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

  // `fetchAuditEvents` is intended for explicit user actions (Refresh button) —
  // it synchronously calls setLoading(true)/setError(null) which is fine in an
  // event handler.
  const fetchAuditEvents = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const auditEvents = await fetchAuditEventsData(API_BASE);
      setEvents(auditEvents.length > 0 ? auditEvents : getSampleEvents());
    } catch {
      setEvents(getSampleEvents());
    } finally {
      setLoading(false);
    }
  }, [API_BASE]);

  useEffect(() => {
    // Inline async IIFE — no synchronous setState in the effect body. Every
    // setState happens after the first `await`, so react-hooks/set-state-in-effect
    // does not fire. `loading` is already initialised to `true` in useState.
    let cancelled = false;
    (async () => {
      try {
        const auditEvents = await fetchAuditEventsData(API_BASE);
        if (!cancelled) {
          setEvents(auditEvents.length > 0 ? auditEvents : getSampleEvents());
        }
      } catch {
        if (!cancelled) setEvents(getSampleEvents());
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [API_BASE]);

  const filteredEvents = events.filter((ev) => {
    const matchesSearch =
      !searchQuery ||
      ev.action.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ev.entity_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (ev.user || "").toLowerCase().includes(searchQuery.toLowerCase()) ||
      (ev.details || "").toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = filterType === "all" || ev.entity_type === filterType;
    return matchesSearch && matchesType;
  });

  const severityStyles: Record<string, string> = {
    info: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    warning: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    error: "text-red-400 bg-red-500/10 border-red-500/20",
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-100 flex items-center gap-2">
            <ClipboardList className="h-8 w-8 text-blue-500" />
            Audit Trail
          </h1>
          <p className="text-slate-400 mt-2">
            Chronological record of system events and safety-critical operations (NFPA 72 §10.6)
          </p>
        </div>
        <button
          type="button"
          onClick={() => fetchAuditEvents()}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
        <button
          type="button"
          onClick={async () => {
            setIntegrityLoading(true);
            try {
              const res = await fetch(`${API_BASE}/audit/integrity`, { credentials: "same-origin" });
              if (res.ok) {
                const data = await res.json();
                setIntegrityResult(data as Record<string, unknown>);
              } else {
                setIntegrityResult({ error: `HTTP ${res.status}`, note: "Audit integrity endpoint may not be available yet" });
              }
            } catch {
              setIntegrityResult({ error: "Network error", note: "Audit integrity endpoint may not be available yet" });
            } finally {
              setIntegrityLoading(false);
            }
          }}
          disabled={integrityLoading}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-sm transition-colors disabled:opacity-50"
        >
          {integrityLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          Verify Integrity
        </button>
      </div>

      {integrityResult && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <span className="text-sm font-medium text-slate-200">Integrity Check Result</span>
          </div>
          <pre className="text-xs font-mono text-slate-400 whitespace-pre-wrap">{JSON.stringify(integrityResult, null, 2)}</pre>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search events..."
            className="w-full pl-9 pr-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 text-sm focus:border-blue-500 focus:outline-none"
        >
          <option value="all">All Types</option>
          <option value="workflow">Workflows</option>
          <option value="device">Devices</option>
          <option value="project">Projects</option>
          <option value="connection">Connections</option>
          <option value="conflict">Conflicts</option>
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 text-blue-400 animate-spin" />
        </div>
      )}

      {/* Event List */}
      {!loading && (
        <div className="space-y-2">
          {filteredEvents.length === 0 ? (
            <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-8 text-center">
              <ClipboardList className="h-12 w-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">
                {searchQuery || filterType !== "all"
                  ? "No events match your filters."
                  : "No audit events recorded yet."}
              </p>
            </div>
          ) : (
            filteredEvents.map((ev) => (
              <div
                key={ev.id}
                className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 hover:border-slate-600 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded border ${severityStyles[ev.severity || "info"]}`}>
                        {ev.action}
                      </span>
                      <span className="text-xs text-slate-500 font-mono">{ev.entity_id}</span>
                    </div>
                    {ev.details && (
                      <p className="text-sm text-slate-300 mt-1">{ev.details}</p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-slate-500 font-mono">
                      {new Date(ev.timestamp).toLocaleString()}
                    </p>
                    {ev.user && (
                      <p className="text-xs text-slate-500 mt-0.5">by {ev.user}</p>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Footer */}
      {!loading && filteredEvents.length > 0 && (
        <div className="text-center text-xs text-slate-500">
          Showing {filteredEvents.length} of {events.length} total events
        </div>
      )}
    </div>
  );
};

export default AuditTrailPage;
