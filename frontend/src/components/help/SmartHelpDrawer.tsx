import { lazy, Suspense } from "react";
import type { HelpTopicId } from "@/help/types";

const GlobalHelpDrawerLazy = lazy(() =>
	import("@/components/shared/GlobalHelpDrawer").then((m) => ({ default: m.GlobalHelpDrawer }))
);

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
	const activeTopic = initialTopicId ?? undefined;
	void initialContextId; // Preserved for backward-compatible API; not passed through
	if (!open) return null;
	return (
		<Suspense fallback={null}>
			<GlobalHelpDrawerLazy
				open={open}
				onOpenChange={onOpenChange}
				initialTopicId={activeTopic}
				initialSearch={initialSearch}
			/>
		</Suspense>
	);
}

