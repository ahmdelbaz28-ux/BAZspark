/**
 * CADSettingsPage.tsx — AutoCAD & Revit Connection Configuration
 *
 * Provides UI for:
 * - AutoCAD connection parameters (path, version, template)
 * - Revit connection parameters (path, version, template)
 * - Connection status monitoring
 * - File import/export preferences
 */

import {
	AlertCircle,
	CheckCircle2,
	FileText,
	FolderOpen,
	Loader2,
	Monitor,
	RefreshCw,
	Settings,
	Wrench,
	XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { RevitFamilyBrowser } from "@/components/engineering/RevitFamilyBrowser";
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
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cadConfigApi } from "@/services/fullApi";

// Module-level cache for cad_settings to avoid repeated synchronous localStorage I/O
let _cachedCadSettings: Record<string, unknown> | null = null;

interface CadSettingsShape {
	autocad?: {
		path?: string;
		version?: string;
		template?: string;
		units?: string;
	};
	revit?: {
		path?: string;
		version?: string;
		template?: string;
		units?: string;
	};
	cloud?: {
		speckleServer?: string;
		speckleStreamId?: string;
		apsClientId?: string;
		apsActivityId?: string;
	};
}

function getCadSettings(): Record<string, unknown> {
	if (_cachedCadSettings !== null) return _cachedCadSettings;
	try {
		const saved = localStorage.getItem("cad_settings");
		_cachedCadSettings = saved ? JSON.parse(saved) : {};
	} catch {
		_cachedCadSettings = {};
	}
	return _cachedCadSettings!;
}

function setCadSettings(settings: Record<string, unknown>): void {
	try {
		localStorage.setItem("cad_settings", JSON.stringify(settings));
	} catch {
		// Storage unavailable or quota exceeded
	}
	_cachedCadSettings = settings;
}

interface CADConnectionStatus {
	connected: boolean;
	version?: string;
	document?: string;
	lastChecked: string;
}

interface RevitConnectionStatus {
	connected: boolean;
	version?: string;
	document?: string;
	lastChecked: string;
}

