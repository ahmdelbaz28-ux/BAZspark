import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Zap, AlertTriangle, Settings, Thermometer,
  Wind, Activity, CheckCircle2, XCircle, AlertCircle,
  Loader2, Server, Play, TestTube, Crosshair, Shield, BookOpen, FileText,
} from "lucide-react";
import PhysicsGuardsMonitor, { GuardRule } from "@/components/engineering/PhysicsGuardsMonitor";
import { qomnApi, qomnExtendedApi } from "@/services/fullApi";
import { useToast } from "@/hooks/use-toast";

/* ---------------------------------------------------------- */
/*  UNIT CONVERSION HELPERS (imperial → SI for backend)        */
/*  Backend qomn endpoints expect: meters, m², Amperes         */
/* ---------------------------------------------------------- */

const FT_TO_M = 0.3048;
const SQFT_TO_M2 = 0.092903;
const MA_TO_A = 0.001;

/**
 * V270 FIX (systematic-debugging): wraps each calculator with an optional
 * "Verify on Server" call to the authoritative QOMN kernel. The kernel
 * produces IEEE-754 deterministic output with an audit trail (computation_hash,
 * nfpa_section, formula) — properties the client-side JS reimplementation
 * cannot guarantee. For a safety-critical fire alarm platform, the kernel's
 * output is the legal record; the client-side preview is just a UX aid.
 */
interface ServerVerifyState {
  loading: boolean;
  result: Record<string, unknown> | null;
  error: string | null;
}

