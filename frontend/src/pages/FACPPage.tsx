/**
 * FACPPage.tsx — Fire Alarm Control Panel Selection (NFPA 72 §10.6.10).
 *
 * V216: New page — 5 backend endpoints now have UI.
 * Panel selection, verification, schedule generation, spec, panel list.
 *
 * Phase 13 (frontend-design skill): applied FACP industrial identity.
 * See styles/facp.css for the visual vocabulary. All shadcn Card/Input/Button
 * defaults are overridden with .facp-* classes — graphite + panel-recess +
 * evac-green + IBM Plex Mono + 2px sharp corners.
 */

import {
	Cpu,
	FileCode2,
	FileText,
	ListChecks,
	Loader2,
	ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import { facpApi, facpExtendedApi } from "@/services/fullApi";
import "@/styles/facp.css";

interface FACPForm {
	device_count: string;
	nac_circuit_count: string;
	building_size_m2: string;
	building_floors: string;
	requires_network: boolean;
	requires_voice: boolean;
	requires_releasing: boolean;
	jurisdiction: string;
	min_temperature_c: string;
}

// NFPA 72 §10.6.10.1.2 — NAC utilization cap is 80%, derating zone starts at 70%.
// We use 70% / 90% as the green/amber/red thresholds with a 10% safety margin.
const UTIL_THRESHOLD_WARNING = 0.7;
const UTIL_THRESHOLD_DANGER = 0.9;

function utilClass(value: number): "ok" | "warning" | "danger" {
	if (value >= UTIL_THRESHOLD_DANGER) return "danger";
	if (value >= UTIL_THRESHOLD_WARNING) return "warning";
	return "ok";
}

export function FACPPage() {
	const { toast } = useToast();
	const [loading, setLoading] = useState(false);
	const [panels, setPanels] = useState<unknown[]>([]);
	const [result, setResult] = useState<Record<string, unknown> | null>(null);

	const [extendedResult, setExtendedResult] = useState<Record<
		string,
		unknown
	> | null>(null);
	const [panelId, setPanelId] = useState("");

	const [form, setForm] = useState<FACPForm>({
		device_count: "150",
		nac_circuit_count: "4",
		building_size_m2: "3000",
		building_floors: "3",
		requires_network: false,
		requires_voice: false,
		requires_releasing: false,
		jurisdiction: "UL",
		min_temperature_c: "0",
	});

	const handleSelect = async () => {
		setLoading(true);
		setResult(null);
		try {
			const res = await facpApi.select({
				device_count: Number.parseInt(form.device_count),
				nac_circuit_count: Number.parseInt(form.nac_circuit_count),
				building_size_m2: Number.parseFloat(form.building_size_m2),
				building_floors: Number.parseInt(form.building_floors),
				requires_network: form.requires_network,
				requires_voice: form.requires_voice,
				requires_releasing: form.requires_releasing,
				jurisdiction: form.jurisdiction,
				min_temperature_c: Number.parseFloat(form.min_temperature_c),
			});
			setResult(res as Record<string, unknown>);
		} catch (err) {
			toast({
				title: "FACP Selection Failed",
				description: err instanceof Error ? err.message : "Failed",
				variant: "destructive",
			});
		} finally {
			setLoading(false);
		}
	};

	const handleListPanels = async () => {
		setLoading(true);
		try {
			const res = await facpApi.getPanels();
			setPanels((res as { panels?: unknown[] }).panels || []);
		} catch (err) {
			toast({
				title: "Failed to load panels",
				description: err instanceof Error ? err.message : "Failed",
				variant: "destructive",
			});
		} finally {
			setLoading(false);
		}
	};

	const capacityUtil = result
		? ((result.capacity_utilization as number) ?? 0)
		: 0;
	const nacUtil = result ? ((result.nac_utilization as number) ?? 0) : 0;

	return (
		<div className="flex-1 overflow-auto">
			<div className="p-6 max-w-5xl mx-auto space-y-6">
				{/* Page header — FACP nameplate vocabulary */}
				<div className="facp-page-header">
					<h1 className="facp-page-title">
						<Cpu aria-hidden="true" className="h-6 w-6 facp-page-title-icon" />
						FACP Panel Selection
					</h1>
					<p className="facp-page-ref">
						<span className="facp-page-ref-accent">NFPA 72 §10.6.10</span>
						{" · "}
						UL 864
						{" · "}
						Battery sizing with temperature/aging derating
					</p>
				</div>

				{/* Requirements Input */}
				<div className="facp-card">
					<div className="facp-card-header">
						<h2 className="facp-card-title">Project Requirements</h2>
						<p className="facp-card-desc">
							Define the building and system requirements for panel selection
						</p>
					</div>
					<div className="facp-card-content">
						<div className="grid grid-cols-2 md:grid-cols-3 gap-4">
							<div className="space-y-1">
								<Label className="facp-field-label">Device Count</Label>
								<Input
									type="number"
									className="facp-input"
									value={form.device_count}
									onChange={(e) =>
										setForm({ ...form, device_count: e.target.value })
									}
								/>
							</div>
							<div className="space-y-1">
								<Label className="facp-field-label">NAC Circuits</Label>
								<Input
									type="number"
									className="facp-input"
									value={form.nac_circuit_count}
									onChange={(e) =>
										setForm({ ...form, nac_circuit_count: e.target.value })
									}
								/>
							</div>
							<div className="space-y-1">
								<Label className="facp-field-label">Building Size (m²)</Label>
								<Input
									type="number"
									className="facp-input"
									value={form.building_size_m2}
									onChange={(e) =>
										setForm({ ...form, building_size_m2: e.target.value })
									}
								/>
							</div>
							<div className="space-y-1">
								<Label className="facp-field-label">Building Floors</Label>
								<Input
									type="number"
									className="facp-input"
									value={form.building_floors}
									onChange={(e) =>
										setForm({ ...form, building_floors: e.target.value })
									}
								/>
							</div>
							<div className="space-y-1">
								<Label className="facp-field-label">Min Temp (°C)</Label>
								<Input
									type="number"
									className="facp-input"
									value={form.min_temperature_c}
									onChange={(e) =>
										setForm({ ...form, min_temperature_c: e.target.value })
									}
								/>
							</div>
							<div className="space-y-1">
								<Label className="facp-field-label">Jurisdiction</Label>
								<Select
									value={form.jurisdiction}
									onValueChange={(v) => setForm({ ...form, jurisdiction: v })}
								>
									<SelectTrigger className="facp-select-trigger">
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										<SelectItem value="UL">UL</SelectItem>
										<SelectItem value="ULC">ULC</SelectItem>
										<SelectItem value="FM">FM</SelectItem>
										<SelectItem value="FDNY">FDNY</SelectItem>
									</SelectContent>
								</Select>
							</div>
						</div>

						<div className="flex flex-wrap gap-4 mt-4">
							<div className="flex items-center gap-2">
								<Checkbox
									id="network"
									checked={form.requires_network}
									onCheckedChange={(v) =>
										setForm({ ...form, requires_network: v === true })
									}
								/>
								<Label htmlFor="network" className="facp-check-label">
									Networked
								</Label>
							</div>
							<div className="flex items-center gap-2">
								<Checkbox
									id="voice"
									checked={form.requires_voice}
									onCheckedChange={(v) =>
										setForm({ ...form, requires_voice: v === true })
									}
								/>
								<Label htmlFor="voice" className="facp-check-label">
									Voice Evac
								</Label>
							</div>
							<div className="flex items-center gap-2">
								<Checkbox
									id="releasing"
									checked={form.requires_releasing}
									onCheckedChange={(v) =>
										setForm({ ...form, requires_releasing: v === true })
									}
								/>
								<Label htmlFor="releasing" className="facp-check-label">
									Releasing Service
								</Label>
							</div>
						</div>
					</div>
				</div>

				{/* Actions */}
				<div className="flex flex-wrap gap-3">
					<Button
						onClick={handleSelect}
						disabled={loading}
						className="facp-btn-primary inline-flex items-center gap-2 px-4 py-2"
					>
						{loading ? (
							<Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
						) : (
							<Cpu aria-hidden="true" className="h-4 w-4" />
						)}
						Select Panel
					</Button>
					<Button
						onClick={handleListPanels}
						disabled={loading}
						className="facp-btn-outline inline-flex items-center gap-2 px-4 py-2"
					>
						{loading ? (
							<Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
						) : (
							<ListChecks aria-hidden="true" className="h-4 w-4" />
						)}
						List All Panels
					</Button>
				</div>

				{/* Selection Result */}
				{result && (
					<div className="facp-card">
						<div className="facp-card-header">
							<h2 className="facp-card-title">
								<ShieldCheck
									aria-hidden="true"
									className="h-5 w-5 facp-card-title-icon"
								/>
								Recommended Panel
							</h2>
						</div>
						<div className="facp-card-content">
							<div className="space-y-4">
								<div className="flex flex-wrap items-center gap-3">
									<span className="facp-result-nameplate">
										{result.recommended_model as string}
									</span>
									<span className="facp-result-manufacturer">
										{result.manufacturer as string}
									</span>
								</div>
								<div className="space-y-3">
									<div className="facp-util-row">
										<span className="facp-util-label">
											Capacity Utilization
										</span>
										<span className="facp-util-value">
											{(capacityUtil * 100).toFixed(1)}%
										</span>
										<progress
											className="facp-util-bar"
											value={Math.round(capacityUtil * 100)}
											max={100}
											aria-label="Capacity utilization"
										>
											<div
												className={`facp-util-bar-fill ${utilClass(capacityUtil)}`}
												style={{
													width: `${Math.min(100, capacityUtil * 100)}%`,
												}}
											/>
										</progress>
									</div>
									<div className="facp-util-row">
										<span className="facp-util-label">NAC Utilization</span>
										<span className="facp-util-value">
											{(nacUtil * 100).toFixed(1)}%
										</span>
										<progress
											className="facp-util-bar"
											value={Math.round(nacUtil * 100)}
											max={100}
											aria-label="NAC utilization"
										>
											<div
												className={`facp-util-bar-fill ${utilClass(nacUtil)}`}
												style={{ width: `${Math.min(100, nacUtil * 100)}%` }}
											/>
										</progress>
									</div>
									<div className="facp-util-row">
										<span className="facp-util-label">Battery Size</span>
										<span className="facp-util-value">
											{result.battery_size_ah as number} Ah
										</span>
										<div className="facp-util-bar" aria-hidden="true">
											<div
												className="facp-util-bar-fill ok"
												style={{ width: `100%` }}
											/>
										</div>
									</div>
								</div>
								{result.battery_derating_details ? (
									<dl className="facp-derating-block">
										<dt>Method</dt>
										<dd>
											{
												(
													result.battery_derating_details as Record<
														string,
														unknown
													>
												).method as string
											}
										</dd>
										<dt>Temperature Derating</dt>
										<dd>
											{
												(
													result.battery_derating_details as Record<
														string,
														unknown
													>
												).temperature_derating as number
											}
										</dd>
										<dt>Aging Derating</dt>
										<dd>
											{
												(
													result.battery_derating_details as Record<
														string,
														unknown
													>
												).aging_derating as number
											}
										</dd>
										<dt>Combined Safety Factor</dt>
										<dd>
											{
												(
													result.battery_derating_details as Record<
														string,
														unknown
													>
												).combined_safety_factor as number
											}
										</dd>
									</dl>
								) : null}
							</div>
						</div>
					</div>
				)}

				{/* Panel Database */}
				{panels.length > 0 && (
					<div className="facp-card">
						<div className="facp-card-header">
							<h2 className="facp-card-title">
								<ListChecks
									aria-hidden="true"
									className="h-5 w-5 facp-card-title-icon"
								/>
								Panel Database ({panels.length})
							</h2>
						</div>
						<div className="facp-card-content">
							<div className="space-y-0">
								{panels.map((p) => {
									const panel = p as {
										model: string;
										manufacturer: string;
										device_capacity?: number;
										points_capacity?: number;
										points?: number;
										nac_capacity?: number;
									};
									const devCap =
										panel.device_capacity ??
										panel.points_capacity ??
										panel.points ??
										0;
									const nacCap = panel.nac_capacity ?? 0;
									return (
										<div
											key={`${panel.manufacturer}-${panel.model}`}
											className="facp-panel-row"
										>
											<span className="facp-panel-model">{panel.model}</span>
											<span className="facp-panel-manufacturer">
												{panel.manufacturer}
											</span>
											<span className="facp-panel-capacity">
												{devCap} dev / {nacCap} NAC
											</span>
										</div>
									);
								})}
							</div>
						</div>
					</div>
				)}

				{/* Extended FACP Operations */}
				<div className="facp-card">
					<div className="facp-card-header">
						<h2 className="facp-card-title">Extended Operations</h2>
						<p className="facp-card-desc">
							Verify compliance, generate schedules and specifications
						</p>
					</div>
					<div className="facp-card-content">
						<div className="space-y-4">
							<div className="space-y-1">
								<Label className="facp-field-label">Panel ID</Label>
								<Input
									type="text"
									className="facp-input"
									value={panelId}
									onChange={(e) => setPanelId(e.target.value)}
									placeholder="Enter panel ID..."
								/>
							</div>
							<div className="flex flex-wrap gap-3">
								<Button
									onClick={async () => {
										if (!panelId) {
											toast({
												title: "Panel ID required",
												variant: "destructive",
											});
											return;
										}
										setLoading(true);
										setExtendedResult(null);
										try {
											const res = await facpExtendedApi.verify({
												panel_id: panelId,
											});
											setExtendedResult(res as Record<string, unknown>);
											toast({ title: "Compliance verified" });
										} catch (err) {
											toast({
												title: "Verify failed",
												description:
													err instanceof Error ? err.message : "Failed",
												variant: "destructive",
											});
										} finally {
											setLoading(false);
										}
									}}
									disabled={loading || !panelId}
									className="facp-btn-outline inline-flex items-center gap-2 px-4 py-2"
								>
									{loading ? (
										<Loader2
											aria-hidden="true"
											className="h-4 w-4 animate-spin"
										/>
									) : (
										<ShieldCheck aria-hidden="true" className="h-4 w-4" />
									)}
									Verify Compliance
								</Button>
								<Button
									onClick={async () => {
										if (!panelId) {
											toast({
												title: "Panel ID required",
												variant: "destructive",
											});
											return;
										}
										setLoading(true);
										setExtendedResult(null);
										try {
											const res = await facpExtendedApi.generateSchedule({
												panel_id: panelId,
											});
											setExtendedResult(res as Record<string, unknown>);
											toast({ title: "Schedule generated" });
										} catch (err) {
											toast({
												title: "Schedule failed",
												description:
													err instanceof Error ? err.message : "Failed",
												variant: "destructive",
											});
										} finally {
											setLoading(false);
										}
									}}
									disabled={loading || !panelId}
									className="facp-btn-outline inline-flex items-center gap-2 px-4 py-2"
								>
									{loading ? (
										<Loader2
											aria-hidden="true"
											className="h-4 w-4 animate-spin"
										/>
									) : (
										<FileCode2 aria-hidden="true" className="h-4 w-4" />
									)}
									Generate DXF Schedule
								</Button>
								<Button
									onClick={async () => {
										if (!panelId) {
											toast({
												title: "Panel ID required",
												variant: "destructive",
											});
											return;
										}
										setLoading(true);
										setExtendedResult(null);
										try {
											const res = await facpExtendedApi.generateSpec({
												panel_id: panelId,
											});
											setExtendedResult(res as Record<string, unknown>);
											toast({ title: "Spec generated" });
										} catch (err) {
											toast({
												title: "Spec failed",
												description:
													err instanceof Error ? err.message : "Failed",
												variant: "destructive",
											});
										} finally {
											setLoading(false);
										}
									}}
									disabled={loading || !panelId}
									className="facp-btn-outline inline-flex items-center gap-2 px-4 py-2"
								>
									{loading ? (
										<Loader2
											aria-hidden="true"
											className="h-4 w-4 animate-spin"
										/>
									) : (
										<FileText aria-hidden="true" className="h-4 w-4" />
									)}
									Generate CSI Spec
								</Button>
							</div>
							{extendedResult && (
								<pre className="facp-event-log">
									{JSON.stringify(extendedResult, null, 2)}
								</pre>
							)}
						</div>
					</div>
				</div>

				{/* Distributed FACP Cluster Visualizer */}
				<div className="facp-card">
					<div className="facp-card-header">
						<h2 className="facp-card-title">
							<Cpu
								aria-hidden="true"
								className="h-5 w-5 facp-card-title-icon"
							/>
							Distributed FACP Cluster Visualizer
						</h2>
						<p className="facp-card-desc">
							Real-time cluster node state, leader node status, and event bus
							communicator metrics
						</p>
					</div>
					<div className="facp-card-content">
						<div className="space-y-4">
							<div className="flex items-center justify-between">
								<Button
									onClick={async () => {
										try {
											const res = await facpApi.getClusterStatus();
											setExtendedResult(res as Record<string, unknown>);
											toast({ title: "Cluster status refreshed" });
										} catch (err) {
											toast({
												title: "Cluster status failed",
												description:
													err instanceof Error ? err.message : "Failed",
												variant: "destructive",
											});
										}
									}}
									className="facp-btn-outline inline-flex items-center gap-2 px-4 py-2"
								>
									Fetch Cluster Status
								</Button>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}
