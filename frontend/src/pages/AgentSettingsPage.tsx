/**
 * AgentSettingsPage — Phase 3 (Workstation Cockpit)
 *
 * Professional AI Agent Settings Workspace inspired by Anthropic Claude's
 * clean, high-contrast, minimalist aesthetic (slate/zinc palette, structured
 * cards, smooth switches, telemetry meters).
 *
 * Sections:
 *  1. Model Routing         — LLM provider selector + API key (local only)
 *  2. Context Budget        — Token budget slider + CAD/mesh pruning toggle
 *  3. Governance & Safety   — Approval threshold, auto-rollback, lineage gate
 *  4. Capability Registry   — Per-domain enable/disable toggles
 *  5. Working Memory        — Ephemeral cache TTL slider
 */
import {
	AlertCircle,
	Brain,
	ChevronRight,
	Cpu,
	Database,
	Eye,
	EyeOff,
	Flame,
	Key,
	Layers,
	Lock,
	RefreshCcw,
	Shield,
	Sliders,
	Zap,
} from "lucide-react";
import type React from "react";
import { useCallback, useState } from "react";
import {
	type ApprovalRiskLevel,
	type LLMProvider,
	type PingProviderResult,
	pingProvider,
	useAgentSettings,
} from "@/contexts/AgentSettingsContext";

// ─── Primitives ────────────────────────────────────────────────────────────────

const SectionCard: React.FC<{
	icon: React.ReactNode;
	title: string;
	subtitle: string;
	children: React.ReactNode;
}> = ({ icon, title, subtitle, children }) => (
	<section className="bg-card border border-border rounded-xl overflow-hidden">
		<div className="flex items-center gap-3 px-5 py-4 border-b border-border bg-card/50">
			<div className="text-cyan-400 shrink-0">{icon}</div>
			<div>
				<h2 className="text-sm font-semibold text-foreground">{title}</h2>
				<p className="text-xs text-muted-foreground mt-0.5">{subtitle}</p>
			</div>
		</div>
		<div className="p-5 space-y-4">{children}</div>
	</section>
);

const FieldLabel: React.FC<{
	htmlFor?: string;
	label: string;
	hint?: string;
}> = ({ htmlFor, label, hint }) => (
	<div className="flex flex-col gap-0.5 mb-1.5">
		<label
			htmlFor={htmlFor}
			className="text-xs font-medium text-foreground cursor-pointer"
		>
			{label}
		</label>
		{hint && <p className="text-[11px] text-muted-foreground">{hint}</p>}
	</div>
);

