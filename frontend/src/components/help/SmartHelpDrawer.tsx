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
	initialSearch?: string | null;
}

export function SmartHelpDrawer({
	open = false,
	onOpenChange = () => { },
	initialTopicId,
	initialContextId,
	initialSearch,
}: SmartHelpDrawerProps) {
	// Only use initialContextId if it matches a known HelpTopicId;
	// otherwise fall back to initialTopicId only.
	const activeTopic = initialTopicId ?? undefined;
	void initialContextId; // Preserved for backward-compatible API; not passed through
	return (
		<GlobalHelpDrawer
			open={open}
			onOpenChange={onOpenChange}
			initialTopicId={activeTopic}
			initialSearch={initialSearch}
		/>
	);
}

export { GlobalHelpDrawer as HelpDrawer };
