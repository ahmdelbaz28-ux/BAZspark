/**
 * EngineeringCopilotPage.tsx — Engineering AI Copilot Chat.
 *
 * AI-powered engineering assistant that answers questions about
 * NFPA 72, NEC, building codes, and fire safety design.
 *
 * Backend: POST /engineering-copilot/chat, /engineering-copilot/translate
 */

import { useMutation } from "@tanstack/react-query";
import {
	AlertTriangle,
	ArrowRightLeft,
	Bot,
	FileOutput,
	FileText,
	Heart,
	Info,
	List,
	Loader2,
	PlusCircle,
	Send,
	ShieldCheck,
	Trash2,
	User,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import {
	copilotApi,
	copilotExtendedApi,
	llmExtendedApi,
} from "@/services/fullApi";

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

// ── Entity creation form state ──
interface EntityForm {
	name: string;
	entity_type: string;
	description: string;
	x: string;
	y: string;
	z: string;
}

const ENTITY_TYPES = [
	"Panel",
	"Transformer",
	"Bus",
	"Cable",
	"Breaker",
	"Load",
	"Generator",
	"Equipment",
];

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
	const [extResult, setExtResult] = useState<Record<string, unknown> | null>(
		null,
	);
	const [extLoading, setExtLoading] = useState(false);
	const [capabilitiesResult, setCapabilitiesResult] = useState<Record<
		string,
		unknown
	> | null>(null);
	const [healthResult, setHealthResult] = useState<Record<
		string,
		unknown
	> | null>(null);
	const [showEntityForm, setShowEntityForm] = useState(false);
	const [entityForm, setEntityForm] = useState<EntityForm>({
		name: "",
		entity_type: "Panel",
		description: "",
		x: "0",
		y: "0",
		z: "0",
	});
	const [entityLoading, setEntityLoading] = useState(false);

	const handleListModels = async () => {
		setExtLoading(true);
		try {
			const res = await llmExtendedApi.getModels();
			setExtResult(res as Record<string, unknown>);
		} catch (err) {
			// silent
		} finally {
			setExtLoading(false);
		}
	};

	const handleComplianceNarrative = async () => {
		setExtLoading(true);
		try {
			const res = await llmExtendedApi.complianceNarrative({
				calculation_type: "voltage_drop",
				calculation_result: { drop_pct: 3.2 },
			});
			setExtResult(res as Record<string, unknown>);
		} catch (err) {
			// silent
		} finally {
			setExtLoading(false);
		}
	};

	const handleTranslateModel = async () => {
		setExtLoading(true);
		try {
			const res = await copilotExtendedApi.translateModel({
				source_format: "ifc",
				target_format: "revit",
				model_data: {},
			});
			setExtResult(res as Record<string, unknown>);
		} catch (err) {
			// silent
		} finally {
			setExtLoading(false);
		}
	};

	const handleValidateModel = async () => {
		setExtLoading(true);
		try {
			const res = await copilotExtendedApi.validateModel({
				model_data: {},
				standard: "NFPA 72",
			});
			setExtResult(res as Record<string, unknown>);
		} catch (err) {
			// silent
		} finally {
			setExtLoading(false);
		}
	};

	const handleGenerateReports = async () => {
		setExtLoading(true);
		try {
			const res = await copilotExtendedApi.generateReports({});
			setExtResult(res as Record<string, unknown>);
		} catch (err) {
			// silent
		} finally {
			setExtLoading(false);
		}
	};

	const handleGetCapabilities = async () => {
		setExtLoading(true);
		try {
			const data = await copilotApi.getCapabilities();
			setCapabilitiesResult(data as Record<string, unknown>);
		} catch (err) {
			// silent
		} finally {
			setExtLoading(false);
		}
	};

	const handleHealthCheck = async () => {
		setExtLoading(true);
		try {
			const data = await copilotApi.getHealth();
			setHealthResult(data as Record<string, unknown>);
		} catch (err) {
			// silent
		} finally {
			setExtLoading(false);
		}
	};

	const handleCreateEntity = async () => {
		if (!entityForm.name.trim()) return;
		setEntityLoading(true);
		try {
			const data = await copilotApi.createEntity({
				name: entityForm.name,
				entity_type: entityForm.entity_type,
				description: entityForm.description,
				coordinates: {
					x: Number.parseFloat(entityForm.x) || 0,
					y: Number.parseFloat(entityForm.y) || 0,
					z: Number.parseFloat(entityForm.z) || 0,
				},
				properties: {},
			});
			setExtResult(data as Record<string, unknown>);
			setShowEntityForm(false);
		} catch (err) {
			// silent
		} finally {
			setEntityLoading(false);
		}
	};

	const [input, setInput] = useState("");
	const messagesEndRef = useRef<HTMLDivElement>(null);

	const chatMutation = useMutation({
		mutationFn: async (message: string) => {
			const res = await copilotApi.chat({ request: message });
			return res as ChatResponse;
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
			{
				id: `user-${Date.now()}`,
				role: "user",
				content: text,
				timestamp: new Date(),
			},
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
							AI-powered engineering assistant for fire safety and building code
							questions
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

				{/* Extended Operations */}
				<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4 mb-4">
					<h3 className="text-sm font-semibold text-slate-200 mb-3">
						Extended Operations
					</h3>
					<div className="flex flex-wrap gap-2">
						<button
							type="button"
							onClick={handleListModels}
							disabled={extLoading}
							className="inline-flex items-center gap-1.5 px-3 py-2 text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
						>
							{extLoading ? (
								<Loader2 className="h-3.5 w-3.5 animate-spin" />
							) : (
								<List className="h-3.5 w-3.5" />
							)}
							List Models
						</button>
						<button
							type="button"
							onClick={handleComplianceNarrative}
							disabled={extLoading}
							className="inline-flex items-center gap-1.5 px-3 py-2 text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
						>
							{extLoading ? (
								<Loader2 className="h-3.5 w-3.5 animate-spin" />
							) : (
								<FileText className="h-3.5 w-3.5" />
							)}
							Compliance Narrative
						</button>
						<button
							type="button"
							onClick={handleTranslateModel}
							disabled={extLoading}
							className="inline-flex items-center gap-1.5 px-3 py-2 text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
						>
							{extLoading ? (
								<Loader2 className="h-3.5 w-3.5 animate-spin" />
							) : (
								<ArrowRightLeft className="h-3.5 w-3.5" />
							)}
							Translate Model
						</button>
						<button
							type="button"
							onClick={handleValidateModel}
							disabled={extLoading}
							className="inline-flex items-center gap-1.5 px-3 py-2 text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
						>
							{extLoading ? (
								<Loader2 className="h-3.5 w-3.5 animate-spin" />
							) : (
								<ShieldCheck className="h-3.5 w-3.5" />
							)}
							Validate Model
						</button>
						<button
							type="button"
							onClick={handleGenerateReports}
							disabled={extLoading}
							className="inline-flex items-center gap-1.5 px-3 py-2 text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
						>
							{extLoading ? (
								<Loader2 className="h-3.5 w-3.5 animate-spin" />
							) : (
								<FileOutput className="h-3.5 w-3.5" />
							)}
							Generate Reports
						</button>
						<button
							type="button"
							onClick={handleGetCapabilities}
							disabled={extLoading}
							className="inline-flex items-center gap-1.5 px-3 py-2 text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
						>
							{extLoading ? (
								<Loader2 className="h-3.5 w-3.5 animate-spin" />
							) : (
								<Info className="h-3.5 w-3.5" />
							)}
							Capabilities
						</button>
						<button
							type="button"
							onClick={() => setShowEntityForm(!showEntityForm)}
							disabled={extLoading}
							className="inline-flex items-center gap-1.5 px-3 py-2 text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
						>
							{extLoading ? (
								<Loader2 className="h-3.5 w-3.5 animate-spin" />
							) : (
								<PlusCircle className="h-3.5 w-3.5" />
							)}
							Create Entity
						</button>
						<button
							type="button"
							onClick={handleHealthCheck}
							disabled={extLoading}
							className="inline-flex items-center gap-1.5 px-3 py-2 text-xs text-slate-300 bg-slate-700/50 hover:bg-slate-700 rounded-lg transition-colors disabled:opacity-50"
						>
							{extLoading ? (
								<Loader2 className="h-3.5 w-3.5 animate-spin" />
							) : (
								<Heart className="h-3.5 w-3.5" />
							)}
							Health
						</button>
					</div>
					{extResult && (
						<pre className="mt-3 text-xs font-mono text-slate-400 bg-slate-900 p-3 rounded-lg overflow-auto max-h-48">
							{JSON.stringify(extResult, null, 2)}
						</pre>
					)}
					{capabilitiesResult && (
						<div className="mt-3">
							<h4 className="text-xs font-semibold text-slate-300 mb-2">
								Copilot Capabilities
							</h4>
							<pre className="text-xs font-mono text-slate-400 bg-slate-900 p-3 rounded-lg overflow-auto max-h-48">
								{JSON.stringify(capabilitiesResult, null, 2)}
							</pre>
							<button
								type="button"
								onClick={() => setCapabilitiesResult(null)}
								className="mt-1 text-xs text-slate-500 hover:text-slate-300"
							>
								Close
							</button>
						</div>
					)}
					{healthResult && (
						<div className="mt-3">
							<h4 className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5">
								<Heart className="h-3 w-3 text-emerald-400" />
								Copilot Health Status
							</h4>
							<pre className="text-xs font-mono text-slate-400 bg-slate-900 p-3 rounded-lg overflow-auto max-h-48">
								{JSON.stringify(healthResult, null, 2)}
							</pre>
							<button
								type="button"
								onClick={() => setHealthResult(null)}
								className="mt-1 text-xs text-slate-500 hover:text-slate-300"
							>
								Close
							</button>
						</div>
					)}
					{showEntityForm && (
						<div className="mt-3 bg-slate-900/50 border border-slate-600 rounded-lg p-3">
							<h4 className="text-xs font-semibold text-slate-300 mb-2">
								Create Engineering Entity
							</h4>
							<div className="grid grid-cols-2 gap-2">
								<input
									type="text"
									placeholder="Entity name"
									value={entityForm.name}
									onChange={(e) =>
										setEntityForm({ ...entityForm, name: e.target.value })
									}
									className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-slate-100"
								/>
								<select
									value={entityForm.entity_type}
									onChange={(e) =>
										setEntityForm({
											...entityForm,
											entity_type: e.target.value,
										})
									}
									className="bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-slate-100"
								>
									{ENTITY_TYPES.map((t) => (
										<option key={t} value={t}>
											{t}
										</option>
									))}
								</select>
								<input
									type="text"
									placeholder="Description"
									value={entityForm.description}
									onChange={(e) =>
										setEntityForm({
											...entityForm,
											description: e.target.value,
										})
									}
									className="col-span-2 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-slate-100"
								/>
								<div className="col-span-2 flex gap-2">
									<input
										type="text"
										placeholder="X"
										value={entityForm.x}
										onChange={(e) =>
											setEntityForm({ ...entityForm, x: e.target.value })
										}
										className="w-16 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-slate-100"
									/>
									<input
										type="text"
										placeholder="Y"
										value={entityForm.y}
										onChange={(e) =>
											setEntityForm({ ...entityForm, y: e.target.value })
										}
										className="w-16 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-slate-100"
									/>
									<input
										type="text"
										placeholder="Z"
										value={entityForm.z}
										onChange={(e) =>
											setEntityForm({ ...entityForm, z: e.target.value })
										}
										className="w-16 bg-slate-700 border border-slate-600 rounded px-2 py-1 text-xs text-slate-100"
									/>
									<button
										type="button"
										onClick={handleCreateEntity}
										disabled={entityLoading || !entityForm.name.trim()}
										className="ml-auto px-3 py-1 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-xs rounded transition-colors"
									>
										{entityLoading ? (
											<Loader2 className="h-3 w-3 animate-spin" />
										) : (
											"Create"
										)}
									</button>
								</div>
							</div>
						</div>
					)}
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
							aria-label="Send"
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
						Responses are AI-generated. Always verify critical code requirements
						against official NFPA/NEC publications.
					</p>
				</div>
			</div>
		</div>
	);
};

export default EngineeringCopilotPage;
