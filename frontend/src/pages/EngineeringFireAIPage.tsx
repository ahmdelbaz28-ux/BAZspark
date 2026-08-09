import { Building2, CheckCircle2, Flame, Loader2, XCircle } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiCall } from "@/services/fullApi";

export function EngineeringFireAIPage() {
	const { t } = useTranslation();
	const [activeTab, setActiveTab] = useState("room-analysis");
	const [loading, setLoading] = useState(false);
	const [roomResults, setRoomResults] = useState<Record<
		string,
		unknown
	> | null>(null);
	const [floorResults, setFloorResults] = useState<Record<
		string,
		unknown
	> | null>(null);
	const [roomId, setRoomId] = useState("");
	const [floorId, setFloorId] = useState("");

	const handleRoomAnalysis = async () => {
		setLoading(true);
		try {
			const result = await apiCall("/analyse", {
				method: "POST",
				body: JSON.stringify({ room_id: roomId }),
			});
			setRoomResults(result as Record<string, unknown>);
		} catch {
			setRoomResults({ error: "Analysis failed" });
		} finally {
			setLoading(false);
		}
	};

	const handleFloorAnalysis = async () => {
		setLoading(true);
		try {
			const result = await apiCall("/analyse/floor", {
				method: "POST",
				body: JSON.stringify({ floor_id: floorId }),
			});
			setFloorResults(result as Record<string, unknown>);
		} catch {
			setFloorResults({ error: "Analysis failed" });
		} finally {
			setLoading(false);
		}
	};

	const renderComplianceBadge = (compliant: boolean) => (
		<Badge
			variant={compliant ? "default" : "destructive"}
			className="flex items-center gap-1 w-fit"
		>
			{compliant ? (
				<CheckCircle2 className="h-3 w-3" />
			) : (
				<XCircle className="h-3 w-3" />
			)}
			{compliant ? t("fireai.compliant") : t("fireai.nonCompliant")}
		</Badge>
	);

	return (
		<div className="space-y-6 p-6">
			<div className="flex items-center gap-3">
				<Flame className="h-8 w-8 text-orange-500" />
				<div>
					<h1 className="text-2xl font-bold">{t("fireai.title")}</h1>
					<p className="text-muted-foreground">
						NFPA 72 Fire Protection Analysis
					</p>
				</div>
			</div>

			<Tabs value={activeTab} onValueChange={setActiveTab}>
				<TabsList>
					<TabsTrigger value="room-analysis">
						{t("fireai.roomAnalysis")}
					</TabsTrigger>
					<TabsTrigger value="floor-analysis">
						{t("fireai.floorAnalysis")}
					</TabsTrigger>
					<TabsTrigger value="acoustic-heatmap">
						NFPA 72 Acoustic Heatmap
					</TabsTrigger>
				</TabsList>

				<TabsContent value="room-analysis" className="space-y-4">
					<Card>
						<CardHeader>
							<CardTitle>{t("fireai.roomAnalysis")}</CardTitle>
							<CardDescription>{t("fireai.selectRoom")}</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div className="flex gap-4 items-end">
								<div className="flex-1 space-y-2">
									<Label htmlFor="room-id">Room ID</Label>
									<Input
										id="room-id"
										value={roomId}
										onChange={(e) => setRoomId(e.target.value)}
										placeholder="e.g., room-101"
									/>
								</div>
								<Button
									onClick={handleRoomAnalysis}
									disabled={loading || !roomId}
								>
									{loading ? (
										<Loader2 className="h-4 w-4 animate-spin mr-2" />
									) : (
										<Flame className="h-4 w-4 mr-2" />
									)}
									{t("fireai.analyzeRoom")}
								</Button>
							</div>
						</CardContent>
					</Card>

					{roomResults && (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2">
									{t("fireai.results")}
									{roomResults.compliant !== undefined &&
										renderComplianceBadge(roomResults.compliant as boolean)}
								</CardTitle>
							</CardHeader>
							<CardContent>
								<pre className="bg-muted p-4 rounded-lg overflow-auto text-sm">
									{JSON.stringify(roomResults, null, 2)}
								</pre>
							</CardContent>
						</Card>
					)}
				</TabsContent>

				<TabsContent value="floor-analysis" className="space-y-4">
					<Card>
						<CardHeader>
							<CardTitle>{t("fireai.floorAnalysis")}</CardTitle>
							<CardDescription>{t("fireai.selectFloor")}</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div className="flex gap-4 items-end">
								<div className="flex-1 space-y-2">
									<Label htmlFor="floor-id">Floor ID</Label>
									<Input
										id="floor-id"
										value={floorId}
										onChange={(e) => setFloorId(e.target.value)}
										placeholder="e.g., floor-1"
									/>
								</div>
								<Button
									onClick={handleFloorAnalysis}
									disabled={loading || !floorId}
								>
									{loading ? (
										<Loader2 className="h-4 w-4 animate-spin mr-2" />
									) : (
										<Building2 className="h-4 w-4 mr-2" />
									)}
									{t("fireai.analyzeFloor")}
								</Button>
							</div>
						</CardContent>
					</Card>

					{floorResults && (
						<Card>
							<CardHeader>
								<CardTitle className="flex items-center gap-2">
									{t("fireai.results")}
									{floorResults.compliant !== undefined &&
										renderComplianceBadge(floorResults.compliant as boolean)}
								</CardTitle>
							</CardHeader>
							<CardContent>
								<pre className="bg-muted p-4 rounded-lg overflow-auto text-sm">
									{JSON.stringify(floorResults, null, 2)}
								</pre>
							</CardContent>
						</Card>
					)}
				</TabsContent>

				<TabsContent value="acoustic-heatmap" className="space-y-4">
					<Card>
						<CardHeader>
							<CardTitle>
								NFPA 72 Acoustics dB Decay & Speech Intelligibility (STI) Matrix
							</CardTitle>
							<CardDescription>
								Visual 2D/3D acoustic attenuation matrix and speech transmission
								index visualization for notification devices.
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							<div className="p-4 border rounded-lg bg-card space-y-4">
								<div className="flex justify-between items-center">
									<h3 className="font-semibold text-sm">
										Acoustic Sound Field Matrix (10m x 10m Space)
									</h3>
									<div className="flex items-center gap-3 text-xs">
										<span className="flex items-center gap-1">
											<span className="w-3 h-3 bg-emerald-500 rounded-full"></span>{" "}
											STI Excellent (&gt; 0.60)
										</span>
										<span className="flex items-center gap-1">
											<span className="w-3 h-3 bg-amber-500 rounded-full"></span>{" "}
											STI Fair (0.45 - 0.60)
										</span>
										<span className="flex items-center gap-1">
											<span className="w-3 h-3 bg-rose-500 rounded-full"></span>{" "}
											STI Poor (&lt; 0.45)
										</span>
									</div>
								</div>
								<div className="aspect-video w-full bg-slate-950 rounded-lg flex items-center justify-center p-6 border relative overflow-hidden">
									<div className="grid grid-cols-10 gap-1.5 w-full max-w-lg aspect-square">
										{Array.from({ length: 100 }).map((_, idx) => {
											const row = Math.floor(idx / 10);
											const col = idx % 10;
											const dist = Math.sqrt(
												(col - 4.5) ** 2 + (row - 4.5) ** 2,
											);
											const spl = Math.max(50, roundTo1(92 - dist * 4.5));
											const sti = Math.max(0.2, roundTo1((spl - 55 + 15) / 30));
											const color =
												sti >= 0.6
													? "bg-emerald-600/80"
													: sti >= 0.45
														? "bg-amber-500/80"
														: "bg-rose-600/80";
											return (
												<div
													key={`heat-cell-${row}-${col}`}
													className={`${color} rounded flex flex-col items-center justify-center text-[10px] font-mono text-white p-1 hover:scale-110 transition-transform cursor-pointer shadow-sm`}
													title={`Grid (${col}, ${row}): ${spl} dBA | STI: ${sti}`}
												>
													<span>{spl}dB</span>
													<span className="text-[8px] opacity-80">{sti}</span>
												</div>
											);
										})}
									</div>
								</div>
							</div>
						</CardContent>
					</Card>
				</TabsContent>
			</Tabs>
		</div>
	);
}

function roundTo1(num: number): number {
	return Math.round(num * 10) / 10;
}
