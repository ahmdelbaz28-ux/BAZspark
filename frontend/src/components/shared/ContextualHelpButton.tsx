/**
 * ContextualHelpButton.tsx — Per-page help button
 *
 * Displays a floating help button in the top-right of each page.
 * When clicked, opens the help drawer showing the topic for the current page.
 * Uses ROUTE_HELP_MAP to find the relevant help topic.
 */

import { HelpCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router";
import { toast } from "sonner";
import { HELP_TOPICS as TOPICS } from "@/help/helpTopics";
import { ROUTE_HELP_MAP } from "@/help/types";

// Vercel React Best Practices: js-hoist-regexp / js-cache-function-results
// Pre-sort routes once at module level to avoid sorting on every click
const SORTED_ROUTES = Object.keys(ROUTE_HELP_MAP).sort(
	(a, b) => b.length - a.length,
);

interface ContextualHelpButtonProps {
	/** Override the route (defaults to current location) */
	route?: string;
	/** Custom label */
	label?: string;
}

function useSafeLocation() {
	try {
		return useLocation();
	} catch {
		return {
			pathname: typeof window !== "undefined" ? window.location.pathname : "/",
			search: "",
			hash: "",
			state: null,
			key: "default",
		};
	}
}

export function ContextualHelpButton({
	route,
	label,
}: ContextualHelpButtonProps) {
	const location = useSafeLocation();
	const { i18n } = useTranslation();
	const currentRoute = route || location.pathname;

	// Find the best matching help topic for the current route
	const findHelpTopic = (): string | null => {
		// Try exact match first
		if (ROUTE_HELP_MAP[currentRoute]) {
			return ROUTE_HELP_MAP[currentRoute];
		}
		// Try prefix match (e.g. /elements/123 → /elements)
		for (const r of SORTED_ROUTES) {
			if (currentRoute.startsWith(`${r}/`) || currentRoute === r) {
				return ROUTE_HELP_MAP[r];
			}
		}
		return null;
	};

	const topicId = findHelpTopic();
	const topic = topicId ? TOPICS[topicId as keyof typeof TOPICS] : null;

	const handleClick = () => {
		if (!topic) {
			toast.info(
				i18n.language === "ar"
					? "لا يوجد مساعدة متاحة لهذه الصفحة"
					: "No help available for this page",
			);
			return;
		}
		// Show help content in a toast (lightweight, no heavy drawer needed)
		const title = i18n.language === "ar" ? topic.titleAr : topic.titleEn;
		const desc =
			i18n.language === "ar" ? topic.descriptionAr : topic.descriptionEn;
		const steps = i18n.language === "ar" ? topic.stepsAr : topic.stepsEn;

		toast(
			<div className="space-y-2 max-w-md">
				<h3 className="font-bold text-foreground">{title}</h3>
				<p className="text-sm text-muted-foreground">{desc}</p>
				{steps.length > 0 && (
					<ol className="text-xs text-muted-foreground list-decimal list-inside space-y-1">
						{steps.slice(0, 5).map((step, i) => (
							<li key={i}>{step}</li>
						))}
					</ol>
				)}
			</div>,
			{ duration: 10000, position: "top-right" },
		);

		// Also try to open the SmartHelpDrawer if available
		const helpEvent = new CustomEvent("fireai:open-help", {
			detail: { topicId },
		});
		globalThis.dispatchEvent(helpEvent);
	};

	return (
		<button
			type="button"
			onClick={handleClick}
			className="p-1.5 text-muted-foreground hover:text-primary hover:bg-card transition-[color,background-color,border-color,transform] duration-200 hover:scale-110 rounded flex items-center gap-1"
			title={
				label ||
				(i18n.language === "ar" ? "مساعدة هذه الصفحة" : "Help for this page")
			}
			aria-label={
				i18n.language === "ar" ? "مساعدة هذه الصفحة" : "Help for this page"
			}
		>
			<HelpCircle aria-hidden="true" className="h-4 w-4" />
		</button>
	);
}
