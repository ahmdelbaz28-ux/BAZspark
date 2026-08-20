import type React from "react";
import { createContext, useCallback, useContext, useMemo, useState } from "react";

export interface PreviewDevice {
	id: string;
	x_m: number;
	y_m: number;
	z_m: number;
	type: "smoke" | "heat" | "pull" | "horns" | "speaker" | "facp" | "iso";
	coverage_radius_m: number;
	spacing_m: number;
	candela?: number;
}

export interface CircuitPreview {
	circuitId: string;
	voltageDropV: number;
	voltageDropPct: number;
	terminalVoltageV: number;
	resistanceTotalOhm?: number;
	isCompliant: boolean;
	recommendedAwg: string;
	violations?: string[];
}

export interface HydraulicPreview {
	pipeSegmentId: string;
	flowVelocityMS: number;
	reynoldsNumber: number;
	frictionFactor: number;
	headLossM: number;
	pressureLossPsi: number;
	totalPressureLossPsi: number;
	flowRegime: string;
	isCompliant: boolean;
	warnings: string[];
}

export interface BatteryPreview {
	panelId: string;
	baseCapacityAh: number;
	requiredAh: number;
	installedAh?: number;
	usableAh?: number;
	temperatureDerating: number;
	agingDerating: number;
	dischargeRateCorrection: number;
	isAdequate: boolean;
	marginPct?: number;
	warnings: string[];
}

export interface WorkflowStepResultPreview {
	nodeId: string;
	capabilityId: string;
	commandId: string;
	success: boolean;
	resultData: Record<string, unknown>;
	errorCode?: string;
	errorMessage?: string;
}

export interface CompositeWorkflowPreview {
	workflowId: string;
	correlationId: string;
	projectId: string;
	expectedRevision: number;
	dag: { nodes: Array<{ node_id: string; capability_id: string; dependencies?: string[]; payload_template?: Record<string, unknown>; description?: string }> };
	stepResults: WorkflowStepResultPreview[];
	projectedState: {
		devices?: PreviewDevice[];
		circuits?: Record<string, unknown>;
		hydraulics?: Record<string, unknown>;
		calculations?: Record<string, unknown>;
		revision: number;
	};
	combinedAuditDigest: string;
	isCompliant: boolean;
	tokenTelemetry?: {
		measured_tokens: number;
		budget_limit: number;
		utilization_pct: number;
	};
}

export interface DomainCommandPreview {
	commandId: string;
	correlationId: string;
	projectId: string;
	expectedRevision: number;
	capabilityId: string;
	previewDevices: PreviewDevice[];
	circuitPreview?: CircuitPreview;
	hydraulicPreview?: HydraulicPreview;
	batteryPreview?: BatteryPreview;
	compositePreview?: CompositeWorkflowPreview;
	deviceCount: number;
	coveragePct: number;
	isCompliant: boolean;
	tokenTelemetry?: {
		measured_tokens: number;
		budget_limit: number;
		utilization_pct: number;
	};
	payload: Record<string, unknown>;
}

