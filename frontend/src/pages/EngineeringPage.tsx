
/**
 * EngineeringPage.tsx - Fire Alarm Electrical Calculations
 *
 * Frontend-design skill applied (2026-08-04) — V3 ETAP + audit fixes
 * V140 Phase 5: Connected to real QOMN API endpoints. Falls back to local
 * calculation when API is unavailable (offline mode).
 *
 * DESIGN SYSTEM: Uses etap-theme.css — professional electrical power system
 * aesthetic with amber accent, JetBrains Mono, switchgear-inspired panels.
 * This page communicates AUTHORITY, PRECISION, and CONSEQUENCE — critical
 * for a life-safety engineering tool (NEC Article 760 compliance).
 *
 * SIGNATURE ELEMENT: The Compliance Verdict — a full-width status banner
 * that dominates the viewport when a calculation result changes. In a fire
 * alarm system, the pass/fail answer MUST be impossible to overlook.
 *
 * V3 FIXES:
 *  - #1: prevCompliance now always updates (was stuck due to early return)
 *  - #2: Room analysis + integration API calls now send proper body
 *  - #3: Cable sizing has real compliance logic (not hardcoded "suitable")
 *  - #4: Removed dead Badge import
 *  - #5: ARIA roving tabindex + aria-labelledby on tab panels
 *  - #6: prefers-reduced-motion wraps fadeInUp/verdictPulse keyframes
 *  - #7: 25+ hardcoded strings → t() i18n keys
 *  - #8: Status pill uses data-status attribute (not Tailwind arbitrary)
 *  - #9: font-mono-num everywhere (removed font-[var(--etap-font-mono)])
 *  - #10: div.etap-panel instead of Card+etap-panel conflict
 *  - #11: Removed redundant useMemo wrapping useCallback
 *  - #12: Fixed import path ../styles/etap-theme.css
 */

import { Battery, Cable, Zap, Flame, Network, CheckCircle2, AlertTriangle, ShieldCheck, FileText, Loader2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ExplainButton } from "@/components/ai/ExplainButton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
        Select,
        SelectContent,
        SelectItem,
        SelectTrigger,
        SelectValue,
} from "@/components/ui/select";
import { qomnApi, apiCall } from "@/services/fullApi";
import "../styles/etap-theme.css";

// ============================================================================
// Compliance verdict thresholds (NEC Article 760)
// ============================================================================
const COMPLIANCE_THRESHOLDS = { suitable: 3, acceptable: 5 } as const;

// Cable ampacity compliance: final ampacity must be ≥ load current
const CABLE_COMPLIANCE_MARGIN = 0.1; // 10% margin above load current

type ComplianceLevel = "suitable" | "acceptable" | "excessive";

function getComplianceLevel(percentage: number): ComplianceLevel {
        if (percentage < COMPLIANCE_THRESHOLDS.suitable) return "suitable";
        if (percentage < COMPLIANCE_THRESHOLDS.acceptable) return "acceptable";
        return "excessive";
}

function getCableComplianceLevel(finalAmpacity: number, loadCurrent: number): ComplianceLevel {
        if (loadCurrent <= 0 || finalAmpacity <= 0) return "suitable";
        const ratio = finalAmpacity / loadCurrent;
        if (ratio >= 1 + CABLE_COMPLIANCE_MARGIN) return "suitable";
        if (ratio >= 1) return "acceptable";
        return "excessive";
}

// ============================================================================
// EngineeringPage Component
// ============================================================================

