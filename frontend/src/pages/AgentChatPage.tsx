/**
 * AgentChatPage.tsx — AI-First / Chat-First Control Center (Phase 7 Universal Chat Control Plane).
 *
 * Mandated by BAZSPARK_PLAN_V2_2_1 §5 Phase 7:
 * - 100% server-authoritative routing via ControlRequest -> Planner -> Policy -> Approval -> Run.
 * - Zero parallel unmonitored planning/execution paths or local export/import bypasses.
 * - Visual surfaces read exclusively from official run/selection state with audit records.
 * - Server-authoritative Agent Run execution spine (useAgentRun).
 * - Auto Approval policy mode toggle (AUTO vs STEP-BY-STEP).
 * - Multi-step timeline & human review gates (WorkflowActionCard).
 * - Voice input (useVoiceControl).
 * - CAD/BIM file attachment metadata surface.
 * - Produced engineering artifact visualization derived from official selection/run state.
 */
import {
	Bot,
	Loader,
	Mic,
	MicOff,
	Send,
	Sparkles,
	User,
	Zap,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArtifactDisplay, type ProducedArtifact } from "@/components/chat/ArtifactDisplay";
import { AttachmentButton, AttachmentSurface, type AttachedFile } from "@/components/chat/AttachmentSurface";
import { AutoApprovalToggle } from "@/components/chat/AutoApprovalToggle";
import { ExecutionTimeline } from "@/components/chat/ExecutionTimeline";
import { ExportPlanCard } from "@/components/chat/ExportPlanCard";
import { ImportPreviewCard } from "@/components/chat/ImportPreviewCard";
import { ProjectContextBar } from "@/components/chat/ProjectContextBar";
import { RunLifecycleControls } from "@/components/chat/RunLifecycleControls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { WorkflowActionCard } from "@/components/ui/WorkflowActionCard";
import { useActiveProject } from "@/contexts/ProjectContext";
import { useAgentRun } from "@/hooks/useAgentRun";
import { useLlmChat } from "@/hooks/useLlmChat";
import { useVoiceControl } from "@/hooks/useVoiceControl";
import type { ExportPlan, ExportTargetFormat } from "@/services/exportApi";
import { importApi, type ImportPlan, type StagedFileRecord } from "@/services/importApi";
import { agentWorkflowApi } from "@/services/agentWorkflowApi";

interface QuickAction {
	label: string;
	capabilityId: string;
	description: string;
	prompt: string;
	spec?: Record<string, unknown>;
}

const QUICK_ENGINEERING_ACTIONS: QuickAction[] = [
	{
		label: "Place Smoke Detectors",
		capabilityId: "spatial.place_devices",
		description: "Auto-layout NFPA 72 compliant detectors in Zone A",
		prompt: "Auto-layout NFPA 72 compliant smoke detectors in Zone A 15x20m with 3.5m ceiling height and verify SLC voltage drop",
		spec: { room_id: "zone-a", width_m: 15.0, length_m: 20.0, ceiling_height_m: 3.5, detector_type: "smoke" },
	},
	{
		label: "Voltage Drop Analysis",
		capabilityId: "electrical.calculate_voltage_drop",
		description: "Compute end-of-line voltage drop for NAC-01",
		prompt: "Calculate voltage drop on circuit nac-01 with current 2.5A over 60m 12 AWG wire",
		spec: { circuit_id: "nac-01", current_a: 2.5, one_way_length_m: 60.0, awg: "12" },
	},
	{
		label: "Battery Backup Sizing",
		capabilityId: "electrical.calculate_battery",
		description: "Calculate 24h standby + 5m alarm battery Ah capacity",
		prompt: "Size battery backup for panel facp-main with 0.85A standby load and 3.5A alarm load for 24h standby",
		spec: { panel_id: "facp-main", standby_load_amps: 0.85, alarm_load_amps: 3.5, standby_hours: 24.0, alarm_hours: 5.0 / 60.0, installed_ah: 40.0 },
	},
	{
		label: "Hydraulic Darcy-Weisbach",
		capabilityId: "hydraulics.solve_darcy_weisbach",
		description: "Calculate pipe friction loss & flow velocity",
		prompt: "Solve Darcy-Weisbach friction loss for pipe main-riser-01 length 25m diameter 65mm flow 500 l/min",
		spec: { pipe_segment_id: "main-riser-01", length_m: 25.0, diameter_mm: 65.0, flow_l_min: 500.0 },
	},
	{
		label: "Full Multi-Domain Audit",
		capabilityId: "composite.workflow_execution",
		description: "Execute end-to-end NFPA 72 + IEEE engineering audit",
		prompt: "Execute full multi-domain audit in atrium: place detectors 25x30m, calculate voltage drop on nac-atrium 3.0A 80m, and size battery for facp-atrium",
		spec: { room_id: "atrium", width_m: 25.0, length_m: 30.0, ceiling_height_m: 8.0, detector_type: "smoke" },
	},
	{
		label: "Export DXF / BIM Deliverable",
		capabilityId: "export.execute_export",
		description: "Export project canonical devices & circuits to DXF CAD",
		prompt: "Plan and generate signed DXF CAD export deliverable",
		spec: { target_format: "dxf" },
	},
];

