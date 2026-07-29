/**
 * miningApi.ts — Mining fire protection API client.
 *
 * V214: Exposes the 6 mining endpoints from backend/routers/mining.py:
 *   GET  /api/v1/mining/standards
 *   POST /api/v1/mining/methane-check
 *   POST /api/v1/mining/ventilation-check
 *   POST /api/v1/mining/co-check
 *   POST /api/v1/mining/conveyor-suppression
 *   POST /api/v1/mining/compliance-report
 *
 * Standards: NFPA 120-2022, NFPA 122-2022, MSHA 30 CFR Part 75, IEC 60079-10-1
 */

import { ApiClient } from "./apiClient";

const client = new ApiClient("/api/v1");

export const miningApi = {
        /** GET /mining/standards — List supported mining standards */
        getStandards: () =>
                client.get<{
                        success: boolean;
                        standards: Array<{ code: string; title: string }>;
                }>("/mining/standards"),

        /** POST /mining/methane-check — Classify methane hazard per MSHA §75.323 */
        methaneCheck: (data: { concentration_pct: number; location?: string }) =>
                client.post<{
                        success: boolean;
                        concentration_pct: number;
                        hazard_level: string;
                        is_in_explosive_range: boolean;
                        distance_to_lel_pct: number;
                        location: string;
                        standard: string;
                        thresholds: Record<string, number>;
                }>("/mining/methane-check", data),

        /** POST /mining/ventilation-check — Check MSHA ventilation compliance */
        ventilationCheck: (data: {
                airflow_m3_s: number;
                location_type?: string;
                cross_sectional_area_m2?: number;
        }) =>
                client.post<{
                        success: boolean;
                        airflow_m3_s: number;
                        location_type: string;
                        is_compliant: boolean;
                        violations: string[];
                        velocity_m_s: number | null;
                        standard: string;
                }>("/mining/ventilation-check", data),

        /** POST /mining/co-check — Classify CO hazard per MSHA §75.351 */
        coCheck: (data: { co_ppm: number }) =>
                client.post<{
                        success: boolean;
                        co_ppm: number;
                        hazard_level: string;
                        thresholds: Record<string, number>;
                        standard: string;
                }>("/mining/co-check", data),

        /** POST /mining/conveyor-suppression — Design suppression per NFPA 120 §8.4 */
        conveyorSuppression: (data: {
                belt_length_m: number;
                belt_width_m: number;
                belt_speed_m_s?: number;
                has_fire_resistant_belt?: boolean;
        }) =>
                client.post<{
                        success: boolean;
                        design: {
                                number_of_nozzle_groups: number;
                                water_flow_rate_lpm: number;
                                water_duration_min: number;
                                total_water_volume_l: number;
                                nozzle_locations: string[];
                                is_compliant: boolean;
                                violations: string[];
                        };
                        standard: string;
                }>("/mining/conveyor-suppression", data),

        /** POST /mining/compliance-report — Full MSHA + NFPA 120 compliance report */
        complianceReport: (data: {
                mine_name: string;
                section_name: string;
                methane_pct?: number;
                co_ppm?: number;
                airflow_m3_s?: number;
                ventilation_location?: string;
                conveyor_length_m?: number;
                conveyor_width_m?: number;
                has_fire_resistant_belt?: boolean;
        }) =>
                client.post<{
                        success: boolean;
                        overall_status: string;
                        checks: Array<{
                                rule_id: string;
                                standard: string;
                                description: string;
                                status: string;
                                details: string;
                                remediation: string;
                        }>;
                        markdown_report: string;
                }>("/mining/compliance-report", data),
};