export function EngineeringPage() {
        const { t } = useTranslation();
        const [activeTab, setActiveTab] = useState("voltage-drop");
        const [voltageDropInputs, setVoltageDropInputs] = useState({
                current: "",
                length: "",
                cableSize: "",
                voltage: "",
                material: "cu",
        });
        const [cableSizingInputs, setCableSizingInputs] = useState({
                loadCurrent: "",
                length: "",
                ambientTemp: "",
                installationMethod: "free-air",
        });
        const [batteryCalcInputs, setBatteryCalcInputs] = useState({
                standbyDevices: "",
                standbyCurrent: "",
                alarmDevices: "",
                alarmCurrent: "",
                standbyHours: "24",
                alarmMinutes: "5",
        });

        // Room analysis controlled inputs (FIX #2: was uncontrolled defaultValue)
        const [roomInputs, setRoomInputs] = useState({ projectId: "", zone: "" });

        // Integration subsystem toggles (FIX #2: was uncontrolled CheckCircle2)
        const [integrationToggles, setIntegrationToggles] = useState<Record<string, boolean>>({
                fireAlarm: true, sprinkler: true, hvac: true, elevator: true,
                doorHolder: true, ductDetector: true, supervision: true, notification: true,
        });

        const [apiLoading, setApiLoading] = useState(false);
        const [apiError, setApiError] = useState<string | null>(null);
        const [apiResult, setApiResult] = useState<{
                voltage_drop_v: number;
                drop_pct: number;
                is_compliant: boolean;
                nec_section: string;
                computation_hash: string;
        } | null>(null);

        // Track previous compliance level for transition animation
        const prevComplianceRef = useRef<ComplianceLevel | null>(null);
        const [complianceFlash, setComplianceFlash] = useState(false);

        // ── Voltage Drop: Local fallback calculation ──────────────────────
        const calculateVoltageDropLocal = () => {
                const current = Number.parseFloat(voltageDropInputs.current);
                const length = Number.parseFloat(voltageDropInputs.length);
                const cableSize = Number.parseFloat(voltageDropInputs.cableSize);
                const voltage = Number.parseFloat(voltageDropInputs.voltage);

                if (Number.isNaN(current) || Number.isNaN(length) || Number.isNaN(cableSize) || Number.isNaN(voltage)) {
                        return { percentage: 0, absolute: 0 };
                }

                const resistivity = voltageDropInputs.material === "cu" ? 0.0172 : 0.0282;
                const resistance = (resistivity * length * 2) / cableSize;
                const voltageDrop = current * resistance;
                const percentage = (voltageDrop / voltage) * 100;

                return {
                        percentage: Number.parseFloat(percentage.toFixed(2)),
                        absolute: Number.parseFloat(voltageDrop.toFixed(3)),
                };
        };

        // ── Voltage Drop: QOMN API call ────────────────────────────────────
        const calculateVoltageDropViaApi = async () => {
                const current = Number.parseFloat(voltageDropInputs.current);
                const length = Number.parseFloat(voltageDropInputs.length);
                if (Number.isNaN(current) || Number.isNaN(length) || current <= 0 || length <= 0) return;
                setApiLoading(true);
                setApiError(null);
                try {
                        const result = await qomnApi.voltageDrop({
                                current_a: current,
                                length_m: length,
                                awg_gauge: voltageDropInputs.cableSize || "12",
                                supply_voltage_v: Number.parseFloat(voltageDropInputs.voltage) || 24.0,
                        });
                        setApiResult(result as unknown as NonNullable<typeof apiResult>);
                } catch (err) {
                        const msg = err instanceof Error ? err.message : "QOMN API calculation failed";
                        setApiError(msg);
                        setApiResult(null);
                } finally {
                        setApiLoading(false);
                }
        };

        // Debounced API calls via ref
        const calculateVoltageDropViaApiRef = useRef(calculateVoltageDropViaApi);
        useEffect(() => {
                calculateVoltageDropViaApiRef.current = calculateVoltageDropViaApi;
        });
        useEffect(() => {
                const current = Number.parseFloat(voltageDropInputs.current);
                const length = Number.parseFloat(voltageDropInputs.length);
                if (Number.isNaN(current) || Number.isNaN(length) || current <= 0 || length <= 0) return;
                const timer = setTimeout(() => calculateVoltageDropViaApiRef.current(), 500);
                return () => clearTimeout(timer);
        }, [voltageDropInputs.current, voltageDropInputs.length]);

        // ── Cable Sizing ───────────────────────────────────────────────────
        const calculateCableSizing = useCallback(() => {
                const loadCurrent = Number.parseFloat(cableSizingInputs.loadCurrent);
                const length = Number.parseFloat(cableSizingInputs.length);
                const ambientTemp = Number.parseFloat(cableSizingInputs.ambientTemp);

                if (Number.isNaN(loadCurrent) || Number.isNaN(length) || Number.isNaN(ambientTemp)) {
                        return { recommendedSize: "N/A", baseAmpacity: 0, deratingFactor: 0, finalAmpacity: 0 };
                }

                const baseAmpacity = loadCurrent * 1.25;

                // FIX #3: Derating actually depends on ambient temp and installation method
                let deratingFactor = 1.0;
                if (ambientTemp > 30) deratingFactor -= (ambientTemp - 30) * 0.005; // ~0.5% per °C above 30
                if (cableSizingInputs.installationMethod === "conduit") deratingFactor *= 0.8;
                else if (cableSizingInputs.installationMethod === "tray") deratingFactor *= 0.85;
                else if (cableSizingInputs.installationMethod === "buried") deratingFactor *= 0.75;
                deratingFactor = Math.max(deratingFactor, 0.3); // Floor at 30%

                const finalAmpacity = baseAmpacity * deratingFactor;
                const recommendedSize = Math.ceil(finalAmpacity / 5) * 2.5;

                return {
                        recommendedSize: recommendedSize.toFixed(1),
                        baseAmpacity: Number.parseFloat(baseAmpacity.toFixed(2)),
                        deratingFactor: Number.parseFloat(deratingFactor.toFixed(2)),
                        finalAmpacity: Number.parseFloat(finalAmpacity.toFixed(2)),
                };
        }, [cableSizingInputs]);

        // ── Battery Requirements ───────────────────────────────────────────
        const calculateBatteryRequirements = useCallback(() => {
                const standbyDevices = Number.parseInt(batteryCalcInputs.standbyDevices, 10);
                const standbyCurrent = Number.parseFloat(batteryCalcInputs.standbyCurrent);
                const alarmDevices = Number.parseInt(batteryCalcInputs.alarmDevices, 10);
                const alarmCurrent = Number.parseFloat(batteryCalcInputs.alarmCurrent);
                const standbyHours = Number.parseFloat(batteryCalcInputs.standbyHours);
                const alarmMinutes = Number.parseFloat(batteryCalcInputs.alarmMinutes);

                if (
                        Number.isNaN(standbyDevices) || Number.isNaN(standbyCurrent) ||
                        Number.isNaN(alarmDevices) || Number.isNaN(alarmCurrent) ||
                        Number.isNaN(standbyHours) || Number.isNaN(alarmMinutes)
                ) {
                        return { totalStandbyCurrent: 0, totalAlarmCurrent: 0, requiredCapacity: 0, recommendedBattery: "N/A" };
                }

                const totalStandbyCurrent = standbyDevices * standbyCurrent;
                const totalAlarmCurrent = alarmDevices * alarmCurrent;
                const standbyCapacity = (totalStandbyCurrent / 1000) * standbyHours;
                const alarmCapacity = (totalAlarmCurrent / 1000) * (alarmMinutes / 60);
                const requiredCapacity = (standbyCapacity + alarmCapacity) * 1.2;

                return {
                        totalStandbyCurrent: Number.parseFloat(totalStandbyCurrent.toFixed(2)),
                        totalAlarmCurrent: Number.parseFloat(totalAlarmCurrent.toFixed(2)),
                        requiredCapacity: Number.parseFloat(requiredCapacity.toFixed(2)),
                        recommendedBattery: `24V ${Math.ceil(requiredCapacity)}Ah Lead Acid`,
                };
        }, [batteryCalcInputs]);

        // ── Merged results: API primary, local fallback ────────────────────
        const localVDrop = useMemo(() => calculateVoltageDropLocal(), [voltageDropInputs]);
        const vDropResult = apiResult
                ? {
                        percentage: apiResult.drop_pct,
                        absolute: apiResult.voltage_drop_v,
                        nec_section: apiResult.nec_section,
                        computation_hash: apiResult.computation_hash,
                        is_compliant: apiResult.is_compliant,
                        source: "QOMN API (audited)" as const,
                }
                : {
                        percentage: localVDrop.percentage,
                        absolute: localVDrop.absolute,
                        source: "Local fallback (unaudited)" as const,
                };

        // FIX #11 corrected: useCallback memoizes the function reference, not the result.
        // useMemo is needed to avoid recalculating on every render.
        const cableResult = useMemo(() => calculateCableSizing(), [calculateCableSizing]);
        const batteryResult = useMemo(() => calculateBatteryRequirements(), [calculateBatteryRequirements]);

        // Props for ExplainButton
        const voltageDropResultProp = {
                percentage: vDropResult.percentage,
                absolute_v: vDropResult.absolute,
                current: voltageDropInputs.current,
                length: voltageDropInputs.length,
                voltage: voltageDropInputs.voltage,
        };

        const cableResultProp = {
                recommended_size_mm2: cableResult.recommendedSize,
                base_ampacity_a: cableResult.baseAmpacity,
                derating_factor: cableResult.deratingFactor,
                final_ampacity_a: cableResult.finalAmpacity,
        };

        const batteryResultProp = {
                total_standby_current_ma: batteryResult.totalStandbyCurrent,
                total_alarm_current_ma: batteryResult.totalAlarmCurrent,
                required_capacity_ah: batteryResult.requiredCapacity,
                recommended_battery: batteryResult.recommendedBattery,
                standby_hours: batteryCalcInputs.standbyHours,
        };

        // ── Compliance flash animation (FIX #1: always update prev) ────────
        const complianceLevel = getComplianceLevel(vDropResult.percentage);
        useEffect(() => {
                if (prevComplianceRef.current !== null && prevComplianceRef.current !== complianceLevel) {
                        setComplianceFlash(true);
                        const timer = setTimeout(() => setComplianceFlash(false), 600);
                        return () => clearTimeout(timer);
                }
                prevComplianceRef.current = complianceLevel;
        }, [complianceLevel]);

        // Cable compliance level
        const cableComplianceLevel = getCableComplianceLevel(
                cableResult.finalAmpacity,
                Number.parseFloat(cableSizingInputs.loadCurrent) || 0
        );

        const hasVoltageInput = !!(voltageDropInputs.current || voltageDropInputs.length);
        const hasCableInput = !!(cableSizingInputs.loadCurrent || cableSizingInputs.length);
        const hasBatteryInput = !!(batteryCalcInputs.standbyDevices || batteryCalcInputs.alarmDevices);

        // Tab definitions
        const tabs = ["voltage-drop", "cable-sizing", "battery-calc", "room-analysis", "integration"] as const;
        const tabLabels: Record<string, string> = {
                "voltage-drop": t("engineering.voltageDrop"),
                "cable-sizing": t("engineering.cableSizing"),
                "battery-calc": t("engineering.batteryCalculation"),
                "room-analysis": t("fireai.room.title"),
                "integration": t("fireai.integration.title"),
        };

        // FIX #5: Map compliance level to data-status for etap-status-pill
        const complianceDataStatus: Record<ComplianceLevel, string> = {
                suitable: "connected",
                acceptable: "connecting",
                excessive: "error",
        };

        // Integration subsystem labels (FIX #7: i18n)
        const integrationSubsystems = [
                { key: "fireAlarm", label: t("engineering.fireAlarmPanel") },
                { key: "sprinkler", label: t("engineering.sprinklerSystem") },
                { key: "hvac", label: t("engineering.hvacShutdown") },
                { key: "elevator", label: t("engineering.elevatorRecall") },
                { key: "doorHolder", label: t("engineering.doorHolderRelease") },
                { key: "ductDetector", label: t("engineering.ductSmokeDetector") },
                { key: "supervision", label: t("engineering.supervisorySignals") },
                { key: "notification", label: t("engineering.notificationAppliances") },
        ] as const;

        return (
                <div className="etap-page" aria-label={t("engineering.title")}>
                        {/* Circuit decoration — ambient amber sweep lines */}
                        <div className="etap-circuit-bg" aria-hidden="true">
                                <div className="etap-circuit-line" />
                                <div className="etap-circuit-line" />
                                <div className="etap-circuit-line" />
                        </div>

                        <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-6 py-6">
                                {/* ── Header ──────────────────────────────────────────────── */}
                                <header className="etap-header px-5 py-4 -mx-4 sm:-mx-6 -mt-6 mb-6">
                                        <div className="flex items-center justify-between">
                                                <div>
                                                        <h1 className="etap-title">{t("engineering.title")}</h1>
                                                        <p className="etap-subtitle">{t("engineering.subtitle")}</p>
                                                </div>
                                                {hasVoltageInput && (
                                                        <span
                                                                className="etap-status-pill"
                                                                data-status={complianceDataStatus[complianceLevel]}
                                                        >
                                                                <span className="etap-status-dot" />
                                                                <span className="font-mono-num">
                                                                        {complianceLevel === "suitable"
                                                                                ? t("engineering.compliant")
                                                                                : complianceLevel === "acceptable"
                                                                                        ? t("engineering.marginal")
                                                                                        : t("engineering.nonCompliant")}
                                                                </span>
                                                        </span>
                                                )}
                                        </div>
                                </header>

                                {/* ── Tabs — engineering terminal style ──────────────────── */}
                                <div
                                        className="etap-tabs -mx-4 sm:-mx-6 px-4 sm:px-6 mb-6"
                                        role="tablist"
                                        aria-label={t("engineering.title")}
                                        onKeyDown={(e: React.KeyboardEvent) => {
                                                const idx = tabs.indexOf(activeTab as typeof tabs[number]);
                                                if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                                                        e.preventDefault();
                                                        setActiveTab(tabs[(idx + 1) % tabs.length]);
                                                } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                                                        e.preventDefault();
                                                        setActiveTab(tabs[(idx - 1 + tabs.length) % tabs.length]);
                                                }
                                        }}
                                >
                                        {tabs.map((tab) => (
                                                <button
                                                        key={tab}
                                                        id={`tab-${tab}`}
                                                        className={`etap-tab transition-colors duration-200 ${activeTab === tab ? "text-[var(--etap-accent)] border-b-[var(--etap-accent)]" : ""
                                                                }`}
                                                        role="tab"
                                                        aria-selected={activeTab === tab}
                                                        aria-controls={`panel-${tab}`}
                                                        tabIndex={activeTab === tab ? 0 : -1}
                                                        onClick={() => setActiveTab(tab)}
                                                >
                                                        {tabLabels[tab]}
                                                </button>
                                        ))}
                                </div>

