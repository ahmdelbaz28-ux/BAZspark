/**
 * SyncPage.tsx — Project Synchronization Dashboard.
 *
 * Provides UI to:
 *  - Select a project
 *  - View sync status (last sync time, device/connection counts)
 *  - Trigger a project sync (POST /projects/{id}/sync)
 *
 * Backend: backend/routers/sync.py (prefix: /projects/{project_id}/sync)
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  RefreshCw,
  Loader2,
  Send,
  AlertTriangle,
  Database,
  Activity,
  Clock,
  Info,
} from "lucide-react";
import { syncApi, fullApi } from "@/services/fullApi";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

interface SyncStatus {
  status: "synced" | "syncing" | "error" | string;
  lastSync: string;
  pendingChanges: number;
  deviceCount?: number;
  connectionCount?: number;
}

interface SyncStatusResponse {
  data: SyncStatus;
  success: boolean;
}

export const SyncPage: React.FC = () => {
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const queryClient = useQueryClient();

  // Fetch projects
  const { data: projects, isLoading: projectsLoading } = useQuery({
    queryKey: ["sync-projects"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/projects?limit=50`, {
        credentials: "same-origin",
      });
      if (!res.ok) return [];
      const json = await res.json();
      return json?.data?.data || json?.data || [];
    },
  });

  // Fetch sync status for selected project
  const {
    data: syncData,
    isLoading: statusLoading,
    error: statusError,
    refetch: refetchStatus,
  } = useQuery({
    queryKey: ["sync-status", selectedProjectId],
    queryFn: async () => {
      if (!selectedProjectId) return null;
      const res = await syncApi.getSyncStatus(selectedProjectId) as SyncStatusResponse;
      return res.data;
    },
    enabled: !!selectedProjectId,
  });

  // Trigger sync mutation
  const syncMutation = useMutation({
    mutationFn: async () => {
      if (!selectedProjectId) throw new Error("No project selected");
      const res = await syncApi.syncProject(selectedProjectId) as { data: SyncStatus };
      return res.data as SyncStatus;
    },
    onSuccess: () => {
      // Refetch status after sync completes
      queryClient.invalidateQueries({ queryKey: ["sync-status"] });
    },
  });

  const projectList = Array.isArray(projects) ? projects : [];
  const syncStatus = syncData || syncMutation.data;

  const formatTime = (iso: string | undefined) => {
    if (!iso) return "Never";
    try {
      return new Date(iso).toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return iso;
    }
  };

  const isSyncing = syncMutation.isPending || syncData?.status === "syncing";

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <RefreshCw className="h-6 w-6 text-cyan-400" />
            Project Sync
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Synchronize project data — scans devices and connections, updates
            sync status, and broadcasts real-time updates via WebSocket
          </p>
        </div>

        {/* Project Selector */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Select Project
          </label>
          {projectsLoading ? (
            <div className="flex items-center gap-2 text-slate-400 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading projects...
            </div>
          ) : (
            <select
              value={selectedProjectId}
              onChange={(e) => {
                setSelectedProjectId(e.target.value);
                syncMutation.reset();
              }}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
            >
              <option value="">Select a project...</option>
              {projectList.map(
                (p: { id: string; name: string; [key: string]: unknown }) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                )
              )}
            </select>
          )}
        </div>

        {/* Sync Status Panel */}
        {selectedProjectId && (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-200">
                  Sync Status
                </h3>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => refetchStatus()}
                  disabled={statusLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded-lg transition-colors disabled:opacity-50"
                >
                  <RefreshCw
                    className={`h-3.5 w-3.5 ${
                      statusLoading ? "animate-spin" : ""
                    }`}
                  />
                  Refresh
                </button>
                <button
                  type="button"
                  onClick={() => syncMutation.mutate()}
                  disabled={isSyncing || !selectedProjectId}
                  className="flex items-center gap-1.5 px-4 py-1.5 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors"
                >
                  {syncMutation.isPending ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Syncing...
                    </>
                  ) : (
                    <>
                      <Send className="h-3.5 w-3.5" />
                      Sync Now
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Loading state */}
            {statusLoading && !syncMutation.data && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 text-cyan-400 animate-spin" />
              </div>
            )}

            {/* Error state */}
            {statusError && !syncMutation.data && (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400" />
                  <p className="text-sm text-amber-400">
                    Failed to load sync status
                  </p>
                </div>
              </div>
            )}

            {/* Sync mutation error */}
            {syncMutation.isError && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-red-400" />
                  <p className="text-sm text-red-400">
                    {syncMutation.error instanceof Error
                      ? syncMutation.error.message
                      : "Sync failed"}
                  </p>
                </div>
              </div>
            )}

            {/* Status display */}
            {syncStatus && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center">
                  <div className="text-[10px] text-slate-500 mb-1 flex items-center justify-center gap-1">
                    <Activity className="h-3 w-3" />
                    Status
                  </div>
                  <span
                    className={`text-sm font-bold font-mono ${
                      syncStatus?.status === "synced"
                        ? "text-emerald-400"
                        : syncStatus?.status === "syncing"
                          ? "text-amber-400"
                          : "text-slate-100"
                    }`}
                  >
                    {syncStatus?.status === "synced"
                      ? "Synced"
                      : syncStatus?.status === "syncing"
                        ? "Syncing..."
                        : syncStatus?.status || "Unknown"}
                  </span>
                </div>

                <div className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center">
                  <div className="text-[10px] text-slate-500 mb-1 flex items-center justify-center gap-1">
                    <Clock className="h-3 w-3" />
                    Last Sync
                  </div>
                  <div className="text-[11px] font-bold text-slate-100 font-mono leading-tight">
                    {formatTime(syncStatus?.lastSync)}
                  </div>
                </div>

                <div className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center">
                  <div className="text-[10px] text-slate-500 mb-1 flex items-center justify-center gap-1">
                    <Database className="h-3 w-3" />
                    Devices
                  </div>
                  <div className="text-sm font-bold text-slate-100 font-mono">
                    {syncStatus?.deviceCount ?? "—"}
                  </div>
                </div>

                <div className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center">
                  <div className="text-[10px] text-slate-500 mb-1 flex items-center justify-center gap-1">
                    <Database className="h-3 w-3" />
                    Connections
                  </div>
                  <div className="text-sm font-bold text-slate-100 font-mono">
                    {syncStatus?.connectionCount ?? "—"}
                  </div>
                </div>
              </div>
            )}

            {/* No status yet */}
            {!statusLoading && !statusError && !syncStatus && (
              <div className="py-6 text-center">
                <p className="text-slate-500 text-sm">
                  No sync data available. Click "Sync Now" to trigger a sync.
                </p>
              </div>
            )}
          </div>
        )}

        {/* Info Section */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-cyan-400" />
            <h3 className="text-sm font-semibold text-slate-200">
              About Project Sync
          </h3>
          </div>
          <div className="space-y-2 text-xs text-slate-400 leading-relaxed">
            <p>
              <strong className="text-slate-300">What it does:</strong> Project
              sync scans all devices and connections associated with the selected
              project and updates the sync status. It performs a database
              consistency check to ensure all records are accounted for.
            </p>
            <p>
              <strong className="text-slate-300">Real-time updates:</strong> Sync
              completion events are broadcast via WebSocket to all subscribed
              clients. Open the WebSocket connection at <code className="text-cyan-300">/ws</code>{" "}
              and subscribe to the project to receive live updates.
            </p>
            <p>
              <strong className="text-slate-300">External BIM sync:</strong>{" "}
              For synchronization with external BIM systems (Revit, AutoCAD),
              use the IFC pipeline at the Digital Twin Convert page.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SyncPage;
