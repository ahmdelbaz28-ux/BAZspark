/**
 * CADToolsPage.tsx — CAD/BIM Tooling Dashboard.
 *
 * Provides UI for all /cad router endpoints:
 *  - Connect/Disconnect (AutoCAD or Revit)
 *  - Connection status
 *  - Drawing operations: line, polyline, circle, text
 *  - File read/write
 *
 * Backend: backend/routers/cad.py (prefix: /cad)
 */
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  PenLine,
  Building2,
  Plug,
  PlugZap,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  Info,
  FileUp,
  FileDown,
  Square,
  Circle,
  Type,
  Minus,
} from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

type CADProvider = "autocad" | "revit";

interface CADStatus {
  connected: boolean;
  simulation_mode: boolean;
  provider?: string;
  [key: string]: unknown;
}

interface ConnectResult {
  success: boolean;
  message: string;
  connected: boolean;
  simulation_mode: boolean;
}

interface DrawResult {
  success: boolean;
  message: string;
  handle?: string;
}

interface ReadResult {
  success: boolean;
  element_count: number;
  elements: Array<{ handle: string; type: string; layer: string; [key: string]: unknown }>;
  filepath: string;
  provider: string;
}

interface WriteResult {
  success: boolean;
  message: string;
}

export const CADToolsPage: React.FC = () => {
  const [provider, setProvider] = useState<CADProvider>("autocad");
  const [status, setStatus] = useState<CADStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  // Drawing form state
  const [drawLineStart, setDrawLineStart] = useState("0,0,0");
  const [drawLineEnd, setDrawLineEnd] = useState("10,10,0");
  const [drawLineLayer, setDrawLineLayer] = useState("0");

  const [polyVertices, setPolyVertices] = useState("0,0,0\n10,0,0\n10,10,0\n0,10,0");
  const [polyLayer, setPolyLayer] = useState("0");
  const [polyClosed, setPolyClosed] = useState(true);

  const [circleCenter, setCircleCenter] = useState("5,5,0");
  const [circleRadius, setCircleRadius] = useState("5");
  const [circleLayer, setCircleLayer] = useState("0");

  const [textContent, setTextContent] = useState("CAD TOOLS");
  const [textInsertion, setTextInsertion] = useState("0,0,0");
  const [textHeight, setTextHeight] = useState("0.2");
  const [textLayer, setTextLayer] = useState("0");

  // File read/write state
  const [readFilepath, setReadFilepath] = useState("");
  const [writeFilepath, setWriteFilepath] = useState("");
  const [readResult, setReadResult] = useState<ReadResult | null>(null);
  const [activeTab, setActiveTab] = useState<"connect" | "draw" | "file">("connect");

  // Fetch status
  const statusMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE}/cad/status?provider=${provider}`, {
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<{ success: boolean; provider: string; status: CADStatus }>;
    },
    onSuccess: (data) => {
      setStatus(data.status);
      setStatusError(null);
    },
    onError: (err) => {
      setStatusError(err instanceof Error ? err.message : "Status check failed");
      setStatus(null);
    },
  });

  // Connect
  const connectMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE}/cad/connect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ provider, visible: true, force_new: false, method: "simulation" }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Connection failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json() as Promise<ConnectResult>;
    },
    onSuccess: (data) => {
      setStatus({ connected: data.connected, simulation_mode: data.simulation_mode });
      setStatusError(null);
    },
    onError: (err) => {
      setStatusError(err instanceof Error ? err.message : "Connection failed");
    },
  });

  // Disconnect
  const disconnectMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE}/cad/disconnect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ provider }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<DrawResult>;
    },
    onSuccess: () => {
      setStatus({ connected: false, simulation_mode: false });
    },
    onError: (err) => {
      setStatusError(err instanceof Error ? err.message : "Disconnect failed");
    },
  });

  // Draw line
  const drawLineMutation = useMutation({
    mutationFn: async () => {
      const [sx, sy, sz] = drawLineStart.split(",").map(Number);
      const [ex, ey, ez] = drawLineEnd.split(",").map(Number);
      const res = await fetch(`${API_BASE}/cad/draw_line`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          provider,
          start_point: [sx, sy, sz],
          end_point: [ex, ey, ez],
          layer: drawLineLayer,
          color: 256,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Draw failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json() as Promise<DrawResult>;
    },
  });

  // Draw polyline
  const drawPolylineMutation = useMutation({
    mutationFn: async () => {
      const vertices = polyVertices
        .split("\n")
        .filter(Boolean)
        .map((line) => line.split(",").map(Number));
      const res = await fetch(`${API_BASE}/cad/draw_polyline`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          provider,
          vertices,
          layer: polyLayer,
          color: 256,
          closed: polyClosed,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Draw failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json() as Promise<DrawResult>;
    },
  });

  // Draw circle
  const drawCircleMutation = useMutation({
    mutationFn: async () => {
      const [cx, cy, cz] = circleCenter.split(",").map(Number);
      const res = await fetch(`${API_BASE}/cad/draw_circle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          provider,
          center: [cx, cy, cz],
          radius: parseFloat(circleRadius) || 1,
          layer: circleLayer,
          color: 256,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Draw failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json() as Promise<DrawResult>;
    },
  });

  // Draw text
  const drawTextMutation = useMutation({
    mutationFn: async () => {
      const [ix, iy, iz] = textInsertion.split(",").map(Number);
      const res = await fetch(`${API_BASE}/cad/draw_text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          provider,
          text: textContent,
          insertion_point: [ix, iy, iz],
          height: parseFloat(textHeight) || 0.2,
          layer: textLayer,
          color: 256,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Draw failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json() as Promise<DrawResult>;
    },
  });

  // Read drawing
  const readMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${API_BASE}/cad/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ provider, filepath: readFilepath }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Read failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json() as Promise<ReadResult>;
    },
    onSuccess: (data) => setReadResult(data),
  });

  // Write drawing
  const writeMutation = useMutation({
    mutationFn: async () => {
      // Write requires elements from a prior read
      const res = await fetch(`${API_BASE}/cad/write`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({
          provider,
          filepath: writeFilepath,
          elements: readResult?.elements || [],
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Write failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json() as Promise<WriteResult>;
    },
  });

  const isConnected = status?.connected ?? false;
  const isSimulation = status?.simulation_mode ?? false;

  const tabs = [
    { key: "connect" as const, label: "Connection", icon: Plug },
    { key: "draw" as const, label: "Drawing Tools", icon: PenLine },
    { key: "file" as const, label: "File Read/Write", icon: FileUp },
  ];

  const CoordInput = ({
    label,
    value,
    onChange,
  }: {
    label: string;
    value: string;
    onChange: (v: string) => void;
  }) => (
    <div>
      <label className="block text-[11px] text-slate-500 mb-1 font-mono">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-2.5 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-100 text-xs font-mono focus:border-cyan-500 focus:outline-none"
        placeholder="x,y,z"
      />
    </div>
  );

  const ActionButton = ({
    mutation,
    label,
    icon: Icon,
    loadingLabel,
    disabled,
    color = "cyan",
  }: {
    mutation: { isPending: boolean; mutate: () => void; isError: boolean; isSuccess: boolean; error: Error | null; data: unknown; reset: () => void };
    label: string;
    icon: React.ElementType;
    loadingLabel: string;
    disabled?: boolean;
    color?: "cyan" | "emerald" | "amber";
  }) => {
    const colors = {
      cyan: "bg-cyan-600 hover:bg-cyan-700",
      emerald: "bg-emerald-600 hover:bg-emerald-700",
      amber: "bg-amber-600 hover:bg-amber-700",
    };
    return (
      <div>
        <button
          type="button"
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending || disabled}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 ${colors[color]} disabled:opacity-50 text-white text-xs font-medium rounded-lg transition-colors`}
        >
          {mutation.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Icon className="h-3.5 w-3.5" />
          )}
          {mutation.isPending ? loadingLabel : label}
        </button>
        {mutation.isError && (
          <p className="text-[11px] text-red-400 mt-1">
            {mutation.error instanceof Error ? mutation.error.message : "Failed"}
          </p>
        )}
        {mutation.isSuccess && mutation.data != null && (
          <p className="text-[11px] text-emerald-400 mt-1 flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3" />
            {(mutation.data as { message?: string })?.message || "Success"}
          </p>
        )}
      </div>
    );
  };

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <PenLine className="h-6 w-6 text-cyan-400" />
            CAD & BIM Tools
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Connect to AutoCAD or Revit, manage drawings, and execute CAD operations
          </p>
        </div>

        {/* Provider Selector + Status Bar */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            <div className="flex-1">
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Provider
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setProvider("autocad");
                    setStatus(null);
                  }}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    provider === "autocad"
                      ? "bg-cyan-600/20 text-cyan-300 border border-cyan-500/30"
                      : "bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-600"
                  }`}
                >
                  <PenLine className="h-4 w-4" />
                  AutoCAD
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setProvider("revit");
                    setStatus(null);
                  }}
                  className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    provider === "revit"
                      ? "bg-cyan-600/20 text-cyan-300 border border-cyan-500/30"
                      : "bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-600"
                  }`}
                >
                  <Building2 className="h-4 w-4" />
                  Revit
                </button>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Status indicator */}
              <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-lg border border-slate-700">
                <span
                  className={`h-2 w-2 rounded-full ${
                    isConnected ? "bg-emerald-400" : "bg-slate-500"
                  }`}
                />
                <span className="text-xs text-slate-400">
                  {isConnected
                    ? `Connected${isSimulation ? " (simulation)" : ""}`
                    : "Disconnected"}
                </span>
              </div>

              <ActionButton
                mutation={{
                  ...connectMutation,
                  isPending: connectMutation.isPending,
                  mutate: () => connectMutation.mutate(),
                  isError: connectMutation.isError,
                  error: connectMutation.error,
                  data: connectMutation.data,
                  reset: () => connectMutation.reset(),
                }}
                label="Connect"
                icon={Plug}
                loadingLabel="Connecting..."
                disabled={isConnected}
                color="emerald"
              />
              <ActionButton
                mutation={{
                  ...disconnectMutation,
                  isPending: disconnectMutation.isPending,
                  mutate: () => disconnectMutation.mutate(),
                  isError: disconnectMutation.isError,
                  error: disconnectMutation.error,
                  data: disconnectMutation.data,
                  reset: () => disconnectMutation.reset(),
                }}
                label="Disconnect"
                icon={PlugZap}
                loadingLabel="Disconnecting..."
                disabled={!isConnected}
                color="amber"
              />
              <button
                type="button"
                onClick={() => statusMutation.mutate()}
                disabled={statusMutation.isPending}
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded-lg transition-colors disabled:opacity-50"
                title="Refresh status"
              >
                <Loader2 className={`h-3.5 w-3.5 ${statusMutation.isPending ? "animate-spin" : ""}`} />
                Status
              </button>
            </div>
          </div>

          {/* Status error */}
          {statusError && (
            <div className="mt-3 bg-red-500/10 border border-red-500/30 rounded-lg p-2">
              <p className="text-xs text-red-400">{statusError}</p>
            </div>
          )}
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 flex-wrap">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? "bg-cyan-600/20 text-cyan-300 border border-cyan-500/30"
                    : "bg-slate-800/50 text-slate-400 hover:text-slate-200 border border-slate-700"
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Connection Tab */}
        {activeTab === "connect" && (
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <Info className="h-4 w-4 text-cyan-400" />
              Connection Information
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
              <div className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center">
                <div className="text-[10px] text-slate-500 mb-1">Provider</div>
                <div className="text-sm font-bold text-slate-100 font-mono uppercase">
                  {provider}
                </div>
              </div>
              <div className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center">
                <div className="text-[10px] text-slate-500 mb-1">Status</div>
                <span
                  className={`text-sm font-bold font-mono ${
                    isConnected ? "text-emerald-400" : "text-slate-500"
                  }`}
                >
                  {isConnected ? "Connected" : "Disconnected"}
                </span>
              </div>
              <div className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center">
                <div className="text-[10px] text-slate-500 mb-1">Mode</div>
                <div className="text-sm font-bold text-slate-100 font-mono">
                  {isSimulation ? "Simulation" : "Live"}
                </div>
              </div>
              <div className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center">
                <div className="text-[10px] text-slate-500 mb-1">Endpoint</div>
                <div className="text-[11px] font-bold text-cyan-300 font-mono truncate">
                  POST /cad/{isConnected ? "disconnect" : "connect"}
                </div>
              </div>
            </div>
            <div className="bg-slate-800/30 border border-slate-700/30 rounded-lg p-3">
              <p className="text-xs text-slate-500">
                <strong className="text-slate-400">Note:</strong> Connection uses
                simulation mode by default. Set{" "}
                <code className="text-cyan-300">visible=true</code> and{" "}
                <code className="text-cyan-300">method=simulation</code> to see the
                CAD application window (simulated). For real CAD connections, configure
                the provider path in CAD Settings.
              </p>
            </div>
          </div>
        )}

        {/* Drawing Tools Tab */}
        {activeTab === "draw" && (
          <div className="space-y-4">
            {/* Draw Line */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                <Minus className="h-4 w-4 text-cyan-400" />
                Draw Line
              </h3>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <CoordInput label="Start (x,y,z)" value={drawLineStart} onChange={setDrawLineStart} />
                <CoordInput label="End (x,y,z)" value={drawLineEnd} onChange={setDrawLineEnd} />
                <div>
                  <label className="block text-[11px] text-slate-500 mb-1 font-mono">Layer</label>
                  <input
                    type="text"
                    value={drawLineLayer}
                    onChange={(e) => setDrawLineLayer(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-100 text-xs font-mono focus:border-cyan-500 focus:outline-none"
                  />
                </div>
              </div>
              <ActionButton
                mutation={{
                  ...drawLineMutation,
                  mutate: () => drawLineMutation.mutate(),
                }}
                label="Draw Line"
                icon={Minus}
                loadingLabel="Drawing..."
                disabled={!isConnected}
              />
              {drawLineMutation.isSuccess && (
                <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Handle: {(drawLineMutation.data as DrawResult)?.handle || "N/A"}
                </p>
              )}
            </div>

            {/* Draw Polyline */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                <Square className="h-4 w-4 text-cyan-400" />
                Draw Polyline
              </h3>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label className="block text-[11px] text-slate-500 mb-1 font-mono">
                    Vertices (one per line: x,y,z)
                  </label>
                  <textarea
                    value={polyVertices}
                    onChange={(e) => setPolyVertices(e.target.value)}
                    rows={4}
                    className="w-full px-2.5 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-100 text-xs font-mono focus:border-cyan-500 focus:outline-none resize-none"
                  />
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="block text-[11px] text-slate-500 mb-1 font-mono">Layer</label>
                    <input
                      type="text"
                      value={polyLayer}
                      onChange={(e) => setPolyLayer(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-100 text-xs font-mono focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={polyClosed}
                      onChange={(e) => setPolyClosed(e.target.checked)}
                      className="rounded bg-slate-700 border-slate-600 text-cyan-500 focus:ring-cyan-500"
                    />
                    <span className="text-xs text-slate-400">Closed polyline</span>
                  </label>
                </div>
              </div>
              <ActionButton
                mutation={{
                  ...drawPolylineMutation,
                  mutate: () => drawPolylineMutation.mutate(),
                }}
                label="Draw Polyline"
                icon={Square}
                loadingLabel="Drawing..."
                disabled={!isConnected}
              />
              {drawPolylineMutation.isSuccess && (
                <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Handle: {(drawPolylineMutation.data as DrawResult)?.handle || "N/A"}
                </p>
              )}
            </div>

            {/* Draw Circle */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                <Circle className="h-4 w-4 text-cyan-400" />
                Draw Circle
              </h3>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <CoordInput label="Center (x,y,z)" value={circleCenter} onChange={setCircleCenter} />
                <div>
                  <label className="block text-[11px] text-slate-500 mb-1 font-mono">Radius</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={circleRadius}
                    onChange={(e) => setCircleRadius(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-100 text-xs font-mono focus:border-cyan-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[11px] text-slate-500 mb-1 font-mono">Layer</label>
                  <input
                    type="text"
                    value={circleLayer}
                    onChange={(e) => setCircleLayer(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-100 text-xs font-mono focus:border-cyan-500 focus:outline-none"
                  />
                </div>
              </div>
              <ActionButton
                mutation={{
                  ...drawCircleMutation,
                  mutate: () => drawCircleMutation.mutate(),
                }}
                label="Draw Circle"
                icon={Circle}
                loadingLabel="Drawing..."
                disabled={!isConnected}
              />
              {drawCircleMutation.isSuccess && (
                <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Handle: {(drawCircleMutation.data as DrawResult)?.handle || "N/A"}
                </p>
              )}
            </div>

            {/* Draw Text */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                <Type className="h-4 w-4 text-cyan-400" />
                Draw Text
              </h3>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <label className="block text-[11px] text-slate-500 mb-1 font-mono">Text</label>
                  <input
                    type="text"
                    value={textContent}
                    onChange={(e) => setTextContent(e.target.value)}
                    className="w-full px-2.5 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-100 text-xs font-mono focus:border-cyan-500 focus:outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] text-slate-500 mb-1 font-mono">Height</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      value={textHeight}
                      onChange={(e) => setTextHeight(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-100 text-xs font-mono focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-500 mb-1 font-mono">Layer</label>
                    <input
                      type="text"
                      value={textLayer}
                      onChange={(e) => setTextLayer(e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-slate-700 border border-slate-600 rounded text-slate-100 text-xs font-mono focus:border-cyan-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>
              <div className="mb-3">
                <CoordInput label="Insertion Point (x,y,z)" value={textInsertion} onChange={setTextInsertion} />
              </div>
              <ActionButton
                mutation={{
                  ...drawTextMutation,
                  mutate: () => drawTextMutation.mutate(),
                }}
                label="Draw Text"
                icon={Type}
                loadingLabel="Drawing..."
                disabled={!isConnected}
              />
              {drawTextMutation.isSuccess && (
                <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Handle: {(drawTextMutation.data as DrawResult)?.handle || "N/A"}
                </p>
              )}
            </div>
          </div>
        )}

        {/* File Read/Write Tab */}
        {activeTab === "file" && (
          <div className="space-y-4">
            {/* Read */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
                <FileDown className="h-4 w-4 text-cyan-400" />
                Read Drawing
              </h3>
              <div className="flex gap-3 mb-3">
                <div className="flex-1">
                  <label className="block text-[11px] text-slate-500 mb-1 font-mono">
                    File Path (.dwg, .dxf, .rvt, .rfa, .ifc)
                  </label>
                  <input
                    type="text"
                    value={readFilepath}
                    onChange={(e) => setReadFilepath(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
                    placeholder="/path/to/drawing.dwg"
                  />
                </div>
              </div>
              <ActionButton
                mutation={{
                  ...readMutation,
                  mutate: () => readMutation.mutate(),
                }}
                label="Read File"
                icon={FileDown}
                loadingLabel="Reading..."
                disabled={!isConnected || !readFilepath}
              />
              {readMutation.isSuccess && (
                <div className="mt-3 bg-slate-800 rounded-lg border border-slate-700/50 p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    <span className="text-sm text-slate-200 font-medium">
                      {readResult?.element_count || 0} elements found
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mb-2 font-mono truncate">
                    {readResult?.filepath}
                  </p>
                  {readResult && readResult.elements.length > 0 && (
                    <div className="max-h-40 overflow-y-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-slate-500 border-b border-slate-700">
                            <th className="text-left py-1 pr-2">Handle</th>
                            <th className="text-left py-1 pr-2">Type</th>
                            <th className="text-left py-1">Layer</th>
                          </tr>
                        </thead>
                        <tbody>
                          {readResult.elements.slice(0, 20).map((el, i) => (
                            <tr key={i} className="border-b border-slate-700/30 text-slate-400">
                              <td className="py-1 pr-2 font-mono">{el.handle}</td>
                              <td className="py-1 pr-2">{el.type}</td>
                              <td className="py-1">{el.layer}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {readResult.elements.length > 20 && (
                        <p className="text-[10px] text-slate-600 mt-1">
                          +{readResult.elements.length - 20} more elements
                        </p>
                      )}
                    </div>
                  )}
                  {/* Write after read */}
                  <div className="mt-4 pt-3 border-t border-slate-700/50">
                    <label className="block text-[11px] text-slate-500 mb-1 font-mono">
                      Write to File Path
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={writeFilepath}
                        onChange={(e) => setWriteFilepath(e.target.value)}
                        className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
                        placeholder="/path/to/output.dwg"
                      />
                      <ActionButton
                        mutation={{
                          ...writeMutation,
                          mutate: () => writeMutation.mutate(),
                        }}
                        label="Write"
                        icon={FileUp}
                        loadingLabel="Writing..."
                        disabled={!isConnected || !writeFilepath}
                        color="emerald"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Quick Info */}
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-medium text-amber-400 mb-1">
                    File Operations Require Connection
                  </p>
                  <p className="text-xs text-amber-300/70">
                    Connect to a provider (AutoCAD or Revit) before reading or writing
                    drawing files. Only .dwg, .dxf, .rvt, .rfa, and .ifc files
                    are allowed. File paths are validated against path traversal attacks.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Drawing Tools Info (always visible when draw tab) */}
        {activeTab === "draw" && !isConnected && (
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
            <div className="flex items-start gap-2">
              <Info className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
              <p className="text-xs text-amber-400">
                Connect to {provider === "autocad" ? "AutoCAD" : "Revit"} first to enable
                drawing tools. Use the Connection panel above to establish a connection.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CADToolsPage;
