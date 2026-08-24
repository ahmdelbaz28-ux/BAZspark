/**
 * AttachmentSurface.tsx — Drawing & BIM Attachment Surface (Phase 2).
 *
 * Provides file selection and metadata display for engineering files
 * (.dwg, .dxf, .pdf, .ifc, .rvt) without routing through Phase 3 importers.
 */
import { FileCode, FileText, Paperclip, X } from "lucide-react";
import type React from "react";
import { useCallback, useRef } from "react";

export interface AttachedFile {
	id: string;
	file: File;
	name: string;
	sizeBytes: number;
	extension: string;
	status: "ready" | "uploading" | "validated" | "error";
	errorMessage?: string;
}

interface AttachmentSurfaceProps {
	files: AttachedFile[];
	onAddFiles: (files: File[]) => void;
	onRemoveFile: (id: string) => void;
	disabled?: boolean;
}

const ALLOWED_EXTENSIONS = [".dwg", ".dxf", ".pdf", ".ifc", ".rvt"];

function formatFileSize(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(ext: string) {
	if (ext === ".pdf") {
		return <FileText className="h-3.5 w-3.5 text-red-400" />;
	}
	return <FileCode className="h-3.5 w-3.5 text-cyan-400" />;
}

export const AttachmentSurface: React.FC<AttachmentSurfaceProps> = ({
	files,
	onAddFiles,
	onRemoveFile,
	disabled = false,
}) => {
	const fileInputRef = useRef<HTMLInputElement>(null);

	const handleFileSelect = useCallback(
		(e: React.ChangeEvent<HTMLInputElement>) => {
			const selectedFiles = e.target.files;
			if (!selectedFiles || selectedFiles.length === 0) return;

			const validFiles: File[] = [];
			for (let i = 0; i < selectedFiles.length; i++) {
				const file = selectedFiles[i];
				const ext = `.${file.name.split(".").pop()?.toLowerCase()}`;
				if (ALLOWED_EXTENSIONS.includes(ext)) {
					validFiles.push(file);
				}
			}

			if (validFiles.length > 0) {
				onAddFiles(validFiles);
			}

			// Reset input so re-selecting same file triggers change
			if (fileInputRef.current) {
				fileInputRef.current.value = "";
			}
		},
		[onAddFiles],
	);

	return (
		<div>
			<input
				ref={fileInputRef}
				type="file"
				multiple
				accept={ALLOWED_EXTENSIONS.join(",")}
				onChange={handleFileSelect}
				className="hidden"
				data-testid="file-attachment-input"
			/>

			{/* Attached File Chips List */}
			{files.length > 0 && (
				<div
					className="flex flex-wrap gap-2 mb-2 px-1"
					data-testid="attached-files-list"
				>
					{files.map((att) => (
						<div
							key={att.id}
							className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-card/90 border border-border/80 text-xs shadow-sm"
						>
							{getFileIcon(att.extension)}
							<span
								className="font-medium text-foreground max-w-[150px] truncate"
								title={att.name}
							>
								{att.name}
							</span>
							<span className="text-[10px] font-mono text-muted-foreground">
								({formatFileSize(att.sizeBytes)})
							</span>
							<button
								type="button"
								onClick={() => onRemoveFile(att.id)}
								disabled={disabled}
								className="text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded"
								aria-label={`Remove file ${att.name}`}
							>
								<X className="h-3 w-3" />
							</button>
						</div>
					))}
				</div>
			)}
		</div>
	);
};

export const AttachmentButton: React.FC<{
	onClick: () => void;
	disabled?: boolean;
}> = ({ onClick, disabled }) => (
	<button
		type="button"
		onClick={onClick}
		disabled={disabled}
		title="Attach CAD / BIM / PDF file (.dwg, .dxf, .pdf, .ifc, .rvt)"
		aria-label="Attach drawing or BIM file"
		className="h-9 w-9 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
		data-testid="attachment-btn"
	>
		<Paperclip className="h-4 w-4" />
	</button>
);
