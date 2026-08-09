/**
 * EnvironmentRepository.ts — Concrete implementation of IEnvironmentRepository.
 * Delegates environmental data retrieval to fullApi while maintaining clean domain interface contract.
 */

import type {
	EnvironmentalContext,
	IEnvironmentRepository,
} from "../../domain/repositories/IEnvironmentRepository";
import { fullApi } from "../../services/fullApi";

export class EnvironmentRepository implements IEnvironmentRepository {
	async getEnvironmentalContext(
		lat: number,
		lon: number,
	): Promise<EnvironmentalContext> {
		try {
			const res = await fullApi.getEnvironmentalContext(lat, lon);
			if (res?.data) {
				return res.data as EnvironmentalContext;
			}
			return {};
		} catch {
			return {};
		}
	}

	async getWeatherForecast(location: string): Promise<Record<string, unknown>> {
		try {
			const res = await fullApi.getWeatherForecast(location);
			return (res?.data as Record<string, unknown>) || {};
		} catch {
			return {};
		}
	}

	async getAirQualityData(
		lat: number,
		lon: number,
	): Promise<Record<string, unknown>> {
		try {
			const res = await fullApi.getAirQualityData(lat, lon);
			return (res?.data as Record<string, unknown>) || {};
		} catch {
			return {};
		}
	}
}

export const environmentRepository = new EnvironmentRepository();
