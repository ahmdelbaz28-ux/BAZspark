/**
 * @file apiKey.ts
 * @description Single source of truth for API key retrieval.
 *
 * V256 SECURITY FIX: The sessionStorage fallback has been REMOVED.
 * V288 SECURITY FIX: The VITE_FIREAI_API_KEY fallback has been REMOVED.
 * Vite inlines VITE_ env vars at build time into the JS bundle, making
 * them visible in DevTools. This is a client-only SPA (no SSR), so the
 * env var path was never reachable in production anyway.
 *
 * The canonical auth flow uses an HttpOnly session cookie set by
 * POST /auth/login, which JavaScript cannot read. All fetch calls use
 * credentials: "same-origin" so the cookie is sent automatically.
 *
 * Storing API keys in XSS-accessible storage (env vars, sessionStorage,
 * localStorage) gave full account takeover on a single XSS.
 */

/**
 * Get the API key for backend authentication.
 *
 * This is a client-only SPA with no SSR. API keys must NOT be embedded
 * in the bundle. The HttpOnly session cookie is used instead.
 *
 * @returns Always null — use the HttpOnly session cookie for auth.
 */
export function getApiKey(): string | null {
	return null;
}
