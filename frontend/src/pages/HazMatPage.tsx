/**
 * HazMatPage.tsx — Hazardous Materials Database for Engineering Calculations.
 *
 * Search hazardous materials and view their properties for HAC zone
 * classification, temperature class, and equipment group selection.
 *
 * Backend:
 *   GET /environment/hazmat?material=...
 *   GET /environment/hazmat/known
 */

import {
	AlertTriangle,
	Beaker,
	BookOpen,
	FlaskConical,
	Loader2,
	Search,
	Thermometer,
} from "lucide-react";
import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_URL || "/api/v1";

interface HazMatData {
	name: string;
	cas_number: string;
	lfl_vol_pct: number;
	ufl_vol_pct: number;
	flammable_range_vol_pct: string;
	flash_point_c: number;
	auto_ignition_c: number;
	material_group: string;
	temperature_class: string;
	molecular_weight: number;
	vapor_density: number;
	source: string;
	is_default: boolean;
	is_conservative: boolean;
	engineering_notes: {
		hac: string;
		equipment: string;
	};
}

export const HazMatPage: React.FC = () => {
	const [query, setQuery] = useState("");
	const [material, setMaterial] = useState<HazMatData | null>(null);
	const [knownMaterials, setKnownMaterials] = useState<string[]>([]);
	const [loading, setLoading] = useState(false);
	const [loadingKnown, setLoadingKnown] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchKnown = async () => {
			try {
				const res = await fetch(`${API_BASE}/environment/hazmat/known`, {
					credentials: "same-origin",
				});
				if (res.ok) {
					const json = await res.json();
					setKnownMaterials(json.data?.materials || []);
				}
			} catch {
				/* ignore */
			}
			setLoadingKnown(false);
		};
		fetchKnown();
	}, []);

	const fetchMaterial = async (name: string) => {
		setLoading(true);
		setError(null);
		try {
			const res = await fetch(
				`${API_BASE}/environment/hazmat?material=${encodeURIComponent(name)}`,
				{ credentials: "same-origin" },
			);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const json = await res.json();
			if (json.success && json.data) {
				setMaterial(json.data);
			} else {
				setError(json.error || "Material not found");
			}
		} catch (err) {
			setError(err instanceof Error ? err.message : "Failed to fetch material");
		} finally {
			setLoading(false);
		}
	};

	const handleSearch = () => {
		if (query.trim()) fetchMaterial(query.trim());
	};

	return (
		<div className="flex-1 overflow-auto">
			<div className="p-6 max-w-4xl mx-auto space-y-6">
				{/* Header */}
				<div>
					<h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
						<FlaskConical className="h-6 w-6 text-cyan-400" />
						Hazardous Materials Database
					</h1>
					<p className="text-slate-400 text-sm mt-1">
						Material properties for HAC zone classification, temperature class,
						and equipment group selection (IEC 60079 / NFPA 497)
					</p>
				</div>

				{/* Search */}
				<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
					<div className="flex gap-2">
						<input
							type="text"
							value={query}
							onChange={(e) => setQuery(e.target.value)}
							onKeyDown={(e) => e.key === "Enter" && handleSearch()}
							placeholder="Search material (e.g., methane, propane, hydrogen)"
							className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded-lg text-slate-100 text-sm placeholder-slate-500 focus:border-cyan-500 focus:outline-none"
						/>
						<button
							type="button"
							onClick={handleSearch}
							disabled={loading || !query.trim()}
							className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
						>
							{loading ? (
								<Loader2 className="h-4 w-4 animate-spin" />
							) : (
								<Search className="h-4 w-4" />
							)}
							Search
						</button>
					</div>

					{/* Known Materials */}
					{!loadingKnown && knownMaterials.length > 0 && (
						<div className="mt-3">
							<p className="text-[10px] text-slate-500 mb-1.5">
								Known materials:
							</p>
							<div className="flex flex-wrap gap-1.5">
								{knownMaterials.map((name) => (
									<button
										key={name}
										type="button"
										onClick={() => {
											setQuery(name);
											fetchMaterial(name);
										}}
										className="px-2 py-1 text-[11px] bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors"
									>
										{name}
									</button>
								))}
							</div>
						</div>
					)}
				</div>

				{/* Error */}
				{error && (
					<div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
						<p className="text-sm text-red-400">{error}</p>
					</div>
				)}

				{/* Material Results */}
				{material && (
					<div className="space-y-4">
						{/* Header Card */}
						<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
							<div className="flex items-center justify-between mb-3">
								<div>
									<h3 className="text-base font-semibold text-slate-100">
										{material.name}
									</h3>
									<p className="text-xs text-slate-500 mt-0.5">
										CAS: {material.cas_number}
									</p>
								</div>
								<span className="text-[10px] text-slate-500">
									{material.is_conservative
										? "Conservative estimate"
										: `Source: ${material.source}`}
								</span>
							</div>

							{/* Key Properties */}
							<div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
								<div className="bg-slate-700/30 rounded-lg p-3 text-center">
									<div className="text-[10px] text-slate-500 mb-1">
										Flammable Range
									</div>
									<div className="text-sm font-bold text-slate-100 font-mono">
										{material.lfl_vol_pct}% – {material.ufl_vol_pct}%
									</div>
								</div>
								<div className="bg-slate-700/30 rounded-lg p-3 text-center">
									<Thermometer className="h-3.5 w-3.5 text-amber-400 mx-auto mb-1" />
									<div className="text-sm font-bold text-slate-100 font-mono">
										{material.flash_point_c}°C
									</div>
									<div className="text-[10px] text-slate-500">Flash Point</div>
								</div>
								<div className="bg-slate-700/30 rounded-lg p-3 text-center">
									<AlertTriangle className="h-3.5 w-3.5 text-red-400 mx-auto mb-1" />
									<div className="text-sm font-bold text-slate-100 font-mono">
										{material.auto_ignition_c}°C
									</div>
									<div className="text-[10px] text-slate-500">
										Auto-Ignition
									</div>
								</div>
								<div className="bg-slate-700/30 rounded-lg p-3 text-center">
									<Beaker className="h-3.5 w-3.5 text-cyan-400 mx-auto mb-1" />
									<div className="text-sm font-bold text-slate-100 font-mono">
										{material.molecular_weight}
									</div>
									<div className="text-[10px] text-slate-500">Mol. Weight</div>
								</div>
							</div>
						</div>

						{/* Classification */}
						<div className="grid grid-cols-2 gap-4">
							<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
								<h4 className="text-xs font-medium text-slate-400 mb-3">
									Material Group
								</h4>
								<div className="text-lg font-bold text-cyan-400 font-mono">
									{material.material_group}
								</div>
								<p className="text-[10px] text-slate-500 mt-1">
									Per IEC 60079-0 Table 1
								</p>
							</div>
							<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-4">
								<h4 className="text-xs font-medium text-slate-400 mb-3">
									Temperature Class
								</h4>
								<div className="text-lg font-bold text-cyan-400 font-mono">
									{material.temperature_class}
								</div>
								<p className="text-[10px] text-slate-500 mt-1">
									Per IEC 60079-0
								</p>
							</div>
						</div>

						{/* Engineering Notes */}
						<div className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
							<h4 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-3">
								<BookOpen className="h-3.5 w-3.5 text-cyan-400" />
								Engineering Notes
							</h4>
							<div className="space-y-3">
								<div className="bg-slate-700/20 rounded-lg p-3">
									<p className="text-xs text-slate-400 leading-relaxed">
										{material.engineering_notes.hac}
									</p>
								</div>
								<div className="bg-slate-700/20 rounded-lg p-3">
									<p className="text-xs text-slate-400 leading-relaxed">
										{material.engineering_notes.equipment}
									</p>
								</div>
							</div>
						</div>
					</div>
				)}

				{/* Info */}
				<div className="bg-slate-800/30 border border-slate-700/50 rounded-lg p-4">
					<p className="text-xs text-slate-500">
						Data sourced from internal IEC 60079-10-1 Table B.1 / NFPA 497
						database (12 common materials) with PubChem API fallback.
						Conservative defaults applied when exact data is unavailable.
						Temperature class determines maximum surface temperature for
						equipment in hazardous areas.
					</p>
				</div>
			</div>
		</div>
	);
};

export default HazMatPage;
