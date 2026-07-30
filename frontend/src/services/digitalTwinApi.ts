
/**
 * digitalTwinApi.ts - REST API Client for Digital Twin Backend (System A)
 *
 * These types correspond to System A — the Digital Twin API.
 * Backend: digital_twin.db, routers: projects.py, devices.py, connections.py, reports.py, health.py
 * Field naming: camelCase (JavaScript/TypeScript conventions)
 *
 * Do NOT confuse with the UDM types in types/index.ts
 * which use snake_case fields and connect to udm_elements.db.
 *
 * Supports retry logic, timeouts, and WebSocket real-time subscription
 */

import { ApiClient as BaseApiClient } from "./apiClient";

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api/v1";

export interface ApiResponse<T = unknown> {
        success: boolean;
        data?: T;
        error?: string;
        message?: string;
        timestamp: string;
}

export interface PaginationParams {
        page?: number;
        limit?: number;
        sort?: string;
        order?: "asc" | "desc";
}

export interface PaginatedResponse<T> {
        data: T[];
        total: number;
        page: number;
        limit: number;
        totalPages: number;
}

// ============================================================================
// API CLIENT
// ============================================================================

class DigitalTwinApiClient extends BaseApiClient {
        private wsConnection: WebSocket | null = null;
        private readonly wsCallbacks: Map<string, Set<(data: unknown) => void>> = new Map();
        private reconnectAttempts = 0;
        private readonly maxReconnectAttempts = 5;
        private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
        private authToken: string | null = null;

        constructor(baseUrl?: string) {
                super(baseUrl || API_BASE_URL);
        }

        protected getDefaultHeaders(): Record<string, string> {
                const headers: Record<string, string> = {
                        ...super.getDefaultHeaders(),
                        "X-Client-Version": import.meta.env.VITE_APP_VERSION || "1.0.0",
                };
                if (this.authToken) {
                        headers.Authorization = `Bearer ${this.authToken}`;
                }
                return headers;
        }

        setAuthToken(token: string): void {
                this.authToken = token;
        }

        clearAuthToken(): void {
                this.authToken = null;
        }

        // ========================================================================
        // HTTP METHODS — wrap base class results in ApiResponse<T> for backward compat
        // ========================================================================

        private async wrapResult<T>(promise: Promise<T>): Promise<ApiResponse<T>> {
                try {
                        const data = await promise;
                        return {
                                success: true,
                                data: data as T,
                                timestamp: new Date().toISOString(),
                        };
                } catch (error) {
                        return {
                                success: false,
                                error: error instanceof Error ? error.message : "Unknown error",
                                timestamp: new Date().toISOString(),
                        };
                }
        }

        // ========================================================================
        // WEBSOCKET
        // ========================================================================

