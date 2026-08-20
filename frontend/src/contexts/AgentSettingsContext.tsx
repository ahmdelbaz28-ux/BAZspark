/**
 * AgentSettingsContext — Phase 3 (Workstation Cockpit)
 *
 * Manages AI agent configuration: LLM provider routing, context token budget,
 * governance & safety policies, capability registry toggles, and ephemeral
 * memory lifecycle.
 *
 * SECURITY INVARIANT: API keys are stored in localStorage only. They are never
 * injected into WebSocket domain payloads or sent to the backend.
 */
import type React from "react";
import {
	createContext,
	useCallback,
	useContext,
	useEffect,
	useMemo,
	useState,
} from "react";

// ─── Types ────────────────────────────────────────────────────────────────────

export type LLMProvider = "anthropic" | "gemini" | "openai" | "ollama";

export interface LLMProviderConfig {
	provider: LLMProvider;
	/** Stored locally only — never transmitted to backend */
	apiKeyLocal: string;
	model: string;
	/** Optional custom endpoint / proxy URL */
	baseUrl?: string;
	/** Sampling temperature: 0.00–0.10 for deterministic engineering outputs */
	temperature: number;
}

export type ApprovalRiskLevel =
	| "READ"
	| "REVERSIBLE_VISUAL"
	| "ENGINEERING_MUTATION"
	| "SAFETY_CRITICAL";

export interface GovernancePolicy {
	/** Minimum risk level that requires explicit user approval */
	approvalThreshold: ApprovalRiskLevel;
	/** Auto-rollback if any physics/compliance warning is detected */
	autoRollbackOnPhysicsWarning: boolean;
	/** Require SHA-256 lineage hash to be shown before commit */
	requireLineageBeforeApprove: boolean;
}

export interface CapabilityRegistry {
	"spatial.place_devices": boolean;
	"electrical.calculate_voltage_drop": boolean;
	"electrical.calculate_battery": boolean;
	"hydraulics.solve_darcy_weisbach": boolean;
}

export interface ContextBudgetConfig {
	/** Max tokens per composite context packet (500–4000, default 1500) */
	tokenBudget: number;
	/** Enable CAD/mesh graph pruning before context assembly */
	cadMeshPruning: boolean;
}

export interface WorkingMemoryConfig {
	/** Ephemeral overlay cache TTL in seconds (60–3600) */
	cacheTtlSeconds: number;
}

export interface AgentSettingsState {
	llm: LLMProviderConfig;
	governance: GovernancePolicy;
	capabilities: CapabilityRegistry;
	contextBudget: ContextBudgetConfig;
	workingMemory: WorkingMemoryConfig;
}

export interface AgentSettingsContextValue {
	settings: AgentSettingsState;
	updateLLM: (patch: Partial<LLMProviderConfig>) => void;
	updateGovernance: (patch: Partial<GovernancePolicy>) => void;
	updateCapability: (key: keyof CapabilityRegistry, enabled: boolean) => void;
	updateContextBudget: (patch: Partial<ContextBudgetConfig>) => void;
	updateWorkingMemory: (patch: Partial<WorkingMemoryConfig>) => void;
	resetToDefaults: () => void;
}

// ─── Defaults ─────────────────────────────────────────────────────────────────

const PROVIDER_MODELS: Record<LLMProvider, string> = {
	anthropic: "claude-sonnet-4-5",
	gemini: "gemini-2.0-flash",
	openai: "gpt-4o",
	ollama: "qwen2.5-coder:7b",
};

const PROVIDER_BASE_URLS: Record<LLMProvider, string> = {
	anthropic: "https://api.anthropic.com",
	gemini: "https://generativelanguage.googleapis.com",
	openai: "https://api.openai.com/v1",
	ollama: "http://localhost:11434",
};

const DEFAULT_SETTINGS: AgentSettingsState = {
	llm: {
		provider: "anthropic",
		apiKeyLocal: "",
		model: PROVIDER_MODELS.anthropic,
		baseUrl: PROVIDER_BASE_URLS.anthropic,
		temperature: 0.0,
	},
	governance: {
		approvalThreshold: "REVERSIBLE_VISUAL",
		autoRollbackOnPhysicsWarning: true,
		requireLineageBeforeApprove: false,
	},
	capabilities: {
		"spatial.place_devices": true,
		"electrical.calculate_voltage_drop": true,
		"electrical.calculate_battery": true,
		"hydraulics.solve_darcy_weisbach": true,
	},
	contextBudget: {
		tokenBudget: 1500,
		cadMeshPruning: true,
	},
	workingMemory: {
		cacheTtlSeconds: 300,
	},
};

const STORAGE_KEY = "bazspark:agent-settings:v1";