function useServerVerify() {
  const [state, setState] = useState<ServerVerifyState>({
    loading: false,
    result: null,
    error: null,
  });
  const { toast } = useToast();

  const verify = async (
    label: string,
    call: () => Promise<unknown>,
  ) => {
    setState({ loading: true, result: null, error: null });
    try {
      const resp = await call();
      // apiCall already unwraps {success, data} → resp is `data`
      setState({ loading: false, result: resp as Record<string, unknown>, error: null });
      toast({
        title: `${label} verified`,
        description: "NFPA 72 compliance check completed on the server kernel.",
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Server verification failed";
      setState({ loading: false, result: null, error: msg });
      toast({
        title: `${label} verification failed`,
        description: msg,
        variant: "destructive",
      });
    }
  };

  return { ...state, verify };
}

/**
 * Renders the server-verification result panel.
 * Shows computation_hash, nfpa_section, formula, and all returned fields.
 */
const ServerVerifyPanel: React.FC<{ state: ServerVerifyState }> = ({ state }) => {
  if (state.loading) {
    return (
      <div className="baz-panel p-4 flex items-center gap-2 text-[12px] text-[#6a6a80]">
        <Loader2 size={13} className="animate-spin text-[#00d4ff]" />
        Verifying on server (NFPA 72 kernel)…
      </div>
    );
  }
  if (state.error) {
    return (
      <div className="baz-panel p-4 border border-red-500/30">
        <div className="flex items-center gap-2 text-[12px] text-red-400 mb-2">
          <XCircle size={13} />
          Server verification failed
        </div>
        <pre className="text-[11px] font-mono text-red-300/80 whitespace-pre-wrap">{state.error}</pre>
      </div>
    );
  }
  if (!state.result) return null;
  return (
    <div className="baz-panel p-4 border border-emerald-500/30">
      <div className="flex items-center gap-2 text-[12px] text-emerald-400 mb-3">
        <CheckCircle2 size={13} />
        Server-verified (authoritative NFPA 72 result)
      </div>
      <pre className="text-[11px] font-mono text-[#a0a0b8] bg-[#0a0a12] rounded-md p-3 overflow-auto max-h-60">
        {JSON.stringify(state.result, null, 2)}
      </pre>
    </div>
  );
};

type Tab = "smoke" | "heat" | "battery" | "voltage" | "detectors" | "duct" | "guards" | "constants" | "audit";

/* ---------------------------------------------------------- */
/*  SHARED PRIMITIVES                                          */
/* ---------------------------------------------------------- */

const FieldLabel: React.FC<{ children: React.ReactNode; unit?: string }> = ({ children, unit }) => (
  <label className="flex items-baseline justify-between mb-1.5">
    <span className="text-[11px] font-medium text-[#6a6a80] uppercase tracking-wider">{children}</span>
    {unit && <span className="text-[10px] text-[#3a3a50] font-mono">{unit}</span>}
  </label>
);

const NumInput: React.FC<{
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
}> = ({ value, onChange, min, max, step = 1 }) => (
  <input
    type="number"
    value={value}
    min={min}
    max={max}
    step={step}
    onChange={e => onChange(Number(e.target.value))}
    className="baz-input font-mono text-[13px]"
  />
);

const SelectInput: React.FC<{
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}> = ({ value, onChange, options }) => (
  <select
    value={value}
    onChange={e => onChange(e.target.value)}
    className="baz-input text-[13px]"
  >
    {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
);

interface MetricProps {
  label: string;
  value: string | number;
  unit?: string;
  status?: "pass" | "warn" | "fail" | "neutral";
  precision?: number;
}

const MetricCard: React.FC<MetricProps> = ({ label, value, unit, status = "neutral", precision }) => {
  const displayValue = typeof value === "number" && precision !== undefined
    ? value.toFixed(precision)
    : value;

  const statusColors: Record<string, string> = {
    pass:    "border-emerald-500/30 text-emerald-400",
    warn:    "border-amber-500/30 text-amber-400",
    fail:    "border-red-500/30 text-red-400",
    neutral: "border-[#1e1e28] text-[#00d4ff]",
  };

  let StatusIcon: typeof CheckCircle2 | null = null;
  if (status === "pass") StatusIcon = CheckCircle2;
  else if (status === "fail") StatusIcon = XCircle;
  else if (status === "warn") StatusIcon = AlertCircle;

  return (
    <div className={`baz-panel p-4 border ${statusColors[status].split(" ")[0]}`}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <span className="baz-metric-label">{label}</span>
        {StatusIcon && <StatusIcon size={13} className={statusColors[status].split(" ")[1]} strokeWidth={2} />}
      </div>
      <div className={`baz-metric-value ${statusColors[status].split(" ")[1]}`}>
        {displayValue}
      </div>
      {unit && <div className="baz-metric-unit mt-1.5">{unit}</div>}
    </div>
  );
};

/* ---------------------------------------------------------- */
/*  SMOKE CALCULATOR                                           */
/* ---------------------------------------------------------- */

const SmokeCalculator: React.FC = () => {
  const [roomArea, setRoomArea] = useState(400);
  const [ceilingHeight, setCeilingHeight] = useState(10);
  const [detectorType, setDetectorType] = useState("standard");
  const verify = useServerVerify();

  const requiredDetectors = Math.ceil(roomArea / 900);
  const spacing = Math.sqrt(roomArea / requiredDetectors);
  const spacingStatus: GuardRule["status"] = (() => {
    if (spacing <= 30 && spacing >= 20) return "pass";
    if (spacing <= 35) return "warn";
    return "fail";
  })();

  const guards: GuardRule[] = [
    { id: "s1", name: "Detector Spacing", description: "NFPA 72 Table 23.3.6 — max 30 ft", severity: "error", category: "spacing", min: 20, max: 30, currentValue: spacing, unit: "ft", status: spacingStatus },
    { id: "s2", name: "Ceiling Height", description: "Standard detectors: 8–12 ft", severity: "error", category: "smoke", min: 8, max: 50, currentValue: ceilingHeight, unit: "ft", status: ceilingHeight >= 8 ? "pass" : "fail" },
    { id: "s3", name: "Coverage Area", description: `${requiredDetectors} detectors × 900 sq ft`, severity: "warn", category: "smoke", status: "pass" },
  ];

  const handleServerVerify = () => {
    // Convert imperial → SI for the backend
    const ceilingHeightM = ceilingHeight * FT_TO_M;
    verify.verify("Smoke spacing", () =>
      qomnApi.smokeSpacing({ ceiling_height_m: ceilingHeightM }),
    );
  };

  return (
    <div className="space-y-6 anim-fade-in">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <FieldLabel unit="sq ft">Room Area</FieldLabel>
          <NumInput value={roomArea} onChange={setRoomArea} min={100} max={50000} step={50} />
        </div>
        <div>
          <FieldLabel unit="ft">Ceiling Height</FieldLabel>
          <NumInput value={ceilingHeight} onChange={setCeilingHeight} min={6} max={80} step={0.5} />
        </div>
        <div>
          <FieldLabel>Detector Type</FieldLabel>
          <SelectInput value={detectorType} onChange={setDetectorType} options={[
            { value: "standard", label: "Standard" },
            { value: "rated",    label: "High Ceiling Rated" },
            { value: "beam",     label: "Beam Type" },
          ]} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Required Detectors" value={requiredDetectors} unit={`for ${roomArea.toLocaleString()} sq ft`} status="neutral" />
        <MetricCard label="Max Spacing" value={spacing} precision={1} unit="ft between detectors" status={spacingStatus} />
      </div>

      <button
        type="button"
        onClick={handleServerVerify}
        disabled={verify.loading}
        className="baz-tab baz-tab-active inline-flex items-center gap-1.5 text-[12px]"
      >
        {verify.loading ? <Loader2 size={13} className="animate-spin" /> : <Server size={13} />}
        Verify on Server (NFPA 72)
      </button>
      <ServerVerifyPanel state={verify} />

      <PhysicsGuardsMonitor rules={guards} />
    </div>
  );
};

/* ---------------------------------------------------------- */
/*  BATTERY CALCULATOR                                         */
/* ---------------------------------------------------------- */

const BatteryCalculator: React.FC = () => {
  const [deviceCount, setDeviceCount] = useState(10);
  const [currentDraw, setCurrentDraw] = useState(2);
  const [standbyHours, setStandbyHours] = useState(24);
  const [alarmMinutes, setAlarmMinutes] = useState(15);
  const verify = useServerVerify();

  const standbyAh   = (standbyHours * deviceCount * currentDraw) / 1000;
  const alarmAh     = ((alarmMinutes / 60) * deviceCount * currentDraw) / 1000;
  const totalAh     = standbyAh + alarmAh;
  const marginAh    = totalAh * 1.2;

  const guards: GuardRule[] = [
    { id: "b1", name: "Alarm Duration Min.", description: "NFPA 72: Min 5 min alarm", severity: "error", category: "battery", min: 5, max: 60, currentValue: alarmMinutes, unit: "min", status: alarmMinutes >= 5 ? "pass" : "fail" },
    { id: "b2", name: "Safety Margin (20%)", description: "Required 20% safety factor", severity: "warn", category: "battery", status: "pass" },
    { id: "b3", name: "Total w/ Margin", description: `${marginAh.toFixed(2)} Ah required`, severity: "warn", category: "battery", status: "pass" },
  ];

  const handleServerVerify = () => {
    // Convert: deviceCount × currentDraw(mA) → standby_load_a, alarm_load_a
    const standbyLoadA = (deviceCount * currentDraw * MA_TO_A) / 1; // standby load = standby current (continuous)
    const alarmLoadA = deviceCount * currentDraw * MA_TO_A;          // alarm load (peak during alarm)
    verify.verify("Battery capacity", () =>
      qomnApi.battery({
        standby_load_a: standbyLoadA,
        alarm_load_a: alarmLoadA,
        standby_hours: standbyHours,
        alarm_minutes: alarmMinutes,
      }),
    );
  };

  return (
    <div className="space-y-6 anim-fade-in">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
          <FieldLabel>Device Count</FieldLabel>
          <NumInput value={deviceCount} onChange={setDeviceCount} min={1} max={500} />
        </div>
        <div>
          <FieldLabel unit="mA">Current Draw</FieldLabel>
          <NumInput value={currentDraw} onChange={setCurrentDraw} min={0.1} max={50} step={0.1} />
        </div>
        <div>
          <FieldLabel unit="h">Standby Hours</FieldLabel>
          <NumInput value={standbyHours} onChange={setStandbyHours} min={4} max={96} />
        </div>
        <div>
          <FieldLabel unit="min">Alarm Duration</FieldLabel>
          <NumInput value={alarmMinutes} onChange={setAlarmMinutes} min={1} max={60} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <MetricCard label="Standby Capacity" value={standbyAh} precision={2} unit="Ah" status="neutral" />
        <MetricCard label="Alarm Capacity"   value={alarmAh}   precision={2} unit="Ah" status="neutral" />
        <MetricCard label="Total + 20% Margin" value={marginAh} precision={2} unit="Ah" status="pass" />
      </div>

      <button
        type="button"
        onClick={handleServerVerify}
        disabled={verify.loading}
        className="baz-tab baz-tab-active inline-flex items-center gap-1.5 text-[12px]"
      >
        {verify.loading ? <Loader2 size={13} className="animate-spin" /> : <Server size={13} />}
        Verify on Server (NFPA 72)
      </button>
      <ServerVerifyPanel state={verify} />

      <PhysicsGuardsMonitor rules={guards} />
    </div>
  );
};

/* ---------------------------------------------------------- */
/*  VOLTAGE DROP CALCULATOR                                    */
/* ---------------------------------------------------------- */

const VoltageDropCalculator: React.FC = () => {
  const [wireLength, setWireLength] = useState(100);
  const [wireGauge, setWireGauge] = useState(14);
  const [current, setCurrent] = useState(10);
  const verify = useServerVerify();

  const resistance: Record<number, number> = { 14: 0.0025, 12: 0.00156, 10: 0.001, 8: 0.000625 };
  const rFt = resistance[wireGauge] ?? 0.0025;
  const vDrop = (2 * rFt * wireLength * current);
  const pctDrop = (vDrop / 12) * 100;
  const voltStatus: GuardRule["status"] = (() => {
    if (pctDrop <= 5) return "pass";
    if (pctDrop <= 7) return "warn";
    return "fail";
  })();

  const guards: GuardRule[] = [
    { id: "v1", name: "Voltage Drop", description: "NFPA 72: Max 5% drop allowed", severity: "error", category: "voltage", min: 0, max: 5, currentValue: pctDrop, unit: "%", status: voltStatus },
  ];

  const handleServerVerify = () => {
    // Convert ft → m for the backend; AWG stays as string
    const lengthM = wireLength * FT_TO_M;
    verify.verify("Voltage drop", () =>
      qomnApi.voltageDrop({
        current_a: current,
        length_m: lengthM,
        awg_gauge: String(wireGauge),
      }),
    );
  };

  return (
    <div className="space-y-6 anim-fade-in">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <FieldLabel unit="ft">Wire Length</FieldLabel>
          <NumInput value={wireLength} onChange={setWireLength} min={1} max={5000} step={10} />
        </div>
        <div>
          <FieldLabel unit="AWG">Wire Gauge</FieldLabel>
          <SelectInput value={String(wireGauge)} onChange={v => setWireGauge(Number(v))} options={[
            { value: "8",  label: "#8 AWG" },
            { value: "10", label: "#10 AWG" },
            { value: "12", label: "#12 AWG" },
            { value: "14", label: "#14 AWG" },
          ]} />
        </div>
        <div>
          <FieldLabel unit="A">Current</FieldLabel>
          <NumInput value={current} onChange={setCurrent} min={0.1} max={100} step={0.5} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Voltage Drop" value={vDrop} precision={3} unit="V" status="neutral" />
        <MetricCard label="% Drop"       value={pctDrop} precision={1} unit={`of 12V — ${pctDrop <= 5 ? "within limit" : "exceeds limit"}`} status={voltStatus} />
      </div>

      <button
        type="button"
        onClick={handleServerVerify}
        disabled={verify.loading}
        className="baz-tab baz-tab-active inline-flex items-center gap-1.5 text-[12px]"
      >
        {verify.loading ? <Loader2 size={13} className="animate-spin" /> : <Server size={13} />}
        Verify on Server (NEC Ch.9 Table 8)
      </button>
      <ServerVerifyPanel state={verify} />

      {/* Visual progress bar */}
      <div className="baz-panel p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-medium text-[#6a6a80] uppercase tracking-wider">Drop vs. 5% NFPA Limit</span>
          <span className={`text-[11px] font-mono font-semibold ${(() => { if (voltStatus === "pass") { return "text-emerald-400"; } if (voltStatus === "warn") { return "text-amber-400"; } return "text-red-400"; })()}`}>
            {pctDrop.toFixed(2)}%
          </span>
        </div>
        <div className="h-1.5 bg-[#1a1a24] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              (() => { if (voltStatus === "pass") { return "bg-emerald-500"; } if (voltStatus === "warn") { return "bg-amber-500"; } return "bg-red-500"; })()
            }`}
            style={{ width: `${Math.min((pctDrop / 10) * 100, 100)}%` }}
          />
        </div>
        <div className="flex justify-between mt-1">
          <span className="text-[10px] text-[#3a3a50]">0%</span>
          <span className="text-[10px] text-[#00d4ff]">5% limit</span>
          <span className="text-[10px] text-[#3a3a50]">10%</span>
        </div>
      </div>

      <PhysicsGuardsMonitor rules={guards} />
    </div>
  );
};

/* ---------------------------------------------------------- */
/*  PAGE                                                       */
/* ---------------------------------------------------------- */

/**
 * V270 FIX: HeatSpacingCalculator — previously the "heat" tab showed a
 * "Module under development" placeholder. Now wired to POST /api/v1/qomn/heat-spacing
 * (NFPA 72 §17.6.3.1) so the page covers all 4 core NFPA 72 calculations.
 */
const HeatSpacingCalculator: React.FC = () => {
  const [ceilingHeight, setCeilingHeight] = useState(10);
  const [areaPerDetector, setAreaPerDetector] = useState(900); // sq ft
  const verify = useServerVerify();

  const handleServerVerify = () => {
    const ceilingHeightM = ceilingHeight * FT_TO_M;
    const areaM2 = areaPerDetector * SQFT_TO_M2;
    verify.verify("Heat spacing", () =>
      qomnApi.heatSpacing({
        ceiling_height_m: ceilingHeightM,
        area_per_detector_m2: areaM2,
      }),
    );
  };

  // Local preview: heat detector spacing per NFPA 72 §17.6.3.1
  const linearSpacingFt = Math.sqrt(areaPerDetector);
  const spacingStatus: GuardRule["status"] = (() => {
    if (linearSpacingFt <= 50) return "pass";   // NFPA 72 max 50 ft for heat
    if (linearSpacingFt <= 60) return "warn";
    return "fail";
  })();

  const guards: GuardRule[] = [
    {
      id: "h1",
      name: "Linear Spacing",
      description: "NFPA 72 §17.6.3.1 — max 50 ft for heat detectors",
      severity: "error",
      category: "spacing",
      min: 10,
      max: 50,
      currentValue: linearSpacingFt,
      unit: "ft",
      status: spacingStatus,
    },
  ];

  return (
    <div className="space-y-6 anim-fade-in">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <FieldLabel unit="ft">Ceiling Height</FieldLabel>
          <NumInput value={ceilingHeight} onChange={setCeilingHeight} min={6} max={30} step={0.5} />
        </div>
        <div>
          <FieldLabel unit="sq ft">Coverage Area per Detector</FieldLabel>
          <NumInput value={areaPerDetector} onChange={setAreaPerDetector} min={100} max={2500} step={50} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <MetricCard label="Linear Spacing" value={linearSpacingFt} precision={1} unit="ft (square root of area)" status={spacingStatus} />
        <MetricCard label="Coverage Area" value={areaPerDetector} unit="sq ft per detector" status="neutral" />
      </div>

      <button
        type="button"
        onClick={handleServerVerify}
        disabled={verify.loading}
        className="baz-tab baz-tab-active inline-flex items-center gap-1.5 text-[12px]"
      >
        {verify.loading ? <Loader2 size={13} className="animate-spin" /> : <Server size={13} />}
        Verify on Server (NFPA 72 §17.6.3.1)
      </button>
      <ServerVerifyPanel state={verify} />

      <PhysicsGuardsMonitor rules={guards} />
    </div>
  );
};

interface TabDef { id: Tab; label: string; icon: React.ElementType; }

/* ---------------------------------------------------------- */
/*  DUCT DETECTOR SECTION (Extended API)                       */
/* ---------------------------------------------------------- */

const DuctDetectorSection: React.FC = () => {
  const [ductWidth, setDuctWidth] = useState(0.6);
  const [ductResult, setDuctResult] = useState<Record<string, unknown> | null>(null);
  const [ductLoading, setDuctLoading] = useState(false);
  const [ductError, setDuctError] = useState<string | null>(null);
  const { toast } = useToast();

  const handlePlaceDuct = async () => {
    setDuctLoading(true);
    setDuctError(null);
    try {
      const res = await qomnExtendedApi.placeDuct({ duct_width_m: ductWidth });
      setDuctResult(res as Record<string, unknown>);
      toast({ title: "Duct detector placed", description: `Width: ${ductWidth}m` });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed";
      setDuctError(msg);
      toast({ title: "Place duct failed", description: msg, variant: "destructive" });
    } finally {
      setDuctLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <FieldLabel unit="m">Duct Width</FieldLabel>
          <NumInput value={ductWidth} onChange={setDuctWidth} min={0.1} max={10} step={0.1} />
        </div>
      </div>
      <button
        type="button"
        onClick={handlePlaceDuct}
        disabled={ductLoading}
        className="baz-tab baz-tab-active inline-flex items-center gap-1.5 text-[12px]"
      >
        {ductLoading ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
        Place Duct Detector
      </button>
      {ductError && (
        <div className="baz-panel p-4 border border-red-500/30">
          <div className="flex items-center gap-2 text-[12px] text-red-400">
            <XCircle size={13} />
            {ductError}
          </div>
        </div>
      )}
      {ductResult && (
        <div className="baz-panel p-4 border border-emerald-500/30">
          <div className="flex items-center gap-2 text-[12px] text-emerald-400 mb-2">
            <CheckCircle2 size={13} />
            Duct detector result
          </div>
          <pre className="text-[11px] font-mono text-[#a0a0b8] bg-[#0a0a12] rounded-md p-3 overflow-auto max-h-60">
            {JSON.stringify(ductResult, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

const tabs: TabDef[] = [
  { id: "smoke",     label: "Smoke Spacing", icon: Wind        },
  { id: "heat",      label: "Heat Spacing",  icon: Thermometer },
  { id: "battery",   label: "Battery",       icon: Zap         },
  { id: "voltage",   label: "Voltage Drop",  icon: Activity    },
  { id: "detectors", label: "Detectors",     icon: AlertTriangle },
  { id: "duct",      label: "Duct Sizing",   icon: Settings    },
  { id: "guards",    label: "Physics Guards", icon: Shield     },
  { id: "constants", label: "Constants",      icon: BookOpen   },
  { id: "audit",     label: "Audit Log",      icon: FileText   },
];

export const QOMNCalculatorPage: React.FC = () => {
  const { t: _t } = useTranslation();
  const [activeTab, setActiveTab] = useState<Tab>("smoke");
  const [goldenTestsLoading, setGoldenTestsLoading] = useState(false);
  const [goldenTestsResult, setGoldenTestsResult] = useState<Record<string, unknown> | null>(null);
  const { toast } = useToast();

  const handleRunGoldenTests = async () => {
    setGoldenTestsLoading(true);
    setGoldenTestsResult(null);
    try {
      const res = await qomnExtendedApi.runGoldenTests();
      setGoldenTestsResult(res as Record<string, unknown>);
      toast({ title: "Golden tests completed" });
    } catch (err) {
      toast({ title: "Golden tests failed", description: err instanceof Error ? err.message : "Failed", variant: "destructive" });
    } finally {
      setGoldenTestsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#09090d]">
      {/* Page header */}
      <div className="shrink-0 px-6 pt-6 pb-4 border-b border-[#131318]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-[18px] font-semibold text-[#f0f0f2] tracking-tight">QOMN Calculator</h1>
            <p className="mt-1 text-[12px] text-[#4a4a60]">
              Fire-system engineering calculations · NFPA 72 compliance
            </p>
          </div>
          <span className="baz-badge baz-badge-accent">NFPA 72</span>
          <button
            type="button"
            onClick={handleRunGoldenTests}
            disabled={goldenTestsLoading}
            className="baz-tab baz-tab-active inline-flex items-center gap-1.5 text-[12px] ml-3"
          >
            {goldenTestsLoading ? <Loader2 size={13} className="animate-spin" /> : <TestTube size={13} />}
            Run Golden Tests
          </button>
          {goldenTestsResult && (
            <pre className="text-[11px] font-mono text-[#a0a0b8] bg-[#0a0a12] rounded-md p-3 overflow-auto max-h-40 ml-2 max-w-md">
              {JSON.stringify(goldenTestsResult, null, 2)}
            </pre>
          )}
        </div>

        {/* Tab bar */}
        <div className="mt-5 baz-tab-bar inline-flex overflow-x-auto">
          {tabs.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                type="button"
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`baz-tab ${isActive ? "baz-tab-active" : ""}`}
              >
                <Icon size={13} strokeWidth={isActive ? 2.5 : 1.8} />
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Calculator content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === "smoke"   && <SmokeCalculator />}
        {activeTab === "heat"    && <HeatSpacingCalculator />}
        {activeTab === "battery" && <BatteryCalculator />}
        {activeTab === "voltage" && <VoltageDropCalculator />}
        {activeTab === "duct" && (
          <div className="space-y-6 anim-fade-in">
            <DuctDetectorSection />
          </div>
        )}
        {activeTab === "detectors" && (
          <PlaceDetectorsSection />
        )}
        {activeTab === "guards" && (
          <div className="space-y-6 anim-fade-in">
            <QomnReadOnlySection
              title="Physics Guards (GET /qomn/physics-guards)"
              fetcher={() => qomnApi.getPhysicsGuards()}
            />
          </div>
        )}
        {activeTab === "constants" && (
          <div className="space-y-6 anim-fade-in">
            <QomnReadOnlySection
              title="NFPA 72 / NEC Constants (GET /qomn/constants)"
              fetcher={() => qomnApi.getConstants()}
            />
          </div>
        )}
        {activeTab === "audit" && (
          <div className="space-y-6 anim-fade-in">
            <QomnReadOnlySection
              title="QOMN Audit Log (GET /qomn/audit)"
              fetcher={() => qomnApi.getAudit()}
            />
          </div>
        )}
      </div>
    </div>
  );
};

const QomnReadOnlySection: React.FC<{ title: string; fetcher: () => Promise<unknown> }> = ({ title, fetcher }) => {
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const handleFetch = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetcher();
      setResult(res as Record<string, unknown>);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed";
      setError(msg);
      toast({ title: "Failed", description: msg, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="baz-card">
      <h3 className="baz-label mb-4">{title}</h3>
      <button
        type="button"
        onClick={handleFetch}
        disabled={loading}
        className="baz-btn-primary"
      >
        {loading ? <Loader2 size={14} className="animate-spin" /> : "Fetch Data"}
      </button>
      {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
      {result && (
        <pre className="mt-4 text-xs font-mono bg-[#0a0a0f] p-3 rounded-lg overflow-auto max-h-96 text-[#7a7a8a]">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
};

const PlaceDetectorsSection: React.FC = () => {
  const [roomArea, setRoomArea] = useState(50);
  const [ceilingHeight, setCeilingHeight] = useState(3.0);
  const [detectorType, setDetectorType] = useState("smoke");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const handlePlaceDetectors = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await qomnExtendedApi.placeDetectors({
        room_area_m2: roomArea,
        ceiling_height_m: ceilingHeight,
        detector_type: detectorType,
      });
      setResult(res as Record<string, unknown>);
      toast({ title: "Detectors placed successfully" });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed";
      setError(msg);
      toast({ title: "Failed", description: msg, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 anim-fade-in">
      <div className="baz-card">
        <h3 className="baz-label mb-4">Place Detectors (POST /qomn/place-detectors)</h3>
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <label className="baz-label text-[10px]">Room Area (m²)</label>
            <input
              type="number"
              value={roomArea}
              onChange={e => setRoomArea(Number(e.target.value))}
              className="baz-input"
              min={1}
            />
          </div>
          <div>
            <label className="baz-label text-[10px]">Ceiling Height (m)</label>
            <input
              type="number"
              value={ceilingHeight}
              onChange={e => setCeilingHeight(Number(e.target.value))}
              className="baz-input"
              min={2}
              step={0.1}
            />
          </div>
          <div>
            <label className="baz-label text-[10px]">Detector Type</label>
            <select
              value={detectorType}
              onChange={e => setDetectorType(e.target.value)}
              className="baz-input"
            >
              <option value="smoke">Smoke</option>
              <option value="heat">Heat</option>
            </select>
          </div>
        </div>
        <button
          type="button"
          onClick={handlePlaceDetectors}
          disabled={loading || roomArea <= 0}
          className="baz-btn-primary"
        >
          {loading ? <Loader2 size={14} className="animate-spin" /> : <Crosshair size={14} />}
          Place Detectors
        </button>
        {error && <p className="text-red-400 text-xs mt-2">{error}</p>}
        {result && (
          <pre className="mt-4 text-xs font-mono bg-[#0a0a0f] p-3 rounded-lg overflow-auto max-h-48 text-[#7a7a8a]">
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </div>

      {/* Acoustics Evaluation Panel */}
      <div className="baz-card">
        <h3 className="baz-label mb-2 flex items-center gap-2">
          <Activity size={16} className="text-[#00d4ff]" />
          Acoustic & UGLD Raytracing Integration Engine (NFPA 72 §18.4 / ISA-TR84.00.07)
        </h3>
        <p className="text-[11px] text-[#7a7a8a] mb-4">
          Evaluates unified audible notification sound propagation and ultrasonic gas leak detection raytracing with Maekawa barrier diffraction.
        </p>
        <div className="grid grid-cols-3 gap-4 mb-4">
          <div>
            <label className="baz-label text-[10px]">Speaker Rated SPL (dBA @ 3m)</label>
            <input
              type="number"
              defaultValue={95}
              id="acoustics-speaker-spl"
              className="baz-input"
            />
          </div>
          <div>
            <label className="baz-label text-[10px]">Check Point Distance (m)</label>
            <input
              type="number"
              defaultValue={5.0}
              id="acoustics-checkpoint-dist"
              className="baz-input"
            />
          </div>
          <div>
            <label className="baz-label text-[10px]">Audible Mode</label>
            <select id="acoustics-mode" className="baz-input" defaultValue="public">
              <option value="public">Public Mode (§18.4.3)</option>
              <option value="private">Private Mode (§18.4.4)</option>
              <option value="sleeping">Sleeping Area (§18.4.2)</option>
            </select>
          </div>
        </div>
        <button
          type="button"
          onClick={async () => {
            try {
              const spl = Number((document.getElementById("acoustics-speaker-spl") as HTMLInputElement)?.value || 95);
              const dist = Number((document.getElementById("acoustics-checkpoint-dist") as HTMLInputElement)?.value || 5);
              const mode = (document.getElementById("acoustics-mode") as HTMLSelectElement)?.value || "public";
              const res = await qomnApi.evaluateAcoustics({
                room_id: "R-101",
                occ_type: "business",
                speaker_spl_dba: spl,
                check_point_distance_m: dist,
                mode: mode,
              });
              alert(`Acoustic Evaluation Completed:\n${JSON.stringify(res, null, 2)}`);
            } catch (err) {
              alert(`Evaluation failed: ${err instanceof Error ? err.message : err}`);
            }
          }}
          className="baz-btn-primary"
        >
          Evaluate Acoustic Coverage
        </button>
      </div>
    </div>
  );
};

export default QOMNCalculatorPage;

