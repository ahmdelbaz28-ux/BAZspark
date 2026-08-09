import type React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
	icon?: React.ReactNode;
	title: string;
	description?: string;
	action?: {
		label: string;
		onClick: () => void;
	};
	className?: string;
	rtl?: boolean;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
	icon,
	title,
	description,
	action,
	className,
	rtl: _rtl = false,
}) => {
	return (
		<div
			className={cn(
				"flex flex-col items-center justify-center text-center p-8",
				className,
			)}
			role="status"
			aria-live="polite"
		>
			{icon && (
				<div className="mb-4 text-muted-foreground" aria-hidden="true">
					{icon}
				</div>
			)}
			<h3 className="text-lg font-semibold text-foreground/90 mb-2">{title}</h3>
			{description && (
				<p className="text-sm text-muted-foreground max-w-md mb-6">
					{description}
				</p>
			)}
			{action && (
				<Button
					onClick={action.onClick}
					className="bg-primary hover:bg-cyan-300 text-primary-foreground shadow-lg shadow-cyan-500/20 transition-[color,background-color,border-color,box-shadow] duration-200 hover:shadow-cyan-500/30"
				>
					{action.label}
				</Button>
			)}
		</div>
	);
};