const Toggle: React.FC<{
	id: string;
	checked: boolean;
	onChange: (v: boolean) => void;
	label: string;
	hint?: string;
	disabled?: boolean;
}> = ({ id, checked, onChange, label, hint, disabled }) => (
	<div className="flex items-center justify-between gap-4 py-2 border-b border-border/40 last:border-0">
		<div className="flex-1 min-w-0">
			<label
				htmlFor={id}
				className="text-xs font-medium text-foreground cursor-pointer"
			>
				{label}
			</label>
			{hint && <p className="text-[11px] text-muted-foreground mt-0.5">{hint}</p>}
		</div>
		<button
			type="button"
			id={id}
			role="switch"
			aria-checked={checked}
			onClick={() => !disabled && onChange(!checked)}
			disabled={disabled}
			className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-background disabled:opacity-50 disabled:cursor-not-allowed ${
				checked
					? "bg-cyan-500 border-cyan-500"
					: "bg-muted border-muted-foreground/20"
			}`}
		>
			<span
				className={`pointer-events-none inline-block h-3.5 w-3.5 rounded-full bg-white shadow-sm transform transition-transform duration-200 mt-[-1px] ${
					checked ? "translate-x-4" : "translate-x-0"
				}`}
			/>
		</button>
	</div>
);

// ─── Provider selector ────────────────────────────────────────────────────────

const PROVIDERS: Array<{
	id: LLMProvider;
	label: string;
	models: string[];
	badge?: string;
}> = [
	{
		id: "anthropic",
		label: "Anthropic",
		models: [
			"claude-sonnet-4-5",
			"claude-opus-4-5",
			"claude-haiku-3-5",
		],
		badge: "RECOMMENDED",
	},
	{
		id: "gemini",
		label: "Google Gemini",
		models: ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
	},
	{
		id: "openai",
		label: "OpenAI",
		models: ["gpt-4o", "gpt-4o-mini", "o1-preview"],
	},
	{
		id: "ollama",
		label: "Local / Ollama",
		models: ["qwen2.5-coder:7b", "llama3.2", "mistral:7b"],
	},
];

const APPROVAL_LEVELS: Array<{
	id: ApprovalRiskLevel;
	label: string;
	description: string;
}> = [
	{
		id: "READ",
		label: "Read Only",
		description: "All mutations require approval",
	},
	{
		id: "REVERSIBLE_VISUAL",
		label: "Reversible Visual",
		description: "Auto-approve ghost previews only",
	},
	{
		id: "ENGINEERING_MUTATION",
		label: "Engineering Mutation",
		description: "Auto-approve spatial/electrical changes",
	},
	{
		id: "SAFETY_CRITICAL",
		label: "Safety Critical",
		description: "Require manual approval for every change",
	},
];

// ─── Main Page ─────────────────────────────────────────────────────────────────

export function AgentSettingsPage() {
	const {
		settings,
		updateLLM,
		updateGovernance,
		updateCapability,
		updateContextBudget,
		updateWorkingMemory,
		resetToDefaults,
	} = useAgentSettings();

	const [showApiKey, setShowApiKey] = useState(false);
	const [resetConfirm, setResetConfirm] = useState(false);
	const [pingLoading, setPingLoading] = useState(false);
	const [pingResult, setPingResult] = useState<PingProviderResult | null>(null);

	const selectedProvider = PROVIDERS.find(
		(p) => p.id === settings.llm.provider,
	);

	const handleReset = useCallback(() => {
		if (resetConfirm) {
			resetToDefaults();
			setResetConfirm(false);
		} else {
			setResetConfirm(true);
			setTimeout(() => setResetConfirm(false), 3000);
		}
	}, [resetConfirm, resetToDefaults]);

	const handleTestConnection = useCallback(async () => {
		setPingLoading(true);
		setPingResult(null);
		try {
			const res = await pingProvider({
				provider: settings.llm.provider,
				baseUrl: settings.llm.baseUrl,
				apiKey: settings.llm.apiKeyLocal,
				modelName: settings.llm.model,
			});
			setPingResult(res);
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : String(err);
			setPingResult({ success: false, latencyMs: 0, error: msg });
		} finally {
			setPingLoading(false);
		}
	}, [settings.llm]);

	// Token budget utilization meter
	const budgetPct = Math.round(
		((settings.contextBudget.tokenBudget - 500) / (4000 - 500)) * 100,
	);

	return (
		<div
			className="min-h-screen bg-background"
			data-testid="agent-settings-page"
		>
			{/* Page header */}
			<div className="border-b border-border bg-card/50 px-6 py-5">
				<div className="max-w-3xl mx-auto">
					<div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
						<span>Settings</span>
						<ChevronRight className="h-3 w-3" />
						<span className="text-foreground font-medium">AI Agent</span>
					</div>
					<div className="flex items-start justify-between gap-4">
						<div>
							<h1 className="text-lg font-bold text-foreground tracking-tight">
								AI Agent Workspace
							</h1>
							<p className="text-sm text-muted-foreground mt-1">
								Configure the deterministic engineering AI — model routing,
								context budget, governance policies, and capability registry.
							</p>
						</div>
						<button
					type="button"
					id="agent-settings-reset-btn"
					onClick={handleReset}
					aria-label={resetConfirm ? "Confirm Reset" : "Reset Defaults"}
					className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border text-xs font-medium transition-colors shrink-0 cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-offset-background ${
						resetConfirm
							? "bg-red-500/15 border-red-500/40 text-red-400 hover:bg-red-500/25 focus:ring-red-400"
							: "border-border text-muted-foreground hover:text-foreground hover:border-border/80 focus:ring-cyan-500"
					}`}
				>
					<RefreshCcw className="h-3 w-3" aria-hidden="true" />
					{resetConfirm ? "Confirm Reset" : "Reset Defaults"}
				</button>
					</div>
				</div>
			</div>

			{/* Content */}
			<div className="max-w-3xl mx-auto px-6 py-6 space-y-4">
				{/* 1. Model Routing */}
				<SectionCard
					icon={<Brain className="h-4 w-4" />}
					title="Model Routing"
					subtitle="Select the LLM provider and configure API credentials (stored locally only)"
				>
					{/* Provider selector */}
					<div>
						<FieldLabel label="Provider" />
						<div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="LLM Provider">
							{PROVIDERS.map((p) => (
								<button
									type="button"
									key={p.id}
									id={`provider-btn-${p.id}`}
									role="radio"
									aria-checked={settings.llm.provider === p.id}
									onClick={() => updateLLM({ provider: p.id })}
									className={`relative flex flex-col gap-0.5 px-3 py-2.5 rounded-lg border text-left transition-colors cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-1 focus:ring-offset-background ${
										settings.llm.provider === p.id
											? "border-cyan-500/60 bg-cyan-500/10 text-foreground"
											: "border-border bg-muted/30 text-muted-foreground hover:border-border/80 hover:text-foreground"
									}`}
								>
									{p.badge && (
										<span className="absolute top-1.5 right-1.5 text-[9px] font-bold font-mono tracking-wider text-cyan-400">
											{p.badge}
										</span>
									)}
									<span className="text-xs font-semibold">{p.label}</span>
								</button>
							))}
						</div>
					</div>

					{/* Model selector */}
					<div>
						<FieldLabel
							htmlFor="model-select"
							label="Model"
							hint="Model variant for this provider"
						/>
						<select
							id="model-select"
							value={settings.llm.model}
							onChange={(e) => updateLLM({ model: e.target.value })}
							className="w-full px-3 py-2 rounded-md border border-border bg-background text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-cyan-500"
						>
							{selectedProvider?.models.map((m) => (
								<option key={m} value={m}>
									{m}
								</option>
							))}
						</select>
					</div>

					{/* Endpoint Base URL */}
					<div>
						<FieldLabel
							htmlFor="base-url-input"
							label="Endpoint Base URL"
							hint={
								settings.llm.provider === "ollama"
									? "Local Ollama server address (http://localhost:11434)"
									: "Target API or proxy base URL"
							}
						/>
						<input
							id="base-url-input"
							type="text"
							value={settings.llm.baseUrl ?? ""}
							onChange={(e) => updateLLM({ baseUrl: e.target.value })}
							placeholder={
								settings.llm.provider === "ollama"
									? "http://localhost:11434"
									: "https://api.anthropic.com"
							}
							className="w-full px-3 py-2 rounded-md border border-border bg-background text-xs text-foreground font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500 placeholder:text-muted-foreground/50"
							data-testid="base-url-input"
						/>
					</div>

					{/* API Key (local only) */}
					<div>
						<FieldLabel
							htmlFor="api-key-input"
							label="API Key"
							hint="Stored in localStorage only — never transmitted to backend or WebSocket payloads"
						/>
						<div className="flex items-center gap-2">
							<div className="relative flex-1">
								<input
									id="api-key-input"
									type={showApiKey ? "text" : "password"}
									value={settings.llm.apiKeyLocal}
									onChange={(e) => updateLLM({ apiKeyLocal: e.target.value })}
									placeholder={`${settings.llm.provider === "ollama" ? "No key required" : "sk-…"}`}
									className="w-full px-3 py-2 pr-8 rounded-md border border-border bg-background text-xs text-foreground font-mono focus:outline-none focus:ring-2 focus:ring-cyan-500 placeholder:text-muted-foreground/50"
									autoComplete="off"
									data-testid="api-key-input"
								/>
								<button
									type="button"
									onClick={() => setShowApiKey((v) => !v)}
									className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
									aria-label={showApiKey ? "Hide API key" : "Show API key"}
								>
									{showApiKey ? (
										<EyeOff className="h-3 w-3" />
									) : (
										<Eye className="h-3 w-3" />
									)}
								</button>
							</div>
							<div className="flex items-center gap-1 text-[10px] text-muted-foreground">
								<Lock className="h-3 w-3 text-emerald-400" />
								<span>Local</span>
							</div>
						</div>
					</div>

					{/* Temperature */}
					<div>
						<FieldLabel
							htmlFor="temperature-slider"
							label={`Temperature — ${settings.llm.temperature.toFixed(2)}`}
							hint="0.00 = fully deterministic engineering outputs (recommended)"
						/>
						<input
							id="temperature-slider"
							type="range"
							min={0}
							max={0.1}
							step={0.01}
							value={settings.llm.temperature}
							onChange={(e) =>
								updateLLM({ temperature: parseFloat(e.target.value) })
							}
							className="w-full accent-cyan-500"
							data-testid="temperature-slider"
						/>
						<div className="flex justify-between text-[10px] text-muted-foreground mt-1">
							<span>0.00 (deterministic)</span>
							<span>0.10</span>
						</div>
					</div>

					{/* Live Connection Test Button & Ping Status */}
					<div className="pt-2 flex items-center justify-between gap-3 border-t border-border/40">
						<button
							type="button"
							id="test-connection-btn"
							data-testid="test-connection-btn"
							onClick={() => void handleTestConnection()}
							disabled={pingLoading}
							className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-semibold hover:bg-cyan-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer focus:outline-none focus:ring-2 focus:ring-cyan-500"
						>
							{pingLoading ? (
								<RefreshCcw className="h-3.5 w-3.5 animate-spin" />
							) : (
								<Zap className="h-3.5 w-3.5" />
							)}
							<span>{pingLoading ? "Testing..." : "Test Connection"}</span>
						</button>

						{pingResult && (
							<div
								data-testid="ping-status-badge"
								className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border ${
									pingResult.success
										? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
										: "bg-red-500/10 border-red-500/30 text-red-400"
								}`}
							>
								{pingResult.success ? (
									<>
										<Shield className="h-3.5 w-3.5" />
										<span>Connected ({pingResult.latencyMs} ms)</span>
									</>
								) : (
									<>
										<AlertCircle className="h-3.5 w-3.5" />
										<span>{pingResult.error || "Connection Failed"}</span>
									</>
								)}
							</div>
						)}
					</div>
				</SectionCard>

				{/* 2. Context Budget & Telemetry Vault */}
				<SectionCard
					icon={<Sliders className="h-4 w-4" />}
					title="Context Budget & Telemetry Vault"
					subtitle="Control token consumption and enable CAD/mesh graph pruning"
				>
					<div>
						<FieldLabel
							htmlFor="token-budget-slider"
							label={`Token Budget — ${settings.contextBudget.tokenBudget.toLocaleString()} tokens`}
							hint="Maximum tokens per composite context packet (deduplicated)"
						/>
						<input
							id="token-budget-slider"
							type="range"
							min={500}
							max={4000}
							step={100}
							value={settings.contextBudget.tokenBudget}
							onChange={(e) =>
								updateContextBudget({ tokenBudget: parseInt(e.target.value) })
							}
							className="w-full accent-cyan-500"
							data-testid="token-budget-slider"
						/>
						<div className="flex justify-between text-[10px] text-muted-foreground mt-1">
							<span>500</span>
							<span>4,000</span>
						</div>
						{/* Utilization meter */}
						<div className="mt-3 space-y-1">
							<div className="flex items-center justify-between text-[10px] text-muted-foreground">
								<span>Budget Utilization</span>
								<span
									className={`font-mono font-semibold ${budgetPct > 80 ? "text-amber-400" : "text-foreground"}`}
								>
									{budgetPct}%
								</span>
							</div>
							<div className="h-1.5 rounded-full bg-muted overflow-hidden">
								<div
									className={`h-full rounded-full transition-all duration-300 ${
										budgetPct > 80 ? "bg-amber-400" : "bg-cyan-500"
									}`}
									style={{ width: `${budgetPct}%` }}
									role="progressbar"
									aria-valuenow={budgetPct}
									aria-valuemin={0}
									aria-valuemax={100}
									aria-label="Token budget utilization"
								/>
							</div>
						</div>
					</div>

					<Toggle
						id="cad-mesh-pruning-toggle"
						checked={settings.contextBudget.cadMeshPruning}
						onChange={(v) => updateContextBudget({ cadMeshPruning: v })}
						label="CAD/Mesh Graph Pruning"
						hint="Remove non-essential geometry references before context assembly"
					/>
				</SectionCard>

				{/* 3. Governance & Safety */}
				<SectionCard
					icon={<Shield className="h-4 w-4" />}
					title="Governance & Safety Policies"
					subtitle="Define approval thresholds and automatic safeguards"
				>
					<div>
						<FieldLabel label="Approval Threshold" hint="Minimum risk level requiring explicit user approval before commit" />
						<div className="space-y-1" role="radiogroup" aria-label="Approval threshold">
							{APPROVAL_LEVELS.map((level) => (
								<button
									type="button"
									key={level.id}
									id={`approval-level-${level.id}`}
									role="radio"
									aria-checked={settings.governance.approvalThreshold === level.id}
									onClick={() =>
										updateGovernance({ approvalThreshold: level.id })
									}
									className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg border text-left transition-colors ${
										settings.governance.approvalThreshold === level.id
											? "border-cyan-500/50 bg-cyan-500/8 text-foreground"
											: "border-border bg-transparent text-muted-foreground hover:text-foreground hover:border-border/80"
									}`}
								>
									<div
										className={`h-3 w-3 rounded-full border-2 shrink-0 transition-colors ${
											settings.governance.approvalThreshold === level.id
												? "border-cyan-500 bg-cyan-500"
												: "border-muted-foreground/50"
										}`}
									/>
									<div className="flex-1 min-w-0">
										<p className="text-xs font-semibold">{level.label}</p>
										<p className="text-[11px] text-muted-foreground">
											{level.description}
										</p>
									</div>
								</button>
							))}
						</div>
					</div>

					<div className="space-y-0">
						<Toggle
							id="auto-rollback-toggle"
							checked={settings.governance.autoRollbackOnPhysicsWarning}
							onChange={(v) =>
								updateGovernance({ autoRollbackOnPhysicsWarning: v })
							}
							label="Auto-Rollback on Physics Warning"
							hint="Revert commit if any NFPA/IEEE compliance check fails post-commit"
						/>
						<Toggle
							id="lineage-before-approve-toggle"
							checked={settings.governance.requireLineageBeforeApprove}
							onChange={(v) =>
								updateGovernance({ requireLineageBeforeApprove: v })
							}
							label="Require Lineage Before Approve"
							hint="Show SHA-256 Merkle audit hash before enabling the approve button"
						/>
					</div>
				</SectionCard>

				{/* 4. Capability Registry */}
				<SectionCard
					icon={<Cpu className="h-4 w-4" />}
					title="Active Capability Registry"
					subtitle="Enable or disable individual engineering solver domains"
				>
					<div className="space-y-0">
						<Toggle
							id="cap-spatial-toggle"
							checked={settings.capabilities["spatial.place_devices"]}
							onChange={(v) =>
								updateCapability("spatial.place_devices", v)
							}
							label="Spatial — Place Devices"
							hint="NFPA 72 §17 automatic detector placement via UGLD raytrace"
						/>
						<Toggle
							id="cap-voltage-drop-toggle"
							checked={
								settings.capabilities["electrical.calculate_voltage_drop"]
							}
							onChange={(v) =>
								updateCapability("electrical.calculate_voltage_drop", v)
							}
							label="Electrical — Voltage Drop"
							hint="Darcy-Weisbach-inspired AWG voltage drop solver (NFPA 72 §10)"
						/>
						<Toggle
							id="cap-battery-toggle"
							checked={settings.capabilities["electrical.calculate_battery"]}
							onChange={(v) =>
								updateCapability("electrical.calculate_battery", v)
							}
							label="Electrical — Battery Sizing"
							hint="IEEE 485 VRLA/LiFePO4/NiCad thermal derating engine"
						/>
						<Toggle
							id="cap-hydraulics-toggle"
							checked={settings.capabilities["hydraulics.solve_darcy_weisbach"]}
							onChange={(v) =>
								updateCapability("hydraulics.solve_darcy_weisbach", v)
							}
							label="Hydraulics — Darcy-Weisbach Solver"
							hint="NFPA 13 sprinkler pipe flow/pressure loss calculator"
						/>
					</div>

					{/* Registry summary */}
					<div className="flex items-center gap-2 px-3 py-2 rounded-md bg-muted/40 border border-border">
						<Layers className="h-3 w-3 text-muted-foreground shrink-0" />
						<span className="text-[11px] text-muted-foreground">
							{
								Object.values(settings.capabilities).filter(Boolean).length
							}{" "}
							of {Object.keys(settings.capabilities).length} capabilities active
						</span>
					</div>
				</SectionCard>

				{/* 5. Working Memory Lifecycle */}
				<SectionCard
					icon={<Database className="h-4 w-4" />}
					title="Working Memory Lifecycle"
					subtitle="Ephemeral overlay cache time-to-live before automatic eviction"
				>
					<div>
						<FieldLabel
							htmlFor="cache-ttl-slider"
							label={`Cache TTL — ${settings.workingMemory.cacheTtlSeconds}s (${Math.round(settings.workingMemory.cacheTtlSeconds / 60)}m)`}
							hint="Ephemeral ghost overlays auto-evict after this duration"
						/>
						<input
							id="cache-ttl-slider"
							type="range"
							min={60}
							max={3600}
							step={60}
							value={settings.workingMemory.cacheTtlSeconds}
							onChange={(e) =>
								updateWorkingMemory({
									cacheTtlSeconds: parseInt(e.target.value),
								})
							}
							className="w-full accent-cyan-500"
							data-testid="cache-ttl-slider"
						/>
						<div className="flex justify-between text-[10px] text-muted-foreground mt-1">
							<span>60s (1m)</span>
							<span>3600s (1h)</span>
						</div>
					</div>

					<div className="flex items-start gap-2 px-3 py-2.5 rounded-md border border-amber-500/25 bg-amber-500/8">
						<AlertCircle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
						<p className="text-[11px] text-amber-300/80 leading-relaxed">
							Uncommitted proposals (ghost overlays) live{" "}
							<strong>in-memory only</strong>. They are never written to the
							database and are discarded on TTL expiry or manual rejection.
						</p>
					</div>
				</SectionCard>

				{/* Quick action links */}
				<div className="flex items-center gap-3 py-2 text-[11px] text-muted-foreground">
					<Key className="h-3 w-3" />
					<a href="/api-keys" className="hover:text-foreground transition-colors underline underline-offset-2">
						Manage API Keys
					</a>
					<span>·</span>
					<Flame className="h-3 w-3" />
					<a href="/engineering/fireai" className="hover:text-foreground transition-colors underline underline-offset-2">
						FireAI Analysis
					</a>
					<span>·</span>
					<Zap className="h-3 w-3" />
					<a href="/workflow" className="hover:text-foreground transition-colors underline underline-offset-2">
						Workflow Engine
					</a>
				</div>
			</div>
		</div>
	);
}

export default AgentSettingsPage;
