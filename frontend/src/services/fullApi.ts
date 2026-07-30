
/**
 * fullApi.ts — Comprehensive API client covering ALL backend endpoints.
 *
 * V140 Phase 5: This module provides typed methods for every backend API
 * endpoint (188 total across 23 routers). Pages import from here instead
 * of maintaining scattered inline fetch() calls.
 *
 * Categories:
 *   - Core CRUD: projects, devices, connections, elements, conflicts, reports
 *   - Engineering: qomn (smoke/heat spacing, battery, voltage drop, detectors)
 *   - FACP: panel selection, verification, scheduling
 *   - Environment: weather, geocode, air quality, hazmat, severe weather
 *   - Revit: 32 endpoints (connect, elements CRUD, families, search)
 *   - AutoCAD: 13 endpoints (connect, draw, entity CRUD)
 *   - Digital Twin: convert, history, mappings, config
 *   - Monitor: health, metrics, engine status, alerts
 *   - Workflow: start, approve, reject, audit
 *   - Memory: store, search, history
 *   - V2: generative design, BIM, IFC43, AR, webhooks, topology, graphrag
 *   - Marine: 14 endpoints (ship design, zones, extinguishing, alarm logic)
 *   - API Keys: CRUD, roles
 *   - Exports: DXF, Revit, IFC
 *   - Health & Cache
 */

import { ApiClient } from "./apiClient";
import { getApiKey } from "./apiKey";
import {
        CSRF_HEADER_NAME,
        getCachedCsrfToken,
        getCsrfToken,
} from "./csrf";

// ─── Types ──────────────────────────────────────────────────────────────────

export interface ApiResponse<T> {
        success: boolean;
        data: T;
        message?: string;
        timestamp?: string;
}

export interface PaginatedResponse<T> {
        data: T[];
        total: number;
        page: number;
        limit: number;
        totalPages: number;
}

// ─── Digital Twin types (moved from digitalTwinService.ts) ──────────────────

export interface ConversionResult {
        success: boolean;
        source_file: string;
        target_file: string;
        conversion_type: string;
        elements_count: number;
        duration_seconds: number;
}

export interface VersionInfo {
        version_id: string;
        timestamp: string;
        source_file: string;
        target_file: string;
        conversion_type: "autocad_to_revit" | "revit_to_autocad";
        elements_count: number;
        status: "success" | "partial" | "failed";
}

// ─── API Base Configuration ─────────────────────────────────────────────────

// V187 FIX: Use VITE_API_URL env var (same pattern as digitalTwinApi.ts).
// Previously hardcoded to '/api/v1' which broke POST requests on Vercel.
const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";
const API_V2_BASE = `${(import.meta.env.VITE_API_URL || "/api").replace("/v1", "")}/v2`;

/**
 * Shared ApiClient subclass that exposes a public `call` method matching
 * the original standalone `apiCall` signature for backward compatibility.
 */
class FullApiClient extends ApiClient {
        async call<T>(
                path: string,
                options: RequestInit = {},
                baseUrl: string = API_BASE,
                retries = 3,
        ): Promise<T> {
                const url = path.startsWith("http") ? path : baseUrl + path;
                return this.fetchWithRetry<T>(url, options, retries);
        }
}

const client = new FullApiClient();

/** Unifies auth, CSRF, timeout, retry for all fullApi endpoints. */
export async function apiCall<T>(
        path: string,
        options: RequestInit = {},
        baseUrl: string = API_BASE,
        retries = 3,
): Promise<T> {
        return client.call<T>(path, options, baseUrl, retries);
}

// ─── Engineering API (QOMN) ─────────────────────────────────────────────────

/**
 * V270 FIX (systematic-debugging): QOMNCalculatorPage was previously
 * pure client-side math with NO backend calls — 9 backend NFPA 72
 * calculation endpoints were orphaned. Wiring them here so the page can
 * call the authoritative server-side kernel (with IEEE-754 deterministic
 * audit trail) instead of relying on a JS reimplementation.
 *
 * Each method maps 1:1 to a backend endpoint defined in
 * backend/routers/qomn.py. Inputs use SI units (meters, m², Amperes)
 * to match the backend Pydantic models. The page handles unit conversion.
 */
