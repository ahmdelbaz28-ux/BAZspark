/**
 * KeyboardShortcutsHelp.tsx — Keyboard shortcuts reference dialog.
 *
 * Displays all available keyboard shortcuts organized by category
 * (Navigation, Actions, Global). Triggered by pressing `?` globally.
 *
 * Uses the Radix Dialog primitive (already in the codebase) for
 * consistent modal behavior with proper focus trapping and escape handling.
 */

import { Keyboard, Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

interface ShortcutEntry {
	keys: string[];
	labelKey: string;
	defaultLabel: string;
}

const SHORTCUT_GROUPS: {
	categoryKey: string;
	defaultCategory: string;
	icon: string;
	shortcuts: ShortcutEntry[];
}[] = [
	{
		categoryKey: "shortcuts.category.navigation",
		defaultCategory: "Navigation",
		icon: "→",
		shortcuts: [
			{ keys: ["G", "D"], labelKey: "shortcuts.dashboard", defaultLabel: "Go to Dashboard" },
			{ keys: ["G", "P"], labelKey: "shortcuts.projects", defaultLabel: "Go to Projects" },
			{ keys: ["G", "E"], labelKey: "shortcuts.engineering", defaultLabel: "Go to Engineering" },
			{ keys: ["G", "S"], labelKey: "shortcuts.settings", defaultLabel: "Go to Settings" },
			{ keys: ["G", "R"], labelKey: "shortcuts.reports", defaultLabel: "Go to Reports" },
			{ keys: ["G", "F"], labelKey: "shortcuts.fireAlarm", defaultLabel: "Go to Fire Alarm Designer" },
			{ keys: ["G", "T"], labelKey: "shortcuts.digitalTwin", defaultLabel: "Go to Digital Twin" },
		],
	},
	{
		categoryKey: "shortcuts.category.actions",
		defaultCategory: "Actions",
		icon: "⚡",
		shortcuts: [
			{ keys: ["Ctrl+K"], labelKey: "shortcuts.commandPalette", defaultLabel: "Open Command Palette" },
			{ keys: ["Ctrl+J"], labelKey: "shortcuts.aiCopilot", defaultLabel: "Toggle AI Copilot" },
			{ keys: ["Ctrl+H"], labelKey: "shortcuts.help", defaultLabel: "Open Contextual Help" },
			{ keys: ["F1"], labelKey: "shortcuts.helpF1", defaultLabel: "Open Help" },
		],
	},
	{
		categoryKey: "shortcuts.category.general",
		defaultCategory: "General",
		icon: "⌨",
		shortcuts: [
			{ keys: ["?"], labelKey: "shortcuts.showHelp", defaultLabel: "Show Keyboard Shortcuts" },
			{ keys: ["/"], labelKey: "shortcuts.search", defaultLabel: "Focus Search / Command Palette" },
			{ keys: ["Esc"], labelKey: "shortcuts.close", defaultLabel: "Close Modals / Panels" },
			{ keys: ["↑", "↓"], labelKey: "shortcuts.navigate", defaultLabel: "Navigate Results" },
			{ keys: ["Enter"], labelKey: "shortcuts.select", defaultLabel: "Select / Confirm" },
		],
	},
];

function ShortcutKey({ children }: { children: string }) {
	const isMac =
		typeof navigator !== "undefined" &&
		(navigator.platform.toLowerCase().includes("mac") ||
			navigator.userAgent.toLowerCase().includes("mac"));

	// Platform-aware modifier display
	let display = children;
	if (children === "Ctrl+K" && isMac) display = "⌘K";
	if (children === "Ctrl+J" && isMac) display = "⌘J";
	if (children === "Ctrl+H" && isMac) display = "⌘H";

	const renderKbd = (text: string) => (
		<kbd className="inline-flex h-6 min-w-[1.5rem] items-center justify-center rounded border border-border bg-muted px-1.5 font-mono text-[11px] font-medium text-foreground">
			{text}
		</kbd>
	);

	// Single character keys: ?, /, Enter (Enter is ≤ 5 chars)
	if (display.length <= 2 && display !== "Esc") {
		return renderKbd(display);
	}

	// Esc is a single key label
	if (display === "Esc") {
		return renderKbd("Esc");
	}

	// Chorded shortcut: Ctrl+K → ["Ctrl", "K"] with + separator
	if (display.includes("+")) {
		const parts = display.split("+");
		return (
			<span className="inline-flex items-center gap-0.5">
				{parts.map((part, i) => (
					<span key={part} className="inline-flex items-center gap-0.5">
						{i > 0 && <span className="text-xs text-muted-foreground select-none">+</span>}
						{renderKbd(part)}
					</span>
				))}
			</span>
		);
	}

	// Sequential shortcut: "G D" → [G] [D] side by side (no + separator)
	if (display.includes(" ")) {
		const parts = display.split(" ");
		return (
			<span className="inline-flex items-center gap-1">
				{parts.map((part) => renderKbd(part))}
			</span>
		);
	}

	// Fallback: display as-is
	return renderKbd(display);
}

interface KeyboardShortcutsHelpProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

export function KeyboardShortcutsHelp({ open, onOpenChange }: KeyboardShortcutsHelpProps) {
	const { t } = useTranslation();

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="sm:max-w-[520px] max-h-[80vh] p-0 gap-0 bg-card border-border">
				<DialogHeader className="px-6 pt-6 pb-4 border-b border-border">
					<div className="flex items-center gap-3">
						<div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
							<Keyboard aria-hidden="true" className="h-5 w-5 text-primary" />
						</div>
						<div>
							<DialogTitle className="text-lg text-foreground">
								{t("shortcuts.title", "Keyboard Shortcuts")}
							</DialogTitle>
							<DialogDescription className="text-sm text-muted-foreground mt-0.5">
								{t("shortcuts.description", "Press keys to navigate and control the application")}
							</DialogDescription>
						</div>
					</div>
				</DialogHeader>

				<ScrollArea className="p-6 max-h-[55vh]">
					<div className="space-y-6">
						{SHORTCUT_GROUPS.map((group) => (
							<div key={group.categoryKey}>
								<h3 className="flex items-center gap-2 text-sm font-semibold text-foreground mb-3">
									<span className="text-base" aria-hidden="true">{group.icon}</span>
									{t(group.categoryKey, group.defaultCategory)}
								</h3>
								<div className="space-y-1.5">
									{group.shortcuts.map((shortcut) => (
										<div
											key={shortcut.defaultLabel}
											className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-muted/50 transition-colors"
										>
											<span className="text-sm text-muted-foreground">
												{t(shortcut.labelKey, shortcut.defaultLabel)}
											</span>
											<ShortcutKey>{shortcut.keys.join(" ")}</ShortcutKey>
										</div>
									))}
								</div>
							</div>
						))}
					</div>
				</ScrollArea>

				<div className="flex items-center justify-between border-t border-border px-6 py-3 bg-muted/30">
					<div className="flex items-center gap-2 text-xs text-muted-foreground">
						<Search aria-hidden="true" className="h-3 w-3" />
						<span>
							{t("shortcuts.commandHint", "Press Ctrl+K for commands")}
						</span>
					</div>
					<span className="text-xs text-muted-foreground">
						<kbd className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded border border-border bg-background px-1 font-mono text-[10px]">
							Esc
						</kbd>
						{" "}
						{t("shortcuts.close", "Close")}
					</span>
				</div>
			</DialogContent>
		</Dialog>
	);
}