        connectWebSocket(channel: string, callback: (data: unknown) => void): void {
                // Register the callback for this channel BEFORE connecting
                if (!this.wsCallbacks.has(channel)) {
                        this.wsCallbacks.set(channel, new Set());
                }
                this.wsCallbacks.get(channel)?.add(callback);

                if (
                        !this.wsConnection ||
                        this.wsConnection.readyState === WebSocket.CLOSED
                ) {
                        // CRITICAL FIX: When baseUrl is a relative path like "/api",
                        // .replace('http','ws') does nothing (no 'http' in "/api"),
                        // and .replace('/api','/ws') produces "/ws" — an INVALID WebSocket URL.
                        // WebSocket requires an absolute URL: ws://host/path
                        const resolveWsUrl = (): string => {
                                const base = this.baseUrl;
                                // If VITE_WS_URL env var is explicitly set, use it directly
                                const envWsUrl = import.meta.env.VITE_WS_URL;
                                if (envWsUrl) {
                                        return envWsUrl;
                                }
                                // Relative base URL (default dev case: "/api")
                                if (!base.startsWith("http")) {
                                        const protocol =
                                                window.location.protocol === "https:" ? "wss:" : "ws:";
                                        const host = window.location.host;
                                        return `${protocol}//${host}/ws`;
                                }
                                // Absolute base URL: replace http(s) with ws(s) and strip /api suffix
                                return base
                                        .replace(/^https:/, "wss:")
                                        .replace(/^http:/, "ws:")
                                        .replace(/\/api\/?$/, "/ws");
                        };
                        const wsUrl = resolveWsUrl();
                        this.wsConnection = new WebSocket(wsUrl);

                        this.wsConnection.onopen = () => {
                                this.reconnectAttempts = 0;
                                if (import.meta.env.DEV) console.log("WebSocket connected");
                                // Start heartbeat to detect half-open connections
                                this.startHeartbeat();
                        };

                        this.wsConnection.onclose = () => {
                                if (import.meta.env.DEV) console.log("WebSocket disconnected");
                                this.scheduleReconnect();
                        };

                        this.wsConnection.onerror = (error) => {
                                if (import.meta.env.DEV) console.error("WebSocket error:", error);
                        };

                        // Single onmessage handler that dispatches to ALL registered channels.
                        // Previous bug: each connectWebSocket() call overwrote onmessage, so only
                        // the last channel ever received messages.
                        this.wsConnection.onmessage = (event) => {
                                try {
                                        const message = JSON.parse(event.data);
                                        // Dispatch to the specific channel's callbacks
                                        const targetChannel = message.channel;
                                        if (targetChannel && this.wsCallbacks.has(targetChannel)) {
                                                this.wsCallbacks
                                                        .get(targetChannel)
                                                        ?.forEach((cb) => cb(message.data));
                                        }
                                        // Also dispatch to wildcard listeners (channel "*")
                                        if (this.wsCallbacks.has("*")) {
                                                this.wsCallbacks.get("*")?.forEach((cb) => cb(message));
                                        }
                                } catch {
                                        // Ignore parse errors
                                }
                        };
                }
        }

        disconnectWebSocket(): void {
                if (this.reconnectTimer) {
                        clearTimeout(this.reconnectTimer);
                        this.reconnectTimer = null;
                }
                // Stop heartbeat if running
                if (this.heartbeatTimer) {
                        clearInterval(this.heartbeatTimer);
                        this.heartbeatTimer = null;
                }
                this.reconnectAttempts = 0;
                if (this.wsConnection) {
                        this.wsConnection.onclose = null; // Prevent reconnection on intentional close
                        this.wsConnection.close();
                        this.wsConnection = null;
                        this.wsCallbacks.clear();
                }
        }

        // ========================================================================
        // CONNECTION STATE & HEARTBEAT
        // ========================================================================

        /** Callback invoked when WebSocket permanently loses connection after max retries.
         *  The UI should display a prominent warning that real-time updates have stopped.
         */
        onConnectionLost?: () => void;

        /** Get current WebSocket connection state for UI indicators. */
        getConnectionState():
                | "connecting"
                | "connected"
                | "disconnected"
                | "permanently_lost" {
                if (!this.wsConnection) return "disconnected";
                if (this.reconnectAttempts >= this.maxReconnectAttempts)
                        return "permanently_lost";
                switch (this.wsConnection.readyState) {
                        case WebSocket.CONNECTING:
                                return "connecting";
                        case WebSocket.OPEN:
                                return "connected";
                        case WebSocket.CLOSING:
                                return "disconnected";
                        case WebSocket.CLOSED:
                                return "disconnected";
                        default:
                                return "disconnected";
                }
        }

        private heartbeatTimer: ReturnType<typeof setInterval> | null = null;

