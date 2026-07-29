import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Zap, AlertTriangle, Settings, Thermometer,
  Wind, Activity, CheckCircle2, XCircle, AlertCircle,
} from "lucide-react";
import PhysicsGuardsMonitor, { GuardRule } from "@/components/engineering/PhysicsGuardsMonitor";

type Tab = "smoke" | "heat" | "battery" | "voltage" | "detectors" | "duct";

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

  const StatusIcon = status === "pass"
    ? CheckCircle2
    : status === "fail"
    ? XCircle
    : status === "warn"
    ? AlertCircle
    : null;

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

  const requiredDetectors = Math.ceil(roomArea / 900);
  const spacing = Math.sqrt(roomArea / requiredDetectors);
  const spacingStatus: GuardRule["status"] = spacing <= 30 && spacing >= 20 ? "pass" : spacing <= 35 ? "warn" : "fail";

  const guards: GuardRule[] = [
    { id: "s1", name: "Detector Spacing", description: "NFPA 72 Table 23.3.6 — max 30 ft", severity: "error", category: "spacing", min: 20, max: 30, currentValue: spacing, unit: "ft", status: spacingStatus },
    { id: "s2", name: "Ceiling Height", description: "Standard detectors: 8–12 ft", severity: "error", category: "smoke", min: 8, max: 50, currentValue: ceilingHeight, unit: "ft", status: ceilingHeight >= 8 ? "pass" : "fail" },
    { id: "s3", name: "Coverage Area", description: `${requiredDetectors} detectors × 900 sq ft`, severity: "warn", category: "smoke", status: "pass" },
  ];

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

  const standbyAh   = (standbyHours * deviceCount * currentDraw) / 1000;
  const alarmAh     = ((alarmMinutes / 60) * deviceCount * currentDraw) / 1000;
  const totalAh     = standbyAh + alarmAh;
  const marginAh    = totalAh * 1.2;

  const guards: GuardRule[] = [
    { id: "b1", name: "Alarm Duration Min.", description: "NFPA 72: Min 5 min alarm", severity: "error", category: "battery", min: 5, max: 60, currentValue: alarmMinutes, unit: "min", status: alarmMinutes >= 5 ? "pass" : "fail" },
    { id: "b2", name: "Safety Margin (20%)", description: "Required 20% safety factor", severity: "warn", category: "battery", status: "pass" },
    { id: "b3", name: "Total w/ Margin", description: `${marginAh.toFixed(2)} Ah required`, severity: "warn", category: "battery", status: "pass" },
  ];

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

  const resistance: Record<number, number> = { 14: 0.0025, 12: 0.00156, 10: 0.001, 8: 0.000625 };
  const rFt = resistance[wireGauge] ?? 0.0025;
  const vDrop = (2 * rFt * wireLength * current);
  const pctDrop = (vDrop / 12) * 100;
  const voltStatus: GuardRule["status"] = pctDrop <= 5 ? "pass" : pctDrop <= 7 ? "warn" : "fail";

  const guards: GuardRule[] = [
    { id: "v1", name: "Voltage Drop", description: "NFPA 72: Max 5% drop allowed", severity: "error", category: "voltage", min: 0, max: 5, currentValue: pctDrop, unit: "%", status: voltStatus },
  ];

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

      {/* Visual progress bar */}
      <div className="baz-panel p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[11px] font-medium text-[#6a6a80] uppercase tracking-wider">Drop vs. 5% NFPA Limit</span>
          <span className={`text-[11px] font-mono font-semibold ${voltStatus === "pass" ? "text-emerald-400" : voltStatus === "warn" ? "text-amber-400" : "text-red-400"}`}>
            {pctDrop.toFixed(2)}%
          </span>
        </div>
        <div className="h-1.5 bg-[#1a1a24] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              voltStatus === "pass" ? "bg-emerald-500" : voltStatus === "warn" ? "bg-amber-500" : "bg-red-500"
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

interface TabDef { id: Tab; label: string; icon: React.ElementType; }

const tabs: TabDef[] = [
  { id: "smoke",     label: "Smoke Spacing", icon: Wind        },
  { id: "heat",      label: "Heat Spacing",  icon: Thermometer },
  { id: "battery",   label: "Battery",       icon: Zap         },
  { id: "voltage",   label: "Voltage Drop",  icon: Activity    },
  { id: "detectors", label: "Detectors",     icon: AlertTriangle },
  { id: "duct",      label: "Duct Sizing",   icon: Settings    },
];

export const QOMNCalculatorPage: React.FC = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<Tab>("smoke");

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
        </div>

        {/* Tab bar */}
        <div className="mt-5 baz-tab-bar inline-flex overflow-x-auto">
          {tabs.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
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
        {activeTab === "battery" && <BatteryCalculator />}
        {activeTab === "voltage" && <VoltageDropCalculator />}
        {(activeTab === "heat" || activeTab === "detectors" || activeTab === "duct") && (
          <div className="flex flex-col items-center justify-center py-24 text-center anim-fade-in">
            <div className="w-10 h-10 rounded-lg bg-[#111118] border border-[#1e1e28] flex items-center justify-center mb-4">
              <Settings size={18} strokeWidth={1.5} className="text-[#3a3a50]" />
            </div>
            <h3 className="text-[14px] font-semibold text-[#4a4a60] mb-1">
              {tabs.find(t => t.id === activeTab)?.label}
            </h3>
            <p className="text-[12px] text-[#2a2a38]">Module under development</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default QOMNCalculatorPage;
