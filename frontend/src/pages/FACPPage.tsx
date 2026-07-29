/**
 * FACPPage.tsx — Fire Alarm Control Panel Selection (NFPA 72 §10.6.10).
 *
 * V216: New page — 5 backend endpoints now have UI.
 * Panel selection, verification, schedule generation, spec, panel list.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Loader2, Cpu, ListChecks, ShieldCheck, Calendar, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { facpApi } from "@/services/fullApi";

/* ─── Form interfaces ────────────────────────────────────────────────────── */

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

interface VerifyForm extends FACPForm {
	recommended_model: string;
	manufacturer: string;
	capacity_utilization: string;
	nac_utilization: string;
	battery_size_ah: string;
	battery_derating_method: string;
}

interface ScheduleForm {
	recommended_model: string;
	manufacturer: string;
	capacity_utilization: string;
	nac_utilization: string;
	battery_size_ah: string;
	battery_derating_method: string;
	power_supply_watts: string;
	listings: string;
	signature_hash: string;
	quantity: string;
}

interface SpecForm extends FACPForm {
	recommended_model: string;
	manufacturer: string;
	capacity_utilization: string;
	nac_utilization: string;
	battery_size_ah: string;
	battery_derating_method: string;
	power_supply_watts: string;
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export function FACPPage() {
	const { t } = useTranslation();

	/* ── Shared state ─────────────────────────────────────────────────── */
	const [selectLoading, setSelectLoading] = useState(false);
	const [verifyLoading, setVerifyLoading] = useState(false);
	const [scheduleLoading, setScheduleLoading] = useState(false);
	const [specLoading, setSpecLoading] = useState(false);

	const [panels, setPanels] = useState<unknown[]>([]);
	const [selectResult, setSelectResult] = useState<Record<string, unknown> | null>(null);
	const [verifyResult, setVerifyResult] = useState<Record<string, unknown> | null>(null);
	const [scheduleResult, setScheduleResult] = useState<Record<string, unknown> | null>(null);
	const [specResult, setSpecResult] = useState<Record<string, unknown> | null>(null);

	/* ── Select form ──────────────────────────────────────────────────── */
	const [selectForm, setSelectForm] = useState<FACPForm>({
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

	/* ── Verify form ──────────────────────────────────────────────────── */
	const [verifyForm, setVerifyForm] = useState<VerifyForm>({
		device_count: "150",
		nac_circuit_count: "4",
		building_size_m2: "3000",
		building_floors: "3",
		requires_network: false,
		requires_voice: false,
		requires_releasing: false,
		jurisdiction: "UL",
		min_temperature_c: "0",
		recommended_model: "",
		manufacturer: "",
		capacity_utilization: "0.5",
		nac_utilization: "0.5",
		battery_size_ah: "55",
		battery_derating_method: "nfpa_aging",
	});

	/* ── Schedule form ────────────────────────────────────────────────── */
	const [scheduleForm, setScheduleForm] = useState<ScheduleForm>({
		recommended_model: "",
		manufacturer: "",
		capacity_utilization: "0.5",
		nac_utilization: "0.5",
		battery_size_ah: "55",
		battery_derating_method: "nfpa_aging",
		power_supply_watts: "100",
		listings: "UL",
		signature_hash: "",
		quantity: "1",
	});

	/* ── Spec form ────────────────────────────────────────────────────── */
	const [specForm, setSpecForm] = useState<SpecForm>({
		device_count: "150",
		nac_circuit_count: "4",
		building_size_m2: "3000",
		building_floors: "3",
		requires_network: false,
		requires_voice: false,
		requires_releasing: false,
		jurisdiction: "UL",
		min_temperature_c: "0",
		recommended_model: "",
		manufacturer: "",
		capacity_utilization: "0.5",
		nac_utilization: "0.5",
		battery_size_ah: "55",
		battery_derating_method: "nfpa_aging",
		power_supply_watts: "100",
	});

	/* ─── Handlers ─────────────────────────────────────────────────────── */

	const handleSelect = async () => {
		setSelectLoading(true);
		setSelectResult(null);
		try {
			const res = await facpApi.select({
				device_count: Number.parseInt(selectForm.device_count),
				nac_circuit_count: Number.parseInt(selectForm.nac_circuit_count),
				building_size_m2: Number.parseFloat(selectForm.building_size_m2),
				building_floors: Number.parseInt(selectForm.building_floors),
				requires_network: selectForm.requires_network,
				requires_voice: selectForm.requires_voice,
				requires_releasing: selectForm.requires_releasing,
				jurisdiction: selectForm.jurisdiction,
				min_temperature_c: Number.parseFloat(selectForm.min_temperature_c),
			});
			setSelectResult(res as Record<string, unknown>);
		} catch (err) {
			toast.error(t("facp.selectFailed"), {
				description: err instanceof Error ? err.message : "Failed",
			});
		} finally {
			setSelectLoading(false);
		}
	};

	const handleListPanels = async () => {
		setSelectLoading(true);
		try {
			const res = await facpApi.getPanels();
			setPanels((res as { panels?: unknown[] }).panels || []);
		} catch (err) {
			toast.error(t("facp.listPanelsFailed"), {
				description: err instanceof Error ? err.message : "Failed",
			});
		} finally {
			setSelectLoading(false);
		}
	};

	const handleVerify = async () => {
		setVerifyLoading(true);
		setVerifyResult(null);
		try {
			const res = await facpApi.verify({
				device_count: Number.parseInt(verifyForm.device_count),
				nac_circuit_count: Number.parseInt(verifyForm.nac_circuit_count),
				building_size_m2: Number.parseFloat(verifyForm.building_size_m2),
				building_floors: Number.parseInt(verifyForm.building_floors),
				requires_network: verifyForm.requires_network,
				requires_voice: verifyForm.requires_voice,
				requires_releasing: verifyForm.requires_releasing,
				jurisdiction: verifyForm.jurisdiction,
				min_temperature_c: Number.parseFloat(verifyForm.min_temperature_c),
				recommended_model: verifyForm.recommended_model,
				manufacturer: verifyForm.manufacturer,
				capacity_utilization: Number.parseFloat(verifyForm.capacity_utilization),
				nac_utilization: Number.parseFloat(verifyForm.nac_utilization),
				battery_size_ah: Number.parseFloat(verifyForm.battery_size_ah),
				battery_derating_method: verifyForm.battery_derating_method,
			});
			setVerifyResult(res as Record<string, unknown>);
		} catch (err) {
			toast.error(t("facp.verifyFailed"), {
				description: err instanceof Error ? err.message : "Failed",
			});
		} finally {
			setVerifyLoading(false);
		}
	};

	const handleSchedule = async () => {
		setScheduleLoading(true);
		setScheduleResult(null);
		try {
			const res = await facpApi.schedule({
				recommended_model: scheduleForm.recommended_model,
				manufacturer: scheduleForm.manufacturer,
				capacity_utilization: Number.parseFloat(scheduleForm.capacity_utilization),
				nac_utilization: Number.parseFloat(scheduleForm.nac_utilization),
				battery_size_ah: Number.parseFloat(scheduleForm.battery_size_ah),
				battery_derating_method: scheduleForm.battery_derating_method,
				power_supply_watts: Number.parseFloat(scheduleForm.power_supply_watts),
				listings: scheduleForm.listings ? scheduleForm.listings.split(",").map((s) => s.trim()) : undefined,
				signature_hash: scheduleForm.signature_hash,
				quantity: scheduleForm.quantity ? Number.parseInt(scheduleForm.quantity) : undefined,
			});
			setScheduleResult(res as Record<string, unknown>);
		} catch (err) {
			toast.error(t("facp.scheduleFailed"), {
				description: err instanceof Error ? err.message : "Failed",
			});
		} finally {
			setScheduleLoading(false);
		}
	};

	const handleSpec = async () => {
		setSpecLoading(true);
		setSpecResult(null);
		try {
			const res = await facpApi.spec({
				device_count: Number.parseInt(specForm.device_count),
				nac_circuit_count: Number.parseInt(specForm.nac_circuit_count),
				building_size_m2: Number.parseFloat(specForm.building_size_m2),
				building_floors: Number.parseInt(specForm.building_floors),
				requires_network: specForm.requires_network,
				requires_voice: specForm.requires_voice,
				requires_releasing: specForm.requires_releasing,
				jurisdiction: specForm.jurisdiction,
				recommended_model: specForm.recommended_model,
				manufacturer: specForm.manufacturer,
				capacity_utilization: Number.parseFloat(specForm.capacity_utilization),
				nac_utilization: Number.parseFloat(specForm.nac_utilization),
				battery_size_ah: Number.parseFloat(specForm.battery_size_ah),
				battery_derating_method: specForm.battery_derating_method,
				power_supply_watts: Number.parseFloat(specForm.power_supply_watts),
			});
			setSpecResult(res as Record<string, unknown>);
		} catch (err) {
			toast.error(t("facp.specFailed"), {
				description: err instanceof Error ? err.message : "Failed",
			});
		} finally {
			setSpecLoading(false);
		}
	};

	/* ─── Shared building-requirements form fragment ──────────────────── */

	const buildingRequirementsFields = (
		form: FACPForm | VerifyForm | SpecForm,
		setter: (update: any) => void,
	) => (
		<>
			<div className="grid grid-cols-2 md:grid-cols-3 gap-4">
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">{t("facp.deviceCount")}</Label>
					<Input
						type="number"
						value={form.device_count}
						onChange={(e) => setter({ ...form, device_count: e.target.value } as typeof form)}
					/>
				</div>
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">{t("facp.nacCircuits")}</Label>
					<Input
						type="number"
						value={form.nac_circuit_count}
						onChange={(e) => setter({ ...form, nac_circuit_count: e.target.value } as typeof form)}
					/>
				</div>
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">{t("facp.buildingSize")}</Label>
					<Input
						type="number"
						value={form.building_size_m2}
						onChange={(e) => setter({ ...form, building_size_m2: e.target.value } as typeof form)}
					/>
				</div>
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">{t("facp.buildingFloors")}</Label>
					<Input
						type="number"
						value={form.building_floors}
						onChange={(e) => setter({ ...form, building_floors: e.target.value } as typeof form)}
					/>
				</div>
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">{t("facp.minTemp")}</Label>
					<Input
						type="number"
						value={form.min_temperature_c}
						onChange={(e) => setter({ ...form, min_temperature_c: e.target.value } as typeof form)}
					/>
				</div>
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">{t("facp.jurisdiction")}</Label>
					<Select
						value={form.jurisdiction}
						onValueChange={(v) => setter({ ...form, jurisdiction: v } as typeof form)}
					>
						<SelectTrigger>
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
						id={`network-${form.jurisdiction}`}
						checked={form.requires_network}
						onCheckedChange={(v) => setter({ ...form, requires_network: v === true } as typeof form)}
					/>
					<Label htmlFor={`network-${form.jurisdiction}`} className="text-xs text-muted-foreground cursor-pointer">
						{t("facp.networked")}
					</Label>
				</div>
				<div className="flex items-center gap-2">
					<Checkbox
						id={`voice-${form.jurisdiction}`}
						checked={form.requires_voice}
						onCheckedChange={(v) => setter({ ...form, requires_voice: v === true } as typeof form)}
					/>
					<Label htmlFor={`voice-${form.jurisdiction}`} className="text-xs text-muted-foreground cursor-pointer">
						{t("facp.voiceEvac")}
					</Label>
				</div>
				<div className="flex items-center gap-2">
					<Checkbox
						id={`releasing-${form.jurisdiction}`}
						checked={form.requires_releasing}
						onCheckedChange={(v) => setter({ ...form, requires_releasing: v === true } as typeof form)}
					/>
					<Label htmlFor={`releasing-${form.jurisdiction}`} className="text-xs text-muted-foreground cursor-pointer">
						{t("facp.releasingService")}
					</Label>
				</div>
			</div>
		</>
	);

	/* ─── Panel detail fields fragment (verify / schedule / spec) ─────── */

	const panelDetailFields = (
		form: VerifyForm | ScheduleForm | SpecForm,
		setter: (update: any) => void,
		showPowerSupply: boolean,
	) => (
		<div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-4">
			<div className="space-y-1.5">
				<Label className="text-xs text-muted-foreground">{t("facp.recommendedModel")}</Label>
				<Input
					value={form.recommended_model}
					onChange={(e) => setter({ ...form, recommended_model: e.target.value } as typeof form)}
				/>
			</div>
			<div className="space-y-1.5">
				<Label className="text-xs text-muted-foreground">{t("facp.manufacturer")}</Label>
				<Input
					value={form.manufacturer}
					onChange={(e) => setter({ ...form, manufacturer: e.target.value } as typeof form)}
				/>
			</div>
			<div className="space-y-1.5">
				<Label className="text-xs text-muted-foreground">{t("facp.capacityUtilization")}</Label>
				<Input
					type="number"
					step="0.01"
					value={form.capacity_utilization}
					onChange={(e) => setter({ ...form, capacity_utilization: e.target.value } as typeof form)}
				/>
			</div>
			<div className="space-y-1.5">
				<Label className="text-xs text-muted-foreground">{t("facp.nacUtilization")}</Label>
				<Input
					type="number"
					step="0.01"
					value={form.nac_utilization}
					onChange={(e) => setter({ ...form, nac_utilization: e.target.value } as typeof form)}
				/>
			</div>
			<div className="space-y-1.5">
				<Label className="text-xs text-muted-foreground">{t("facp.batterySizeAh")}</Label>
				<Input
					type="number"
					step="0.1"
					value={form.battery_size_ah}
					onChange={(e) => setter({ ...form, battery_size_ah: e.target.value } as typeof form)}
				/>
			</div>
			<div className="space-y-1.5">
				<Label className="text-xs text-muted-foreground">{t("facp.batteryDeratingMethod")}</Label>
				<Select
					value={form.battery_derating_method}
					onValueChange={(v) => setter({ ...form, battery_derating_method: v } as typeof form)}
				>
					<SelectTrigger>
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						<SelectItem value="nfpa_aging">NFPA Aging</SelectItem>
						<SelectItem value="temperature_only">Temperature Only</SelectItem>
						<SelectItem value="none">None</SelectItem>
					</SelectContent>
				</Select>
			</div>
			{showPowerSupply && "power_supply_watts" in form && (
				<div className="space-y-1.5">
					<Label className="text-xs text-muted-foreground">{t("facp.powerSupplyWatts")}</Label>
					<Input
						type="number"
						step="1"
						value={(form as ScheduleForm | SpecForm).power_supply_watts}
						onChange={(e) => setter({ ...form, power_supply_watts: e.target.value } as typeof form)}
					/>
				</div>
			)}
		</div>
	);

	/* ─── Render ───────────────────────────────────────────────────────── */

	return (
		<div className="flex-1 overflow-auto">
			<div className="p-6 max-w-5xl mx-auto space-y-6">
				<div>
					<h1 className="text-lg font-semibold text-foreground flex items-center gap-2">
						<Cpu aria-hidden="true" className="h-5 w-5 text-primary" />
						{t("facp.title")}
					</h1>
					<p className="text-sm text-muted-foreground mt-1">
						{t("facp.subtitle")}
					</p>
				</div>

				<Tabs defaultValue="select" className="space-y-4">
					<TabsList>
						<TabsTrigger value="select">{t("facp.selectTab")}</TabsTrigger>
						<TabsTrigger value="verify">{t("facp.verifyTab")}</TabsTrigger>
						<TabsTrigger value="schedule">{t("facp.scheduleTab")}</TabsTrigger>
						<TabsTrigger value="spec">{t("facp.specTab")}</TabsTrigger>
					</TabsList>

					{/* ─── SELECT TAB ─────────────────────────────────────── */}
					<TabsContent value="select" className="space-y-4">
						<Card>
							<CardHeader>
								<CardTitle>{t("facp.projectRequirements")}</CardTitle>
								<CardDescription>{t("facp.projectRequirementsDesc")}</CardDescription>
							</CardHeader>
							<CardContent>
								{buildingRequirementsFields(selectForm, setSelectForm as React.Dispatch<React.SetStateAction<FACPForm>>)}
							</CardContent>
						</Card>

						<div className="flex gap-3">
							<Button onClick={handleSelect} disabled={selectLoading}>
								{selectLoading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Cpu aria-hidden="true" className="h-4 w-4" />}
								{t("facp.selectPanel")}
							</Button>
							<Button onClick={handleListPanels} disabled={selectLoading} variant="outline">
								{selectLoading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <ListChecks aria-hidden="true" className="h-4 w-4" />}
								{t("facp.listAllPanels")}
							</Button>
						</div>

						{selectResult && (
							<Card>
								<CardHeader>
									<CardTitle>{t("facp.recommendedPanel")}</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="space-y-3">
										<div className="flex items-center gap-3">
											<Badge variant="default" className="text-sm">
												{selectResult.recommended_model as string}
											</Badge>
											<span className="text-sm text-muted-foreground">
												{selectResult.manufacturer as string}
											</span>
										</div>
										<div className="grid grid-cols-2 gap-3 text-sm">
											<div>
												<span className="text-muted-foreground">{t("facp.capacityUtil")}</span>
												<span className="font-mono text-foreground">
													{((selectResult.capacity_utilization as number) * 100).toFixed(1)}%
												</span>
											</div>
											<div>
												<span className="text-muted-foreground">{t("facp.nacUtil")}</span>
												<span className="font-mono text-foreground">
													{((selectResult.nac_utilization as number) * 100).toFixed(1)}%
												</span>
											</div>
											<div>
												<span className="text-muted-foreground">{t("facp.batterySize")}</span>
												<span className="font-mono text-foreground">
													{selectResult.battery_size_ah as number} Ah
												</span>
											</div>
										</div>
										{selectResult.battery_derating_details ? (
											<div className="text-xs text-muted-foreground bg-muted p-3 rounded-md">
												<div>{t("facp.method")}{(selectResult.battery_derating_details as Record<string, unknown>).method as string}</div>
												<div>{t("facp.tempDerating")}{(selectResult.battery_derating_details as Record<string, unknown>).temperature_derating as number}</div>
												<div>{t("facp.agingDerating")}{(selectResult.battery_derating_details as Record<string, unknown>).aging_derating as number}</div>
												<div>{t("facp.combinedSafety")}{(selectResult.battery_derating_details as Record<string, unknown>).combined_safety_factor as number}</div>
											</div>
										) : null}
									</div>
								</CardContent>
							</Card>
						)}

						{panels.length > 0 && (
							<Card>
								<CardHeader>
									<CardTitle>{t("facp.panelDatabase")} ({panels.length})</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="space-y-2">
										{panels.map((p, i) => {
											const panel = p as { model: string; manufacturer: string; device_capacity: number; nac_capacity: number };
											return (
												<div key={i} className="flex items-center justify-between text-sm border-b border-border pb-2">
													<span className="font-mono text-foreground">{panel.model}</span>
													<span className="text-muted-foreground">{panel.manufacturer}</span>
													<span className="font-mono text-muted-foreground">
														{panel.device_capacity} dev / {panel.nac_capacity} NAC
													</span>
												</div>
											);
										})}
									</div>
								</CardContent>
							</Card>
						)}
					</TabsContent>

					{/* ─── VERIFY TAB ─────────────────────────────────────── */}
					<TabsContent value="verify" className="space-y-4">
						<Card>
							<CardHeader>
								<CardTitle>{t("facp.verifyParams")}</CardTitle>
								<CardDescription>{t("facp.verifyParamsDesc")}</CardDescription>
							</CardHeader>
							<CardContent>
								{buildingRequirementsFields(verifyForm, setVerifyForm as React.Dispatch<React.SetStateAction<VerifyForm>>)}
								{panelDetailFields(verifyForm, setVerifyForm as React.Dispatch<React.SetStateAction<VerifyForm>>, false)}
							</CardContent>
						</Card>

						<Button onClick={handleVerify} disabled={verifyLoading}>
							{verifyLoading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <ShieldCheck aria-hidden="true" className="h-4 w-4" />}
							{t("facp.verifyCompliance")}
						</Button>

						{verifyResult && (
							<Card>
								<CardHeader>
									<CardTitle>{t("facp.verifyResult")}</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="space-y-3">
										<div className="flex items-center gap-2">
											<Badge variant={verifyResult.compliant ? "default" : "destructive"}>
												{verifyResult.compliant ? t("facp.compliant") : t("facp.violations")}
											</Badge>
										</div>
										{Array.isArray(verifyResult.violations) && (verifyResult.violations as unknown[]).length > 0 && (
											<div className="bg-muted/50 p-3 rounded-md">
												<p className="text-xs font-semibold text-muted-foreground mb-1">{t("facp.violations")}</p>
												<ul className="text-sm text-foreground space-y-1">
													{(verifyResult.violations as string[]).map((v, i) => (
														<li key={i} className="flex items-start gap-2">
															<span className="text-destructive mt-0.5">•</span>
															{v}
														</li>
													))}
												</ul>
											</div>
										)}
										{Array.isArray(verifyResult.warnings) && (verifyResult.warnings as unknown[]).length > 0 && (
											<div className="bg-muted/50 p-3 rounded-md">
												<p className="text-xs font-semibold text-muted-foreground mb-1">{t("facp.warnings")}</p>
												<ul className="text-sm text-foreground space-y-1">
													{(verifyResult.warnings as string[]).map((w, i) => (
														<li key={i} className="flex items-start gap-2">
															<span className="text-yellow-500 mt-0.5">•</span>
															{w}
														</li>
													))}
												</ul>
											</div>
										)}
										{Array.isArray(verifyResult.code_references) && (verifyResult.code_references as unknown[]).length > 0 && (
											<div className="bg-muted/50 p-3 rounded-md">
												<p className="text-xs font-semibold text-muted-foreground mb-1">{t("facp.codeReferences")}</p>
												<div className="text-sm font-mono text-foreground">
													{(verifyResult.code_references as string[]).join(", ")}
												</div>
											</div>
										)}
									</div>
								</CardContent>
							</Card>
						)}
					</TabsContent>

					{/* ─── SCHEDULE TAB ───────────────────────────────────── */}
					<TabsContent value="schedule" className="space-y-4">
						<Card>
							<CardHeader>
								<CardTitle>{t("facp.scheduleParams")}</CardTitle>
								<CardDescription>{t("facp.scheduleParamsDesc")}</CardDescription>
							</CardHeader>
							<CardContent>
								<div className="grid grid-cols-2 md:grid-cols-3 gap-4">
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.recommendedModel")}</Label>
										<Input
											value={scheduleForm.recommended_model}
											onChange={(e) => setScheduleForm({ ...scheduleForm, recommended_model: e.target.value })}
										/>
									</div>
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.manufacturer")}</Label>
										<Input
											value={scheduleForm.manufacturer}
											onChange={(e) => setScheduleForm({ ...scheduleForm, manufacturer: e.target.value })}
										/>
									</div>
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.capacityUtilization")}</Label>
										<Input
											type="number"
											step="0.01"
											value={scheduleForm.capacity_utilization}
											onChange={(e) => setScheduleForm({ ...scheduleForm, capacity_utilization: e.target.value })}
										/>
									</div>
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.nacUtilization")}</Label>
										<Input
											type="number"
											step="0.01"
											value={scheduleForm.nac_utilization}
											onChange={(e) => setScheduleForm({ ...scheduleForm, nac_utilization: e.target.value })}
										/>
									</div>
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.batterySizeAh")}</Label>
										<Input
											type="number"
											step="0.1"
											value={scheduleForm.battery_size_ah}
											onChange={(e) => setScheduleForm({ ...scheduleForm, battery_size_ah: e.target.value })}
										/>
									</div>
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.batteryDeratingMethod")}</Label>
										<Select
											value={scheduleForm.battery_derating_method}
											onValueChange={(v) => setScheduleForm({ ...scheduleForm, battery_derating_method: v })}
										>
											<SelectTrigger>
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="nfpa_aging">NFPA Aging</SelectItem>
												<SelectItem value="temperature_only">Temperature Only</SelectItem>
												<SelectItem value="none">None</SelectItem>
											</SelectContent>
										</Select>
									</div>
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.powerSupplyWatts")}</Label>
										<Input
											type="number"
											step="1"
											value={scheduleForm.power_supply_watts}
											onChange={(e) => setScheduleForm({ ...scheduleForm, power_supply_watts: e.target.value })}
										/>
									</div>
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.listings")}</Label>
										<Input
											value={scheduleForm.listings}
											placeholder="UL, FM (comma-separated)"
											onChange={(e) => setScheduleForm({ ...scheduleForm, listings: e.target.value })}
										/>
									</div>
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.signatureHash")}</Label>
										<Input
											value={scheduleForm.signature_hash}
											onChange={(e) => setScheduleForm({ ...scheduleForm, signature_hash: e.target.value })}
										/>
									</div>
									<div className="space-y-1.5">
										<Label className="text-xs text-muted-foreground">{t("facp.quantity")}</Label>
										<Input
											type="number"
											value={scheduleForm.quantity}
											onChange={(e) => setScheduleForm({ ...scheduleForm, quantity: e.target.value })}
										/>
									</div>
								</div>
							</CardContent>
						</Card>

						<Button onClick={handleSchedule} disabled={scheduleLoading}>
							{scheduleLoading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <Calendar aria-hidden="true" className="h-4 w-4" />}
							{t("facp.generateSchedule")}
						</Button>

						{scheduleResult && (
							<Card>
								<CardHeader>
									<CardTitle>{t("facp.scheduleResult")}</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="bg-muted/50 p-3 rounded-md">
										<pre className="text-sm font-mono text-foreground whitespace-pre-wrap break-words">
											{typeof scheduleResult.dxf === "string"
												? (scheduleResult.dxf as string)
												: JSON.stringify(scheduleResult, null, 2)}
										</pre>
									</div>
								</CardContent>
							</Card>
						)}
					</TabsContent>

					{/* ─── SPEC TAB ───────────────────────────────────────── */}
					<TabsContent value="spec" className="space-y-4">
						<Card>
							<CardHeader>
								<CardTitle>{t("facp.specParams")}</CardTitle>
								<CardDescription>{t("facp.specParamsDesc")}</CardDescription>
							</CardHeader>
							<CardContent>
								{buildingRequirementsFields(specForm, setSpecForm as React.Dispatch<React.SetStateAction<SpecForm>>)}
								{panelDetailFields(specForm, setSpecForm as React.Dispatch<React.SetStateAction<SpecForm>>, true)}
							</CardContent>
						</Card>

						<Button onClick={handleSpec} disabled={specLoading}>
							{specLoading ? <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" /> : <FileText aria-hidden="true" className="h-4 w-4" />}
							{t("facp.generateSpec")}
						</Button>

						{specResult && (
							<Card>
								<CardHeader>
									<CardTitle>{t("facp.specResult")}</CardTitle>
								</CardHeader>
								<CardContent>
									<div className="bg-muted/50 p-3 rounded-md">
										<pre className="text-sm font-mono text-foreground whitespace-pre-wrap break-words">
											{typeof specResult.specification === "string"
												? (specResult.specification as string)
												: JSON.stringify(specResult, null, 2)}
										</pre>
									</div>
								</CardContent>
							</Card>
						)}
					</TabsContent>
				</Tabs>
			</div>
		</div>
	);
}
