/**
 * AnalysisPage.tsx — NFPA 72 / NEC / Darcy-Weisbach Analysis Dashboard.
 *
 * Runs project-level engineering calculations:
 *  - Battery capacity (POST /api/analyze/battery)
 *  - Voltage drop (POST /api/analyze/voltage)
 *  - Full room analysis (POST /api/projects/{id}/analyze/room)
 *  - Hydraulics Darcy-Weisbach Solver (POST /api/analyze/hydraulic)
 *
 * Backend: backend/routers/analyze.py
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import {
	AlertTriangle,
	Battery,
	Building2,
	Calculator,
	CheckCircle2,
	Droplets,
	FlaskConical,
	Loader2,
	Plus,
	Send,
	Trash2,
	Zap,
} from "lucide-react";
import React, { useState } from "react";
import { analyzeApi } from "@/services/fullApi";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

interface BatteryResult {
	success: boolean;
	data?: {
		required_capacity_ah: number;
		selected_battery_ah: number;
		backup_minutes: number;
		margin_percent: number;
	};
	error?: string;
}

interface VoltageResult {
	success: boolean;
	data?: {
		drop_percent: number;
		drop_volts: number;
		passes: boolean;
		recommended_wire: string;
	};
	error?: string;
}

interface RoomAnalysisResult {
	success: boolean;
	data?: {
		room_name: string;
		detector_count: number;
		coverage_percent: number;
		notifications: number;
		warnings: string[];
	};
	error?: string;
}

export interface PipeSegment {
	id: string;
	diameter_mm: number;
	length_m: number;
	roughness_mm: number;
	flow_rate_lpm: number;
	elevation_change_m: number;
}

export interface HydraulicSegmentResult {
	id: string;
	diameter_mm: number;
	length_m: number;
	flow_rate_lpm: number;
	velocity_ms: number;
	reynolds_number: number;
	friction_factor: number;
	flow_regime: "Laminar" | "Turbulent" | "Transitional";
	friction_head_loss_m: number;
	elevation_head_loss_m: number;
	total_head_loss_m: number;
	pressure_drop_kpa: number;
	pressure_drop_bar: number;
	velocity_warning: boolean;
}

export interface HydraulicResult {
	success: boolean;
	data?: {
		segments: HydraulicSegmentResult[];
		total_pressure_drop_kpa: number;
		total_pressure_drop_bar: number;
		total_head_loss_m: number;
		max_velocity_ms: number;
		has_high_velocity_alert: boolean;
	};
	error?: string;
}

/** Pure local Darcy-Weisbach solver */
export function solveDarcyWeisbach(pipes: PipeSegment[]): HydraulicResult {
	const segments: HydraulicSegmentResult[] = [];
	let totalHeadLoss = 0;
	let maxVelocity = 0;
	let hasHighVelocityAlert = false;

	const g = 9.80665;
	const nu = 1.004e-6; // Water kinematic viscosity at 20°C (m²/s)
	const rho = 1000; // Water density (kg/m³)

	for (const pipe of pipes) {
		const dM = Math.max(pipe.diameter_mm, 1) / 1000;
		const area = (Math.PI * dM * dM) / 4;
		const qM3s = (Math.max(pipe.flow_rate_lpm, 0) / 60000);
		const v = qM3s / area;
		if (v > maxVelocity) maxVelocity = v;
		const velocityWarning = v > 5.0;
		if (velocityWarning) hasHighVelocityAlert = true;

		const re = (v * dM) / nu;
		let f: number;
		let regime: "Laminar" | "Turbulent" | "Transitional";

		if (re < 2000) {
			regime = "Laminar";
			f = re > 0 ? 64 / re : 0.02;
		} else if (re >= 2000 && re < 4000) {
			regime = "Transitional";
			const epsM = pipe.roughness_mm / 1000;
			const denom = Math.log10(epsM / (3.7 * dM) + 5.74 / Math.pow(re, 0.9));
			f = 0.25 / (denom * denom);
		} else {
			regime = "Turbulent";
			const epsM = pipe.roughness_mm / 1000;
			const denom = Math.log10(epsM / (3.7 * dM) + 5.74 / Math.pow(re, 0.9));
			f = 0.25 / (denom * denom);
		}

		const hFriction = f * (pipe.length_m / dM) * ((v * v) / (2 * g));
		const hElevation = pipe.elevation_change_m;
		const hTotal = hFriction + hElevation;
		totalHeadLoss += hTotal;

		const deltaPKpa = (rho * g * hTotal) / 1000;
		const deltaPBar = deltaPKpa / 100;

		segments.push({
			id: pipe.id,
			diameter_mm: pipe.diameter_mm,
			length_m: pipe.length_m,
			flow_rate_lpm: pipe.flow_rate_lpm,
			velocity_ms: Number.parseFloat(v.toFixed(2)),
			reynolds_number: Math.round(re),
			friction_factor: Number.parseFloat(f.toFixed(4)),
			flow_regime: regime,
			friction_head_loss_m: Number.parseFloat(hFriction.toFixed(3)),
			elevation_head_loss_m: Number.parseFloat(hElevation.toFixed(3)),
			total_head_loss_m: Number.parseFloat(hTotal.toFixed(3)),
			pressure_drop_kpa: Number.parseFloat(deltaPKpa.toFixed(2)),
			pressure_drop_bar: Number.parseFloat(deltaPBar.toFixed(3)),
			velocity_warning: velocityWarning,
		});
	}

	const totalDeltaPKpa = (rho * g * totalHeadLoss) / 1000;

	return {
		success: true,
		data: {
			segments,
			total_pressure_drop_kpa: Number.parseFloat(totalDeltaPKpa.toFixed(2)),
			total_pressure_drop_bar: Number.parseFloat((totalDeltaPKpa / 100).toFixed(3)),
			total_head_loss_m: Number.parseFloat(totalHeadLoss.toFixed(2)),
			max_velocity_ms: Number.parseFloat(maxVelocity.toFixed(2)),
			has_high_velocity_alert: hasHighVelocityAlert,
		},
	};
}

