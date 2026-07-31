
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
        getCountries: () => apiCall("/environment/countries"),

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

        /** GET /environment/context */
        getContext: (params?: { lat?: number; lon?: number; address?: string }) => {
                const query = new URLSearchParams();
                if (params?.lat) query.set("lat", String(params.lat));
                if (params?.lon) query.set("lon", String(params.lon));
                if (params?.address) query.set("address", params.address);
                const qs = query.toString();
                return apiCall(`/environment/context${qs ? `?${qs}` : ""}`);
        },

        /** GET /environment/full-context */
        getFullContext: (params?: { lat?: number; lon?: number; address?: string }) => {
                const query = new URLSearchParams();
                if (params?.lat) query.set("lat", String(params.lat));
                if (params?.lon) query.set("lon", String(params.lon));
                if (params?.address) query.set("address", params.address);
                const qs = query.toString();
                return apiCall(`/environment/full-context${qs ? `?${qs}` : ""}`);
        },

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
        getAlerts: (params?: { limit?: number; severity?: string }) => {
                const query = new URLSearchParams();
                if (params?.limit) query.set("limit", String(params.limit));
                if (params?.severity) query.set("severity", params.severity);
                const qs = query.toString();
                return apiCall(
                        `/monitor/alerts${qs ? `?${qs}` : ""}`,  // NOSONAR: typescript:S4624
                );
        },

        /** GET /monitor/uptime */
        getUptime: () => apiCall("/monitor/uptime"),
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
        getHistory: (memoryId: string) =>
                apiCall(`/memory/${memoryId}/history`),
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

        // ── V2 Memory endpoints ──
        /** POST /memory/store — Store a memory item in V2 */
        storeMemory: (data: { key: string; value: string; metadata?: Record<string, unknown> }) =>
                apiCall("/memory/store", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /memory/search — Search V2 memories */
        searchMemory: (query: string, limit?: number) =>
                apiCall("/memory/search", { method: "POST", body: JSON.stringify({ query, limit: limit || 10 }) }, API_V2_BASE),

        /** GET /memory/health — V2 memory service health */
        getMemoryHealth: () => apiCall("/memory/health", {}, API_V2_BASE),

        // ── V2 Health ──
        /** GET /health — V2 API health check */
        getV2Health: () => apiCall("/health", {}, API_V2_BASE),

        // ── V2 Auth ──
        /** GET /auth/csrf-token — Get CSRF token for V2 API */
        getAuthCsrfToken: () => apiCall("/auth/csrf-token", {}, API_V2_BASE),
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

// ─── System Admin API (Cache, Feature Flags, Secret Rotation) ──────────────

export const adminApi = {
        /** GET /cache/stats — Cache statistics (admin only) */
        getCacheStats: () =>
                apiCall<{ success: boolean; data: { entries: number; max_entries: number; memory_usage_mb: number; hit_rate: number } }>("/cache/stats"),

        /** POST /cache/clear — Clear all cached data (admin only) */
        clearCache: () =>
                apiCall<{ success: boolean; message: string }>("/cache/clear", { method: "POST" }),

        /** GET /feature-flags — Get all feature flag states */
        getFeatureFlags: () =>
                apiCall<{ success: boolean; data: Record<string, boolean> }>("/feature-flags"),

        /** POST /feature-flags — Toggle a feature flag */
        setFeatureFlag: (data: { key: string; enabled: boolean }) =>
                apiCall<{ success: boolean; message: string }>("/feature-flags", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /settings/secret-rotation/rotate — Hot-rotate a security secret */
        rotateSecret: (data: { secret_name: string; new_value: string; grace_period_seconds?: number }) =>
                apiCall<{ success: boolean; message: string }>("/settings/secret-rotation/rotate", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /settings/admin-token/rotate — Rotate master admin token */
        rotateAdminToken: (data: { new_token: string; grace_period_seconds?: number }) =>
                apiCall<{ success: boolean; message: string }>("/settings/admin-token/rotate", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /api/database-health — Multi-DB health check */
        getDatabaseHealth: () =>
                apiCall<{ success: boolean; data: Record<string, { status: string; latency_ms: number; details?: string }> }>("/database-health", undefined, API_BASE.replace("/v1", "")),

        /** GET /health/statistics — System-wide statistics */
        getHealthStatistics: () =>
                apiCall<{ success: boolean; data: { projects: number; devices: number; connections: number; reports: number; uptime_seconds: number } }>("/health/statistics"),
};

// ─── Extended FACP API (verify, schedule, spec) ────────────────────────────

export const facpExtendedApi = {
        /** POST /facp/verify — Verify FACP compliance (UL/FDNY/NFPA) */
        verify: (data: { panel_id: string; jurisdiction?: string; standards?: string[] }) =>
                apiCall("/facp/verify", { method: "POST", body: JSON.stringify(data) }),

        /** POST /facp/schedule — Generate DXF schedule table */
        generateSchedule: (data: { panel_id: string; project_id?: string }) =>
                apiCall("/facp/schedule", { method: "POST", body: JSON.stringify(data) }),

        /** POST /facp/spec — Generate CSI specification (28 31 11) */
        generateSpec: (data: { panel_id: string; project_id?: string }) =>
                apiCall("/facp/spec", { method: "POST", body: JSON.stringify(data) }),
};

// ─── Extended QOMN API (golden tests, place duct) ─────────────────────────

export const qomnExtendedApi = {
        /** POST /qomn/place-duct — Duct detector placement */
        placeDuct: (data: { duct_width_m: number; duct_velocity_mps?: number; airflow_direction?: string }) =>
                apiCall("/qomn/place-duct", { method: "POST", body: JSON.stringify(data) }),

        /** POST /qomn/golden-tests — Run golden test suite */
        runGoldenTests: () =>
                apiCall("/qomn/golden-tests", { method: "POST" }),

        /** POST /qomn/place-detectors — Place smoke/heat detectors on a floor plan */
        placeDetectors: (data: { room_area_m2: number; ceiling_height_m: number; detector_type?: string }) =>
                apiCall("/qomn/place-detectors", { method: "POST", body: JSON.stringify(data) }),
};

// ─── Extended LLM API (models, compliance narrative) ───────────────────────

export const llmExtendedApi = {
        /** GET /llm/models — List available LLM models */
        getModels: () => apiCall<{ success: boolean; data: { id: string; name: string; provider: string }[] }>("/llm/models"),

        /** POST /llm/compliance-narrative — Draft compliance narrative for AHJ */
        complianceNarrative: (data: { calculation_type: string; calculation_result: Record<string, unknown>; jurisdiction?: string }) =>
                apiCall("/llm/compliance-narrative", { method: "POST", body: JSON.stringify(data) }),
};

// ─── Extended Revit API (search, execute NL) ──────────────────────────────

export const revitExtendedApi = {
        /** POST /revit/search/api/load — Load RevitAPIDocs.com index */
        loadApiSearchIndex: () =>
                apiCall("/revit/search/api/load", { method: "POST" }),

        /** POST /revit/search/api — Search RevitAPIDocs.com (local) */
        searchApi: (data: { query: string; max_results?: number }) =>
                apiCall("/revit/search/api", { method: "POST", body: JSON.stringify(data) }),

        /** GET /revit/search/online?q= — Search RevitAPIDocs.com (online) */
        searchOnline: (query: string) =>
                apiCall(`/revit/search/online?q=${encodeURIComponent(query)}`),

        /** POST /revit/execute — Execute natural language command */
        executeNlCommand: (data: { command: string; context?: Record<string, unknown> }) =>
                apiCall("/revit/execute", { method: "POST", body: JSON.stringify(data) }),
};

// ─── Extended Marine API (SCADA, ETAP, DXF, Revit, Alarm, Divisions) ─────

export const marineExtendedApi = {
        /** POST /marine/generate-alarm-logic — Generate alarm logic */
        generateAlarmLogic: (data: { ship_id: string; zone_ids?: string[] }) =>
                apiCall("/marine/generate-alarm-logic", { method: "POST", body: JSON.stringify(data) }),

        /** POST /marine/generate-divisions — Generate ship divisions */
        generateDivisions: (data: { ship_id: string; division_count?: number }) =>
                apiCall("/marine/generate-divisions", { method: "POST", body: JSON.stringify(data) }),

        /** POST /marine/generate-scada — SCADA integration generation */
        generateScada: (data: { ship_id: string; protocol?: string }) =>
                apiCall("/marine/generate-scada", { method: "POST", body: JSON.stringify(data) }),

        /** POST /marine/generate-etap — ETAP integration generation */
        generateEtap: (data: { ship_id: string }) =>
                apiCall("/marine/generate-etap", { method: "POST", body: JSON.stringify(data) }),

        /** POST /marine/generate-dxf — Generate DXF output */
        generateDxf: (data: { ship_id: string }) =>
                apiCall("/marine/generate-dxf", { method: "POST", body: JSON.stringify(data) }),

        /** POST /marine/generate-revit — Generate Revit output */
        generateRevit: (data: { ship_id: string }) =>
                apiCall("/marine/generate-revit", { method: "POST", body: JSON.stringify(data) }),
};

// ─── Engineering Copilot Extended API ──────────────────────────────────────

export const copilotExtendedApi = {
        /** POST /engineering-copilot/translate-model — Translate model between formats */
        translateModel: (data: { source_format: string; target_format: string; model_data: Record<string, unknown> }) =>
                apiCall("/engineering-copilot/translate-model", { method: "POST", body: JSON.stringify(data) }),

        /** POST /engineering-copilot/validate-model — Validate model compliance */
        validateModel: (data: { model_data: Record<string, unknown>; standard?: string }) =>
                apiCall("/engineering-copilot/validate-model", { method: "POST", body: JSON.stringify(data) }),

        /** POST /engineering-copilot/generate-reports — Generate engineering reports */
        generateReports: (data: { project_id?: string; report_types?: string[] }) =>
                apiCall("/engineering-copilot/generate-reports", { method: "POST", body: JSON.stringify(data) }),
};

// ─── Extended V2 API (smoke sim, webhook publish, multi-db BIM) ────────────

export const v2ExtendedApi = {
        /** POST /v2/smoke-simulation/state — Create/update smoke simulation state */
        updateSmokeSimulation: (data: { simulation_id?: string; state: Record<string, unknown> }) =>
                apiCall("/smoke-simulation/state", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /v2/webhooks/publish — Publish a webhook event */
        publishWebhook: (data: { event_type: string; payload: Record<string, unknown> }) =>
                apiCall("/webhooks/publish", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /v2/multi-db/bim/cache-element — Cache BIM element in Redis */
        cacheBimElement: (data: { element_id: string; element_data: Record<string, unknown>; ttl_seconds?: number }) =>
                apiCall("/multi-db/bim/cache-element", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** GET /v2/multi-db/bim/get-cached-element/{element_id} — Get cached BIM element */
        getCachedBimElement: (elementId: string) =>
                apiCall(`/multi-db/bim/get-cached-element/${elementId}`, undefined, API_V2_BASE),

        /** POST /v2/multi-db/bim/store-embeddings — Store embeddings in Qdrant */
        storeEmbeddings: (data: { element_id: string; embedding: number[]; metadata?: Record<string, unknown> }) =>
                apiCall("/multi-db/bim/store-embeddings", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /v2/multi-db/bim/find-similar — Find similar elements via Qdrant */
        findSimilar: (data: { embedding: number[]; top_k?: number }) =>
                apiCall("/multi-db/bim/find-similar", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** POST /v2/multi-db/bim/create-relationships — Create relationships in Neo4j */
        createRelationships: (data: { element_id: string; related_ids: string[]; relationship_type: string }) =>
                apiCall("/multi-db/bim/create-relationships", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** GET /v2/multi-db/bim/related-elements/{element_id} — Get related elements from Neo4j */
        getRelatedElements: (elementId: string) =>
                apiCall(`/multi-db/bim/related-elements/${elementId}`, undefined, API_V2_BASE),
};

// ─── CAD Generic API (backend/routers/cad.py) ──────────────────────────────

export const cadApi = {
        /** POST /cad/connect — Connect to a CAD application */
        connect: (data: { provider?: string; simulation_mode?: boolean }) =>
                apiCall("/cad/connect", { method: "POST", body: JSON.stringify(data) }),

        /** POST /cad/disconnect — Disconnect from CAD application */
        disconnect: () =>
                apiCall("/cad/disconnect", { method: "POST" }),

        /** GET /cad/status — Get CAD connection status */
        getStatus: () =>
                apiCall("/cad/status", { method: "GET" }),

        /** POST /cad/read — Read a CAD drawing */
        read: (data: { file_path?: string; format?: string }) =>
                apiCall("/cad/read", { method: "POST", body: JSON.stringify(data) }),

        /** POST /cad/write — Write a CAD drawing */
        write: (data: { file_path?: string; format?: string; data?: Record<string, unknown> }) =>
                apiCall("/cad/write", { method: "POST", body: JSON.stringify(data) }),

        /** POST /cad/draw_line — Draw a line in CAD */
        drawLine: (data: { start_x: number; start_y: number; end_x: number; end_y: number; layer?: string }) =>
                apiCall("/cad/draw_line", { method: "POST", body: JSON.stringify(data) }),

        /** POST /cad/draw_polyline — Draw a polyline in CAD */
        drawPolyline: (data: { points: number[][]; layer?: string; closed?: boolean }) =>
                apiCall("/cad/draw_polyline", { method: "POST", body: JSON.stringify(data) }),

        /** POST /cad/draw_circle — Draw a circle in CAD */
        drawCircle: (data: { center_x: number; center_y: number; radius: number; layer?: string }) =>
                apiCall("/cad/draw_circle", { method: "POST", body: JSON.stringify(data) }),

        /** POST /cad/draw_text — Draw text in CAD */
        drawText: (data: { x: number; y: number; text: string; height?: number; layer?: string }) =>
                apiCall("/cad/draw_text", { method: "POST", body: JSON.stringify(data) }),
};

// ─── Analyze API (backend/routers/analyze.py) ──────────────────────────────

export const analyzeApi = {
        /** POST /analyze/battery — Analyze battery capacity (NFPA 72 §10.6.7) */
        battery: (data: { standby_load_a: number; alarm_load_a: number; standby_hours?: number; alarm_minutes?: number }) =>
                apiCall("/analyze/battery", { method: "POST", body: JSON.stringify(data) }),

        /** POST /analyze/voltage — Analyze voltage drop (NEC Ch.9 Table 8) */
        voltage: (data: { current_a: number; length_m: number; awg_gauge: string; supply_voltage_v?: number }) =>
                apiCall("/analyze/voltage", { method: "POST", body: JSON.stringify(data) }),

        /** POST /projects/{project_id}/analyze/room — Full room analysis */
        room: (projectId: string, data: { room_name?: string; area_m2?: number; ceiling_height_m?: number }) =>
                apiCall(`/projects/${encodeURIComponent(projectId)}/analyze/room`, { method: "POST", body: JSON.stringify(data) }),
};

// ─── Admin Config API (backend/routers/admin_config.py) ────────────────────

export const adminConfigApi = {
        /** GET /feature-flags — List all feature flags */
        getFeatureFlags: () =>
                apiCall("/feature-flags", { method: "GET" }),

        /** POST /feature-flags — Update a feature flag */
        setFeatureFlag: (data: { flag: string; enabled: boolean }) =>
                apiCall("/feature-flags", { method: "POST", body: JSON.stringify(data) }),

        /** GET /env-config — Get environment configuration */
        getEnvConfig: () =>
                apiCall("/env-config", { method: "GET" }),

        /** PUT /env-config — Update environment configuration */
        updateEnvConfig: (data: Record<string, unknown>) =>
                apiCall("/env-config", { method: "PUT", body: JSON.stringify(data) }),

        /** POST /settings/secret-rotation/rotate — Rotate secrets */
        rotateSecret: (data: { secret_type?: string }) =>
                apiCall("/settings/secret-rotation/rotate", { method: "POST", body: JSON.stringify(data) }),

        /** POST /settings/admin-token/rotate — Rotate admin token */
        rotateAdminToken: () =>
                apiCall("/settings/admin-token/rotate", { method: "POST" }),
};

// ─── Connections V2 API (backend/routers/connections_v2.py) ─────────────────

export const connectionsV2Api = {
        /** GET /connections — List all connections (v2, non-project-scoped) */
        list: () =>
                apiCall("/connections", { method: "GET" }),

        /** POST /connections — Create a new connection */
        create: (data: Record<string, unknown>) =>
                apiCall("/connections", { method: "POST", body: JSON.stringify(data) }),

        /** PUT /connections/{connection_id} — Update a connection */
        update: (connectionId: string, data: Record<string, unknown>) =>
                apiCall(`/connections/${encodeURIComponent(connectionId)}`, { method: "PUT", body: JSON.stringify(data) }),

        /** DELETE /connections/{connection_id} — Delete a connection */
        delete: (connectionId: string) =>
                apiCall(`/connections/${encodeURIComponent(connectionId)}`, { method: "DELETE" }),
};

// ─── Elements API (backend/routers/elements.py) ────────────────────────────

export const elementsApi = {
        /** GET /elements — List all elements */
        list: () =>
                apiCall("/elements", { method: "GET" }),

        /** POST /elements — Create a new element */
        create: (data: Record<string, unknown>) =>
                apiCall("/elements", { method: "POST", body: JSON.stringify(data) }),

        /** GET /elements/{element_id} — Get element by ID */
        get: (elementId: string) =>
                apiCall(`/elements/${encodeURIComponent(elementId)}`, { method: "GET" }),

        /** PUT /elements/{element_id} — Update an element */
        update: (elementId: string, data: Record<string, unknown>) =>
                apiCall(`/elements/${encodeURIComponent(elementId)}`, { method: "PUT", body: JSON.stringify(data) }),

        /** DELETE /elements/{element_id} — Delete an element */
        delete: (elementId: string) =>
                apiCall(`/elements/${encodeURIComponent(elementId)}`, { method: "DELETE" }),
};

// ─── DWG Parser API (backend/routers/dwg.py) ──────────────────────────────

export const dwgApi = {
        /** POST /parse-dwg — Parse a DWG/DXF file */
        parse: (file: File) => {
                const formData = new FormData();
                formData.append("file", file);
                return apiCall("/parse-dwg", {
                        method: "POST",
                        body: formData,
                        headers: {},
                });
        },
};

// ─── Engineering Copilot Full API (backend/routers/engineering_copilot.py) ─

export const copilotApi = {
        /** POST /engineering-copilot/chat — Chat with the engineering copilot */
        chat: (data: { request: string; context?: Record<string, unknown> }) =>
                apiCall("/engineering-copilot/chat", { method: "POST", body: JSON.stringify(data) }),

        /** POST /engineering-copilot/process-request — Process an engineering request */
        processRequest: (data: { request_type: string; parameters: Record<string, unknown> }) =>
                apiCall("/engineering-copilot/process-request", { method: "POST", body: JSON.stringify(data) }),

        /** POST /engineering-copilot/create-entity — Create an engineering entity */
        createEntity: (data: { name: string; entity_type: string; description?: string; coordinates?: Record<string, number>; properties?: Record<string, unknown> }) =>
                apiCall("/engineering-copilot/create-entity", { method: "POST", body: JSON.stringify(data) }),

        /** GET /engineering-copilot/health — Health check */
        getHealth: () =>
                apiCall("/engineering-copilot/health", { method: "GET" }),

        /** GET /engineering-copilot/capabilities — List copilot capabilities */
        getCapabilities: () =>
                apiCall("/engineering-copilot/capabilities", { method: "GET" }),
};

// ─── Environment Region API (backend/routers/environment.py) ───────────────

export const environmentRegionApi = {
        /** GET /environment/region — Get region information */
        getRegion: (params?: { lat?: number; lon?: number; address?: string }) => {
                const query = new URLSearchParams();
                if (params?.lat) query.set("lat", String(params.lat));
                if (params?.lon) query.set("lon", String(params.lon));
                if (params?.address) query.set("address", params.address);
                const qs = query.toString();
                return apiCall(`/environment/region${qs ? `?${qs}` : ""}`, { method: "GET" });
        },
};

// ─── Experimental Services API (backend/routers/experimental_services.py) ──

export const experimentalApi = {
        /** GET /experimental/features — List experimental features and their status */
        getFeatures: () =>
                apiCall("/experimental/features", { method: "GET" }),

        /** POST /experimental/ocr/process — Process OCR on a PDF/image */
        processOcr: (data: { file_url?: string; language?: string }) =>
                apiCall("/experimental/ocr/process", { method: "POST", body: JSON.stringify(data) }),

        /** POST /experimental/scan-to-bim/process — Scan-to-BIM processing */
        processScanToBim: (data: { file_url?: string; project_id?: string }) =>
                apiCall("/experimental/scan-to-bim/process", { method: "POST", body: JSON.stringify(data) }),

        /** POST /experimental/speckle/push — Push elements to Speckle */
        specklePush: (data: { stream_id?: string; elements?: Record<string, unknown>[] }) =>
                apiCall("/experimental/speckle/push", { method: "POST", body: JSON.stringify(data) }),

        /** POST /experimental/speckle/receive — Receive elements from Speckle */
        speckleReceive: (data: { stream_id?: string; commit_id?: string }) =>
                apiCall("/experimental/speckle/receive", { method: "POST", body: JSON.stringify(data) }),
};

// ─── Health API (backend/routers/health.py) ────────────────────────────────

export const healthApi = {
        /** GET /health — Basic health check */
        check: () =>
                apiCall("/health", { method: "GET" }, API_BASE.replace("/api/v1", "/api")),

        /** GET /health/statistics — Detailed health statistics */
        getStatistics: () =>
                apiCall("/health/statistics", { method: "GET" }, API_BASE.replace("/api/v1", "/api")),

        /** GET /reports/statistics — Legacy alias for /health/statistics */
        getReportsStatistics: () =>
                apiCall("/reports/statistics", { method: "GET" }, API_BASE.replace("/api/v1", "/api")),
};

// ─── LLM Extended API (backend/routers/llm.py) ────────────────────────────

export const llmExtendedApi2 = {
        /** POST /llm/chat — Non-streaming chat completion */
        chat: (data: { prompt: string; system?: string; model?: string; temperature?: number; max_tokens?: number }) =>
                apiCall("/llm/chat", { method: "POST", body: JSON.stringify(data) }),

        /** GET /llm/health — LLM service health check */
        getHealth: () =>
                apiCall("/llm/health", { method: "GET" }),
};

// ─── RBAC Admin API (backend/routers/rbac_admin.py) ────────────────────────

export const rbacApi = {
        /** GET /admin/rbac/permissions — Get role-permission matrix */
        getPermissions: () =>
                apiCall("/admin/rbac/permissions", { method: "GET" }),
};

// ─── Settings API (backend/routers/settings.py) ────────────────────────────

export const settingsApi = {
        /** GET /settings/keys/providers/list — List supported key providers */
        listProviders: () =>
                apiCall("/settings/keys/providers/list", { method: "GET" }),

        /** POST /settings/keys/{provider} — Store a provider key */
        storeKey: (provider: string, data: { key: string; label?: string }) =>
                apiCall(`/settings/keys/${encodeURIComponent(provider)}`, { method: "POST", body: JSON.stringify(data) }),

        /** POST /settings/keys/openai — Store OpenAI key (compat alias) */
        storeOpenaiKey: (data: { key: string; label?: string }) =>
                apiCall("/settings/keys/openai", { method: "POST", body: JSON.stringify(data) }),

        /** GET /settings/keys/{provider} — List keys for a provider */
        listKeys: (provider: string) =>
                apiCall(`/settings/keys/${encodeURIComponent(provider)}`, { method: "GET" }),

        /** GET /settings/keys/openai — List OpenAI keys (compat alias) */
        listOpenaiKeys: () =>
                apiCall("/settings/keys/openai", { method: "GET" }),

        /** GET /settings/keys/{provider}/{key_id} — Get a specific key */
        getKey: (provider: string, keyId: string) =>
                apiCall(`/settings/keys/${encodeURIComponent(provider)}/${encodeURIComponent(keyId)}`, { method: "GET" }),

        /** DELETE /settings/keys/{provider}/{key_id} — Delete a key */
        deleteKey: (provider: string, keyId: string) =>
                apiCall(`/settings/keys/${encodeURIComponent(provider)}/${encodeURIComponent(keyId)}`, { method: "DELETE" }),

        /** POST /settings/keys/{provider}/bulk-delete — Bulk delete keys */
        bulkDeleteKeys: (provider: string, data: { key_ids: string[] }) =>
                apiCall(`/settings/keys/${encodeURIComponent(provider)}/bulk-delete`, { method: "POST", body: JSON.stringify(data) }),

        /** POST /settings/keys/{provider}/{key_id}/test — Test a key */
        testKey: (provider: string, keyId: string) =>
                apiCall(`/settings/keys/${encodeURIComponent(provider)}/${encodeURIComponent(keyId)}/test`, { method: "POST" }),

        /** GET /settings/keys/openai/{key_id} — Get OpenAI key (compat alias) */
        getOpenaiKey: (keyId: string) =>
                apiCall(`/settings/keys/openai/${encodeURIComponent(keyId)}`, { method: "GET" }),

        /** DELETE /settings/keys/openai/{key_id} — Delete OpenAI key (compat alias) */
        deleteOpenaiKey: (keyId: string) =>
                apiCall(`/settings/keys/openai/${encodeURIComponent(keyId)}`, { method: "DELETE" }),

        /** POST /settings/keys/openai/{key_id}/test — Test OpenAI key (compat alias) */
        testOpenaiKey: (keyId: string) =>
                apiCall(`/settings/keys/openai/${encodeURIComponent(keyId)}/test`, { method: "POST" }),
};

// ─── Digital Twin Upload-and-Convert API ────────────────────────────────────

export const digitalTwinUploadApi = {
        /** POST /digital-twin/upload-and-convert — Upload file and convert in one step */
        uploadAndConvert: (file: File, options?: { target_format?: string; mapping_profile?: string }) => {
                const formData = new FormData();
                formData.append("file", file);
                if (options?.target_format) formData.append("target_format", options.target_format);
                if (options?.mapping_profile) formData.append("mapping_profile", options.mapping_profile);
                return apiCall("/digital-twin/upload-and-convert", {
                        method: "POST",
                        body: formData,
                        headers: {},
                });
        },
};

// ─── APS API (backend/routers/aps.py) ──────────────────────────────────────

export const apsApi = {
        /** POST /aps/process — Submit file to Autodesk Cloud for processing */
        process: (data: { input_urn: string; output_urn: string; activity_id?: string; params?: Record<string, unknown> }) =>
                apiCall("/aps/process", { method: "POST", body: JSON.stringify(data) }, API_V2_BASE),

        /** GET /aps/status/{work_item_id} — Get APS work item status */
        getStatus: (workItemId: string) =>
                apiCall(`/aps/status/${encodeURIComponent(workItemId)}`, { method: "GET" }, API_V2_BASE),
};

// ─── Revit Integration API (APS-based cloud sync) ──────────────────────────

export const revitIntegrationApi = {
        /** POST /revit-integration/upload — Upload a Revit model file for processing */
        uploadModel: (projectId: string, file: File) => {
                const formData = new FormData();
                formData.append("file", file);
                return apiCall(`/revit-integration/upload?project_id=${encodeURIComponent(projectId)}`, {
                        method: "POST",
                        body: formData,
                        headers: {},
                });
        },

        /** POST /revit-integration/sync — Initiate synchronization of a Revit model */
        syncModel: (data: { project_id: string; incremental?: boolean; force_full_sync?: boolean }) =>
                apiCall("/revit-integration/sync", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /revit-integration/model/{model_id} — Retrieve a specific Revit model */
        getModel: (modelId: string) =>
                apiCall(`/revit-integration/model/${modelId}`),

        /** POST /revit-integration/export — Export Revit data in various formats */
        exportData: (data: { project_id: string; format: string; include_electrical?: boolean; include_structural?: boolean; include_architectural?: boolean }) =>
                apiCall("/revit-integration/export", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /revit-integration/status — Get synchronization status of a Revit project */
        getSyncStatus: (projectId: string) =>
                apiCall(`/revit-integration/status?project_id=${encodeURIComponent(projectId)}`),
};

// ─── Sync API (backend/routers/sync.py) ─────────────────────────────────────

export const syncApi = {
        /** POST /projects/{project_id}/sync — Trigger project synchronization */
        syncProject: (projectId: string) =>
                apiCall(`/projects/${encodeURIComponent(projectId)}/sync`, {
                        method: "POST",
                }),

        /** GET /projects/{project_id}/sync — Get project sync status */
        getSyncStatus: (projectId: string) =>
                apiCall(`/projects/${encodeURIComponent(projectId)}/sync`),
};

// ─── Reports API (backend/routers/reports.py) ────────────────────────────────

export const reportsApi = {
        /** GET /projects/{project_id}/reports — List reports for a project */
        list: (projectId: string, params?: { page?: number; limit?: number; type?: string }) => {
                const query = new URLSearchParams();
                if (params?.page) query.set("page", String(params.page));
                if (params?.limit) query.set("limit", String(params.limit));
                if (params?.type) query.set("type", params.type);
                const qs = query.toString();
                return apiCall(`/projects/${encodeURIComponent(projectId)}/reports${qs ? `?${qs}` : ""}`);
        },

        /** POST /projects/{project_id}/reports — Generate a new report */
        generate: (projectId: string, data: { report_type: string; config?: Record<string, unknown> }) =>
                apiCall(`/projects/${encodeURIComponent(projectId)}/reports`, {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** POST /reports/generate — Generate a global report (no project_id in URL) */
        generateGlobal: (data: { project_id: string; report_type: string; config?: Record<string, unknown> }) =>
                apiCall("/reports/generate", {
                        method: "POST",
                        body: JSON.stringify(data),
                }),

        /** GET /projects/{project_id}/reports/{report_id} — Get a specific report */
        get: (projectId: string, reportId: string) =>
                apiCall(`/projects/${encodeURIComponent(projectId)}/reports/${encodeURIComponent(reportId)}`),

        /** GET /projects/{project_id}/reports/{report_id}/export — Export a report (PDF or DXF) */
        exportReport: (projectId: string, reportId: string, format: string = "pdf") =>
                apiCall(`/projects/${encodeURIComponent(projectId)}/reports/${encodeURIComponent(reportId)}/export?format=${encodeURIComponent(format)}`),

        /** POST /projects/{project_id}/reports/ahj-submittal — Generate AHJ submittal document */
        generateAhjSubmittal: (projectId: string, data: { designer?: string; jurisdiction?: string; nfpa_edition?: string }) =>
                apiCall(`/projects/${encodeURIComponent(projectId)}/reports/ahj-submittal`, {
                        method: "POST",
                        body: JSON.stringify(data),
                }),
};

export default fullApi;


