import React, { useState, useRef } from "react";
import {
	Box,
	CheckCircle2,
	AlertCircle,
	AlertTriangle,
	FolderOpen,
	Cpu,
	Layers,
	Loader2,
	Play,
	Copy,
	Check,
	FileText,
	Sparkles,
} from "lucide-react";
import { convertSimReady } from "../services/apiSimReady";
import type { SimReadyConvertResponse } from "../types/simready";

export function SimReadyPage() {
	const [sourceFilepath, setSourceFilepath] = useState("");
	const [simreadyProfile, setSimreadyProfile] = useState("Prop-Robotics-Neutral");
	const [propertyAssignment, setPropertyAssignment] = useState<"run" | "skip" | "blocked">("run");
	const [outputRoot, setOutputRoot] = useState("");

	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [result, setResult] = useState<SimReadyConvertResponse | null>(null);
	const [copiedField, setCopiedField] = useState<string | null>(null);

	const fileInputRef = useRef<HTMLInputElement>(null);

	const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (file) {
			// Set file path (in browser environment file.name or relative path)
			// Users can also manually type absolute path
			setSourceFilepath((file as unknown as { path?: string }).path || file.name);
		}
	};

	const handleCopy = (text: string, fieldKey: string) => {
		navigator.clipboard.writeText(text);
		setCopiedField(fieldKey);
		setTimeout(() => setCopiedField(null), 2000);
	};

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		if (!sourceFilepath.trim()) {
			setError("Source File Path is required.");
			return;
		}

		setLoading(true);
		setError(null);
		setResult(null);

		try {
			const res = await convertSimReady({
				source_filepath: sourceFilepath.trim(),
				simready_profile: simreadyProfile,
				property_assignment: propertyAssignment,
				output_root: outputRoot.trim() || undefined,
			});
			setResult(res);
		} catch (err) {
			const msg = err instanceof Error ? err.message : "Failed to execute SimReady conversion.";
			setError(msg);
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="container mx-auto p-4 md:p-6 space-y-8 max-w-6xl">
			{/* Header Section */}
			<div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-border pb-6">
				<div>
					<div className="flex items-center gap-2 text-primary font-semibold mb-1">
						<Sparkles className="w-5 h-5 text-cyan-400 animate-pulse" />
						<span className="text-xs uppercase tracking-wider bg-cyan-950/60 text-cyan-400 px-2.5 py-0.5 rounded-full border border-cyan-800/40">
							NVIDIA Omniverse CAD-to-SimReady
						</span>
					</div>
					<h1 className="text-3xl font-bold tracking-tight text-foreground">
						SimReady Converter
					</h1>
					<p className="text-muted-foreground mt-1 text-sm md:text-base">
						Transform raw 3D CAD models into physics-ready, conformant USD assets for Omniverse simulation.
					</p>
				</div>
			</div>

			{/* Form & Controls Card */}
			<div className="bg-card/80 backdrop-blur-sm border border-border rounded-xl p-6 shadow-xl relative overflow-hidden">
				<div className="absolute -top-24 -right-24 w-48 h-48 bg-primary/10 rounded-full blur-3xl pointer-events-none" />

				<form onSubmit={handleSubmit} className="space-y-6">
					{/* Source File Path */}
					<div className="space-y-2">
						<label htmlFor="source_filepath" className="block text-sm font-medium text-foreground">
							Source File Path <span className="text-destructive">*</span>
						</label>
						<div className="flex gap-2">
							<input
								id="source_filepath"
								type="text"
								value={sourceFilepath}
								onChange={(e) => setSourceFilepath(e.target.value)}
								placeholder="e.g. /path/to/cad_model.gltf or C:\models\robot.fbx"
								className="flex-1 px-4 py-2.5 rounded-lg border border-input bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"
								required
							/>
							<input
								type="file"
								ref={fileInputRef}
								onChange={handleFileSelect}
								className="hidden"
								accept=".gltf,.glb,.fbx,.obj,.stl,.usd,.usda,.usdc,.usdz"
							/>
							<button
								type="button"
								onClick={() => fileInputRef.current?.click()}
								className="px-4 py-2.5 rounded-lg border border-input bg-muted hover:bg-muted/80 text-foreground text-sm font-medium flex items-center gap-2 transition"
								title="Browse local files"
							>
								<FolderOpen className="w-4 h-4 text-cyan-400" />
								Browse
							</button>
						</div>
						<p className="text-xs text-muted-foreground">
							Supports GLTF/GLB, FBX, OBJ, STL, and raw USD formats.
						</p>
					</div>

					{/* Profile & Property Assignment Controls Grid */}
					<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
						{/* SimReady Profile Dropdown */}
						<div className="space-y-2">
							<label htmlFor="simready_profile" className="block text-sm font-medium text-foreground">
								SimReady Profile
							</label>
							<div className="relative">
								<select
									id="simready_profile"
									value={simreadyProfile}
									onChange={(e) => setSimreadyProfile(e.target.value)}
									className="w-full px-4 py-2.5 rounded-lg border border-input bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition appearance-none"
								>
									<option value="Prop-Robotics-Neutral">Prop-Robotics-Neutral (Default)</option>
									<option value="Prop-Robotics-Heavy">Prop-Robotics-Heavy</option>
									<option value="Prop-Robotics-Precision">Prop-Robotics-Precision</option>
									<option value="RigidBody-Generic">RigidBody-Generic</option>
								</select>
								<Cpu className="w-4 h-4 text-muted-foreground absolute right-3 top-3 pointer-events-none" />
							</div>
						</div>

						{/* Property Assignment Radio */}
						<div className="space-y-2">
							<span className="block text-sm font-medium text-foreground">
								Property Assignment Mode
							</span>
							<div className="flex gap-4 pt-1">
								{(["run", "skip", "blocked"] as const).map((mode) => (
									<label
										key={mode}
										className={`flex-1 flex items-center justify-center gap-2 p-2.5 rounded-lg border text-xs font-medium cursor-pointer transition ${
											propertyAssignment === mode
												? "border-primary bg-primary/10 text-primary"
												: "border-input bg-background hover:bg-muted text-muted-foreground"
										}`}
									>
										<input
											type="radio"
											name="property_assignment"
											value={mode}
											checked={propertyAssignment === mode}
											onChange={() => setPropertyAssignment(mode)}
											className="sr-only"
										/>
										<span className="capitalize">{mode}</span>
									</label>
								))}
							</div>
						</div>
					</div>

					{/* Output Root Directory */}
					<div className="space-y-2">
						<label htmlFor="output_root" className="block text-sm font-medium text-foreground">
							Output Root Directory <span className="text-xs text-muted-foreground">(Optional)</span>
						</label>
						<input
							id="output_root"
							type="text"
							value={outputRoot}
							onChange={(e) => setOutputRoot(e.target.value)}
							placeholder="Leave empty for default workspace deliverables folder"
							className="w-full px-4 py-2.5 rounded-lg border border-input bg-background text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition"
						/>
					</div>

					{/* Form Error Banner */}
					{error && (
						<div className="p-4 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm flex items-start gap-3">
							<AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
							<div>
								<p className="font-semibold">Conversion Error</p>
								<p>{error}</p>
							</div>
						</div>
					)}

					{/* Convert Action Button */}
					<div className="flex justify-end">
						<button
							type="submit"
							disabled={loading}
							className="px-6 py-3 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground font-semibold text-sm flex items-center gap-2 shadow-lg shadow-primary/25 disabled:opacity-50 disabled:cursor-not-allowed transition"
						>
							{loading ? (
								<>
									<Loader2 className="w-5 h-5 animate-spin" />
									Processing CAD to SimReady...
								</>
							) : (
								<>
									<Play className="w-5 h-5 fill-current" />
									Convert to SimReady USD
								</>
							)}
						</button>
					</div>
				</form>
			</div>

			{/* Results Display Panel */}
			{result && (
				<div className="space-y-6">
					<div className="bg-card border border-border rounded-xl p-6 shadow-lg space-y-6">
						{/* Result Header & Status */}
						<div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border pb-4">
							<div className="flex items-center gap-3">
								{result.success ? (
									<div className="p-2 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
										<CheckCircle2 className="w-6 h-6" />
									</div>
								) : (
									<div className="p-2 rounded-full bg-destructive/10 text-destructive border border-destructive/20">
										<AlertCircle className="w-6 h-6" />
									</div>
								)}
								<div>
									<h2 className="text-xl font-bold text-foreground">
										{result.success ? "SimReady Asset Conformed Successfully" : "Conversion Completed with Warnings/Errors"}
									</h2>
									<p className="text-xs text-muted-foreground">
										Format: {result.source_format.toUpperCase()} | Profile: {result.simready_profile}
									</p>
								</div>
							</div>
							<div className="flex items-center gap-2">
								<span
									className={`px-3 py-1 rounded-full text-xs font-semibold ${
										result.success
											? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60"
											: "bg-red-950/80 text-red-400 border border-red-800/60"
									}`}
								>
									{result.success ? "SUCCESS" : "FAILED"}
								</span>
							</div>
						</div>

						{/* Output Paths */}
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							{/* Output USD Path */}
							{result.output_usd_path && (
								<div className="p-4 rounded-lg bg-muted/40 border border-border space-y-2">
									<div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
										<span className="flex items-center gap-1.5">
											<Box className="w-4 h-4 text-cyan-400" /> Output USD Path
										</span>
										<button
											type="button"
											onClick={() => handleCopy(result.output_usd_path || "", "output_usd")}
											className="hover:text-foreground transition"
										>
											{copiedField === "output_usd" ? (
												<Check className="w-3.5 h-3.5 text-emerald-400" />
											) : (
												<Copy className="w-3.5 h-3.5" />
											)}
										</button>
									</div>
									<p className="text-xs font-mono text-foreground break-all bg-background/60 p-2 rounded border border-border/50">
										{result.output_usd_path}
									</p>
								</div>
							)}

							{/* Conformed USD Path */}
							{result.conformed_usd_path && (
								<div className="p-4 rounded-lg bg-muted/40 border border-border space-y-2">
									<div className="flex items-center justify-between text-xs text-muted-foreground font-medium">
										<span className="flex items-center gap-1.5">
											<Layers className="w-4 h-4 text-cyan-400" /> Conformed SimReady Path
										</span>
										<button
											type="button"
											onClick={() => handleCopy(result.conformed_usd_path || "", "conformed_usd")}
											className="hover:text-foreground transition"
										>
											{copiedField === "conformed_usd" ? (
												<Check className="w-3.5 h-3.5 text-emerald-400" />
											) : (
												<Copy className="w-3.5 h-3.5" />
											)}
										</button>
									</div>
									<p className="text-xs font-mono text-foreground break-all bg-background/60 p-2 rounded border border-border/50">
										{result.conformed_usd_path}
									</p>
								</div>
							)}
						</div>

						{/* Warnings & Errors List */}
						{result.warnings.length > 0 && (
							<div className="p-4 rounded-lg bg-amber-950/20 border border-amber-800/30 text-amber-300 text-xs space-y-2">
								<div className="flex items-center gap-2 font-semibold text-amber-400">
									<AlertTriangle className="w-4 h-4" /> Warnings ({result.warnings.length})
								</div>
								<ul className="list-disc list-inside space-y-1">
									{result.warnings.map((w, idx) => (
										<li key={idx}>{w}</li>
									))}
								</ul>
							</div>
						)}

						{result.errors.length > 0 && (
							<div className="p-4 rounded-lg bg-red-950/20 border border-red-800/30 text-red-300 text-xs space-y-2">
								<div className="flex items-center gap-2 font-semibold text-red-400">
									<AlertCircle className="w-4 h-4" /> Errors ({result.errors.length})
								</div>
								<ul className="list-disc list-inside space-y-1">
									{result.errors.map((err, idx) => (
										<li key={idx}>{err}</li>
									))}
								</ul>
							</div>
						)}

						{/* Stage Reports JSON Details */}
						{result.stage_reports && Object.keys(result.stage_reports).length > 0 && (
							<details className="group border border-border rounded-lg bg-muted/20">
								<summary className="p-4 text-xs font-semibold text-foreground cursor-pointer flex items-center justify-between select-none">
									<span className="flex items-center gap-2">
										<FileText className="w-4 h-4 text-primary" /> View Detailed Stage Execution Reports
									</span>
									<span className="text-muted-foreground group-open:rotate-180 transition-transform">
										▼
									</span>
								</summary>
								<div className="p-4 border-t border-border bg-background/50">
									<pre className="text-[11px] font-mono text-muted-foreground overflow-x-auto p-3 rounded bg-muted/30">
										{JSON.stringify(result.stage_reports, null, 2)}
									</pre>
								</div>
							</details>
						)}
					</div>
				</div>
			)}
		</div>
	);
}

export default SimReadyPage;