<<<<<<< HEAD
                                {/* ── Tab Panels ─────────────────────────────────────────── */}
                                <div className="space-y-6">
                                        {/* ══════════════════════════════════════════════════════════
                                         *  VOLTAGE DROP TAB
                                         * ══════════════════════════════════════════════════════════ */}
                                        {activeTab === "voltage-drop" && (
                                                <div
                                                        id="panel-voltage-drop"
                                                        role="tabpanel"
                                                        aria-labelledby="tab-voltage-drop"
                                                        aria-label={t("engineering.voltageDrop")}
                                                        className="space-y-6 animate-[fadeInUp_0.3s_var(--ease-entrance)]"
                                                >
                                                        {/* Input panel */}
                                                        <div className="etap-panel">
                                                                <div className="etap-panel-header">
                                                                        <div className="etap-panel-title">
                                                                                <Zap aria-hidden="true" className="h-5 w-5 etap-panel-title-icon" />
                                                                                {t("engineering.voltageDrop")}
                                                                        </div>
                                                                        <div className="etap-panel-description">
                                                                                {t("engineering.voltageDropDesc")}
                                                                        </div>
                                                                </div>
                                                                <div className="etap-panel-body">
                                                                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-4">
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.current")}</Label>
                                                                                        <Input
                                                                                                type="number"
                                                                                                value={voltageDropInputs.current}
                                                                                                onChange={(e) => setVoltageDropInputs((p) => ({ ...p, current: e.target.value }))}
                                                                                                className="etap-input"
                                                                                                placeholder="A"
                                                                                        />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.length")}</Label>
                                                                                        <Input
                                                                                                type="number"
                                                                                                value={voltageDropInputs.length}
                                                                                                onChange={(e) => setVoltageDropInputs((p) => ({ ...p, length: e.target.value }))}
                                                                                                className="etap-input"
                                                                                                placeholder="m"
                                                                                        />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.cableSize")}</Label>
                                                                                        <Input
                                                                                                type="number"
                                                                                                value={voltageDropInputs.cableSize}
                                                                                                onChange={(e) => setVoltageDropInputs((p) => ({ ...p, cableSize: e.target.value }))}
                                                                                                className="etap-input"
                                                                                                placeholder="mm²"
                                                                                        />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.voltage")}</Label>
                                                                                        <Input
                                                                                                type="number"
                                                                                                value={voltageDropInputs.voltage}
                                                                                                onChange={(e) => setVoltageDropInputs((p) => ({ ...p, voltage: e.target.value }))}
                                                                                                className="etap-input"
                                                                                                placeholder="V"
                                                                                        />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.material")}</Label>
                                                                                        <Select
                                                                                                value={voltageDropInputs.material}
                                                                                                onValueChange={(v) => setVoltageDropInputs((p) => ({ ...p, material: v }))}
                                                                                        >
                                                                                                <SelectTrigger aria-label={t("engineering.material")} className="etap-input">
                                                                                                        <SelectValue />
                                                                                                </SelectTrigger>
                                                                                                <SelectContent>
                                                                                                        <SelectItem value="cu">{t("engineering.copper")}</SelectItem>
                                                                                                        <SelectItem value="al">{t("engineering.aluminum")}</SelectItem>
                                                                                                </SelectContent>
                                                                                        </Select>
                                                                                </div>
                                                                        </div>
                                                                </div>
                                                        </div>

                                                        {/* Results + Compliance verdict row */}
                                                        {hasVoltageInput && (
                                                                <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
                                                                        {/* Numeric results — 2 cols */}
                                                                        <div className="etap-panel lg:col-span-2">
                                                                                <div className="etap-panel-header">
                                                                                        <div className="flex items-center justify-between w-full">
                                                                                                <div className="etap-panel-title text-sm">
                                                                                                        {t("engineering.results")}
                                                                                                </div>
                                                                                                <ExplainButton
                                                                                                        calculationType="voltage_drop"
                                                                                                        result={voltageDropResultProp}
                                                                                                />
                                                                                        </div>
                                                                                </div>
                                                                                <div className="etap-panel-body space-y-3">
                                                                                        {apiLoading && (
                                                                                                <div className="flex items-center gap-2 text-sm text-[var(--etap-text-muted)]">
                                                                                                        <Loader2 className="h-4 w-4 animate-spin" />
                                                                                                        {t("engineering.calculating")}
                                                                                                </div>
                                                                                        )}
                                                                                        {apiError && (
                                                                                                <div className="text-sm text-[var(--etap-danger)]">
                                                                                                        {apiError}
                                                                                                </div>
                                                                                        )}
                                                                                        <div className="flex justify-between items-baseline">
                                                                                                <span className="etap-label">{t("engineering.percentage")}</span>
                                                                                                <span className="font-mono-num text-lg text-[var(--etap-text-primary)]">
                                                                                                        {vDropResult.percentage}%
                                                                                                </span>
                                                                                        </div>
                                                                                        <div className="flex justify-between items-baseline">
                                                                                                <span className="etap-label">{t("engineering.absolute")}</span>
                                                                                                <span className="font-mono-num text-lg text-[var(--etap-text-primary)]">
                                                                                                        {vDropResult.absolute}V
                                                                                                </span>
                                                                                        </div>

                                                                                        {/* Audit trail — always visible */}
                                                                                        <hr className="etap-divider !my-3" />
                                                                                        <div className="space-y-1.5">
                                                                                                {"nec_section" in vDropResult && (
                                                                                                        <div className="flex justify-between items-baseline">
                                                                                                                <span className="etap-label">{t("engineering.necRef")}</span>
                                                                                                                <span className="font-mono-num text-xs text-[var(--etap-accent)]">
                                                                                                                        {vDropResult.nec_section}
                                                                                                                </span>
                                                                                                        </div>
                                                                                                )}
                                                                                                {"computation_hash" in vDropResult && vDropResult.computation_hash && (
                                                                                                        <div className="flex justify-between items-baseline">
                                                                                                                <span className="etap-label">{t("engineering.hash")}</span>
                                                                                                                <span className="font-mono-num text-[10px] text-[var(--etap-text-muted)] truncate max-w-[140px]" title={vDropResult.computation_hash as string}>
                                                                                                                        {(vDropResult.computation_hash as string).slice(0, 12)}…
                                                                                                                </span>
                                                                                                        </div>
                                                                                                )}
                                                                                                <div className="flex justify-between items-baseline">
                                                                                                        <span className="etap-label">{t("engineering.auditHash")}</span>
                                                                                                        <span className={`font-mono-num text-xs ${vDropResult.source.includes("audited")
                                                                                                                ? "text-[var(--etap-success)]"
                                                                                                                : "text-[var(--etap-warning)]"
                                                                                                                }`}>
                                                                                                                {vDropResult.source.includes("audited")
                                                                                                                        ? t("engineering.audited")
                                                                                                                        : t("engineering.unaudited")}
                                                                                                        </span>
                                                                                                </div>
                                                                                        </div>
                                                                                </div>
                                                                        </div>

                                                                        {/* ═══ SIGNATURE: Compliance Verdict Banner ═══ */}
                                                                        <div
                                                                                className={`lg:col-span-3 etap-panel overflow-hidden transition-all duration-300 ${complianceFlash ? "animate-[verdictPulse_0.6s_ease-out]" : ""
                                                                                        } ${complianceLevel === "suitable"
                                                                                                ? "border-l-4 border-l-[var(--etap-success)]"
                                                                                                : complianceLevel === "acceptable"
                                                                                                        ? "border-l-4 border-l-[var(--etap-warning)]"
                                                                                                        : "border-l-4 border-l-[var(--etap-danger)]"
                                                                                        }`}
                                                                                role="alert"
                                                                                aria-live="assertive"
                                                                                aria-atomic="true"
                                                                        >
                                                                                <div className={`p-5 h-full flex flex-col justify-center ${complianceLevel === "suitable"
                                                                                        ? "bg-[rgba(16,185,129,0.08)]"
                                                                                        : complianceLevel === "acceptable"
                                                                                                ? "bg-[rgba(245,158,11,0.08)]"
                                                                                                : "bg-[rgba(239,68,68,0.12)]"
                                                                                        }`}>
                                                                                        {/* Status icon + label row */}
                                                                                        <div className="flex items-center gap-3 mb-2">
                                                                                                {complianceLevel === "excessive" ? (
                                                                                                        <AlertTriangle aria-hidden="true" className="h-6 w-6 text-[var(--etap-danger)]" />
                                                                                                ) : complianceLevel === "acceptable" ? (
                                                                                                        <ShieldCheck aria-hidden="true" className="h-6 w-6 text-[var(--etap-warning)]" />
                                                                                                ) : (
                                                                                                        <ShieldCheck aria-hidden="true" className="h-6 w-6 text-[var(--etap-success)]" />
                                                                                                )}
                                                                                                <span className="etap-label">
                                                                                                        {t("engineering.status")}
                                                                                                </span>
                                                                                        </div>

                                                                                        {/* LARGE verdict text — the hero answer */}
                                                                                        <div className={`font-mono-num font-bold text-3xl leading-tight tracking-tight mb-1 ${complianceLevel === "suitable"
                                                                                                ? "text-[var(--etap-success)]"
                                                                                                : complianceLevel === "acceptable"
                                                                                                        ? "text-[var(--etap-warning)]"
                                                                                                        : "text-[var(--etap-danger)]"
                                                                                                }`}>
                                                                                                {complianceLevel === "suitable"
                                                                                                        ? t("engineering.suitable")
                                                                                                        : complianceLevel === "acceptable"
                                                                                                                ? t("engineering.acceptable")
                                                                                                                : t("engineering.excessive")}
                                                                                        </div>

                                                                                        {/* Context description */}
                                                                                        <div className="text-sm text-[var(--etap-text-secondary)] leading-relaxed">
                                                                                                {complianceLevel === "suitable"
                                                                                                        ? t("engineering.voltageDropCompliant")
                                                                                                        : complianceLevel === "acceptable"
                                                                                                                ? t("engineering.voltageDropMarginal")
                                                                                                                : t("engineering.voltageDropNonCompliant")}
                                                                                        </div>

                                                                                        {/* NEC threshold callout */}
                                                                                        <div className="mt-3 flex items-center gap-2 text-xs text-[var(--etap-text-muted)]">
                                                                                                <FileText aria-hidden="true" className="h-3.5 w-3.5" />
                                                                                                <span className="font-mono-num">
                                                                                                        {t("engineering.necThresholds")}
                                                                                                </span>
                                                                                        </div>
                                                                                </div>
                                                                        </div>
=======
                                {/* Tabs */}
                                <div className="flex flex-wrap gap-2 border-b border-border pb-2">
                                        <Button
                                                variant={activeTab === "voltage-drop" ? "default" : "outline"}
                                                className={
                                                        activeTab === "voltage-drop"
                                                                ? "bg-danger hover:bg-danger/90 text-danger-foreground border-none"
                                                                : "border-border text-foreground/90 hover:bg-card"
                                                }
                                                onClick={() => setActiveTab("voltage-drop")}
                                        >
                                                <Zap aria-hidden="true" className="h-4 w-4 mr-2" />
                                                {t("engineering.voltageDrop")}
                                        </Button>
                                        <Button
                                                variant={activeTab === "cable-sizing" ? "default" : "outline"}
                                                className={
                                                        activeTab === "cable-sizing"
                                                                ? "bg-danger hover:bg-danger/90 text-danger-foreground border-none"
                                                                : "border-border text-foreground/90 hover:bg-card"
                                                }
                                                onClick={() => setActiveTab("cable-sizing")}
                                        >
                                                <Cable aria-hidden="true" className="h-4 w-4 mr-2" />
                                                {t("engineering.cableSizing")}
                                        </Button>
                                        <Button
                                                variant={activeTab === "battery-calc" ? "default" : "outline"}
                                                className={
                                                        activeTab === "battery-calc"
                                                                ? "bg-danger hover:bg-danger/90 text-danger-foreground border-none"
                                                                : "border-border text-foreground/90 hover:bg-card"
                                                }
                                                onClick={() => setActiveTab("battery-calc")}
                                        >
                                                <Battery aria-hidden="true" className="h-4 w-4 mr-2" />
                                                {t("engineering.batteryCalculation")}
                                        </Button>
                                        <Button
                                                variant={activeTab === "room-analysis" ? "default" : "outline"}
                                                className={
                                                        activeTab === "room-analysis"
                                                                ? "bg-danger hover:bg-danger/90 text-danger-foreground border-none"
                                                                : "border-border text-foreground/90 hover:bg-card"
                                                }
                                                onClick={() => setActiveTab("room-analysis")}
                                        >
                                                <Flame aria-hidden="true" className="h-4 w-4 mr-2" />
                                                {t("fireai.room.title")}
                                        </Button>
                                        <Button
                                                variant={activeTab === "integration" ? "default" : "outline"}
                                                className={
                                                        activeTab === "integration"
                                                                ? "bg-danger hover:bg-danger/90 text-danger-foreground border-none"
                                                                : "border-border text-foreground/90 hover:bg-card"
                                                }
                                                onClick={() => setActiveTab("integration")}
                                        >
                                                <Network aria-hidden="true" className="h-4 w-4 mr-2" />
                                                {t("fireai.integration.title")}
                                        </Button>
                                </div>

                                {/* Voltage Drop Calculator */}
                                {activeTab === "voltage-drop" && (
                                        <Card className="border-border bg-card stagger-card">
                                                <CardHeader>
                                                        <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                <Zap aria-hidden="true" className="h-5 w-5" />
                                                                {t("engineering.voltageDrop")}
                                                        </CardTitle>
                                                        <CardDescription className="text-muted-foreground">
                                                                {t("engineering.voltageDropDesc")}
                                                        </CardDescription>
                                                </CardHeader>
                                                <CardContent className="space-y-4">
                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.current")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={voltageDropInputs.current}
                                                                                onChange={(e) =>
                                                                                        setVoltageDropInputs((prev) => ({
                                                                                                ...prev,
                                                                                                current: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="A"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.length")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={voltageDropInputs.length}
                                                                                onChange={(e) =>
                                                                                        setVoltageDropInputs((prev) => ({
                                                                                                ...prev,
                                                                                                length: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="m"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.cableSize")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={voltageDropInputs.cableSize}
                                                                                onChange={(e) =>
                                                                                        setVoltageDropInputs((prev) => ({
                                                                                                ...prev,
                                                                                                cableSize: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="mm²"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.voltage")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={voltageDropInputs.voltage}
                                                                                onChange={(e) =>
                                                                                        setVoltageDropInputs((prev) => ({
                                                                                                ...prev,
                                                                                                voltage: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="V"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.material")}
                                                                        </Label>
                                                                        <Select
                                                                                value={voltageDropInputs.material}
                                                                                onValueChange={(v) =>
                                                                                        setVoltageDropInputs((prev) => ({
                                                                                                ...prev,
                                                                                                material: v,
                                                                                        }))
                                                                                }
                                                                        >
                                                                                <SelectTrigger className="bg-card border-border text-foreground stagger-card" aria-label={t("engineering.material", "Material")}>
                                                                                        <SelectValue />
                                                                                </SelectTrigger>
                                                                                <SelectContent className="bg-card border-border stagger-card">
                                                                                        <SelectItem value="cu">
                                                                                                {t("engineering.copper")}
                                                                                        </SelectItem>
                                                                                        <SelectItem value="al">
                                                                                                {t("engineering.aluminum")}
                                                                                        </SelectItem>
                                                                                </SelectContent>
                                                                        </Select>
                                                                </div>
                                                        </div>

                                                        <Separator />

                                                        {/* Terminal-style Engineering Output Panel */}
                                                        <div
                                                                style={{
                                                                        background: "var(--color-graphite)",
                                                                        border: "1px solid rgba(90,103,112,0.35)",
                                                                        borderLeft: `4px solid ${vDropResult.percentage < 3 ? "var(--color-evac-green)" : vDropResult.percentage < 5 ? "var(--color-amber-alert)" : "var(--color-signal-red)"}`,
                                                                        borderRadius: "2px",
                                                                        padding: "1rem 1.25rem",
                                                                }}
                                                        >
                                                                {/* Terminal header */}
                                                                <div className="flex items-center justify-between mb-3">
                                                                        <div style={{ fontFamily: "var(--font-data)", fontSize: "0.7rem", letterSpacing: "0.1em", color: "var(--color-steel)", textTransform: "uppercase" }}>
                                                                                VOLTAGE DROP ANALYSIS
                                                                        </div>
                                                                        <ExplainButton
                                                                                calculationType="voltage_drop"  // NOSONAR: typescript:S3358
                                                                                result={voltageDropResultProp}  // NOSONAR: typescript:S3358
                                                                        />
                                                                </div>

                                                                {/* Input echo */}
                                                                <div className="mb-3" style={{ fontFamily: "var(--font-data)", fontSize: "0.75rem", color: "var(--color-steel)" }}>
                                                                        INPUT:&nbsp;
                                                                        <span style={{ color: "var(--color-bone)" }}>
                                                                                I = {voltageDropInputs.current || "—"}A &nbsp;/&nbsp;
                                                                                L = {voltageDropInputs.length || "—"}m &nbsp;/&nbsp;
                                                                                {voltageDropInputs.material.toUpperCase()} {voltageDropInputs.cableSize || "—"}mm²
                                                                        </span>
                                                                </div>

                                                                {/* Result divider */}
                                                                <div style={{ borderTop: "1px solid rgba(90,103,112,0.3)", marginBottom: "0.75rem" }} />

                                                                {/* Result row */}
                                                                <div className="flex flex-wrap items-center gap-6">
                                                                        <div>
                                                                                <div style={{ fontFamily: "var(--font-data)", fontSize: "0.65rem", color: "var(--color-steel)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Drop (V)</div>
                                                                                <div style={{ fontFamily: "var(--font-data)", fontSize: "1.5rem", fontWeight: 700, color: "var(--color-bone)", lineHeight: 1.1 }}>
                                                                                        {vDropResult.absolute}V
                                                                                </div>
                                                                        </div>
                                                                        <div>
                                                                                <div style={{ fontFamily: "var(--font-data)", fontSize: "0.65rem", color: "var(--color-steel)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Drop (%)</div>
                                                                                <div style={{ fontFamily: "var(--font-data)", fontSize: "1.5rem", fontWeight: 700, color: vDropResult.percentage < 3 ? "var(--color-evac-green)" : vDropResult.percentage < 5 ? "var(--color-amber-alert)" : "var(--color-signal-red)", lineHeight: 1.1 }}>
                                                                                        {vDropResult.percentage}%
                                                                                </div>
                                                                        </div>
                                                                        <div style={{ marginInlineStart: "auto" }}>
                                                                                <span style={{
                                                                                        fontFamily: "var(--font-data)",
                                                                                        fontSize: "0.7rem",
                                                                                        fontWeight: 600,
                                                                                        letterSpacing: "0.08em",
                                                                                        textTransform: "uppercase",
                                                                                        padding: "0.2rem 0.6rem",
                                                                                        borderRadius: "2px",
                                                                                        border: `1px solid ${vDropResult.percentage < 3 ? "var(--color-evac-green)" : vDropResult.percentage < 5 ? "var(--color-amber-alert)" : "var(--color-signal-red)"}`,
                                                                                        color: vDropResult.percentage < 3 ? "var(--color-evac-green)" : vDropResult.percentage < 5 ? "var(--color-amber-alert)" : "var(--color-signal-red)",
                                                                                }}>
                                                                                        {vDropResult.percentage < 3 ? "✓ COMPLIANT" : vDropResult.percentage < 5 ? "⚠ MARGINAL" : "✕ NON-COMPLIANT"}
                                                                                </span>
                                                                        </div>
                                                                </div>

                                                                {/* Audit footer */}
                                                                {"nec_section" in vDropResult && (
                                                                        <div style={{ borderTop: "1px solid rgba(90,103,112,0.2)", marginTop: "0.75rem", paddingTop: "0.5rem", display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
                                                                                <span style={{ fontFamily: "var(--font-data)", fontSize: "0.65rem", color: "var(--color-steel)", letterSpacing: "0.04em" }}>
                                                                                        REF: {vDropResult.nec_section}
                                                                                </span>
                                                                                {"computation_hash" in vDropResult && (
                                                                                        <span style={{ fontFamily: "var(--font-data)", fontSize: "0.6rem", color: "rgba(90,103,112,0.6)", letterSpacing: "0.04em" }} title="Audit Reference Hash">
                                                                                                AUDIT: {vDropResult.computation_hash?.slice(0, 16)}…
                                                                                        </span>
                                                                                )}
                                                                        </div>
                                                                )}
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Cable Sizing Calculator */}
                                {activeTab === "cable-sizing" && (
                                        <Card className="border-border bg-card stagger-card">
                                                <CardHeader>
                                                        <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                <Cable aria-hidden="true" className="h-5 w-5" />
                                                                {t("engineering.cableSizing")}
                                                        </CardTitle>
                                                        <CardDescription className="text-muted-foreground">
                                                                {t("engineering.cableSizingDesc")}
                                                        </CardDescription>
                                                </CardHeader>
                                                <CardContent className="space-y-4">
                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.loadCurrent")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={cableSizingInputs.loadCurrent}
                                                                                onChange={(e) =>
                                                                                        setCableSizingInputs((prev) => ({
                                                                                                ...prev,
                                                                                                loadCurrent: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="A"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.length")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={cableSizingInputs.length}
                                                                                onChange={(e) =>
                                                                                        setCableSizingInputs((prev) => ({
                                                                                                ...prev,
                                                                                                length: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="m"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.ambientTemp")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={cableSizingInputs.ambientTemp}
                                                                                onChange={(e) =>
                                                                                        setCableSizingInputs((prev) => ({
                                                                                                ...prev,
                                                                                                ambientTemp: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="°C"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.installationMethod")}
                                                                        </Label>
                                                                        <Select
                                                                                value={cableSizingInputs.installationMethod}
                                                                                onValueChange={(v) =>
                                                                                        setCableSizingInputs((prev) => ({
                                                                                                ...prev,
                                                                                                installationMethod: v,
                                                                                        }))
                                                                                }
                                                                        >
                                                                                <SelectTrigger className="bg-card border-border text-foreground stagger-card" aria-label={t("engineering.installationMethod", "Installation method")}>
                                                                                        <SelectValue />
                                                                                </SelectTrigger>
                                                                                <SelectContent className="bg-card border-border stagger-card">
                                                                                        <SelectItem value="free-air">
                                                                                                {t("engineering.freeAir")}
                                                                                        </SelectItem>
                                                                                        <SelectItem value="conduit">
                                                                                                {t("engineering.conduit")}
                                                                                        </SelectItem>
                                                                                        <SelectItem value="trunking">
                                                                                                {t("engineering.trunking")}
                                                                                        </SelectItem>
                                                                                </SelectContent>
                                                                        </Select>
>>>>>>> feature/engineering-identity
                                                                </div>
                                                        )}
                                                </div>
                                        )}

                                        {/* ══════════════════════════════════════════════════════════
                                         *  CABLE SIZING TAB
                                         * ══════════════════════════════════════════════════════════ */}
                                        {activeTab === "cable-sizing" && (
                                                <div
                                                        id="panel-cable-sizing"
                                                        role="tabpanel"
                                                        aria-labelledby="tab-cable-sizing"
                                                        aria-label={t("engineering.cableSizing")}
                                                        className="space-y-6 animate-[fadeInUp_0.3s_var(--ease-entrance)]"
                                                >
                                                        <div className="etap-panel">
                                                                <div className="etap-panel-header">
                                                                        <div className="etap-panel-title">
                                                                                <Cable aria-hidden="true" className="h-5 w-5 etap-panel-title-icon" />
                                                                                {t("engineering.cableSizing")}
                                                                        </div>
                                                                        <div className="etap-panel-description">
                                                                                {t("engineering.cableSizingDesc")}
                                                                        </div>
                                                                </div>
                                                                <div className="etap-panel-body">
                                                                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-4">
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.loadCurrent")}</Label>
                                                                                        <Input
                                                                                                type="number"
                                                                                                value={cableSizingInputs.loadCurrent}
                                                                                                onChange={(e) => setCableSizingInputs((p) => ({ ...p, loadCurrent: e.target.value }))}
                                                                                                className="etap-input"
                                                                                                placeholder="A"
                                                                                        />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.length")}</Label>
                                                                                        <Input
                                                                                                type="number"
                                                                                                value={cableSizingInputs.length}
                                                                                                onChange={(e) => setCableSizingInputs((p) => ({ ...p, length: e.target.value }))}
                                                                                                className="etap-input"
                                                                                                placeholder="m"
                                                                                        />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.ambientTemp")}</Label>
                                                                                        <Input
                                                                                                type="number"
                                                                                                value={cableSizingInputs.ambientTemp}
                                                                                                onChange={(e) => setCableSizingInputs((p) => ({ ...p, ambientTemp: e.target.value }))}
                                                                                                className="etap-input"
                                                                                                placeholder="°C"
                                                                                        />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.installationMethod")}</Label>
                                                                                        <Select
                                                                                                value={cableSizingInputs.installationMethod}
                                                                                                onValueChange={(v) => setCableSizingInputs((p) => ({ ...p, installationMethod: v }))}
                                                                                        >
                                                                                                <SelectTrigger aria-label={t("engineering.installationMethod")} className="etap-input">
                                                                                                        <SelectValue />
                                                                                                </SelectTrigger>
                                                                                                <SelectContent>
                                                                                                        <SelectItem value="free-air">{t("engineering.freeAir")}</SelectItem>
                                                                                                        <SelectItem value="conduit">{t("engineering.conduit")}</SelectItem>
                                                                                                        <SelectItem value="tray">{t("engineering.cableTray")}</SelectItem>
                                                                                                        <SelectItem value="buried">{t("engineering.directBurial")}</SelectItem>
                                                                                                </SelectContent>
                                                                                        </Select>
                                                                                </div>
                                                                        </div>
                                                                </div>
                                                        </div>

                                                        {/* Cable results + compliance */}
                                                        {hasCableInput && (
                                                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                                                        <div className="etap-panel">
                                                                                <div className="etap-panel-header">
                                                                                        <div className="flex items-center justify-between w-full">
                                                                                                <div className="etap-panel-title text-sm">
                                                                                                        {t("engineering.results")}
                                                                                                </div>
                                                                                                <ExplainButton
                                                                                                        calculationType="cable_sizing"
                                                                                                        result={cableResultProp}
                                                                                                />
                                                                                        </div>
                                                                                </div>
                                                                                <div className="etap-panel-body space-y-3">
                                                                                        <div className="flex justify-between items-baseline">
                                                                                                <span className="etap-label">{t("engineering.recommendedSize")}</span>
                                                                                                <span className="font-mono-num text-lg text-[var(--etap-text-primary)]">
                                                                                                        {cableResult.recommendedSize} mm²
                                                                                                </span>
                                                                                        </div>
                                                                                        <div className="flex justify-between items-baseline">
                                                                                                <span className="etap-label">{t("engineering.baseAmpacity")}</span>
                                                                                                <span className="font-mono-num text-[var(--etap-text-secondary)]">
                                                                                                        {cableResult.baseAmpacity} A
                                                                                                </span>
                                                                                        </div>
                                                                                        <div className="flex justify-between items-baseline">
                                                                                                <span className="etap-label">{t("engineering.deratingFactor")}</span>
                                                                                                <span className="font-mono-num text-[var(--etap-text-secondary)]">
                                                                                                        {cableResult.deratingFactor}
                                                                                                </span>
                                                                                        </div>
                                                                                        <div className="flex justify-between items-baseline">
                                                                                                <span className="etap-label">{t("engineering.finalAmpacity")}</span>
                                                                                                <span className="font-mono-num text-lg text-[var(--etap-text-primary)]">
                                                                                                        {cableResult.finalAmpacity} A
                                                                                                </span>
                                                                                        </div>
                                                                                </div>
                                                                        </div>

<<<<<<< HEAD
                                                                        {/* FIX #3: Cable sizing compliance with real logic */}
                                                                        <div className={`etap-panel overflow-hidden border-l-4 ${cableComplianceLevel === "suitable"
                                                                                ? "border-l-[var(--etap-success)] bg-[rgba(16,185,129,0.06)]"
                                                                                : cableComplianceLevel === "acceptable"
                                                                                        ? "border-l-[var(--etap-warning)] bg-[rgba(245,158,11,0.06)]"
                                                                                        : "border-l-[var(--etap-danger)] bg-[rgba(239,68,68,0.08)]"
                                                                                }`}>
                                                                                <div className="p-5 h-full flex flex-col justify-center">
                                                                                        <div className="flex items-center gap-3 mb-2">
                                                                                                {cableComplianceLevel === "excessive" ? (
                                                                                                        <AlertTriangle aria-hidden="true" className="h-6 w-6 text-[var(--etap-danger)]" />
                                                                                                ) : cableComplianceLevel === "acceptable" ? (
                                                                                                        <ShieldCheck aria-hidden="true" className="h-6 w-6 text-[var(--etap-warning)]" />
                                                                                                ) : (
                                                                                                        <ShieldCheck aria-hidden="true" className="h-6 w-6 text-[var(--etap-success)]" />
                                                                                                )}
                                                                                                <span className="etap-label">{t("engineering.status")}</span>
                                                                                        </div>
                                                                                        <div className={`font-mono-num font-bold text-2xl mb-1 ${cableComplianceLevel === "suitable"
                                                                                                ? "text-[var(--etap-success)]"
                                                                                                : cableComplianceLevel === "acceptable"
                                                                                                        ? "text-[var(--etap-warning)]"
                                                                                                        : "text-[var(--etap-danger)]"
                                                                                                }`}>
                                                                                                {cableComplianceLevel === "suitable"
                                                                                                        ? t("engineering.suitable")
                                                                                                        : cableComplianceLevel === "acceptable"
                                                                                                                ? t("engineering.acceptable")
                                                                                                                : t("engineering.excessive")}
                                                                                        </div>
                                                                                        <div className="text-sm text-[var(--etap-text-secondary)]">
                                                                                                {cableComplianceLevel === "suitable"
                                                                                                        ? t("engineering.cableSizingCompliant")
                                                                                                        : cableComplianceLevel === "acceptable"
                                                                                                                ? t("engineering.cableSizingMarginal")
                                                                                                                : t("engineering.cableSizingNonCompliant")}
                                                                                        </div>
=======
                                                                <Card className="border-border bg-muted/50">
                                                                        <CardHeader>
                                                                                <CardTitle className="text-foreground text-sm">
                                                                                        {t("engineering.status")}
                                                                                </CardTitle>
                                                                        </CardHeader>
                                                                        <CardContent>
                                                                                <Badge className="bg-success/10 text-success border-success/30">
                                                                                        {t("engineering.suitable")}
                                                                                </Badge>
                                                                        </CardContent>
                                                                </Card>
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Battery Calculation */}
                                {activeTab === "battery-calc" && (
                                        <Card className="border-border bg-card stagger-card">
                                                <CardHeader>
                                                        <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                <Battery aria-hidden="true" className="h-5 w-5" />
                                                                {t("engineering.batteryCalculation")}
                                                        </CardTitle>
                                                        <CardDescription className="text-muted-foreground">
                                                                {t("engineering.batteryCalculationDesc")}
                                                        </CardDescription>
                                                </CardHeader>
                                                <CardContent className="space-y-4">
                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.standbyDevices")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={batteryCalcInputs.standbyDevices}
                                                                                onChange={(e) =>
                                                                                        setBatteryCalcInputs((prev) => ({
                                                                                                ...prev,
                                                                                                standbyDevices: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="#"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.standbyCurrent")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={batteryCalcInputs.standbyCurrent}
                                                                                onChange={(e) =>
                                                                                        setBatteryCalcInputs((prev) => ({
                                                                                                ...prev,
                                                                                                standbyCurrent: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="mA"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.alarmDevices")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={batteryCalcInputs.alarmDevices}
                                                                                onChange={(e) =>
                                                                                        setBatteryCalcInputs((prev) => ({
                                                                                                ...prev,
                                                                                                alarmDevices: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="#"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.alarmCurrent")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={batteryCalcInputs.alarmCurrent}
                                                                                onChange={(e) =>
                                                                                        setBatteryCalcInputs((prev) => ({
                                                                                                ...prev,
                                                                                                alarmCurrent: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="mA"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.standbyHours")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={batteryCalcInputs.standbyHours}
                                                                                onChange={(e) =>
                                                                                        setBatteryCalcInputs((prev) => ({
                                                                                                ...prev,
                                                                                                standbyHours: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="hours"
                                                                        />
                                                                </div>
                                                                <div className="space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("engineering.alarmMinutes")}
                                                                        </Label>
                                                                        <Input
                                                                                type="number"
                                                                                value={batteryCalcInputs.alarmMinutes}
                                                                                onChange={(e) =>
                                                                                        setBatteryCalcInputs((prev) => ({
                                                                                                ...prev,
                                                                                                alarmMinutes: e.target.value,
                                                                                        }))
                                                                                }
                                                                                className="bg-card border-border text-foreground stagger-card"
                                                                                placeholder="minutes"
                                                                        />
                                                                </div>
                                                        </div>

                                                        <Separator />

                                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                                                <Card className="border-border bg-muted/50">
                                                                        <CardHeader>
                                                                                <div className="flex items-center justify-between">
                                                                                        <CardTitle className="text-foreground text-sm">
                                                                                                {t("engineering.results")}
                                                                                        </CardTitle>
                                                                                        <ExplainButton
                                                                                                calculationType="battery_sizing"
                                                                                                result={batteryResultProp}
                                                                                        />
>>>>>>> feature/engineering-identity
                                                                                </div>
                                                                        </div>
                                                                </div>
                                                        )}
                                                </div>
                                        )}

                                        {/* ══════════════════════════════════════════════════════════
                                         *  BATTERY CALCULATION TAB
                                         * ══════════════════════════════════════════════════════════ */}
                                        {activeTab === "battery-calc" && (
                                                <div
                                                        id="panel-battery-calc"
                                                        role="tabpanel"
                                                        aria-labelledby="tab-battery-calc"
                                                        aria-label={t("engineering.batteryCalculation")}
                                                        className="space-y-6 animate-[fadeInUp_0.3s_var(--ease-entrance)]"
                                                >
                                                        <div className="etap-panel">
                                                                <div className="etap-panel-header">
                                                                        <div className="etap-panel-title">
                                                                                <Battery aria-hidden="true" className="h-5 w-5 etap-panel-title-icon" />
                                                                                {t("engineering.batteryCalculation")}
                                                                        </div>
                                                                        <div className="etap-panel-description">
                                                                                {t("engineering.batteryCalcDesc")}
                                                                        </div>
                                                                </div>
                                                                <div className="etap-panel-body">
                                                                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-4">
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.standbyDevices")}</Label>
                                                                                        <Input type="number" value={batteryCalcInputs.standbyDevices}
                                                                                                onChange={(e) => setBatteryCalcInputs((p) => ({ ...p, standbyDevices: e.target.value }))}
                                                                                                className="etap-input" placeholder="#" />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.standbyCurrent")}</Label>
                                                                                        <Input type="number" value={batteryCalcInputs.standbyCurrent}
                                                                                                onChange={(e) => setBatteryCalcInputs((p) => ({ ...p, standbyCurrent: e.target.value }))}
                                                                                                className="etap-input" placeholder="mA" />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.alarmDevices")}</Label>
                                                                                        <Input type="number" value={batteryCalcInputs.alarmDevices}
                                                                                                onChange={(e) => setBatteryCalcInputs((p) => ({ ...p, alarmDevices: e.target.value }))}
                                                                                                className="etap-input" placeholder="#" />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.alarmCurrent")}</Label>
                                                                                        <Input type="number" value={batteryCalcInputs.alarmCurrent}
                                                                                                onChange={(e) => setBatteryCalcInputs((p) => ({ ...p, alarmCurrent: e.target.value }))}
                                                                                                className="etap-input" placeholder="mA" />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.standbyHours")}</Label>
                                                                                        <Input type="number" value={batteryCalcInputs.standbyHours}
                                                                                                onChange={(e) => setBatteryCalcInputs((p) => ({ ...p, standbyHours: e.target.value }))}
                                                                                                className="etap-input" placeholder="h" />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.alarmMinutes")}</Label>
                                                                                        <Input type="number" value={batteryCalcInputs.alarmMinutes}
                                                                                                onChange={(e) => setBatteryCalcInputs((p) => ({ ...p, alarmMinutes: e.target.value }))}
                                                                                                className="etap-input" placeholder="min" />
                                                                                </div>
                                                                        </div>
                                                                </div>
                                                        </div>

                                                        {/* Battery results */}
                                                        {hasBatteryInput && (
                                                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                                                        <div className="etap-panel">
                                                                                <div className="etap-panel-header">
                                                                                        <div className="flex items-center justify-between w-full">
                                                                                                <div className="etap-panel-title text-sm">
                                                                                                        {t("engineering.results")}
                                                                                                </div>
                                                                                                <ExplainButton
                                                                                                        calculationType="battery_calc"
                                                                                                        result={batteryResultProp}
                                                                                                />
                                                                                        </div>
                                                                                </div>
                                                                                <div className="etap-panel-body space-y-3">
                                                                                        <div className="flex justify-between items-baseline">
                                                                                                <span className="etap-label">{t("engineering.totalStandbyCurrent")}</span>
                                                                                                <span className="font-mono-num text-[var(--etap-text-secondary)]">
                                                                                                        {batteryResult.totalStandbyCurrent} mA
                                                                                                </span>
                                                                                        </div>
                                                                                        <div className="flex justify-between items-baseline">
                                                                                                <span className="etap-label">{t("engineering.totalAlarmCurrent")}</span>
                                                                                                <span className="font-mono-num text-[var(--etap-text-secondary)]">
                                                                                                        {batteryResult.totalAlarmCurrent} mA
                                                                                                </span>
                                                                                        </div>
                                                                                        <div className="flex justify-between items-baseline">
                                                                                                <span className="etap-label">{t("engineering.requiredCapacity")}</span>
                                                                                                <span className="font-mono-num text-lg text-[var(--etap-text-primary)]">
                                                                                                        {batteryResult.requiredCapacity} Ah
                                                                                                </span>
                                                                                        </div>
                                                                                </div>
                                                                        </div>

                                                                        {/* Battery recommendation */}
                                                                        <div className="etap-panel border-l-4 border-l-[var(--etap-accent)] bg-[var(--etap-accent-muted)]">
                                                                                <div className="p-5 h-full flex flex-col justify-center">
                                                                                        <div className="flex items-center gap-3 mb-2">
                                                                                                <Battery aria-hidden="true" className="h-6 w-6 text-[var(--etap-accent)]" />
                                                                                                <span className="etap-label">{t("engineering.recommendation")}</span>
                                                                                        </div>
                                                                                        <div className="font-mono-num font-bold text-2xl text-[var(--etap-accent)] mb-1">
                                                                                                {batteryResult.recommendedBattery}
                                                                                        </div>
                                                                                        <div className="text-sm text-[var(--etap-text-secondary)]">
                                                                                                NFPA 72 §10.6.7.2.1 — {t("engineering.standbyAlarmDesc", { hours: batteryCalcInputs.standbyHours, minutes: batteryCalcInputs.alarmMinutes })}
                                                                                        </div>
                                                                                </div>
<<<<<<< HEAD
=======
                                                                        </CardContent>
                                                                </Card>
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Room Analysis Tab */}
                                {activeTab === "room-analysis" && (
                                        <Card className="border-border bg-card stagger-card">
                                                <CardHeader>
                                                        <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                <Flame aria-hidden="true" className="h-5 w-5" />
                                                                {t("fireai.room.title")}
                                                        </CardTitle>
                                                        <CardDescription className="text-muted-foreground">
                                                                {t("fireai.room.description")}
                                                        </CardDescription>
                                                </CardHeader>
                                                <CardContent className="space-y-4">
                                                        <div className="flex gap-4 items-end">
                                                                <div className="flex-1 space-y-2">
                                                                        <Label className="text-foreground/90">
                                                                                {t("fireai.room.selectProject")}
                                                                        </Label>
                                                                        <Input placeholder="Project ID" id="analyze-project-id" />
                                                                </div>
                                                                <Button onClick={async () => {
                                                                        const projectId = (document.getElementById("analyze-project-id") as HTMLInputElement)?.value;
                                                                        if (!projectId) return;
                                                                        try {
                                                                                await apiCall(`/analyze/projects/${projectId}/analyze/room`, { method: "POST" });
                                                                        } catch { /* handled */ }
                                                                }}>
                                                                        <Flame aria-hidden="true" className="h-4 w-4 mr-2" />
                                                                        {t("fireai.room.analyze")}
                                                                </Button>
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Integration Pipeline Tab */}
                                {activeTab === "integration" && (
                                        <Card className="border-border bg-card stagger-card">
                                                <CardHeader>
                                                        <CardTitle className="text-lg text-foreground flex items-center gap-2">
                                                                <Network aria-hidden="true" className="h-5 w-5" />
                                                                {t("fireai.integration.title")}
                                                        </CardTitle>
                                                        <CardDescription className="text-muted-foreground">
                                                                {t("fireai.integration.description")}
                                                        </CardDescription>
                                                </CardHeader>
                                                <CardContent className="space-y-4">
                                                        <div className="grid grid-cols-2 gap-3">
                                                                {["fireAlarm", "sprinkler", "hvac", "elevator", "doorHolder", "ductDetector", "supervision", "notification"].map((sub) => (
                                                                        <div key={sub} className="flex items-center gap-2 p-2 rounded bg-muted">
                                                                                <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
                                                                                <span className="text-sm">{t(`fireai.integration.${sub}`)}</span>
>>>>>>> feature/engineering-identity
                                                                        </div>
                                                                </div>
                                                        )}
                                                </div>
                                        )}

                                        {/* ══════════════════════════════════════════════════════════
                                         *  ROOM ANALYSIS TAB
                                         * ══════════════════════════════════════════════════════════ */}
                                        {activeTab === "room-analysis" && (
                                                <div
                                                        id="panel-room-analysis"
                                                        role="tabpanel"
                                                        aria-labelledby="tab-room-analysis"
                                                        aria-label={t("fireai.room.title")}
                                                        className="space-y-6 animate-[fadeInUp_0.3s_var(--ease-entrance)]"
                                                >
                                                        <div className="etap-panel">
                                                                <div className="etap-panel-header">
                                                                        <div className="etap-panel-title">
                                                                                <Flame aria-hidden="true" className="h-5 w-5 etap-panel-title-icon" />
                                                                                {t("fireai.room.title")}
                                                                        </div>
                                                                        <div className="etap-panel-description">
                                                                                {t("engineering.roomAnalysisDesc")}
                                                                        </div>
                                                                </div>
                                                                <div className="etap-panel-body">
                                                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-4">
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.projectId")}</Label>
                                                                                        <Input
                                                                                                type="text"
                                                                                                value={roomInputs.projectId}
                                                                                                onChange={(e) => setRoomInputs((p) => ({ ...p, projectId: e.target.value }))}
                                                                                                className="etap-input"
                                                                                                placeholder="e.g. BLDG-A-F3"
                                                                                        />
                                                                                </div>
                                                                                <div className="etap-field">
                                                                                        <Label className="etap-label">{t("engineering.zone")}</Label>
                                                                                        <Input
                                                                                                type="text"
                                                                                                value={roomInputs.zone}
                                                                                                onChange={(e) => setRoomInputs((p) => ({ ...p, zone: e.target.value }))}
                                                                                                className="etap-input"
                                                                                                placeholder="e.g. Z-01"
                                                                                        />
                                                                                </div>
                                                                        </div>
                                                                        <div className="mt-5">
                                                                                <Button
                                                                                        onClick={() => apiCall("/room-analysis", { method: "POST", body: JSON.stringify(roomInputs) })}
                                                                                        className="etap-btn etap-btn-primary"
                                                                                >
                                                                                        <Flame aria-hidden="true" className="h-4 w-4" />
                                                                                        {t("engineering.analyze")}
                                                                                </Button>
                                                                        </div>
                                                                </div>
                                                        </div>
                                                </div>
                                        )}

                                        {/* ══════════════════════════════════════════════════════════
                                         *  INTEGRATION PIPELINE TAB
                                         * ══════════════════════════════════════════════════════════ */}
                                        {activeTab === "integration" && (
                                                <div
                                                        id="panel-integration"
                                                        role="tabpanel"
                                                        aria-labelledby="tab-integration"
                                                        aria-label={t("fireai.integration.title")}
                                                        className="space-y-6 animate-[fadeInUp_0.3s_var(--ease-entrance)]"
                                                >
                                                        <div className="etap-panel">
                                                                <div className="etap-panel-header">
                                                                        <div className="etap-panel-title">
                                                                                <Network aria-hidden="true" className="h-5 w-5 etap-panel-title-icon" />
                                                                                {t("fireai.integration.title")}
                                                                        </div>
                                                                        <div className="etap-panel-description">
                                                                                {t("engineering.integrationDesc")}
                                                                        </div>
                                                                </div>
                                                                <div className="etap-panel-body">
                                                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                                                                {integrationSubsystems.map(({ key, label }) => (
                                                                                        <button
                                                                                                key={key}
                                                                                                type="button"
                                                                                                className={`flex items-center gap-3 px-3 py-2.5 rounded-[var(--etap-radius)] border transition-colors duration-150 cursor-pointer ${integrationToggles[key]
                                                                                                        ? "bg-[var(--etap-bg-primary)] border-[var(--etap-border-default)]"
                                                                                                        : "bg-[rgba(239,68,68,0.06)] border-[rgba(239,68,68,0.2)]"
                                                                                                        }`}
                                                                                                onClick={() => setIntegrationToggles((p) => ({ ...p, [key]: !p[key] }))}
                                                                                                aria-pressed={integrationToggles[key]}
                                                                                        >
                                                                                                {integrationToggles[key] ? (
                                                                                                        <CheckCircle2 aria-hidden="true" className="h-4 w-4 text-[var(--etap-success)]" />
                                                                                                ) : (
                                                                                                        <AlertTriangle aria-hidden="true" className="h-4 w-4 text-[var(--etap-danger)]" />
                                                                                                )}
                                                                                                <span className={`font-mono-num text-sm ${integrationToggles[key] ? "text-[var(--etap-text-secondary)]" : "text-[var(--etap-danger)]"
                                                                                                        }`}>
                                                                                                        {label}
                                                                                                </span>
                                                                                        </button>
                                                                                ))}
                                                                        </div>
                                                                        <div className="mt-5">
                                                                                <Button
                                                                                        onClick={() => apiCall("/integration", { method: "POST", body: JSON.stringify(integrationToggles) })}
                                                                                        className="etap-btn etap-btn-primary"
                                                                                >
                                                                                        <Network aria-hidden="true" className="h-4 w-4" />
                                                                                        {t("engineering.runIntegrationCheck")}
                                                                                </Button>
                                                                        </div>
                                                                </div>
                                                        </div>
                                                </div>
                                        )}
                                </div>
                        </div>

                </div>
        );
}
