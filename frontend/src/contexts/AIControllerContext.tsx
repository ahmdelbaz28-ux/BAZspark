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

export interface DomainCommandPreview {
	commandId: string;
	correlationId: string;
	projectId: string;
	expectedRevision: number;
	capabilityId: string;
	previewDevices: PreviewDevice[];
	circuitPreview?: CircuitPreview;
	hydraulicPreview?: HydraulicPreview;
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
	approveProposal: (
		onCommitted?: (
			devices: PreviewDevice[],
			revision: number,
			circuit?: CircuitPreview,
			hydraulic?: HydraulicPreview,
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

	const approveProposal = useCallback(
		async (
			onCommitted?: (
				devices: PreviewDevice[],
				revision: number,
				circuit?: CircuitPreview,
				hydraulic?: HydraulicPreview,
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
				);
			}

			setProposedCommand(null);
			setPreviewDevices([]);
			setIsAiActive(false);
			return true;
		},
		[proposedCommand, currentRevision],
	);

	const rejectProposal = useCallback(() => {
		setPreviewDevices([]);
		setProposedCommand(null);
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
			concurrencyError,
			currentRevision,
			tokenTelemetry,
			submitIntent,
			submitElectricalIntent,
			submitHydraulicIntent,
			approveProposal,
			rejectProposal,
			replan,
			simulateUserEdit,
		}),
		[
			isAiActive,
			isPlanning,
			previewDevices,
			proposedCommand,
			concurrencyError,
			currentRevision,
			tokenTelemetry,
			submitIntent,
			submitElectricalIntent,
			submitHydraulicIntent,
			approveProposal,
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