export const qomnApi = {
        /** POST /qomn/smoke-spacing — NFPA 72 §17.7.3.2.4 smoke detector spacing */
        smokeSpacing: (data: { ceiling_height_m: number }) =>
                apiCall("/qomn/smoke-spacing", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /qomn/heat-spacing — NFPA 72 §17.6.3.1 heat detector spacing */
        heatSpacing: (data: { ceiling_height_m: number; area_per_detector_m2: number }) =>
                apiCall("/qomn/heat-spacing", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /qomn/battery — NFPA 72 §10.6.7.2.1 battery capacity */
        battery: (data: {
                standby_load_a: number;
                alarm_load_a: number;
                standby_hours?: number;
                alarm_minutes?: number;
                safety_factor?: number;
                efficiency?: number;
        }) =>
                apiCall("/qomn/battery", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /qomn/voltage-drop — Calculate voltage drop (NEC Ch.9 Table 8) */
        voltageDrop: (data: {
                current_a: number;
                length_m: number;
                awg_gauge: string;
                supply_voltage_v?: number;
                max_drop_pct?: number;
        }) =>
                apiCall("/qomn/voltage-drop", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /qomn/physics-guards — List all physics guard limits */
        getPhysicsGuards: () =>
                apiCall("/qomn/physics-guards", { method: "GET" }),

        /** GET /qomn/constants — List NFPA 72 / NEC constants used by the kernel */
        getConstants: () =>
                apiCall("/qomn/constants", { method: "GET" }),

        /** GET /qomn/audit — Export the QOMN audit log (AHJ access) */
        getAudit: () =>
                apiCall("/qomn/audit", { method: "GET" }),

};


// ─── LLM / AI Copilot API ────────────────────────────────────────────────────

/** Response from POST /llm/chat (unwrapped from {success, data} envelope) */
export interface LLMChatResponse {
        content: string;
        model: string;
        source: string;
        finish_reason: string;
        prompt_tokens: number;
        completion_tokens: number;
        total_tokens: number;
        disclaimer: string;
}

export const llmApi = {
        /**
         * POST /llm/chat/stream — Stream a chat completion via SSE.
         * Calls onChunk for each token, onDone when complete, onError on failure.
         */
        chatStream: async (
                data: {
                        prompt: string;
                        system?: string;
                        model?: string;
                        temperature?: number;
                        max_tokens?: number;
                },
                signal: AbortSignal,
                onChunk: (chunk: string) => void,
                onDone: (done: { content: string; model: string; source: string }) => void,
                onError: (message: string) => void,
        ): Promise<void> => {
                const apiKey = getApiKey();
                const headers: Record<string, string> = {
                        "Content-Type": "application/json",
                };
                if (apiKey) {
                        headers["X-API-Key"] = apiKey;
                }
                // SECURITY FIX: Inject CSRF token for POST request (bypassed apiCall)
                let csrfToken = getCachedCsrfToken();
                if (!csrfToken) csrfToken = await getCsrfToken();
                if (csrfToken) headers[CSRF_HEADER_NAME] = csrfToken;

                try {
                        const response = await fetch(
                                `${API_BASE}/llm/chat/stream`,
                                {
                                        method: "POST",
                                        headers,
                                        body: JSON.stringify(data),
                                        signal,
                                        credentials: "same-origin",
                                },
                        );

                        if (!response.ok) {
                                const errorBody = await response.json().catch(() => ({}));
                                throw new Error(
                                        errorBody?.detail?.message ||
                                                errorBody?.detail ||
                                                `HTTP ${response.status}`,
                                );
                        }

                        const reader = response.body?.getReader();
                        if (!reader) {
                                throw new Error("No response body for streaming");
                        }

                        const decoder = new TextDecoder();
                        let buffer = "";

                        while (true) {
                                const { done, value } = await reader.read();
                                if (done) break;

                                buffer += decoder.decode(value, { stream: true });

                                // Parse SSE events (separated by \n\n)
                                const lines = buffer.split("\n\n");
                                buffer = lines.pop() || ""; // Keep incomplete chunk in buffer

                                for (const line of lines) {
                                        if (!line.startsWith("data: ")) continue;
                                        const jsonStr = line.slice(6).trim();
                                        if (!jsonStr) continue;

                                        try {
                                                const event = JSON.parse(jsonStr);
                                                if (event.type === "chunk") {
                                                        onChunk(event.content);
                                                } else if (event.type === "done") {
                                                        onDone({
                                                                content: event.content,
                                                                model: event.model,
                                                                source: event.source,
                                                        });
                                                } else if (event.type === "error") {
                                                        onError(event.message || "Stream error");
                                                        return;
                                                }
                                        } catch {
                                                // Skip malformed JSON
                                        }
                                }
                        }
                } catch (err: unknown) {
                        if (err instanceof Error && err.name === "AbortError") {
                                return; // Silent abort
                        }
                        throw err;
                }
        },

        /** POST /llm/explain — Explain a calculation result */
        explain: (data: {
                calculation_type: string;
                calculation_result: Record<string, unknown>;
                question?: string;
        }) =>
                apiCall<LLMChatResponse>("/llm/explain", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

};

// ─── FACP API ───────────────────────────────────────────────────────────────

export const facpApi = {
        /** POST /facp/select — Select FACP panel (V216 FIX: aligned schema) */
        select: (data: {
                device_count: number;
                nac_circuit_count: number;
                building_size_m2: number;
                building_floors: number;
                requires_network?: boolean;
                requires_voice?: boolean;
                requires_releasing?: boolean;
                jurisdiction?: string;
                preferred_manufacturer?: string | null;
                min_temperature_c?: number;
        }) =>
                apiCall("/facp/select", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /facp/panels — List all FACP panels */
        getPanels: () => apiCall("/facp/panels"),
};

// ─── Environment API ────────────────────────────────────────────────────────

export const environmentApi = {
        /** GET /environment/countries */

        /** GET /environment/weather?lat=&lon= */
        getWeather: (lat: number, lon: number) =>
                apiCall(`/environment/weather?lat=${lat}&lon=${lon}`),

        /** GET /environment/geocode?address= */
        geocode: (address: string) =>
                apiCall(`/environment/geocode?address=${encodeURIComponent(address)}`),

        /** GET /environment/elevation?lat=&lon= */
        getElevation: (lat: number, lon: number) =>
                apiCall(`/environment/elevation?lat=${lat}&lon=${lon}`),

        /** GET /environment/air-quality?lat=&lon= */
        getAirQuality: (lat: number, lon: number) =>
                apiCall(`/environment/air-quality?lat=${lat}&lon=${lon}`),

        /** GET /environment/severe-weather?lat=&lon= */
        getSevereWeather: (lat: number, lon: number) =>
                apiCall(`/environment/severe-weather?lat=${lat}&lon=${lon}`),

        /** GET /environment/hazmat?substance= */
        getHazmat: (substance: string) =>
                apiCall(`/environment/hazmat?substance=${encodeURIComponent(substance)}`),

        /** GET /environment/hazmat/known */
        getKnownHazmat: () => apiCall("/environment/hazmat/known"),

};

// ─── Revit API ──────────────────────────────────────────────────────────────

export const revitApi = {
        /** POST /revit/connect — V221 FIX: send {method} not {visible, force_new} */
        connect: (method: string = "auto") =>
                apiCall("/revit/connect", {
                        method: "POST",
                        body: JSON.stringify({ method }),
                }),

        /** POST /revit/disconnect */
        disconnect: () => apiCall("/revit/disconnect", { method: "POST" }),

        /** GET /revit/status */
        getStatus: () => apiCall("/revit/status"),

        /** POST /revit/document/open */
        openDocument: (data: { filepath: string }) =>
                apiCall("/revit/document/open", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/document/save */
        saveDocument: (data: { filepath?: string }) =>
                apiCall("/revit/document/save", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/document/close — V221 FIX: send {save_changes} body */
        closeDocument: (saveChanges: boolean = true) =>
                apiCall("/revit/document/close", {
                        method: "POST",
                        body: JSON.stringify({ save_changes: saveChanges }),
                }),

        /** POST /revit/read_rvt */
        readRvt: (data: { filepath: string }) =>
                apiCall("/revit/read_rvt", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/write_rvt */
        writeRvt: (data: { filepath: string; elements: unknown[] }) =>
                apiCall("/revit/write_rvt", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/upload_rvt — Upload RVT file (multipart) */
        uploadRvt: (file: File) => {
                const formData = new FormData();
                formData.append("file", file);
                return apiCall("/revit/upload_rvt", {
                        method: "POST",
                        body: formData,
                        headers: {}, // Let browser set Content-Type for FormData
                });
        },

        /** GET /revit/elements */
        getElements: () => apiCall("/revit/elements"),

        /** GET /revit/elements/selected */
        getSelectedElements: () => apiCall("/revit/elements/selected"),

        /** GET /revit/elements/{element_id} */
        getElement: (elementId: string) => apiCall(`/revit/elements/${elementId}`),

        /** GET /revit/elements/{element_id}/parameters */
        getElementParameters: (elementId: string) =>
                apiCall(`/revit/elements/${elementId}/parameters`),

        /** POST /revit/elements/create/wall */
        createWall: (data: {
                start_point: number[];
                end_point: number[];
                height?: number;
                level?: string;
                wall_type?: string;
        }) =>
                apiCall("/revit/elements/create/wall", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/elements/create/floor */
        createFloor: (data: {
                boundary_points: number[][];
                level?: string;
                floor_type?: string;
        }) =>
                apiCall("/revit/elements/create/floor", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/elements/create/door */
        createDoor: (data: {
                host_wall_id: string;
                location_point: number[];
                family_type?: string;
                level?: string;
        }) =>
                apiCall("/revit/elements/create/door", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/elements/create/window */
        createWindow: (data: {
                host_wall_id: string;
                location_point: number[];
                family_type?: string;
                level?: string;
        }) =>
                apiCall("/revit/elements/create/window", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/elements/create/column */
        createColumn: (data: {
                location_point: number[];
                height?: number;
                level?: string;
                column_type?: string;
        }) =>
                apiCall("/revit/elements/create/column", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/elements/create/beam */
        createBeam: (data: {
                start_point: number[];
                end_point: number[];
                level?: string;
                beam_type?: string;
        }) =>
                apiCall("/revit/elements/create/beam", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/elements/create/family */
        createFamily: (data: {
                family_name: string;
                category: string;
                location_point: number[];
                level?: string;
        }) =>
                apiCall("/revit/elements/create/family", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** PUT /revit/elements/{element_id}/parameters — V221 FIX: wrap in {parameters} */
        updateElementParameters: (elementId: string, data: Record<string, unknown>) =>
                apiCall(`/revit/elements/${elementId}/parameters`, {
                        method: "PUT",
                        body: JSON.stringify({ parameters: data }),
                }),

        /** DELETE /revit/elements/{element_id} */
        deleteElement: (elementId: string) =>
                apiCall(`/revit/elements/${elementId}`, { method: "DELETE" }),

        /** GET /revit/views */
        getViews: () => apiCall("/revit/views"),

        /** GET /revit/levels */
        getLevels: () => apiCall("/revit/levels"),

        /** GET /revit/grids */
        getGrids: () => apiCall("/revit/grids"),

        /** GET /revit/worksets */
        getWorksets: () => apiCall("/revit/worksets"),

        /** GET /revit/families/{category}/symbols */
        getFamilySymbols: (category: string) =>
                apiCall(`/revit/families/${category}/symbols`),

        /** POST /revit/families/load */
        loadFamily: (data: { family_path: string; category?: string }) =>
                apiCall("/revit/families/load", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/search/api/load */
        loadSearchApi: (data: { json_path: string }) =>
                apiCall("/revit/search/api/load", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /revit/search/api — AI-powered Revit API search */
        searchApi: (data: { query: string; context?: string }) =>
                apiCall("/revit/search/api", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /revit/search/online?q= */
        searchOnline: (query: string) =>
                apiCall(`/revit/search/online?q=${encodeURIComponent(query)}`),

        /** POST /revit/execute — Execute Revit command */
        execute: (data: { command: string; parameters?: Record<string, unknown> }) =>
                apiCall("/revit/execute", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),
};

// ─── AutoCAD API ────────────────────────────────────────────────────────────

export const autocadApi = {
        /** POST /autocad/connect */
        connect: (data: { visible?: boolean; force_new?: boolean } = {}) =>
                apiCall("/autocad/connect", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /autocad/disconnect */
        disconnect: () => apiCall("/autocad/disconnect", { method: "POST" }),

        /** POST /autocad/read_dwg */
        readDwg: (data: { filepath: string }) =>
                apiCall("/autocad/read_dwg", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /autocad/write_dwg */
        writeDwg: (data: { filepath: string; entities: unknown[] }) =>
                apiCall("/autocad/write_dwg", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /autocad/draw_line */
        drawLine: (data: {
                start_point: number[];
                end_point: number[];
                layer?: string;
        }) =>
                apiCall("/autocad/draw_line", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /autocad/draw_polyline — V221 FIX: points→vertices, add color/closed */
        drawPolyline: (data: {
                vertices: number[][];
                layer?: string;
                color?: number;
                closed?: boolean;
        }) =>
                apiCall("/autocad/draw_polyline", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /autocad/draw_circle */
        drawCircle: (data: { center: number[]; radius: number; layer?: string }) =>
                apiCall("/autocad/draw_circle", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /autocad/draw_text — V221 FIX: point→insertion_point, add color */
        drawText: (data: {
                text: string;
                insertion_point: number[];
                height?: number;
                layer?: string;
                color?: number;
        }) =>
                apiCall("/autocad/draw_text", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /autocad/status */
        getStatus: () => apiCall("/autocad/status"),

        /** POST /autocad/save — V221 FIX: filepath required (was optional) */
        save: (data: { filepath: string }) =>
                apiCall("/autocad/save", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /autocad/upload_dwg — Upload DWG file (multipart) */
        uploadDwg: (file: File) => {
                const formData = new FormData();
                formData.append("file", file);
                return apiCall("/autocad/upload_dwg", {
                        method: "POST",
                        body: formData,
                        headers: {},
                });
        },

        /** DELETE /autocad/entity/{handle} */
        deleteEntity: (handle: string) =>
                apiCall(`/autocad/entity/${handle}`, { method: "DELETE" }),

        /** PUT /autocad/entity/{handle} */
        updateEntity: (handle: string, data: Record<string, unknown>) =>
                apiCall(`/autocad/entity/${handle}`, {
                        method: "PUT",
                        body: JSON.stringify(data),
                }),
};

// ─── Digital Twin API ───────────────────────────────────────────────────────

export const digitalTwinApi = {
        /** POST /digital-twin/convert — V216 FIX: aligned field names with backend ConvertRequest */
        convert: (data: {
                source_filepath: string;
                target_filepath: string;
                conversion_type: string;
        }) =>
                apiCall("/digital-twin/convert", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /digital-twin/history — V221 FIX: restored (was accidentally removed in V220) */
        getHistory: () => apiCall("/digital-twin/history"),

        /** POST /digital-twin/configure — V221 FIX: wrap config in {config: ...} */
        configure: (data: Record<string, unknown>) =>
                apiCall("/digital-twin/configure", {
                        method: "POST",
                        body: JSON.stringify({ config: data }),
                }),

        /** POST /digital-twin/rollback/{version_id} — V221 FIX: send {target_file} body */
        rollback: (versionId: string, targetFile: string) =>
                apiCall(`/digital-twin/rollback/${versionId}`, {
                        method: "POST",
                        body: JSON.stringify({ target_file: targetFile }),
                }),

        /** GET /digital-twin/mappings */
        getMappings: () => apiCall("/digital-twin/mappings"),

        /** GET /digital-twin/status */
        getStatus: () => apiCall("/digital-twin/status"),

        /** POST /digital-twin/update_mapping */
        updateMapping: (data: Record<string, unknown>) =>
                apiCall("/digital-twin/update_mapping", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /digital-twin/config */
        getConfig: () => apiCall("/digital-twin/config"),

        /** PUT /digital-twin/config — V221 FIX: wrap config in {config: ...} */
        setConfig: (data: Record<string, unknown>) =>
                apiCall("/digital-twin/config", {
                        method: "PUT",
                        body: JSON.stringify({ config: data }),
                }),

        /** GET /digital-twin/download/{filename} */
        download: (filename: string) =>
                apiCall<Blob>(`/digital-twin/download/${filename}`),
};

// ─── Monitor API ────────────────────────────────────────────────────────────

export const monitorApi = {
        /** GET /monitor/health */
        getHealth: () => apiCall("/monitor/health"),

        /** GET /monitor/metrics (Prometheus format) */
        getMetrics: () => apiCall<string>("/monitor/metrics"),

        /** GET /monitor/engine-status */
        getEngineStatus: () => apiCall("/monitor/engine-status"),

        /** GET /monitor/agent-activity */
        getAgentActivity: (params?: { limit?: number }) =>
                apiCall(
                        `/monitor/agent-activity${params?.limit ? `?limit=${params.limit}` : ""}`,  // NOSONAR: typescript:S4624
                ),

        /** GET /monitor/security-alerts */
        getSecurityAlerts: (params?: { limit?: number; severity?: string }) => {
                const query = new URLSearchParams();
                if (params?.limit) query.set("limit", String(params.limit));
                if (params?.severity) query.set("severity", params.severity);
                const qs = query.toString();
                return apiCall(
                        `/monitor/security-alerts${qs ? `?${qs}` : ""}`,  // NOSONAR: typescript:S4624
                );
        },

        /** GET /monitor/alerts */
};

// ─── Workflow API ───────────────────────────────────────────────────────────

export const workflowApi = {
        /** GET /workflow/status */
        getStatus: () => apiCall("/workflow/status"),

        /** POST /workflow/start */
        start: (data: {
                project_id: string;
                workflow_type: string;
                config?: Record<string, unknown>;
        }) =>
                apiCall("/workflow/start", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /workflow/{workflow_id}/status */
        getWorkflowStatus: (workflowId: string) =>
                apiCall(`/workflow/${workflowId}/status`),

        /** POST /workflow/{workflow_id}/approve */
        approve: (workflowId: string, data?: { comment?: string }) =>
                apiCall(`/workflow/${workflowId}/approve`, {
                        method: "POST",
                        body: JSON.stringify(data || {}),
                }),

        /** POST /workflow/{workflow_id}/reject */
        reject: (workflowId: string, data?: { reason?: string }) =>
                apiCall(`/workflow/${workflowId}/reject`, {
                        method: "POST",
                        body: JSON.stringify(data || {}),
                }),

        /** GET /workflow/{workflow_id}/audit — V221 FIX: restored (accidentally removed in V220) */
        getAudit: (workflowId: string) => apiCall(`/workflow/${workflowId}/audit`),
};

// ─── Memory API ─────────────────────────────────────────────────────────────

export const memoryApi = {
        /** GET /memory/status */
        getStatus: () => apiCall("/memory/status"),

        /** POST /memory/add */
        add: (data: { content: string; metadata?: Record<string, unknown> }) =>
                apiCall("/memory/add", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /memory/search */
        search: (data: { query: string; limit?: number }) =>
                apiCall("/memory/search", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /memory/all */
        getAll: () => apiCall("/memory/all"),

        /** DELETE /memory/{memory_id} */
        delete: (memoryId: string) =>
                apiCall(`/memory/${memoryId}`, { method: "DELETE" }),

        /** GET /memory/{memory_id}/history */
};

// ─── V2 API (generative, BIM, IFC43, AR, webhooks, topology, graphrag) ──────

export const v2Api = {
        // ── GraphRAG (already wired in GraphRAGPage) ──
        /** POST /graphrag/knowledge */
        ingestGraphragKnowledge: (data: Record<string, unknown>) =>
                apiCall("/graphrag/knowledge", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /graphrag/ask */
        askGraphrag: (data: { question: string; context?: string }) =>
                apiCall("/graphrag/ask", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /graphrag/search */
        searchGraphrag: (data: { query: string; limit?: number }) =>
                apiCall("/graphrag/search", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** GET /graphrag/health */
        getGraphragHealth: () => apiCall("/graphrag/health", {}, API_V2_BASE),

        // ── V214: Newly wired V2 endpoints ──

        /** POST /generative/design — Generative design optimization */
        generativeDesign: (data: Record<string, unknown>) =>
                apiCall("/generative/design", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** GET /bim/providers — List available BIM providers */
        getBimProviders: () => apiCall("/bim/providers", {}, API_V2_BASE),

        /** POST /bim/extract-rooms — Extract rooms from BIM model */
        extractBimRooms: (data: Record<string, unknown>) =>
                apiCall("/bim/extract-rooms", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** GET /bim/health — BIM provider health check */
        getBimHealth: () => apiCall("/bim/health", {}, API_V2_BASE),

        /** POST /ifc43/map-detector — Map fire alarm detector to IFC 4.3 */
        mapDetectorToIfc43: (data: Record<string, unknown>) =>
                apiCall("/ifc43/map-detector", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /ifc43/map-project — Map entire project to IFC 4.3 */
        mapProjectToIfc43: (data: Record<string, unknown>) =>
                apiCall("/ifc43/map-project", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /ar/export — Export AR visualization data */
        exportAr: (data: Record<string, unknown>) =>
                apiCall("/ar/export", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /webhooks/subscribe — Subscribe to webhook events */
        subscribeWebhook: (data: Record<string, unknown>) =>
                apiCall("/webhooks/subscribe", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** GET /webhooks/subscriptions — List webhook subscriptions */
        getWebhookSubscriptions: () => apiCall("/webhooks/subscriptions", {}, API_V2_BASE),

        /** DELETE /webhooks/subscriptions/{id} — Delete webhook subscription */
        deleteWebhookSubscription: (subId: string) =>
                apiCall(`/webhooks/subscriptions/${subId}`, { method: "DELETE" }, API_V2_BASE),

        /** POST /webhooks/publish — Publish event to webhooks */
        publishWebhook: (data: Record<string, unknown>) =>
                apiCall("/webhooks/publish", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /smoke-simulation/state — Run smoke simulation state */
        runSmokeSimulation: (data: Record<string, unknown>) =>
                apiCall("/smoke-simulation/state", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /topology/element — Add element to topology graph */
        addTopologyElement: (data: Record<string, unknown>) =>
                apiCall("/topology/element", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /topology/connection — Add connection to topology graph */
        addTopologyConnection: (data: Record<string, unknown>) =>
                apiCall("/topology/connection", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /topology/impact — Analyze topology impact */
        analyzeTopologyImpact: (data: Record<string, unknown>) =>
                apiCall("/topology/impact", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** GET /topology/health — Topology service health check */
        getTopologyHealth: () => apiCall("/topology/health", {}, API_V2_BASE),

        // ── Multi-Database Admin ──
        /** GET /multi-db/health — Check health of all database connections */
        getMultiDbHealth: () => apiCall("/multi-db/health"),

        /** GET /multi-db/redis/get/{key} — Get a value from Redis */
        getRedisValue: (key: string) => apiCall(`/multi-db/redis/get/${key}`),

        /** POST /multi-db/redis/set — Set a value in Redis */
        setRedisValue: (key: string, value: string, ttl?: number) => {
                const ttlParam = ttl ? `&ttl=${ttl}` : "";
                return apiCall(`/multi-db/redis/set?key=${key}&value=${encodeURIComponent(value)}${ttlParam}`, { method: "POST" });
        },

        /** GET /multi-db/neo4j/query — Execute predefined Neo4j query */
        executeNeo4jQuery: (queryType: string, parameters?: string) => {
                const paramsSuffix = parameters ? `&parameters=${encodeURIComponent(parameters)}` : "";
                return apiCall(`/multi-db/neo4j/query?query_type=${queryType}${paramsSuffix}`);
        },

        /** GET /multi-db/qdrant/collections — List Qdrant collections */
        getQdrantCollections: () => apiCall("/multi-db/qdrant/collections"),

        // ── Multi-DB: BIM-specific endpoints (V273) ──
        /** POST /multi-db/bim/cache-element — Cache a BIM element in Redis */
        cacheBimElement: (elementId: string, elementData: Record<string, unknown>) =>
                apiCall("/multi-db/bim/cache-element", {
                        method: "POST",
                        body: JSON.stringify({ element_id: elementId, element_data: elementData }),
                }),

        /** GET /multi-db/bim/get-cached-element/{elementId} — Get cached BIM element */
        getCachedBimElement: (elementId: string) =>
                apiCall(`/multi-db/bim/get-cached-element/${elementId}`),

        /** POST /multi-db/bim/store-embeddings — Store element embeddings in Qdrant */
        storeElementEmbeddings: (elementId: string, embeddings: number[]) =>
                apiCall("/multi-db/bim/store-embeddings", {
                        method: "POST",
                        body: JSON.stringify({ element_id: elementId, embeddings }),
                }),

        /** POST /multi-db/bim/find-similar — Find similar elements by vector search */
        findSimilarElements: (queryEmbedding: number[], limit: number = 5) =>
                apiCall("/multi-db/bim/find-similar", {
                        method: "POST",
                        body: JSON.stringify({ query_embedding: queryEmbedding, limit }),
                }),

        /** POST /multi-db/bim/create-relationships — Create Neo4j relationships */
        createElementRelationships: (
                elementId: string,
                relatedElements: string[],
                relationshipType: string = "CONNECTED_TO",
        ) =>
                apiCall("/multi-db/bim/create-relationships", {
                        method: "POST",
                        body: JSON.stringify({
                                element_id: elementId,
                                related_elements: relatedElements,
                                relationship_type: relationshipType,
                        }),
                }),

        /** GET /multi-db/bim/related-elements/{elementId} — Find related elements in Neo4j */
        findRelatedElements: (elementId: string, relationshipType: string = "CONNECTED_TO") =>
                apiCall(`/multi-db/bim/related-elements/${elementId}?relationship_type=${relationshipType}`),

        // ── V270: FDS Simulation endpoints ──
        /** POST /fds/submit — Submit an FDS simulation job */
        submitFdsJob: (data: { fds_input: string; project_id?: string; metadata?: Record<string, unknown> }) =>
                apiCall("/fds/submit", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** GET /fds/status/{job_id} — Get FDS job status */
        getFdsJobStatus: (jobId: string) =>
                apiCall(`/fds/status/${jobId}`, {}, API_V2_BASE),

        /** GET /fds/jobs — List FDS simulation jobs */
        listFdsJobs: (limit?: number) => {
                const limitParam = limit ? `?limit=${limit}` : "";
                return apiCall(`/fds/jobs${limitParam}`, {}, API_V2_BASE);
        },

        /** POST /smoke-simulation/state — Create/update smoke simulation state */
        setSmokeSimulationState: (data: {
                room_id: string;
                smoke_density_points?: Array<{ x: number; y: number; z: number; density_kg_m3: number }>;
                visibility_at_height?: Record<string, number>;
                fds_run_id?: string;
        }) =>
                apiCall("/smoke-simulation/state", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),
};

// ─── Marine API ─────────────────────────────────────────────────────────────

export const marineApi = {
        /** GET /marine/standards */
        getStandards: () => apiCall("/marine/standards"),

        /** GET /marine/fire-classes */
        getFireClasses: () => apiCall("/marine/fire-classes"),

        /** POST /marine/ship/validate */
        validateShip: (data: Record<string, unknown>) =>
                apiCall("/marine/ship/validate", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/ship/design */
        designShip: (data: Record<string, unknown>) =>
                apiCall("/marine/ship/design", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/zones/divide */
        divideZones: (data: Record<string, unknown>) =>
                apiCall("/marine/zones/divide", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/extinguishing/design */
        designExtinguishing: (data: Record<string, unknown>) =>
                apiCall("/marine/extinguishing/design", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/detection/design */
        designDetection: (data: Record<string, unknown>) =>
                apiCall("/marine/detection/design", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/alarm-logic/generate */
        generateAlarmLogic: (data: Record<string, unknown>) =>
                apiCall("/marine/alarm-logic/generate", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/divisions/generate */
        generateDivisions: (data: Record<string, unknown>) =>
                apiCall("/marine/divisions/generate", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/power/design */
        designPower: (data: Record<string, unknown>) =>
                apiCall("/marine/power/design", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/integrations/scada */
        integrateScada: (data: Record<string, unknown>) =>
                apiCall("/marine/integrations/scada", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/integrations/etap */
        integrateEtap: (data: Record<string, unknown>) =>
                apiCall("/marine/integrations/etap", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/integrations/dxf */
        exportDxf: (data: Record<string, unknown>) =>
                apiCall("/marine/integrations/dxf", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /marine/integrations/revit */
        exportRevit: (data: Record<string, unknown>) =>
                apiCall("/marine/integrations/revit", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

};

// ─── ETAP Integration API ────────────────────────────────────────────────────

export interface EtapConnectionSettings {
        host: string;
        port: number;
        username: string;
        password: string;
        timeout_seconds: number;
}

export interface EtapConnectionTestResponse {
        success: boolean;
        message: string;
        latency_ms?: number;
        server_version?: string;
}

export interface EtapProjectInfo {
        project_id: string;
        name: string;
        modified_at?: string;
        size_mb?: number;
        is_remote: boolean;
}

export interface EtapExportRequest {
        project_id: string;
        include_loads: boolean;
        include_sources: boolean;
        include_topology: boolean;
        format: "csv" | "ort";
}

export interface EtapImportRequest {
        project_id: string;
        etap_project_id: string;
        import_loads: boolean;
        import_sources: boolean;
        conflict_resolution: "skip" | "overwrite" | "merge";
}

export interface EtapSyncLog {
        id: string;
        direction: "export" | "import";
        status: "success" | "error" | "partial";
        records_synced: number;
        error_message?: string;
        created_at: string;
}

export interface EtapSettingsResponse {
        id: string;
        project_id: string;
        host: string;
        port: number;
        username: string;
        enabled: boolean;
        last_sync?: string;
        created_at: string;
        updated_at: string;
}

export interface EtapSyncLogResponse {
        items: EtapSyncLog[];
        total: number;
        page: number;
        page_size: number;
}

export const etapApi = {
        /** POST /integrations/etap/connect */
        testConnection: async (settings: EtapConnectionSettings, projectId?: string): Promise<EtapConnectionTestResponse> => {
                const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
                return apiCall(`/integrations/etap/connect${qs}`, {
                        method: "POST",
                        body: JSON.stringify(settings),
                });
        },

        /** POST /integrations/etap/disconnect */
        disconnect: async (projectId?: string): Promise<{ message: string; enabled: boolean }> => {
                const qs = projectId ? `?project_id=${encodeURIComponent(projectId)}` : "";
                return apiCall(`/integrations/etap/disconnect${qs}`, { method: "POST" });
        },

        /** GET /integrations/etap/status */
        getStatus: async (projectId: string): Promise<{ enabled: boolean; configured: boolean; last_sync?: string; host?: string; port?: number; username?: string }> =>
                apiCall(`/integrations/etap/status?project_id=${encodeURIComponent(projectId)}`),

        /** GET /integrations/etap/projects */
        listEtapProjects: async (projectId: string): Promise<EtapProjectInfo[]> =>
                apiCall(`/integrations/etap/projects?project_id=${encodeURIComponent(projectId)}`),

        /** GET /integrations/etap/projects/local */
        listLocalProjects: async (): Promise<Array<{ id: string; name: string }>> =>
                apiCall("/integrations/etap/projects/local"),

        /** POST /integrations/etap/export */
        exportToEtap: async (data: EtapExportRequest): Promise<{
                project_id: string;
                format: string;
                loads_csv: string;
                sources_csv: string;
                records_exported: number;
        }> => apiCall("/integrations/etap/export", {
                method: "POST",
                body: JSON.stringify(data),
        }),

        /** POST /integrations/etap/import */
        importFromEtap: async (data: EtapImportRequest): Promise<{
                project_id: string;
                etap_project_id: string;
                records_imported: number;
                message: string;
        }> => apiCall("/integrations/etap/import", {
                method: "POST",
                body: JSON.stringify(data),
        }),

        /** GET /integrations/etap/logs */
        getLogs: async (projectId: string, page = 1, pageSize = 50): Promise<EtapSyncLogResponse> =>
                apiCall(`/integrations/etap/logs?project_id=${encodeURIComponent(projectId)}&page=${page}&page_size=${pageSize}`),

        /** POST /integrations/etap/settings */
        createSettings: async (projectId: string, settings: EtapConnectionSettings): Promise<EtapSettingsResponse> =>
                apiCall(`/integrations/etap/settings?project_id=${encodeURIComponent(projectId)}`, {
                        method: "POST",
                        body: JSON.stringify(settings),
                }),

        /** GET /integrations/etap/settings */
        getSettings: async (projectId: string): Promise<EtapSettingsResponse | null> =>
                apiCall(`/integrations/etap/settings?project_id=${encodeURIComponent(projectId)}`),

        /** PUT /integrations/etap/settings */
        updateSettings: async (projectId: string, data: Partial<EtapConnectionSettings> & { enabled?: boolean }): Promise<EtapSettingsResponse> =>
                apiCall(`/integrations/etap/settings?project_id=${encodeURIComponent(projectId)}`, {
                        method: "PUT",
                        body: JSON.stringify(data),
                }),

        /** DELETE /integrations/etap/settings */
        deleteSettings: async (projectId: string): Promise<{ message: string }> =>
                apiCall(`/integrations/etap/settings?project_id=${encodeURIComponent(projectId)}`, {
                        method: "DELETE",
                }),
};

export const fullApi = {
        login: async (username: string, password?: string) => apiCall<{ success: boolean; token?: string; user?: any; message?: string }>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
        logout: async () => apiCall<{ success: boolean }>("/auth/logout", { method: "POST" }),
        getMe: async () => apiCall<{ data?: any }>("/auth/me"),
        verifyToken: async (token: string) => apiCall<{ success: boolean }>("/auth/verify", { method: "POST", body: JSON.stringify({ token }) }),
        /**
         * qomnCalculate — V270 FIX (audit bug C-qomn-calculate).
         *
         * The audit flagged this call as 404 because the backend has no generic
         * /qomn/calculate endpoint — only specific endpoints per calculation type
         * (smoke-spacing, heat-spacing, battery, voltage-drop, place-detectors,
         * place-duct). The actual production page (EngineeringPage.tsx) correctly
         * calls qomnApi.voltageDrop() etc. directly; this fullApi.qomnCalculate
         * method is only used by the orphan EngineeringRepository → useQOMNCalculatorViewModel
         * path. Rather than leaving a 404 in the codebase, route the call to the
         * correct specific endpoint based on the params shape.
         *
         * V272 FIX (honest self-criticism): the V270 version of this smart router
         * had THREE unit-conversion / unit-naming defects that would have produced
         * silently wrong fire-safety calculations if anyone ever wired this path
         * into production:
         *
         *   1. `params.battery_load_ah` (amp-hours, a CAPACITY) was being mapped
         *      to `standby_load_a` (amps, a CURRENT). Ah ≠ A — the unit names
         *      even look similar, which is exactly why the bug slipped through.
         *      The backend Pydantic model expects `standby_load_a` and
         *      `alarm_load_a` as currents in amperes.
         *
         *   2. `params.ceiling_height`, `params.wire_length` were passed through
         *      with NO unit conversion, then assigned to `_m` (meters) fields.
         *      If the caller passed feet (which the QOMNCalculatorPage does for
         *      its own state), the calculation would be wrong by a factor of
         *      3.28084. The smart router had no way to know which unit the
         *      caller intended.
         *
         *   3. `params.ceiling_height ?? 3.0` — silently defaulting a fire-safety
         *      input to 3.0 m is dangerous. If a caller forgets to pass it, the
         *      endpoint will happily run a calculation on a phantom 3 m ceiling
         *      and return a "valid" result.
         *
         * The fix: the smart router now refuses to guess units. If a caller
         * passes the legacy param names (battery_load_ah, ceiling_height,
         * wire_length), the router returns a structured failure with a clear
         * migration message instead of silently producing wrong numbers.
         * Callers MUST use the typed qomnApi methods (which take SI units
         * directly) or pass the SI-named fields explicitly.
         */
        qomnCalculate: async (params: any): Promise<{ success: boolean; data?: any; message?: string }> => {
                // V271 FIX: guard against null/undefined params to prevent TypeError
                // on property access. Returns structured failure instead of crashing.
                if (params === null || params === undefined || typeof params !== "object") {
                        return {
                                success: false,
                                message: "qomnCalculate: params must be a non-null object. Use qomnApi.smokeSpacing/battery/voltageDrop directly for typed calls.",
                        };
                }

                // V272 FIX: detect the legacy ambiguous param names and refuse to
                // guess units. Returning a clear error is safer than silently
                // producing wrong fire-safety calculations.
                const legacyAmbiguousKeys = ["battery_load_ah", "ceiling_height", "wire_length", "room_length", "room_width"];
                const detectedLegacy = legacyAmbiguousKeys.filter((k) => params[k] !== undefined);
                if (detectedLegacy.length > 0) {
                        return {
                                success: false,
                                message:
                                        "qomnCalculate: refusing to infer units for legacy param names (" +
                                        detectedLegacy.join(", ") +
                                        "). The V270 smart router silently converted these to SI-named fields, " +
                                        "but the unit semantics were ambiguous (Ah vs A, ft vs m). " +
                                        "Use qomnApi.smokeSpacing({ceiling_height_m}) / qomnApi.battery({standby_load_a, alarm_load_a}) / " +
                                        "qomnApi.voltageDrop({current_a, length_m, awg_gauge}) directly with SI units.",
                        };
                }

                // Route based on SI-named params (matches backend schemas exactly).
                if (params.ceiling_height_m !== undefined) {
                        return apiCall<{ success: boolean; data?: any; message?: string }>("/qomn/smoke-spacing", {
                                method: "POST",
                                body: JSON.stringify({ ceiling_height_m: Number(params.ceiling_height_m) }),
                        });
                }
                if (params.standby_load_a !== undefined || params.alarm_load_a !== undefined) {
                        return apiCall<{ success: boolean; data?: any; message?: string }>("/qomn/battery", {
                                method: "POST",
                                body: JSON.stringify({
                                        standby_load_a: Number(params.standby_load_a ?? 0),
                                        alarm_load_a: Number(params.alarm_load_a ?? 0),
                                        standby_hours: Number(params.standby_hours ?? 24),
                                        alarm_minutes: Number(params.alarm_minutes ?? 10),
                                }),
                        });
                }
                if (params.current_a !== undefined || params.length_m !== undefined) {
                        return apiCall<{ success: boolean; data?: any; message?: string }>("/qomn/voltage-drop", {
                                method: "POST",
                                body: JSON.stringify({
                                        current_a: Number(params.current_a ?? 0),
                                        length_m: Number(params.length_m ?? 0),
                                        awg_gauge: String(params.awg_gauge ?? "12"),
                                        supply_voltage_v: Number(params.supply_voltage_v ?? 24),
                                }),
                        });
                }
                // No recognized param shape — return a structured failure instead of 404.
                return {
                        success: false,
                        message:
                                "qomnCalculate: could not infer QOMN calculation type from params. " +
                                "Pass SI-named fields (ceiling_height_m / standby_load_a+alarm_load_a / current_a+length_m+awg_gauge) " +
                                "or use qomnApi.smokeSpacing/battery/voltageDrop directly.",
                };
        },
        getEnvironmentalContext: async (lat: number, lon: number) => apiCall<{ data?: any }>(`/environment/context?lat=${lat}&lon=${lon}`),
        getWeatherForecast: async (location: string) => apiCall<{ data?: any }>(`/environment/weather?location=${encodeURIComponent(location)}`),
        getAirQualityData: async (lat: number, lon: number) => apiCall<{ data?: any }>(`/environment/air-quality?lat=${lat}&lon=${lon}`),
};

export default fullApi;


