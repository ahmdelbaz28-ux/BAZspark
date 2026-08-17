import {
	Cpu,
	Loader,
	Mic,
	MicOff,
	Plus,
	Send,
	Server,
	Settings,
	Trash2,
	Zap,
} from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useLlmChat } from "@/hooks/useLlmChat";
import { useVoiceControl } from "@/hooks/useVoiceControl";

const QUICK_COMMANDS = [
	"فحص الامتثال",
	"حساب الحمل",
	"دراسة القوس الكهربائي",
	"تحديد حجم الكابل",
	"تحليل التيار القصير",
	"دراسة التنسيق",
	"إنشاء مخطط",
	"تصدير التقرير",
] as const;

function getStatusClass(isConnected: boolean, hasError: boolean): string {
	if (isConnected) return "text-emerald-500";
	if (hasError) return "text-destructive";
	return "text-muted-foreground";
}

function getStatusDotClass(isConnected: boolean, hasError: boolean): string {
	if (isConnected) return "w-1.5 h-1.5 rounded-full bg-emerald-500";
	if (hasError) return "w-1.5 h-1.5 rounded-full bg-destructive";
	return "w-1.5 h-1.5 rounded-full bg-muted-foreground animate-pulse";
}

function getStatusText(loading: boolean, hasError: boolean): string {
	if (loading) return "Connecting...";
	if (hasError) return "Offline";
	return "Connected";
}

function getInputPlaceholder(isListening: boolean, isArabic: boolean): string {
	if (!isListening) return "اكتب سؤالاً أو أمراً...";
	return isArabic
		? "جاري الاستماع... (أو اكتب هنا)"
		: "Listening... (or type here)";
}

function getVoiceTitle(isSupported: boolean, isListening: boolean): string {
	if (!isSupported) return "التعرف الصوتي غير مدعوم";
	if (isListening) return "إيقاف الاستماع";
	return "بدء الإدخال الصوتي";
}

