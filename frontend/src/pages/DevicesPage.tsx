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
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <Cpu className="h-6 w-6 text-cyan-400" />
              Devices
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              {isLoading
                ? "Loading devices..."
                : `${total} fire alarm device${total !== 1 ? "s" : ""}`}
            </p>
          </div>
          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white text-sm font-medium rounded-lg transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add Device
          </button>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <select
            value={typeFilter}
            onChange={(e) => {
              setTypeFilter(e.target.value);
              setPage(1);
            }}
            className="bg-slate-800 border border-slate-700 text-slate-100 text-sm rounded-lg px-3 py-2 focus:border-cyan-500 focus:outline-none"
          >
            <option value="">All Types</option>
            {DEVICE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
            className="bg-slate-800 border border-slate-700 text-slate-100 text-sm rounded-lg px-3 py-2 focus:border-cyan-500 focus:outline-none"
          >
            <option value="">All Categories</option>
            {DEVICE_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c.charAt(0).toUpperCase() + c.slice(1)}
              </option>
            ))}
          </select>
          {(typeFilter || categoryFilter) && (
            <button
              type="button"
              onClick={() => {
                setTypeFilter("");
                setCategoryFilter("");
                setPage(1);
              }}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              ✕ Clear filters
            </button>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <p className="text-red-400 text-sm">Failed to load devices</p>
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 text-cyan-400 animate-spin" />
          </div>
        )}

        {/* Device Table */}
        {!isLoading && (
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-700 bg-slate-800/80">
                    <th className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">Name</th>
                    <th className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">Type</th>
                    <th className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">Category</th>
                    <th className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">Load</th>
                    <th className="text-left text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">Voltage</th>
                    <th className="text-right text-xs font-semibold text-slate-400 uppercase tracking-wider px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {devices.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center">
                        <Cpu className="h-12 w-12 text-slate-600 mx-auto mb-3" />
                        <p className="text-slate-400">No devices found</p>
                        <p className="text-xs text-slate-500 mt-1">
                          {typeFilter || categoryFilter
                            ? "Try changing your filters"
                            : "Add your first fire alarm device"}
                        </p>
                      </td>
                    </tr>
                  ) : (
                    devices.map((device: Device) => (
                      <tr
                        key={device.id}
                        className="hover:bg-slate-700/20 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <span className="text-slate-100 font-medium">
                            {device.name}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-700 text-slate-300">
                            {device.type.replace(/_/g, " ")}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs text-slate-500">
                            {device.category.charAt(0).toUpperCase() + device.category.slice(1)}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-300">
                          {device.load != null ? `${device.load.toFixed(3)} A` : "—"}
                        </td>
                        <td className="px-4 py-3 font-mono text-slate-300">
                          {device.voltage != null ? `${device.voltage} V` : "—"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              type="button"
                              onClick={() => setViewTarget(device)}
                              className="p-1.5 text-slate-500 hover:text-cyan-400 transition-colors rounded hover:bg-slate-700/50"
                              title="View Details"
                            >
                              <Eye className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditTarget(device)}
                              className="p-1.5 text-slate-500 hover:text-cyan-400 transition-colors rounded hover:bg-slate-700/50"
                              title="Edit"
                            >
                              <Pencil className="h-4 w-4" />
                            </button>
                            <button
                              type="button"
                              onClick={() => setDeleteTarget(device)}
                              className="p-1.5 text-slate-500 hover:text-red-400 transition-colors rounded hover:bg-slate-700/50"
                              title="Delete"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <p className="text-sm text-slate-500">
              Page {page} of {totalPages}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="px-3 py-1.5 bg-slate-700 text-slate-200 text-sm rounded-lg disabled:opacity-40 hover:bg-slate-600 transition-colors"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="px-3 py-1.5 bg-slate-700 text-slate-200 text-sm rounded-lg disabled:opacity-40 hover:bg-slate-600 transition-colors"
              >
                Next
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
