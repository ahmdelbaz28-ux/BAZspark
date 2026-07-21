/**
 * useLlmChat.ts - React hook for the AI Copilot LLM chat with SSE streaming.
 *
 * Streams responses token-by-token via POST /api/v1/llm/chat/stream (SSE).
 * Falls back to non-streaming if the stream fails to connect.
 */
import { useCallback, useRef, useState } from "react";
import { llmApi } from "@/services/fullApi";
import { useToast } from "@/hooks/use-toast";

export interface ChatMessage {
	role: "user" | "assistant";
	content: string;
	source?: string;
	model?: string;
	timestamp: number;
	isStreaming?: boolean;
}

export interface UseLlmChatResult {
	messages: ChatMessage[];
	loading: boolean;
	error: string | null;
	sendMessage: (content: string) => Promise<void>;
	clearChat: () => void;
}

const BATCH_INTERVAL_MS = 50;

/**
 * Hook for AI Copilot chat with SSE streaming.
 * Maintains message history and calls the backend LLM streaming endpoint.
 * Batches streaming updates to reduce GC pressure from rapid array copies.
 */
export function useLlmChat(systemPrompt?: string): UseLlmChatResult {
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const { toast } = useToast();
	const abortRef = useRef<AbortController | null>(null);
	const streamBufferRef = useRef("");
	const batchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	const streamIndexRef = useRef<number>(-1);

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
			setMessages((prev) => {
				streamIndexRef.current = prev.length + 1;
				return [
					...prev,
					userMessage,
					{
						role: "assistant",
						content: "",
						timestamp: assistantTimestamp,
						isStreaming: true,
					},
				];
			});
			setLoading(true);
			setError(null);
			streamBufferRef.current = "";

			try {
				await llmApi.chatStream(
					{
						prompt: content.trim(),
						system: systemPrompt,
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
					(done: { content: string; model: string; source: string }) => {
						if (batchTimerRef.current) {
							clearTimeout(batchTimerRef.current);
							batchTimerRef.current = null;
						}
						flushBuffer();
						setMessages((prev) => {
							const updated = [...prev];
							const lastMsg = updated[updated.length - 1];
							if (lastMsg && lastMsg.role === "assistant") {
								updated[updated.length - 1] = {
									...lastMsg,
									content: done.content || lastMsg.content,
									model: done.model,
									source: done.source,
									isStreaming: false,
								};
							}
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
							const lastMsg = updated[updated.length - 1];
							if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
								updated[updated.length - 1] = {
									...lastMsg,
									content: lastMsg.content || `(Error: ${errMsg})`,
									isStreaming: false,
								};
							}
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
					const last = prev[prev.length - 1];
					if (last && last.role === "assistant" && last.isStreaming && !last.content) {
						return prev.slice(0, -1);
					}
					return prev;
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
		[loading, systemPrompt, toast, flushBuffer],
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
		setError(null);
	}, []);

	return { messages, loading, error, sendMessage, clearChat };
}
