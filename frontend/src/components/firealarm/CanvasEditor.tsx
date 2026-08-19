import type React from "react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

/**
 * RACE GUARD: This component uses local React state for detector positions.
 * If WebSocket-driven live updates are added (e.g., real-time collaboration),
 * they MUST go through useWebSocketStream to prevent state mutation during
 * render and out-of-order message processing.
 */

// Define detector types
export type DetectorType =
	| "smoke"
	| "heat"
	| "pull"
	| "horns"
	| "speaker"
	| "facp"
	| "iso";

// Define detector interface
export interface Detector {
	id: string;
	x: number;
	y: number;
	type: DetectorType;
	zone?: string;
	address?: string;
	status: "normal" | "warning" | "fault";
	coverageRadius: number;
	location?: string;
	heightAFF?: number;
	manufacturer?: string;
	model?: string;
	sensitivity?: "high" | "standard" | "low";
	lastTestDate?: string;
}

export interface PreviewGhostDevice {
	id: string;
	x_m?: number;
	y_m?: number;
	x?: number;
	y?: number;
	type: DetectorType;
	coverage_radius_m?: number;
}

interface CanvasEditorProps {
	floorPlanImage?: string;
	detectors: Detector[];
	onDetectorsChange: (detectors: Detector[]) => void;
	circuitTopology?: "class_a" | "class_b";
	onTopologyChange?: (topology: "class_a" | "class_b") => void;
	previewDevices?: PreviewGhostDevice[];
}

