
import type {
        Conflict,
        ConflictsListParams,
        ConnectionCreate,
        ConnectionsListParams,
        Element,
        ElementCreate,
        ElementsListParams,
        ElementUpdate,
        HealthStatus,
        ProjectCreate,
        ProjectUpdate,
        Statistics,
        UdmConnection,
        UdmPaginatedData,
        UdmProject,
} from "@/types";
import { ApiClient as BaseApiClient, ApiError, deepCamelToSnake } from "./apiClient";

// V187 FIX: Use VITE_API_URL env var (same pattern as digitalTwinApi.ts).
// Previously this was hardcoded to '/api/v1' (relative), which caused all
// API requests to go to the Vercel frontend domain instead of the backend.
// On Vercel, '/api/v1/conflicts/detect' returned 405 (Method Not Allowed)
// because Vercel serves static files and doesn't accept POST to SPA routes.
// Now uses the same env var as digitalTwinApi.ts, which is set to the HF
// Space backend URL in production.
const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

// camelCase→snake_case transformer is now in apiClient.ts (deepCamelToSnake).
// The subclass overrides transformResponse() to apply it automatically.

/**
 * M-3 FIX: Session-based auth with HttpOnly cookie.
 *
 * The API key is NO LONGER stored in sessionStorage (which is XSS-readable).
 * Instead, the frontend calls POST /api/v1/auth/login once, which sets an
 * HttpOnly cookie that the browser automatically attaches to all subsequent
 * requests. JavaScript cannot read the cookie, so XSS cannot steal the key.
 *
 * For backwards compatibility:
 *  - VITE_FIREAI_API_KEY env var still works (for SSR / CLI / headless builds)
 *  - sessionStorage 'fireai_settings' still works (legacy, deprecated, will be removed in v2)
 *  - If neither is set, the browser cookie handles auth automatically (no header needed)
 */
// V184: getApiKey() is now imported from ./apiKey (line 19). The local
// duplicate definition was removed to avoid a redeclaration error.

/**
 * M-3: Login with API key to establish an HttpOnly session cookie.
 * After calling this, all subsequent API requests will be authenticated
 * via the cookie — no need to set X-API-Key header manually.
 *
 * @returns The user's role if login succeeds, throws ApiError otherwise.
 */
