/**
 * useLlmChat.ts - React hook for the AI Copilot LLM chat.
 *
 * Manages chat message history, loading state, and error handling for
 * POST /api/v1/llm/chat calls. Mirrors the useCreateProject mutation
 * pattern from useApi.ts.
 */
import { useCallback, useRef, useState } from "react";
import { llmApi, type LLMChatResponse } from "@/services/fullApi";
import { useToast } from "@/hooks/use-toast";

export interface ChatMessage {
	role: "user" | "assistant";
	content: string;
	source?: string;
	model?: string;
	timestamp: number;
}

export interface UseLlmChatResult {
	messages: ChatMessage[];
	loading: boolean;
	error: string | null;
	sendMessage: (content: string) => Promise<void>;
	clearChat: () => void;
}

/**
 * Hook for AI Copilot chat. Maintains a local message history and
 * calls the backend LLM service. Errors are surfaced via toast.
 *
 * @param systemPrompt - Optional system prompt to set the AI's persona.
 *   Defaults to a fire-protection engineering assistant persona.
 */
export function useLlmChat(systemPrompt?: string): UseLlmChatResult {
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const { toast } = useToast();
	const abortRef = useRef<AbortController | null>(null);

	const sendMessage = useCallback(
		async (content: string) => {
			if (!content.trim() || loading) return;

			// Abort any in-flight request
			if (abortRef.current) {
				abortRef.current.abort();
			}

			const controller = new AbortController();
			abortRef.current = controller;

			const userMessage: ChatMessage = {
				role: "user",
				content: content.trim(),
				timestamp: Date.now(),
			};
			setMessages((prev) => [...prev, userMessage]);
			setLoading(true);
			setError(null);

			try {
				const result: LLMChatResponse = await llmApi.chat({
					prompt: content.trim(),
					system: systemPrompt,
					temperature: 0.1,
					max_tokens: 1500,
				});

				if (controller.signal.aborted) return;

				const assistantMessage: ChatMessage = {
					role: "assistant",
					content: result.content || "(empty response)",
					source: result.source,
					model: result.model,
					timestamp: Date.now(),
				};
				setMessages((prev) => [...prev, assistantMessage]);
			} catch (err: unknown) {
				if (controller.signal.aborted) return;
				const msg =
					err instanceof Error ? err.message : "Failed to get AI response";
				setError(msg);
				toast({
					title: "AI Error",
					description: msg,
					variant: "destructive",
				});
			} finally {
				if (abortRef.current === controller) {
					abortRef.current = null;
				}
				setLoading(false);
			}
		},
		[loading, systemPrompt, toast],
	);

	const clearChat = useCallback(() => {
		if (abortRef.current) {
			abortRef.current.abort();
		}
		setMessages([]);
		setError(null);
	}, []);

	return { messages, loading, error, sendMessage, clearChat };
}
