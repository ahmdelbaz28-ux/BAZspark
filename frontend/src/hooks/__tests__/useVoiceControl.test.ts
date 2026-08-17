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
let latestMockInstance: MockSpeechRecognition | null = null;

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

const MockSpeechRecognitionProxy = function (this: unknown) {
	const instance = new MockSpeechRecognition();
	latestMockInstance = instance;
	return instance;
} as unknown as typeof MockSpeechRecognition;

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
		latestMockInstance = null;
		originalSpeechRecognition = (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition;
		(window as unknown as { SpeechRecognition: unknown }).SpeechRecognition = MockSpeechRecognitionProxy;
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
			if (latestMockInstance?.onresult) {
				latestMockInstance.onresult({
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
		const onCommandMock = vi.fn();
		const { result } = renderHook(() => useVoiceControl({ onCommand: onCommandMock }));

		act(() => {
			result.current.startListening();
		});

		// Arabic battery command
		act(() => {
			if (latestMockInstance?.onresult) {
				latestMockInstance.onresult({
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
			if (latestMockInstance?.onresult) {
				latestMockInstance.onresult({
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
		const onErrorMock = vi.fn();
		const { result } = renderHook(() => useVoiceControl({ onError: onErrorMock }));

		act(() => {
			result.current.startListening();
		});

		act(() => {
			if (latestMockInstance?.onerror) {
				latestMockInstance.onerror({ error: "not-allowed" });
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
		const { result } = renderHook(() => useVoiceControl());

		act(() => {
			result.current.startListening();
		});

		act(() => {
			if (latestMockInstance?.onerror) {
				latestMockInstance.onerror({ error: "network" });
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

	it("processes remaining voice commands (panel, zoom in/out, clear errors, select/clear)", () => {
		const onCommandMock = vi.fn();
		const { result } = renderHook(() => useVoiceControl({ onCommand: onCommandMock }));

		act(() => {
			result.current.startListening();
		});

		// 1. Add panel
		act(() => {
			latestMockInstance?.onresult?.({
				results: [
					Object.assign([{ transcript: "Add panel", confidence: 0.95 }], {
						isFinal: true,
						length: 1,
					}),
				],
				resultIndex: 0,
			});
		});
		expect(mockAddElement).toHaveBeenCalledWith(
			expect.objectContaining({ type: "panel", voltage: 220 }),
		);
		expect(onCommandMock).toHaveBeenCalledWith("ADD_PANEL", "Add panel");

		// 2. Zoom in
		act(() => {
			latestMockInstance?.onresult?.({
				results: [
					Object.assign([{ transcript: "Zoom in", confidence: 0.95 }], {
						isFinal: true,
						length: 1,
					}),
				],
				resultIndex: 0,
			});
		});
		expect(onCommandMock).toHaveBeenCalledWith("ZOOM_IN", "Zoom in");

		// 3. Zoom out
		act(() => {
			latestMockInstance?.onresult?.({
				results: [
					Object.assign([{ transcript: "Zoom out", confidence: 0.95 }], {
						isFinal: true,
						length: 1,
					}),
				],
				resultIndex: 0,
			});
		});
		expect(onCommandMock).toHaveBeenCalledWith("ZOOM_OUT", "Zoom out");

		// 4. Clear errors
		act(() => {
			latestMockInstance?.onresult?.({
				results: [
					Object.assign([{ transcript: "Clear errors", confidence: 0.95 }], {
						isFinal: true,
						length: 1,
					}),
				],
				resultIndex: 0,
			});
		});
		expect(mockClearErrors).toHaveBeenCalled();
		expect(onCommandMock).toHaveBeenCalledWith("CLEAR_ERRORS", "Clear errors");

		// 5. Select / Deselect
		act(() => {
			latestMockInstance?.onresult?.({
				results: [
					Object.assign([{ transcript: "الغاء التحديد", confidence: 0.95 }], {
						isFinal: true,
						length: 1,
					}),
				],
				resultIndex: 0,
			});
		});
		expect(mockSetSelectedElement).toHaveBeenCalledWith(null);
		expect(onCommandMock).toHaveBeenCalledWith("SELECT_OR_CLEAR", "الغاء التحديد");
	});

	it("handles interim transcripts and onInterim callback", () => {
		const onInterimMock = vi.fn();
		const { result } = renderHook(() =>
			useVoiceControl({ onInterim: onInterimMock }),
		);

		act(() => {
			result.current.startListening();
		});

		act(() => {
			latestMockInstance?.onresult?.({
				results: [
					Object.assign([{ transcript: "calculating drop", confidence: 0.8 }], {
						isFinal: false,
						length: 1,
					}),
				],
				resultIndex: 0,
			});
		});

		expect(result.current.interimTranscript).toBe("calculating drop");
		expect(onInterimMock).toHaveBeenCalledWith("calculating drop");
	});

	it("handles onend and generic speech errors", () => {
		const { result } = renderHook(() => useVoiceControl());

		act(() => {
			result.current.startListening();
		});
		expect(result.current.isListening).toBe(true);

		act(() => {
			latestMockInstance?.onerror?.({ error: "audio-capture" });
		});
		expect(result.current.isListening).toBe(false);
		expect(mockPushError).toHaveBeenCalledWith(
			expect.objectContaining({ message: expect.stringContaining("audio-capture") }),
		);

		act(() => {
			latestMockInstance?.onend?.();
		});
		expect(result.current.isListening).toBe(false);
	});

	it("handles startRecording and stopRecording using MediaRecorder mock", async () => {
		const mockTracks = [{ stop: vi.fn() }];
		const mockStream = {
			getTracks: () => mockTracks,
		};

		const mockMediaRecorder = {
			start: vi.fn(),
			stop: vi.fn(function (this: { onstop?: () => void; addEventListener?: (event: string, cb: () => void) => void }) {
				if (this.onstop) this.onstop();
			}),
			ondataavailable: null as ((e: { data: Blob }) => void) | null,
			onstop: null as (() => void) | null,
			addEventListener: vi.fn((event: string, cb: () => void) => {
				if (event === "stop") cb();
			}),
			state: "recording",
			mimeType: "audio/webm",
		};

		const originalMediaDevices = navigator.mediaDevices;
		const originalMediaRecorder = window.MediaRecorder;

		Object.defineProperty(navigator, "mediaDevices", {
			value: {
				getUserMedia: vi.fn().mockResolvedValue(mockStream),
			},
			configurable: true,
		});

		(window as unknown as { MediaRecorder: unknown }).MediaRecorder = vi.fn().mockImplementation(function () {
			return mockMediaRecorder;
		});

		const { result } = renderHook(() => useVoiceControl());

		await act(async () => {
			await result.current.startRecording();
		});

		expect(result.current.isRecording).toBe(true);

		await act(async () => {
			await result.current.stopRecording();
		});

		expect(result.current.isRecording).toBe(false);

		// Restore
		Object.defineProperty(navigator, "mediaDevices", {
			value: originalMediaDevices,
			configurable: true,
		});
		(window as unknown as { MediaRecorder: unknown }).MediaRecorder = originalMediaRecorder;
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
