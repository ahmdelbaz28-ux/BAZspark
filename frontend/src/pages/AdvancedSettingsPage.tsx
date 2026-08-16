/**
 * AdvancedSettingsPage.tsx — Environment Configuration Manager.
 *
 * Provides editable UI forms for 15+ env-var-only settings grouped by category:
 * NVIDIA, Langfuse, Akamai, Database, Pipeline, Integrations, CORS.
 *
 * Settings are fetched from GET /api/v1/env-config and saved via PUT /api/v1/env-config.
 * Secret values are masked in the UI and never shown in plaintext.
 */

import {
	Activity,
	AlertTriangle,
	CheckCircle2,
	Database,
	Eye,
	EyeOff,
	Flag,
	KeyRound,
	Loader2,
	RefreshCw,
	Save,
	Settings2,
	Shield,
	Trash2,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useState } from "react";
import { adminApi, adminConfigApi } from "../services/fullApi";

// ── Types ───────────────────────────────────────────────────────────────────

interface EnvSetting {
	key: string;
	label: string;
	type: "string" | "secret" | "boolean" | "number" | "url";
	value: string;
	is_set: boolean;
	is_secret: boolean;
	source: "env" | "default" | "override";
}

interface ConfigCategory {
	label: string;
	settings: EnvSetting[];
}

interface EnvConfigData {
	categories: Record<string, ConfigCategory>;
}

// ── Category Icons ──────────────────────────────────────────────────────────

const CATEGORY_META: Record<string, { icon: string; description: string }> = {
	nvidia: {
		icon: "🧠",
		description: "NVIDIA LLM API configuration for AI-powered engineering",
	},
	langfuse: {
		icon: "🔍",
		description: "Langfuse observability and LLM tracing settings",
	},
	akamai: {
		icon: "🛡️",
		description: "Akamai CDN, edge security, and geoblocking",
	},
	database: {
		icon: "🗄️",
		description: "PostgreSQL, Qdrant, Neo4j, and Redis connections",
	},
	pipeline: {
		icon: "⚙️",
		description: "Backend pipeline performance and processing parameters",
	},
	integrations: {
		icon: "🔗",
		description: "Third-party API keys: Resend, Supabase, GitHub, HF",
	},
	cors: {
		icon: "🌐",
		description: "Cross-Origin Resource Sharing and allowed origins",
	},
	acoustic: {
		icon: "🔊",
		description: "NFPA 72 Acoustic noise, decibel drop, and strobe synchronization",
	},
	hydraulic: {
		icon: "💧",
		description: "Hydraulic & Darcy-Weisbach / Hazen-Williams fluid properties and roughness",
	},
	battery: {
		icon: "🔋",
		description: "Secondary power supply, ambient temperature profile, and battery aging derating",
	},
	cad: {
		icon: "📐",
		description: "AutoCAD and Revit connection paths, versions, units, and bridge ports",
	},
	_cache: {
		icon: "💾",
		description: "In-memory cache management — view stats, clear entries",
	},
	_feature_flags: {
		icon: "🚩",
		description: "Toggle feature flags on/off in real-time",
	},
	_secret_rotation: {
		icon: "🔐",
		description: "Hot-rotate security secrets and admin tokens",
	},
	_db_health: {
		icon: "🏥",
		description: "Live health status of all database backends",
	},
};

// ── Component ───────────────────────────────────────────────────────────────

