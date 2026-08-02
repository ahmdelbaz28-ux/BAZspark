/**
 * apiClient.ts — Shared base API client.
 *
 * Consolidates fetch-with-retry, timeout, CSRF injection, auth headers,
 * response unwrapping, and camelCase→snake_case transformation.
 * All API clients (api.ts, digitalTwinApi.ts, fullApi.ts, miningApi.ts,
 * selfHealingApi.ts) extend this class.
 */

import { getApiKey } from "./apiKey";
import {
        CSRF_HEADER_NAME,
        getCsrfToken,
        getCachedCsrfToken,
        invalidateCsrfToken,
} from "./csrf";

// ============================================================================
// ApiError
// ============================================================================

export class ApiError extends Error {
        status: number;
        /** True when the server returned a parseable JSON error body (a definitive application-level answer). */
        structured: boolean;
        constructor(message: string, status: number, structured = false) {
                super(message);
                this.name = "ApiError";
                this.status = status;
                this.structured = structured;
        }
}

/**
 * Extract a human-readable message from a failed HTTP response body.
 * Prefers the JSON `detail`/`message`/`error` fields (FastAPI convention),
 * falls back to the raw text. `structured` is true when the server returned
 * a parseable JSON error body — a definitive application-level answer that
 * retrying will not change.
 */
async function extractErrorBody(
        response: Response,
): Promise<{ message: string; structured: boolean }> {
        let raw = "";
        try {
                raw = await response.text();
        } catch {
                // text() unavailable (e.g. minimal test mocks) — try json() below
        }
        if (raw) {
                try {
                        const parsed = JSON.parse(raw) as Record<string, unknown> | null;
                        if (parsed && typeof parsed === "object") {
                                const msg = parsed.detail ?? parsed.message ?? parsed.error;
                                if (typeof msg === "string" && msg.trim()) {
                                        return { message: msg, structured: true };
                                }
                                if (Array.isArray(parsed.detail)) {
                                        return {
                                                message: JSON.stringify(parsed.detail),
                                                structured: true,
                                        };
                                }
                        }
                } catch {
                        // Not JSON — keep raw text as the message
                }
                return { message: raw, structured: false };
        }
        try {
                const parsed = (await response.json()) as Record<string, unknown> | null;
                if (parsed && typeof parsed === "object") {
                        const msg = parsed.detail ?? parsed.message ?? parsed.error;
                        if (typeof msg === "string" && msg.trim()) {
                                return { message: msg, structured: true };
                        }
                }
        } catch {
                // No usable JSON body
        }
        return { message: "", structured: false };
}

// ============================================================================
// CamelCase → snake_case transformer
// ============================================================================

function camelToSnake(key: string): string {
        if (!/[a-z]/.test(key) || !/[A-Z]/.test(key)) return key;
        return key.replace(/([a-z0-9])([A-Z])/g, "$1_$2").toLowerCase();
}

const FREEFORM_DATA_FIELDS = new Set([
        "metadata",
        "resolution",
        "change_a",
        "changeA",
        "change_b",
        "changeB",
]);

export function deepCamelToSnake<T>(value: T): T {
        if (value === null || value === undefined) return value;
        if (Array.isArray(value)) return value.map(deepCamelToSnake) as unknown as T;
        if (typeof value === "object" && value.constructor === Object) {
                const result: Record<string, unknown> = {};
                for (const key of Object.keys(value as Record<string, unknown>)) {
                        const snakeKey = camelToSnake(key);
                        const val = (value as Record<string, unknown>)[key];
                        if (FREEFORM_DATA_FIELDS.has(key) || FREEFORM_DATA_FIELDS.has(snakeKey)) {
                                result[snakeKey] = val;
                        } else {
                                result[snakeKey] = deepCamelToSnake(val);
                        }
                }
                return result as T;
        }
        return value;
}

// ============================================================================
// Base ApiClient
// ============================================================================

export class ApiClient {
        protected baseUrl: string;

        constructor(baseUrl?: string) {
                this.baseUrl = baseUrl || import.meta.env.VITE_API_URL || "/api/v1";
        }

        /**
         * Hook for subclasses to transform API response data.
         * Called after the {success, data, message} envelope is unwrapped.
         * api.ts overrides this to apply deepCamelToSnake.
         */
        protected transformResponse<T>(data: T): T {
                return data;
        }

        /**
         * Default headers applied to every request.
         * Subclasses can override to add custom headers (e.g. X-Client-Version).
         */
        protected getDefaultHeaders(): Record<string, string> {
                return {
                        "Content-Type": "application/json",
                };
        }

