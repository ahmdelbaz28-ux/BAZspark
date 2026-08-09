/**
 * IEnvironmentRepository.ts — Domain Repository Interface for Environmental Context APIs.
 * Follows Clean Architecture (Domain Layer: Repository Abstraction).
 */

export interface EnvironmentalContext {
	weather?: {
		temperature?: number;
		humidity?: number;
		windSpeed?: number;
		condition?: string;
	};
	airQuality?: {
		aqi?: number;
		pm25?: number;
		pm10?: number;
		status?: string;
	};
	earthquakeAlerts?: Array<{
		magnitude: number;
		location: string;
		distanceKm: number;
		timestamp: string;
	}>;
	hazmatProximity?: Array<{
		facilityName: string;
		hazardType: string;
		distanceKm: number;
	}>;
}

export interface IEnvironmentRepository {
	getEnvironmentalContext(
		lat: number,
		lon: number,
	): Promise<EnvironmentalContext>;
	getWeatherForecast(location: string): Promise<Record<string, unknown>>;
	getAirQualityData(lat: number, lon: number): Promise<Record<string, unknown>>;
}