export interface AIControllerContextValue {
	isAiActive: boolean;
	isPlanning: boolean;
	previewDevices: PreviewDevice[];
	proposedCommand: DomainCommandPreview | null;
	compositeProposal: CompositeWorkflowPreview | null;
	concurrencyError: string | null;
	currentRevision: number;
	tokenTelemetry: { measured_tokens: number; budget_limit: number; utilization_pct: number } | null;
	submitIntent: (
		projectId: string,
		roomId: string,
		roomBounds: { width_m: number; length_m: number; ceiling_height_m: number },
		detectorType?: string,
	) => Promise<DomainCommandPreview | null>;
	submitElectricalIntent: (
		projectId: string,
		circuitId: string,
		circuitSpec: {
			current_a: number;
			one_way_length_m: number;
			awg: string;
			nominal_voltage?: number;
			temperature_c?: number;
		},
	) => Promise<DomainCommandPreview | null>;
	submitHydraulicIntent: (
		projectId: string,
		pipeSegmentId: string,
		hydraulicSpec?: {
			length_m?: number;
			diameter_mm?: number;
			flow_rate_kg_s?: number;
			flow_l_min?: number;
			fluid_type?: string;
			roughness_mm?: number;
			elevation_m?: number;
		},
	) => Promise<DomainCommandPreview | null>;
	submitBatteryIntent: (
		projectId: string,
		panelId: string,
		batterySpec?: {
			standby_load_amps?: number;
			alarm_load_amps?: number;
			standby_hours?: number;
			alarm_hours?: number;
			min_temperature_c?: number;
			service_life_years?: number;
			battery_type?: string;
			installed_ah?: number;
			aging_factor?: number;
		},
	) => Promise<DomainCommandPreview | null>;
	submitCompositeIntent: (
		projectId: string,
		compositeSpec?: {
			room_bounds?: { width_m: number; length_m: number; ceiling_height_m: number };
			circuit?: { circuit_id: string; current_a: number; one_way_length_m: number; awg: string };
			hydraulic?: { pipe_segment_id: string; length_m: number; diameter_mm: number; flow_l_min: number };
			battery?: { panel_id: string; standby_load_amps: number; alarm_load_amps: number; installed_ah?: number };
		},
		nodes?: Array<{ node_id: string; capability_id: string; dependencies?: string[]; payload_template?: Record<string, unknown>; description?: string }>,
	) => Promise<DomainCommandPreview | null>;
	approveProposal: (
		onCommitted?: (
			devices: PreviewDevice[],
			revision: number,
			circuit?: CircuitPreview,
			hydraulic?: HydraulicPreview,
			battery?: BatteryPreview,
		) => void,
	) => Promise<boolean>;
	approveCompositeProposal: (
		onCommitted?: (
			projectedState: Record<string, unknown>,
			revision: number,
			stepResults: WorkflowStepResultPreview[],
		) => void,
	) => Promise<boolean>;
	rejectProposal: () => void;
	replan: () => Promise<void>;
	simulateUserEdit: (projectId: string) => void;
}

const AIControllerContext = createContext<AIControllerContextValue | null>(null);