export const AdvancedSettingsPage: React.FC = () => {
	const [configData, setConfigData] = useState<EnvConfigData | null>(null);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [saveStatus, setSaveStatus] = useState<
		Record<string, "saving" | "saved" | "error">
	>({});
	const [activeCategory, setActiveCategory] = useState<string>("nvidia");
	const [visibleSecrets, setVisibleSecrets] = useState<Set<string>>(new Set());
	const [editedValues, setEditedValues] = useState<Record<string, string>>({});

	// ── Admin section states ──
	const [cacheStats, setCacheStats] = useState<{
		entries: number;
		max_entries: number;
		memory_usage_mb: number;
		hit_rate: number;
	} | null>(null);
	const [cacheLoading, setCacheLoading] = useState(false);
	const [cacheClearing, setCacheClearing] = useState(false);
	const [featureFlags, setFeatureFlags] = useState<Record<
		string,
		boolean
	> | null>(null);
	const [flagsLoading, setFlagsLoading] = useState(false);
	const [flagToggling, setFlagToggling] = useState<string | null>(null);
	const [dbHealth, setDbHealth] = useState<Record<
		string,
		{ status: string; latency_ms: number; details?: string }
	> | null>(null);
	const [dbHealthLoading, setDbHealthLoading] = useState(false);
	const [secretName, setSecretName] = useState("");
	const [secretValue, setSecretValue] = useState("");
	const [secretGrace, setSecretGrace] = useState("300");
	const [secretRotating, setSecretRotating] = useState(false);
	const [adminTokenValue, setAdminTokenValue] = useState("");
	const [adminTokenGrace, setAdminTokenGrace] = useState("300");
	const [adminTokenRotating, setAdminTokenRotating] = useState(false);
	const [adminMessage, setAdminMessage] = useState<{
		type: "success" | "error";
		text: string;
	} | null>(null);

	const fetchConfig = useCallback(async () => {
		setLoading(true);
		setError(null);
		try {
			const data = await adminConfigApi.getEnvConfig();
			const payload = (data as Record<string, unknown>).data
				? ((data as Record<string, unknown>).data as EnvConfigData)
				: (data as unknown as EnvConfigData);
			if (payload.categories) {
				setConfigData(payload);
				// Initialize edited values from current config
				const initial: Record<string, string> = {};
				for (const cat of Object.values(payload.categories)) {
					for (const s of cat.settings) {
						initial[s.key] = s.value;
					}
				}
				setEditedValues(initial);
			}
		} catch (err) {
			setError(
				err instanceof Error ? err.message : "Failed to load configuration",
			);
		} finally {
			setLoading(false);
		}
	}, []);

	useEffect(() => {
		// Inline async IIFE — no synchronous setState in the effect body
		// (react-hooks/set-state-in-effect). `fetchConfig` is still defined above
		// for use by event handlers (refresh button, after-save reload).
		let cancelled = false;
		(async () => {
			try {
				const data = await adminConfigApi.getEnvConfig();
				if (cancelled) return;
				const payload = (data as Record<string, unknown>).data
					? ((data as Record<string, unknown>).data as EnvConfigData)
					: (data as unknown as EnvConfigData);
				if (payload.categories) {
					setConfigData(payload);
					const initial: Record<string, string> = {};
					for (const cat of Object.values(payload.categories)) {
						for (const s of cat.settings) {
							initial[s.key] = s.value;
						}
					}
					setEditedValues(initial);
				}
			} catch (err) {
				if (cancelled) return;
				setError(
					err instanceof Error ? err.message : "Failed to load configuration",
				);
			} finally {
				if (!cancelled) setLoading(false);
			}
		})();
		return () => {
			cancelled = true;
		};
	}, []);

	const handleValueChange = (key: string, value: string) => {
		setEditedValues((prev) => ({ ...prev, [key]: value }));
	};

	const toggleSecretVisibility = (key: string) => {
		setVisibleSecrets((prev) => {
			const next = new Set(prev);
			if (next.has(key)) next.delete(key);
			else next.add(key);
			return next;
		});
	};

	const handleSaveCategory = async (categoryKey: string) => {
		if (!configData) return;
		setSaving(categoryKey);
		setSaveStatus((prev) => ({ ...prev, [categoryKey]: "saving" as const }));

		// Gather only the settings for this category that have been changed
		const overrides: Record<string, string> = {};
		const settings = configData.categories[categoryKey].settings;
		for (const s of settings) {
			const edited = editedValues[s.key];
			const original = s.value;
			// Only include if value differs from original (and for secrets, always include the visible edit)
			if (edited !== original || visibleSecrets.has(s.key)) {
				overrides[s.key] = edited;
			}
		}

		if (Object.keys(overrides).length === 0) {
			setSaveStatus((prev) => ({ ...prev, [categoryKey]: "saved" as const }));
			setTimeout(
				() =>
					setSaveStatus((prev) => {
						const next = { ...prev };
						delete next[categoryKey];
						return next;
					}),
				2000,
			);
			setSaving(null);
			return;
		}

		try {
			const data = await adminConfigApi.updateEnvConfig({ overrides });
			if ((data as Record<string, unknown>).success) {
				setSaveStatus((prev) => ({ ...prev, [categoryKey]: "saved" as const }));
				// Refresh config to get updated masked values
				await fetchConfig();
			} else {
				throw new Error(
					((data as Record<string, unknown>).message as string) ||
						"Save failed",
				);
			}
		} catch (err) {
			setSaveStatus((prev) => ({ ...prev, [categoryKey]: "error" as const }));
		} finally {
			setTimeout(
				() =>
					setSaveStatus((prev) => {
						const next = { ...prev };
						delete next[categoryKey];
						return next;
					}),
				3000,
			);
			setSaving(null);
		}
	};

	const renderBooleanInput = (setting: EnvSetting, value: string) => {
		const isChecked = value === "true" || value === "1";
		return (
			<label className="relative inline-flex items-center cursor-pointer">
				<input
					type="checkbox"
					className="sr-only peer"
					checked={isChecked}
					onChange={(e) =>
						handleValueChange(setting.key, e.target.checked ? "true" : "false")
					}
				/>
				<div className="w-9 h-5 bg-slate-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600" />
			</label>
		);
	};

	const renderSecretInput = (
		setting: EnvSetting,
		value: string,
		isVisible: boolean,
	) => {
		return (
			<div className="flex gap-2">
				<div className="relative flex-1">
					<input
						type={isVisible ? "text" : "password"}
						value={value}
						onChange={(e) => handleValueChange(setting.key, e.target.value)}
						placeholder={
							setting.is_set
								? "••••••••"
								: `Default: ${setting.type === "url" ? "https://..." : "Not set"}`
						}
						className="w-full px-3 py-2 pr-9 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono placeholder-slate-600 focus:border-blue-500 focus:outline-none"
					/>
					<button
						type="button"
						onClick={() => toggleSecretVisibility(setting.key)}
						className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
						title={isVisible ? "Hide value" : "Show value"}
					>
						{isVisible ? (
							<EyeOff className="h-4 w-4" />
						) : (
							<Eye className="h-4 w-4" />
						)}
					</button>
				</div>
			</div>
		);
	};

	const renderNumericInput = (setting: EnvSetting, value: string) => (
		<input
			type="number"
			value={value}
			onChange={(e) => handleValueChange(setting.key, e.target.value)}
			className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-blue-500 focus:outline-none"
		/>
	);

	const renderTextInput = (setting: EnvSetting, value: string) => (
		<input
			type="text"
			value={value}
			onChange={(e) => handleValueChange(setting.key, e.target.value)}
			placeholder={`Default: ${setting.type === "url" ? "https://..." : "Not set"}`}
			className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-blue-500 focus:outline-none"
		/>
	);

	const renderSettingInput = (setting: EnvSetting) => {
		const value = editedValues[setting.key] ?? setting.value;
		if (setting.type === "boolean") return renderBooleanInput(setting, value);
		if (setting.is_secret || setting.type === "secret") {
			return renderSecretInput(setting, value, visibleSecrets.has(setting.key));
		}
		if (setting.type === "number") return renderNumericInput(setting, value);
		return renderTextInput(setting, value);
	};

	const getSourceBadge = (source: string) => {
		switch (source) {
			case "env":
				return (
					<span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-green-500/15 text-green-400 border border-green-500/30">
						Env
					</span>
				);
			case "override":
				return (
					<span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-400 border border-blue-500/30">
						Override
					</span>
				);
			default:
				return (
					<span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-500/15 text-slate-400 border border-slate-500/30">
						Default
					</span>
				);
		}
	};

	const categoryKeys = configData ? Object.keys(configData.categories) : [];

	// ── Admin action handlers ──

	// `fetchCacheStatsCore` does NOT call setCacheLoading(true) synchronously —
	// only setCacheStats/setCacheLoading(false) after the first await. Safe to
	// call from an effect (react-hooks/set-state-in-effect). `fetchCacheStats`
	// wraps it with synchronous setCacheLoading(true) for explicit user actions.
	const fetchCacheStatsCore = useCallback(async () => {
		try {
			const res = await adminApi.getCacheStats();
			if (res.success && res.data) setCacheStats(res.data);
		} catch {
			/* ignore */
		} finally {
			setCacheLoading(false);
		}
	}, []);

	const fetchCacheStats = useCallback(async () => {
		setCacheLoading(true);
		await fetchCacheStatsCore();
	}, [fetchCacheStatsCore]);

	const handleClearCache = useCallback(async () => {
		setCacheClearing(true);
		setAdminMessage(null);
		try {
			const res = await adminApi.clearCache();
			setAdminMessage({
				type: "success",
				text: res.message || "Cache cleared successfully",
			});
			await fetchCacheStats();
		} catch (err) {
			setAdminMessage({
				type: "error",
				text: err instanceof Error ? err.message : "Failed to clear cache",
			});
		} finally {
			setCacheClearing(false);
		}
	}, [fetchCacheStats]);

	const handleToggleFlag = useCallback(
		async (key: string, enabled: boolean) => {
			setFlagToggling(key);
			setAdminMessage(null);
			try {
				const res = await adminApi.setFeatureFlag({ key, enabled });
				setAdminMessage({
					type: "success",
					text:
						res.message || `Flag "${key}" ${enabled ? "enabled" : "disabled"}`,
				});
				setFeatureFlags((prev) => (prev ? { ...prev, [key]: enabled } : prev));
			} catch (err) {
				setAdminMessage({
					type: "error",
					text: err instanceof Error ? err.message : "Failed to toggle flag",
				});
			} finally {
				setFlagToggling(null);
			}
		},
		[],
	);

	const fetchDbHealthCore = useCallback(async () => {
		try {
			const res = await adminApi.getDatabaseHealth();
			if (res.success && res.data) setDbHealth(res.data);
		} catch {
			/* ignore */
		} finally {
			setDbHealthLoading(false);
		}
	}, []);

	const fetchDbHealth = useCallback(async () => {
		setDbHealthLoading(true);
		await fetchDbHealthCore();
	}, [fetchDbHealthCore]);

	const handleRotateSecret = useCallback(async () => {
		if (!secretName || !secretValue) return;
		setSecretRotating(true);
		setAdminMessage(null);
		try {
			const res = await adminApi.rotateSecret({
				secret_name: secretName,
				new_value: secretValue,
				grace_period_seconds: Number(secretGrace) || 300,
			});
			setAdminMessage({
				type: "success",
				text: res.message || "Secret rotated successfully",
			});
			setSecretName("");
			setSecretValue("");
		} catch (err) {
			setAdminMessage({
				type: "error",
				text: err instanceof Error ? err.message : "Failed to rotate secret",
			});
		} finally {
			setSecretRotating(false);
		}
	}, [secretName, secretValue, secretGrace]);

	const handleRotateAdminToken = useCallback(async () => {
		if (!adminTokenValue) return;
		setAdminTokenRotating(true);
		setAdminMessage(null);
		try {
			const res = await adminApi.rotateAdminToken({
				new_token: adminTokenValue,
				grace_period_seconds: Number(adminTokenGrace) || 300,
			});
			setAdminMessage({
				type: "success",
				text: res.message || "Admin token rotated successfully",
			});
			setAdminTokenValue("");
		} catch (err) {
			setAdminMessage({
				type: "error",
				text:
					err instanceof Error ? err.message : "Failed to rotate admin token",
			});
		} finally {
			setAdminTokenRotating(false);
		}
	}, [adminTokenValue, adminTokenGrace]);

	// Load admin data when category is selected. Uses a shared helper that
	// performs the fetch + setState after the first `await`, so no synchronous
	// setState in the effect body (react-hooks/set-state-in-effect). The helper
	// eliminates the cross-category duplication (SonarCloud CPD finding).
	useEffect(() => {
		let cancelled = false;
		const run = <T,>(
			fetcher: () => Promise<{ success: boolean; data?: T }>,
			setter: (data: T) => void,
			loadingSetter: (loading: boolean) => void,
		) => {
			(async () => {
				try {
					const res = await fetcher();
					if (cancelled) return;
					if (res.success && res.data) setter(res.data);
				} catch {
					/* ignore */
				} finally {
					if (!cancelled) loadingSetter(false);
				}
			})();
		};
		if (activeCategory === "_cache")
			run(adminApi.getCacheStats, setCacheStats, setCacheLoading);
		else if (activeCategory === "_feature_flags")
			run(adminApi.getFeatureFlags, setFeatureFlags, setFlagsLoading);
		else if (activeCategory === "_db_health")
			run(adminApi.getDatabaseHealth, setDbHealth, setDbHealthLoading);
		return () => {
			cancelled = true;
		};
	}, [activeCategory]);

	// ── Render admin sections ──

	const renderCacheSection = () => (
		<div className="space-y-4">
			<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
				<div className="flex items-center gap-2 mb-1">
					<Database className="h-5 w-5 text-blue-400" />
					<h2 className="text-lg font-semibold text-slate-100">
						Cache Management
					</h2>
				</div>
				<p className="text-sm text-slate-400">
					View cache statistics and clear cached data. Admin-only operation.
				</p>
			</div>
			{cacheLoading ? (
				<div className="flex items-center justify-center py-8">
					<Loader2 className="h-6 w-6 text-blue-400 animate-spin" />
				</div>
			) : cacheStats ? (
				<div className="bg-slate-800/50 border border-slate-700 rounded-lg divide-y divide-slate-700/50">
					<div className="p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
						<div className="text-center">
							<p className="text-2xl font-bold text-slate-100">
								{cacheStats.entries}
							</p>
							<p className="text-xs text-slate-500">Entries</p>
						</div>
						<div className="text-center">
							<p className="text-2xl font-bold text-slate-100">
								{cacheStats.max_entries}
							</p>
							<p className="text-xs text-slate-500">Max Entries</p>
						</div>
						<div className="text-center">
							<p className="text-2xl font-bold text-slate-100">
								{cacheStats.memory_usage_mb.toFixed(1)} MB
							</p>
							<p className="text-xs text-slate-500">Memory Usage</p>
						</div>
						<div className="text-center">
							<p className="text-2xl font-bold text-slate-100">
								{(cacheStats.hit_rate * 100).toFixed(1)}%
							</p>
							<p className="text-xs text-slate-500">Hit Rate</p>
						</div>
					</div>
					<div className="p-4 flex items-center justify-between">
						<span className="text-xs text-slate-500">
							Clearing the cache will remove all cached data. This cannot be
							undone.
						</span>
						<button
							type="button"
							onClick={handleClearCache}
							disabled={cacheClearing}
							className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
						>
							<Trash2 className="h-4 w-4" />
							{cacheClearing ? "Clearing..." : "Clear Cache"}
						</button>
					</div>
				</div>
			) : (
				<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-center text-slate-500 text-sm">
					Failed to load cache stats
				</div>
			)}
		</div>
	);

	const renderFeatureFlagsSection = () => (
		<div className="space-y-4">
			<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
				<div className="flex items-center gap-2 mb-1">
					<Flag className="h-5 w-5 text-amber-400" />
					<h2 className="text-lg font-semibold text-slate-100">
						Feature Flags
					</h2>
				</div>
				<p className="text-sm text-slate-400">
					Toggle feature flags in real-time. Changes take effect immediately.
				</p>
			</div>
			{flagsLoading ? (
				<div className="flex items-center justify-center py-8">
					<Loader2 className="h-6 w-6 text-amber-400 animate-spin" />
				</div>
			) : featureFlags ? (
				<div className="bg-slate-800/50 border border-slate-700 rounded-lg divide-y divide-slate-700/50">
					{Object.entries(featureFlags).length === 0 ? (
						<div className="p-4 text-center text-slate-500 text-sm">
							No feature flags configured
						</div>
					) : (
						Object.entries(featureFlags).map(([key, enabled]) => (
							<div
								key={key}
								className="p-4 flex items-center justify-between hover:bg-slate-700/20 transition-colors"
							>
								<div>
									<p className="text-sm font-medium text-slate-200">{key}</p>
									<p className="text-xs text-slate-500 font-mono">{key}</p>
								</div>
								<div className="flex items-center gap-3">
									<span
										className={`text-xs font-medium px-2 py-0.5 rounded ${enabled ? "bg-green-500/15 text-green-400 border border-green-500/30" : "bg-red-500/15 text-red-400 border border-red-500/30"}`}
									>
										{enabled ? "Enabled" : "Disabled"}
									</span>
									<button
										type="button"
										onClick={() => handleToggleFlag(key, !enabled)}
										disabled={flagToggling === key}
										className="relative inline-flex items-center h-6 w-11 rounded-full transition-colors focus:outline-none disabled:opacity-50"
										style={{ backgroundColor: enabled ? "#22c55e" : "#475569" }}
									>
										<span
											className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? "translate-x-6" : "translate-x-1"}`}
										/>
									</button>
								</div>
							</div>
						))
					)}
				</div>
			) : (
				<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-center text-slate-500 text-sm">
					Failed to load feature flags
				</div>
			)}
		</div>
	);

	const renderSecretRotationSection = () => (
		<div className="space-y-4">
			<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
				<div className="flex items-center gap-2 mb-1">
					<KeyRound className="h-5 w-5 text-red-400" />
					<h2 className="text-lg font-semibold text-slate-100">
						Secret Rotation
					</h2>
				</div>
				<p className="text-sm text-slate-400">
					Hot-rotate security secrets with a grace period. Old secrets remain
					valid during the grace period.
				</p>
			</div>
			{/* Secret Rotation Form */}
			<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 space-y-4">
				<h3 className="text-sm font-semibold text-slate-300">
					Rotate Security Secret
				</h3>
				<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
					<div>
						<label className="text-xs text-slate-500 mb-1 block">
							Secret Name
						</label>
						<input
							type="text"
							value={secretName}
							onChange={(e) => setSecretName(e.target.value)}
							placeholder="e.g. FIREAI_SESSION_SECRET"
							className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-blue-500 focus:outline-none"
						/>
					</div>
					<div>
						<label className="text-xs text-slate-500 mb-1 block">
							New Value
						</label>
						<input
							type="password"
							value={secretValue}
							onChange={(e) => setSecretValue(e.target.value)}
							placeholder="New secret value"
							className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-blue-500 focus:outline-none"
						/>
					</div>
					<div>
						<label className="text-xs text-slate-500 mb-1 block">
							Grace Period (s)
						</label>
						<input
							type="number"
							value={secretGrace}
							onChange={(e) => setSecretGrace(e.target.value)}
							className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-blue-500 focus:outline-none"
						/>
					</div>
				</div>
				<button
					type="button"
					onClick={handleRotateSecret}
					disabled={secretRotating || !secretName || !secretValue}
					className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
				>
					<Shield className="h-4 w-4" />
					{secretRotating ? "Rotating..." : "Rotate Secret"}
				</button>
			</div>
			{/* Admin Token Rotation */}
			<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 space-y-4">
				<h3 className="text-sm font-semibold text-slate-300">
					Rotate Admin Token
				</h3>
				<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
					<div className="md:col-span-2">
						<label className="text-xs text-slate-500 mb-1 block">
							New Admin Token
						</label>
						<input
							type="password"
							value={adminTokenValue}
							onChange={(e) => setAdminTokenValue(e.target.value)}
							placeholder="New admin token value"
							className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-blue-500 focus:outline-none"
						/>
					</div>
					<div>
						<label className="text-xs text-slate-500 mb-1 block">
							Grace Period (s)
						</label>
						<input
							type="number"
							value={adminTokenGrace}
							onChange={(e) => setAdminTokenGrace(e.target.value)}
							className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-blue-500 focus:outline-none"
						/>
					</div>
				</div>
				<button
					type="button"
					onClick={handleRotateAdminToken}
					disabled={adminTokenRotating || !adminTokenValue}
					className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
				>
					<KeyRound className="h-4 w-4" />
					{adminTokenRotating ? "Rotating..." : "Rotate Admin Token"}
				</button>
			</div>
		</div>
	);

	const renderDbHealthSection = () => (
		<div className="space-y-4">
			<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
				<div className="flex items-center justify-between mb-1">
					<div className="flex items-center gap-2">
						<Activity className="h-5 w-5 text-green-400" />
						<h2 className="text-lg font-semibold text-slate-100">
							Database Health
						</h2>
					</div>
					<button
						type="button"
						onClick={fetchDbHealth}
						disabled={dbHealthLoading}
						className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-xs transition-colors disabled:opacity-50"
					>
						<RefreshCw
							className={`h-3 w-3 ${dbHealthLoading ? "animate-spin" : ""}`}
						/>
						Refresh
					</button>
				</div>
				<p className="text-sm text-slate-400">
					Live health status of all database backends (PostgreSQL, Qdrant,
					Neo4j, Redis).
				</p>
			</div>
			{dbHealthLoading ? (
				<div className="flex items-center justify-center py-8">
					<Loader2 className="h-6 w-6 text-green-400 animate-spin" />
				</div>
			) : dbHealth ? (
				<div className="bg-slate-800/50 border border-slate-700 rounded-lg divide-y divide-slate-700/50">
					{Object.entries(dbHealth).map(([name, info]) => (
						<div
							key={name}
							className="p-4 flex items-center justify-between hover:bg-slate-700/20 transition-colors"
						>
							<div className="flex items-center gap-3">
								<div
									className={`h-3 w-3 rounded-full ${info.status === "healthy" ? "bg-green-500" : info.status === "degraded" ? "bg-yellow-500" : "bg-red-500"}`}
								/>
								<div>
									<p className="text-sm font-medium text-slate-200">{name}</p>
									{info.details && (
										<p className="text-xs text-slate-500">{info.details}</p>
									)}
								</div>
							</div>
							<div className="text-right">
								<span
									className={`text-xs font-medium px-2 py-0.5 rounded ${info.status === "healthy" ? "bg-green-500/15 text-green-400" : info.status === "degraded" ? "bg-yellow-500/15 text-yellow-400" : "bg-red-500/15 text-red-400"}`}
								>
									{info.status}
								</span>
								<p className="text-xs text-slate-500 mt-1">
									{info.latency_ms}ms
								</p>
							</div>
						</div>
					))}
				</div>
			) : (
				<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-center text-slate-500 text-sm">
					Failed to load database health
				</div>
			)}
		</div>
	);

	return (
		<div className="p-6 space-y-6">
			{/* Header */}
			<div className="flex items-start justify-between">
				<div>
					<h1 className="text-3xl font-bold text-slate-100 flex items-center gap-2">
						<Settings2 className="h-8 w-8 text-purple-500" />
						Environment Configuration
					</h1>
					<p className="text-slate-400 mt-2">
						Manage all environment-level settings — changes persist in the
						database and apply on next server restart
					</p>
				</div>
				<button
					type="button"
					onClick={fetchConfig}
					disabled={loading}
					className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded-lg text-sm transition-colors disabled:opacity-50"
				>
					<RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
					Refresh
				</button>
			</div>

			{/* Loading */}
			{loading && (
				<div className="flex items-center justify-center py-16">
					<Loader2 className="h-8 w-8 text-purple-400 animate-spin" />
				</div>
			)}

			{/* Error */}
			{error && (
				<div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-start gap-3">
					<AlertTriangle className="h-5 w-5 text-red-400 mt-0.5 shrink-0" />
					<div>
						<p className="text-sm font-medium text-red-400">
							Failed to load configuration
						</p>
						<p className="text-xs text-red-300/70 mt-1">{error}</p>
					</div>
				</div>
			)}

			{/* Main Content */}
			{!loading && configData && (
				<div className="flex flex-col lg:flex-row gap-6">
					{/* Sidebar Category Nav */}
					<div className="lg:w-56 shrink-0">
						<nav className="space-y-1 sticky top-6">
							{categoryKeys.map((key) => {
								const meta = CATEGORY_META[key];
								return (
									<button
										key={key}
										type="button"
										onClick={() => setActiveCategory(key)}
										className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium transition-all text-left ${
											activeCategory === key
												? "bg-purple-500/15 text-purple-300 border border-purple-500/30"
												: "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50 border border-transparent"
										}`}
									>
										<span className="text-base">{meta?.icon || "⚙️"}</span>
										<span>{configData.categories[key]?.label || key}</span>
									</button>
								);
							})}
						</nav>
					</div>

					{/* Settings Forms */}
					<div className="flex-1 min-w-0">
						{/* Admin Message Banner */}
						{adminMessage && (
							<div
								className={`mb-4 p-3 rounded-lg border flex items-center gap-2 ${adminMessage.type === "success" ? "bg-green-500/10 border-green-500/30" : "bg-red-500/10 border-red-500/30"}`}
							>
								{adminMessage.type === "success" ? (
									<CheckCircle2 className="h-4 w-4 text-green-400 shrink-0" />
								) : (
									<AlertTriangle className="h-4 w-4 text-red-400 shrink-0" />
								)}
								<p
									className={`text-sm ${adminMessage.type === "success" ? "text-green-400" : "text-red-400"}`}
								>
									{adminMessage.text}
								</p>
								<button
									type="button"
									onClick={() => setAdminMessage(null)}
									className="ml-auto text-slate-500 hover:text-slate-300 text-xs"
								>
									Dismiss
								</button>
							</div>
						)}
						{/* Admin sections (rendered before regular categories) */}
						{activeCategory === "_cache" && renderCacheSection()}
						{activeCategory === "_feature_flags" && renderFeatureFlagsSection()}
						{activeCategory === "_secret_rotation" &&
							renderSecretRotationSection()}
						{activeCategory === "_db_health" && renderDbHealthSection()}
						{/* Regular category settings */}
						{categoryKeys.map((catKey) => {
							if (catKey !== activeCategory) return null;
							const cat = configData.categories[catKey];
							const meta = CATEGORY_META[catKey];
							const status = saveStatus[catKey];

							return (
								<div key={catKey} className="space-y-4">
									{/* Category Header */}
									<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4">
										<div className="flex items-center gap-2 mb-1">
											<span className="text-xl">{meta?.icon || "⚙️"}</span>
											<h2 className="text-lg font-semibold text-slate-100">
												{cat.label}
											</h2>
										</div>
										<p className="text-sm text-slate-400">
											{meta?.description || ""}
										</p>
									</div>

									{/* Settings */}
									<div className="bg-slate-800/50 border border-slate-700 rounded-lg divide-y divide-slate-700/50">
										{cat.settings.map((setting) => (
											<div
												key={setting.key}
												className="p-4 hover:bg-slate-700/20 transition-colors"
											>
												<div className="flex items-start justify-between gap-4">
													<div className="flex-1 min-w-0">
														<div className="flex items-center gap-2 mb-1">
															<label className="text-sm font-medium text-slate-200">
																{setting.label}
															</label>
															{getSourceBadge(setting.source)}
														</div>
														<p className="text-xs text-slate-500 font-mono mb-2">
															{setting.key}
														</p>
													</div>
													<div className="w-full max-w-sm shrink-0">
														{renderSettingInput(setting)}
													</div>
												</div>
											</div>
										))}
									</div>

									{/* Action Bar */}
									<div className="flex items-center justify-between bg-slate-800/50 border border-slate-700 rounded-lg p-3">
										<div>
											{status === "saving" && (
												<span className="text-xs text-blue-400 flex items-center gap-1">
													<Loader2 className="h-3 w-3 animate-spin" /> Saving...
												</span>
											)}
											{status === "saved" && (
												<span className="text-xs text-green-400 flex items-center gap-1">
													<CheckCircle2 className="h-3 w-3" /> Saved
													successfully
												</span>
											)}
											{status === "error" && (
												<span className="text-xs text-red-400 flex items-center gap-1">
													<AlertTriangle className="h-3 w-3" /> Save failed
												</span>
											)}
											{!status && (
												<span className="text-xs text-slate-500">
													Changes persist to the database and apply on next
													restart
												</span>
											)}
										</div>
										<button
											type="button"
											onClick={() => handleSaveCategory(catKey)}
											disabled={saving === catKey}
											className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
										>
											<Save className="h-4 w-4" />
											Save {cat.label}
										</button>
									</div>

									{/* Info Note */}
									<div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-start gap-2">
										<AlertTriangle className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
										<p className="text-xs text-amber-400">
											Some settings require a server restart to take effect.
											Secrets are encrypted at rest and masked in the UI.
										</p>
									</div>
								</div>
							);
						})}
					</div>
				</div>
			)}
		</div>
	);
};

export default AdvancedSettingsPage;