function loadFromStorage(): AgentSettingsState {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return DEFAULT_SETTINGS;
		const parsed = JSON.parse(raw) as Partial<AgentSettingsState>;
		return {
			llm: { ...DEFAULT_SETTINGS.llm, ...parsed.llm },
			governance: { ...DEFAULT_SETTINGS.governance, ...parsed.governance },
			capabilities: {
				...DEFAULT_SETTINGS.capabilities,
				...parsed.capabilities,
			},
			contextBudget: {
				...DEFAULT_SETTINGS.contextBudget,
				...parsed.contextBudget,
			},
			workingMemory: {
				...DEFAULT_SETTINGS.workingMemory,
				...parsed.workingMemory,
			},
		};
	} catch {
		return DEFAULT_SETTINGS;
	}
}

function saveToStorage(state: AgentSettingsState): void {
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
	} catch {
		// Storage quota exceeded — silent fail
	}
}

// ─── Context ──────────────────────────────────────────────────────────────────

const AgentSettingsContext = createContext<AgentSettingsContextValue | null>(
	null,
);

export const AgentSettingsProvider: React.FC<{ children: React.ReactNode }> = ({
	children,
}) => {
	const [settings, setSettings] = useState<AgentSettingsState>(loadFromStorage);

	// Persist on every change
	useEffect(() => {
		saveToStorage(settings);
	}, [settings]);

	const updateLLM = useCallback((patch: Partial<LLMProviderConfig>) => {
		setSettings((prev) => {
			const next = { ...prev, llm: { ...prev.llm, ...patch } };
			// Auto-update model and baseUrl when provider changes
			if (patch.provider && patch.provider !== prev.llm.provider) {
				if (!patch.model) {
					next.llm.model = PROVIDER_MODELS[patch.provider];
				}
				if (!patch.baseUrl) {
					next.llm.baseUrl = PROVIDER_BASE_URLS[patch.provider];
				}
			}
			return next;
		});
	}, []);

	const updateGovernance = useCallback((patch: Partial<GovernancePolicy>) => {
		setSettings((prev) => ({
			...prev,
			governance: { ...prev.governance, ...patch },
		}));
	}, []);

	const updateCapability = useCallback(
		(key: keyof CapabilityRegistry, enabled: boolean) => {
			setSettings((prev) => ({
				...prev,
				capabilities: { ...prev.capabilities, [key]: enabled },
			}));
		},
		[],
	);

	const updateContextBudget = useCallback(
		(patch: Partial<ContextBudgetConfig>) => {
			setSettings((prev) => ({
				...prev,
				contextBudget: { ...prev.contextBudget, ...patch },
			}));
		},
		[],
	);

	const updateWorkingMemory = useCallback(
		(patch: Partial<WorkingMemoryConfig>) => {
			setSettings((prev) => ({
				...prev,
				workingMemory: { ...prev.workingMemory, ...patch },
			}));
		},
		[],
	);

	const resetToDefaults = useCallback(() => {
		setSettings(DEFAULT_SETTINGS);
	}, []);

	const value = useMemo<AgentSettingsContextValue>(
		() => ({
			settings,
			updateLLM,
			updateGovernance,
			updateCapability,
			updateContextBudget,
			updateWorkingMemory,
			resetToDefaults,
		}),
		[
			settings,
			updateLLM,
			updateGovernance,
			updateCapability,
			updateContextBudget,
			updateWorkingMemory,
			resetToDefaults,
		],
	);

	return (
		<AgentSettingsContext.Provider value={value}>
			{children}
		</AgentSettingsContext.Provider>
	);
};

export function useAgentSettings(): AgentSettingsContextValue {
	const ctx = useContext(AgentSettingsContext);
	if (!ctx) {
		throw new Error(
			"useAgentSettings must be used within <AgentSettingsProvider>",
		);
	}
	return ctx;
}

export interface PingProviderResult {
	success: boolean;
	latencyMs: number;
	error?: string;
}

export async function pingProvider(config: {
	provider: LLMProvider;
	baseUrl?: string;
	apiKey?: string;
	modelName?: string;
}): Promise<PingProviderResult> {
	try {
		const res = await fetch("/api/v1/agent/ping-provider", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				provider: config.provider,
				baseUrl: config.baseUrl,
				apiKey: config.apiKey,
				modelName: config.modelName,
			}),
		});
		if (!res.ok) {
			return {
				success: false,
				latencyMs: 0,
				error: `HTTP ${res.status}: ${res.statusText}`,
			};
		}
		return (await res.json()) as PingProviderResult;
	} catch (err: unknown) {
		const msg = err instanceof Error ? err.message : String(err);
		return {
			success: false,
			latencyMs: 0,
			error: msg,
		};
	}
}

/** Exported for testing — re-hydrate defaults */
export { DEFAULT_SETTINGS, PROVIDER_MODELS, PROVIDER_BASE_URLS };