export const AIControllerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
	const [isAiActive, setIsAiActive] = useState<boolean>(false);
	const [isPlanning, setIsPlanning] = useState<boolean>(false);
	const [previewDevices, setPreviewDevices] = useState<PreviewDevice[]>([]);
	const [proposedCommand, setProposedCommand] = useState<DomainCommandPreview | null>(null);
	const [compositeProposal, setCompositeProposal] = useState<CompositeWorkflowPreview | null>(null);
	const [concurrencyError, setConcurrencyError] = useState<string | null>(null);
	const [currentRevision, setCurrentRevision] = useState<number>(1);
	const [tokenTelemetry, setTokenTelemetry] = useState<{ measured_tokens: number; budget_limit: number; utilization_pct: number } | null>(null);

	const [lastIntentParams, setLastIntentParams] = useState<{
		projectId: string;
		roomId: string;
		roomBounds: { width_m: number; length_m: number; ceiling_height_m: number };
		detectorType?: string;
	} | null>(null);

	const submitIntent = useCallback(
		async (
			projectId: string,
			roomId: string,
			roomBounds: { width_m: number; length_m: number; ceiling_height_m: number },
			detectorType: string = "smoke",
		): Promise<DomainCommandPreview | null> => {
			setIsPlanning(true);
			setConcurrencyError(null);
			setLastIntentParams({ projectId, roomId, roomBounds, detectorType });

			const simulatedDevices: PreviewDevice[] = [
				{
					id: `det-p1-${Date.now()}`,
					x_m: roomBounds.width_m / 2,
					y_m: roomBounds.length_m / 2,
					z_m: roomBounds.ceiling_height_m,
					type: detectorType as "smoke" | "heat",
					coverage_radius_m: 6.37,
					spacing_m: 9.1,
				},
			];

			const preview: DomainCommandPreview = {
				commandId: `cmd-dryrun-${Date.now()}`,
				correlationId: `corr-${Date.now()}`,
				projectId,
				expectedRevision: currentRevision,
				capabilityId: "spatial.place_devices",
				previewDevices: simulatedDevices,
				deviceCount: simulatedDevices.length,
				coveragePct: 100.0,
				isCompliant: true,
				tokenTelemetry: {
					measured_tokens: 120,
					budget_limit: 1500,
					utilization_pct: 8.0,
				},
				payload: {
					room_id: roomId,
					width_m: roomBounds.width_m,
					length_m: roomBounds.length_m,
					ceiling_height_m: roomBounds.ceiling_height_m,
					detector_type: detectorType,
				},
			};

			setPreviewDevices(simulatedDevices);
			setProposedCommand(preview);
			setTokenTelemetry(preview.tokenTelemetry ?? null);
			setIsAiActive(true);
			setIsPlanning(false);
			return preview;
		},
		[currentRevision],
	);

	const submitElectricalIntent = useCallback(
		async (
			projectId: string,
			circuitId: string,
			circuitSpec: {
				current_a: number;
				one_way_length_m: number;
				awg: string;
				nominal_voltage?: number;
			},
		): Promise<DomainCommandPreview | null> => {
			setIsPlanning(true);
			setConcurrencyError(null);

			const vNom = circuitSpec.nominal_voltage ?? 24.0;
			const vDropV = 1.25;
			const vDropPct = (vDropV / vNom) * 100;
			const isCompliant = vDropPct <= 10.0;

			const preview: DomainCommandPreview = {
				commandId: `cmd-dryrun-${Date.now()}`,
				correlationId: `corr-${Date.now()}`,
				projectId,
				expectedRevision: currentRevision,
				capabilityId: "electrical.calculate_voltage_drop",
				previewDevices: [],
				circuitPreview: {
					circuitId,
					voltageDropV: vDropV,
					voltageDropPct: Number(vDropPct.toFixed(2)),
					terminalVoltageV: Number((vNom - vDropV).toFixed(2)),
					resistanceTotalOhm: 0.833,
					isCompliant,
					recommendedAwg: circuitSpec.awg,
					violations: isCompliant ? [] : ["Voltage drop exceeds 10% limit."],
				},
				deviceCount: 0,
				coveragePct: 100.0,
				isCompliant,
				tokenTelemetry: {
					measured_tokens: 112,
					budget_limit: 1500,
					utilization_pct: 7.47,
				},
				payload: {
					circuit_id: circuitId,
					...circuitSpec,
				},
			};

			setPreviewDevices([]);
			setProposedCommand(preview);
			setTokenTelemetry(preview.tokenTelemetry ?? null);
			setIsAiActive(true);
			setIsPlanning(false);
			return preview;
		},
		[currentRevision],
	);

	const submitHydraulicIntent = useCallback(
		async (
			projectId: string,
			pipeSegmentId: string,
			hydraulicSpec?: {
				length_m?: number;
				diameter_mm?: number;
				flow_rate_kg_s?: number;
				flow_l_min?: number;
				fluid_type?: string;
				roughness_mm?: number;
				elevation_m?: number;
			},
		): Promise<DomainCommandPreview | null> => {
			setIsPlanning(true);
			setConcurrencyError(null);

			const spec = hydraulicSpec ?? {};
			const lengthM = spec.length_m ?? 15.0;
			const diameterMm = spec.diameter_mm ?? 50.0;
			const diameterM = diameterMm / 1000.0;
			const area = (Math.PI * diameterM * diameterM) / 4.0;
			const rho = 999.7;
			const flowKgS = spec.flow_rate_kg_s ?? ((spec.flow_l_min ?? 250.0) / 60000.0) * rho;
			const flowLMin = spec.flow_l_min ?? ((flowKgS / rho) * 60000.0);
			const velocity = flowKgS / (rho * area);
			const isCompliant = true;
			const warnings: string[] = [];
			if (velocity > 10.0) {
				warnings.push("Excessive flow velocity flag: risk of erosion and water hammer.");
			} else if (velocity > 5.0) {
				warnings.push("High flow velocity flag: exceeds standard distribution main velocity guideline (5.0 m/s).");
			}

			const preview: DomainCommandPreview = {
				commandId: `cmd-dryrun-${Date.now()}`,
				correlationId: `corr-${Date.now()}`,
				projectId,
				expectedRevision: currentRevision,
				capabilityId: "hydraulics.solve_darcy_weisbach",
				previewDevices: [],
				hydraulicPreview: {
					pipeSegmentId,
					flowVelocityMS: Number(velocity.toFixed(3)),
					reynoldsNumber: Number(((rho * velocity * diameterM) / 0.001002).toFixed(1)),
					frictionFactor: 0.0215,
					headLossM: 1.45,
					pressureLossPsi: 2.06,
					totalPressureLossPsi: 2.06,
					flowRegime: velocity > 0 ? "turbulent" : "no_flow",
					isCompliant,
					warnings,
				},
				deviceCount: 0,
				coveragePct: 100.0,
				isCompliant,
				tokenTelemetry: {
					measured_tokens: 125,
					budget_limit: 1500,
					utilization_pct: 8.33,
				},
				payload: {
					pipe_segment_id: pipeSegmentId,
					length_m: lengthM,
					diameter_mm: diameterMm,
					flow_rate_kg_s: flowKgS,
					flow_l_min: flowLMin,
					fluid_type: spec.fluid_type ?? "water",
					roughness_mm: spec.roughness_mm ?? 0.0457,
					elevation_m: spec.elevation_m ?? 0.0,
				},
			};

			setPreviewDevices([]);
			setProposedCommand(preview);
			setTokenTelemetry(preview.tokenTelemetry ?? null);
			setIsAiActive(true);
			setIsPlanning(false);
			return preview;
		},
		[currentRevision],
	);

	const submitBatteryIntent = useCallback(
		async (
			projectId: string,
			panelId: string,
			batterySpec?: {
				standby_load_amps?: number;
				alarm_load_amps?: number;
				standby_hours?: number;
				alarm_hours?: number;
				min_temperature_c?: number;
				service_life_years?: number;
				battery_type?: string;
				installed_ah?: number;
				aging_factor?: number;
			},
		): Promise<DomainCommandPreview | null> => {
			setIsPlanning(true);
			setConcurrencyError(null);

			const spec = batterySpec ?? {};
			const standbyLoadAmps = spec.standby_load_amps ?? 0.5;
			const alarmLoadAmps = spec.alarm_load_amps ?? 2.0;
			const standbyHours = spec.standby_hours ?? 24.0;
			const alarmHours = spec.alarm_hours ?? 5.0 / 60.0;
			const minTempC = spec.min_temperature_c ?? 20.0;
			const serviceLife = spec.service_life_years ?? 5.0;
			const bType = spec.battery_type ?? "vrla";
			const installedAh = spec.installed_ah;
			const agingFactor = spec.aging_factor ?? 1.25;

			const baseAh = standbyLoadAmps * standbyHours + alarmLoadAmps * alarmHours;
			const tempDerating = minTempC >= 20.0 ? 0.95 : (minTempC >= 0.0 ? 0.72 : 0.60);
			const agingDerating = 0.80;
			const dischargeRateCorrection = 0.90;
			const requiredAh = Number(((baseAh * agingFactor) / (tempDerating * agingDerating * dischargeRateCorrection)).toFixed(2));
			const isAdequate = installedAh ? installedAh >= requiredAh : true;
			const usableAh = installedAh ? Number((installedAh * tempDerating * agingDerating).toFixed(2)) : undefined;
			const marginPct = installedAh ? Number((((installedAh - requiredAh) / requiredAh) * 100).toFixed(2)) : undefined;

			const warnings: string[] = [];
			if (bType === "lifepo4" && minTempC < 0.0) {
				warnings.push("Low temperature warning: LiFePO4 charging below 0°C risks lithium plating.");
			} else if (bType === "vrla" && minTempC < -10.0) {
				warnings.push("Severe cold warning: VRLA capacity drops below 60% of rated value.");
			}

			const preview: DomainCommandPreview = {
				commandId: `cmd-dryrun-${Date.now()}`,
				correlationId: `corr-${Date.now()}`,
				projectId,
				expectedRevision: currentRevision,
				capabilityId: "electrical.calculate_battery",
				previewDevices: [],
				batteryPreview: {
					panelId,
					baseCapacityAh: Number(baseAh.toFixed(3)),
					requiredAh,
					installedAh,
					usableAh,
					temperatureDerating: tempDerating,
					agingDerating,
					dischargeRateCorrection,
					isAdequate,
					marginPct,
					warnings,
				},
				deviceCount: 0,
				coveragePct: 100.0,
				isCompliant: isAdequate,
				tokenTelemetry: {
					measured_tokens: 118,
					budget_limit: 1500,
					utilization_pct: 7.87,
				},
				payload: {
					panel_id: panelId,
					standby_load_amps: standbyLoadAmps,
					alarm_load_amps: alarmLoadAmps,
					standby_hours: standbyHours,
					alarm_hours: alarmHours,
					min_temperature_c: minTempC,
					service_life_years: serviceLife,
					battery_type: bType,
					installed_ah: installedAh,
					aging_factor: agingFactor,
				},
			};

			setPreviewDevices([]);
			setProposedCommand(preview);
			setTokenTelemetry(preview.tokenTelemetry ?? null);
			setIsAiActive(true);
			setIsPlanning(false);
			return preview;
		},
		[currentRevision],
	);

	const submitCompositeIntent = useCallback(
		async (
			projectId: string,
			compositeSpec?: {
				room_bounds?: { width_m: number; length_m: number; ceiling_height_m: number };
				circuit?: { circuit_id: string; current_a: number; one_way_length_m: number; awg: string };
				hydraulic?: { pipe_segment_id: string; length_m: number; diameter_mm: number; flow_l_min: number };
				battery?: { panel_id: string; standby_load_amps: number; alarm_load_amps: number; installed_ah?: number };
			},
			nodes?: Array<{ node_id: string; capability_id: string; dependencies?: string[]; payload_template?: Record<string, unknown>; description?: string }>,
		): Promise<DomainCommandPreview | null> => {
			setIsPlanning(true);
			setConcurrencyError(null);

			const spec = compositeSpec ?? {};
			const rb = spec.room_bounds ?? { width_m: 12.0, length_m: 16.0, ceiling_height_m: 3.2 };
			const circ = spec.circuit ?? { circuit_id: "nac-01", current_a: 2.0, one_way_length_m: 35.0, awg: "14" };
			const bat = spec.battery ?? { panel_id: "facp-01", standby_load_amps: 0.8, alarm_load_amps: 3.0, installed_ah: 55.0 };

			const workflowDag = {
				nodes: nodes ?? [
					{ node_id: "step-1-spatial", capability_id: "spatial.place_devices", dependencies: [], payload_template: rb },
					{ node_id: "step-2-electrical", capability_id: "electrical.calculate_voltage_drop", dependencies: ["step-1-spatial"], payload_template: circ },
					{ node_id: "step-3-battery", capability_id: "electrical.calculate_battery", dependencies: ["step-2-electrical"], payload_template: bat },
				],
			};

			const simulatedDevices: PreviewDevice[] = [
				{ id: "dev-comp-01", type: "smoke", x_m: 3.0, y_m: 4.0, z_m: 3.2, coverage_radius_m: 6.4, spacing_m: 9.1 },
				{ id: "dev-comp-02", type: "smoke", x_m: 9.0, y_m: 4.0, z_m: 3.2, coverage_radius_m: 6.4, spacing_m: 9.1 },
				{ id: "dev-comp-03", type: "smoke", x_m: 3.0, y_m: 12.0, z_m: 3.2, coverage_radius_m: 6.4, spacing_m: 9.1 },
				{ id: "dev-comp-04", type: "smoke", x_m: 9.0, y_m: 12.0, z_m: 3.2, coverage_radius_m: 6.4, spacing_m: 9.1 },
			];

			const stepResults: WorkflowStepResultPreview[] = [
				{
					nodeId: "step-1-spatial",
					capabilityId: "spatial.place_devices",
					commandId: `cmd-step1-${Date.now()}`,
					success: true,
					resultData: { devices: simulatedDevices, device_count: 4, coverage_pct: 100.0, is_compliant: true },
				},
				{
					nodeId: "step-2-electrical",
					capabilityId: "electrical.calculate_voltage_drop",
					commandId: `cmd-step2-${Date.now()}`,
					success: true,
					resultData: { circuit_id: circ.circuit_id, voltage_drop_v: 0.62, voltage_drop_pct: 2.58, is_compliant: true },
				},
				{
					nodeId: "step-3-battery",
					capabilityId: "electrical.calculate_battery",
					commandId: `cmd-step3-${Date.now()}`,
					success: true,
					resultData: { panel_id: bat.panel_id, required_ah: 28.5, installed_ah: bat.installed_ah ?? 55.0, is_adequate: true },
				},
			];

			const compPreview: CompositeWorkflowPreview = {
				workflowId: `wf-${Date.now()}`,
				correlationId: `corr-comp-${Date.now()}`,
				projectId,
				expectedRevision: currentRevision,
				dag: workflowDag,
				stepResults,
				projectedState: {
					devices: simulatedDevices,
					circuits: { [circ.circuit_id]: stepResults[1].resultData },
					hydraulics: {},
					calculations: { battery: { [bat.panel_id]: stepResults[2].resultData } },
					revision: currentRevision,
				},
				combinedAuditDigest: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
				isCompliant: true,
				tokenTelemetry: {
					measured_tokens: 185,
					budget_limit: 1500,
					utilization_pct: 12.33,
				},
			};

			const preview: DomainCommandPreview = {
				commandId: compPreview.workflowId,
				correlationId: compPreview.correlationId,
				projectId,
				expectedRevision: currentRevision,
				capabilityId: "composite.workflow_execution",
				previewDevices: simulatedDevices,
				compositePreview: compPreview,
				deviceCount: simulatedDevices.length,
				coveragePct: 100.0,
				isCompliant: true,
				tokenTelemetry: compPreview.tokenTelemetry,
				payload: { composite_spec: spec, dag: workflowDag },
			};

			setPreviewDevices(simulatedDevices);
			setProposedCommand(preview);
			setCompositeProposal(compPreview);
			setTokenTelemetry(compPreview.tokenTelemetry ?? null);
			setIsAiActive(true);
			setIsPlanning(false);
			return preview;
		},
		[currentRevision],
	);

	const approveProposal = useCallback(
		async (
			onCommitted?: (
				devices: PreviewDevice[],
				revision: number,
				circuit?: CircuitPreview,
				hydraulic?: HydraulicPreview,
				battery?: BatteryPreview,
			) => void,
		): Promise<boolean> => {
			if (!proposedCommand) return false;

			// Optimistic Concurrency Control (OCC) Check
			if (proposedCommand.expectedRevision !== currentRevision) {
				setConcurrencyError(
					`CONCURRENCY_CONFLICT: AI proposal expected revision ${proposedCommand.expectedRevision}, but project is at revision ${currentRevision}.`,
				);
				return false;
			}

			// Atomic commit & revision increment N -> N+1
			const newRevision = currentRevision + 1;
			setCurrentRevision(newRevision);

			if (onCommitted) {
				onCommitted(
					proposedCommand.previewDevices,
					newRevision,
					proposedCommand.circuitPreview,
					proposedCommand.hydraulicPreview,
					proposedCommand.batteryPreview,
				);
			}

			setProposedCommand(null);
			setCompositeProposal(null);
			setPreviewDevices([]);
			setIsAiActive(false);
			return true;
		},
		[proposedCommand, currentRevision],
	);

	const approveCompositeProposal = useCallback(
		async (
			onCommitted?: (
				projectedState: Record<string, unknown>,
				revision: number,
				stepResults: WorkflowStepResultPreview[],
			) => void,
		): Promise<boolean> => {
			if (!compositeProposal) return false;

			if (compositeProposal.expectedRevision !== currentRevision) {
				setConcurrencyError(
					`CONCURRENCY_CONFLICT: AI proposal expected revision ${compositeProposal.expectedRevision}, but project is at revision ${currentRevision}.`,
				);
				return false;
			}

			const newRevision = currentRevision + 1;
			setCurrentRevision(newRevision);

			if (onCommitted) {
				onCommitted(
					compositeProposal.projectedState,
					newRevision,
					compositeProposal.stepResults,
				);
			}

			setCompositeProposal(null);
			setProposedCommand(null);
			setPreviewDevices([]);
			setIsAiActive(false);
			return true;
		},
		[compositeProposal, currentRevision],
	);

	const rejectProposal = useCallback(() => {
		setPreviewDevices([]);
		setProposedCommand(null);
		setCompositeProposal(null);
		setIsAiActive(false);
		setConcurrencyError(null);
	}, []);

	const simulateUserEdit = useCallback((_projectId: string) => {
		// User manually edits a device in the canvas -> increments canonical revision to N+1
		setCurrentRevision((prev) => prev + 1);
	}, []);

	const replan = useCallback(async () => {
		if (lastIntentParams) {
			setConcurrencyError(null);
			await submitIntent(
				lastIntentParams.projectId,
				lastIntentParams.roomId,
				lastIntentParams.roomBounds,
				lastIntentParams.detectorType,
			);
		}
	}, [lastIntentParams, submitIntent]);

	const value = useMemo(
		() => ({
			isAiActive,
			isPlanning,
			previewDevices,
			proposedCommand,
			compositeProposal,
			concurrencyError,
			currentRevision,
			tokenTelemetry,
			submitIntent,
			submitElectricalIntent,
			submitHydraulicIntent,
			submitBatteryIntent,
			submitCompositeIntent,
			approveProposal,
			approveCompositeProposal,
			rejectProposal,
			replan,
			simulateUserEdit,
		}),
		[
			isAiActive,
			isPlanning,
			previewDevices,
			proposedCommand,
			compositeProposal,
			concurrencyError,
			currentRevision,
			tokenTelemetry,
			submitIntent,
			submitElectricalIntent,
			submitHydraulicIntent,
			submitBatteryIntent,
			submitCompositeIntent,
			approveProposal,
			approveCompositeProposal,
			rejectProposal,
			replan,
			simulateUserEdit,
		],
	);

	return <AIControllerContext.Provider value={value}>{children}</AIControllerContext.Provider>;
};

export const useAIController = (): AIControllerContextValue => {
	const ctx = useContext(AIControllerContext);
	if (!ctx) {
		throw new Error("useAIController must be used within an AIControllerProvider");
	}
	return ctx;
};

