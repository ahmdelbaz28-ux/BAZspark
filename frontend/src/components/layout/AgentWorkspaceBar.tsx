import { ArrowRight, MessageSquareText } from "lucide-react";
import { Link } from "react-router";

/**
 * Phase 5 — Legacy UI De-emphasis.
 *
 * Provides one persistent, lightweight entry point to the existing
 * AI-first Control Center while keeping every legacy engineering route
 * directly reachable from the existing navigation.
 */
export function AgentWorkspaceBar() {
	return (
		<section
			aria-label="AI engineering workspace"
			data-testid="agent-workspace-bar"
			className="mx-4 mt-3 rounded-lg border border-border bg-card/80 shadow-sm backdrop-blur-sm"
		>
			<div className="flex items-center gap-3 px-4 py-3">
				<div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
					<MessageSquareText aria-hidden="true" className="h-5 w-5" />
				</div>
				<div className="min-w-0 flex-1">
					<p className="text-sm font-semibold text-foreground">AI Control Center</p>
					<p className="truncate text-xs text-muted-foreground">
						Chat-first engineering workspace for governed project operations.
					</p>
				</div>
				<Link
					to="/agent"
					aria-label="Open AI Control Center"
					className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
				>
					<span>Open</span>
					<ArrowRight aria-hidden="true" className="h-4 w-4" />
				</Link>
			</div>
		</section>
	);
}
