/**
 * useVoiceControl.test.ts - Unit Tests for useVoiceControl Hook & Speech Subsystem.
 */

import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	resolveSpeechLocale,
	sanitizeVoiceInput,
	useVoiceControl,
} from "../useVoiceControl";

// Mock toast
const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
	toast: (...args: unknown[]) => mockToast(...args),
	useToast: () => ({ toast: mockToast }),
}));

// Mock simpleStore actions
const mockAddElement = vi.fn();
const mockClearErrors = vi.fn();
const mockPushError = vi.fn();
const mockSetVoiceActive = vi.fn();
const mockSetDataMode = vi.fn();
const mockSetSelectedElement = vi.fn();

vi.mock("@/store/simpleStore", () => ({
	actions: {
		addElement: (el: unknown) => mockAddElement(el),
		clearErrors: () => mockClearErrors(),
		pushError: (err: unknown) => mockPushError(err),
		setVoiceActive: (active: boolean) => mockSetVoiceActive(active),
		setDataMode: (mode: string) => mockSetDataMode(mode),
		setSelectedElement: (el: unknown) => mockSetSelectedElement(el),
	},
}));

// Mock i18n
const mockI18nListeners = new Map<string, Array<(lang: string) => void>>();
vi.mock("@/i18n", () => {
	return {
		default: {
			language: "en",
			on: (event: string, cb: (lang: string) => void) => {
				const existing = mockI18nListeners.get(event) || [];
				existing.push(cb);
				mockI18nListeners.set(event, existing);
			},
			off: (event: string, cb: (lang: string) => void) => {
				const existing = mockI18nListeners.get(event) || [];
				mockI18nListeners.set(
					event,
					existing.filter((fn) => fn !== cb),
				);
			},
		},
	};
});

// Mock SpeechRecognition Class
class MockSpeechRecognition {
	continuous = false;
	interimResults = false;
	lang = "en-US";
	onstart: (() => void) | null = null;
	onresult: ((event: unknown) => void) | null = null;
	onerror: ((event: unknown) => void) | null = null;
	onend: (() => void) | null = null;

	start = vi.fn(() => {
		if (this.onstart) this.onstart();
	});
	stop = vi.fn(() => {
		if (this.onend) this.onend();
	});
	abort = vi.fn();
}

describe("sanitizeVoiceInput", () => {
	it("returns empty string when input is empty or null", () => {
		expect(sanitizeVoiceInput("")).toBe("");
		expect(sanitizeVoiceInput(null as unknown as string)).toBe("");
	});

	it("preserves clean speech queries", () => {
		const text = "Calculate voltage drop for branch circuit 2";
		expect(sanitizeVoiceInput(text)).toBe(text);
	});

	it("preserves Arabic voice queries", () => {
		const text = "احسب هبوط الجهد للوحة الرئيسية";
		expect(sanitizeVoiceInput(text)).toBe(text);
	});

	it("strips control characters and escape codes", () => {
		const raw = "Add generator\x00\x08\x1b now\x7f";
		expect(sanitizeVoiceInput(raw)).toBe("Add generator now");
	});

	it("neutralizes template formatting and backticks", () => {
		const raw = "Run `command` with ${param}";
		const sanitized = sanitizeVoiceInput(raw);
		expect(sanitized).not.toContain("`");
		expect(sanitized).not.toContain("${");
		expect(sanitized).not.toContain("}");
		expect(sanitized).toBe("Run command with param");
	});

	it("normalizes excessive whitespaces", () => {
		const raw = "  zoom    in    canvas   ";
		expect(sanitizeVoiceInput(raw)).toBe("zoom in canvas");
	});
});

describe("resolveSpeechLocale", () => {
	it("resolves Arabic to ar-EG", () => {
		expect(resolveSpeechLocale("ar")).toBe("ar-EG");
		expect(resolveSpeechLocale("ar-EG")).toBe("ar-EG");
		expect(resolveSpeechLocale("ar-SA")).toBe("ar-EG");
	});

	it("resolves English to en-US", () => {
		expect(resolveSpeechLocale("en")).toBe("en-US");
		expect(resolveSpeechLocale("en-GB")).toBe("en-US");
	});

	it("defaults non-Arabic to en-US", () => {
		expect(resolveSpeechLocale("fr")).toBe("en-US");
		expect(resolveSpeechLocale("de")).toBe("en-US");
	});
});