interface AgentChatPageProps {
	projectId?: string;
}

export function AgentChatPage({ projectId: propProjectId }: AgentChatPageProps = {}) {
	const { i18n } = useTranslation();
	const isArabic = Boolean(i18n.language?.startsWith("ar"));
	const { activeProjectId, activeRevision, activeModelId } = useActiveProject();
	const effectiveProjectId = propProjectId || activeProjectId;

	// Conversational LLM chat hook
	const { messages, loading: llmLoading, error: llmError, sendMessage, clearChat } =
		useLlmChat("engineer_assistant");

	// Authoritative Agent Run lifecycle hook
	const {
		state: runState,
		startRun,
		pauseRun,
		resumeRun,
		cancelRun,
		retryRun,
		approveStep,
		rejectStep,
		setApprovalMode,
		clearRun,
	} = useAgentRun(effectiveProjectId);

	const [inputValue, setInputValue] = useState("");
	const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
	const [stagedImport, setStagedImport] = useState<{
		stagedFile: StagedFileRecord;
		plan: ImportPlan | null;
		isExecuting: boolean;
	} | null>(null);
	const [stagedExport, setStagedExport] = useState<{
		plan: ExportPlan;
		isExecuting: boolean;
	} | null>(null);
	const scrollAreaRef = useRef<HTMLDivElement>(null);

	// Voice control integration
	const handleSpeechTranscript = useCallback((spokenText: string) => {
		setInputValue((prev) => {
			const cleaned = spokenText.trim();
			return prev ? `${prev} ${cleaned}` : cleaned;
		});
	}, []);

	const {
		isListening,
		startListening,
		stopListening,
		interimTranscript,
		isSupported: voiceSupported,
	} = useVoiceControl({
		onTranscript: handleSpeechTranscript,
	});

	const toggleListening = useCallback(() => {
		if (isListening) {
			stopListening();
		} else {
			startListening();
		}
	}, [isListening, startListening, stopListening]);

	// Auto-scroll on new messages or step transitions
	useEffect(() => {
		if (scrollAreaRef.current) {
			scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
		}
	}, [messages, runState.status, runState.currentStep]);

	// File attachment handlers with Phase 3 Import auto-staging
	const handleAddFiles = useCallback(
		async (newFiles: File[]) => {
			const formatted: AttachedFile[] = newFiles.map((f) => ({
				id: `att-${Date.now()}-${typeof window !== "undefined" && window.crypto?.randomUUID ? window.crypto.randomUUID().slice(0, 8) : "file"}`,
				file: f,
				name: f.name,
				sizeBytes: f.size,
				extension: `.${f.name.split(".").pop()?.toLowerCase()}`,
				status: "ready",
			}));
			setAttachedFiles((prev) => [...prev, ...formatted]);

			if (newFiles.length > 0) {
				const targetFile = newFiles[0];
				try {
					const staged = await importApi.uploadDrawingFile(targetFile);
					const plan = await importApi.planImport(staged.file_id, runState.projectId || effectiveProjectId);
					setStagedImport({ stagedFile: staged, plan, isExecuting: false });
				} catch (err) {
					console.warn("Auto-staging file for import preview failed:", err);
				}
			}
		},
		[runState.projectId, effectiveProjectId],
	);

	const handleRemoveFile = useCallback((id: string) => {
		setAttachedFiles((prev) => prev.filter((f) => f.id !== id));
		setStagedImport(null);
	}, []);

	// S1: Governed Import Initiation via ControlRequest pipeline (zero direct execute bypass)
	const handleStartImportRun = useCallback(
		async (staged: StagedFileRecord, mode: "AUTO" | "STEP_BY_STEP") => {
			setStagedImport((prev) => (prev ? { ...prev, isExecuting: true } : null));
			try {
				const plan = await agentWorkflowApi.planWorkflow({
					prompt: `Import and integrate ${staged.detected_format.toUpperCase()} drawing ${staged.sanitized_filename}`,
					projectId: runState.projectId || effectiveProjectId,
					modelId: activeModelId || undefined,
					expectedRevision: activeRevision !== undefined ? activeRevision : undefined,
					approvalMode: mode,
					compositeSpec: { file_id: staged.file_id, filename: staged.sanitized_filename },
				});

				if (plan.steps && plan.steps.length > 0) {
					await startRun({
						projectId: runState.projectId || effectiveProjectId,
						modelId: activeModelId || undefined,
						expectedRevision: activeRevision !== undefined ? activeRevision : undefined,
						steps: plan.steps.map((s) => ({
							step_id: s.step_id,
							capability_id: s.capability_id,
							description: s.description,
							payload: s.payload,
						})),
						approvalMode: mode,
						plan: {
							plan_id: plan.plan_id,
							intent_summary: plan.intent_summary,
							dag: plan.dag,
						},
					});

					await sendMessage(
						`⚡ Staged Drawing Ingestion Workflow Initiated for ${staged.sanitized_filename} (${plan.steps.length} steps). Policy: ${plan.overall_policy_decision}.`,
					);
				}
			} catch (err) {
				console.warn("Import run initiation failed:", err);
			} finally {
				setStagedImport(null);
			}
		},
		[startRun, runState.projectId, effectiveProjectId, activeModelId, activeRevision, sendMessage],
	);

	// S1: Governed Export Planning and Execution via ControlRequest pipeline (zero direct execute bypass)
	const handlePlanExport = useCallback(
		async (targetFormat: ExportTargetFormat) => {
			try {
				const plan = await agentWorkflowApi.planWorkflow({
					prompt: `Plan and export engineering deliverable in ${targetFormat.toUpperCase()} format`,
					projectId: runState.projectId || effectiveProjectId,
					modelId: activeModelId || undefined,
					expectedRevision: activeRevision !== undefined ? activeRevision : undefined,
					approvalMode: runState.approvalMode,
					compositeSpec: { target_format: targetFormat },
				});

				const exportPlanObj: ExportPlan = {
					plan_id: plan.plan_id,
					project_id: runState.projectId || effectiveProjectId,
					expected_revision: plan.expected_revision,
					target_format: targetFormat,
					estimated_devices: (plan.projected_state?.devices as unknown[])?.length || 0,
					estimated_connections: 0,
					estimated_rooms: 1,
					mapping_status: "LOSSLESS",
					mapping_report: {
						target_format: targetFormat,
						entity_counts: { devices: (plan.projected_state?.devices as unknown[])?.length || 0 },
						unmapped_properties: [],
						warnings: [],
						is_lossless: true,
					},
					required_policy: plan.requires_human_approval ? "MANDATORY_HUMAN_REVIEW" : "AUTO_APPROVED",
					created_at: new Date().toISOString(),
				};
				setStagedExport({ plan: exportPlanObj, isExecuting: false });
			} catch (err: unknown) {
				console.error("Export planning failed", err);
			}
		},
		[runState.projectId, runState.approvalMode, effectiveProjectId, activeModelId, activeRevision],
	);

	const handleStartExportRun = useCallback(async () => {
		if (!stagedExport) return;
		const fmt = stagedExport.plan.target_format;
		const expectedRev = stagedExport.plan.expected_revision;
		setStagedExport(null);
		try {
			const plan = await agentWorkflowApi.planWorkflow({
				prompt: `Export deliverable as ${fmt.toUpperCase()} format with OCC check`,
				projectId: runState.projectId || effectiveProjectId,
				modelId: activeModelId || undefined,
				expectedRevision: expectedRev,
				approvalMode: runState.approvalMode,
				compositeSpec: { target_format: fmt },
			});

			if (plan.steps && plan.steps.length > 0) {
				await startRun({
					projectId: runState.projectId || effectiveProjectId,
					modelId: activeModelId || undefined,
					expectedRevision: expectedRev,
					steps: plan.steps.map((s) => ({
						step_id: s.step_id,
						capability_id: s.capability_id,
						description: s.description,
						payload: s.payload,
					})),
					approvalMode: runState.approvalMode,
					plan: {
						plan_id: plan.plan_id,
						intent_summary: plan.intent_summary,
						dag: plan.dag,
					},
				});

				await sendMessage(
					`⚡ Export Deliverable Workflow Initiated: ${fmt.toUpperCase()} format (${plan.steps.length} steps). Policy: ${plan.overall_policy_decision}.`,
				);
			}
		} catch (err) {
			console.warn("Export run start failed:", err);
		}
	}, [stagedExport, startRun, runState.projectId, runState.approvalMode, effectiveProjectId, activeModelId, sendMessage]);

	// S1: Execute a quick engineering action via server-authoritative ControlRequest pipeline
	const handleQuickAction = useCallback(
		async (action: QuickAction) => {
			try {
				const plan = await agentWorkflowApi.planWorkflow({
					prompt: action.prompt,
					projectId: runState.projectId || effectiveProjectId,
					modelId: activeModelId || undefined,
					expectedRevision: activeRevision !== undefined ? activeRevision : undefined,
					approvalMode: runState.approvalMode,
					compositeSpec: action.spec,
				});

				if (plan.steps && plan.steps.length > 0) {
					await startRun({
						projectId: runState.projectId || effectiveProjectId,
						modelId: activeModelId || undefined,
						expectedRevision: activeRevision !== undefined ? activeRevision : undefined,
						steps: plan.steps.map((s) => ({
							step_id: s.step_id,
							capability_id: s.capability_id,
							description: s.description,
							payload: s.payload,
						})),
						approvalMode: runState.approvalMode,
						plan: {
							plan_id: plan.plan_id,
							intent_summary: plan.intent_summary,
							dag: plan.dag,
						},
					});

					await sendMessage(
						`⚡ Autonomous Engineering Workflow Initiated: ${plan.intent_summary} (${plan.steps.length} steps). Policy: ${plan.overall_policy_decision}. Requires Approval: ${plan.requires_human_approval ? "YES" : "NO"}.`,
					);
				}
			} catch (err) {
				console.warn("Quick action planning failed, falling back to conversational prompt:", err);
				await sendMessage(action.prompt);
			}
		},
		[startRun, runState.projectId, runState.approvalMode, effectiveProjectId, activeModelId, activeRevision, sendMessage],
	);

	// S1: Unified submit handler — 100% ControlRequest pipeline
	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		const prompt = inputValue.trim();
		if (!prompt || llmLoading || runState.isActionPending) return;

		setInputValue("");

		// Route through real backend workflow planner (ControlRequest pipeline)
		try {
			const plan = await agentWorkflowApi.planWorkflow({
				prompt,
				projectId: runState.projectId || effectiveProjectId,
				modelId: activeModelId || undefined,
				expectedRevision: activeRevision !== undefined ? activeRevision : undefined,
				approvalMode: runState.approvalMode,
				compositeSpec: attachedFiles.length > 0 ? { file_id: attachedFiles[0].id, filename: attachedFiles[0].name } : undefined,
			});

			if (plan.steps && plan.steps.length > 0) {
				await startRun({
					projectId: runState.projectId || effectiveProjectId,
					modelId: activeModelId || undefined,
					expectedRevision: activeRevision !== undefined ? activeRevision : undefined,
					steps: plan.steps.map((s) => ({
						step_id: s.step_id,
						capability_id: s.capability_id,
						description: s.description,
						payload: s.payload,
					})),
					approvalMode: runState.approvalMode,
					plan: {
						plan_id: plan.plan_id,
						intent_summary: plan.intent_summary,
						dag: plan.dag,
					},
				});

				await sendMessage(
					`⚡ Autonomous Engineering Workflow Initiated: ${plan.intent_summary} (${plan.steps.length} steps). Execution Policy: ${plan.overall_policy_decision}. Requires Approval: ${plan.requires_human_approval ? "YES" : "NO"}.`,
				);
				return;
			}
		} catch (err) {
			console.warn("Autonomous planner fallback to conversational LLM stream:", err);
		}

		// Conversational stream for advisory/code Q&A
		await sendMessage(prompt);
	};

	// S2: Connect visual surfaces to official run selection and step results (zero local parallel artifact state)
	const producedArtifacts: ProducedArtifact[] = useMemo(() => {
		const list: ProducedArtifact[] = [];
		if (!runState.steps) return list;

		for (const step of runState.steps) {
			if (step.status === "completed" && step.result_data) {
				const resData = step.result_data;
				// 1. Single artifact record
				if (resData.artifact && typeof resData.artifact === "object") {
					const art = resData.artifact as Record<string, unknown>;
					list.push({
						artifact_id: String(art.artifact_id || `art-${step.step_id}`),
						filename: String(art.filename || `deliverable.${String(art.target_format || "dxf").toLowerCase()}`),
						format: String(art.target_format || art.format || "DXF").toUpperCase(),
						size_bytes: typeof art.file_size_bytes === "number" ? art.file_size_bytes : typeof art.size_bytes === "number" ? art.size_bytes : undefined,
						status: "ready",
						download_url: typeof art.download_url === "string" ? art.download_url : `/api/v1/exports/download/${art.artifact_id || step.step_id}`,
						created_at: typeof art.created_at === "string" ? art.created_at : undefined,
					});
				}
				// 2. Artifact list
				if (Array.isArray(resData.artifacts)) {
					for (const artItem of resData.artifacts) {
						if (artItem && typeof artItem === "object") {
							const art = artItem as Record<string, unknown>;
							list.push({
								artifact_id: String(art.artifact_id || `art-${step.step_id}-${list.length}`),
								filename: String(art.filename || `deliverable.${String(art.target_format || "dxf").toLowerCase()}`),
								format: String(art.target_format || art.format || "DXF").toUpperCase(),
								size_bytes: typeof art.file_size_bytes === "number" ? art.file_size_bytes : typeof art.size_bytes === "number" ? art.size_bytes : undefined,
								status: "ready",
								download_url: typeof art.download_url === "string" ? art.download_url : `/api/v1/exports/download/${art.artifact_id || step.step_id}`,
								created_at: typeof art.created_at === "string" ? art.created_at : undefined,
							});
						}
					}
				}
				// 3. Export deliverable capability direct output
				if (step.capability_id === "export.execute_export" && resData.filename) {
					const exists = list.some((a) => a.filename === resData.filename);
					if (!exists) {
						list.push({
							artifact_id: String(resData.artifact_id || `art-${step.step_id}`),
							filename: String(resData.filename),
							format: String(resData.target_format || "DXF").toUpperCase(),
							size_bytes: typeof resData.file_size_bytes === "number" ? resData.file_size_bytes : undefined,
							status: "ready",
							download_url: typeof resData.download_url === "string" ? resData.download_url : `/api/v1/exports/download/${resData.artifact_id || step.step_id}`,
						});
					}
				}
			}
		}
		return list;
	}, [runState.steps]);

	return (
		<div className="h-full flex flex-col bg-background text-foreground overflow-hidden">
			{/* 1. Project & Model Context Header */}
			<ProjectContextBar
				projectId={effectiveProjectId || runState.projectId}
				projectRevision={runState.status ? runState.version : activeRevision}
				isConnected={runState.isConnected}
				isReconnecting={runState.isReconnecting}
				onClearChat={clearChat}
				onNewRun={clearRun}
			/>

			{/* 2. Main Scrollable Chat & Execution Timeline Canvas */}
			<ScrollArea className="flex-1 p-4 md:p-6" ref={scrollAreaRef}>
				<div className="max-w-4xl mx-auto space-y-6 pb-4">
					{/* Welcome Hero when no messages or active runs */}
					{messages.length === 0 && !runState.status && (
						<div className="text-center py-12 px-4 rounded-3xl border border-border/40 bg-gradient-to-b from-card/80 to-background shadow-xl">
							<div className="w-14 h-14 rounded-2xl bg-secondary/15 border border-secondary/30 flex items-center justify-center mx-auto mb-4 shadow-sm">
								<Sparkles className="h-7 w-7 text-secondary" />
							</div>
							<h2 className="text-xl font-bold text-foreground mb-2">
								{isArabic ? "مركز التحكم الذكي FireAI" : "FireAI Engineering Control Center"}
							</h2>
							<p className="text-sm text-muted-foreground max-w-lg mx-auto leading-relaxed">
								{isArabic
									? "تفاعل مباشرة مع المساعد الذكي لتنفيذ الحسابات الهندسية، التحقق من الامتثال لـ NFPA 72، وتوليد المخططات الهندسية بدقة عالية."
									: "Interact directly with FireAI to execute deterministic calculations, verify NFPA 72 compliance, and review automated engineering proposals."}
							</p>

							{/* Quick Action Cards Grid */}
							<div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 mt-8 text-left">
								{QUICK_ENGINEERING_ACTIONS.slice(0, 3).map((act) => (
									<button
										key={act.label}
										type="button"
										onClick={() => void handleQuickAction(act)}
										className="p-3.5 rounded-2xl border border-border bg-card/60 hover:bg-secondary/10 hover:border-secondary/50 transition-all text-left group"
									>
										<div className="flex items-center justify-between mb-1.5">
											<span className="text-xs font-semibold text-foreground group-hover:text-secondary transition-colors">
												{act.label}
											</span>
											<Zap className="h-3.5 w-3.5 text-secondary/60 group-hover:text-secondary transition-colors" />
										</div>
										<p className="text-[11px] text-muted-foreground line-clamp-2">
											{act.description}
										</p>
									</button>
								))}
							</div>
						</div>
					)}

					{/* Staged Import Inspection / Plan Preview */}
					{stagedImport && (
						<ImportPreviewCard
							stagedFile={stagedImport.stagedFile}
							plan={stagedImport.plan}
							isExecuting={stagedImport.isExecuting}
							onStartAgentRun={handleStartImportRun}
							onDirectExecute={(staged) => void handleStartImportRun(staged, "AUTO")}
							onDismiss={() => setStagedImport(null)}
						/>
					)}

					{/* Staged Export Planning / Loss Preview Card (Phase 4 & 7) */}
					{stagedExport && (
						<ExportPlanCard
							plan={stagedExport.plan}
							isExecuting={stagedExport.isExecuting}
							onFormatChange={(fmt) => void handlePlanExport(fmt)}
							onStartAgentRun={() => void handleStartExportRun()}
							onDirectExecute={() => void handleStartExportRun()}
							onDismiss={() => setStagedExport(null)}
						/>
					)}

					{/* Active Execution Spine / Step Timeline */}
					{runState.status && (
						<div className="space-y-3">
							<ExecutionTimeline
								status={runState.status}
								currentStep={runState.currentStep}
								completedSteps={runState.completedSteps}
								failedSteps={runState.failedSteps}
								steps={runState.steps}
								elapsedSeconds={runState.elapsedSeconds}
								runId={runState.runId}
							/>

							{/* Human Review Approval Card (When WAITING_APPROVAL) */}
							{runState.status === "WAITING_APPROVAL" && (
								<WorkflowActionCard
									lifecycleState="APPROVE"
									pendingApproval={runState.pendingApproval}
									expectedRevision={runState.version}
									isLoading={runState.isActionPending}
									onApprove={approveStep}
									onReject={rejectStep}
								/>
							)}

							{/* Lifecycle Action Bar */}
							<RunLifecycleControls
								status={runState.status}
								isActionPending={runState.isActionPending}
								onPause={pauseRun}
								onResume={resumeRun}
								onCancel={cancelRun}
								onRetry={retryRun}
								onClear={clearRun}
							/>

							{/* Produced Artifacts Display (Derived strictly from official selection & run state) */}
							{producedArtifacts.length > 0 && (
								<ArtifactDisplay artifacts={producedArtifacts} />
							)}
						</div>
					)}

					{/* Conversational Message Stream */}
					{messages.map((message, index) => {
						const isUser = message.role === "user";
						return (
							<div
								key={`${message.timestamp}-${index}`}
								className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}
							>
								{!isUser && (
									<div className="w-8 h-8 rounded-xl bg-secondary/15 border border-secondary/30 flex items-center justify-center shrink-0">
										<Bot className="h-4 w-4 text-secondary" />
									</div>
								)}

								<div className={`max-w-2xl ${isUser ? "items-end" : "items-start"}`}>
									<div
										className={`p-4 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap shadow-sm ${
											isUser
												? "bg-secondary text-secondary-foreground rounded-br-none font-medium"
												: "bg-card border border-border text-foreground rounded-bl-none"
										}`}
									>
										{message.content}
										{message.isStreaming && (
											<span className="inline-block w-2 h-4 ml-1 bg-secondary animate-pulse align-middle" />
										)}
									</div>

									{/* Assistant Metadata Badges */}
									{!isUser && (message.source || message.model) && (
										<div className="flex gap-2 mt-2 flex-wrap items-center">
											{message.model && (
												<Badge
													variant="outline"
													className="text-[10px] text-muted-foreground bg-muted/30 border-border"
												>
													{message.model}
												</Badge>
											)}
											{message.disclaimer && (
												<span className="text-[10px] text-muted-foreground">
													{message.disclaimer}
												</span>
											)}
										</div>
									)}
								</div>

								{isUser && (
									<div className="w-8 h-8 rounded-xl bg-muted border border-border flex items-center justify-center shrink-0">
										<User className="h-4 w-4 text-foreground" />
									</div>
								)}
							</div>
						);
					})}

					{/* Loading indicator */}
					{llmLoading && (
						<div className="flex gap-3 justify-start">
							<div className="w-8 h-8 rounded-xl bg-secondary/15 border border-secondary/30 flex items-center justify-center shrink-0">
								<Loader className="h-4 w-4 text-secondary animate-spin" />
							</div>
							<div className="bg-card border border-border text-foreground p-4 rounded-2xl rounded-bl-none text-sm">
								Thinking & assembling engineering context…
							</div>
						</div>
					)}

					{/* Error banner */}
					{(llmError || runState.error) && (
						<div className="p-3 rounded-xl bg-destructive/10 border border-destructive/30 text-destructive text-xs">
							{llmError || runState.error}
						</div>
					)}
				</div>
			</ScrollArea>

			{/* 3. Quick Action Chips */}
			<div className="px-6 py-2 border-t border-border/40 bg-card/40 backdrop-blur-sm flex items-center gap-2 overflow-x-auto">
				<span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground shrink-0">
					Quick Runs:
				</span>
				{QUICK_ENGINEERING_ACTIONS.map((act) => (
					<button
						key={act.label}
						type="button"
						onClick={() => void handleQuickAction(act)}
						className="px-2.5 py-1 rounded-full text-xs border border-border/80 bg-card hover:border-secondary/50 hover:text-secondary text-muted-foreground transition-all shrink-0 font-medium"
					>
						{act.label}
					</button>
				))}
			</div>

			{/* 4. Input & Control Bar */}
			<div className="p-4 border-t border-border bg-card/90 backdrop-blur-md">
				{/* Live Speech Recognition Banner */}
				{isListening && (
					<div className="max-w-4xl mx-auto mb-2 px-3 py-1.5 rounded-xl bg-secondary/10 border border-secondary/30 text-xs text-secondary flex items-center gap-2 animate-pulse">
						<Mic className="h-3.5 w-3.5 animate-bounce shrink-0" />
						<span className="truncate">
							{interimTranscript || (isArabic ? "جاري الاستماع... تحدث الآن" : "Listening... Speak your command...")}
						</span>
					</div>
				)}

				{/* Attached Files List */}
				<div className="max-w-4xl mx-auto">
					<AttachmentSurface
						files={attachedFiles}
						onAddFiles={handleAddFiles}
						onRemoveFile={handleRemoveFile}
						disabled={llmLoading || runState.isActionPending}
					/>
				</div>

				{/* Input Form with AutoApprovalToggle & Mic */}
				<form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
					<div className="flex items-center gap-2 bg-muted/40 border border-border/80 rounded-2xl p-1.5 shadow-inner focus-within:border-secondary/60 focus-within:ring-2 focus-within:ring-secondary/20 transition-all">
						{/* File Attachment Button */}
						<AttachmentButton
							onClick={() => {
								const input = document.querySelector<HTMLInputElement>(
									'[data-testid="file-attachment-input"]',
								);
								input?.click();
							}}
							disabled={llmLoading || runState.isActionPending}
						/>

						{/* Text Input */}
						<Input
							value={inputValue}
							onChange={(e) => setInputValue(e.target.value)}
							placeholder={
								isArabic
									? "اطلب تحليلاً هندسياً، حساب حمل، أو فحص امتثال..."
									: "Ask an engineering question, run voltage drop, or place detectors..."
							}
							disabled={llmLoading || runState.isActionPending}
							className="flex-1 bg-transparent border-0 shadow-none focus-visible:ring-0 text-sm h-10 px-2"
						/>

						{/* Auto Approval Mode Switcher (AUTO vs STEP-BY-STEP) */}
						<AutoApprovalToggle
							mode={runState.approvalMode}
							onChange={setApprovalMode}
							disabled={llmLoading || runState.isActionPending}
						/>

						{/* Voice Recognition Button */}
						{voiceSupported && (
							<button
								type="button"
								onClick={toggleListening}
								title={isListening ? "Stop listening" : "Start voice control"}
								aria-label={isListening ? "Stop voice control" : "Start voice control"}
								className={`h-9 w-9 rounded-full flex items-center justify-center transition-all ${
									isListening
										? "bg-secondary text-secondary-foreground animate-pulse shadow-md"
										: "text-muted-foreground hover:text-foreground hover:bg-muted"
								}`}
							>
								{isListening ? (
									<MicOff className="h-4 w-4" />
								) : (
									<Mic className="h-4 w-4" />
								)}
							</button>
						)}

						{/* Send / Execute Button */}
						<Button
							type="submit"
							size="icon"
							disabled={!inputValue.trim() || llmLoading || runState.isActionPending}
							className="h-9 w-9 rounded-xl bg-secondary hover:bg-secondary/90 text-secondary-foreground shadow-sm transition-all"
						>
							<Send className="h-4 w-4" />
						</Button>
					</div>
				</form>
			</div>
		</div>
	);
}

export default AgentChatPage;
