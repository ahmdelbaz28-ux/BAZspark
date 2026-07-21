
/**
 * RouteGuard.tsx — Protects routes that require authentication.
 *
 * V193 (R1): Wraps any page that needs a logged-in user. If the user is not
 * authenticated, redirects to /login?from=<original-path> so the user
 * returns to their intended page after login.
 *
 * Usage in App.tsx:
 *   <Route
 *     path="/dashboard"
 *     element={
 *       <RouteGuard>
 *         <DashboardPage />
 *       </RouteGuard>
 *     }
 *   />
 *
 * The guard shows a minimal spinner while the AuthContext is performing its
 * initial /auth/me check (state.loading === true). Once the check completes,
 * it either renders the children (authenticated) or redirects (not).
 */
import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

interface RouteGuardProps {
        readonly children: ReactNode;
        /**
         * Optional role required to access this route.
         * - If set and user lacks this role, renders an AccessDenied view.
         * - If not set, any authenticated user can access.
         * Backend roles: admin, engineer, viewer
         */
        readonly requiredRole?: string;
}

// C-07 FIX: Role mapping for human-readable access denied messages
const ROLE_LABELS: Record<string, string> = {
        admin: "Administrator",
        engineer: "Engineer",
        viewer: "Viewer",
};

export function RouteGuard({ children, requiredRole }: RouteGuardProps) {

        const { isAuthenticated, loading, role } = useAuth();
        const location = useLocation();

        if (loading) {
                return (
                        <div className="min-h-screen flex items-center justify-center bg-background">
                                <div className="flex flex-col items-center gap-3">
                                        <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                        <p className="text-sm text-muted-foreground">Verifying session...</p>
                                </div>
                        </div>
                );
        }

        if (!isAuthenticated) {
                // Preserve the original path so we can return after login
                const from = encodeURIComponent(location.pathname + location.search);
                return <Navigate to={`/login?from=${from}`} replace />;
        }

        // C-07 FIX: Check role-based access if a requiredRole is specified
        if (requiredRole && role !== requiredRole) {
                const requiredLabel = ROLE_LABELS[requiredRole] || requiredRole;
                const userLabel = (role && ROLE_LABELS[role]) || role || "Unknown";
                return (
                        <div className="min-h-screen flex items-center justify-center bg-background">
                                <div className="flex flex-col items-center gap-4 max-w-md text-center px-4">
                                        <div className="rounded-full bg-destructive/10 p-4">
                                                <svg
                                                        className="h-8 w-8 text-destructive"
                                                        fill="none"
                                                        viewBox="0 0 24 24"
                                                        stroke="currentColor"
                                                        strokeWidth={2}
                                                >
                                                        <path
                                                                strokeLinecap="round"
                                                                strokeLinejoin="round"
                                                                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
                                                        />
                                                </svg>
                                        </div>
                                        <h2 className="text-xl font-semibold text-foreground">
                                                Access Denied
                                        </h2>
                                        <p className="text-sm text-muted-foreground">
                                                This page requires the <strong>{requiredLabel}</strong> role.
                                                Your current role is <strong>{userLabel}</strong>.
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                                Contact your administrator if you need elevated access.
                                        </p>
                                </div>
                        </div>
                );
        }

        return <>{children}</>;
}
