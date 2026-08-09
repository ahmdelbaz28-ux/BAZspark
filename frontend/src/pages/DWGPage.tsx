/**
 * DWGPage.tsx — DWG/DXF File Upload & Parser Results.
 *
 * Upload DWG/DXF files to the backend parser and view structured results
 * including room count, conversion time, errors, and warnings.
 *
 * Backend: POST /parse-dwg
 */

import {
	AlertTriangle,
	CheckCircle2,
	Clock,
	FileText,
	HardDrive,
	Loader2,
	PenLine,
	Upload,
	X,
} from "lucide-react";
import { useRef, useState } from "react";
import { dwgApi } from "@/services/fullApi";

interface ParseResult {
	success: boolean;
	source: string;
	room_count: number;
	conversion_time_s: number;
	errors: string[];
	warnings: string[];
}

export const DWGPage: React.FC = () => {
	const fileInputRef = useRef<HTMLInputElement>(null);
	const [uploading, setUploading] = useState(false);
	const [result, setResult] = useState<ParseResult | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [fileName, setFileName] = useState<string | null>(null);
	const [dragOver, setDragOver] = useState(false);

	const handleUpload = async (file: File) => {
		const ext = file.name.split(".").pop()?.toLowerCase();
		if (ext !== "dwg" && ext !== "dxf") {
			setError("Only .dwg and .dxf files are supported");
			return;
		}
		if (file.size > 50 * 1024 * 1024) {
			setError("File too large (max 50 MB)");
			return;
		}

		setUploading(true);
		setError(null);
		setResult(null);
		setFileName(file.name);

		try {
			const data = await dwgApi.parse(file);
			setResult(data as ParseResult);
		} catch (e) {
			setError(e instanceof Error ? e.message : "Upload failed");
		} finally {
			setUploading(false);
		}
	};

	const onFileDrop = (e: React.DragEvent) => {
		e.preventDefault();
		setDragOver(false);
		const file = e.dataTransfer.files[0];
		if (file) handleUpload(file);
	};

	const onFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
		const file = e.target.files?.[0];
		if (file) handleUpload(file);
	};

	const resetForm = () => {
		setResult(null);
		setError(null);
		setFileName(null);
		if (fileInputRef.current) fileInputRef.current.value = "";
	};

	return (
		<div className="flex-1 overflow-auto">
			<div className="p-6 max-w-4xl mx-auto space-y-6">
				{/* Header */}
				<div>
					<h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
						<PenLine className="h-6 w-6 text-cyan-400" />
						DWG / DXF Parser
					</h1>
					<p className="text-slate-400 text-sm mt-1">
						Upload AutoCAD DWG or DXF files to extract structured building data
						— rooms, layers, and geometry
					</p>
				</div>

				{/* Upload Zone */}
				<button
					type="button"
					aria-label="Upload DWG or DXF file"
					onDragOver={(e) => {
						e.preventDefault();
						setDragOver(true);
					}}
					onDragLeave={() => setDragOver(false)}
					onDrop={onFileDrop}
					onClick={() => fileInputRef.current?.click()}
					onKeyDown={(e) => {
						if (e.key === "Enter" || e.key === " ") {
							e.preventDefault();
							fileInputRef.current?.click();
						}
					}}
					className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors outline-none focus-visible:ring-2 focus-visible:ring-cyan-400 ${
						dragOver
							? "border-cyan-400 bg-cyan-500/5"
							: "border-slate-600 bg-slate-800/30 hover:border-slate-500"
					}`}
				>
					<input
						ref={fileInputRef}
						type="file"
						accept=".dwg,.dxf"
						onChange={onFileSelect}
						className="hidden"
					/>

					{uploading ? (
						<div className="flex flex-col items-center gap-3">
							<Loader2 className="h-10 w-10 text-cyan-400 animate-spin" />
							<p className="text-slate-300 text-sm">Parsing {fileName}...</p>
							<p className="text-xs text-slate-500">Processing drawing data</p>
						</div>
					) : (
						<div className="flex flex-col items-center gap-3">
							<Upload className="h-10 w-10 text-slate-500" />
							<div>
								<p className="text-slate-300 text-sm font-medium">
									Drop a DWG or DXF file here, or click to browse
								</p>
								<p className="text-xs text-slate-500 mt-1">
									Max file size: 50 MB &middot; Supported: .dwg, .dxf
								</p>
							</div>
						</div>
					)}
				</button>

				{/* Error */}
				{error && (
					<div className="flex items-start gap-3 bg-red-500/10 border border-red-500/30 rounded-lg p-4">
						<AlertTriangle className="h-5 w-5 text-red-400 flex-shrink-0 mt-0.5" />
						<div className="flex-1">
							<p className="text-red-400 text-sm font-medium">Parse Error</p>
							<p className="text-red-300/70 text-xs mt-1">{error}</p>
						</div>
						<button
							type="button"
							aria-label="Close"
							onClick={resetForm}
							className="text-red-400 hover:text-red-300"
						>
							<X className="h-4 w-4" />
						</button>
					</div>
				)}

				{/* Results */}
				{result && (
					<div className="space-y-4">
						{/* Success banner */}
						{result.success && (
							<div className="flex items-center gap-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4">
								<CheckCircle2 className="h-5 w-5 text-emerald-400 flex-shrink-0" />
								<div>
									<p className="text-emerald-400 text-sm font-medium">
										File parsed successfully
									</p>
									<p className="text-emerald-300/70 text-xs mt-1">
										{result.source}
									</p>
								</div>
								<button
									type="button"
									onClick={resetForm}
									className="ml-auto text-slate-500 hover:text-slate-300"
								>
									<X className="h-4 w-4" />
								</button>
							</div>
						)}

						{/* Stats */}
						<div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
							<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-center">
								<HardDrive className="h-4 w-4 text-cyan-400 mx-auto mb-1" />
								<div className="text-lg font-bold text-slate-100 font-mono">
									{result.source.split(".").pop()?.toUpperCase()}
								</div>
								<div className="text-[10px] text-slate-500 mt-1">Format</div>
							</div>
							<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-center">
								<FileText className="h-4 w-4 text-cyan-400 mx-auto mb-1" />
								<div className="text-lg font-bold text-slate-100 font-mono">
									{result.room_count}
								</div>
								<div className="text-[10px] text-slate-500 mt-1">Rooms</div>
							</div>
							<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-center">
								<Clock className="h-4 w-4 text-cyan-400 mx-auto mb-1" />
								<div className="text-lg font-bold text-slate-100 font-mono">
									{result.conversion_time_s.toFixed(2)}s
								</div>
								<div className="text-[10px] text-slate-500 mt-1">Time</div>
							</div>
							<div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-center">
								<CheckCircle2 className="h-4 w-4 text-emerald-400 mx-auto mb-1" />
								<div className="text-lg font-bold text-slate-100 font-mono">
									{result.success ? "OK" : "FAIL"}
								</div>
								<div className="text-[10px] text-slate-500 mt-1">Status</div>
							</div>
						</div>

						{/* Warnings */}
						{result.warnings && result.warnings.length > 0 && (
							<div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
								<h4 className="text-xs font-semibold text-amber-400 mb-2 flex items-center gap-1">
									<AlertTriangle className="h-3 w-3" />
									Warnings ({result.warnings.length})
								</h4>
								<ul className="space-y-1">
									{result.warnings.map((w, i) => (
										<li key={i} className="text-xs text-amber-300/70 font-mono">
											{w}
										</li>
									))}
								</ul>
							</div>
						)}

						{/* Errors (non-fatal) */}
						{result.errors && result.errors.length > 0 && (
							<div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
								<h4 className="text-xs font-semibold text-red-400 mb-2 flex items-center gap-1">
									<AlertTriangle className="h-3 w-3" />
									Errors ({result.errors.length})
								</h4>
								<ul className="space-y-1">
									{result.errors.map((e, i) => (
										<li key={i} className="text-xs text-red-300/70 font-mono">
											{e}
										</li>
									))}
								</ul>
							</div>
						)}
					</div>
				)}

				{/* Info */}
				<div className="bg-slate-800/30 border border-slate-700/50 rounded-lg p-4">
					<p className="text-xs text-slate-500">
						The DWG/DXF parser extracts room layouts, layer information, and
						building geometry from AutoCAD drawings. Parsed data can be used for
						fire safety analysis, egress calculations, and digital twin
						creation. All uploads are ephemeral — files are deleted after
						processing.
					</p>
				</div>
			</div>
		</div>
	);
};

export default DWGPage;
