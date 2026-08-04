/**
 * DevicesPage.tsx — Fire alarm device CRUD management.
 *
 * Lists, creates, updates, and deletes fire alarm devices (smoke detectors,
 * heat detectors, notification appliances, pull stations, etc.).
 * Uses the Digital Twin API for all CRUD operations.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Loader2, Plus, Trash2, Pencil, Cpu, Eye } from "lucide-react";
import digitalTwinApi, {
  type Device,
  type CreateDeviceInput,
  type UpdateDeviceInput,
} from "@/services/digitalTwinApi";

const DEVICE_TYPES = [
  "smoke_detector",
  "heat_detector",
  "multisensor_detector",
  "beam_detector",
  "duct_detector",
  "pull_station",
  "notification_appliance",
  "strobe",
  "speaker",
  "nac_extender",
  "control_module",
  "monitor_module",
  "isolator_module",
  "relay_module",
  "facp_panel",
  "annunciator",
  "power_supply",
  "battery_backup",
  "flow_switch",
  "tamper_switch",
  "valve_sensor",
] as const;

const DEVICE_CATEGORIES = [
  "detection",
  "notification",
  "control",
  "power",
  "annunciation",
  "input",
  "output",
  "supervision",
  "communication",
] as const;

const PAGE_SIZE = 20;

const LOAD_UNITS = ["A", "mA", "W"] as const;

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

export const DevicesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [viewTarget, setViewTarget] = useState<Device | null>(null);
  const [editTarget, setEditTarget] = useState<Device | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Device | null>(null);

  // Fetch the first available project ID for CRUD operations
  const { data: projectData } = useQuery({
    queryKey: ["devices-project"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/projects?page=1&limit=1`, {
        credentials: "same-origin",
      });
      if (!res.ok) return null;
      const json = await res.json();
      // Backend wraps in {success, data: { data: [...], total, ... }}
      const projects = json?.data?.data || json?.data || [];
      return Array.isArray(projects) && projects.length > 0 ? projects[0] : null;
    },
    staleTime: 60000, // Cache project ID for 1 minute
  });

  const projectId = projectData?.id || "";

  // Fetch devices — waits for projectId to resolve before calling project-scoped API
  const { data, isLoading, error } = useQuery({
    queryKey: ["devices", projectId || "global", page, typeFilter, categoryFilter],
    queryFn: async () => {
      // Try project-scoped endpoint first
      if (projectId) {
        const response = await digitalTwinApi.getDevices(projectId, {
          page,
          limit: PAGE_SIZE,
          sort: "createdAt",
          order: "desc",
        });
        if (response.success) return response.data;
      }
      // Fallback: try the global /devices endpoint
      try {
        const fallback = await fetch(
          `${API_BASE}/devices?page=${page}&limit=${PAGE_SIZE}`,
          { credentials: "same-origin" }
        );
        if (fallback.ok) {
          const json = await fallback.json();
          const result = json.data || json;
          // Ensure result has consistent paginated shape
          if (result && Array.isArray(result.data)) return result;
          if (Array.isArray(result)) return { data: result, total: result.length, page, limit: PAGE_SIZE, totalPages: Math.ceil(result.length / PAGE_SIZE) };
          return result;
        }
      } catch {
        // Return empty if both fail
      }
      return { data: [], total: 0, page, limit: PAGE_SIZE, totalPages: 0 };
    },
    enabled: true,
  });

  const devices = data?.data ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.totalPages ?? Math.ceil(total / PAGE_SIZE);

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (device: Device) => {
      const pid = device.projectId || projectId;
      if (!pid) throw new Error("No project available for device operations");
      const res = await digitalTwinApi.deleteDevice(pid, device.id);
      if (!res.success) throw new Error(res.error || "Delete failed");
      return res;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["devices"] });
      setDeleteTarget(null);
    },
  });

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-6xl mx-auto space-y-5">
        {/* FACP Page Header */}
        <div className="facp-page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Cpu aria-hidden="true" style={{ color: "var(--color-primary)" }} className="h-5 w-5" />
              <h1 className="facp-page-title">Devices</h1>
            </div>
            <p className="facp-page-count">
              {isLoading
                ? "Loading…"
                : `${total} fire alarm device${total !== 1 ? "s" : ""} registered`}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="facp-btn facp-btn--primary"
            aria-label="Add new fire alarm device"
          >
            <Plus aria-hidden="true" className="h-4 w-4" />
            Add Device
          </button>
        </div>

        {/* Filter Bar */}
        <div className="facp-filter-bar">
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(1);
            }}
            className="facp-select"
            style={{ minWidth: "140px", flex: "0 0 auto" }}
            aria-label="Filter by device type"
          >
            <option value="">All Types</option>
            {DEVICE_TYPES.map((t) => (
              <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
            ))}
          </select>
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
            className="facp-select"
            style={{ minWidth: "130px", flex: "0 0 auto" }}
            aria-label="Filter by device category"
          >
            <option value="">All Categories</option>
            {DEVICE_CATEGORIES.map((c) => (
              <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
            ))}
          </select>
          {(typeFilter || categoryFilter) && (
            <button
              type="button"
              onClick={() => { setTypeFilter(""); setCategoryFilter(""); setPage(1); }}
              className="facp-btn facp-btn--ghost"
              aria-label="Clear all filters"
            >
              ✕ Clear
            </button>
          )}
        </div>

        {/* Error */}
        {error && (
          <div
            className="facp-panel"
            role="alert"
            style={{ borderLeft: "4px solid var(--color-signal-red)", padding: "1rem 1.25rem" }}
          >
            <span className="facp-badge facp-badge--error">Error</span>
            <span style={{ fontFamily: "var(--font-body)", fontSize: "0.8125rem", color: "var(--color-bone)", marginLeft: "0.5rem" }}>
              Failed to load devices. Check your connection.
            </span>
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 aria-hidden="true" style={{ color: "var(--color-primary)" }} className="h-8 w-8 animate-spin" />
          </div>
        )}

        {/* Device Table */}
        {!isLoading && (
          <div className="facp-table-wrap">
            <table className="facp-table" aria-label="Fire alarm devices">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Type</th>
                  <th scope="col">Category</th>
                  <th scope="col">Load</th>
                  <th scope="col">Voltage</th>
                  <th scope="col" style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {devices.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ padding: 0 }}>
                      <div className="facp-empty">
                        <Cpu aria-hidden="true" className="facp-empty-icon h-10 w-10" />
                        <p className="facp-empty-title">No devices registered</p>
                        <p className="facp-empty-desc">
                          {typeFilter || categoryFilter
                            ? "No devices match the current filters. Try adjusting or clearing them."
                            : "Add your first fire alarm device to begin coverage calculations."}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  devices.map((device: Device) => (
                    <tr key={device.id}>
                      <td>
                        <span className="facp-table-name">{device.name}</span>
                        <div className="facp-table-id">{device.id.slice(0, 8)}&hellip;</div>
                      </td>
                      <td>
                        <span className="facp-type-chip">
                          {device.type.replace(/_/g, " ")}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontFamily: "var(--font-data)", fontSize: "0.7rem", color: "var(--color-steel)", letterSpacing: "0.05em" }}>
                          {device.category.charAt(0).toUpperCase() + device.category.slice(1)}
                        </span>
                      </td>
                      <td className="facp-table-num">
                        {device.load != null ? `${device.load.toFixed(3)} A` : "—"}
                      </td>
                      <td className="facp-table-num">
                        {device.voltage != null ? `${device.voltage} V` : "—"}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => setViewTarget(device)}
                            className="facp-btn facp-btn--ghost facp-btn--icon"
                            title="View Details"
                            aria-label={`View details for ${device.name}`}
                          >
                            <Eye aria-hidden="true" className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditTarget(device)}
                            className="facp-btn facp-btn--ghost facp-btn--icon"
                            title="Edit"
                            aria-label={`Edit ${device.name}`}
                          >
                            <Pencil aria-hidden="true" className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteTarget(device)}
                            className="facp-btn facp-btn--danger facp-btn--icon"
                            title="Delete"
                            aria-label={`Delete ${device.name}`}
                          >
                            <Trash2 aria-hidden="true" className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="facp-pagination">
            <span>Page {page} of {totalPages} &bull; {total} devices</span>
            <div className="facp-pagination-btns">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="facp-btn facp-btn--ghost"
                aria-label="Previous page"
              >
                &larr; Prev
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="facp-btn facp-btn--ghost"
                aria-label="Next page"
              >
                Next &rarr;
              </button>
            </div>
          </div>
        )}

        {/* Create Device Modal */}
        {showCreateModal && (
          <DeviceFormModal
            mode="create"
            projectId={projectId}
            onClose={() => setShowCreateModal(false)}
            onSuccess={() => {
              setShowCreateModal(false);
              queryClient.invalidateQueries({ queryKey: ["devices"] });
            }}
          />
        )}

        {/* Edit Device Modal */}
        {editTarget && (
          <DeviceFormModal
            mode="edit"
            device={editTarget}
            projectId={projectId}
            onClose={() => setEditTarget(null)}
            onSuccess={() => {
              setEditTarget(null);
              queryClient.invalidateQueries({ queryKey: ["devices"] });
            }}
          />
        )}

        {/* View Device Modal */}
        {viewTarget && (
          <DeviceDetailModal
            device={viewTarget}
            projectId={projectId}
            onClose={() => setViewTarget(null)}
          />
        )}

        {/* Delete Confirmation */}
        {deleteTarget && (
          <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-xl max-w-md w-full p-6 shadow-2xl">
              <h3 className="text-lg font-semibold text-slate-100 mb-2">
                Delete Device
              </h3>
              <p className="text-slate-400 text-sm mb-4">
                Are you sure you want to delete{" "}
                <span className="text-slate-200 font-medium">{deleteTarget.name}</span>?
                This action affects coverage calculations and cannot be undone.
              </p>
              {deleteMutation.isError && (
                <p className="text-red-400 text-sm mb-3">
                  Delete failed:{" "}
                  {deleteMutation.error instanceof Error
                    ? deleteMutation.error.message
                    : "Unknown error"}
                </p>
              )}
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setDeleteTarget(null)}
                  className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(deleteTarget)}
                  disabled={deleteMutation.isPending}
                  className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  {deleteMutation.isPending ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ─── Device View Modal ───────────────────────────────────────────────

interface DeviceDetailModalProps {
  device: Device;
  projectId: string;
  onClose: () => void;
}

function DeviceDetailModal({ device, projectId, onClose }: DeviceDetailModalProps) {
  const { data: detailData, isLoading, error } = useQuery({
    queryKey: ["device", projectId, device.id],
    queryFn: async () => {
      const res = await digitalTwinApi.getDevice(projectId, device.id);
      if (!res.success) throw new Error(res.error || "Failed to load device details");
      return res.data;
    },
  });

  const fullDevice = detailData || device;

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-xl max-w-lg w-full p-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white"
        >
          ✕
        </button>
        <h3 className="text-xl font-bold text-slate-100 mb-4">{fullDevice.name}</h3>

        {isLoading ? (
          <div className="flex justify-center py-8"><Loader2 className="animate-spin text-cyan-400" /></div>
        ) : error ? (
          <p className="text-red-400">Error loading details</p>
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-slate-400">Type</p>
                <p className="text-sm text-slate-200">{fullDevice.type.replace(/_/g, " ")}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Category</p>
                <p className="text-sm text-slate-200">{fullDevice.category}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Location (X, Y, Z)</p>
                <p className="text-sm text-slate-200">{`${fullDevice.x}, ${fullDevice.y}, ${fullDevice.z}`}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Rotation</p>
                <p className="text-sm text-slate-200">{fullDevice.rotation}°</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Voltage</p>
                <p className="text-sm text-slate-200">{fullDevice.voltage} V</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Current / Load</p>
                <p className="text-sm text-slate-200">{fullDevice.current} A / {fullDevice.load} A</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Created At</p>
                <p className="text-sm text-slate-200">{new Date(fullDevice.createdAt).toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Updated At</p>
                <p className="text-sm text-slate-200">{new Date(fullDevice.updatedAt).toLocaleString()}</p>
              </div>
            </div>
            
            {fullDevice.properties && Object.keys(fullDevice.properties).length > 0 && (
              <div className="mt-4 border-t border-slate-700 pt-4">
                <p className="text-xs font-semibold text-slate-400 mb-2">Extended Properties</p>
                <pre className="bg-slate-900 p-3 rounded-lg text-xs text-slate-300 overflow-auto max-h-32">
                  {JSON.stringify(fullDevice.properties, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Device Create/Edit Modal ───────────────────────────────────────────────

interface DeviceFormModalProps {
  mode: "create" | "edit";
  device?: Device;
  projectId: string;
  onClose: () => void;
  onSuccess: () => void;
}

function DeviceFormModal({ mode, device, projectId, onClose, onSuccess }: DeviceFormModalProps) {
  const [name, setName] = useState(device?.name ?? "");
  const [type, setType] = useState(device?.type ?? "smoke_detector");
  const [category, setCategory] = useState(device?.category ?? "detection");
  const [x, setX] = useState(String(device?.x ?? 0));
  const [y, setY] = useState(String(device?.y ?? 0));
  const [z, setZ] = useState(String(device?.z ?? 0));
  const [rotation, setRotation] = useState(String(device?.rotation ?? 0));
  const [voltage, setVoltage] = useState(String(device?.voltage ?? 0));
  const [current, setCurrent] = useState(String(device?.current ?? 0));
  const [load, setLoad] = useState(String(device?.load ?? 0));
  const [loadUnit, setLoadUnit] = useState<"A" | "mA" | "W">("A");

  const mutation = useMutation({
    mutationFn: async () => {
      const pid = device?.projectId || projectId;
      if (!pid) throw new Error("No project available for device operations");

      const common = {
        name,
        type,
        category,
        x: Number.parseFloat(x) || 0,
        y: Number.parseFloat(y) || 0,
        z: Number.parseFloat(z) || 0,
        rotation: Number.parseFloat(rotation) || 0,
        voltage: Number.parseFloat(voltage) || 0,
        current: Number.parseFloat(current) || 0,
        load: Number.parseFloat(load) || 0,
        load_unit: loadUnit,
      };

      if (mode === "create") {
        const input: CreateDeviceInput = {
          ...common,
          properties: {},
        };
        const res = await digitalTwinApi.createDevice(pid, input);
        if (!res.success) throw new Error(res.error || "Create failed");
        return res;
      } else {
        const input: UpdateDeviceInput = common;
        const res = await digitalTwinApi.updateDevice(pid, device!.id, input);
        if (!res.success) throw new Error(res.error || "Update failed");
        return res;
      }
    },
    onSuccess,
  });

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div className="bg-slate-800 border border-slate-700 rounded-xl max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto shadow-2xl">
        <h3 className="text-lg font-semibold text-slate-100 mb-4">
          {mode === "create" ? "Add New Device" : `Edit: ${device?.name}`}
        </h3>

        {mutation.isError && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4">
            <p className="text-red-400 text-sm">
              {mutation.error instanceof Error
                ? mutation.error.message
                : "Operation failed"}
            </p>
          </div>
        )}

        <div className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
              placeholder="e.g., SD-101"
            />
          </div>

          {/* Type & Category */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Type *</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
              >
                {DEVICE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-1">Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
              >
                {DEVICE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c.charAt(0).toUpperCase() + c.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Position */}
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Position</p>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">X</label>
                <input
                  type="number"
                  step="0.1"
                  value={x}
                  onChange={(e) => setX(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Y</label>
                <input
                  type="number"
                  step="0.1"
                  value={y}
                  onChange={(e) => setY(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Z</label>
                <input
                  type="number"
                  step="0.1"
                  value={z}
                  onChange={(e) => setZ(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Electrical Parameters */}
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">Electrical</p>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Voltage (V)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={voltage}
                  onChange={(e) => setVoltage(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Current (A)</label>
                <input
                  type="number"
                  step="0.001"
                  min="0"
                  value={current}
                  onChange={(e) => setCurrent(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div>
                <label className="block text-xs text-slate-500 mb-1">Load</label>
                <input
                  type="number"
                  step="0.001"
                  min="0"
                  value={load}
                  onChange={(e) => setLoad(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-500 mb-1">Load Unit</label>
                <select
                  value={loadUnit}
                  onChange={(e) => setLoadUnit(e.target.value as "A" | "mA" | "W")}
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
                >
                  {LOAD_UNITS.map((u) => (
                    <option key={u} value={u}>{u}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-700">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={!name || !type || !category || mutation.isPending}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {mutation.isPending
              ? "Saving..."
              : mode === "create"
                ? "Create Device"
                : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default DevicesPage;
