/**
 * AgentSettingsContext.test.tsx — Unit test suite for AgentSettingsContext
 *
 * Covers:
 *  1. Initial default state
 *  2. useAgentSettings error when outside provider
 *  3. Storage load & corrupt JSON fallback
 *  4. Storage save & error handling
 *  5. updateLLM (auto-model update vs explicit model)
 *  6. updateGovernance
 *  7. updateCapability
 *  8. updateContextBudget
 *  9. updateWorkingMemory
 * 10. resetToDefaults
 */
import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, beforeEach, vi } from "vitest";
import React from "react";
import {
	AgentSettingsProvider,
	useAgentSettings,
	DEFAULT_SETTINGS,
	PROVIDER_MODELS,
} from "../AgentSettingsContext";

const STORAGE_KEY = "bazspark:agent-settings:v1";

describe("AgentSettingsContext", () => {
	beforeEach(() => {
		localStorage.clear();
		vi.restoreAllMocks();
	});

	it("throws error when used outside provider", () => {
		expect(() => renderHook(() => useAgentSettings())).toThrow(
			"useAgentSettings must be used within <AgentSettingsProvider>",
		);
	});

	it("provides default settings when localStorage is empty", () => {
		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		expect(result.current.settings).toEqual(DEFAULT_SETTINGS);
	});

	it("loads and merges settings from localStorage", () => {
		const customState = {
			llm: {
				provider: "openai" as const,
				apiKeyLocal: "sk-test1234",
				model: "gpt-4o-mini",
				temperature: 0.05,
			},
			contextBudget: {
				tokenBudget: 3000,
				cadMeshPruning: false,
			},
		};
		localStorage.setItem(STORAGE_KEY, JSON.stringify(customState));

		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		expect(result.current.settings.llm.provider).toBe("openai");
		expect(result.current.settings.llm.apiKeyLocal).toBe("sk-test1234");
		expect(result.current.settings.llm.model).toBe("gpt-4o-mini");
		expect(result.current.settings.contextBudget.tokenBudget).toBe(3000);
		expect(result.current.settings.contextBudget.cadMeshPruning).toBe(false);
		expect(result.current.settings.governance).toEqual(DEFAULT_SETTINGS.governance);
	});

	it("falls back to DEFAULT_SETTINGS if localStorage has corrupted JSON", () => {
		localStorage.setItem(STORAGE_KEY, "{corrupt-json");

		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		expect(result.current.settings).toEqual(DEFAULT_SETTINGS);
	});

	it("handles localStorage quota exceeded gracefully", () => {
		const setItemSpy = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
			throw new Error("QuotaExceededError");
		});

		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		act(() => {
			result.current.updateLLM({ temperature: 0.08 });
		});

		expect(result.current.settings.llm.temperature).toBe(0.08);
		setItemSpy.mockRestore();
	});

	it("updates LLM provider and automatically switches default model", () => {
		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		act(() => {
			result.current.updateLLM({ provider: "gemini" });
		});

		expect(result.current.settings.llm.provider).toBe("gemini");
		expect(result.current.settings.llm.model).toBe(PROVIDER_MODELS.gemini);
	});

	it("updates LLM provider and preserves custom model when supplied", () => {
		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		act(() => {
			result.current.updateLLM({ provider: "openai", model: "o1-preview" });
		});

		expect(result.current.settings.llm.provider).toBe("openai");
		expect(result.current.settings.llm.model).toBe("o1-preview");
	});

	it("updates governance policies", () => {
		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		act(() => {
			result.current.updateGovernance({
				approvalThreshold: "SAFETY_CRITICAL",
				requireLineageBeforeApprove: true,
			});
		});

		expect(result.current.settings.governance.approvalThreshold).toBe("SAFETY_CRITICAL");
		expect(result.current.settings.governance.requireLineageBeforeApprove).toBe(true);
		expect(result.current.settings.governance.autoRollbackOnPhysicsWarning).toBe(true);
	});

	it("updates capability registry toggles", () => {
		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		act(() => {
			result.current.updateCapability("electrical.calculate_battery", false);
		});

		expect(result.current.settings.capabilities["electrical.calculate_battery"]).toBe(false);
		expect(result.current.settings.capabilities["spatial.place_devices"]).toBe(true);
	});

	it("updates context budget", () => {
		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		act(() => {
			result.current.updateContextBudget({ tokenBudget: 2500, cadMeshPruning: false });
		});

		expect(result.current.settings.contextBudget.tokenBudget).toBe(2500);
		expect(result.current.settings.contextBudget.cadMeshPruning).toBe(false);
	});

	it("updates working memory configuration", () => {
		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		act(() => {
			result.current.updateWorkingMemory({ cacheTtlSeconds: 600 });
		});

		expect(result.current.settings.workingMemory.cacheTtlSeconds).toBe(600);
	});

	it("resets settings to defaults", () => {
		const { result } = renderHook(() => useAgentSettings(), {
			wrapper: ({ children }) => (
				<AgentSettingsProvider>{children}</AgentSettingsProvider>
			),
		});

		act(() => {
			result.current.updateLLM({ provider: "ollama", apiKeyLocal: "12345" });
			result.current.updateContextBudget({ tokenBudget: 4000 });
		});

		expect(result.current.settings.llm.provider).toBe("ollama");

		act(() => {
			result.current.resetToDefaults();
		});

		expect(result.current.settings).toEqual(DEFAULT_SETTINGS);
	});
});
