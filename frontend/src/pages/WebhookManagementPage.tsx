/**
 * WebhookManagementPage.tsx — Webhook subscription management UI.
 *
 * V270: New page for v2 webhook endpoints.
 * - List subscriptions (GET /webhooks/subscriptions)
 * - Subscribe (POST /webhooks/subscribe)
 * - Unsubscribe (DELETE /webhooks/subscriptions/{id})
 * - Publish event (POST /webhooks/publish)
 */

import {
	Bell,
	BellOff,
	Globe,
	Loader2,
	Plus,
	RefreshCw,
	Send,
	Trash2,
} from "lucide-react";
import { useState } from "react";
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
import { useToast } from "@/hooks/use-toast";
import { v2Api, v2ExtendedApi } from "@/services/fullApi";

interface WebhookSubscription {
	id: string;
	url: string;
	event_types: string[];
	status: string;
}

const EVENT_TYPES = [
	"project.updated",
	"project.created",
	"device.added",
	"device.updated",
	"device.deleted",
	"connection.added",
	"report.generated",
	"conversion.completed",
	"alert.triggered",
	"workflow.completed",
];

export function WebhookManagementPage() {
	const { toast } = useToast();
	const [loading, setLoading] = useState(false);
	const [subscriptions, setSubscriptions] = useState<WebhookSubscription[]>([]);
	const [publishResult, setPublishResult] = useState<Record<
		string,
		unknown
	> | null>(null);

	// Subscribe form
	const [subUrl, setSubUrl] = useState("");
	const [subSecret, setSubSecret] = useState("");
	const [subEventTypes, setSubEventTypes] = useState<string[]>([
		"project.updated",
	]);

	// Publish form
	const [pubEventType, setPubEventType] = useState("project.updated");
	const [pubSource, setPubSource] = useState("webhook-ui");
	const [pubData, setPubData] = useState('{"message": "Test event"}');

	const handleListSubscriptions = async () => {
		setLoading(true);
		try {
			const res = (await v2Api.getWebhookSubscriptions()) as {
				subscriptions?: WebhookSubscription[];
				count?: number;
			};
			setSubscriptions(res.subscriptions || []);
			toast({
				title: "Subscriptions loaded",
				description: `${res.count || 0} subscription(s) found`,
			});
		} catch (err) {
			toast({
				title: "Failed to load subscriptions",
				description:
					err instanceof Error
						? err.message
						: "Webhook service may not be configured",
				variant: "destructive",
			});
		} finally {
			setLoading(false);
		}
	};

	const handleSubscribe = async () => {
		if (!subUrl) {
			toast({ title: "URL is required", variant: "destructive" });
			return;
		}
		if (!subSecret || subSecret.length < 32) {
			toast({
				title: "Secret must be at least 32 characters",
				description: "Per NIST SP 800-107 minimum entropy requirements",
				variant: "destructive",
			});
			return;
		}
		setLoading(true);
		try {
			await v2Api.subscribeWebhook({
				url: subUrl,
				secret: subSecret,
				event_types: subEventTypes,
			});
			toast({
				title: "Subscribed",
				description: `Webhook registered for ${subUrl}`,
			});
			setSubUrl("");
			setSubSecret("");
			handleListSubscriptions();
		} catch (err) {
			toast({
				title: "Subscribe failed",
				description: err instanceof Error ? err.message : "Failed",
				variant: "destructive",
			});
		} finally {
			setLoading(false);
		}
	};

	const handleUnsubscribe = async (subId: string) => {
		setLoading(true);
		try {
			await v2Api.deleteWebhookSubscription(subId);
			toast({
				title: "Unsubscribed",
				description: `Subscription ${subId} removed`,
			});
			handleListSubscriptions();
		} catch (err) {
			toast({
				title: "Unsubscribe failed",
				description: err instanceof Error ? err.message : "Failed",
				variant: "destructive",
			});
		} finally {
			setLoading(false);
		}
	};

	const handlePublish = async () => {
		let parsedData: Record<string, unknown>;
		try {
			parsedData = JSON.parse(pubData);
		} catch {
			toast({ title: "Invalid JSON in data field", variant: "destructive" });
			return;
		}
		setLoading(true);
		try {
			const res = await v2Api.publishWebhook({
				event_type: pubEventType,
				source: pubSource,
				data: parsedData,
			});
			setPublishResult(res as Record<string, unknown>);
			toast({
				title: "Event published",
				description: `Event type: ${pubEventType}`,
			});
		} catch (err) {
			toast({
				title: "Publish failed",
				description: err instanceof Error ? err.message : "Failed",
				variant: "destructive",
			});
		} finally {
			setLoading(false);
		}
	};

	const handlePublishExtended = async () => {
		let parsedPayload: Record<string, unknown>;
		try {
			parsedPayload = JSON.parse(pubData);
		} catch {
			toast({ title: "Invalid JSON in data field", variant: "destructive" });
			return;
		}
		setLoading(true);
		try {
			const res = await v2ExtendedApi.publishWebhook({
				event_type: pubEventType,
				payload: parsedPayload,
			});
			setPublishResult(res as Record<string, unknown>);
			toast({
				title: "Event published (v2 Extended)",
				description: `Event type: ${pubEventType}`,
			});
		} catch (err) {
			toast({
				title: "Publish failed (v2 Extended)",
				description: err instanceof Error ? err.message : "Failed",
				variant: "destructive",
			});
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="flex-1 overflow-auto">
			<div className="p-6 max-w-5xl mx-auto space-y-6">
				{/* Header */}
				<div>
					<h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
						<Bell aria-hidden="true" className="h-5 w-5 text-primary" />
						Webhook Management
					</h1>
					<p className="text-sm text-muted-foreground mt-1">
						Register, manage, and test webhook event delivery endpoints
					</p>
				</div>

				{/* Actions Bar */}
				<div className="flex items-center gap-3">
					<Button
						onClick={handleListSubscriptions}
						disabled={loading}
						variant="outline"
					>
						{loading ? (
							<Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
						) : (
							<RefreshCw aria-hidden="true" className="h-4 w-4" />
						)}
						Refresh Subscriptions
					</Button>
					{subscriptions.length > 0 && (
						<Badge variant="secondary" className="text-xs">
							{subscriptions.length} active
						</Badge>
					)}
				</div>

				{/* Subscribe Card */}
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Plus aria-hidden="true" className="h-4 w-4 text-primary" />
							Subscribe to Webhook Events
						</CardTitle>
						<CardDescription>
							Register a URL to receive HTTP POST notifications when events
							occur
						</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="grid grid-cols-1 md:grid-cols-2 gap-4">
							<div className="space-y-1.5">
								<Label className="text-xs text-muted-foreground">
									Webhook URL
								</Label>
								<Input
									autoComplete="off"
									value={subUrl}
									onChange={(e) => setSubUrl(e.target.value)}
									placeholder="https://example.com/webhook"
								/>
							</div>
							<div className="space-y-1.5">
								<Label className="text-xs text-muted-foreground">
									Secret (min 32 chars)
								</Label>
								<Input
									autoComplete="off"
									type="password"
									value={subSecret}
									onChange={(e) => setSubSecret(e.target.value)}
									placeholder="Your webhook secret..."
								/>
							</div>
						</div>
						<div className="mt-4 space-y-1.5">
							<Label className="text-xs text-muted-foreground">
								Event Types
							</Label>
							<div className="flex flex-wrap gap-2">
								{EVENT_TYPES.map((et) => {
									const selected = subEventTypes.includes(et);
									return (
										<Badge
											key={et}
											variant={selected ? "default" : "outline"}
											className="cursor-pointer transition-all text-xs"
											onClick={() => {
												setSubEventTypes((prev) =>
													selected
														? prev.filter((t) => t !== et)
														: [...prev, et],
												);
											}}
										>
											{et}
										</Badge>
									);
								})}
							</div>
							{subEventTypes.length === 0 && (
								<p className="text-xs text-amber-500 mt-1">
									Select at least one event type, or leave empty for all events
								</p>
							)}
						</div>
						<Button
							onClick={handleSubscribe}
							disabled={loading}
							className="mt-4 bg-primary hover:bg-primary/90 text-primary-foreground"
						>
							{loading ? (
								<Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
							) : (
								<Bell aria-hidden="true" className="h-4 w-4" />
							)}
							Subscribe
						</Button>
					</CardContent>
				</Card>

				{/* Subscriptions List */}
				{subscriptions.length > 0 && (
					<Card>
						<CardHeader>
							<CardTitle className="flex items-center gap-2">
								<Globe aria-hidden="true" className="h-4 w-4 text-primary" />
								Active Subscriptions ({subscriptions.length})
							</CardTitle>
							<CardDescription>
								Currently registered webhook endpoints
							</CardDescription>
						</CardHeader>
						<CardContent>
							<div className="space-y-3">
								{subscriptions.map((sub) => (
									<div
										key={sub.id}
										className="flex items-center justify-between p-3 rounded-lg border border-border bg-card/50 stagger-card"
									>
										<div className="flex-1 min-w-0">
											<div className="flex items-center gap-2">
												<span className="text-sm font-medium text-foreground truncate">
													{sub.url}
												</span>
												<Badge
													variant={
														sub.status === "active" ? "default" : "secondary"
													}
													className="text-xs shrink-0"
												>
													{sub.status}
												</Badge>
											</div>
											<div className="flex flex-wrap gap-1 mt-1">
												<span className="text-xs text-muted-foreground font-mono">
													{sub.id}
												</span>
												{sub.event_types.map((et) => (
													<Badge
														key={et}
														variant="outline"
														className="text-[10px]"
													>
														{et}
													</Badge>
												))}
											</div>
										</div>
										<Button
											variant="ghost"
											size="icon"
											onClick={() => handleUnsubscribe(sub.id)}
											disabled={loading}
											className="text-muted-foreground hover:text-danger shrink-0 ml-2"
											aria-label={`Unsubscribe ${sub.url}`}
										>
											<Trash2 aria-hidden="true" className="h-4 w-4" />
										</Button>
									</div>
								))}
							</div>
						</CardContent>
					</Card>
				)}

				{/* Publish Event Card */}
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Send aria-hidden="true" className="h-4 w-4 text-primary" />
							Publish Test Event
						</CardTitle>
						<CardDescription>
							Send a test event to verify delivery to all matching subscribers
						</CardDescription>
					</CardHeader>
					<CardContent>
						<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
							<div className="space-y-1.5">
								<Label className="text-xs text-muted-foreground">
									Event Type
								</Label>
								<Select value={pubEventType} onValueChange={setPubEventType}>
									<SelectTrigger>
										<SelectValue />
									</SelectTrigger>
									<SelectContent>
										{EVENT_TYPES.map((et) => (
											<SelectItem key={et} value={et}>
												{et}
											</SelectItem>
										))}
									</SelectContent>
								</Select>
							</div>
							<div className="space-y-1.5">
								<Label className="text-xs text-muted-foreground">Source</Label>
								<Input
									autoComplete="off"
									value={pubSource}
									onChange={(e) => setPubSource(e.target.value)}
									placeholder="webhook-ui"
								/>
							</div>
							<div className="space-y-1.5">
								<Label className="text-xs text-muted-foreground">
									Event Data (JSON)
								</Label>
								<Input
									autoComplete="off"
									value={pubData}
									onChange={(e) => setPubData(e.target.value)}
									placeholder='{"message": "Test"}'
								/>
							</div>
						</div>
						<Button
							onClick={handlePublish}
							disabled={loading}
							className="mt-4 bg-primary hover:bg-primary/90 text-primary-foreground"
						>
							{loading ? (
								<Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
							) : (
								<Send aria-hidden="true" className="h-4 w-4" />
							)}
							Publish Event
						</Button>
						<Button
							onClick={handlePublishExtended}
							disabled={loading}
							className="mt-4 bg-primary hover:bg-primary/90 text-primary-foreground"
						>
							{loading ? (
								<Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
							) : (
								<Send aria-hidden="true" className="h-4 w-4" />
							)}
							Publish Event (v2 Extended)
						</Button>

						{publishResult && (
							<div className="mt-4 p-3 rounded-lg bg-muted/50 border border-border">
								<pre className="text-xs font-mono whitespace-pre-wrap text-foreground">
									{JSON.stringify(publishResult, null, 2)}
								</pre>
							</div>
						)}
					</CardContent>
				</Card>

				{/* Empty State */}
				{subscriptions.length === 0 && !loading && (
					<Card>
						<CardContent className="py-12">
							<div className="flex flex-col items-center text-center">
								<BellOff
									aria-hidden="true"
									className="h-12 w-12 text-muted-foreground/40 mb-4"
								/>
								<p className="text-muted-foreground font-medium">
									No webhook subscriptions
								</p>
								<p className="text-sm text-muted-foreground/60 mt-1">
									Register a webhook URL above to receive event notifications
								</p>
							</div>
						</CardContent>
					</Card>
				)}
			</div>
		</div>
	);
}
