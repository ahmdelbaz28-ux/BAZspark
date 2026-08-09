import { ApiClient } from "./apiClient";
import type { SimReadyConvertRequest, SimReadyConvertResponse } from "../types/simready";

const apiClient = new ApiClient();

export async function convertSimReady(
	payload: SimReadyConvertRequest,
): Promise<SimReadyConvertResponse> {
	return apiClient.post<SimReadyConvertResponse>(
		"/digital-twin/cad-to-simready",
		payload,
	);
}
