/**
 * useVoiceControl.ts - Bilingual Voice Recognition & Speech Control Hook.
 *
 * Provides production-grade speech-to-text recognition with:
 * - Dynamic i18n locale binding ('ar-EG' for Arabic, 'en-US' for English)
 * - Bilingual workspace and AI command matching (Arabic + English)
 * - Accessible toast notifications on permission denial and network issues
 * - Cross-browser fallback detection and standard MediaRecorder API support
 * - Input text sanitization against injection attacks
 * - 100% backward compatibility for existing store and page consumers
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "@/hooks/use-toast";
import i18n from "@/i18n";
import { actions } from "@/store/simpleStore";

// Web Speech API interfaces
export interface SpeechRecognitionAlternative {
	readonly transcript: string;
	readonly confidence: number;
}

export interface SpeechRecognitionResult {
	readonly 0: SpeechRecognitionAlternative;
	readonly length: number;
	readonly isFinal?: boolean;
	item?(index: number): SpeechRecognitionAlternative;
}

export interface SpeechRecognitionResultList {
	readonly [index: number]: SpeechRecognitionResult;
	readonly length: number;
	item?(index: number): SpeechRecognitionResult;
}

export interface SpeechRecognitionEvent {
	readonly resultIndex?: number;
	readonly results: SpeechRecognitionResultList;
}

export interface SpeechRecognitionErrorEvent {
	readonly error: string;
	readonly message?: string;
}

export interface SpeechRecognitionInstance extends EventTarget {
	continuous: boolean;
	interimResults: boolean;
	lang: string;
	onresult: ((event: SpeechRecognitionEvent) => void) | null;
	onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
	onend: (() => void) | null;
	onstart: (() => void) | null;
	start(): void;
	stop(): void;
	abort(): void;
}

export type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

export interface VoiceControlOptions {
	readonly onCommand?: (command: string, transcript: string) => void;
	readonly onTranscript?: (transcript: string) => void;
	readonly onInterim?: (interim: string) => void;
	readonly onError?: (error: string) => void;
	readonly lang?: string;
	readonly continuous?: boolean;
	readonly interimResults?: boolean;
}

export interface VoiceControlReturn {
	readonly isListening: boolean;
	readonly isRecording: boolean;
	readonly isSupported: boolean;
	readonly isMediaRecorderSupported: boolean;
	readonly transcript: string;
	readonly interimTranscript: string;
	readonly audioBlob: Blob | null;
	readonly startListening: () => void;
	readonly stopListening: () => void;
	readonly startRecording: () => Promise<void>;
	readonly stopRecording: () => Promise<Blob | null>;
	readonly clearTranscript: () => void;
}

/**
 * Sanitizes voice-transcribed input to prevent command injection,
 * control codes, and malformed characters before ingestion by AI pipelines.
 */