export function CADSettingsPage() {
	useTranslation(); // V249: Keep hook for language context, remove unused 't'
	const [activeTab, setActiveTab] = useState("autocad");

	// V284 SECURITY: speckleToken / apsClientSecret are NO LONGER loaded from
	// localStorage — they were readable by any XSS payload. A backend credential
	// vault is in development (POST /api/v1/integrations/credentials, encrypted
	// at rest). Until then, the token fields stay empty on page load and are
	// never persisted to localStorage by saveCloudSettings().
	//
	// Load saved settings via a single lazy initializer (runs once on first
	// render — avoids react-hooks/set-state-in-effect: no setState in effect).
	const [savedSettings] = useState(() => {
		const raw = getCadSettings();
		return raw as unknown as CadSettingsShape;
	});

	// AutoCAD settings
	const [acadPath, setAcadPath] = useState(savedSettings.autocad?.path || "");
	const [acadVersion, setAcadVersion] = useState(
		savedSettings.autocad?.version || "2024",
	);
	const [acadTemplate, setAcadTemplate] = useState(
		savedSettings.autocad?.template || "",
	);
	const [acadUnits, setAcadUnits] = useState(
		savedSettings.autocad?.units || "Millimeters",
	);
	const [acadStatus, setAcadStatus] = useState<CADConnectionStatus | null>(
		null,
	);
	const [checkingAcad, setCheckingAcad] = useState(false);

	// Revit settings
	const [revitPath, setRevitPath] = useState(savedSettings.revit?.path || "");
	const [revitVersion, setRevitVersion] = useState(
		savedSettings.revit?.version || "2024",
	);
	const [revitTemplate, setRevitTemplate] = useState(
		savedSettings.revit?.template || "",
	);
	const [revitUnits, setRevitUnits] = useState(
		savedSettings.revit?.units || "Millimeters",
	);
	const [revitStatus, setRevitStatus] = useState<RevitConnectionStatus | null>(
		null,
	);
	const [checkingRevit, setCheckingRevit] = useState(false);

	// Speckle settings
	const [speckleServer, setSpeckleServer] = useState(
		savedSettings.cloud?.speckleServer || "https://speckle.xyz",
	);
	const [speckleToken, setSpeckleToken] = useState("");
	const [speckleStreamId, setSpeckleStreamId] = useState(
		savedSettings.cloud?.speckleStreamId || "",
	);

	// APS settings
	const [apsClientId, setApsClientId] = useState(
		savedSettings.cloud?.apsClientId || "",
	);
	const [apsClientSecret, setApsClientSecret] = useState("");
	const [apsActivityId, setApsActivityId] = useState(
		savedSettings.cloud?.apsActivityId || "BazSparkAutoCADBridge.DrawLayout",
	);

	// Synchronize with live backend configuration on mount
	useEffect(() => {
		let active = true;
		cadConfigApi
			.get()
			.then((res) => {
				if (!active || !res?.data) return;
				const d = res.data;
				if (d.autocad) {
					if (d.autocad.path !== undefined) setAcadPath(d.autocad.path);
					if (d.autocad.version !== undefined) setAcadVersion(d.autocad.version);
					if (d.autocad.template !== undefined) setAcadTemplate(d.autocad.template);
					if (d.autocad.units !== undefined) setAcadUnits(d.autocad.units);
				}
				if (d.revit) {
					if (d.revit.path !== undefined) setRevitPath(d.revit.path);
					if (d.revit.version !== undefined) setRevitVersion(d.revit.version);
					if (d.revit.template !== undefined) setRevitTemplate(d.revit.template);
					if (d.revit.units !== undefined) setRevitUnits(d.revit.units);
				}
				if (d.cloud) {
					if (d.cloud.speckle_server) setSpeckleServer(d.cloud.speckle_server);
					if (d.cloud.speckle_stream_id) setSpeckleStreamId(d.cloud.speckle_stream_id);
					if (d.cloud.aps_client_id) setApsClientId(d.cloud.aps_client_id);
					if (d.cloud.aps_activity_id) setApsActivityId(d.cloud.aps_activity_id);
				}
			})
			.catch(() => {
				// Retain localStorage fallback silently
			});
		return () => {
			active = false;
		};
	}, []);

	const checkAutoCADConnection = async () => {
		setCheckingAcad(true);
		try {
			const apiUrl = import.meta.env.VITE_API_URL || "/api/v1";
			const resp = await fetch(`${apiUrl}/autocad/status`, {
				credentials: "same-origin",
			});
			if (!resp.ok) {
				throw new Error(`HTTP ${resp.status}`);
			}
			const body = await resp.json();
			const data = body.data || body;
			setAcadStatus({
				connected: data.connected ?? false,
				version: data.version || "Unknown",
				document: data.document || data.active_document || "",
				lastChecked: new Date().toISOString(),
			});
			if (data.connected) {
				toast.success("AutoCAD connection verified");
			} else {
				toast.warning("AutoCAD is not connected");
			}
		} catch (error) {
			setAcadStatus({
				connected: false,
				lastChecked: new Date().toISOString(),
			});
			toast.error(
				`AutoCAD connection check failed: ${error instanceof Error ? error.message : "Unknown error"}`,
			);
		} finally {
			setCheckingAcad(false);
		}
	};

	const checkRevitConnection = async () => {
		setCheckingRevit(true);
		try {
			const apiUrl = import.meta.env.VITE_API_URL || "/api/v1";
			const resp = await fetch(`${apiUrl}/revit/status`, {
				credentials: "same-origin",
			});
			if (!resp.ok) {
				throw new Error(`HTTP ${resp.status}`);
			}
			const body = await resp.json();
			const data = body.data || body;
			setRevitStatus({
				connected: data.connected ?? false,
				version: data.version || "Unknown",
				document: data.document || data.active_document || "",
				lastChecked: new Date().toISOString(),
			});
			if (data.connected) {
				toast.success("Revit connection verified");
			} else {
				toast.warning("Revit is not connected");
			}
		} catch (error) {
			setRevitStatus({
				connected: false,
				lastChecked: new Date().toISOString(),
			});
			toast.error(
				`Revit connection check failed: ${error instanceof Error ? error.message : "Unknown error"}`,
			);
		} finally {
			setCheckingRevit(false);
		}
	};

	const saveAutoCADSettings = async () => {
		try {
			const settings = getCadSettings();
			settings.autocad = {
				path: acadPath,
				version: acadVersion,
				template: acadTemplate,
				units: acadUnits,
			};
			setCadSettings(settings);
			await cadConfigApi.update({
				autocad: {
					path: acadPath,
					version: acadVersion,
					template: acadTemplate,
					units: acadUnits,
				},
			});
			toast.success("AutoCAD settings saved to backend");
		} catch {
			toast.error("Failed to save AutoCAD settings");
		}
	};

	const saveRevitSettings = async () => {
		try {
			const settings = getCadSettings();
			settings.revit = {
				path: revitPath,
				version: revitVersion,
				template: revitTemplate,
				units: revitUnits,
			};
			setCadSettings(settings);
			await cadConfigApi.update({
				revit: {
					path: revitPath,
					version: revitVersion,
					template: revitTemplate,
					units: revitUnits,
				},
			});
			toast.success("Revit settings saved to backend");
		} catch {
			toast.error("Failed to save Revit settings");
		}
	};

	const saveCloudSettings = async () => {
		try {
			const settings = getCadSettings();
			settings.cloud = {
				speckleServer,
				speckleStreamId,
				apsClientId,
				apsActivityId,
			};
			setCadSettings(settings);
			await cadConfigApi.update({
				cloud: {
					speckle_server: speckleServer,
					speckle_stream_id: speckleStreamId,
					speckle_token: speckleToken || undefined,
					aps_client_id: apsClientId,
					aps_client_secret: apsClientSecret || undefined,
					aps_activity_id: apsActivityId,
				},
			});
			if (speckleToken || apsClientSecret) {
				toast.success("Cloud settings & credentials securely updated on backend");
			} else {
				toast.success("Cloud settings saved to backend");
			}
		} catch {
			toast.error("Failed to save cloud settings");
		}
	};

	return (
		<div className="flex-1 overflow-auto">
			<div className="p-6 max-w-5xl mx-auto space-y-6">
				{/* Header */}
				<div>
					<h1 className="text-2xl font-bold text-foreground">
						CAD/BIM Connection Settings
					</h1>
					<p className="text-sm text-muted-foreground mt-1">
						Configure AutoCAD and Revit connections for file operations
					</p>
				</div>

				{/* Main Tabs */}
				<Tabs value={activeTab} onValueChange={setActiveTab}>
					<TabsList className="bg-card border border-border stagger-card">
						<TabsTrigger
							value="autocad"
							className="data-[state=active]:bg-secondary"
						>
							<Monitor aria-hidden="true" className="h-4 w-4 mr-2" />
							AutoCAD
						</TabsTrigger>
						<TabsTrigger
							value="revit"
							className="data-[state=active]:bg-secondary"
						>
							<FileText aria-hidden="true" className="h-4 w-4 mr-2" />
							Revit
						</TabsTrigger>
						<TabsTrigger
							value="cloud"
							className="data-[state=active]:bg-secondary"
						>
							<Settings aria-hidden="true" className="h-4 w-4 mr-2" />
							Cloud Integration
						</TabsTrigger>
					</TabsList>

					{/* AutoCAD Tab */}
					<TabsContent value="autocad" className="space-y-6">
						{/* Connection Status */}
						<Card className="border-border bg-card stagger-card">
							<CardHeader>
								<CardTitle className="text-lg text-foreground flex items-center justify-between">
									<span className="flex items-center gap-2">
										<Monitor aria-hidden="true" className="h-5 w-5 text-info" />
										AutoCAD Connection Status
									</span>
									<Button
										variant="outline"
										size="sm"
										className="border-border text-foreground/90 hover:bg-card stagger-card"
										onClick={checkAutoCADConnection}
										disabled={checkingAcad}
									>
										{checkingAcad ? (
											<Loader2
												aria-hidden="true"
												className="h-4 w-4 animate-spin"
											/>
										) : (
											<RefreshCw aria-hidden="true" className="h-4 w-4" />
										)}
									</Button>
								</CardTitle>
							</CardHeader>
							<CardContent>
								{acadStatus ? (
									<div className="flex items-center gap-4">
										{acadStatus.connected ? (
											<CheckCircle2
												aria-hidden="true"
												className="h-8 w-8 text-success"
											/>
										) : (
											<XCircle
												aria-hidden="true"
												className="h-8 w-8 text-danger"
											/>
										)}
										<div className="flex-1">
											<p className="text-sm font-medium text-foreground">
												{acadStatus.connected ? "Connected" : "Disconnected"}
											</p>
											{acadStatus.connected && (
												<div className="text-xs text-muted-foreground mt-1 space-y-1">
													<p>Version: {acadStatus.version}</p>
													<p>Document: {acadStatus.document}</p>
													<p>
														Last checked:{" "}
														{new Date(acadStatus.lastChecked).toLocaleString()}
													</p>
												</div>
											)}
										</div>
										<Badge
											variant={acadStatus.connected ? "default" : "destructive"}
										>
											{acadStatus.connected ? "Active" : "Inactive"}
										</Badge>
									</div>
								) : (
									<div className="text-center py-6 text-muted-foreground">
										<AlertCircle
											aria-hidden="true"
											className="h-12 w-12 mx-auto mb-3 opacity-50"
										/>
										<p>Connection status unknown</p>
										<p className="text-xs mt-1">Click refresh to check</p>
									</div>
								)}
							</CardContent>
						</Card>

						{/* AutoCAD Configuration */}
						<Card className="border-border bg-card stagger-card">
							<CardHeader>
								<CardTitle className="text-lg text-foreground flex items-center gap-2">
									<Settings aria-hidden="true" className="h-5 w-5 text-info" />
									AutoCAD Configuration
								</CardTitle>
								<CardDescription className="text-muted-foreground">
									Configure AutoCAD installation and default settings
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2">
									<Label className="text-foreground/90">
										Installation Path
									</Label>
									<div className="flex gap-2">
										<Input
											value={acadPath}
											onChange={(e) => setAcadPath(e.target.value)}
											placeholder="C:\Program Files\Autodesk\AutoCAD 2024"
											className="bg-card border-border text-foreground flex-1 stagger-card"
										/>
										<Button
											variant="outline"
											className="border-border text-foreground/90 hover:bg-card stagger-card"
											onClick={() => {
												// V194 (TD-3) FIX: Use hidden file input to let the user select the
												// AutoCAD executable. Browsers cannot return full paths for
												// security reasons, so we use the file's name and prompt the
												// user to confirm the directory. This is the standard web pattern.
												const input = document.createElement("input");
												input.type = "file";
												input.accept = ".exe,application/x-msdownload";
												input.onchange = (e: Event) => {
													const file = (e.target as HTMLInputElement)
														.files?.[0];
													if (file) {
														setAcadPath(file.name);
														toast.info(
															`Selected: ${file.name}. Please verify the full installation path is correct above.`,
														);
													}
												};
												input.click();
											}}
										>
											<FolderOpen aria-hidden="true" className="h-4 w-4" />
										</Button>
									</div>
									<p className="text-xs text-muted-foreground">
										Path to AutoCAD executable (acad.exe)
									</p>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div className="space-y-2">
										<Label className="text-foreground/90">Version</Label>
										<Select value={acadVersion} onValueChange={setAcadVersion}>
											<SelectTrigger className="bg-card border-border text-foreground stagger-card">
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="2024">AutoCAD 2024</SelectItem>
												<SelectItem value="2023">AutoCAD 2023</SelectItem>
												<SelectItem value="2022">AutoCAD 2022</SelectItem>
												<SelectItem value="2021">AutoCAD 2021</SelectItem>
												<SelectItem value="2020">AutoCAD 2020</SelectItem>
											</SelectContent>
										</Select>
									</div>

									<div className="space-y-2">
										<Label className="text-foreground/90">Default Units</Label>
										<Select value={acadUnits} onValueChange={setAcadUnits}>
											<SelectTrigger className="bg-card border-border text-foreground stagger-card">
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="Millimeters">Millimeters</SelectItem>
												<SelectItem value="Meters">Meters</SelectItem>
												<SelectItem value="Inches">Inches</SelectItem>
												<SelectItem value="Feet">Feet</SelectItem>
											</SelectContent>
										</Select>
									</div>
								</div>

								<div className="space-y-2">
									<Label className="text-foreground/90">Default Template</Label>
									<div className="flex gap-2">
										<Input
											value={acadTemplate}
											onChange={(e) => setAcadTemplate(e.target.value)}
											placeholder="C:\Templates\architectural.dwt"
											className="bg-card border-border text-foreground flex-1 stagger-card"
										/>
										<Button
											variant="outline"
											className="border-border text-foreground/90 hover:bg-card stagger-card"
											onClick={() => {
												// V247 FIX: Use hidden file input (was "not implemented")
												const input = document.createElement("input");
												input.type = "file";
												input.accept = ".dwt";
												input.onchange = (e: Event) => {
													const file = (e.target as HTMLInputElement)
														.files?.[0];
													if (file) {
														setAcadTemplate(file.name);
														toast.info(`Selected: ${file.name}`);
													}
												};
												input.click();
											}}
										>
											<FolderOpen aria-hidden="true" className="h-4 w-4" />
										</Button>
									</div>
									<p className="text-xs text-muted-foreground">
										Default .dwt template file for new drawings
									</p>
								</div>

								<Button
									className="w-full bg-danger hover:bg-danger/90 text-danger-foreground border-none"
									onClick={saveAutoCADSettings}
								>
									Save AutoCAD Settings
								</Button>
							</CardContent>
						</Card>
					</TabsContent>

					{/* Revit Tab */}
					<TabsContent value="revit" className="space-y-6">
						{/* Connection Status */}
						<Card className="border-border bg-card stagger-card">
							<CardHeader>
								<CardTitle className="text-lg text-foreground flex items-center justify-between">
									<span className="flex items-center gap-2">
										<FileText
											aria-hidden="true"
											className="h-5 w-5 text-info"
										/>
										Revit Connection Status
									</span>
									<Button
										variant="outline"
										size="sm"
										className="border-border text-foreground/90 hover:bg-card stagger-card"
										onClick={checkRevitConnection}
										disabled={checkingRevit}
									>
										{checkingRevit ? (
											<Loader2
												aria-hidden="true"
												className="h-4 w-4 animate-spin"
											/>
										) : (
											<RefreshCw aria-hidden="true" className="h-4 w-4" />
										)}
									</Button>
								</CardTitle>
							</CardHeader>
							<CardContent>
								{revitStatus ? (
									<div className="flex items-center gap-4">
										{revitStatus.connected ? (
											<CheckCircle2
												aria-hidden="true"
												className="h-8 w-8 text-success"
											/>
										) : (
											<XCircle
												aria-hidden="true"
												className="h-8 w-8 text-danger"
											/>
										)}
										<div className="flex-1">
											<p className="text-sm font-medium text-foreground">
												{revitStatus.connected ? "Connected" : "Disconnected"}
											</p>
											{revitStatus.connected && (
												<div className="text-xs text-muted-foreground mt-1 space-y-1">
													<p>Version: {revitStatus.version}</p>
													<p>Document: {revitStatus.document}</p>
													<p>
														Last checked:{" "}
														{new Date(revitStatus.lastChecked).toLocaleString()}
													</p>
												</div>
											)}
										</div>
										<Badge
											variant={
												revitStatus.connected ? "default" : "destructive"
											}
										>
											{revitStatus.connected ? "Active" : "Inactive"}
										</Badge>
									</div>
								) : (
									<div className="text-center py-6 text-muted-foreground">
										<AlertCircle
											aria-hidden="true"
											className="h-12 w-12 mx-auto mb-3 opacity-50"
										/>
										<p>Connection status unknown</p>
										<p className="text-xs mt-1">Click refresh to check</p>
									</div>
								)}
							</CardContent>
						</Card>

						{/* Revit Configuration */}
						<Card className="border-border bg-card stagger-card">
							<CardHeader>
								<CardTitle className="text-lg text-foreground flex items-center gap-2">
									<Wrench aria-hidden="true" className="h-5 w-5 text-info" />
									Revit Configuration
								</CardTitle>
								<CardDescription className="text-muted-foreground">
									Configure Revit installation and default settings
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2">
									<Label className="text-foreground/90">
										Installation Path
									</Label>
									<div className="flex gap-2">
										<Input
											value={revitPath}
											onChange={(e) => setRevitPath(e.target.value)}
											placeholder="C:\Program Files\Autodesk\Revit 2024"
											className="bg-card border-border text-foreground flex-1 stagger-card"
										/>
										<Button
											variant="outline"
											className="border-border text-foreground/90 hover:bg-card stagger-card"
											onClick={() => {
												// V247 FIX: Use hidden file input (was "not implemented")
												const input = document.createElement("input");
												input.type = "file";
												input.accept = ".exe,application/x-msdownload";
												input.onchange = (e: Event) => {
													const file = (e.target as HTMLInputElement)
														.files?.[0];
													if (file) {
														setRevitPath(file.name);
														toast.info(
															`Selected: ${file.name}. Please verify the full installation path.`,
														);
													}
												};
												input.click();
											}}
										>
											<FolderOpen aria-hidden="true" className="h-4 w-4" />
										</Button>
									</div>
									<p className="text-xs text-muted-foreground">
										Path to Revit executable (Revit.exe)
									</p>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<div className="space-y-2">
										<Label className="text-foreground/90">Version</Label>
										<Select
											value={revitVersion}
											onValueChange={setRevitVersion}
										>
											<SelectTrigger className="bg-card border-border text-foreground stagger-card">
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="2024">Revit 2024</SelectItem>
												<SelectItem value="2023">Revit 2023</SelectItem>
												<SelectItem value="2022">Revit 2022</SelectItem>
												<SelectItem value="2021">Revit 2021</SelectItem>
												<SelectItem value="2020">Revit 2020</SelectItem>
											</SelectContent>
										</Select>
									</div>

									<div className="space-y-2">
										<Label className="text-foreground/90">Default Units</Label>
										<Select value={revitUnits} onValueChange={setRevitUnits}>
											<SelectTrigger className="bg-card border-border text-foreground stagger-card">
												<SelectValue />
											</SelectTrigger>
											<SelectContent>
												<SelectItem value="Millimeters">Millimeters</SelectItem>
												<SelectItem value="Meters">Meters</SelectItem>
												<SelectItem value="Inches">Inches</SelectItem>
												<SelectItem value="Feet">Feet</SelectItem>
											</SelectContent>
										</Select>
									</div>
								</div>

								<div className="space-y-2">
									<Label className="text-foreground/90">Default Template</Label>
									<div className="flex gap-2">
										<Input
											value={revitTemplate}
											onChange={(e) => setRevitTemplate(e.target.value)}
											placeholder="C:\Templates\Architectural-Template.rte"
											className="bg-card border-border text-foreground flex-1 stagger-card"
										/>
										<Button
											variant="outline"
											className="border-border text-foreground/90 hover:bg-card stagger-card"
											onClick={() => {
												// V247 FIX: Use hidden file input (was "not implemented")
												const input = document.createElement("input");
												input.type = "file";
												input.accept = ".rte";
												input.onchange = (e: Event) => {
													const file = (e.target as HTMLInputElement)
														.files?.[0];
													if (file) {
														setRevitTemplate(file.name);
														toast.info(`Selected: ${file.name}`);
													}
												};
												input.click();
											}}
										>
											<FolderOpen aria-hidden="true" className="h-4 w-4" />
										</Button>
									</div>
									<p className="text-xs text-muted-foreground">
										Default .rte template file for new projects
									</p>
								</div>

								<div className="grid grid-cols-2 gap-4">
									<Button
										className="w-full bg-danger hover:bg-danger/90 text-danger-foreground border-none"
										onClick={saveRevitSettings}
									>
										Save Revit Settings
									</Button>
									<RevitFamilyBrowser />
								</div>
							</CardContent>
						</Card>
					</TabsContent>

					{/* Cloud Integration Tab */}
					<TabsContent value="cloud" className="space-y-6">
						{/* Speckle Configuration */}
						<Card className="border-border bg-card stagger-card">
							<CardHeader>
								<CardTitle className="text-lg text-foreground flex items-center gap-2">
									<Settings aria-hidden="true" className="h-5 w-5 text-info" />
									Speckle Live Synchronization
								</CardTitle>
								<CardDescription className="text-muted-foreground">
									Configure Speckle live synchronization server and target
									stream
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2">
									<Label className="text-foreground/90">
										Speckle Server URL
									</Label>
									<Input
										value={speckleServer}
										onChange={(e) => setSpeckleServer(e.target.value)}
										placeholder="https://speckle.xyz"
										className="bg-card border-border text-foreground stagger-card"
									/>
								</div>
								<div className="space-y-2">
									<Label className="text-foreground/90">
										Personal Access Token
									</Label>
									<Input
										type="password"
										value={speckleToken}
										onChange={(e) => setSpeckleToken(e.target.value)}
										placeholder="Paste your Speckle access token here (session-only — NOT saved)"
										className="bg-card border-border text-foreground stagger-card"
									/>
									<p className="text-xs text-amber-500">
										V284 SECURITY: Token is session-only and never written to
										localStorage. Re-enter each session. Backend credential
										vault (encrypted at rest) is in development (P0-8
										follow-up).
									</p>
								</div>
								<div className="space-y-2">
									<Label className="text-foreground/90">
										Default Stream/Project ID
									</Label>
									<Input
										value={speckleStreamId}
										onChange={(e) => setSpeckleStreamId(e.target.value)}
										placeholder="e.g. 7a92cfb38f"
										className="bg-card border-border text-foreground stagger-card"
									/>
								</div>
							</CardContent>
						</Card>

						{/* Autodesk Platform Services Configuration */}
						<Card className="border-border bg-card stagger-card">
							<CardHeader>
								<CardTitle className="text-lg text-foreground flex items-center gap-2">
									<Wrench aria-hidden="true" className="h-5 w-5 text-info" />
									Autodesk Platform Services (APS)
								</CardTitle>
								<CardDescription className="text-muted-foreground">
									Configure headless cloud processing credentials and activities
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2">
									<Label className="text-foreground/90">APS Client ID</Label>
									<Input
										value={apsClientId}
										onChange={(e) => setApsClientId(e.target.value)}
										placeholder="Your APS Client ID"
										className="bg-card border-border text-foreground stagger-card"
									/>
								</div>
								<div className="space-y-2">
									<Label className="text-foreground/90">
										APS Client Secret
									</Label>
									<Input
										type="password"
										value={apsClientSecret}
										onChange={(e) => setApsClientSecret(e.target.value)}
										placeholder="Your APS Client Secret (session-only — NOT saved)"
										className="bg-card border-border text-foreground stagger-card"
									/>
									<p className="text-xs text-amber-500">
										V284 SECURITY: Secret is session-only and never written to
										localStorage. Re-enter each session. Backend credential
										vault (encrypted at rest) is in development (P0-8
										follow-up).
									</p>
								</div>
								<div className="space-y-2">
									<Label className="text-foreground/90">APS Activity ID</Label>
									<Input
										value={apsActivityId}
										onChange={(e) => setApsActivityId(e.target.value)}
										placeholder="e.g. BazSparkAutoCADBridge.DrawLayout"
										className="bg-card border-border text-foreground stagger-card"
									/>
								</div>

								<Button
									className="w-full bg-danger hover:bg-danger/90 text-danger-foreground border-none"
									onClick={saveCloudSettings}
								>
									Save Cloud Settings
								</Button>
							</CardContent>
						</Card>
					</TabsContent>
				</Tabs>
			</div>
		</div>
	);
}
