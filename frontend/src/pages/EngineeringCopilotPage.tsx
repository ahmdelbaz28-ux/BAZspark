/**
 * EngineeringCopilotPage.tsx — Engineering AI Copilot Chat.
 *
 * AI-powered engineering assistant that answers questions about
 * NFPA 72, NEC, building codes, and fire safety design.
 *
 * Backend: POST /engineering-copilot/chat, /engineering-copilot/translate
 */
import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  Bot,
  Send,
  Loader2,
  User,
  AlertTriangle,
  Trash2,
} from "lucide-react";

const COPILOT_API =
  import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL.replace(/\/api\/v1\/?$/, "")}/engineering-copilot`
    : "/engineering-copilot";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

interface ChatResponse {
  response: string;
  sources?: string[];
  model?: string;
}

export const EngineeringCopilotPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! I'm the Engineering Copilot. I can help with NFPA 72, NEC, building codes, and fire safety design questions. What would you like to know?",
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      const res = await fetch(`${COPILOT_API}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ request: message }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json() as Promise<ChatResponse>;
    },
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.response,
          timestamp: new Date(),
        },
      ]);
    },
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text) return;
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", content: text, timestamp: new Date() },
    ]);
    setInput("");
    chatMutation.mutate(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content:
          "Hello! I'm the Engineering Copilot. I can help with NFPA 72, NEC, building codes, and fire safety design questions. What would you like to know?",
        timestamp: new Date(),
      },
    ]);
    chatMutation.reset();
  };

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-4xl mx-auto h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
              <Bot className="h-6 w-6 text-cyan-400" />
              Engineering Copilot
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              AI-powered engineering assistant for fire safety and building
              code questions
            </p>
          </div>
          <button
            type="button"
            onClick={clearChat}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs text-slate-400 hover:text-red-400 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear Chat
          </button>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 pr-2 mb-4 min-h-0">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start gap-3 ${
                msg.role === "user" ? "flex-row-reverse" : ""
              }`}
            >
              <div
                className={`p-2 rounded-lg flex-shrink-0 ${
                  msg.role === "user"
                    ? "bg-cyan-600 text-white"
                    : "bg-slate-700 text-slate-300"
                }`}
              >
                {msg.role === "user" ? (
                  <User className="h-4 w-4" />
                ) : (
                  <Bot className="h-4 w-4" />
                )}
              </div>
              <div
                className={`max-w-[80%] rounded-xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-cyan-600/20 border border-cyan-500/20"
                    : "bg-slate-800/50 border border-slate-700"
                }`}
              >
                <p className="text-sm text-slate-200 whitespace-pre-wrap">
                  {msg.content}
                </p>
                <p className="text-[10px] text-slate-600 mt-1.5">
                  {msg.timestamp.toLocaleTimeString()}
                </p>
              </div>
            </div>
          ))}

          {chatMutation.isPending && (
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-slate-700 text-slate-300 flex-shrink-0">
                <Bot className="h-4 w-4" />
              </div>
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3">
                <div className="flex items-center gap-2 text-slate-400 text-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Thinking...
                </div>
              </div>
            </div>
          )}

          {chatMutation.isError && (
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-red-600/20 text-red-400 flex-shrink-0">
                <AlertTriangle className="h-4 w-4" />
              </div>
              <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3">
                <p className="text-red-400 text-sm">
                  {chatMutation.error instanceof Error
                    ? chatMutation.error.message
                    : "Failed to get response"}
                </p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-3">
          <div className="flex items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about NFPA 72, NEC, fire safety design..."
              rows={2}
              className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none resize-none"
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || chatMutation.isPending}
              className="p-2.5 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white rounded-lg transition-colors flex-shrink-0"
            >
              {chatMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </div>
          <p className="text-[10px] text-slate-600 mt-2">
            Responses are AI-generated. Always verify critical code
            requirements against official NFPA/NEC publications.
          </p>
        </div>
      </div>
    </div>
  );
};

export default EngineeringCopilotPage;
