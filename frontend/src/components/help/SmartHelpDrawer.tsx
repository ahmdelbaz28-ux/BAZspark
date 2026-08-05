/**
 * SmartHelpDrawer.tsx — Backward-compatible wrapper component
 *
 * Merged into GlobalHelpDrawer.tsx. Delegates all props and renders GlobalHelpDrawer.
 */
import { GlobalHelpDrawer } from "@/components/shared/GlobalHelpDrawer";
import type { HelpTopicId } from "@/help/types";

export interface SmartHelpDrawerProps {
	open?: boolean;
	onOpenChange?: (open: boolean) => void;
	initialTopicId?: HelpTopicId | null;
	initialContextId?: string | null;
	initialSearch?: string;
	[key: string]: unknown;
}

export function SmartHelpDrawer({
	open = false,
	onOpenChange = () => {},
	initialTopicId,
	initialContextId,
}: SmartHelpDrawerProps) {
	const activeTopic = (initialTopicId || initialContextId) as HelpTopicId | undefined;
	return (
		<GlobalHelpDrawer
			open={open}
			onOpenChange={onOpenChange}
			initialTopicId={activeTopic}
		/>
	);
}

export { GlobalHelpDrawer as HelpDrawer };