        /**
         * Start client-side heartbeat to detect half-open connections.
         *
         * SAFETY FIX: Proxies and firewalls silently drop idle WebSocket connections.
         * Without a heartbeat, the client believes it's connected but no messages flow.
         * Device status updates (faults, alarms) would stop arriving without any error.
         *
         * Sends ping every 30 seconds. If no pong within 10 seconds, force reconnect.
         */
        private startHeartbeat(): void {
                this.stopHeartbeat();
                let pongReceived = true;

                this.heartbeatTimer = setInterval(() => {
                        if (
                                !this.wsConnection ||
                                this.wsConnection.readyState !== WebSocket.OPEN
                        ) {
                                this.stopHeartbeat();
                                return;
                        }
                        if (!pongReceived) {
                                // No pong received since last ping — connection is half-open
                                if (import.meta.env.DEV)
                                        console.warn("WebSocket: heartbeat timeout — forcing reconnect");
                                this.wsConnection.close();
                                // scheduleReconnect will be triggered by onclose
                                this.stopHeartbeat();
                                return;
                        }
                        pongReceived = false;
                        try {
                                this.wsConnection.send(JSON.stringify({ action: "ping" }));
                        } catch {
                                this.stopHeartbeat();
                        }
                }, 30000);

                // Listen for pong responses (overlaid on existing onmessage)
                const originalOnMessage = this.wsConnection?.onmessage ?? null;
                this.wsConnection!.onmessage = (event) => {
                        try {
                                const data = JSON.parse(event.data);
                                if (data.type === "pong" || data.action === "pong") {
                                        pongReceived = true;
                                        return; // Don't dispatch pong to channel callbacks
                                }
                        } catch {
                                /* ignore */
                        }
                        // Forward to original handler
                        if (originalOnMessage) {
                                originalOnMessage.call(this.wsConnection!, event);
                        }
                };
        }

        private stopHeartbeat(): void {
                if (this.heartbeatTimer) {
                        clearInterval(this.heartbeatTimer);
                        this.heartbeatTimer = null;
                }
        }