export function sanitizeVoiceInput(raw: string): string {
	if (!raw) return "";
	return raw
		.replace(/[\u0000-\u001F\u007F-\u009F]/g, "") // strip control characters
		.replace(/[`${}\\]/g, " ") // neutralize escape/interpolation chars
		.replace(/\s+/g, " ") // normalize whitespace
		.trim();
}

/**
 * Resolves standard speech recognition locale code based on i18n language.
 */
export function resolveSpeechLocale(lang?: string): string {
	const current = (lang || i18n.language || "en").toLowerCase();
	return current.startsWith("ar") ? "ar-EG" : "en-US";
}

export function useVoiceControl(
	options?: VoiceControlOptions,
): VoiceControlReturn {
	const [isListening, setIsListening] = useState(false);
	const [isRecording, setIsRecording] = useState(false);
	const [transcript, setTranscript] = useState("");
	const [interimTranscript, setInterimTranscript] = useState("");
	const [audioBlob, setAudioBlob] = useState<Blob | null>(null);

	const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
	const mediaRecorderRef = useRef<MediaRecorder | null>(null);
	const audioChunksRef = useRef<Blob[]>([]);
	const mediaStreamRef = useRef<MediaStream | null>(null);
	const optionsRef = useRef<VoiceControlOptions | undefined>(options);

	// Keep optionsRef up to date without re-triggering effects
	useEffect(() => {
		optionsRef.current = options;
	});

	const isSupported =
		typeof window !== "undefined" &&
		Boolean(
			(
				window as unknown as {
					SpeechRecognition?: SpeechRecognitionConstructor;
					webkitSpeechRecognition?: SpeechRecognitionConstructor;
				}
			).SpeechRecognition ||
				(
					window as unknown as {
						webkitSpeechRecognition?: SpeechRecognitionConstructor;
					}
				).webkitSpeechRecognition,
		);

	const isMediaRecorderSupported =
		typeof window !== "undefined" &&
		typeof navigator !== "undefined" &&
		typeof navigator.mediaDevices !== "undefined" &&
		typeof navigator.mediaDevices.getUserMedia === "function" &&
		typeof window.MediaRecorder !== "undefined";

	// Initialize SpeechRecognition
	useEffect(() => {
		if (typeof window === "undefined") return;

		const SpeechRecognitionCtor =
			(
				window as unknown as {
					SpeechRecognition?: SpeechRecognitionConstructor;
				}
			).SpeechRecognition ||
			(
				window as unknown as {
					webkitSpeechRecognition?: SpeechRecognitionConstructor;
				}
			).webkitSpeechRecognition;

		if (SpeechRecognitionCtor) {
			const rec = new SpeechRecognitionCtor();
			rec.continuous = options?.continuous ?? false;
			rec.interimResults = options?.interimResults ?? true;
			rec.lang = resolveSpeechLocale(options?.lang);

			rec.onstart = () => {
				setIsListening(true);
				actions.setVoiceActive(true);
			};

			rec.onresult = (event: SpeechRecognitionEvent) => {
				let finalTranscript = "";
				let currentInterim = "";

				const results = event.results;
				const startIndex = event.resultIndex ?? 0;

				for (let i = startIndex; i < results.length; i++) {
					const result = results[i];
					const text = result[0]?.transcript || "";
					if (result.isFinal || !rec.interimResults) {
						finalTranscript += text;
					} else {
						currentInterim += text;
					}
				}

				if (currentInterim) {
					const cleanInterim = sanitizeVoiceInput(currentInterim);
					setInterimTranscript(cleanInterim);
					optionsRef.current?.onInterim?.(cleanInterim);
				}

				if (finalTranscript) {
					const cleanFinal = sanitizeVoiceInput(finalTranscript);
					const lower = cleanFinal.toLowerCase();

					setTranscript(cleanFinal);
					setInterimTranscript("");
					optionsRef.current?.onTranscript?.(cleanFinal);

					if (import.meta.env.DEV) {
						console.log("Voice Transcript Received:", cleanFinal);
					}

					// Bilingual Command Matching
					let matchedCommand: string | null = null;

					if (
						lower.includes("add generator") ||
						lower.includes("اضف مولد") ||
						lower.includes("إضافة مولد") ||
						lower.includes("مولد")
					) {
						matchedCommand = "ADD_GENERATOR";
						actions.addElement({
							type: "generator",
							x: 100,
							y: 100,
							voltage: 11000,
						});
					} else if (
						lower.includes("add battery") ||
						lower.includes("اضف بطارية") ||
						lower.includes("إضافة بطارية") ||
						lower.includes("بطارية")
					) {
						matchedCommand = "ADD_BATTERY";
						actions.addElement({
							type: "battery",
							x: 200,
							y: 200,
							voltage: 220,
						});
					} else if (
						lower.includes("add panel") ||
						lower.includes("اضف لوحة") ||
						lower.includes("إضافة لوحة") ||
						lower.includes("لوحة")
					) {
						matchedCommand = "ADD_PANEL";
						actions.addElement({
							type: "panel",
							x: 300,
							y: 300,
							voltage: 220,
						});
					} else if (
						lower.includes("zoom in") ||
						lower.includes("تكبير") ||
						lower.includes("قرب") ||
						lower.includes("زووم ان")
					) {
						matchedCommand = "ZOOM_IN";
					} else if (
						lower.includes("zoom out") ||
						lower.includes("تصغير") ||
						lower.includes("ابعد") ||
						lower.includes("زووم اوت")
					) {
						matchedCommand = "ZOOM_OUT";
					} else if (
						lower.includes("run simulation") ||
						lower.includes("تشغيل المحاكاة") ||
						lower.includes("ابدأ الحسابات") ||
						lower.includes("بدء المحاكاة") ||
						lower.includes("احسب")
					) {
						matchedCommand = "RUN_SIMULATION";
						actions.setDataMode("simulation");
					} else if (
						lower.includes("clear errors") ||
						lower.includes("مسح الاخطاء") ||
						lower.includes("مسح الأخطاء")
					) {
						matchedCommand = "CLEAR_ERRORS";
						actions.clearErrors();
					} else if (
						lower.includes("select") ||
						lower.includes("تحديد") ||
						lower.includes("مسح") ||
						lower.includes("الغاء التحديد") ||
						lower.includes("إلغاء التحديد")
					) {
						matchedCommand = "SELECT_OR_CLEAR";
						if (
							lower.includes("مسح") ||
							lower.includes("الغاء التحديد") ||
							lower.includes("إلغاء التحديد")
						) {
							actions.setSelectedElement(null);
						}
					}

					if (matchedCommand) {
						optionsRef.current?.onCommand?.(matchedCommand, cleanFinal);
					}
				}
			};

			rec.onerror = (event: SpeechRecognitionErrorEvent) => {
				const err = event.error;
				if (import.meta.env.DEV) {
					console.warn("Speech recognition error:", err);
				}
				setIsListening(false);
				actions.setVoiceActive(false);
				optionsRef.current?.onError?.(err);

				const isArabic = (i18n.language || "en").startsWith("ar");

				if (
					err === "not-allowed" ||
					err === "permission-denied" ||
					err === "service-not-allowed"
				) {
					toast({
						title: isArabic
							? "تم رفض إذن الميكروفون"
							: "Microphone Access Denied",
						description: isArabic
							? "يرجى السماح بالوصول إلى الميكروفون في إعدادات المتصفح لاستخدام التحكم الصوتي."
							: "Please enable microphone permissions in your browser settings to use voice control.",
						variant: "destructive",
					});
					actions.pushError({
						message: isArabic
							? "تم رفض إذن الميكروفون في المتصفح"
							: "Microphone permission denied in browser",
					});
				} else if (err === "network") {
					toast({
						title: isArabic ? "خطأ في اتصال الصوت" : "Voice Network Error",
						description: isArabic
							? "تعذر الاتصال بخدمة التعرف على الصوت عبر الشبكة."
							: "Speech recognition service encountered a network error.",
						variant: "destructive",
					});
				} else if (err !== "no-speech") {
					actions.pushError({
						message: `Speech recognition error: ${err}`,
					});
				}
			};

			rec.onend = () => {
				setIsListening(false);
				actions.setVoiceActive(false);
			};

			recognitionRef.current = rec;

			// Handle dynamic i18n language changes
			const handleLanguageChanged = (newLang: string) => {
				if (recognitionRef.current) {
					recognitionRef.current.lang = resolveSpeechLocale(newLang);
				}
			};

			i18n.on("languageChanged", handleLanguageChanged);

			return () => {
				i18n.off("languageChanged", handleLanguageChanged);
				try {
					rec.abort();
				} catch {
					// Ignore abort errors during cleanup
				}
			};
		}
	}, [options?.continuous, options?.interimResults, options?.lang]);

	// Clean up media recorder stream on unmount
	useEffect(() => {
		return () => {
			if (mediaStreamRef.current) {
				mediaStreamRef.current.getTracks().forEach((track) => track.stop());
				mediaStreamRef.current = null;
			}
		};
	}, []);

	const startListening = useCallback(() => {
		const recognition = recognitionRef.current;
		if (recognition) {
			try {
				recognition.lang = resolveSpeechLocale(optionsRef.current?.lang);
				recognition.start();
				setIsListening(true);
				actions.setVoiceActive(true);
			} catch (e) {
				if (import.meta.env.DEV) {
					console.warn("Failed to start recognition, resetting:", e);
				}
				try {
					recognition.stop();
					recognition.start();
					setIsListening(true);
					actions.setVoiceActive(true);
				} catch (retryError) {
					if (import.meta.env.DEV) {
						console.error("Speech recognition start failed:", retryError);
					}
				}
			}
		} else {
			const isArabic = (i18n.language || "en").startsWith("ar");
			toast({
				title: isArabic
					? "التعرف الصوتي غير مدعوم"
					: "Speech Recognition Unavailable",
				description: isArabic
					? "متصفحك لا يدعم Speech Recognition المباشر. يمكنك استخدام تسجيل الصوت كبديل."
					: "Speech Recognition is not natively supported in this browser. MediaRecorder fallback is available.",
				variant: "destructive",
			});
			actions.pushError({
				message: "Speech Recognition not supported in this browser.",
			});
		}
	}, []);

	const stopListening = useCallback(() => {
		const recognition = recognitionRef.current;
		if (recognition) {
			try {
				recognition.stop();
			} catch {
				// Ignore stop errors if already stopped
			}
			setIsListening(false);
			actions.setVoiceActive(false);
		}
	}, []);

	const startRecording = useCallback(async () => {
		if (
			typeof window === "undefined" ||
			typeof navigator === "undefined" ||
			typeof navigator.mediaDevices === "undefined" ||
			typeof navigator.mediaDevices.getUserMedia !== "function"
		) {
			const isArabic = (i18n.language || "en").startsWith("ar");
			toast({
				title: isArabic ? "غير مدعوم" : "Not Supported",
				description: isArabic
					? "تسجيل الصوت غير مدعوم في هذا المتصفح."
					: "Audio recording is not supported in this browser.",
				variant: "destructive",
			});
			return;
		}

		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			mediaStreamRef.current = stream;
			audioChunksRef.current = [];

			const recorder = new MediaRecorder(stream);
			recorder.ondataavailable = (event) => {
				if (event.data && event.data.size > 0) {
					audioChunksRef.current.push(event.data);
				}
			};

			recorder.onstop = () => {
				const blob = new Blob(audioChunksRef.current, {
					type: recorder.mimeType || "audio/webm",
				});
				setAudioBlob(blob);
				stream.getTracks().forEach((track) => track.stop());
				mediaStreamRef.current = null;
			};

			mediaRecorderRef.current = recorder;
			recorder.start();
			setIsRecording(true);
		} catch (e) {
			const isArabic = (i18n.language || "en").startsWith("ar");
			toast({
				title: isArabic ? "خطأ في الميكروفون" : "Microphone Access Error",
				description: isArabic
					? "تعذر بدء تسجيل الصوت. يرجى التحقق من أذونات الميكروفون."
					: "Unable to start audio recording. Please verify microphone permissions.",
				variant: "destructive",
			});
			setIsRecording(false);
		}
	}, []);

	const stopRecording = useCallback((): Promise<Blob | null> => {
		return new Promise((resolve) => {
			const recorder = mediaRecorderRef.current;
			if (!recorder || recorder.state === "inactive") {
				setIsRecording(false);
				resolve(audioBlob);
				return;
			}

			recorder.addEventListener(
				"stop",
				() => {
					const blob = new Blob(audioChunksRef.current, {
						type: recorder.mimeType || "audio/webm",
					});
					setAudioBlob(blob);
					setIsRecording(false);
					resolve(blob);
				},
				{ once: true },
			);

			recorder.stop();
		});
	}, [audioBlob]);

	const clearTranscript = useCallback(() => {
		setTranscript("");
		setInterimTranscript("");
		setAudioBlob(null);
	}, []);

	return {
		isListening,
		isRecording,
		isSupported,
		isMediaRecorderSupported,
		transcript,
		interimTranscript,
		audioBlob,
		startListening,
		stopListening,
		startRecording,
		stopRecording,
		clearTranscript,
	};
}
