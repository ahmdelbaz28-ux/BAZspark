import { useCallback, useEffect, useRef, useState } from "react";
import { actions } from "@/store/simpleStore";

// Web Speech API types — not in all TS DOM lib configurations
interface SpeechRecognitionResult {
	readonly 0: SpeechRecognitionAlternative;
	readonly length: number;
}
interface SpeechRecognitionResultList {
	readonly [index: number]: SpeechRecognitionResult;
	readonly length: number;
}
interface SpeechRecognitionAlternative {
	readonly transcript: string;
	readonly confidence: number;
}
interface SpeechRecognitionEvent {
	readonly results: SpeechRecognitionResultList;
}
interface SpeechRecognitionErrorEvent {
	readonly error: string;
}
interface SpeechRecognition extends EventTarget {
	continuous: boolean;
	interimResults: boolean;
	lang: string;
	onresult: ((event: SpeechRecognitionEvent) => void) | null;
	onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
	onend: (() => void) | null;
	start(): void;
	stop(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognition;

export function useVoiceControl() {
	const [isListening, setIsListening] = useState(false);
	// `recognition` is a ref-like value (used to call .start() / .stop()
	// from event handlers). It does NOT need to trigger re-renders, so we
	// use useRef instead of useState (avoids react-hooks/set-state-in-effect:
	// no setState needed when creating the SpeechRecognition object on mount).
	const recognitionRef = useRef<SpeechRecognition | null>(null);

	useEffect(() => {
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
			const rec = new (
				SpeechRecognitionCtor as unknown as new () => SpeechRecognition
			)();
			rec.continuous = false;
			rec.interimResults = false;
			rec.lang = "en-US"; // English supported mostly

			rec.onresult = (event: SpeechRecognitionEvent) => {
				const transcript = event.results[0][0].transcript.toLowerCase();
				if (import.meta.env.DEV)
					console.log("Voice Command Received:", transcript);

				// Handle commands
				if (transcript.includes("add generator")) {
					actions.addElement({
						id: `gen-${Date.now()}`,
						type: "generator",
						x: 100,
						y: 100,
						voltage: 11000,
					});
				} else if (transcript.includes("add battery")) {
					actions.addElement({
						id: `bat-${Date.now()}`,
						type: "battery",
						x: 200,
						y: 200,
						voltage: 220,
					});
				} else if (transcript.includes("add panel")) {
					actions.addElement({
						id: `pan-${Date.now()}`,
						type: "panel",
						x: 300,
						y: 300,
						voltage: 220,
					});
				} else if (transcript.includes("clear errors")) {
					actions.clearErrors();
				} else {
					actions.pushError({
						message: `Unknown voice command: "${transcript}"`,
					});
				}

				setIsListening(false);
				actions.setVoiceActive(false);
			};

			rec.onerror = (event: SpeechRecognitionErrorEvent) => {
				if (import.meta.env.DEV)
					console.error("Speech recognition error", event.error);
				setIsListening(false);
				actions.setVoiceActive(false);
				actions.pushError({
					message: `Speech recognition error: ${event.error}`,
				});
			};

			rec.onend = () => {
				setIsListening(false);
				actions.setVoiceActive(false);
			};

			recognitionRef.current = rec;
		}
	}, []);

	const startListening = useCallback(() => {
		const recognition = recognitionRef.current;
		if (recognition) {
			try {
				recognition.start();
				setIsListening(true);
				actions.setVoiceActive(true);
			} catch (e) {
				if (import.meta.env.DEV)
					console.error("Failed to start recognition", e);
			}
		} else {
			actions.pushError({
				message: "Speech Recognition not supported in this browser.",
			});
		}
	}, []);

	const stopListening = useCallback(() => {
		const recognition = recognitionRef.current;
		if (recognition) {
			recognition.stop();
			setIsListening(false);
			actions.setVoiceActive(false);
		}
	}, []);

	return { isListening, startListening, stopListening };
}
