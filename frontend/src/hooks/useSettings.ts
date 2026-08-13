/**
 * useSettings.ts — Hook for user settings persistence via backend API
 *
 * Links Placebo settings (apiTimeout, reportFormat, etc.) to the backend
 * instead of only using localStorage. Falls back to localStorage when
 * the backend is unavailable.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "@/services/api";

// ── Types ──────────────────────────────────────────────────────────────

export interface UserSettings {
	// General
	theme: string;
	language: string;
	notifications: boolean;

	// Security
	twoFactorAuth: boolean;
	passwordExpiry: number;

	// API
	apiTimeout: number;
	retryAttempts: number;

	// Reports
	autoSaveReports: boolean;
	reportFormat: string;
	reportQuality: string;
}

export const DEFAULT_SETTINGS: UserSettings = {
	theme: "dark",
	language: "en",
	notifications: true,

	twoFactorAuth: false,
	passwordExpiry: 90,

	apiTimeout: 30,
	retryAttempts: 3,

	autoSaveReports: true,
	reportFormat: "pdf",
	reportQuality: "high",
};

// ── localStorage helpers ───────────────────────────────────────────────

const SETTINGS_KEY = "fireai_settings_all";

function loadFromLocalStorage(): Partial<UserSettings> {
	try {
		const raw = localStorage.getItem(SETTINGS_KEY);
		if (!raw) return {};
		return JSON.parse(raw);
	} catch {
		return {};
	}
}

function saveToLocalStorage(settings: UserSettings): void {
	try {
		// Strip sensitive keys before persisting
		const SENSITIVE_KEYS = ["apiKey", "api_key", "password", "token", "secret"];
		const safe: Record<string, unknown> = {};
		for (const [k, v] of Object.entries(settings)) {
			if (
				!SENSITIVE_KEYS.some((s) => k.toLowerCase().includes(s.toLowerCase()))
			) {
				safe[k] = v;
			}
		}
		localStorage.setItem(SETTINGS_KEY, JSON.stringify(safe));
	} catch {
		// localStorage may be unavailable in sandboxed environments
	}
}

// ── Legacy per-key localStorage migration ──────────────────────────────

function migrateLegacySettings(): Partial<UserSettings> {
	const merged: Partial<UserSettings> = {};
	const legacyPrefix = "fireai_settings_";
	const keys = ["general", "security", "api", "reports"];

	try {
		for (const key of keys) {
			const raw = localStorage.getItem(`${legacyPrefix}${key}`);
			if (raw) {
				try {
					Object.assign(merged, JSON.parse(raw));
				} catch {
					// Skip malformed entries
				}
			}
		}
	} catch {
		// localStorage unavailable
	}

	return merged;
}

// ── Hook ───────────────────────────────────────────────────────────────

export function useSettings() {
	const [settings, setSettings] = useState<UserSettings>(DEFAULT_SETTINGS);
	const [loading, setLoading] = useState(true);
	const [saving, setSaving] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">(
		"idle",
	);

	// Load settings on mount — try backend first, fall back to localStorage
	useEffect(() => {
		let cancelled = false;

		const loadSettings = async () => {
			setLoading(true);
			try {
				// Try backend API first
				const backendSettings = await api.getSettings();
				if (!cancelled && backendSettings) {
					setSettings({ ...DEFAULT_SETTINGS, ...backendSettings });
					// Mirror to localStorage for offline access
					saveToLocalStorage({ ...DEFAULT_SETTINGS, ...backendSettings });
					setLoading(false);
					return;
				}
			} catch {
				// Backend unavailable — fall back to localStorage
			}

			if (!cancelled) {
				// Migrate legacy per-key settings, then load unified key
				const legacy = migrateLegacySettings();
				const local = loadFromLocalStorage();
				setSettings({ ...DEFAULT_SETTINGS, ...legacy, ...local });
				setLoading(false);
			}
		};

		loadSettings();
		return () => {
			cancelled = true;
		};
	}, []);

	// Save a partial settings update — persists to backend + localStorage
	const saveSettings = useCallback(
		async (partial: Partial<UserSettings>) => {
			const next = { ...settings, ...partial };
			setSettings(next);
			setSaving(true);
			setError(null);

			try {
				// Attempt backend save
				await api.saveSettings(next);
			} catch {
				// Backend save failed — still persist locally
				setError("backend_unavailable");
			}

			// Always persist to localStorage as fallback
			saveToLocalStorage(next);
			setSaving(false);
			setSaveStatus("saved");
			setTimeout(() => setSaveStatus("idle"), 2000);
		},
		[settings],
	);

	// Convenience: save a single section
	const saveSection = useCallback(
		(section: string, data: Record<string, unknown>) => {
			return saveSettings(data as Partial<UserSettings>);
		},
		[saveSettings],
	);

	return {
		settings,
		loading,
		saving,
		error,
		saveStatus,
		saveSettings,
		saveSection,
	};
}
