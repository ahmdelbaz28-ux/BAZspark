import React from "react";
import { CheckCircle2, XCircle, AlertCircle, ShieldCheck } from "lucide-react";

export interface GuardRule {
  id: string;
  name: string;
  description: string;
  severity: "info" | "warn" | "error";
  category: string;
  min?: number;
  max?: number;
  currentValue?: number;
  unit?: string;
  status: "pass" | "warn" | "fail";
}

interface PhysicsGuardsMonitorProps {
  rules: GuardRule[];
  compact?: boolean;
}

const STATUS_CFG = {
  pass: {
    Icon: CheckCircle2,
    text: "text-emerald-400",
    bg: "bg-emerald-500/5",
    badge: "bg-emerald-500/15 text-emerald-400",
    label: "Pass",
  },
  warn: {
    Icon: AlertCircle,
    text: "text-amber-400",
    bg: "bg-amber-500/5",
    badge: "bg-amber-500/15 text-amber-400",
    label: "Warn",
  },
  fail: {
    Icon: XCircle,
    text: "text-red-400",
    bg: "bg-red-500/5",
    badge: "bg-red-500/15 text-red-400",
    label: "Fail",
  },
};

const PhysicsGuardsMonitor: React.FC<PhysicsGuardsMonitorProps> = ({
  rules,
  compact = false,
}) => {
  const passes = rules.filter(r => r.status === "pass").length;
  const warns  = rules.filter(r => r.status === "warn").length;
  const fails  = rules.filter(r => r.status === "fail").length;
  const allOk  = fails === 0 && warns === 0;

  /* ---- Compact pill ---- */
  if (compact) {
    const cfg = fails > 0
      ? STATUS_CFG.fail
      : warns > 0
      ? STATUS_CFG.warn
      : STATUS_CFG.pass;
    const { Icon } = cfg;
    return (
      <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-semibold ${cfg.badge}`}>
        <Icon size={11} strokeWidth={2.5} />
        {fails > 0 ? `${fails} fail` : warns > 0 ? `${warns} warn` : "All pass"}
      </div>
    );
  }

  /* ---- Full view ---- */
  return (
    <div className="rounded-[5px] overflow-hidden border border-[#1a1a24] bg-[#0e0e14]">
      {/* Header row */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-[#1a1a24] bg-[#111118]">
        <div className="flex items-center gap-2">
          <ShieldCheck
            size={13}
            strokeWidth={2}
            className={allOk ? "text-emerald-400" : fails > 0 ? "text-red-400" : "text-amber-400"}
          />
          <span className="text-[11px] font-semibold uppercase tracking-widest text-[#8a8a9e]">
            Physics Guards
          </span>
          <span className="text-[10px] text-[#3a3a50]">NFPA 72</span>
        </div>
        <div className="flex items-center gap-2.5 text-[11px] font-mono">
          {passes > 0 && <span className="text-emerald-400">{passes}P</span>}
          {warns  > 0 && <span className="text-amber-400">{warns}W</span>}
          {fails  > 0 && <span className="text-red-400">{fails}F</span>}
        </div>
      </div>

      {/* Rule rows */}
      <div className="divide-y divide-[#111118]">
        {rules.map(rule => {
          const cfg = STATUS_CFG[rule.status];
          const { Icon } = cfg;
          const hasRange = rule.currentValue !== undefined && rule.min !== undefined && rule.max !== undefined;
          const pct = hasRange
            ? Math.max(0, Math.min(100, ((rule.currentValue! - rule.min!) / (rule.max! - rule.min!)) * 100))
            : 0;

          return (
            <div key={rule.id} className={`flex items-start gap-3 px-4 py-3 ${cfg.bg}`}>
              <Icon size={13} strokeWidth={2} className={`${cfg.text} mt-0.5 flex-shrink-0`} />

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[12px] font-medium text-[#c0c0cc]">{rule.name}</span>
                  {rule.currentValue !== undefined && (
                    <span className={`font-mono text-[11px] font-semibold ${cfg.text}`}>
                      {rule.currentValue.toFixed(2)}{rule.unit ? ` ${rule.unit}` : ""}
                    </span>
                  )}
                  {rule.min !== undefined && rule.max !== undefined && (
                    <span className="text-[10px] text-[#3a3a50] font-mono">
                      [{rule.min}–{rule.max}{rule.unit ? ` ${rule.unit}` : ""}]
                    </span>
                  )}
                </div>

                <p className="text-[11px] text-[#4a4a60] mt-0.5 leading-relaxed">{rule.description}</p>

                {/* Range progress bar */}
                {hasRange && (
                  <div className="mt-2 h-1 bg-[#1a1a28] rounded-full overflow-hidden w-full max-w-xs">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        rule.status === "fail" ? "bg-red-500" :
                        rule.status === "warn" ? "bg-amber-500" : "bg-emerald-500"
                      }`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                )}
              </div>

              <span className={`flex-shrink-0 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded ${cfg.badge}`}>
                {cfg.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PhysicsGuardsMonitor;
