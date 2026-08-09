/**
 * ContextPage.tsx — Environmental Context (Weather + Geocoding + Region).
 *
 * Provides weather data, geocoding, and regulatory region info
 * for engineering calculations.
 *
 * Backend:
 *   GET /environment/weather?lat=...&lon=...
 *   GET /environment/geocode?address=...
 *   GET /environment/context?lat=...&lon=...
 *   GET /environment/region?country_code=...
 */

import {
	Droplets,
	Globe,
	Landmark,
	Loader2,
	MapPin,
	Search,
	Thermometer,
	Wind,
} from "lucide-react";
import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

interface WeatherData {
	temperature_c: number;
	wind_speed_m_s: number;
	relative_humidity_pct: number;
	air_density_kg_m3: number;
	source: string;
	is_default: boolean;
	location: { latitude: number; longitude: number };
}

interface GeoData {
	latitude: number;
	longitude: number;
	display_name: string;
	country_code: string;
}

interface RegionData {
	country_code: string;
	country_name: string;
	regulatory_framework: string;
	electrical_code: string;
	is_gulf_state: boolean;
	is_eu: boolean;
}

export const ContextPage: React.FC = () => {
	const [lat, setLat] = useState("30.0444");
	const [lon, setLon] = useState("31.2357");
	const [address, setAddress] = useState("");
	const [weather, setWeather] = useState<WeatherData | null>(null);
	const [geocode, setGeocode] = useState<GeoData | null>(null);
	const [region, setRegion] = useState<RegionData | null>(null);
	const [loading, setLoading] = useState(false);
	const [geoLoading, setGeoLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const fetchWeather = async () => {
		setLoading(true);
		setError(null);
		try {
			const res = await fetch(
				`${API_BASE}/environment/weather?lat=${lat}&lon=${lon}`,
				{ credentials: "same-origin" },
			);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const json = await res.json();
			setWeather(json.data);
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to fetch weather");
		} finally {
			setLoading(false);
		}
	};

	const fetchGeocode = async () => {
		if (!address.trim()) return;
		setGeoLoading(true);
		setError(null);
		try {
			const res = await fetch(
				`${API_BASE}/environment/geocode?address=${encodeURIComponent(address)}`,
				{ credentials: "same-origin" },
			);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const json = await res.json();
			if (json.success && json.data) {
				setGeocode(json.data);
				setLat(String(json.data.latitude));
				setLon(String(json.data.longitude));
				// Fetch region for this country
				const regRes = await fetch(
					`${API_BASE}/environment/region?country_code=${json.data.country_code}`,
					{ credentials: "same-origin" },
				);
				if (regRes.ok) {
					const regJson = await regRes.json();
					if (regJson.success) setRegion(regJson.data);
				}
			} else {
				setError(json.error || "Geocoding failed");
			}
		} catch (err) {
			setError(err instanceof Error ? err.message : "Geocoding failed");
		} finally {
			setGeoLoading(false);
		}
	};

	return (
		<div className="flex-1 overflow-auto">
			<div className="p-6 max-w-5xl mx-auto space-y-6">
				{/* Header */}
				<div>
					<h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
						<Wind className="h-6 w-6 text-cyan-400" />
						Weather &amp; Geocoding
					</h1>
					<p className="text-slate-400 text-sm mt-1">
						Environmental context for engineering calculations — weather data,
						address geocoding, and regulatory region lookup
					</p>
				</div>

				{error && (
					<div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
						<p className="text-sm text-red-400">{error}</p>
					</div>
				)}

				<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
					{/* ── Weather Panel ── */}
					<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
						<h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4">
							<Thermometer className="h-4 w-4 text-cyan-400" />
							Current Weather
						</h3>
						<div className="grid grid-cols-2 gap-3 mb-4">
							<div>
								<label className="block text-xs text-slate-500 mb-1">
									Latitude
								</label>
								<input
									type="number"
									step="0.0001"
									value={lat}
									onChange={(e) => setLat(e.target.value)}
									className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
								/>
							</div>
							<div>
								<label className="block text-xs text-slate-500 mb-1">
									Longitude
								</label>
								<input
									type="number"
									step="0.0001"
									value={lon}
									onChange={(e) => setLon(e.target.value)}
									className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
								/>
							</div>
						</div>
						<button
							type="button"
							onClick={fetchWeather}
							disabled={loading}
							className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
						>
							{loading ? (
								<Loader2 className="h-4 w-4 animate-spin" />
							) : (
								<Search className="h-4 w-4" />
							)}
							Get Weather
						</button>

						{weather && (
							<div className="mt-4 space-y-3">
								<div className="grid grid-cols-2 gap-3">
									<div className="bg-slate-700/30 rounded-lg p-3 text-center">
										<Thermometer className="h-4 w-4 text-cyan-400 mx-auto mb-1" />
										<div className="text-lg font-bold text-slate-100 font-mono">
											{weather.temperature_c}°C
										</div>
										<div className="text-[10px] text-slate-500">
											Temperature
										</div>
									</div>
									<div className="bg-slate-700/30 rounded-lg p-3 text-center">
										<Wind className="h-4 w-4 text-cyan-400 mx-auto mb-1" />
										<div className="text-lg font-bold text-slate-100 font-mono">
											{weather.wind_speed_m_s} m/s
										</div>
										<div className="text-[10px] text-slate-500">Wind Speed</div>
									</div>
									<div className="bg-slate-700/30 rounded-lg p-3 text-center">
										<Droplets className="h-4 w-4 text-cyan-400 mx-auto mb-1" />
										<div className="text-lg font-bold text-slate-100 font-mono">
											{weather.relative_humidity_pct}%
										</div>
										<div className="text-[10px] text-slate-500">Humidity</div>
									</div>
									<div className="bg-slate-700/30 rounded-lg p-3 text-center">
										<Wind className="h-4 w-4 text-cyan-400 mx-auto mb-1" />
										<div className="text-lg font-bold text-slate-100 font-mono">
											{weather.air_density_kg_m3} kg/m³
										</div>
										<div className="text-[10px] text-slate-500">
											Air Density
										</div>
									</div>
								</div>
								<div className="text-[10px] text-slate-500 text-center">
									Source: {weather.source} {weather.is_default && "(default)"}
								</div>
							</div>
						)}
					</div>

					{/* ── Geocoding Panel ── */}
					<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
						<h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2 mb-4">
							<MapPin className="h-4 w-4 text-cyan-400" />
							Geocoding &amp; Region
						</h3>
						<div className="flex gap-2 mb-4">
							<input
								type="text"
								value={address}
								onChange={(e) => setAddress(e.target.value)}
								onKeyDown={(e) => e.key === "Enter" && fetchGeocode()}
								placeholder="Enter address (e.g., Cairo, Egypt)"
								className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
							/>
							<button
								type="button"
								onClick={fetchGeocode}
								disabled={geoLoading || !address.trim()}
								className="px-3 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white rounded-lg transition-colors"
							>
								{geoLoading ? (
									<Loader2 className="h-4 w-4 animate-spin" />
								) : (
									<Search className="h-4 w-4" />
								)}
							</button>
						</div>

						{geocode && (
							<div className="space-y-2">
								<div className="bg-slate-700/30 rounded-lg p-3">
									<p className="text-[10px] text-slate-500 mb-1">Address</p>
									<p className="text-xs text-slate-200">
										{geocode.display_name}
									</p>
								</div>
								<div className="grid grid-cols-2 gap-2">
									<div className="bg-slate-700/30 rounded-lg p-2.5 text-center">
										<div className="text-[10px] text-slate-500">Lat</div>
										<div className="text-xs font-mono text-slate-200">
											{geocode.latitude.toFixed(4)}
										</div>
									</div>
									<div className="bg-slate-700/30 rounded-lg p-2.5 text-center">
										<div className="text-[10px] text-slate-500">Lon</div>
										<div className="text-xs font-mono text-slate-200">
											{geocode.longitude.toFixed(4)}
										</div>
									</div>
								</div>
								{region && (
									<>
										<div className="border-t border-slate-700 pt-2 mt-2">
											<h4 className="text-xs font-medium text-slate-400 flex items-center gap-1 mb-2">
												<Landmark className="h-3 w-3" />
												Regulatory Region
											</h4>
											<div className="grid grid-cols-2 gap-2">
												<div className="bg-slate-700/30 rounded-lg p-2">
													<div className="text-[10px] text-slate-500">
														Country
													</div>
													<div className="text-xs text-slate-200">
														{region.country_name}
													</div>
												</div>
												<div className="bg-slate-700/30 rounded-lg p-2">
													<div className="text-[10px] text-slate-500">
														Framework
													</div>
													<div className="text-xs text-slate-200">
														{region.regulatory_framework}
													</div>
												</div>
												<div className="bg-slate-700/30 rounded-lg p-2">
													<div className="text-[10px] text-slate-500">
														Electrical Code
													</div>
													<div className="text-xs text-slate-200">
														{region.electrical_code}
													</div>
												</div>
												<div className="bg-slate-700/30 rounded-lg p-2">
													<div className="text-[10px] text-slate-500">
														Country Code
													</div>
													<div className="text-xs text-slate-200 font-mono">
														{region.country_code}
													</div>
												</div>
											</div>
										</div>
									</>
								)}
							</div>
						)}

						{!geocode && !geoLoading && (
							<div className="flex flex-col items-center justify-center py-8 text-slate-500">
								<Globe className="h-8 w-8 mb-2 opacity-30" />
								<p className="text-xs">
									Search for an address to see location and regulatory data
								</p>
							</div>
						)}
					</div>
				</div>

				{/* Info */}
				<div className="bg-slate-800/30 border border-slate-700/50 rounded-lg p-4">
					<p className="text-xs text-slate-500">
						Weather data sourced from Open-Meteo (free, no auth). Geocoding via
						Nominatim/OpenStreetMap. Regulatory region data provides applicable
						fire and electrical codes for engineering calculations.
					</p>
				</div>
			</div>
		</div>
	);
};

export default ContextPage;
