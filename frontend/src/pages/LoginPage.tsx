/**
 * LoginPage.tsx — API-key based login with session cookie.
 *
 * V193 (R1): Adds the missing /login route. Users enter their FireAI API key,
 * we POST it to /api/v1/auth/login which sets an HttpOnly session cookie,
 * then redirect to /dashboard.
 *
 * Why API key (not username/password)?
 *   The backend auth model is API-key based (backend/routers/auth.py).
 *   API keys are issued by an admin and stored as bcrypt hashes. The login
 *   endpoint accepts {api_key: "..."} and returns {role: "admin|engineer|viewer"}.
 *   There is no username/password table.
 *
 * UX:
 *   - Single password-style input (the API key)
 *   - Show/Hide toggle (API keys are sensitive)
 *   - Inline error messages for 401 / 429 / network errors
 *   - "Remember this key on this device" checkbox (stores in sessionStorage
 *     as a convenience for dev — the cookie is the real auth token)
 *   - Redirect to /dashboard on success
 *   - Redirect to original ?from= URL if present
 */
import { Button } from "@/components/ui/button";
import {
        Card,
        CardContent,
        CardDescription,
        CardFooter,
        CardHeader,
        CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Eye, EyeOff, KeyRound, Loader2, LogIn, AlertCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useSearchParams, Navigate } from "react-router-dom";
import { login } from "@/services/api";
import { useAuth } from "@/contexts/AuthContext";

