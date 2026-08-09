import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { type ReactNode, useEffect, useRef } from "react";

interface LoginModalProps {
	readonly open: boolean;
	readonly onClose: () => void;
	readonly title: string;
	readonly icon: ReactNode;
	readonly children: ReactNode;
}

export function LoginModal({
	open,
	onClose,
	title,
	icon,
	children,
}: LoginModalProps) {
	const headingId = `login-modal-heading-${title.replace(/\s+/g, "-").toLowerCase()}`;
	const closeRef = useRef<HTMLButtonElement>(null);

	useEffect(() => {
		if (open) {
			closeRef.current?.focus();
		}
	}, [open]);

	useEffect(() => {
		if (!open) return;
		const handler = (e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [open, onClose]);

	return (
		<AnimatePresence>
			{open && (
				<dialog
					className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm"
					open
					aria-modal="true"
					aria-labelledby={headingId}
				>
					<motion.div
						initial={{ opacity: 0, scale: 0.95 }}
						animate={{ opacity: 1, scale: 1 }}
						exit={{ opacity: 0, scale: 0.95 }}
						transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
						className="w-full max-w-[420px] login-glass-card-strong rounded-xl p-6 shadow-2xl shadow-black/70 m-auto"
					>
						<div className="flex items-center justify-between border-b border-slate-800/70 pb-3 mb-4">
							<h3
								id={headingId}
								className="text-base font-bold text-white flex items-center gap-2"
							>
								{icon}
								{title}
							</h3>
							<button
								type="button"
								onClick={onClose}
								ref={closeRef}
								className="text-slate-400 hover:text-white cursor-pointer p-1 bg-transparent border-none rounded"
								aria-label="Close dialog"
							>
								<X className="size-4" />
							</button>
						</div>
						{children}
					</motion.div>
				</dialog>
			)}
		</AnimatePresence>
	);
}
