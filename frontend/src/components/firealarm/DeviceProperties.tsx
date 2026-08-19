import { AlertTriangle, CheckCircle2, Save, X, XCircle } from "lucide-react";
import type React from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type { Detector as CanvasDetector, DetectorType } from "./CanvasEditor";

interface DeviceProperty {
	id: string;
	address: string; // "Loop-1, Address-42"
	zone: string; // "Zone 2-02"
	location: string; // "Room 205, Level 2"
	detectorType: DetectorType;
	heightAFF: number; // Above Finished Floor (meters)
	manufacturer: string; // "Hochiki", "System Sensor"
	modelNumber: string;
	sensitivityLevel: "high" | "standard" | "low";
	coverageArea: number; // m²
	status: "normal" | "warning" | "fault";
	lastTestDate?: string;
}

interface DevicePropertiesProps {
	device: CanvasDetector | null;
	onSave: (updatedDevice: Partial<DeviceProperty>) => void;
	onClose: () => void;
}

export const DeviceProperties: React.FC<DevicePropertiesProps> = ({
	device,
	onSave,
	onClose,
}) => {
	const { t } = useTranslation();
	const [editedDevice, setEditedDevice] = useState<Partial<DeviceProperty>>({
		id: device?.id,
		address: device?.address || "",
		zone: device?.zone || "",
		location: device?.location || "",
		detectorType: device?.type || "smoke",
		heightAFF: device?.heightAFF || 2.7, // Default ceiling height
		manufacturer: device?.manufacturer || "",
		modelNumber: device?.model || "",
		sensitivityLevel: device?.sensitivity || "standard",
		coverageArea: device?.coverageRadius
			? Math.PI * device.coverageRadius * device.coverageRadius
			: 0,
		status: device?.status || "normal",
		lastTestDate:
			device?.lastTestDate || new Date().toISOString().split("T")[0],
	});

	const handleChange = (
		field: keyof DeviceProperty,
		value: string | number | boolean,
	) => {
		setEditedDevice((prev) => ({
			...prev,
			[field]: value,
		}));
	};

	const handleSave = () => {
		if (device) {
			// Merge with existing device data to ensure all required fields are present
			const updatedDevice = {
				...device,
				...editedDevice,
				id: device.id, // Preserve the original ID
				x: device.x, // Preserve position
				y: device.y,
				coverageRadius: editedDevice.coverageArea
					? Math.sqrt(editedDevice.coverageArea / Math.PI)
					: device.coverageRadius,
			};

			onSave(updatedDevice);
		}
	};

	if (!device) {
		return (
			<div className="fixed top-14 right-4 w-80 md:w-96 max-h-[calc(100vh-80px)] flex flex-col bg-card border border-border rounded shadow-2xl z-50 overflow-hidden">
				<div className="p-4 flex-none border-b border-border flex justify-between items-center bg-popover/80">
					<h3 className="text-sm font-semibold text-foreground font-mono">
						{t("fireAlarm.deviceProperties")}
					</h3>
					<Button variant="ghost" size="sm" onClick={onClose} className="h-7 w-7 p-0">
						<X aria-hidden="true" className="h-4 w-4" />
					</Button>
				</div>
				<div className="p-4 flex-1">
					<p className="text-xs text-muted-foreground font-mono">
						{t("fireAlarm.selectDevice")}
					</p>
				</div>
			</div>
		);
	}

	return (
		<div className="fixed top-14 right-4 w-80 md:w-96 max-h-[calc(100vh-80px)] flex flex-col bg-card border border-border rounded shadow-2xl z-50 overflow-hidden">
			{/* Fixed Header */}
			<div className="px-4 py-3 flex-none border-b border-border flex justify-between items-center bg-popover/80">
				<div className="flex items-center gap-2">
					<span className="h-2.5 w-2.5 rounded-full bg-primary" />
					<h3 className="text-sm font-semibold text-foreground font-mono">
						{t("fireAlarm.deviceProperties")}
					</h3>
				</div>
				<Button variant="ghost" size="sm" onClick={onClose} className="h-7 w-7 p-0 hover:bg-muted text-muted-foreground">
					<X aria-hidden="true" className="h-4 w-4" />
				</Button>
			</div>

			{/* Scrollable Form Body */}
			<div className="p-4 flex-1 min-h-0 overflow-y-auto space-y-3.5 text-xs">
				<div>
					<Label className="text-xs text-muted-foreground font-mono mb-1 block">
						{t("fireAlarm.address")}
					</Label>
					<Input
						value={editedDevice.address || ""}
						onChange={(e) => handleChange("address", e.target.value)}
						placeholder={t("fireAlarm.addressPlaceholder") || undefined}
						className="h-8 text-xs bg-input border-border text-foreground font-mono"
					/>
				</div>

				<div>
					<Label className="text-xs text-muted-foreground font-mono mb-1 block">
						{t("fireAlarm.zone")}
					</Label>
					<Input
						value={editedDevice.zone || ""}
						onChange={(e) => handleChange("zone", e.target.value)}
						placeholder={t("fireAlarm.zonePlaceholder") || undefined}
						className="h-8 text-xs bg-input border-border text-foreground font-mono"
					/>
				</div>

				<div>
					<Label className="text-xs text-muted-foreground font-mono mb-1 block">
						{t("fireAlarm.location")}
					</Label>
					<Input
						value={editedDevice.location || ""}
						onChange={(e) => handleChange("location", e.target.value)}
						placeholder={t("fireAlarm.locationPlaceholder") || undefined}
						className="h-8 text-xs bg-input border-border text-foreground font-mono"
					/>
				</div>

				<div>
					<Label className="text-xs text-muted-foreground font-mono mb-1 block">
						{t("fireAlarm.detectorType")}
					</Label>
					<Select
						value={editedDevice.detectorType}
						onValueChange={(value: DetectorType) =>
							handleChange("detectorType", value)
						}
					>
						<SelectTrigger className="h-8 text-xs bg-input border-border text-foreground font-mono">
							<SelectValue />
						</SelectTrigger>
						<SelectContent className="bg-card border-border">
							<SelectItem value="smoke">
								{t("fireAlarm.smokeDet")}
							</SelectItem>
							<SelectItem value="heat">{t("fireAlarm.heatDet")}</SelectItem>
							<SelectItem value="pull">
								{t("fireAlarm.pullStation")}
							</SelectItem>
							<SelectItem value="horns">
								{t("fireAlarm.hornStrobe")}
							</SelectItem>
							<SelectItem value="speaker">
								{t("fireAlarm.speaker")}
							</SelectItem>
							<SelectItem value="facp">{t("fireAlarm.facp")}</SelectItem>
						</SelectContent>
					</Select>
				</div>

				<div className="grid grid-cols-2 gap-2">
					<div>
						<Label className="text-xs text-muted-foreground font-mono mb-1 block">
							{t("fireAlarm.heightAff")} (m)
						</Label>
						<Input
							type="number"
							step="0.1"
							value={editedDevice.heightAFF || ""}
							onChange={(e) =>
								handleChange(
									"heightAFF",
									Number.parseFloat(e.target.value) || 0,
								)
							}
							placeholder="2.7"
							className="h-8 text-xs bg-input border-border text-foreground font-mono"
						/>
					</div>
					<div>
						<Label className="text-xs text-muted-foreground font-mono mb-1 block">
							Coverage (m²)
						</Label>
						<Input
							type="number"
							value={editedDevice.coverageArea ? Math.round(editedDevice.coverageArea) : ""}
							onChange={(e) =>
								handleChange(
									"coverageArea",
									Number.parseFloat(e.target.value) || 0,
								)
							}
							placeholder="80"
							className="h-8 text-xs bg-input border-border text-foreground font-mono"
						/>
					</div>
				</div>

				<div className="grid grid-cols-2 gap-2">
					<div>
						<Label className="text-xs text-muted-foreground font-mono mb-1 block">
							{t("fireAlarm.manufacturer")}
						</Label>
						<Input
							value={editedDevice.manufacturer || ""}
							onChange={(e) => handleChange("manufacturer", e.target.value)}
							placeholder="System Sensor"
							className="h-8 text-xs bg-input border-border text-foreground"
						/>
					</div>
					<div>
						<Label className="text-xs text-muted-foreground font-mono mb-1 block">
							{t("fireAlarm.model")}
						</Label>
						<Input
							value={editedDevice.modelNumber || ""}
							onChange={(e) => handleChange("modelNumber", e.target.value)}
							placeholder="2251B"
							className="h-8 text-xs bg-input border-border text-foreground font-mono"
						/>
					</div>
				</div>

				<div>
					<Label className="text-xs text-muted-foreground font-mono mb-1 block">
						{t("fireAlarm.sensitivity")}
					</Label>
					<Select
						value={editedDevice.sensitivityLevel}
						onValueChange={(value: "high" | "standard" | "low") =>
							handleChange("sensitivityLevel", value)
						}
					>
						<SelectTrigger className="h-8 text-xs bg-input border-border text-foreground font-mono">
							<SelectValue />
						</SelectTrigger>
						<SelectContent className="bg-card border-border">
							<SelectItem value="high">{t("fireAlarm.high")}</SelectItem>
							<SelectItem value="standard">
								{t("fireAlarm.standard")}
							</SelectItem>
							<SelectItem value="low">{t("fireAlarm.low")}</SelectItem>
						</SelectContent>
					</Select>
				</div>

				<div>
					<Label className="text-xs text-muted-foreground font-mono mb-1 block">
						{t("fireAlarm.status")}
					</Label>
					<div className="flex items-center gap-2">
						<Badge
							variant="secondary"
							className={
								editedDevice.status === "normal"
									? "bg-success/15 text-emerald-400 border-success/30 font-mono text-[11px]"
									: editedDevice.status === "warning" // NOSONAR: typescript:S3358
										? "bg-warning/15 text-amber-400 border-warning/30 font-mono text-[11px]"
										: "bg-danger/15 text-red-400 border-danger/30 font-mono text-[11px]"
							}
						>
							{editedDevice.status === "normal" && (
								<CheckCircle2 aria-hidden="true" className="h-3 w-3 mr-1" />
							)}
							{editedDevice.status === "warning" && (
								<AlertTriangle
									aria-hidden="true"
									className="h-3 w-3 mr-1"
								/>
							)}
							{editedDevice.status === "fault" && (
								<XCircle aria-hidden="true" className="h-3 w-3 mr-1" />
							)}
							{editedDevice.status?.toUpperCase()}
						</Badge>
					</div>
				</div>

				<div>
					<Label className="text-xs text-muted-foreground font-mono mb-1 block">
						{t("fireAlarm.lastTest")}
					</Label>
					<Input
						type="date"
						value={editedDevice.lastTestDate || ""}
						onChange={(e) => handleChange("lastTestDate", e.target.value)}
						className="h-8 text-xs bg-input border-border text-foreground font-mono"
					/>
				</div>
			</div>

			{/* Fixed Action Footer */}
			<div className="p-3 flex-none border-t border-border bg-popover/80 flex items-center gap-2">
				<Button
					size="sm"
					className="flex-1 bg-primary hover:bg-primary/90 text-primary-foreground font-mono text-xs h-8"
					onClick={handleSave}
				>
					<Save aria-hidden="true" className="h-3.5 w-3.5 mr-1.5" />
					Apply Parameters
				</Button>
				<Button
					variant="outline"
					size="sm"
					className="border-border text-foreground/90 font-mono text-xs h-8"
					onClick={onClose}
				>
					{t("common.cancel")}
				</Button>
			</div>
		</div>
	);
};