export function AgentChatPage() {
	const { i18n } = useTranslation();
	const { messages, loading, error, sendMessage, clearChat } =
		useLlmChat("engineer_assistant");

	const [inputValue, setInputValue] = useState("");
	const scrollAreaRef = useRef<HTMLDivElement>(null);

	const handleSpeechTranscript = useCallback((spokenText: string) => {
		setInputValue((prev) => {
			const cleaned = spokenText.trim();
			return prev ? `${prev} ${cleaned}` : cleaned;
		});
	}, []);

	const {
		isListening,
		startListening,
		stopListening,
		interimTranscript,
		isSupported,
	} = useVoiceControl({
		onTranscript: handleSpeechTranscript,
	});

	const toggleListening = useCallback(() => {
		if (isListening) {
			stopListening();
		} else {
			startListening();
		}
	}, [isListening, startListening, stopListening]);

	useEffect(() => {
		if (scrollAreaRef.current) {
			scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight;
		}
	}, [messages]);

	const handleSendMessage = (e: React.FormEvent) => {
		e.preventDefault();
		if (!inputValue.trim() || loading) return;
		const content = inputValue;
		setInputValue("");
		void sendMessage(content);
	};

	const isConnected = !loading && !error;
	const isArabic = Boolean(i18n.language?.startsWith("ar"));
	const statusTextClass = getStatusClass(isConnected, Boolean(error));
	const statusDotClass = getStatusDotClass(isConnected, Boolean(error));
	const statusText = getStatusText(loading, Boolean(error));
	const inputPlaceholder = getInputPlaceholder(isListening, isArabic);
	const voiceTitle = getVoiceTitle(isSupported, isListening);

	return (
		<div className="h-screen flex flex-col bg-background text-foreground">
			{/* Header */}
			<div className="h-16 border-b border-border flex items-center justify-between px-6 bg-card stagger-card">
				<div className="flex items-center gap-3">
					<div className="w-10 h-10 rounded-lg bg-gradient-to-br from-secondary to-secondary/60 flex items-center justify-center border border-secondary/50">
						<Zap className="h-5 w-5 text-secondary-foreground" />
					</div>
					<div>
						<h1 className="font-semibold text-base text-foreground">
							FireAI Assistant
						</h1>
						<p className="text-xs text-muted-foreground">
							مساعد هندسي ذكي (استشاري — تحقق من المخرجات)
						</p>
					</div>
				</div>
				<div className="flex items-center gap-2">
					<Button
						variant="outline"
						size="icon"
						className="h-9 w-9 border-border hover:bg-muted"
						onClick={clearChat}
						title="مسح المحادثة"
					>
						<Trash2 className="h-4 w-4" />
					</Button>
					<Button
						variant="outline"
						size="icon"
						className="h-9 w-9 border-border hover:bg-muted"
					>
						<Settings className="h-4 w-4" />
					</Button>
				</div>
			</div>

			{/* Chat Area */}
			<ScrollArea className="flex-1 p-6">
				<div className="max-w-3xl mx-auto space-y-6">
					{messages.length === 0 && (
						<div className="text-center py-16">
							<Zap className="h-10 w-10 mx-auto text-secondary/60 mb-4" />
							<p className="text-sm text-muted-foreground">
								ابدأ محادثة مع المساعد الهندسي. المخرجات استشارية وتخضع للتحقق
								من مهندس مرخص.
							</p>
						</div>
					)}

					{messages.map((message, index) => {
						const isUser = message.role === "user";
						const bubbleClass = isUser
							? "bg-secondary/20 text-foreground border border-secondary/30 rounded-br-none"
							: "bg-muted text-foreground border border-border rounded-bl-none";

						return (
							<div
								key={`${message.timestamp}-${index}`}
								className={`flex ${isUser ? "justify-end" : "justify-start"}`}
							>
								{!isUser && (
									<div className="w-8 h-8 rounded bg-secondary/20 flex items-center justify-center border border-secondary/50 shrink-0 mr-3">
										<Zap className="h-4 w-4 text-secondary" />
									</div>
								)}

								<div className={`max-w-md ${isUser ? "order-2 ml-3" : ""}`}>
									<div className={`px-4 py-3 rounded-xl ${bubbleClass}`}>
										<p className="text-sm leading-relaxed whitespace-pre-wrap">
											{message.content}
										</p>
									</div>

									{!isUser && (message.source || message.model) && (
										<div className="flex gap-2 mt-2 flex-wrap">
											{message.source && (
												<Badge
													variant="outline"
													className="text-[10px] text-muted-foreground bg-transparent border-border"
												>
													{message.source}
												</Badge>
											)}
											{message.model && (
												<Badge
													variant="outline"
													className="text-[10px] text-muted-foreground bg-transparent border-border"
												>
													{message.model}
												</Badge>
											)}
											{message.disclaimer && (
												<p className="text-[10px] leading-relaxed text-muted-foreground mt-1 w-full">
													{message.disclaimer}
												</p>
											)}
										</div>
									)}
								</div>
							</div>
						);
					})}

					{loading && (
						<div className="flex justify-start">
							<div className="w-8 h-8 rounded bg-secondary/20 flex items-center justify-center border border-secondary/50 shrink-0 mr-3">
								<Loader className="h-4 w-4 text-secondary animate-spin" />
							</div>
							<div className="bg-muted text-foreground border border-border px-4 py-3 rounded-xl rounded-bl-none">
								<p className="text-sm">جاري المعالجة...</p>
							</div>
						</div>
					)}

					{error && (
						<div className="flex justify-start">
							<div className="bg-destructive/10 text-destructive border border-destructive/30 px-4 py-3 rounded-xl">
								<p className="text-sm">{error}</p>
							</div>
						</div>
					)}
				</div>
			</ScrollArea>

			{/* Quick Commands */}
			<div className="px-6 py-4 border-t border-border bg-card/50 stagger-card">
				<p className="text-xs text-muted-foreground mb-3 font-medium">
					الأوامر السريعة:
				</p>
				<div className="flex flex-wrap gap-2">
					{QUICK_COMMANDS.map((cmd) => (
						<Badge
							key={cmd}
							variant="outline"
							className="bg-muted border-border hover:bg-secondary/20 hover:text-secondary hover:border-secondary/50 cursor-pointer py-1.5 px-3"
							onClick={() => setInputValue(cmd)}
						>
							{cmd}
						</Badge>
					))}
				</div>
			</div>

			{/* Input Area */}
			<div className="border-t border-border p-4 bg-card stagger-card">
				{isListening && (
					<div className="max-w-3xl mx-auto mb-3 px-3.5 py-2 rounded-lg bg-secondary/10 border border-secondary/30 text-xs text-secondary flex items-center gap-2 animate-pulse">
						<Mic className="h-3.5 w-3.5 animate-bounce flex-shrink-0" />
						<span className="truncate">
							{interimTranscript ||
								(isArabic
									? "جاري الاستماع... تحدث الآن..."
									: "Listening... Speak now...")}
						</span>
					</div>
				)}
				<form onSubmit={handleSendMessage} className="max-w-3xl mx-auto">
					<div className="relative flex items-center gap-2">
						<Button
							type="button"
							size="icon"
							variant="ghost"
							className="h-10 w-10 text-muted-foreground hover:text-foreground"
						>
							<Plus className="h-4 w-4" />
						</Button>

						<Input
							value={inputValue}
							onChange={(e) => setInputValue(e.target.value)}
							placeholder={inputPlaceholder}
							className="bg-muted border-border flex-1 h-10 rounded-full px-4"
							disabled={loading}
						/>

						<Button
							type="button"
							size="icon"
							variant="ghost"
							className={`h-10 w-10 transition-colors ${
								isListening
									? "text-secondary bg-secondary/20 hover:bg-secondary/30 animate-pulse"
									: "text-muted-foreground hover:text-foreground"
							}`}
							onClick={toggleListening}
							title={voiceTitle}
						>
							{isListening ? (
								<MicOff className="h-4 w-4 text-secondary" />
							) : (
								<Mic className="h-4 w-4" />
							)}
						</Button>

						<Button
							type="submit"
							size="icon"
							className="h-10 w-10 bg-secondary hover:bg-secondary/90 text-secondary-foreground rounded-full"
							disabled={loading || !inputValue.trim()}
						>
							<Send className="h-4 w-4" />
						</Button>
					</div>
				</form>
			</div>

			{/* Status Bar */}
			<div className="h-8 bg-background border-t border-border flex items-center justify-between px-6 text-[10px] font-mono text-muted-foreground">
				<div className="flex items-center gap-3">
					<span className="flex items-center gap-1">
						<Cpu className="w-3 h-3" /> Expert Mode
					</span>
					<span className="flex items-center gap-1">
						<Server className="w-3 h-3" /> Current Project
					</span>
				</div>
				<div className={`flex items-center gap-1 ${statusTextClass}`}>
					<div className={statusDotClass}></div>
					{statusText}
				</div>
			</div>
		</div>
	);
}
