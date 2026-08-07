/**
 * AirQualityPage.tsx — Air Quality Monitoring for Engineering Calculations.
 *
 * Displays AQI, PM2.5, PM10 data and engineering notes on how
 * air quality affects tenability, detection, and occupant vulnerability.
 *
 * Backend: GET /environment/air-quality?lat=...&lon=...
 */
import { useState } from "react";
import { Search, Loader2, Wind, AlertTriangle, Info } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

interface AQData {
  aqi: number;
  aqi_level: string;
  pm25_ug_m3: number;
  pm10_ug_m3: number;
  is_unhealthy_baseline: boolean;
  source: string;
  is_default: boolean;
  is_stale: boolean;
  location: { latitude: number; longitude: number };
  engineering_notes: {
    tenability: string;
    detection: string;
  };
}

const AQI_COLORS: Record<string, string> = {
  good: "text-emerald-400",
  moderate: "text-amber-400",
  "unhealthy for sensitive groups": "text-orange-400",
  unhealthy: "text-red-400",
  "very unhealthy": "text-purple-400",
  hazardous: "text-rose-400",
};

const AQI_BG: Record<string, string> = {
  good: "bg-emerald-500/10 border-emerald-500/30",
  moderate: "bg-amber-500/10 border-amber-500/30",
  "unhealthy for sensitive groups": "bg-orange-500/10 border-orange-500/30",
  unhealthy: "bg-red-500/10 border-red-500/30",
  "very unhealthy": "bg-purple-500/10 border-purple-500/30",
  hazardous: "bg-rose-500/10 border-rose-500/30",
};

export const AirQualityPage: React.FC = () => {
  const [lat, setLat] = useState("30.0444");
  const [lon, setLon] = useState("31.2357");
  const [data, setData] = useState<AQData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAQ = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/environment/air-quality?lat=${lat}&lon=${lon}`,
        { credentials: "same-origin" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch air quality");
    } finally {
      setLoading(false);
    }
  };

  const level = data?.aqi_level?.toLowerCase() || "unknown";
  const colorClass = AQI_COLORS[level] || "text-slate-400";
  const bgClass = AQI_BG[level] || "bg-slate-500/10 border-slate-500/30";

  return (
    <div className="flex-1 overflow-auto">
      <div className="p-6 max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <Wind className="h-6 w-6 text-cyan-400" />
            Air Quality
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Real-time air quality index and particulate matter data for
            tenability and smoke detection calculations
          </p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {/* Location Input */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Latitude</label>
              <input
                type="number" step="0.0001"
                value={lat}
                onChange={(e) => setLat(e.target.value)}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Longitude</label>
              <input
                type="number" step="0.0001"
                value={lon}
                onChange={(e) => setLon(e.target.value)}
                className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm font-mono focus:border-cyan-500 focus:outline-none"
              />
            </div>
          </div>
          <button
            type="button"
            onClick={fetchAQ}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Check Air Quality
          </button>
        </div>

        {/* Results */}
        {data && (
          <div className="space-y-4">
            {/* AQI Card */}
            <div className={`rounded-xl p-6 border ${bgClass}`}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-200">Air Quality Index</h3>
                <span className={`text-xs font-medium ${colorClass}`}>
                  {data.is_default ? "Default (API unavailable)" : data.source}
                </span>
              </div>
              <div className="flex items-end gap-4">
                <div>
                  <div className={`text-5xl font-bold font-mono ${colorClass}`}>{data.aqi}</div>
                  <div className={`text-sm font-medium mt-1 capitalize ${colorClass}`}>
                    {data.aqi_level}
                  </div>
                </div>
                {data.is_unhealthy_baseline && (
                  <div className="flex items-center gap-1.5 text-xs text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-full">
                    <AlertTriangle className="h-3 w-3" />
                    Unhealthy Baseline
                  </div>
                )}
              </div>
            </div>

            {/* PM Details */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
                <h4 className="text-xs font-medium text-slate-400 mb-3">PM2.5 (Fine Particles)</h4>
                <div className="text-2xl font-bold text-slate-100 font-mono">{data.pm25_ug_m3} µg/m³</div>
                <p className="text-[10px] text-slate-500 mt-1">
                  Affects smoke detector response time estimation
                </p>
              </div>
              <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
                <h4 className="text-xs font-medium text-slate-400 mb-3">PM10 (Coarse Particles)</h4>
                <div className="text-2xl font-bold text-slate-100 font-mono">{data.pm10_ug_m3} µg/m³</div>
                <p className="text-[10px] text-slate-500 mt-1">
                  Affects visibility and egress path assessment
                </p>
              </div>
            </div>

            {/* Engineering Notes */}
            <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
              <h4 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-3">
                <Info className="h-3.5 w-3.5 text-cyan-400" />
                Engineering Impact
              </h4>
              <div className="space-y-3">
                <div className="bg-slate-700/20 rounded-lg p-3">
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {data.engineering_notes.tenability}
                  </p>
                </div>
                <div className="bg-slate-700/20 rounded-lg p-3">
                  <p className="text-xs text-slate-400 leading-relaxed">
                    {data.engineering_notes.detection}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Info */}
        <div className="bg-slate-800/30 border border-slate-700/50 rounded-lg p-4">
          <h4 className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
            Wildfire Smoke & Ambient Particulate Advisory (NFPA 72 §17.7)
          </h4>
          <p className="text-xs text-slate-400 mb-2">
            Elevated ambient PM2.5 from wildfire smoke or dust events can cause detector drift or false alarms.
          </p>
          {data && (
            <div className="mt-2 pt-2 border-t border-slate-700/50 flex items-center justify-between text-xs">
              <span className="text-slate-400">Detector False Alarm Advisory Risk:</span>
              <span className={`font-mono font-semibold px-2 py-0.5 rounded ${
                data.pm25_ug_m3 >= 35.5 ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'
              }`}>
                {data.pm25_ug_m3 >= 35.5 ? 'HIGH RISK' : 'LOW RISK'}
              </span>
            </div>
          )}
          <p className="text-[11px] text-slate-500 mt-2">
            Air quality data sourced from WAQI & Open-Meteo Air Quality API. Moderate AQI (100) is used as
            conservative default when external endpoints are offline per NFPA 72 / NFPA 130 safety protocol.
          </p>
        </div>
      </div>
    </div>
  );
};

export default AirQualityPage;