describe("useVoiceControl Hook", () => {
	let originalSpeechRecognition: unknown;

	beforeEach(() => {
		vi.clearAllMocks();
		originalSpeechRecognition = (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition;
		(window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = MockSpeechRecognition;
	});

	afterEach(() => {
		(window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = originalSpeechRecognition;
	});

	it("initializes with isSupported true and listening false", () => {
		const { result } = renderHook(() => useVoiceControl());
		expect(result.current.isSupported).toBe(true);
		expect(result.current.isListening).toBe(false);
		expect(result.current.transcript).toBe("");
	});

	it("starts and stops listening", () => {
		const { result } = renderHook(() => useVoiceControl());

		act(() => {
			result.current.startListening();
		});

		expect(result.current.isListening).toBe(true);
		expect(mockSetVoiceActive).toHaveBeenCalledWith(true);

		act(() => {
			result.current.stopListening();
		});

		expect(result.current.isListening).toBe(false);
		expect(mockSetVoiceActive).toHaveBeenCalledWith(false);
	});

	it("processes English voice commands and adds generator element", () => {
		let recognitionInstance: MockSpeechRecognition | null = null;

		class CapturingSpeechRecognition extends MockSpeechRecognition {
			constructor() {
				super();
				recognitionInstance = this;
			}
		}
		(window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = CapturingSpeechRecognition;

		const onCommandMock = vi.fn();
		const onTranscriptMock = vi.fn();

		const { result } = renderHook(() =>
			useVoiceControl({
				onCommand: onCommandMock,
				onTranscript: onTranscriptMock,
			}),
		);

		act(() => {
			result.current.startListening();
		});

		// Trigger result with "add generator"
		act(() => {
			if (recognitionInstance?.onresult) {
				recognitionInstance.onresult({
					results: [
						Object.assign([{ transcript: "Add generator", confidence: 0.98 }], {
							isFinal: true,
							length: 1,
						}),
					],
					resultIndex: 0,
				});
			}
		});

		expect(mockAddElement).toHaveBeenCalledWith(
			expect.objectContaining({ type: "generator", voltage: 11000 }),
		);
		expect(onCommandMock).toHaveBeenCalledWith("ADD_GENERATOR", "Add generator");
		expect(onTranscriptMock).toHaveBeenCalledWith("Add generator");
		expect(result.current.transcript).toBe("Add generator");
	});

	it("processes Arabic voice commands for battery addition and simulation", () => {
		let recognitionInstance: MockSpeechRecognition | null = null;

		class CapturingSpeechRecognition extends MockSpeechRecognition {
			constructor() {
				super();
				recognitionInstance = this;
			}
		}
		(window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = CapturingSpeechRecognition;

		const onCommandMock = vi.fn();
		const { result } = renderHook(() => useVoiceControl({ onCommand: onCommandMock }));

		act(() => {
			result.current.startListening();
		});

		// Arabic battery command
		act(() => {
			if (recognitionInstance?.onresult) {
				recognitionInstance.onresult({
					results: [
						Object.assign([{ transcript: "اضف بطارية", confidence: 0.95 }], {
							isFinal: true,
							length: 1,
						}),
					],
					resultIndex: 0,
				});
			}
		});

		expect(mockAddElement).toHaveBeenCalledWith(
			expect.objectContaining({ type: "battery", voltage: 220 }),
		);
		expect(onCommandMock).toHaveBeenCalledWith("ADD_BATTERY", "اضف بطارية");

		// Arabic simulation command
		act(() => {
			if (recognitionInstance?.onresult) {
				recognitionInstance.onresult({
					results: [
						Object.assign([{ transcript: "تشغيل المحاكاة", confidence: 0.97 }], {
							isFinal: true,
							length: 1,
						}),
					],
					resultIndex: 0,
				});
			}
		});

		expect(mockSetDataMode).toHaveBeenCalledWith("simulation");
		expect(onCommandMock).toHaveBeenCalledWith("RUN_SIMULATION", "تشغيل المحاكاة");
	});

	it("triggers toast notification on permission-denied error", () => {
		let recognitionInstance: MockSpeechRecognition | null = null;

		class CapturingSpeechRecognition extends MockSpeechRecognition {
			constructor() {
				super();
				recognitionInstance = this;
			}
		}
		(window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = CapturingSpeechRecognition;

		const onErrorMock = vi.fn();
		const { result } = renderHook(() => useVoiceControl({ onError: onErrorMock }));

		act(() => {
			result.current.startListening();
		});

		act(() => {
			if (recognitionInstance?.onerror) {
				recognitionInstance.onerror({ error: "not-allowed" });
			}
		});

		expect(onErrorMock).toHaveBeenCalledWith("not-allowed");
		expect(mockToast).toHaveBeenCalledWith(
			expect.objectContaining({
				variant: "destructive",
				title: expect.stringMatching(/Microphone|الميكروفون/),
			}),
		);
		expect(result.current.isListening).toBe(false);
	});

	it("triggers toast notification on network error", () => {
		let recognitionInstance: MockSpeechRecognition | null = null;

		class CapturingSpeechRecognition extends MockSpeechRecognition {
			constructor() {
				super();
				recognitionInstance = this;
			}
		}
		(window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = CapturingSpeechRecognition;

		const { result } = renderHook(() => useVoiceControl());

		act(() => {
			result.current.startListening();
		});

		act(() => {
			if (recognitionInstance?.onerror) {
				recognitionInstance.onerror({ error: "network" });
			}
		});

		expect(mockToast).toHaveBeenCalledWith(
			expect.objectContaining({
				variant: "destructive",
				title: expect.stringMatching(/Network|الشبكة|اتصال/),
			}),
		);
	});

	it("handles unsupported browser gracefully", () => {
		delete (window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition;
		delete (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition;

		const { result } = renderHook(() => useVoiceControl());

		expect(result.current.isSupported).toBe(false);

		act(() => {
			result.current.startListening();
		});

		expect(mockToast).toHaveBeenCalledWith(
			expect.objectContaining({
				variant: "destructive",
			}),
		);
		expect(mockPushError).toHaveBeenCalled();
	});

	it("clears transcript when clearTranscript is called", () => {
		const { result } = renderHook(() => useVoiceControl());

		act(() => {
			result.current.clearTranscript();
		});

		expect(result.current.transcript).toBe("");
		expect(result.current.interimTranscript).toBe("");
		expect(result.current.audioBlob).toBeNull();
	});
});