        /**
         * Core fetch-with-retry-and-timeout logic, consolidating:
         *  - 30s AbortController timeout
         *  - External signal linking (for consumer-side cancellation)
         *  - Auth header injection via getApiKey()
         *  - CSRF token injection on POST/PUT/DELETE/PATCH
         *  - CSRF 403 retry (invalidate, refresh, retry once)
         *  - Response unwrapping ({success, data, message} wrapper)
         *  - Blob/binary response detection
         *  - Retry with exponential backoff (1s, 2s, 4s)
         *  - credentials: "same-origin" for cookie-based auth
         */
        protected async fetchWithRetry<T>(  // NOSONAR — S3776: retry logic must handle many error conditions
                url: string,
                options?: RequestInit,
                retries = 3,
        ): Promise<T> {
                let lastError: Error | null = null;

                const method = (options?.method || "GET").toUpperCase();
                const needsCsrf = ["POST", "PUT", "DELETE", "PATCH"].includes(method);

                for (let attempt = 0; attempt < retries; attempt++) {
                        try {
                                const controller = new AbortController();
                                const timeout = setTimeout(() => controller.abort(), 30000);

                                // Link external signal for consumer-side cancellation
                                const externalSignal = options?.signal;
                                if (externalSignal) {
                                        if (externalSignal.aborted) {
                                                controller.abort();
                                        } else {
                                                externalSignal.addEventListener("abort", () => controller.abort(), {
                                                        once: true,
                                                });
                                        }
                                }

                                // Build headers
                                const headers: Record<string, string> = {
                                        ...this.getDefaultHeaders(),
                                };
                                const apiKey = getApiKey();
                                if (apiKey) {
                                        headers["X-API-Key"] = apiKey;
                                }
                                if (needsCsrf) {
                                        let token = getCachedCsrfToken();
                                        if (!token) token = await getCsrfToken();
                                        if (token) headers[CSRF_HEADER_NAME] = token;
                                }
                                // Merge caller headers last (can override Content-Type for file uploads)
                                if (options?.headers) {
                                        const callerHeaders = options.headers as Record<string, string>;
                                        Object.assign(headers, callerHeaders);
                                }

                                const response = await fetch(url, {
                                        ...options,
                                        headers,
                                        signal: controller.signal,
                                        credentials: "same-origin",
                                });

                                clearTimeout(timeout);

                                // CSRF 403 retry: invalidate token, refresh, retry once
                                if (response.status === 403 && needsCsrf && attempt === 0) {
                                        const body = await response.text().catch(() => "");
                                        if (
                                                body.toLowerCase().includes("csrf") ||
                                                body.toLowerCase().includes("token")
                                        ) {
                                                invalidateCsrfToken();
                                                await getCsrfToken(true);
                                                continue;
                                        }
                                }

                                if (!response.ok) {
                                        const { message, structured } = await extractErrorBody(response);
                                        throw new ApiError(
                                                message ||
                                                        `HTTP ${response.status}: ${response.statusText}`,
                                                response.status,
                                                structured,
                                        );
                                }

                                // Handle blob/binary responses
                                // (optional chaining: some environments/test mocks
                                // omit the Headers object entirely)
                                const contentType = response.headers?.get?.("content-type") || "";
                                if (
                                        contentType.includes("application/octet-stream") ||
                                        contentType.includes("application/pdf")
                                ) {
                                        return response.blob() as unknown as T;
                                }

                                const json = await response.json();

                                // Unwrap {success, data, message} envelope
                                if (
                                        json &&
                                        typeof json === "object" &&
                                        "success" in json &&
                                        "data" in json
                                ) {
                                        if (!json.success) {
                                                throw new ApiError(
                                                        json.message || "API request failed",
                                                        response.status,
                                                );
                                        }
                                        return this.transformResponse(json.data as T);
                                }

                                return this.transformResponse(json as T);
                        } catch (error) {
                                lastError = error instanceof Error ? error : new Error(String(error));

                                // Don't retry on client errors (4xx) except 429, or when the
                                // server returned a definitive structured error body (JSON
                                // detail/message) — retrying cannot change that outcome.
                                if (
                                        error instanceof ApiError &&
                                        (error.structured ||
                                                (error.status >= 400 &&
                                                        error.status < 500 &&
                                                        error.status !== 429))
                                ) {
                                        throw error;
                                }

                                // Exponential backoff: 1s, 2s, 4s
                                if (attempt < retries - 1) {
                                        const delay = 2 ** attempt * 1000;
                                        await new Promise((resolve) => setTimeout(resolve, delay));
                                }
                        }
                }

                throw lastError ?? new Error("Request failed after retries");
        }

        // ========================================================================
        // Public HTTP methods
        // ========================================================================

        async get<T>(path: string, params?: Record<string, string>): Promise<T> {
                let url = path.startsWith("http") ? path : this.baseUrl + path;
                if (params) {
                        const sep = url.includes("?") ? "&" : "?";
                        const qs = Object.entries(params)
                                .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
                                .join("&");
                        url += sep + qs;
                }
                return this.fetchWithRetry<T>(url, { method: "GET" });
        }

        async post<T>(path: string, body?: unknown): Promise<T> {
                return this.fetchWithRetry<T>(
                        path.startsWith("http") ? path : this.baseUrl + path,
                        {
                                method: "POST",
                                body: body ? JSON.stringify(body) : undefined,
                        },
                );
        }

        async put<T>(path: string, body?: unknown): Promise<T> {
                return this.fetchWithRetry<T>(
                        path.startsWith("http") ? path : this.baseUrl + path,
                        {
                                method: "PUT",
                                body: body ? JSON.stringify(body) : undefined,
                        },
                );
        }

        async patch<T>(path: string, body?: unknown): Promise<T> {
                return this.fetchWithRetry<T>(
                        path.startsWith("http") ? path : this.baseUrl + path,
                        {
                                method: "PATCH",
                                body: body ? JSON.stringify(body) : undefined,
                        },
                );
        }

        async delete<T>(path: string): Promise<T> {
                return this.fetchWithRetry<T>(
                        path.startsWith("http") ? path : this.baseUrl + path,
                        { method: "DELETE" },
                );
        }
}