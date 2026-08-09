/**
 * AnalysisPage.tsx — NFPA 72 / NEC Analysis Dashboard.
 *
 * Runs project-level engineering calculations:
 *  - Battery capacity (POST /api/analyze/battery)
 *  - Voltage drop (POST /api/analyze/voltage)
 *  - Full room analysis (POST /api/projects/{id}/analyze/room)
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
	FlaskConical,
	Loader2,
	Send,
	Zap,
} from "lucide-react";
import { useState } from "react";
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

export const AnalysisPage: React.FC = () => {
	const [selectedAnalysis, setSelectedAnalysis] = useState<
		"battery" | "voltage" | "room"
	>("battery");
	const [projectId, setProjectId] = useState("");
	const [batteryLoad, setBatteryLoad] = useState("25");
	const [batteryMinutes, setBatteryMinutes] = useState("24");
	const [voltageLength, setVoltageLength] = useState("100");
	const [voltageCurrent, setVoltageCurrent] = useState("2.5");
	const [voltageWire, setVoltageWire] = useState("14");

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

	const currentMutation =
		selectedAnalysis === "battery"
			? batteryMutation
			: selectedAnalysis === "voltage"
				? voltageMutation
				: roomMutation;

	const tabs: {
		key: typeof selectedAnalysis;
		label: string;
		icon: React.ElementType;
		desc: string;
	}[] = [
		{
			key: "battery",
			label: "Battery Capacity",
			icon: Battery,
			desc: "NFPA 72 standby battery sizing",
		},
		{
			key: "voltage",
			label: "Voltage Drop",
			icon: Zap,
			desc: "NEC Chapter 9 Table 8 voltage drop",
		},
		{
			key: "room",
			label: "Room Analysis",
			icon: Building2,
			desc: "Full room coverage & detection analysis",
		},
	];

	return (
		<div className="flex-1 overflow-auto">
			<div className="p-6 max-w-4xl mx-auto space-y-6">
				{/* Header */}
				<div>
					<h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
						<Calculator className="h-6 w-6 text-cyan-400" />
						NFPA 72 / NEC Analysis
					</h1>
					<p className="text-slate-400 text-sm mt-1">
						Engineering calculations for fire alarm system design — battery
						sizing, voltage drop, and room-level analysis
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
								className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
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

				{/* Analysis Form */}
				<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
					<div className="flex items-center gap-2 mb-4">
						<FlaskConical className="h-4 w-4 text-cyan-400" />
						<h3 className="text-sm font-semibold text-slate-200">
							{tabs.find((t) => t.key === selectedAnalysis)?.desc}
						</h3>
					</div>

					<div className="space-y-3">
						{selectedAnalysis === "battery" && (
							<div className="grid grid-cols-2 gap-3">
								<div>
									<label className="block text-xs font-medium text-slate-400 mb-1">
										Total Load (A)
									</label>
									<input
										type="number"
										step="0.1"
										value={batteryLoad}
										onChange={(e) => setBatteryLoad(e.target.value)}
										className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
									/>
								</div>
								<div>
									<label className="block text-xs font-medium text-slate-400 mb-1">
										Backup Duration (min)
									</label>
									<input
										type="number"
										value={batteryMinutes}
										onChange={(e) => setBatteryMinutes(e.target.value)}
										className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
									/>
								</div>
							</div>
						)}

						{selectedAnalysis === "voltage" && (
							<div className="grid grid-cols-3 gap-3">
								<div>
									<label className="block text-xs font-medium text-slate-400 mb-1">
										Length (ft)
									</label>
									<input
										type="number"
										value={voltageLength}
										onChange={(e) => setVoltageLength(e.target.value)}
										className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
									/>
								</div>
								<div>
									<label className="block text-xs font-medium text-slate-400 mb-1">
										Current (A)
									</label>
									<input
										type="number"
										step="0.1"
										value={voltageCurrent}
										onChange={(e) => setVoltageCurrent(e.target.value)}
										className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
									/>
								</div>
								<div>
									<label className="block text-xs font-medium text-slate-400 mb-1">
										Wire (AWG)
									</label>
									<select
										value={voltageWire}
										onChange={(e) => setVoltageWire(e.target.value)}
										className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
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
								<label className="block text-xs font-medium text-slate-400 mb-1">
									Project
								</label>
								<select
									value={projectId}
									onChange={(e) => setProjectId(e.target.value)}
									className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm focus:border-cyan-500 focus:outline-none"
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

						<button
							type="button"
							onClick={() => currentMutation.mutate()}
							disabled={currentMutation.isPending}
							className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
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

				{/* Results */}
				{currentMutation.isError && (
					<div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
						<div className="flex items-center gap-2">
							<AlertTriangle className="h-4 w-4 text-red-400" />
							<p className="text-red-400 text-sm">
								{currentMutation.error instanceof Error
									? currentMutation.error.message
									: "Analysis failed"}
							</p>
						</div>
					</div>
				)}

				{batteryMutation.isSuccess && batteryMutation.data?.data && (
					<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
						<div className="flex items-center gap-2 mb-4">
							<CheckCircle2 className="h-4 w-4 text-emerald-400" />
							<h3 className="text-sm font-semibold text-slate-200">
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
									className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center"
								>
									<div className="text-[10px] text-slate-500 mb-1">
										{m.label}
									</div>
									<div className="text-sm font-bold text-slate-100 font-mono">
										{m.value}
									</div>
								</div>
							))}
						</div>
					</div>
				)}

				{voltageMutation.isSuccess && voltageMutation.data?.data && (
					<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
						<div className="flex items-center gap-2 mb-4">
							<CheckCircle2 className="h-4 w-4 text-emerald-400" />
							<h3 className="text-sm font-semibold text-slate-200">
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
									className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center"
								>
									<div className="text-[10px] text-slate-500 mb-1">
										{m.label}
									</div>
									<div
										className={`text-sm font-bold font-mono ${
											m.label === "Status" && m.value === "PASS"
												? "text-emerald-400"
												: m.label === "Status"
													? "text-red-400"
													: "text-slate-100"
										}`}
									>
										{m.value}
									</div>
								</div>
							))}
						</div>
					</div>
				)}

				{roomMutation.isSuccess && roomMutation.data?.data && (
					<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
						<div className="flex items-center gap-2 mb-4">
							<CheckCircle2 className="h-4 w-4 text-emerald-400" />
							<h3 className="text-sm font-semibold text-slate-200">
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
									className="bg-slate-800 rounded-lg p-3 border border-slate-700/50 text-center"
								>
									<div className="text-[10px] text-slate-500 mb-1">
										{m.label}
									</div>
									<div className="text-sm font-bold text-slate-100 font-mono">
										{m.value}
									</div>
								</div>
							))}
						</div>
						{roomMutation.data.data.warnings.length > 0 && (
							<div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
								<p className="text-xs font-medium text-amber-400 mb-1">
									Warnings
								</p>
								{roomMutation.data.data.warnings.map((w, i) => (
									<p key={i} className="text-xs text-amber-300/70">
										{w}
									</p>
								))}
							</div>
						)}
					</div>
				)}
			</div>
		</div>
	);
};

export default AnalysisPage;