export const AnalysisPage: React.FC = () => {
	const [selectedAnalysis, setSelectedAnalysis] = useState<
		"battery" | "voltage" | "room" | "hydraulic"
	>("battery");
	const [projectId, setProjectId] = useState("");
	const [batteryLoad, setBatteryLoad] = useState("25");
	const [batteryMinutes, setBatteryMinutes] = useState("24");
	const [voltageLength, setVoltageLength] = useState("100");
	const [voltageCurrent, setVoltageCurrent] = useState("2.5");
	const [voltageWire, setVoltageWire] = useState("14");

	// Pipe schedule table state for Darcy-Weisbach hydraulic solver
	const [pipes, setPipes] = useState<PipeSegment[]>([
		{
			id: "P-01",
			diameter_mm: 50,
			length_m: 15.0,
			roughness_mm: 0.045,
			flow_rate_lpm: 350,
			elevation_change_m: 0.0,
		},
		{
			id: "P-02",
			diameter_mm: 65,
			length_m: 25.0,
			roughness_mm: 0.045,
			flow_rate_lpm: 750,
			elevation_change_m: 3.5,
		},
	]);

	// Fetch projects for room analysis
	const { data: projects } = useQuery({
		queryKey: ["analysis-projects"],
		queryFn: async () => {
			const res = await fetch(`${API_BASE}/projects?limit=50`, {
				credentials: "same-origin",
			});
			if (!res.ok) return [];
			const json = await res.json();
			return json?.data?.data || json?.data || [];
		},
	});

	const batteryMutation = useMutation({
		mutationFn: async () => {
			return analyzeApi.battery({
				standby_load_a: Number.parseFloat(batteryLoad) || 0,
				alarm_load_a: 0,
				standby_hours: 24,
				alarm_minutes: Number.parseFloat(batteryMinutes) || 0,
			}) as Promise<BatteryResult>;
		},
	});

	const voltageMutation = useMutation({
		mutationFn: async () => {
			return analyzeApi.voltage({
				current_a: Number.parseFloat(voltageCurrent) || 0,
				length_m: Number.parseFloat(voltageLength) || 0,
				awg_gauge: voltageWire,
			}) as Promise<VoltageResult>;
		},
	});

	const roomMutation = useMutation({
		mutationFn: async () => {
			if (!projectId) throw new Error("Please select a project");
			return analyzeApi.room(projectId, {}) as Promise<RoomAnalysisResult>;
		},
	});

	const hydraulicMutation = useMutation({
		mutationFn: async (): Promise<HydraulicResult> => {
			try {
				const res = await analyzeApi.hydraulic({
					pipes,
					fluid_density_kg_m3: 1000,
					kinematic_viscosity_m2_s: 1.004e-6,
				});
				if (res && (res as HydraulicResult).data) {
					return res as HydraulicResult;
				}
				return solveDarcyWeisbach(pipes);
			} catch {
				// Local Darcy-Weisbach fallback calculation
				return solveDarcyWeisbach(pipes);
			}
		},
	});

	const getActiveMutation = () => {
		if (selectedAnalysis === "battery") return batteryMutation;
		if (selectedAnalysis === "voltage") return voltageMutation;
		if (selectedAnalysis === "room") return roomMutation;
		return hydraulicMutation;
	};
	const currentMutation = getActiveMutation();

	const handleAddPipe = () => {
		const nextIdx = pipes.length + 1;
		setPipes([
			...pipes,
			{
				id: `P-0${nextIdx}`,
				diameter_mm: 50,
				length_m: 10.0,
				roughness_mm: 0.045,
				flow_rate_lpm: 250,
				elevation_change_m: 0.0,
			},
		]);
	};

	const handleRemovePipe = (idx: number) => {
		if (pipes.length <= 1) return;
		setPipes(pipes.filter((_, i) => i !== idx));
	};

	const handleUpdatePipe = (
		idx: number,
		field: keyof PipeSegment,
		value: string | number,
	) => {
		const updated = [...pipes];
		if (field === "id") {
			updated[idx].id = String(value);
		} else {
			updated[idx][field] = Number.parseFloat(String(value)) || 0;
		}
		setPipes(updated);
	};

	const tabs = [
		{
			key: "battery" as const,
			label: "Battery Capacity",
			icon: Battery,
			desc: "NFPA 72 standby battery sizing",
		},
		{
			key: "voltage" as const,
			label: "Voltage Drop",
			icon: Zap,
			desc: "NEC Chapter 9 Table 8 voltage drop",
		},
		{
			key: "room" as const,
			label: "Room Analysis",
			icon: Building2,
			desc: "Full room coverage & detection analysis",
		},
		{
			key: "hydraulic" as const,
			label: "Hydraulics (Darcy-Weisbach)",
			icon: Droplets,
			desc: "Darcy-Weisbach fire sprinkler pipe network pressure drop & velocity calculation",
		},
	];

	return (
		<div className="flex-1 overflow-auto bg-background min-h-screen">
			<div className="p-6 max-w-5xl mx-auto space-y-6">
				{/* Header */}
				<div>
					<h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
						<Calculator className="h-6 w-6 text-primary" />
						NFPA 72 / NEC Analysis
					</h1>
					<p className="text-muted-foreground text-sm mt-1">
						Engineering calculations for fire alarm, electrical, and sprinkler system design — battery
						sizing, voltage drop, room coverage, and Darcy-Weisbach hydraulics
					</p>
				</div>

				{/* Tab Selector */}
				<div className="flex gap-2 flex-wrap">
					{tabs.map((tab) => {
						const Icon = tab.icon;
						const active = selectedAnalysis === tab.key;
						return (
							<button
								key={tab.key}
								type="button"
								onClick={() => setSelectedAnalysis(tab.key)}
								className={`flex items-center gap-2 px-4 py-2 rounded text-xs font-mono font-medium transition-colors ${
									active
										? "bg-primary/20 text-primary border border-primary/40"
										: "bg-card text-muted-foreground hover:text-foreground border border-border"
								}`}
							>
								<Icon className="h-4 w-4" />
								{tab.label}
							</button>
						);
					})}
				</div>

				{/* Analysis Form */}
				<div className="bg-card border border-border rounded p-5">
					<div className="flex items-center gap-2 mb-4">
						<FlaskConical className="h-4 w-4 text-primary" />
						<h3 className="text-xs font-semibold text-foreground font-mono">
							{tabs.find((t) => t.key === selectedAnalysis)?.desc}
						</h3>
					</div>

					<div className="space-y-4">
						{selectedAnalysis === "battery" && (
							<div className="grid grid-cols-2 gap-3">
								<div>
									<label htmlFor="battery-total-load-input" className="block text-xs font-mono text-muted-foreground mb-1">
										Total Load (A)
									</label>
									<input
										id="battery-total-load-input"
										type="number"
										step="0.1"
										value={batteryLoad}
										onChange={(e) => setBatteryLoad(e.target.value)}
										className="w-full px-3 py-1.5 bg-input border border-border rounded text-foreground font-mono text-xs focus:border-primary focus:outline-none"
									/>
								</div>
								<div>
									<label htmlFor="battery-backup-duration-input" className="block text-xs font-mono text-muted-foreground mb-1">
										Backup Duration (min)
									</label>
									<input
										id="battery-backup-duration-input"
										type="number"
										value={batteryMinutes}
										onChange={(e) => setBatteryMinutes(e.target.value)}
										className="w-full px-3 py-1.5 bg-input border border-border rounded text-foreground font-mono text-xs focus:border-primary focus:outline-none"
									/>
								</div>
							</div>
						)}

						{selectedAnalysis === "voltage" && (
							<div className="grid grid-cols-3 gap-3">
								<div>
									<label htmlFor="voltage-circuit-length-input" className="block text-xs font-mono text-muted-foreground mb-1">
										Length (ft)
									</label>
									<input
										id="voltage-circuit-length-input"
										type="number"
										value={voltageLength}
										onChange={(e) => setVoltageLength(e.target.value)}
										className="w-full px-3 py-1.5 bg-input border border-border rounded text-foreground font-mono text-xs focus:border-primary focus:outline-none"
									/>
								</div>
								<div>
									<label htmlFor="voltage-load-current-input" className="block text-xs font-mono text-muted-foreground mb-1">
										Current (A)
									</label>
									<input
										id="voltage-load-current-input"
										type="number"
										step="0.1"
										value={voltageCurrent}
										onChange={(e) => setVoltageCurrent(e.target.value)}
										className="w-full px-3 py-1.5 bg-input border border-border rounded text-foreground font-mono text-xs focus:border-primary focus:outline-none"
									/>
								</div>
								<div>
									<label htmlFor="voltage-wire-gauge-select" className="block text-xs font-mono text-muted-foreground mb-1">
										Wire (AWG)
									</label>
									<select
										id="voltage-wire-gauge-select"
										value={voltageWire}
										onChange={(e) => setVoltageWire(e.target.value)}
										className="w-full px-3 py-1.5 bg-input border border-border rounded text-foreground font-mono text-xs focus:border-primary focus:outline-none"
									>
										{[18, 16, 14, 12, 10, 8, 6, 4].map((awg) => (
											<option key={awg} value={awg}>
												{awg} AWG
											</option>
										))}
									</select>
								</div>
							</div>
						)}

						{selectedAnalysis === "room" && (
							<div>
								<label htmlFor="room-analysis-project-select" className="block text-xs font-mono text-muted-foreground mb-1">
									Project
								</label>
								<select
									id="room-analysis-project-select"
									value={projectId}
									onChange={(e) => setProjectId(e.target.value)}
									className="w-full px-3 py-1.5 bg-input border border-border rounded text-foreground font-mono text-xs focus:border-primary focus:outline-none"
								>
									<option value="">Select a project...</option>
									{(Array.isArray(projects) ? projects : []).map(
										(p: { id: string; name: string }) => (
											<option key={p.id} value={p.id}>
												{p.name}
											</option>
										),
									)}
								</select>
							</div>
						)}

						{selectedAnalysis === "hydraulic" && (
							<div className="space-y-3">
								<div className="flex items-center justify-between">
									<span className="text-xs font-mono text-muted-foreground">
										Pipe Network Schedule (Darcy-Weisbach Method)
									</span>
									<button
										type="button"
										onClick={handleAddPipe}
										className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30 rounded text-xs font-mono"
									>
										<Plus className="h-3 w-3" />
										Add Pipe Segment
									</button>
								</div>

								<div className="overflow-x-auto border border-border rounded">
									<table className="w-full text-xs font-mono text-left">
										<thead className="bg-popover border-b border-border text-muted-foreground uppercase text-[10px]">
											<tr>
												<th className="p-2">Segment ID</th>
												<th className="p-2 text-right">Diameter (mm)</th>
												<th className="p-2 text-right">Length (m)</th>
												<th className="p-2 text-right">Roughness ε (mm)</th>
												<th className="p-2 text-right">Flow (L/min)</th>
												<th className="p-2 text-right">ΔZ Elevation (m)</th>
												<th className="p-2 text-center w-12">Action</th>
											</tr>
										</thead>
										<tbody className="divide-y divide-border">
											{pipes.map((pipe, idx) => (
												<tr key={pipe.id || `pipe-row-${idx}`} className="hover:bg-muted/30">
													<td className="p-1.5">
														<input
															type="text"
															value={pipe.id}
															onChange={(e) =>
																handleUpdatePipe(idx, "id", e.target.value)
															}
															className="w-20 px-2 py-1 bg-input border border-border rounded text-foreground font-mono text-xs"
														/>
													</td>
													<td className="p-1.5 text-right">
														<input
															type="number"
															step="1"
															value={pipe.diameter_mm}
															onChange={(e) =>
																handleUpdatePipe(idx, "diameter_mm", e.target.value)
															}
															className="w-20 px-2 py-1 bg-input border border-border rounded text-foreground font-mono text-xs text-right tabular-nums"
														/>
													</td>
													<td className="p-1.5 text-right">
														<input
															type="number"
															step="0.5"
															value={pipe.length_m}
															onChange={(e) =>
																handleUpdatePipe(idx, "length_m", e.target.value)
															}
															className="w-20 px-2 py-1 bg-input border border-border rounded text-foreground font-mono text-xs text-right tabular-nums"
														/>
													</td>
													<td className="p-1.5 text-right">
														<input
															type="number"
															step="0.005"
															value={pipe.roughness_mm}
															onChange={(e) =>
																handleUpdatePipe(idx, "roughness_mm", e.target.value)
															}
															className="w-20 px-2 py-1 bg-input border border-border rounded text-foreground font-mono text-xs text-right tabular-nums"
														/>
													</td>
													<td className="p-1.5 text-right">
														<input
															type="number"
															step="10"
															value={pipe.flow_rate_lpm}
															onChange={(e) =>
																handleUpdatePipe(idx, "flow_rate_lpm", e.target.value)
															}
															className="w-24 px-2 py-1 bg-input border border-border rounded text-foreground font-mono text-xs text-right tabular-nums"
														/>
													</td>
													<td className="p-1.5 text-right">
														<input
															type="number"
															step="0.5"
															value={pipe.elevation_change_m}
															onChange={(e) =>
																handleUpdatePipe(
																	idx,
																	"elevation_change_m",
																	e.target.value,
																)
															}
															className="w-20 px-2 py-1 bg-input border border-border rounded text-foreground font-mono text-xs text-right tabular-nums"
														/>
													</td>
													<td className="p-1.5 text-center">
														<button
															type="button"
															onClick={() => handleRemovePipe(idx)}
															disabled={pipes.length <= 1}
															className="p-1 text-muted-foreground hover:text-red-400 disabled:opacity-30"
														>
															<Trash2 className="h-3.5 w-3.5" />
														</button>
													</td>
												</tr>
											))}
										</tbody>
									</table>
								</div>
							</div>
						)}

						<button
							type="button"
							onClick={() => currentMutation.mutate()}
							disabled={currentMutation.isPending}
							className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2 bg-primary hover:bg-primary/90 disabled:opacity-50 text-primary-foreground text-xs font-mono font-semibold rounded transition-colors"
						>
							{currentMutation.isPending ? (
								<>
									<Loader2 className="h-4 w-4 animate-spin" />
									Calculating...
								</>
							) : (
								<>
									<Send className="h-4 w-4" />
									Run Analysis
								</>
							)}
						</button>
					</div>
				</div>

				{/* Error display */}
				{currentMutation.isError && (
					<div className="bg-red-500/10 border border-red-500/30 rounded p-4">
						<div className="flex items-center gap-2">
							<AlertTriangle className="h-4 w-4 text-red-400" />
							<p className="text-red-400 text-xs font-mono">
								{currentMutation.error instanceof Error
									? currentMutation.error.message
									: "Analysis failed"}
							</p>
						</div>
					</div>
				)}

				{/* Battery Results */}
				{batteryMutation.isSuccess && batteryMutation.data?.data && (
					<div className="bg-card border border-border rounded p-5">
						<div className="flex items-center gap-2 mb-4">
							<CheckCircle2 className="h-4 w-4 text-emerald-400" />
							<h3 className="text-xs font-semibold text-foreground font-mono">
								Battery Capacity Results
							</h3>
						</div>
						<div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
							{[
								{
									label: "Required Capacity",
									value: `${batteryMutation.data.data.required_capacity_ah.toFixed(1)} Ah`,
								},
								{
									label: "Selected Battery",
									value: `${batteryMutation.data.data.selected_battery_ah} Ah`,
								},
								{
									label: "Backup Time",
									value: `${batteryMutation.data.data.backup_minutes} min`,
								},
								{
									label: "Margin",
									value: `${batteryMutation.data.data.margin_percent.toFixed(1)}%`,
								},
							].map((m) => (
								<div
									key={m.label}
									className="bg-popover rounded p-3 border border-border text-center"
								>
									<div className="text-[10px] text-muted-foreground font-mono mb-1">
										{m.label}
									</div>
									<div className="text-sm font-bold text-foreground font-mono tabular-nums">
										{m.value}
									</div>
								</div>
							))}
						</div>
					</div>
				)}

				{/* Voltage Drop Results */}
				{voltageMutation.isSuccess && voltageMutation.data?.data && (
					<div className="bg-card border border-border rounded p-5">
						<div className="flex items-center gap-2 mb-4">
							<CheckCircle2 className="h-4 w-4 text-emerald-400" />
							<h3 className="text-xs font-semibold text-foreground font-mono">
								Voltage Drop Results
							</h3>
						</div>
						<div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
							{[
								{
									label: "Drop %",
									value: `${voltageMutation.data.data.drop_percent.toFixed(2)}%`,
								},
								{
									label: "Drop (V)",
									value: `${voltageMutation.data.data.drop_volts.toFixed(3)} V`,
								},
								{
									label: "Status",
									value: voltageMutation.data.data.passes ? "PASS" : "FAIL",
								},
								{
									label: "Recommended Wire",
									value: voltageMutation.data.data.recommended_wire,
								},
							].map((m) => (
								<div
									key={m.label}
									className="bg-popover rounded p-3 border border-border text-center"
								>
									<div className="text-[10px] text-muted-foreground font-mono mb-1">
										{m.label}
									</div>
									<div
										className={`text-sm font-bold font-mono tabular-nums ${
											m.label === "Status" && m.value === "PASS"
												? "text-emerald-400"
												: m.label === "Status"
													? "text-red-400"
													: "text-foreground"
										}`}
									>
										{m.value}
									</div>
								</div>
							))}
						</div>
					</div>
				)}

				{/* Room Analysis Results */}
				{roomMutation.isSuccess && roomMutation.data?.data && (
					<div className="bg-card border border-border rounded p-5">
						<div className="flex items-center gap-2 mb-4">
							<CheckCircle2 className="h-4 w-4 text-emerald-400" />
							<h3 className="text-xs font-semibold text-foreground font-mono">
								Room Analysis: {roomMutation.data.data.room_name || "All Rooms"}
							</h3>
						</div>
						<div className="grid grid-cols-3 gap-3 mb-4">
							{[
								{
									label: "Detectors",
									value: String(roomMutation.data.data.detector_count),
								},
								{
									label: "Coverage",
									value: `${roomMutation.data.data.coverage_percent}%`,
								},
								{
									label: "Notifications",
									value: String(roomMutation.data.data.notifications),
								},
							].map((m) => (
								<div
									key={m.label}
									className="bg-popover rounded p-3 border border-border text-center"
								>
									<div className="text-[10px] text-muted-foreground font-mono mb-1">
										{m.label}
									</div>
									<div className="text-sm font-bold text-foreground font-mono tabular-nums">
										{m.value}
									</div>
								</div>
							))}
						</div>
						{roomMutation.data.data.warnings.length > 0 && (
							<div className="bg-amber-500/10 border border-amber-500/30 rounded p-3">
								<p className="text-xs font-medium text-amber-400 mb-1 font-mono">
									Warnings
								</p>
								{roomMutation.data.data.warnings.map((w, i) => (
									<p key={`room-warn-${w.slice(0, 16)}-${i}`} className="text-xs text-amber-300/80 font-mono">
										{w}
									</p>
								))}
							</div>
						)}
					</div>
				)}

				{/* Hydraulic (Darcy-Weisbach) Results */}
				{hydraulicMutation.isSuccess && hydraulicMutation.data?.data && (
					<div className="bg-card border border-border rounded p-5 space-y-4">
						<div className="flex items-center justify-between">
							<div className="flex items-center gap-2">
								<CheckCircle2 className="h-4 w-4 text-emerald-400" />
								<h3 className="text-xs font-semibold text-foreground font-mono">
									Hydraulics (Darcy-Weisbach) Results
								</h3>
							</div>
							{hydraulicMutation.data.data.has_high_velocity_alert && (
								<span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-red-950/60 border border-red-500/50 text-red-400 text-xs font-mono">
									<AlertTriangle className="h-3 w-3" />
									High Velocity Alert (v &gt; 5.0 m/s)
								</span>
							)}
						</div>

						{/* Summary Cards */}
						<div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
							{[
								{
									label: "Total Pressure Drop (ΔP)",
									value: `${hydraulicMutation.data.data.total_pressure_drop_kpa} kPa`,
									sub: `${hydraulicMutation.data.data.total_pressure_drop_bar} bar`,
								},
								{
									label: "Total Head Loss (hf)",
									value: `${hydraulicMutation.data.data.total_head_loss_m} m`,
									sub: "Friction + Elevation",
								},
								{
									label: "Max Flow Velocity",
									value: `${hydraulicMutation.data.data.max_velocity_ms} m/s`,
									sub: hydraulicMutation.data.data.max_velocity_ms > 5.0 ? "EXCESSIVE (>5.0 m/s)" : "NORMAL (≤5.0 m/s)",
								},
								{
									label: "Segments Evaluated",
									value: `${hydraulicMutation.data.data.segments.length}`,
									sub: "Darcy-Weisbach",
								},
							].map((m) => (
								<div
									key={m.label}
									className="bg-popover rounded p-3 border border-border text-center"
								>
									<div className="text-[10px] text-muted-foreground font-mono mb-1">
										{m.label}
									</div>
									<div className="text-sm font-bold text-foreground font-mono tabular-nums">
										{m.value}
									</div>
									<div className="text-[10px] text-primary font-mono mt-0.5">
										{m.sub}
									</div>
								</div>
							))}
						</div>

						{/* Segment Breakdown Table */}
						<div className="overflow-x-auto border border-border rounded mt-3">
							<table className="w-full text-xs font-mono text-left">
								<thead className="bg-popover border-b border-border text-muted-foreground uppercase text-[10px]">
									<tr>
										<th className="p-2">Segment</th>
										<th className="p-2 text-right">Flow (L/min)</th>
										<th className="p-2 text-right">Velocity (m/s)</th>
										<th className="p-2 text-right">Reynolds (Re)</th>
										<th className="p-2 text-right">Friction (f)</th>
										<th className="p-2 text-right">Head Loss (m)</th>
										<th className="p-2 text-right">ΔP (kPa)</th>
										<th className="p-2 text-center">Regime</th>
									</tr>
								</thead>
								<tbody className="divide-y divide-border">
									{hydraulicMutation.data.data.segments.map((seg) => (
										<tr
											key={seg.id}
											className={`hover:bg-muted/30 ${
												seg.velocity_warning ? "bg-red-950/20" : ""
											}`}
										>
											<td className="p-2 font-bold text-foreground">{seg.id}</td>
											<td className="p-2 text-right tabular-nums">{seg.flow_rate_lpm}</td>
											<td
												className={`p-2 text-right font-bold tabular-nums ${
													seg.velocity_warning ? "text-red-400" : "text-emerald-400"
												}`}
											>
												{seg.velocity_ms}
											</td>
											<td className="p-2 text-right tabular-nums">{seg.reynolds_number.toLocaleString()}</td>
											<td className="p-2 text-right tabular-nums">{seg.friction_factor}</td>
											<td className="p-2 text-right tabular-nums">{seg.total_head_loss_m}</td>
											<td className="p-2 text-right font-bold text-primary tabular-nums">
												{seg.pressure_drop_kpa}
											</td>
											<td className="p-2 text-center">
												<span
													className={`px-1.5 py-0.5 rounded text-[10px] ${
														seg.flow_regime === "Turbulent"
															? "bg-cyan-950/60 text-cyan-300 border border-cyan-500/30"
															: "bg-emerald-950/60 text-emerald-300 border border-emerald-500/30"
													}`}
												>
													{seg.flow_regime}
												</span>
											</td>
										</tr>
									))}
								</tbody>
							</table>
						</div>
					</div>
				)}
			</div>
		</div>
	);
};

export default AnalysisPage;
