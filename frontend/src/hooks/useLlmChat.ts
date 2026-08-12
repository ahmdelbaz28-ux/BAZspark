/**
 * useLlmChat.ts - React hook for the AI Copilot LLM chat with SSE streaming.
 *
 * Streams responses token-by-token via POST /api/v1/llm/chat/stream (SSE).
 * Falls back to non-streaming if the stream fails to connect.
 */
import { useCallback, useRef, useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { llmApi } from "@/services/fullApi";

export interface ChatMessage {
	role: "user" | "assistant";
	content: string;
	source?: string;
	model?: string;
	disclaimer?: string;
	timestamp: number;
	isStreaming?: boolean;
}

export type ChatRole =
	| "engineer_assistant"
	| "code_explainer"
	| "narrative_writer";

export interface UseLlmChatResult {
	messages: ChatMessage[];
	loading: boolean;
	error: string | null;
	sendMessage: (content: string) => Promise<void>;
	clearChat: () => void;
}

const BATCH_INTERVAL_MS = 50;
const MAX_HISTORY_TURNS = 10;

/**
 * Hook for AI Copilot chat with SSE streaming.
 * Maintains message history and calls the backend LLM streaming endpoint.
 * Batches streaming updates to reduce GC pressure from rapid array copies.
 *
 * F5a: sends a whitelisted ``role`` (never a free-text system prompt).
 * F5b: sends a bounded history window (last MAX_HISTORY_TURNS completed turns).
 * F4: persists the server-provided disclaimer on the assistant message.
 */
export function useLlmChat(
	role: ChatRole = "engineer_assistant",
): UseLlmChatResult {
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const { toast } = useToast();
	const abortRef = useRef<AbortController | null>(null);
	const streamBufferRef = useRef("");
	const batchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const streamIndexRef = useRef<number>(-1);
	const messagesRef = useRef<ChatMessage[]>([]); // H-12 FIX: ref for stable history reference

	const flushBuffer = useCallback(() => {
		const buffer = streamBufferRef.current;
		if (!buffer || streamIndexRef.current < 0) return;
		const idx = streamIndexRef.current;
		streamBufferRef.current = "";
		setMessages((prev) => {
			const updated = [...prev];
			const lastMsg = updated[idx];
			if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
				updated[idx] = { ...lastMsg, content: lastMsg.content + buffer };
			}
			messagesRef.current = updated;
			return updated;
		});
	}, []);

	const sendMessage = useCallback(
		async (content: string) => {
			if (!content.trim() || loading) return;

			if (abortRef.current) {
				abortRef.current.abort();
			}
			if (batchTimerRef.current) {
				clearTimeout(batchTimerRef.current);
				batchTimerRef.current = null;
			}

			const controller = new AbortController();
			abortRef.current = controller;

			const userMessage: ChatMessage = {
				role: "user",
				content: content.trim(),
				timestamp: Date.now(),
			};

			const assistantTimestamp = Date.now();
			const assistantMessage: ChatMessage = {
				role: "assistant",
				content: "",
				timestamp: assistantTimestamp,
				isStreaming: true,
			};
			setMessages((prev) => {
				streamIndexRef.current = prev.length + 1;
				const updated = [...prev, userMessage, assistantMessage];
				messagesRef.current = updated;
				return updated;
			});
			setLoading(true);
			setError(null);
			streamBufferRef.current = "";

			// F5b: bounded history window — last MAX_HISTORY_TURNS
			// completed turns (oldest first, server also caps at 20).
			// Use messagesRef (ref) instead of state for history because:
			// the history must be stable across renders — streaming updates
			// append chunks to the last message without causing re-renders
			// of the entire history array.
			const history = messagesRef.current
				.filter((m) => m.content)
				.slice(-MAX_HISTORY_TURNS)
				.map((m) => ({ role: m.role, content: m.content }));

			try {
				await llmApi.chatStream(
					{
						prompt: content.trim(),
						role,
						history: history.length > 0 ? history : undefined,
						temperature: 0.1,
						max_tokens: 1500,
					},
					controller.signal,
					// onChunk — buffer and batch updates
					(chunk: string) => {
						streamBufferRef.current += chunk;
						if (!batchTimerRef.current) {
							batchTimerRef.current = setTimeout(() => {
								batchTimerRef.current = null;
								flushBuffer();
							}, BATCH_INTERVAL_MS);
						}
					},
					// onDone — flush remaining buffer and finalize
					(done: {
						content: string;
						model: string;
						source: string;
						disclaimer?: string;
					}) => {
						if (batchTimerRef.current) {
							clearTimeout(batchTimerRef.current);
							batchTimerRef.current = null;
						}
						flushBuffer();
						setMessages((prev) => {
							const updated = [...prev];
							const lastMsg = updated.at(-1);
							if (lastMsg && lastMsg.role === "assistant") {
								updated[updated.length - 1] = {
									...lastMsg,
									content: done.content || lastMsg.content,
									model: done.model,
									source: done.source,
									disclaimer: done.disclaimer,
									isStreaming: false,
								};
							}
							messagesRef.current = updated;
							return updated;
						});
						streamIndexRef.current = -1;
					},
					// onError — mark message as error
					(errMsg: string) => {
						if (batchTimerRef.current) {
							clearTimeout(batchTimerRef.current);
							batchTimerRef.current = null;
						}
						streamBufferRef.current = "";
						streamIndexRef.current = -1;
						setMessages((prev) => {
							const updated = [...prev];
							const lastMsg = updated.at(-1);
							if (
								lastMsg &&
								lastMsg.role === "assistant" &&
								lastMsg.isStreaming
							) {
								updated[updated.length - 1] = {
									...lastMsg,
									content: lastMsg.content || `(Error: ${errMsg})`,
									isStreaming: false,
								};
							}
							messagesRef.current = updated;
							return updated;
						});
						setError(errMsg);
						toast({
							title: "AI Error",
							description: errMsg,
							variant: "destructive",
						});
					},
				);
			} catch (err: unknown) {
				if (controller.signal.aborted) return;
				const msg =
					err instanceof Error ? err.message : "Failed to get AI response";
				setError(msg);
				setMessages((prev) => {
					const updated = prev.slice(0, -1);
					messagesRef.current = updated;
					return updated;
				});
				toast({
					title: "AI Error",
					description: msg,
					variant: "destructive",
				});
			} finally {
				if (batchTimerRef.current) {
					clearTimeout(batchTimerRef.current);
					batchTimerRef.current = null;
				}
				streamBufferRef.current = "";
				streamIndexRef.current = -1;
				if (abortRef.current === controller) {
					abortRef.current = null;
				}
				setLoading(false);
			}
		},
		[loading, role, toast, flushBuffer],
	);

	const clearChat = useCallback(() => {
		if (abortRef.current) {
			abortRef.current.abort();
		}
		if (batchTimerRef.current) {
			clearTimeout(batchTimerRef.current);
			batchTimerRef.current = null;
		}
		streamBufferRef.current = "";
		streamIndexRef.current = -1;
		setMessages([]);
		messagesRef.current = []; // sync ref
		setError(null);
	}, []);

	return { messages, loading, error, sendMessage, clearChat };
}