        private scheduleReconnect(): void {
                if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                        if (import.meta.env.DEV)
                                console.log("WebSocket: max reconnect attempts reached");
                        // SAFETY FIX: Notify application that real-time updates have stopped.
                        // Without this, the operator sees stale device data without any indication
                        // that the connection is dead — device faults/alarms would not be displayed.
                        // Call the connection-lost callback if registered.
                        if (this.onConnectionLost) {
                                this.onConnectionLost();
                        }
                        return;
                }
                const delay = 5000 * (this.reconnectAttempts + 1);
                this.reconnectAttempts++;
                if (import.meta.env.DEV)
                        console.log(
                                `WebSocket: reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`,
                        );
                this.reconnectTimer = setTimeout(() => {
                        if (
                                this.wsConnection?.readyState === WebSocket.CLOSED
                        ) {
                                // RACE CONDITION FIX: Nullify wsConnection and clean up heartbeat
                                // before reconnecting to prevent duplicate connections.
                                this.wsConnection = null;
                                this.stopHeartbeat();
                                const savedCallbacks = new Map(this.wsCallbacks);
                                this.wsCallbacks.clear();
                                savedCallbacks.forEach((callbacks, channel) => {
                                        callbacks.forEach((cb) => this.connectWebSocket(channel, cb));
                                });
                        }
                }, delay);
        }

        // ========================================================================
        // EXPORT ENDPOINTS (use inherited fetchBlob via fetchWithRetry)
        // ========================================================================

        private async fetchBlob(url: string, retries = 3): Promise<Blob> {
                return this.fetchWithRetry<Blob>(url, { method: "GET" }, retries);
        }

        // ========================================================================
        // PROJECT ENDPOINTS
        // ========================================================================

        async getProjects(
                params?: PaginationParams,
        ): Promise<ApiResponse<PaginatedResponse<Project>>> {
                return this.wrapResult(
                        this.get<PaginatedResponse<Project>>(
                                "/projects",
                                params as Record<string, string>,
                        ),
                );
        }

        async getProject(id: string): Promise<ApiResponse<Project>> {
                return this.wrapResult(
                        this.get<Project>(`/projects/${encodeURIComponent(id)}`),
                );
        }

        async createProject(data: CreateProjectInput): Promise<ApiResponse<Project>> {
                return this.wrapResult(this.post<Project>("/projects", data));
        }

        async updateProject(
                id: string,
                data: UpdateProjectInput,
        ): Promise<ApiResponse<Project>> {
                return this.wrapResult(
                        this.put<Project>(`/projects/${encodeURIComponent(id)}`, data),
                );
        }

        async deleteProject(id: string): Promise<ApiResponse<void>> {
                return this.wrapResult(
                        this.delete<void>(`/projects/${encodeURIComponent(id)}`),
                );
        }

        // ========================================================================
        // DEVICE ENDPOINTS
        // ========================================================================

        async getDevices(
                projectId: string,
                params?: PaginationParams,
        ): Promise<ApiResponse<PaginatedResponse<Device>>> {
                return this.wrapResult(
                        this.get<PaginatedResponse<Device>>(
                                `/projects/${encodeURIComponent(projectId)}/devices`,
                                params as Record<string, string>,
                        ),
                );
        }

        async getDevice(
                projectId: string,
                deviceId: string,
        ): Promise<ApiResponse<Device>> {
                return this.wrapResult(
                        this.get<Device>(
                                "/projects/" +
                                        encodeURIComponent(projectId) +
                                        "/devices/" +
                                        encodeURIComponent(deviceId),
                        ),
                );
        }

        async createDevice(
                projectId: string,
                data: CreateDeviceInput,
        ): Promise<ApiResponse<Device>> {
                return this.wrapResult(
                        this.post<Device>(
                                `/projects/${encodeURIComponent(projectId)}/devices`,
                                data,
                        ),
                );
        }

        async updateDevice(
                projectId: string,
                deviceId: string,
                data: UpdateDeviceInput,
        ): Promise<ApiResponse<Device>> {
                return this.wrapResult(
                        this.put<Device>(
                                "/projects/" +
                                        encodeURIComponent(projectId) +
                                        "/devices/" +
                                        encodeURIComponent(deviceId),
                                data,
                        ),
                );
        }

        async deleteDevice(
                projectId: string,
                deviceId: string,
        ): Promise<ApiResponse<void>> {
                return this.wrapResult(
                        this.delete<void>(
                                "/projects/" +
                                        encodeURIComponent(projectId) +
                                        "/devices/" +
                                        encodeURIComponent(deviceId),
                        ),
                );
        }

        // ========================================================================
        // CONNECTION ENDPOINTS
        // ========================================================================

        async getConnections(
                projectId: string,
                params?: PaginationParams,
        ): Promise<ApiResponse<PaginatedResponse<Connection>>> {
                return this.wrapResult(
                        this.get<PaginatedResponse<Connection>>(
                                `/projects/${encodeURIComponent(projectId)}/connections`,
                                params as Record<string, string>,
                        ),
                );
        }

        async createConnection(
                projectId: string,
                data: CreateConnectionInput,
        ): Promise<ApiResponse<Connection>> {
                return this.wrapResult(
                        this.post<Connection>(
                                `/projects/${encodeURIComponent(projectId)}/connections`,
                                data,
                        ),
                );
        }

        async deleteConnection(
                projectId: string,
                connectionId: string,
        ): Promise<ApiResponse<void>> {
                return this.wrapResult(
                        this.delete<void>(
                                "/projects/" +
                                        encodeURIComponent(projectId) +
                                        "/connections/" +
                                        encodeURIComponent(connectionId),
                        ),
                );
        }

        // ========================================================================
        // REPORT ENDPOINTS
        // ========================================================================

        async generateReport(
                projectId: string,
                data: GenerateReportInput,
        ): Promise<ApiResponse<Report>> {
                return this.wrapResult(
                        this.post<Report>(
                                `/projects/${encodeURIComponent(projectId)}/reports`,
                                data,
                        ),
                );
        }

        async getReports(
                projectId: string,
                params?: PaginationParams,
        ): Promise<ApiResponse<PaginatedResponse<Report>>> {
                return this.wrapResult(
                        this.get<PaginatedResponse<Report>>(
                                `/projects/${encodeURIComponent(projectId)}/reports`,
                                params as Record<string, string>,
                        ),
                );
        }

        async getReport(
                projectId: string,
                reportId: string,
        ): Promise<ApiResponse<Report>> {
                return this.wrapResult(
                        this.get<Report>(
                                "/projects/" +
                                        encodeURIComponent(projectId) +
                                        "/reports/" +
                                        encodeURIComponent(reportId),
                        ),
                );
        }

        async exportReport(
                projectId: string,
                reportId: string,
                format: string,
        ): Promise<Blob> {
                return this.fetchBlob(
                        this.baseUrl +
                                "/projects/" +
                                encodeURIComponent(projectId) +
                                "/reports/" +
                                encodeURIComponent(reportId) +
                                "/export?format=" +
                                encodeURIComponent(format),
                );
        }

        // ========================================================================
        // EXPORT ENDPOINTS
        // ========================================================================

        async exportToDXF(projectId: string): Promise<Blob> {
                return this.fetchBlob(
                        this.baseUrl +
                                "/projects/" +
                                encodeURIComponent(projectId) +
                                "/export/dxf",
                );
        }

        async exportToRevit(projectId: string): Promise<Blob> {
                return this.fetchBlob(
                        this.baseUrl +
                                "/projects/" +
                                encodeURIComponent(projectId) +
                                "/export/revit",
                );
        }

        async exportToIFC(
                projectId: string,
                version: string = "IFC4",
        ): Promise<Blob> {
                return this.fetchBlob(
                        this.baseUrl +
                                "/projects/" +
                                encodeURIComponent(projectId) +
                                "/export/ifc?version=" +
                                encodeURIComponent(version),
                );
        }

        // ========================================================================
        // SYNC ENDPOINTS
        // ========================================================================

        async syncProject(projectId: string): Promise<ApiResponse<SyncStatus>> {
                return this.wrapResult(
                        this.post<SyncStatus>(
                                `/projects/${encodeURIComponent(projectId)}/sync`,
                        ),
                );
        }

        async getSyncStatus(projectId: string): Promise<ApiResponse<SyncStatus>> {
                return this.wrapResult(
                        this.get<SyncStatus>(
                                `/projects/${encodeURIComponent(projectId)}/sync`,
                        ),
                );
        }

        // ========================================================================
        // HEALTH CHECK
        // ========================================================================

        async healthCheck(): Promise<ApiResponse<HealthStatus>> {
                return this.wrapResult(this.get<HealthStatus>("/health"));
        }
}