export async function login(apiKey: string): Promise<{ role: string }> {
        const resp = await fetch(`${API_BASE}/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "same-origin",
                body: JSON.stringify({ api_key: apiKey }),
        });
        if (!resp.ok) {
                const body = await resp.json().catch(() => ({}));
                throw new ApiError(
                        body.message || body.detail || "Login failed",
                        resp.status,
                );
        }
        const body = await resp.json();
        return body.data;
}

/**
 * M-3: Logout — clears the session cookie.
 */
export async function logout(): Promise<void> {
        await fetch(`${API_BASE}/auth/logout`, {
                method: "POST",
                credentials: "same-origin",
        });
}

/**
 * M-3: Check current session — returns the role if authenticated.
 */
export async function getCurrentUser(): Promise<{ role: string } | null> {
        const resp = await fetch(`${API_BASE}/auth/me`, {
                credentials: "same-origin",
        });
        if (!resp.ok) return null;
        const body = await resp.json();
        return body.data;
}

class ApiClient extends BaseApiClient {
        constructor() {
                super(API_BASE);
        }

        protected transformResponse<T>(data: T): T {
                return deepCamelToSnake(data);
        }

        // ===== Elements API =====

        async getElements(
                params?: ElementsListParams,
        ): Promise<UdmPaginatedData<Element>> {
                const searchParams = new URLSearchParams();
                if (params?.element_type)
                        searchParams.set("element_type", params.element_type);
                if (params?.project_id) searchParams.set("project_id", params.project_id);
                if (params?.is_deleted !== undefined)
                        searchParams.set("is_deleted", String(params.is_deleted));
                if (params?.page !== undefined)
                        searchParams.set("page", String(params.page));
                if (params?.page_size !== undefined)
                        searchParams.set("page_size", String(params.page_size));
                if (params?.sort_by) searchParams.set("sort_by", params.sort_by);
                if (params?.sort_order) searchParams.set("sort_order", params.sort_order);
                const query = searchParams.toString();
                return this.get<UdmPaginatedData<Element>>(
                        `/elements${query ? `?${query}` : ""}`,
                );
        }

        async getElement(id: string): Promise<Element> {
                return this.get<Element>(`/elements/${encodeURIComponent(id)}`);
        }

        async createElement(data: ElementCreate): Promise<Element> {
                return this.post<Element>("/elements", data);
        }

        async updateElement(id: string, data: ElementUpdate): Promise<Element> {
                return this.put<Element>(`/elements/${encodeURIComponent(id)}`, data);
        }

        async deleteElement(id: string): Promise<void> {
                await this.delete<void>(`/elements/${encodeURIComponent(id)}`);
        }

        // ===== Projects API =====
        // The /api/projects endpoint is served by System A (Digital Twin backend).
        // System A returns project objects with these fields (camelCase from backend,
        // now transformed to snake_case by deepCamelToSnake in fetchWithRetry):
        //   {id, name, description, author, created_at, updated_at, status, device_count, connection_count}
        // The api.ts client uses snake_case UdmProject type from @/types:
        //   {project_id, name, description, status, metadata, element_count, created_timestamp, last_modified_timestamp}
        // We MUST map field names here because System A uses `id` (not `project_id`)
        // and `device_count` (not `element_count`) — these are semantic mismatches
        // that a generic camelToSnake transformer cannot fix.
        //
        // V189 FIX: After adding deepCamelToSnake transformer in fetchWithRetry,
        // the raw object now has snake_case keys (created_at, not createdAt).
        // Updated _mapProjectFromSystemA to read snake_case keys.

        /** Map a System A project object to the System B Project type expected by @/types */
        private _mapProjectFromSystemA(raw: Record<string, unknown>): UdmProject {
                return {
                        project_id: (raw.id as string) || (raw.project_id as string) || "",
                        name: (raw.name as string) || "",
                        description: (raw.description as string) || undefined,
                        status: (raw.status as string) || "draft",
                        metadata: raw.author ? { author: raw.author } : undefined,
                        element_count:
                                (raw.device_count as number) ??
                                (raw.deviceCount as number) ??
                                (raw.element_count as number) ??
                                0,
                        created_timestamp:
                                (raw.created_at as string) ??
                                (raw.createdAt as string) ??
                                (raw.created_timestamp as string) ??
                                null,
                        last_modified_timestamp:
                                (raw.updated_at as string) ??
                                (raw.updatedAt as string) ??
                                (raw.last_modified_timestamp as string) ??
                                null,
                };
        }

        async getProjects(params?: {
                status?: string;
                page?: number;
                page_size?: number;
        }): Promise<UdmPaginatedData<UdmProject>> {
                const searchParams = new URLSearchParams();
                if (params?.status) searchParams.set("status", params.status);
                if (params?.page !== undefined) {
                        searchParams.set("page", String(params.page));
                }
                // System A uses 'limit' not 'page_size' — convert for compatibility
                if (params?.page_size !== undefined) {
                        searchParams.set("limit", String(params.page_size));
                }
                const query = searchParams.toString();
                const url = query ? `/projects?${query}` : "/projects";
                const raw = await this.get<{
                        data: Record<string, unknown>[];
                        total: number;
                        page: number;
                        limit: number;
                        total_pages: number;
                        totalPages: number;
                }>(url);
                const mappedProjects = (raw.data || []).map((p) =>
                        this._mapProjectFromSystemA(p),
                );
                return {
                        items: mappedProjects,
                        total: raw.total,
                        page: raw.page,
                        page_size: raw.limit,
                        total_pages: raw.total_pages ?? raw.totalPages ?? 0,
                };
        }

        async getProject(id: string): Promise<UdmProject> {
                const raw = await this.get<Record<string, unknown>>(
                        `/projects/${encodeURIComponent(id)}`,
                );
                return this._mapProjectFromSystemA(raw);
        }

        async createProject(data: ProjectCreate): Promise<UdmProject> {
                const raw = await this.post<Record<string, unknown>>("/projects", data);
                return this._mapProjectFromSystemA(raw);
        }

        async updateProject(id: string, data: ProjectUpdate): Promise<UdmProject> {
                const raw = await this.put<Record<string, unknown>>(
                        `/projects/${encodeURIComponent(id)}`,
                        data,
                );
                return this._mapProjectFromSystemA(raw);
        }

        async deleteProject(id: string): Promise<void> {
                await this.delete<void>(`/projects/${encodeURIComponent(id)}`);
        }

        // ===== Connections API =====

        async getConnections(
                params?: ConnectionsListParams,
        ): Promise<UdmPaginatedData<UdmConnection>> {
                const searchParams = new URLSearchParams();
                if (params?.project_id) searchParams.set("project_id", params.project_id);
                if (params?.element_id) searchParams.set("element_id", params.element_id);
                if (params?.relationship_type)
                        searchParams.set("relationship_type", params.relationship_type);
                if (params?.page !== undefined)
                        searchParams.set("page", String(params.page));
                if (params?.page_size !== undefined)
                        searchParams.set("page_size", String(params.page_size));
                const query = searchParams.toString();
                return this.get<UdmPaginatedData<UdmConnection>>(
                        `/connections${query ? `?${query}` : ""}`,
                );
        }

        async createConnection(data: ConnectionCreate): Promise<UdmConnection> {
                return this.post<UdmConnection>("/connections", data);
        }

        async updateConnection(
                id: string,
                data: Partial<ConnectionCreate>,
        ): Promise<UdmConnection> {
                return this.put<UdmConnection>(
                        `/connections/${encodeURIComponent(id)}`,
                        data,
                );
        }

        async deleteConnection(id: string): Promise<void> {
                await this.delete<void>(`/connections/${encodeURIComponent(id)}`);
        }

        // ===== Conflicts API =====

        async getConflicts(
                params?: ConflictsListParams,
        ): Promise<UdmPaginatedData<Conflict>> {
                const searchParams = new URLSearchParams();
                if (params?.resolved !== undefined)
                        searchParams.set("resolved", String(params.resolved));
                if (params?.conflict_type)
                        searchParams.set("conflict_type", params.conflict_type);
                if (params?.page !== undefined)
                        searchParams.set("page", String(params.page));
                if (params?.page_size !== undefined)
                        searchParams.set("page_size", String(params.page_size));
                const query = searchParams.toString();
                return this.get<UdmPaginatedData<Conflict>>(
                        `/conflicts${query ? `?${query}` : ""}`,
                );
        }

        async detectConflicts(): Promise<Conflict[]> {
                return this.post<Conflict[]>("/conflicts/detect");
        }

        async resolveConflict(id: string, strategy: string): Promise<Conflict> {
                return this.post<Conflict>(
                        `/conflicts/${encodeURIComponent(id)}/resolve`,
                        { strategy },
                );
        }

        // ===== Reports / Statistics API =====

        async getStatistics(): Promise<Statistics> {
                return this.get<Statistics>("/reports/statistics");
        }

        // ===== Health API =====

        async healthCheck(): Promise<HealthStatus> {
                return this.get<HealthStatus>("/health");
        }
}

export const api = new ApiClient();
export { ApiError };
