import { BellRing, ShieldAlert, Wrench } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { Badge } from "../ui/badge";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "../ui/card";

interface AlarmEvent {
	id: string;
	timestamp: string;
	type: "ALARM" | "SUPERVISORY" | "TROUBLE";
	device: string;
	zone: string;
	description: string;
}

const MOCK_EVENTS: AlarmEvent[] = [
	{
		id: "EV-104",
		timestamp: "2026-08-04T11:45:00Z",
		type: "ALARM",
		device: "SD-03-12",
		zone: "Z03",
		description: "Smoke detected in Cafeteria Kitchen",
	},
	{
		id: "EV-103",
		timestamp: "2026-08-04T10:12:30Z",
		type: "TROUBLE",
		device: "PULL-01-04",
		zone: "Z01",
		description: "Communication lost with Pull Station",
	},
	{
		id: "EV-102",
		timestamp: "2026-08-03T15:20:00Z",
		type: "SUPERVISORY",
		device: "VALVE-04",
		zone: "Z04",
		description: "Sprinkler control valve tampered",
	},
	{
		id: "EV-101",
		timestamp: "2026-08-02T08:00:00Z",
		type: "TROUBLE",
		device: "PANEL-MAIN",
		zone: "SYS",
		description: "Primary power failure, running on battery",
	},
];

export const AlarmLogTimeline: React.FC = () => {
	const [events] = useState<AlarmEvent[]>(MOCK_EVENTS);

	const getTypeIcon = (type: AlarmEvent["type"]) => {
		switch (type) {
			case "ALARM":
				return <BellRing className="h-5 w-5 text-destructive" />;
			case "SUPERVISORY":
				return <ShieldAlert className="h-5 w-5 text-amber-500" />;
			case "TROUBLE":
				return <Wrench className="h-5 w-5 text-blue-500" />;
		}
	};

	const getTypeBadge = (type: AlarmEvent["type"]) => {
		switch (type) {
			case "ALARM":
				return <Badge variant="destructive">ALARM</Badge>;
			case "SUPERVISORY":
				return (
					<Badge variant="secondary" className="bg-amber-500/10 text-amber-600">
						SUPERVISORY
					</Badge>
				);
			case "TROUBLE":
				return (
					<Badge variant="outline" className="text-blue-500 border-blue-500">
						TROUBLE
					</Badge>
				);
		}
	};

	return (
		<Card className="col-span-4 h-[500px] flex flex-col">
			<CardHeader>
				<CardTitle className="flex items-center gap-2">
					<BellRing className="h-5 w-5" />
					Event History
				</CardTitle>
				<CardDescription>Reverse chronological audit trail</CardDescription>
			</CardHeader>
			<CardContent className="flex-1 overflow-y-auto pr-2">
				<div className="relative border-l-2 border-muted ml-3 space-y-6 pb-4">
					{events.map((event) => (
						<div key={event.id} className="relative pl-6">
							<div className="absolute -left-[11px] top-1 bg-background rounded-full p-0.5 border-2 border-muted">
								<div className="w-4 h-4 rounded-full flex items-center justify-center">
									{getTypeIcon(event.type)}
								</div>
							</div>
							<div className="flex flex-col gap-1">
								<div className="flex items-center justify-between">
									{getTypeBadge(event.type)}
									<span className="text-xs text-muted-foreground font-mono">
										{new Date(event.timestamp).toLocaleString()}
									</span>
								</div>
								<p className="text-sm font-semibold mt-1">
									{event.description}
								</p>
								<p className="text-xs text-muted-foreground">
									Device:{" "}
									<span className="font-mono text-primary">{event.device}</span>{" "}
									| Zone:{" "}
									<span className="font-mono text-primary">{event.zone}</span>
								</p>
							</div>
						</div>
					))}
				</div>
			</CardContent>
		</Card>
	);
};