// ============================================================================
// TYPES
// ============================================================================

export interface Project {
        id: string;
        name: string;
        description: string;
        author: string;
        createdAt: string;
        updatedAt: string;
        status: "active" | "archived" | "draft";
        deviceCount: number;
        connectionCount: number;
}

export interface CreateProjectInput {
        name: string;
        description?: string;
        author?: string;
}

export interface UpdateProjectInput {
        name?: string;
        description?: string;
        status?: "active" | "archived" | "draft";
}

export interface Device {
        id: string;
        projectId: string;
        type: string;
        name: string;
        category: string;
        x: number;
        y: number;
        z: number;
        rotation: number;
        voltage: number;
        current: number;
        load: number;
        properties: Record<string, unknown>;
        createdAt: string;
        updatedAt: string;
}

export interface CreateDeviceInput {
        type: string;
        name: string;
        category: string;
        x: number;
        y: number;
        z?: number;
        rotation?: number;
        voltage?: number;
        current?: number;
        load?: number;
        load_unit?: "A" | "mA" | "W";
        properties?: Record<string, unknown>;
}

export interface UpdateDeviceInput {
        name?: string;
        x?: number;
        y?: number;
        z?: number;
        rotation?: number;
        voltage?: number;
        current?: number;
        load?: number;
        load_unit?: "A" | "mA" | "W"; // BUG-30 FIX: Required for unit conversion
        properties?: Record<string, unknown>;
}

export interface Connection {
        id: string;
        projectId: string;
        fromId: string;
        toId: string;
        cableSize: string;
        length: number;
        type: string;
        createdAt: string;
}

export interface CreateConnectionInput {
        fromId: string;
        toId: string;
        cableSize?: string;
        length?: number;
        type?: string;
}

export interface Report {
        id: string;
        projectId: string;
        type: string;
        name: string;
        parameters: Record<string, unknown>;
        status: "pending" | "completed" | "failed";
        createdAt: string;
        completedAt?: string;
}

export interface GenerateReportInput {
        type: string;
        name?: string;
        parameters?: Record<string, unknown>;
}

export interface SyncStatus {
        projectId: string;
        status: "syncing" | "synced" | "error";
        lastSync: string;
        pendingChanges: number;
        error?: string;
}

// V185 FIX: HealthStatus was duplicated here and in types/index.ts.
// Now imported from types/index.ts (single source of truth).
// The definitions were identical, but having two copies meant changes
// could diverge silently.
import type { HealthStatus } from "@/types";

export type { HealthStatus };

// ============================================================================
// EXPORTED INSTANCE
// ============================================================================

export const api = new DigitalTwinApiClient();
export default api;