export function LoginPage() {
        const [searchParams] = useSearchParams();
        const { isAuthenticated, loading: ctxLoading } = useAuth();

        const [apiKey, setApiKey] = useState("");
        const [showKey, setShowKey] = useState(false);
        const [remember, setRemember] = useState(false);
        const [submitting, setSubmitting] = useState(false);
        const [error, setError] = useState<string | null>(null);

        // If already authenticated, redirect to dashboard (or ?from=)
        if (!ctxLoading && isAuthenticated) {
                const from = searchParams.get("from") || "/dashboard";
                return <Navigate to={from} replace />;
        }

        const handleSubmit = async (e: FormEvent) => {
                e.preventDefault();
                setError(null);

                if (!apiKey.trim()) {
                        setError("Please enter your API key.");
                        return;
                }

                setSubmitting(true);
                try {
                        // V193 FIX: Do the optional sessionStorage write FIRST (synchronous),
                        // before login() updates AuthContext state.
                        if (remember) {
                                try {
                                        sessionStorage.setItem(
                                                "fireai_settings",
                                                JSON.stringify({ apiKey: apiKey.trim() }),
                                        );
                                } catch {
                                        // sessionStorage might be unavailable (private mode) — ignore
                                }
                        }

                        // login() calls POST /auth/login, then updates AuthContext state
                        // (isAuthenticated=true, role=result.role). The state update
                        // triggers re-render of LoginPage, which hits the
                        // `if (!ctxLoading && isAuthenticated) return <Navigate to={from}/>`
                        // branch at the top of this component and redirects to the
                        // originally requested page (or /dashboard).
                        //
                        // We DO NOT call navigate() here because React Router v7 has a
                        // known issue where calling navigate() inside an async handler
                        // after a context state update can race with the context-driven
                        // re-render, causing the navigation to be silently dropped.
                        // Trusting the <Navigate> component is the correct pattern.
                        await login(apiKey.trim());

                        // If we reach here, login() resolved but the <Navigate> in the
                        // render branch hasn't fired yet (rare React batching edge case).
                        // Force a re-render by toggling submitting state, which will
                        // re-evaluate the conditional and trigger <Navigate>.
                        setSubmitting(false);
                } catch (err) {
                        const msg = err instanceof Error ? err.message : "Login failed";
                        if (msg.includes("429") || msg.includes("Too many")) {
                                setError(
                                        "Too many failed login attempts. Please wait 5 minutes and try again.",
                                );
                        } else if (msg.includes("401") || msg.includes("Invalid")) {
                                setError("Invalid API key. Please check and try again.");
                        } else if (msg.includes("Failed to fetch") || msg.includes("Network")) {
                                setError(
                                        "Cannot reach the server. Please check your network connection and try again.",
                                );
                        } else {
                                setError(msg);
                        }
                        setSubmitting(false);
                }
        };

        return (
                <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
                        <div className="w-full max-w-md">
                                {/* Brand header */}
                                <div className="text-center mb-6">
                                        <div className="inline-flex items-center gap-2 mb-2">
                                                <div className="h-10 w-10 rounded-lg bg-orange-500 flex items-center justify-center">
                                                        <KeyRound className="h-6 w-6 text-white" />
                                                </div>
                                                <span className="text-2xl font-bold text-slate-100">BAZSPARK</span>
                                        </div>
                                        <p className="text-sm text-slate-400">
                                                Safety-Critical Fire Alarm Engineering Platform
                                        </p>
                                </div>

                                <Card className="bg-slate-900 border-slate-700">
                                        <CardHeader>
                                                <CardTitle className="text-slate-100 flex items-center gap-2">
                                                        <LogIn className="h-5 w-5 text-orange-500" />
                                                        Sign In
                                                </CardTitle>
                                                <CardDescription className="text-slate-400">
                                                        Enter your FireAI API key to access the platform. Your key is
                                                        exchanged for a secure session cookie and never stored on disk.
                                                </CardDescription>
                                        </CardHeader>

                                        <form onSubmit={handleSubmit}>
                                                <CardContent className="space-y-4">
                                                        {error && (
                                                                <Alert variant="destructive">
                                                                        <AlertCircle className="h-4 w-4" />
                                                                        <AlertTitle>Authentication failed</AlertTitle>
                                                                        <AlertDescription>{error}</AlertDescription>
                                                                </Alert>
                                                        )}

                                                        <div className="space-y-2">
                                                                <Label htmlFor="api-key" className="text-slate-200">
                                                                        API Key
                                                                </Label>
                                                                <div className="relative">
                                                                        <Input
                                                                                id="api-key"
                                                                                type={showKey ? "text" : "password"}
                                                                                autoComplete="off"
                                                                                autoFocus
                                                                                placeholder="Paste your FireAI API key here"
                                                                                value={apiKey}
                                                                                onChange={(e) => setApiKey(e.target.value)}
                                                                                disabled={submitting}
                                                                                className="bg-slate-800 border-slate-600 text-slate-100 pr-10 font-mono"
                                                                                aria-describedby="api-key-help"
                                                                        />
                                                                        <button
                                                                                type="button"
                                                                                onClick={() => setShowKey(!showKey)}
                                                                                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200"
                                                                                aria-label={showKey ? "Hide API key" : "Show API key"}
                                                                                tabIndex={-1}
                                                                        >
                                                                                {showKey ? (
                                                                                        <EyeOff className="h-4 w-4" />
                                                                                ) : (
                                                                                        <Eye className="h-4 w-4" />
                                                                                )}
                                                                        </button>
                                                                </div>
                                                                <p id="api-key-help" className="text-xs text-slate-500">
                                                                        Your API key is set by the FIREAI_API_KEY environment variable
                                                                        on the backend at first startup.
                                                                </p>
                                                        </div>

                                                        <div className="flex items-center space-x-2">
                                                                <Checkbox
                                                                        id="remember"
                                                                        checked={remember}
                                                                        onCheckedChange={(v) => setRemember(v === true)}
                                                                        disabled={submitting}
                                                                />
                                                                <Label
                                                                        htmlFor="remember"
                                                                        className="text-sm text-slate-300 cursor-pointer"
                                                                >
                                                                        Remember key on this device (sessionStorage)
                                                                </Label>
                                                        </div>
                                                </CardContent>

                                                <CardFooter className="flex flex-col gap-3">
                                                        <Button
                                                                type="submit"
                                                                className="w-full bg-orange-500 hover:bg-orange-600 text-white"
                                                                disabled={submitting || !apiKey.trim()}
                                                        >
                                                                {submitting ? (
                                                                        <>
                                                                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                                                                Signing in...
                                                                        </>
                                                                ) : (
                                                                        <>
                                                                                <LogIn className="h-4 w-4 mr-2" />
                                                                                Sign In
                                                                        </>
                                                                )}
                                                        </Button>
                                                        <p className="text-xs text-slate-500 text-center">
                                                                By signing in, you agree to use this safety-critical system
                                                                responsibly per NFPA 72 and local AHJ requirements.
                                                        </p>
                                                </CardFooter>
                                        </form>
                                </Card>

                                <p className="text-center text-xs text-slate-600 mt-6">
                                        BAZSPARK v1.55.0 · FireAI Digital Twin · © 2026
                                </p>
                        </div>
                </div>
        );
}
