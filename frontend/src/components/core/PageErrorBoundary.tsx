
/**
 * PageErrorBoundary.tsx - Page-level error boundary
 * Catches errors in individual page routes so that one broken page
 * does NOT crash the entire application. Shows a page-level error
 * message with a "Retry Component" button that resets the boundary.
 *
 * @deprecated New code should prefer ErrorBoundary directly with a
 * `fallback` prop for page-level error handling. PageErrorBoundary
 * is retained for backward compatibility and delegates to
 * ErrorRecoveryView for a consistent error UI.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { ErrorRecoveryView, getErrorContextId } from "./ErrorRecoveryView";

interface Props {
	children: ReactNode;
	pageName?: string;
}

interface State {
	hasError: boolean;
	error: Error | null;
	errorInfo: ErrorInfo | null;
}

export class PageErrorBoundary extends Component<Props, State> {
	constructor(props: Props) {
		super(props);
		this.state = { hasError: false, error: null, errorInfo: null };
	}

	static getDerivedStateFromError(error: Error): State {
		return { hasError: true, error, errorInfo: null };
	}

	componentDidCatch(error: Error, errorInfo: ErrorInfo) {
		// Log the error for debugging — never suppress silently
		console.error(
			`[BAZSPARK PageErrorBoundary] Error in page "${this.props.pageName || "unknown"}":`,
			error,
			errorInfo,
		);
		this.setState({ errorInfo });
	}

	handleRetry = () => {
		this.setState({ hasError: false, error: null, errorInfo: null });
	};

	render() {
		if (this.state.hasError) {
			return (
				<ErrorRecoveryView
					error={this.state.error}
					errorInfo={this.state.errorInfo}
					errorContextId={getErrorContextId(
						this.state.error,
						this.state.errorInfo?.componentStack,
					)}
					reload={this.handleRetry}
				/>
			);
		}

		return this.props.children;
	}
}
