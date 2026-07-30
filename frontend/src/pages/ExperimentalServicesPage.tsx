/**
 * ExperimentalServicesPage.tsx — V270 FIX (audit "5 orphan services").
 *
 * Admin-only page that lists the three previously-orphan services (OCR,
 * Scan-to-BIM, Speckle) and provides upload/action buttons for each.
 *
 * Backend endpoints (all require admin role):
 *   GET  /api/v1/experimental/features             — list services + status
 *   POST /api/v1/experimental/ocr/process           — OCR a PDF/image
 *   POST /api/v1/experimental/scan-to-bim/process   — OCR → BIM room extraction
 *   POST /api/v1/experimental/speckle/push          — push elements to Speckle
 *   POST /api/v1/experimental/speckle/receive       — receive elements from Speckle
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
	Activity,
	ArrowRightLeft,
	Download,
	Loader2,
	RefreshCw,
	Scan,
	Sparkles,
	Upload,
	XCircle,
	CheckCircle2,
} from "lucide-react";
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
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import { apiCall } from "@/services/fullApi";

interface FeatureStatus {
	name: string;
	description: string;
	endpoint: string;
	available: boolean;
	unavailable_reason?: string | null;
}

interface ProcessResult {
	service: string;
	filename?: string;
	result?: unknown;
	[key: string]: unknown;
}

export function ExperimentalServicesPage() {
	const { toast } = useToast();
	const [features, setFeatures] = useState<FeatureStatus[]>([]);
	const [loading, setLoading] = useState(true);
	const [busy, setBusy] = useState<string | null>(null);
	const [ocrResult, setOcrResult] = useState<ProcessResult | null>(null);
	const [bimResult, setBimResult] = useState<ProcessResult | null>(null);
	const [speckleResult, setSpeckleResult] = useState<ProcessResult | null>(null);

	// Speckle form state
	const [streamId, setStreamId] = useState("");
	const [serverUrl, setServerUrl] = useState("https://speckle.xyz");
	const [speckleToken, setSpeckleToken] = useState("");
	const [speckleElements, setSpeckleElements] = useState("");

	const ocrFileRef = useRef<HTMLInputElement>(null);
	const bimFileRef = useRef<HTMLInputElement>(null);

	const fetchFeatures = useCallback(async () => {
		setLoading(true);
		try {
			// V271 FIX: use apiCall for CSRF header injection + auth + retry.
			// Previous direct fetch() bypassed CSRF middleware, causing 403 on
			// all state-changing operations against /api/v1/experimental/*.
			const json = await apiCall<{ data?: { features?: FeatureStatus[] } }>(
				"/experimental/features",
				{ method: "GET" },
			);
			setFeatures(json?.data?.features ?? []);
		} catch (err) {
			toast({
				title: "Failed to load experimental features",
				description: err instanceof Error ? err.message : "Network error",
				variant: "destructive",
			});
		} finally {
			setLoading(false);
		}
	}, [toast]);

	useEffect(() => {
		fetchFeatures();
	}, [fetchFeatures]);

	const handleOcrUpload = async (file: File) => {
		setBusy("ocr");
		setOcrResult(null);
		try {
			// V271 FIX: UploadFile endpoints need multipart/form-data.
			// apiCall sets Content-Type: application/json by default, which
			// would break multipart uploads. To let the browser set the
			// correct boundary automatically, we omit Content-Type entirely
			// — the browser sees FormData body and adds multipart/form-data
			// with a generated boundary. CSRF header is still injected by
			// apiCall via fetchWithRetry.
			const fd = new FormData();
			fd.append("file", file);
			fd.append("lang", "eng+ara");
			const json = await apiCall<ProcessResult & { detail?: string }>(
				"/experimental/ocr/process",
				{
					method: "POST",
					body: fd,
					// Deliberately no Content-Type header — browser sets it.
					headers: { "Content-Type": "" },
				},
			);
			setOcrResult(json as ProcessResult);
			toast({ title: "OCR complete", description: file.name });
		} catch (err) {
			toast({
				title: "OCR failed",
				description: err instanceof Error ? err.message : "Unknown error",
				variant: "destructive",
			});
		} finally {
			setBusy(null);
		}
	};

	const handleBimUpload = async (file: File) => {
		setBusy("bim");
		setBimResult(null);
		try {
			const fd = new FormData();
			fd.append("file", file);
			fd.append("lang", "eng+ara");
			const json = await apiCall<ProcessResult & { detail?: string }>(
				"/experimental/scan-to-bim/process",
				{
					method: "POST",
					body: fd,
					headers: { "Content-Type": "" },
				},
			);
			setBimResult(json as ProcessResult);
			toast({ title: "Scan-to-BIM complete", description: file.name });
		} catch (err) {
			toast({
				title: "Scan-to-BIM failed",
				description: err instanceof Error ? err.message : "Unknown error",
				variant: "destructive",
			});
		} finally {
			setBusy(null);
		}
	};

	const handleSpeckle = async (op: "push" | "receive") => {
		if (!streamId || !speckleToken) {
			toast({
				title: "Missing fields",
				description: "Stream ID and token are required",
				variant: "destructive",
			});
			return;
		}
		setBusy(`speckle-${op}`);
		setSpeckleResult(null);
		try {
			let elements: unknown[] | undefined;
			if (op === "push") {
				if (!speckleElements.trim()) {
					toast({
						title: "Missing elements",
						description: "Push requires JSON elements",
						variant: "destructive",
					});
					setBusy(null);
					return;
				}
				elements = JSON.parse(speckleElements);
			}
			const json = await apiCall<ProcessResult & { detail?: string }>(
				`/experimental/speckle/${op}`,
				{
					method: "POST",
					body: JSON.stringify({
						stream_id: streamId,
						server_url: serverUrl,
						token: speckleToken,
						elements,
					}),
				},
			);
			setSpeckleResult(json as ProcessResult);
			toast({ title: `Speckle ${op} complete` });
		} catch (err) {
			toast({
				title: `Speckle ${op} failed`,
				description: err instanceof Error ? err.message : "Unknown error",
				variant: "destructive",
			});
		} finally {
			setBusy(null);
		}
	};

	return (
		<div className="space-y-6 p-6">
			<div className="flex items-center justify-between">
				<div>
					<h1 className="text-2xl font-bold flex items-center gap-2">
						<Sparkles className="h-6 w-6 text-amber-500" />
						Experimental Services
					</h1>
					<p className="text-sm text-muted-foreground mt-1">
						Previously-orphan backend services now exposed for admin use. Marked experimental —
						not production-hardened.
					</p>
				</div>
				<Button variant="outline" size="sm" onClick={fetchFeatures} disabled={loading}>
					<RefreshCw className={`h-4 w-4 mr-1 ${loading ? "animate-spin" : ""}`} />
					Refresh
				</Button>
			</div>

			{/* Status cards */}
			<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
				{features.map(f => (
					<Card key={f.name}>
						<CardHeader className="pb-3">
							<div className="flex items-center justify-between">
								<CardTitle className="text-base">{f.name}</CardTitle>
								{f.available ? (
									<Badge variant="default" className="bg-emerald-600">
										<CheckCircle2 className="h-3 w-3 mr-1" />
										Available
									</Badge>
								) : (
									<Badge variant="destructive">
										<XCircle className="h-3 w-3 mr-1" />
										Unavailable
									</Badge>
								)}
							</div>
							<CardDescription className="text-xs">{f.description}</CardDescription>
						</CardHeader>
						<CardContent className="pt-0">
							<code className="text-[10px] text-muted-foreground block">{f.endpoint}</code>
							{f.unavailable_reason && (
								<p className="text-xs text-destructive mt-2">{f.unavailable_reason}</p>
							)}
						</CardContent>
					</Card>
				))}
				{features.length === 0 && !loading && (
					<Card className="col-span-3">
						<CardContent className="py-8 text-center text-sm text-muted-foreground">
							No experimental services registered.
						</CardContent>
					</Card>
				)}
			</div>

			{/* OCR */}
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2 text-lg">
						<Scan className="h-5 w-5" />
						OCR Processing
					</CardTitle>
					<CardDescription>
						Upload a scanned PDF or image. Returns extracted text and room names (eng+ara).
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3">
					<input
						ref={ocrFileRef}
						type="file"
						accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
						className="hidden"
						onChange={e => {
							const f = e.target.files?.[0];
							if (f) handleOcrUpload(f);
							e.target.value = "";
						}}
					/>
					<Button
						variant="default"
						onClick={() => ocrFileRef.current?.click()}
						disabled={busy === "ocr"}
					>
						{busy === "ocr" ? (
							<Loader2 className="h-4 w-4 mr-1 animate-spin" />
						) : (
							<Upload className="h-4 w-4 mr-1" />
						)}
						Upload PDF / Image
					</Button>
					{ocrResult && (
						<details className="text-xs">
							<summary className="cursor-pointer text-muted-foreground">
								OCR result for {ocrResult.filename}
							</summary>
							<pre className="mt-2 p-3 bg-muted rounded overflow-x-auto">
								{JSON.stringify(ocrResult, null, 2)}
							</pre>
						</details>
					)}
				</CardContent>
			</Card>

			{/* Scan-to-BIM */}
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2 text-lg">
						<Activity className="h-5 w-5" />
						Scan-to-BIM
					</CardTitle>
					<CardDescription>
						Upload a floor plan. Returns BIM rooms with areas, types, and confidence scores.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3">
					<input
						ref={bimFileRef}
						type="file"
						accept=".pdf,.png,.jpg,.jpeg,.tiff,.tif"
						className="hidden"
						onChange={e => {
							const f = e.target.files?.[0];
							if (f) handleBimUpload(f);
							e.target.value = "";
						}}
					/>
					<Button
						variant="default"
						onClick={() => bimFileRef.current?.click()}
						disabled={busy === "bim"}
					>
						{busy === "bim" ? (
							<Loader2 className="h-4 w-4 mr-1 animate-spin" />
						) : (
							<Upload className="h-4 w-4 mr-1" />
						)}
						Upload Floor Plan
					</Button>
					{bimResult && (
						<details className="text-xs">
							<summary className="cursor-pointer text-muted-foreground">
								Scan-to-BIM result for {bimResult.filename}
							</summary>
							<pre className="mt-2 p-3 bg-muted rounded overflow-x-auto">
								{JSON.stringify(bimResult, null, 2)}
							</pre>
						</details>
					)}
				</CardContent>
			</Card>

			{/* Speckle */}
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2 text-lg">
						<ArrowRightLeft className="h-5 w-5" />
						Speckle Bridge
					</CardTitle>
					<CardDescription>
						Push BIM elements to a Speckle stream or receive elements from one.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3">
					<div className="grid grid-cols-1 md:grid-cols-3 gap-3">
						<div>
							<Label htmlFor="speckle-stream" className="text-xs">Stream ID</Label>
							<Input
								id="speckle-stream"
								value={streamId}
								onChange={e => setStreamId(e.target.value)}
								placeholder="abc123..."
							/>
						</div>
						<div>
							<Label htmlFor="speckle-server" className="text-xs">Server URL</Label>
							<Input
								id="speckle-server"
								value={serverUrl}
								onChange={e => setServerUrl(e.target.value)}
							/>
						</div>
						<div>
							<Label htmlFor="speckle-token" className="text-xs">API Token</Label>
							<Input
								id="speckle-token"
								type="password"
								value={speckleToken}
								onChange={e => setSpeckleToken(e.target.value)}
							/>
						</div>
					</div>
					<div>
						<Label htmlFor="speckle-elements" className="text-xs">
							Elements JSON (push only)
						</Label>
						<Textarea
							id="speckle-elements"
							value={speckleElements}
							onChange={e => setSpeckleElements(e.target.value)}
							placeholder='[{"type":"IfcWall","name":"W1"}]'
							className="font-mono text-xs"
							rows={3}
						/>
					</div>
					<div className="flex gap-2">
						<Button
							variant="default"
							onClick={() => handleSpeckle("push")}
							disabled={busy === "speckle-push"}
						>
							{busy === "speckle-push" ? (
								<Loader2 className="h-4 w-4 mr-1 animate-spin" />
							) : (
								<Upload className="h-4 w-4 mr-1" />
							)}
							Push
						</Button>
						<Button
							variant="outline"
							onClick={() => handleSpeckle("receive")}
							disabled={busy === "speckle-receive"}
						>
							{busy === "speckle-receive" ? (
								<Loader2 className="h-4 w-4 mr-1 animate-spin" />
							) : (
								<Download className="h-4 w-4 mr-1" />
							)}
							Receive
						</Button>
					</div>
					{speckleResult && (
						<details className="text-xs">
							<summary className="cursor-pointer text-muted-foreground">
								Speckle result ({speckleResult.service})
							</summary>
							<pre className="mt-2 p-3 bg-muted rounded overflow-x-auto">
								{JSON.stringify(speckleResult, null, 2)}
							</pre>
						</details>
					)}
				</CardContent>
			</Card>
		</div>
	);
}
