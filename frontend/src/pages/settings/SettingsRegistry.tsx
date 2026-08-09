/**
 * Page-level settings registry — read-only view of environment variables (fetched from /settings/config).
 * Distinct from ui/SettingsRegistry (three-tier security settings with runtime toggles and bootstrap config).
 * Neither component imports the other; they serve different sections of the settings UI.
 */
import React, { useEffect, useState } from "react";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type SystemConfig = Record<string, string>;

export function SettingsRegistry() {
	const [config, setConfig] = useState<SystemConfig>({});
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		fetch("http://localhost:7860/settings/config", {
			headers: {
				"X-API-Key": "dev-key-123",
			},
		})
			.then((res) => res.json())
			.then((data) => {
				setConfig(data);
				setLoading(false);
			})
			.catch((err) => {
				console.error("Failed to load config", err);
				setLoading(false);
			});
	}, []);

	if (loading)
		return <div className="p-8 text-center">Loading registry...</div>;

	return (
		<div className="space-y-6 max-w-4xl mx-auto py-8">
			<div>
				<h1 className="text-3xl font-display font-bold tracking-tight text-white mb-2">
					Settings Registry
				</h1>
				<p className="text-slate-400">
					Unified configuration for the BAZspark environment variables.
				</p>
			</div>

			<Card className="border-slate-800 bg-slate-900/50 backdrop-blur-xl">
				<CardHeader>
					<CardTitle className="text-xl">Environment Variables</CardTitle>
					<CardDescription>
						Read-only view of the current runtime configuration.
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4">
					{Object.entries(config).map(([key, value]) => (
						<div key={key} className="space-y-2">
							<Label htmlFor={key} className="text-slate-300 font-mono text-xs">
								{key}
							</Label>
							<Input
								id={key}
								readOnly
								value={value}
								className="font-mono bg-slate-950/50 border-slate-800 text-slate-400 focus-visible:ring-cyan-500"
							/>
						</div>
					))}
				</CardContent>
			</Card>
		</div>
	);
}