export const CanvasEditor: React.FC<CanvasEditorProps> = ({
	floorPlanImage,
	detectors,
	onDetectorsChange,
	circuitTopology: externalTopology,
	onTopologyChange,
	previewDevices = [],
}) => {
	const { t } = useTranslation();
	const canvasRef = useRef<HTMLDivElement>(null);
	const [draggingDetector, setDraggingDetector] = useState<string | null>(null);
	const [selectedDetector, setSelectedDetector] = useState<string | null>(null);
	const [newDetectorType, setNewDetectorType] = useState<DetectorType>("smoke");
	const [internalTopology, setInternalTopology] = useState<"class_a" | "class_b">("class_b");

	const topology = externalTopology ?? internalTopology;
	const setTopology = (top: "class_a" | "class_b") => {
		setInternalTopology(top);
		onTopologyChange?.(top);
	};

	// Handle click on canvas to add new detector
	const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
		if (!canvasRef.current) return;

		const rect = canvasRef.current.getBoundingClientRect();
		const x = e.clientX - rect.left;
		const y = e.clientY - rect.top;

		// Define coverage radius based on detector type
		let coverageRadius = 6.37; // Default for smoke detector
		if (newDetectorType === "heat") {
			coverageRadius = 4.27; // Smaller for heat detector
		} else if (newDetectorType === "iso" || newDetectorType === "facp") {
			coverageRadius = 0; // Modules / panels don't have optical coverage circles
		}

		const newDetector: Detector = {
			id: `detector-${Date.now()}`,
			x,
			y,
			type: newDetectorType,
			status: "normal",
			coverageRadius,
			location: "Not Set",
			heightAFF: 2.7,
			manufacturer: "Default",
			model: "Generic",
			sensitivity: "standard",
			lastTestDate: new Date().toISOString().split("T")[0],
		};

		onDetectorsChange([...detectors, newDetector]);
	};

	// Handle mouse down on a detector to start dragging
	const handleMouseDown = (id: string, e: React.MouseEvent) => {
		e.stopPropagation();
		setDraggingDetector(id);
		setSelectedDetector(id);
	};

	// Handle mouse move to update detector position
	useEffect(() => {
		const handleMouseMove = (e: MouseEvent) => {
			if (draggingDetector && canvasRef.current) {
				const rect = canvasRef.current.getBoundingClientRect();
				const x = e.clientX - rect.left;
				const y = e.clientY - rect.top;

				const updatedDetectors = detectors.map((detector) => {
					if (detector.id === draggingDetector) {
						return { ...detector, x, y };
					}
					return detector;
				});

				onDetectorsChange(updatedDetectors);
			}
		};

		const handleMouseUp = () => {
			setDraggingDetector(null);
		};

		if (draggingDetector) {
			globalThis.addEventListener("mousemove", handleMouseMove);
			globalThis.addEventListener("mouseup", handleMouseUp);
		}

		return () => {
			globalThis.removeEventListener("mousemove", handleMouseMove);
			globalThis.removeEventListener("mouseup", handleMouseUp);
		};
	}, [draggingDetector, detectors, onDetectorsChange]);

	// Get status color based on detector status
	const getStatusColor = (status: "normal" | "warning" | "fault") => {
		switch (status) {
			case "normal":
				return "#10B981"; // Green
			case "warning":
				return "#F59E0B"; // Amber
			case "fault":
				return "#EF4444"; // Red
			default:
				return "#10B981"; // Green
		}
	};

	// Render detector based on its type
	const renderDetector = (detector: Detector) => {
		const isSelected = selectedDetector === detector.id;
		const statusColor = getStatusColor(detector.status);

		let detectorShape = (
			<circle
				cx="12"
				cy="12"
				r="8"
				fill={statusColor}
				stroke="#FFFFFF"
				strokeWidth="2"
			/>
		);
		switch (detector.type) {
			case "heat":
				detectorShape = (
					<polygon
						points="12,4 20,20 4,20"
						fill={statusColor}
						stroke="#FFFFFF"
						strokeWidth="2"
					/>
				);
				break;
			case "pull":
				detectorShape = (
					<rect
						x="6"
						y="6"
						width="12"
						height="12"
						rx="2"
						fill={statusColor}
						stroke="#FFFFFF"
						strokeWidth="2"
					/>
				);
				break;
			case "horns":
				detectorShape = (
					<rect
						x="4"
						y="8"
						width="16"
						height="8"
						rx="2"
						fill={statusColor}
						stroke="#FFFFFF"
						strokeWidth="2"
					/>
				);
				break;
			case "facp":
				detectorShape = (
					<rect
						x="2"
						y="4"
						width="20"
						height="16"
						rx="3"
						fill={statusColor}
						stroke="#FFFFFF"
						strokeWidth="2"
					/>
				);
				break;
			case "iso":
				detectorShape = (
					<g>
						<polygon
							points="12,2 21,7 21,17 12,22 3,17 3,7"
							fill="#0e7490"
							stroke="#38bdf8"
							strokeWidth="2"
						/>
						<text
							x="12"
							y="14.5"
							textAnchor="middle"
							fill="#ffffff"
							fontSize="7"
							fontWeight="bold"
							fontFamily="monospace"
						>
							ISO
						</text>
					</g>
				);
				break;
		}

		return (
			<g
				key={detector.id}
				transform={`translate(${detector.x - 12}, ${detector.y - 12})`}
				onMouseDown={(e) => handleMouseDown(detector.id, e)}
				onClick={(e) => e.stopPropagation()}
				onKeyDown={(e: React.KeyboardEvent) => {
					if (e.key === "Enter") e.stopPropagation();
				}}
				style={{
					cursor: draggingDetector ? "grabbing" : "grab",
					pointerEvents: "auto",
				}}
			>
				{detectorShape}
				{isSelected && (
					<rect
						x="-2"
						y="-2"
						width="28"
						height="28"
						rx="4"
						fill="none"
						stroke="#38bdf8"
						strokeWidth="2"
						strokeDasharray="4 2"
					/>
				)}
			</g>
		);
	};

	const isolatorCount = detectors.filter((d) => d.type === "iso").length;
	const lastDetector = detectors.at(-1);
	const firstDetector = detectors.at(0);

	return (
		<div className="flex flex-col h-full space-y-3">
			<div className="flex flex-wrap items-center justify-between gap-3 p-2.5 bg-card border border-border rounded text-xs">
				<div className="flex items-center gap-3">
					<div className="flex items-center gap-1.5">
						<label htmlFor="detector-type-select" className="font-mono text-muted-foreground font-semibold">
							Tool / Device:
						</label>
						<select
							id="detector-type-select"
							aria-label={t("fireAlarm.addDetector")}
							value={newDetectorType}
							onChange={(e) => setNewDetectorType(e.target.value as DetectorType)}
							className="bg-input border border-border rounded px-2 py-1 text-xs text-foreground font-mono"
						>
							<option value="smoke">{t("fireAlarm.smokeDet")}</option>
							<option value="heat">{t("fireAlarm.heatDet")}</option>
							<option value="pull">{t("fireAlarm.pullStation")}</option>
							<option value="horns">{t("fireAlarm.hornStrobe")}</option>
							<option value="speaker">{t("fireAlarm.speaker")}</option>
							<option value="facp">{t("fireAlarm.facp")}</option>
							<option value="iso">⚡ Fault Isolator (ISO)</option>
						</select>
					</div>

					<div className="flex items-center gap-1.5">
						<label htmlFor="circuit-topology-select" className="font-mono text-muted-foreground font-semibold">
							Circuit Pathway:
						</label>
						<select
							id="circuit-topology-select"
							aria-label="Circuit Pathway Topology"
							value={topology}
							onChange={(e) => setTopology(e.target.value as "class_a" | "class_b")}
							className="bg-input border border-border rounded px-2 py-1 text-xs text-foreground font-mono"
						>
							<option value="class_b">Class B (Radial / Branch)</option>
							<option value="class_a">Class A (Loop Return / Cyclic)</option>
						</select>
					</div>
				</div>

				<div className="flex items-center gap-2 font-mono text-[11px]">
					<span className="px-2 py-0.5 rounded bg-muted/60 border border-border text-muted-foreground">
						Devices: <strong className="text-foreground">{detectors.length}</strong>
					</span>
					<span className="px-2 py-0.5 rounded bg-cyan-950/40 border border-cyan-500/30 text-cyan-300">
						Isolators: <strong className="text-cyan-200">{isolatorCount}</strong>
					</span>
					{topology === "class_a" && (
						<span className="px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-500/30 text-emerald-400">
							✓ Class A Return Leg Active
						</span>
					)}
				</div>
			</div>

			<div // NOSONAR: typescript:S6848
				ref={canvasRef}
				className="flex-1 bg-card border border-border rounded-lg relative overflow-hidden"
				onClick={handleCanvasClick}
				onKeyDown={(e: React.KeyboardEvent<HTMLDivElement>) => {
					if (e.key === "Enter") {
						e.preventDefault();
						(document.activeElement as HTMLElement)?.click();
					}
				}}
				style={{ minHeight: "400px" }}
			>
				{floorPlanImage ? (
					<img
						src={floorPlanImage}
						alt="Floor Plan"
						className="absolute inset-0 w-full h-full object-contain"
					/>
				) : (
					<div className="absolute inset-0 bg-card flex items-center justify-center pointer-events-none">
						<p className="text-muted-foreground text-sm select-none font-mono">
							{t("fireAlarm.floorPlanPlaceholder")}
						</p>
					</div>
				)}

				<svg className="absolute inset-0 pointer-events-none w-full h-full">
					{/* Coverage circles */}
					{detectors.map((detector) => {
						if (!detector.coverageRadius) return null;
						return (
							<circle
								key={`coverage-${detector.id}`}
								cx={detector.x}
								cy={detector.y}
								r={detector.coverageRadius * 10}
								fill="rgba(56, 189, 248, 0.1)"
								stroke="rgba(56, 189, 248, 0.3)"
								strokeWidth="1"
							/>
						);
					})}

					{/* Circuit Wiring Pathways */}
					{detectors.length > 1 &&
						detectors.map((detector, idx) => {
							if (idx === detectors.length - 1) return null;
							const next = detectors[idx + 1];
							return (
								<line
									key={`wire-${detector.id}-${next.id}`}
									x1={detector.x}
									y1={detector.y}
									x2={next.x}
									y2={next.y}
									stroke="#f59e0b"
									strokeWidth="2"
									strokeOpacity="0.8"
								/>
							);
						})}

					{/* Class A Return Loop Leg (connects last device back to FACP / source) */}
					{topology === "class_a" && detectors.length > 1 && lastDetector && firstDetector && (
						<line
							x1={lastDetector.x}
							y1={lastDetector.y}
							x2={firstDetector.x}
							y2={firstDetector.y}
							stroke="#38bdf8"
							strokeWidth="2"
							strokeDasharray="4 2"
							strokeOpacity="0.9"
						/>
					)}

					{/* AI Proposal Preview Ghost Layer (Transient Projection) */}
					{previewDevices.map((pDev) => {
						const px = pDev.x !== undefined ? pDev.x : (pDev.x_m || 0) * 20 + 50;
						const py = pDev.y !== undefined ? pDev.y : (pDev.y_m || 0) * 20 + 50;
						const rad = (pDev.coverage_radius_m || 6.37) * 10;
						return (
							<g key={`preview-ghost-${pDev.id}`} opacity="0.85">
								<circle
									cx={px}
									cy={py}
									r={rad}
									fill="rgba(6, 182, 212, 0.08)"
									stroke="#06b6d4"
									strokeWidth="1.5"
									strokeDasharray="4 2"
								/>
								<circle
									cx={px}
									cy={py}
									r="10"
									fill="rgba(6, 182, 212, 0.25)"
									stroke="#06b6d4"
									strokeWidth="2"
									strokeDasharray="3 2"
								/>
								<text
									x={px}
									y={py + 3}
									textAnchor="middle"
									fill="#06b6d4"
									fontSize="8"
									fontWeight="bold"
									fontFamily="monospace"
								>
									AI
								</text>
							</g>
						);
					})}

					{/* Detectors & Isolators */}
					{detectors.map(renderDetector)}
				</svg>
			</div>
		</div>
	);
};
