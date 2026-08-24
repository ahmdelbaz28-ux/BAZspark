/**
 * AutoApprovalToggle.tsx — Execution Policy Approval Mode Switcher (Phase 2).
 *
 * Positioned adjacent to the chat input and voice microphone button.
 * Controls whether the backend Agent Run executes autonomously (AUTO)
 * or halts at governed mutation gates (STEP-BY-STEP) for human review.
 */
import { Check, ChevronDown, ShieldCheck, Zap } from "lucide-react";
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { ApprovalMode } from "@/hooks/useAgentRun";

interface AutoApprovalToggleProps {
	mode: ApprovalMode;
	onChange: (mode: ApprovalMode) => void;
	disabled?: boolean;
}

export const AutoApprovalToggle: React.FC<AutoApprovalToggleProps> = ({
	mode,
	onChange,
	disabled = false,
}) => {
	const [isOpen, setIsOpen] = useState(false);
	const dropdownRef = useRef<HTMLDivElement>(null);

	const isAuto = mode === "AUTO";

	const toggleDropdown = useCallback(() => {
		if (!disabled) {
			setIsOpen((prev) => !prev);
		}
	}, [disabled]);

	const selectMode = useCallback(
		(newMode: ApprovalMode) => {
			onChange(newMode);
			setIsOpen(false);
		},
		[onChange],
	);

	// Close on click outside
	useEffect(() => {
		const handleClickOutside = (e: MouseEvent) => {
			if (
				dropdownRef.current &&
				!dropdownRef.current.contains(e.target as Node)
			) {
				setIsOpen(false);
			}
		};
		if (isOpen) {
			document.addEventListener("mousedown", handleClickOutside);
		}
		return () => {
			document.removeEventListener("mousedown", handleClickOutside);
		};
	}, [isOpen]);

	// Close on Escape key
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === "Escape") {
				setIsOpen(false);
			}
		};
		if (isOpen) {
			document.addEventListener("keydown", handleKeyDown);
		}
		return () => {
			document.removeEventListener("keydown", handleKeyDown);
		};
	}, [isOpen]);

	return (
		<div className="relative inline-block text-left" ref={dropdownRef}>
			<button
				type="button"
				onClick={toggleDropdown}
				disabled={disabled}
				aria-haspopup="listbox"
				aria-expanded={isOpen}
				aria-label={`Execution approval mode: currently ${isAuto ? "Auto Approval" : "Step-by-Step"}`}
				className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-semibold border transition-all select-none focus:outline-none focus:ring-2 focus:ring-secondary/50 ${
					isAuto
						? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/20"
						: "bg-amber-500/10 text-amber-300 border-amber-500/30 hover:bg-amber-500/20"
				} ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
				title={
					isAuto
						? "Auto Mode: Governed mutations execute autonomously"
						: "Step-by-Step Mode: Governed mutations halt for human review"
				}
				data-testid="auto-approval-toggle-btn"
			>
				{isAuto ? (
					<Zap className="h-3.5 w-3.5 text-emerald-400 shrink-0 animate-pulse" />
				) : (
					<ShieldCheck className="h-3.5 w-3.5 text-amber-400 shrink-0" />
				)}
				<span className="font-mono text-[11px]">
					{isAuto ? "AUTO" : "STEP-BY-STEP"}
				</span>
				<ChevronDown className="h-3 w-3 opacity-70" />
			</button>

			{/* Dropdown Menu */}
			{isOpen && (
				<div
					role="listbox"
					aria-label="Select execution approval mode"
					className="absolute bottom-full mb-2 left-0 w-64 rounded-xl bg-card/95 backdrop-blur-md border border-border p-1.5 shadow-2xl z-50 animate-in fade-in zoom-in-95 duration-100"
					data-testid="auto-approval-dropdown"
				>
					<div className="px-2.5 py-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground border-b border-border/40 mb-1">
						Execution Policy
					</div>

					{/* AUTO Option */}
					<button
						type="button"
						role="option"
						aria-selected={isAuto}
						onClick={() => selectMode("AUTO")}
						className={`w-full flex items-start gap-2 px-2.5 py-2 rounded-lg text-left transition-colors ${
							isAuto
								? "bg-emerald-500/15 text-foreground"
								: "hover:bg-muted text-muted-foreground hover:text-foreground"
						}`}
						data-testid="auto-mode-option"
					>
						<Zap className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
						<div className="flex-1 min-w-0">
							<div className="flex items-center justify-between">
								<span className="text-xs font-semibold text-foreground">
									Auto Approval
								</span>
								{isAuto && (
									<Check className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
								)}
							</div>
							<p className="text-[10px] text-muted-foreground leading-tight mt-0.5">
								Allowed operations execute continuously without pausing.
							</p>
						</div>
					</button>

					{/* STEP-BY-STEP Option */}
					<button
						type="button"
						role="option"
						aria-selected={!isAuto}
						onClick={() => selectMode("STEP_BY_STEP")}
						className={`w-full flex items-start gap-2 px-2.5 py-2 rounded-lg text-left transition-colors mt-1 ${
							!isAuto
								? "bg-amber-500/15 text-foreground"
								: "hover:bg-muted text-muted-foreground hover:text-foreground"
						}`}
						data-testid="step-by-step-option"
					>
						<ShieldCheck className="h-4 w-4 text-amber-400 mt-0.5 shrink-0" />
						<div className="flex-1 min-w-0">
							<div className="flex items-center justify-between">
								<span className="text-xs font-semibold text-foreground">
									Step-by-Step
								</span>
								{!isAuto && (
									<Check className="h-3.5 w-3.5 text-amber-400 shrink-0" />
								)}
							</div>
							<p className="text-[10px] text-muted-foreground leading-tight mt-0.5">
								Pauses at each governed mutation step for explicit PE sign-off.
							</p>
						</div>
					</button>
				</div>
			)}
		</div>
	);
};
