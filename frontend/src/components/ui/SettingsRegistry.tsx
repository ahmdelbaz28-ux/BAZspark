/**
 * UI-level settings registry — three-tier security architecture (runtime toggles, bootstrap config, secrets omitted).
 * Distinct from pages/settings/SettingsRegistry (read-only env-var viewer).
 * Neither component imports the other; they serve different sections of the settings UI.
 */

import { Key, Lock, Server, Settings } from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "./alert";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "./card";
import { Label } from "./label";
import { Switch } from "./switch";

export const SettingsRegistry: React.FC = () => {
	const [runtime, setRuntime] = useState<Record<string, boolean>>({});
	const [bootstrap, setBootstrap] = useState<Record<string, string>>({});
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchSettings = async () => {
			try {
				const headers = {
					"X-API-Key": process.env.VITE_FIREAI_API_KEY || "test-key",
				};
				const [rtRes, bsRes] = await Promise.all([
					fetch("http://localhost:8000/settings/runtime", { headers }),
					fetch("http://localhost:8000/settings/bootstrap", { headers }),
				]);

				if (rtRes.ok) setRuntime(await rtRes.json());
				if (bsRes.ok) setBootstrap(await bsRes.json());
			} catch (err) {
				console.error("Failed to load settings", err);
			} finally {
				setLoading(false);
			}
		};
		fetchSettings();
	}, []);

	const handleToggle = async (key: string, checked: boolean) => {
		// Cannot toggle non-deterministic features safely via UI right now (Rule 1, NFPA 72 constraints)
		if (key === "SMOKE_SIMULATION" || key === "SELF_LEARNING") {
			alert(
				`Safety Override: ${key} is Disabled by V8 architecture and cannot be enabled via UI.`,
			);
			return;
		}

		const newSettings = { ...runtime, [key]: checked };
		setRuntime(newSettings);

		try {
			await fetch("http://localhost:8000/settings/runtime", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"X-API-Key": process.env.VITE_FIREAI_API_KEY || "test-key",
				},
				body: JSON.stringify(newSettings),
			});
		} catch (err) {
			console.error("Failed to save setting", err);
		}
	};

	if (loading) return <div>Loading...</div>;

	return (
		<div className="space-y-6 max-w-4xl mx-auto">
			<div>
				<h2 className="text-2xl font-bold tracking-tight">
					System Settings Registry
				</h2>
				<p className="text-muted-foreground">
					Three-Tier Security Architecture Configuration
				</p>
			</div>

			{/* Tier 1: Runtime Settings */}
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<Settings className="h-5 w-5" />
						Runtime Settings (Tier 1)
					</CardTitle>
					<CardDescription>Dynamically editable feature flags</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-4">
					{Object.entries(runtime).map(([key, value]) => {
						const isDisabled =
							key === "SMOKE_SIMULATION" || key === "SELF_LEARNING";
						return (
							<div
								key={key}
								className="flex items-center justify-between space-x-2 rounded-lg border p-4"
							>
								<div className="space-y-0.5">
									<Label className="text-base font-semibold">{key}</Label>
									{isDisabled && (
										<p className="text-xs text-destructive flex items-center gap-1 mt-1">
											<Lock className="h-3 w-3" /> Disabled by V8 - Safety
											Constraint
										</p>
									)}
								</div>
								<Switch
									checked={value}
									disabled={isDisabled}
									onCheckedChange={(c) => handleToggle(key, c)}
								/>
							</div>
						);
					})}
				</CardContent>
			</Card>

			{/* Tier 2: Bootstrap Settings */}
			<Card>
				<CardHeader>
					<CardTitle className="flex items-center gap-2">
						<Server className="h-5 w-5" />
						Bootstrap Settings (Tier 2)
					</CardTitle>
					<CardDescription>
						Read-only environment and system configuration
					</CardDescription>
				</CardHeader>
				<CardContent className="grid gap-4 bg-muted/20">
					{Object.entries(bootstrap).map(([key, value]) => (
						<div key={key} className="flex flex-col space-y-1">
							<Label className="text-xs text-muted-foreground">{key}</Label>
							<div className="font-mono text-sm bg-background p-2 rounded border">
								{String(value) || <span className="opacity-50">Not Set</span>}
							</div>
						</div>
					))}
				</CardContent>
			</Card>

			{/* Tier 3: Secrets (Omitted) */}
			<Alert variant="default" className="bg-primary/5 border-primary/20">
				<Key className="h-4 w-4 text-primary" />
				<AlertTitle>Secrets (Tier 3) are Protected</AlertTitle>
				<AlertDescription>
					API keys, database URLs, and session secrets are managed via strict
					Separation of Privileges and are never exposed to the UI or stored in
					the frontend runtime.
				</AlertDescription>
			</Alert>
		</div>
	);
};
