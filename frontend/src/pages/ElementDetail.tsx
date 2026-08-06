
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { RevitParametersPanel } from "@/components/engineering/RevitParametersPanel";
import { api } from "@/services/api";
import type { ElementUpdate } from "@/types";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";

function ElementDetail() {
	const { t } = useTranslation();
	const { id } = useParams<{ id: string }>();
	const navigate = useNavigate();
	const queryClient = useQueryClient();
	const [isEditing, setIsEditing] = useState(false);
	const [editName, setEditName] = useState("");
	const [editMaterial, setEditMaterial] = useState("");
	const [editFireRating, setEditFireRating] = useState("");
	const [editDescription, setEditDescription] = useState("");
	const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
	const containerRef = useRef<HTMLDivElement>(null);

	useGSAP(() => {
		gsap.fromTo(
			".stagger-card",
			{ y: 20, opacity: 0 },
			{ y: 0, opacity: 1, duration: 0.4, stagger: 0.05, ease: "power2.out" }
		);
	}, { scope: containerRef });

	const {
		data: element,
		isLoading,
		error,
	} = useQuery({
		queryKey: ["element", id],
		queryFn: () => api.getElement(id!),
		enabled: !!id,
	});

	const { data: connectionsData } = useQuery({
		queryKey: ["element-connections", id],
		queryFn: () => api.getConnections({ element_id: id! }),
		enabled: !!id,
	});

	const connections = connectionsData?.items ?? [];

	const updateMutation = useMutation({
		mutationFn: (data: ElementUpdate) => api.updateElement(id!, data),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["element", id] });
			queryClient.invalidateQueries({ queryKey: ["elements"] });
			setIsEditing(false);
		},
	});

	const deleteMutation = useMutation({
		mutationFn: () => api.deleteElement(id!),
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["elements"] });
			navigate("/elements");
		},
	});

	const startEditing = () => {
		if (element?.properties) {
			setEditName(element.properties.name ?? "");
			setEditMaterial(element.properties.material ?? "");
			setEditFireRating(element.properties.fire_rating ?? "");
			setEditDescription(element.properties.description ?? "");
		}
		setIsEditing(true);
	};

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-12">
				<div className="w-8 h-8 border-2 border-border border-t-primary rounded-full animate-spin" />
			</div>
		);
	}

	if (error || !element) {
		return (
			<div className="space-y-4">
				<Link
					to="/elements"
					className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-white transition-colors"
				>
					<svg
						width="16"
						height="16"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						strokeWidth="2"
						strokeLinecap="round"
						strokeLinejoin="round"
					>
						<line x1="19" y1="12" x2="5" y2="12" />
						<polyline points="12 19 5 12 12 5" />
					</svg>
					{t("elements.backToElements")}
				</Link>
				<div className="bg-slate-500/10 border border-slate-500/20 rounded-lg p-4">
					<p className="text-danger text-sm">
						{error instanceof Error ? error.message : t("elements.notFound")}
					</p>
				</div>
			</div>
		);
	}

	return (
		<div className="space-y-6" ref={containerRef}>
			{/* Breadcrumb */}
			<div className="flex items-center gap-2 text-sm stagger-card">
				<Link
					to="/elements"
					className="text-muted-foreground hover:text-white transition-colors"
				>
					{t("elements.title")}
				</Link>
				<span className="text-muted-foreground/70">/</span>
				<span className="text-white">
					{element.properties?.name ?? element.element_id}
				</span>
			</div>

			{/* HERO STRIP — Engineering identity header */}
			<div
				className="stagger-card"
				style={{
					background: "var(--color-graphite)",
					borderLeft: "4px solid var(--color-primary)",
					borderRadius: "2px",
					paddingTop: "1rem",
					paddingBottom: "1rem",
					paddingLeft: "1.25rem",
					paddingRight: "1.25rem",
				}}
			>
				<div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
					<div className="space-y-1">
						{/* Element ID in monospace */}
						<div className="flex items-center gap-3">
							<code
								style={{
									fontFamily: "var(--font-data)",
									fontSize: "0.7rem",
									letterSpacing: "0.1em",
									color: "var(--color-steel)",
									textTransform: "uppercase",
								}}
							>
								EL‑{element.element_id.slice(0, 8).toUpperCase()}
							</code>
							{/* Compliance Badge */}
							{element.properties?.fire_rating ? (
								<span
									style={{
										fontFamily: "var(--font-data)",
										fontSize: "0.65rem",
										letterSpacing: "0.08em",
										fontWeight: 600,
										textTransform: "uppercase",
										color: "var(--color-evac-green)",
										border: "1px solid var(--color-evac-green)",
										borderRadius: "2px",
										padding: "0.1rem 0.4rem",
									}}
								>
									{t("elementDetail.nfpa101Compliant")}
								</span>
							) : (
								<span
									style={{
										fontFamily: "var(--font-data)",
										fontSize: "0.65rem",
										letterSpacing: "0.08em",
										fontWeight: 600,
										textTransform: "uppercase",
										color: "var(--color-amber-alert)",
										border: "1px solid var(--color-amber-alert)",
										borderRadius: "2px",
										padding: "0.1rem 0.4rem",
									}}
								>
									{t("elementDetail.dataIncomplete")}
								</span>
							)}
						</div>
						{/* Element Name */}
						<h1
							style={{
								fontFamily: "var(--font-display)",
								fontWeight: 700,
								fontSize: "1.5rem",
								letterSpacing: "-0.02em",
								color: "var(--color-bone)",
								lineHeight: 1.2,
							}}
						>
							{element.properties?.name ?? "Unnamed Element"}
						</h1>
						{/* Meta row */}
						<div className="flex flex-wrap items-center gap-3 mt-1">
							{element.properties?.element_type && (
								<span style={{ fontFamily: "var(--font-data)", fontSize: "0.75rem", color: "var(--color-steel)", letterSpacing: "0.04em" }}>
									{element.properties.element_type}
								</span>
							)}
							{element.properties?.fire_rating && (
								<>
									<span style={{ color: "var(--color-steel)" }}>·</span>
									<span style={{ fontFamily: "var(--font-data)", fontSize: "0.75rem", color: "var(--color-primary)", letterSpacing: "0.04em" }}>
										Fire Rating: {element.properties.fire_rating}
									</span>
								</>
							)}
							<span style={{ color: "var(--color-steel)" }}>·</span>
							<span style={{ fontFamily: "var(--font-data)", fontSize: "0.75rem", color: "var(--color-steel)", letterSpacing: "0.04em" }}>
								v{element.version}
							</span>
						</div>
					</div>
					{/* Actions */}
					<div className="flex gap-2 flex-shrink-0">
						<button
							type="button"
							onClick={startEditing}
							className="px-4 py-2 min-h-[44px] text-sm font-medium rounded transition-colors focus:ring-2 focus:ring-primary focus:outline-none"
							style={{
								fontFamily: "var(--font-data)",
								fontSize: "0.75rem",
								letterSpacing: "0.06em",
								textTransform: "uppercase",
								color: "var(--color-bone)",
								background: "var(--color-panel-recess)",
								border: "1px solid rgba(90,103,112,0.45)",
								borderRadius: "2px",
							}}
						>
							Edit
						</button>
						<button
							type="button"
							onClick={() => setShowDeleteConfirm(true)}
							disabled={deleteMutation.isPending}
							aria-label={t("common.delete")}
							className="px-4 py-2 min-h-[44px] text-sm font-medium transition-colors focus:ring-2 focus:ring-danger focus:outline-none disabled:opacity-50"
							style={{
								fontFamily: "var(--font-data)",
								fontSize: "0.75rem",
								letterSpacing: "0.06em",
								textTransform: "uppercase",
								color: "var(--color-signal-red)",
								background: "rgba(194,54,44,0.08)",
								border: "1px solid rgba(194,54,44,0.35)",
								borderRadius: "2px",
							}}
						>
							{deleteMutation.isPending ? "Deleting…" : t("common.delete")}
						</button>
					</div>
				</div>
			</div>

			{/* Bento Grid Layout */}
			<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
				{/* Main Column */}
				<div className="lg:col-span-2 space-y-6">
					
			{/* Properties */}
			<div className="bg-card border border-border rounded-xl shadow-sm p-6 stagger-card">
				<h2 className="text-lg font-semibold text-white mb-4">Properties</h2>

				{isEditing ? (
					<div className="space-y-4">
						{updateMutation.isError && (
							<div className="bg-slate-500/10 border border-slate-500/20 rounded-lg p-3">
								<p className="text-danger text-sm">
									{updateMutation.error instanceof Error
										? updateMutation.error.message
										: "Failed to update"}
								</p>
							</div>
						)}
						<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
							<div>
								<label className="block text-sm font-medium text-foreground/90 mb-1">
									Name
								</label>
								<input
									type="text"
									value={editName}
									onChange={(e) => setEditName(e.target.value)}
									className="w-full bg-card border border-border text-white text-sm rounded-lg px-3 py-2 min-h-[44px] focus:ring-2 focus:ring-primary focus:outline-none transition-all stagger-card"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium text-foreground/90 mb-1">
									Material
								</label>
								<input
									type="text"
									value={editMaterial}
									onChange={(e) => setEditMaterial(e.target.value)}
									className="w-full bg-card border border-border text-white text-sm rounded-lg px-3 py-2 min-h-[44px] focus:ring-2 focus:ring-primary focus:outline-none transition-all stagger-card"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium text-foreground/90 mb-1">
									Fire Rating
								</label>
								<input
									type="text"
									value={editFireRating}
									onChange={(e) => setEditFireRating(e.target.value)}
									className="w-full bg-card border border-border text-white text-sm rounded-lg px-3 py-2 min-h-[44px] focus:ring-2 focus:ring-primary focus:outline-none transition-all stagger-card"
								/>
							</div>
							<div>
								<label className="block text-sm font-medium text-foreground/90 mb-1">
									Description
								</label>
								<input
									type="text"
									value={editDescription}
									onChange={(e) => setEditDescription(e.target.value)}
									className="w-full bg-card border border-border text-white text-sm rounded-lg px-3 py-2 min-h-[44px] focus:ring-2 focus:ring-primary focus:outline-none transition-all stagger-card"
								/>
							</div>
						</div>
						<div className="flex justify-end gap-3">
							<button
							type="button" onClick={() => setIsEditing(false)}
							className="px-4 py-2 min-h-[44px] text-sm text-foreground/90 hover:text-white transition-colors focus:ring-2 focus:ring-primary focus:outline-none rounded-lg"
						>
							Cancel
						</button>
						<button
							type="button" onClick={() => {
									updateMutation.mutate({
										properties: {
											name: editName,
											material: editMaterial,
											fire_rating: editFireRating,
											description: editDescription,
										},
									});
								}}
								disabled={updateMutation.isPending}
								className="px-4 py-2 min-h-[44px] bg-primary hover:bg-primary/90 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background focus:outline-none"
							>
								{updateMutation.isPending ? "Saving…" : "Save Changes"}
							</button>
						</div>
					</div>
				) : (
					<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
						<PropertyRow
							label="Type"
							value={element.properties?.element_type}
						/>
						<PropertyRow label="Name" value={element.properties?.name} />
						<PropertyRow
							label="Description"
							value={element.properties?.description}
						/>
						<PropertyRow
							label="Material"
							value={element.properties?.material}
						/>
						<PropertyRow
							label="Fire Rating"
							value={element.properties?.fire_rating}
						/>
						<PropertyRow
							label="Height"
							value={
								element.properties?.height != null
									? `${element.properties.height} m`
									: undefined
							}
						/>
						<PropertyRow
							label="Width"
							value={
								element.properties?.width != null
									? `${element.properties.width} m`
									: undefined
							}
						/>
						<PropertyRow
							label="Load Bearing"
							value={
								element.properties?.load_bearing != null
									? element.properties.load_bearing  // NOSONAR: typescript:S3358
										? "Yes"
										: "No"
									: undefined
							}
						/>
						<PropertyRow label="Layer" value={element.properties?.layer} />
						<PropertyRow
							label="Revit Category"
							value={element.properties?.revit_category}
						/>
						<PropertyRow label="Source File" value={element.source_file} />
						<PropertyRow
							label="AutoCAD Handle"
							value={element.autocad_handle}
						/>
						<PropertyRow
							label="Revit Element ID"
							value={
								element.revit_element_id != null
									? String(element.revit_element_id)
									: undefined
							}
						/>
					</div>
				)}
			</div>

			{/* Geometry */}
			<div className="bg-card border border-border rounded-xl shadow-sm p-6 stagger-card">
				<h2 className="text-lg font-semibold text-white mb-4">Geometry</h2>
				{element.geometry ? (
					<div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
						<PropertyRow
							label="Area"
							value={`${element.geometry.area.toFixed(2)} m²`}
						/>
						<PropertyRow
							label="Perimeter"
							value={`${element.geometry.perimeter.toFixed(2)} m`}
						/>
						<PropertyRow
							label="Closed Polyline"
							value={element.geometry.polyline_closed ? "Yes" : "No"}
						/>
						<div className="sm:col-span-3">
							<PropertyRow
								label="Points"
								value={`${element.geometry.points.length} points`}
							/>
							{element.geometry.points.length > 0 && (
								<div className="mt-2 max-h-48 overflow-y-auto custom-scrollbar bg-card rounded-lg p-3 stagger-card">
									<pre className="text-xs text-muted-foreground">
										{JSON.stringify(element.geometry.points, null, 2)}
									</pre>
								</div>
>>>>>>> feature/engineering-identity
							)}
						</div>
						{/* Element Name */}
						<h1
							style={{
								fontFamily: "var(--font-display)",
								fontWeight: 700,
								fontSize: "1.5rem",
								letterSpacing: "-0.02em",
								color: "var(--color-bone)",
								lineHeight: 1.2,
							}}
						>
							{element.properties?.name ?? t("elementDetail.unnamedElement")}
						</h1>
						{/* Meta row */}
						<div className="flex flex-wrap items-center gap-3 mt-1">
							{element.properties?.element_type && (
								<span style={{ fontFamily: "var(--font-data)", fontSize: "0.75rem", color: "var(--color-steel)", letterSpacing: "0.04em" }}>
									{element.properties.element_type}
								</span>
							)}
							{element.properties?.fire_rating && (
								<>
									<span style={{ color: "var(--color-steel)" }}>·</span>
									<span style={{ fontFamily: "var(--font-data)", fontSize: "0.75rem", color: "var(--color-primary)", letterSpacing: "0.04em" }}>
										{t("elementDetail.fireRating")}: {element.properties.fire_rating}
									</span>
								</>
							)}
							<span style={{ color: "var(--color-steel)" }}>·</span>
							<span style={{ fontFamily: "var(--font-data)", fontSize: "0.75rem", color: "var(--color-steel)", letterSpacing: "0.04em" }}>
								v{element.version}
							</span>
						</div>
					</div>
					{/* Actions */}
					<div className="flex gap-2 flex-shrink-0">
						<button
							type="button"
							onClick={startEditing}
							className="px-4 py-2 min-h-[44px] text-sm font-medium rounded transition-colors focus:ring-2 focus:ring-primary focus:outline-none"
							style={{
								fontFamily: "var(--font-data)",
								fontSize: "0.75rem",
								letterSpacing: "0.06em",
								textTransform: "uppercase",
								color: "var(--color-bone)",
								background: "var(--color-panel-recess)",
								border: "1px solid rgba(90,103,112,0.45)",
								borderRadius: "2px",
							}}
						>
							{t("common.edit")}
						</button>
						<button
							type="button"
							onClick={() => setShowDeleteConfirm(true)}
							disabled={deleteMutation.isPending}
							aria-label={t("common.delete")}
							className="px-4 py-2 min-h-[44px] text-sm font-medium transition-colors focus:ring-2 focus:ring-danger focus:outline-none disabled:opacity-50"
							style={{
								fontFamily: "var(--font-data)",
								fontSize: "0.75rem",
								letterSpacing: "0.06em",
								textTransform: "uppercase",
								color: "var(--color-signal-red)",
								background: "rgba(194,54,44,0.08)",
								border: "1px solid rgba(194,54,44,0.35)",
								borderRadius: "2px",
							}}
						>
							{deleteMutation.isPending ? t("common.deleting") : t("common.delete")}
						</button>
					</div>
				</div>
			</div>

			{/* Bento Grid Layout */}
			<div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
				{/* Main Column */}
				<div className="lg:col-span-2 space-y-6">

					{/* Properties */}
					<div className="bg-card border border-border rounded-xl shadow-sm p-6 stagger-card">
						<h2 className="text-lg font-semibold text-white mb-4">{t("elementDetail.properties")}</h2>

						{isEditing ? (
							<div className="space-y-4">
								{updateMutation.isError && (
									<div className="bg-slate-500/10 border border-slate-500/20 rounded-lg p-3">
										<p className="text-danger text-sm">
											{updateMutation.error instanceof Error
												? updateMutation.error.message
												: t("elementDetail.updateFailed")}
										</p>
									</div>
								)}
								<div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
									<div>
										<label className="block text-sm font-medium text-foreground/90 mb-1">
											{t("elementDetail.name")}
										</label>
										<input
											type="text"
											value={editName}
											onChange={(e) => setEditName(e.target.value)}
											className="w-full bg-card border border-border text-white text-sm rounded-lg px-3 py-2 min-h-[44px] focus:ring-2 focus:ring-primary focus:outline-none transition-all stagger-card"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium text-foreground/90 mb-1">
											{t("elementDetail.material")}
										</label>
										<input
											type="text"
											value={editMaterial}
											onChange={(e) => setEditMaterial(e.target.value)}
											className="w-full bg-card border border-border text-white text-sm rounded-lg px-3 py-2 min-h-[44px] focus:ring-2 focus:ring-primary focus:outline-none transition-all stagger-card"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium text-foreground/90 mb-1">
											{t("elementDetail.fireRating")}
										</label>
										<input
											type="text"
											value={editFireRating}
											onChange={(e) => setEditFireRating(e.target.value)}
											className="w-full bg-card border border-border text-white text-sm rounded-lg px-3 py-2 min-h-[44px] focus:ring-2 focus:ring-primary focus:outline-none transition-all stagger-card"
										/>
									</div>
									<div>
										<label className="block text-sm font-medium text-foreground/90 mb-1">
											{t("elementDetail.description")}
										</label>
										<input
											type="text"
											value={editDescription}
											onChange={(e) => setEditDescription(e.target.value)}
											className="w-full bg-card border border-border text-white text-sm rounded-lg px-3 py-2 min-h-[44px] focus:ring-2 focus:ring-primary focus:outline-none transition-all stagger-card"
										/>
									</div>
								</div>
								<div className="flex justify-end gap-3">
									<button
										type="button" onClick={() => setIsEditing(false)}
										className="px-4 py-2 min-h-[44px] text-sm text-foreground/90 hover:text-white transition-colors focus:ring-2 focus:ring-primary focus:outline-none rounded-lg"
									>
										{t("common.cancel")}
									</button>
									<button
										type="button" onClick={() => {
											updateMutation.mutate({
												properties: {
													name: editName,
													material: editMaterial,
													fire_rating: editFireRating,
													description: editDescription,
												},
											});
										}}
										disabled={updateMutation.isPending}
										className="px-4 py-2 min-h-[44px] bg-primary hover:bg-primary/90 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background focus:outline-none"
									>
										{updateMutation.isPending ? t("common.saving") : t("common.saveChanges")}
									</button>
								</div>
=======
				) : (
					<p className="text-muted-foreground text-sm">No geometry data available</p>
				)}
			</div>

			{/* Revit Parameters */}
			<div className="stagger-card">
				{element.revit_element_id && (
					<RevitParametersPanel elementId={id!} />
				)}
			</div>

			</div>{/* End Main Column */}

			{/* Sidebar Column */}
			<div className="lg:col-span-1 space-y-6">

			{/* Timestamps */}
			<div className="bg-card border border-border rounded-xl shadow-sm p-6 stagger-card">
				<h2 className="text-lg font-semibold text-white mb-4">Timestamps</h2>
				<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
					<PropertyRow
						label="Created"
						value={
							element.created_timestamp
								? new Date(element.created_timestamp).toLocaleString()
								: "—"
						}
					/>
					<PropertyRow
						label="Last Modified"
						value={
							element.last_modified_timestamp
								? new Date(element.last_modified_timestamp).toLocaleString()
								: "—"
						}
					/>
					<PropertyRow label="Modified By" value={element.last_modified_by} />
				</div>
			</div>

			{/* Connections */}
			<div className="bg-card border border-border rounded-xl shadow-sm p-6 stagger-card">
				<h2 className="text-lg font-semibold text-white mb-4">
					Connections ({connections.length})
				</h2>
				{connections.length > 0 ? (
					<div className="space-y-2">
						{connections.map((conn) => (
							<div
								key={conn.connection_id}
								className="flex items-center gap-3 bg-muted/50 border border-border/50 rounded-lg p-3"
							>
								<span className="text-primary text-xs font-mono">
									{conn.from_element_id === id ? "→" : "←"}
								</span>
								<Link
									to={`/elements/${conn.from_element_id === id ? conn.to_element_id : conn.from_element_id}`}
									className="text-sm text-white hover:text-primary transition-colors"
								>
									{conn.from_element_id === id
										? conn.to_element_id
										: conn.from_element_id}
								</Link>
								<span className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded">
									{conn.relationship_type}
								</span>
>>>>>>> feature/engineering-identity
							</div>
						) : (
							<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
								<PropertyRow
									label={t("elementDetail.type")}
									value={element.properties?.element_type}
								/>
								<PropertyRow label={t("elementDetail.name")} value={element.properties?.name} />
								<PropertyRow
									label={t("elementDetail.description")}
									value={element.properties?.description}
								/>
								<PropertyRow
									label={t("elementDetail.material")}
									value={element.properties?.material}
								/>
								<PropertyRow
									label={t("elementDetail.fireRating")}
									value={element.properties?.fire_rating}
								/>
								<PropertyRow
									label={t("elementDetail.height")}
									value={
										element.properties?.height != null
											? `${element.properties.height} m`
											: undefined
									}
								/>
								<PropertyRow
									label={t("elementDetail.width")}
									value={
										element.properties?.width != null
											? `${element.properties.width} m`
											: undefined
									}
								/>
								<PropertyRow
									label={t("elementDetail.loadBearing")}
									value={
										element.properties?.load_bearing != null
											? element.properties.load_bearing  // NOSONAR: typescript:S3358
												? t("common.yes")
												: t("common.no")
											: undefined
									}
								/>
								<PropertyRow label={t("elementDetail.layer")} value={element.properties?.layer} />
								<PropertyRow
									label={t("elementDetail.revitCategory")}
									value={element.properties?.revit_category}
								/>
								<PropertyRow label={t("elementDetail.sourceFile")} value={element.source_file} />
								<PropertyRow
									label={t("elementDetail.autocadHandle")}
									value={element.autocad_handle}
								/>
								<PropertyRow
									label={t("elementDetail.revitElementId")}
									value={
										element.revit_element_id != null
											? String(element.revit_element_id)
											: undefined
									}
								/>
							</div>
						)}
					</div>

					{/* Geometry */}
					<div className="bg-card border border-border rounded-xl shadow-sm p-6 stagger-card">
						<h2 className="text-lg font-semibold text-white mb-4">{t("elementDetail.geometry")}</h2>
						{element.geometry ? (
							<div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
								<PropertyRow
									label={t("elementDetail.area")}
									value={`${element.geometry.area.toFixed(2)} m²`}
								/>
								<PropertyRow
									label={t("elementDetail.perimeter")}
									value={`${element.geometry.perimeter.toFixed(2)} m`}
								/>
								<PropertyRow
									label={t("elementDetail.closedPolyline")}
									value={element.geometry.polyline_closed ? t("common.yes") : t("common.no")}
								/>
								<div className="sm:col-span-3">
									<PropertyRow
										label={t("elementDetail.points")}
										value={t("elementDetail.pointsCount", { count: element.geometry.points.length })}
									/>
									{element.geometry.points.length > 0 && (
										<div className="mt-2 max-h-48 overflow-y-auto custom-scrollbar bg-card rounded-lg p-3 stagger-card">
											<pre className="text-xs text-muted-foreground">
												{JSON.stringify(element.geometry.points, null, 2)}
											</pre>
										</div>
									)}
								</div>
							</div>
						) : (
							<p className="text-muted-foreground text-sm">{t("elementDetail.noGeometryData")}</p>
						)}
					</div>

					{/* Revit Parameters */}
					<div className="stagger-card">
						{element.revit_element_id && (
							<RevitParametersPanel elementId={id!} />
						)}
					</div>

				</div>{/* End Main Column */}

				{/* Sidebar Column */}
				<div className="lg:col-span-1 space-y-6">

					{/* Timestamps */}
					<div className="bg-card border border-border rounded-xl shadow-sm p-6 stagger-card">
						<h2 className="text-lg font-semibold text-white mb-4">{t("elementDetail.timestamps")}</h2>
						<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
							<PropertyRow
								label={t("elementDetail.created")}
								value={
									element.created_timestamp
										? new Date(element.created_timestamp).toLocaleString()
										: "—"
								}
							/>
							<PropertyRow
								label={t("elementDetail.lastModified")}
								value={
									element.last_modified_timestamp
										? new Date(element.last_modified_timestamp).toLocaleString()
										: "—"
								}
							/>
							<PropertyRow label={t("elementDetail.modifiedBy")} value={element.last_modified_by} />
						</div>
					</div>

					{/* Connections */}
					<div className="bg-card border border-border rounded-xl shadow-sm p-6 stagger-card">
						<h2 className="text-lg font-semibold text-white mb-4">
							{t("elementDetail.connections", { count: connections.length })}
						</h2>
						{connections.length > 0 ? (
							<div className="space-y-2">
								{connections.map((conn) => (
									<div
										key={conn.connection_id}
										className="flex items-center gap-3 bg-muted/50 border border-border/50 rounded-lg p-3"
									>
										<span className="text-primary text-xs font-mono">
											{conn.from_element_id === id ? "→" : "←"}
										</span>
										<Link
											to={`/elements/${conn.from_element_id === id ? conn.to_element_id : conn.from_element_id}`}
											className="text-sm text-white hover:text-primary transition-colors"
										>
											{conn.from_element_id === id
												? conn.to_element_id
												: conn.from_element_id}
										</Link>
										<span className="text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded">
											{conn.relationship_type}
										</span>
									</div>
								))}
							</div>
						) : (
							<p className="text-muted-foreground text-sm">{t("elementDetail.noConnections")}</p>
						)}
					</div>

				</div>{/* End Sidebar Column */}
			</div>{/* End Bento Grid */}

			</div>{/* End Sidebar Column */}
			</div>{/* End Bento Grid */}

			{/* Accessible Delete Confirmation Dialog */}
			<ConfirmDialog
				isOpen={showDeleteConfirm}
				title={t("elements.deleteElement")}
				message={t("elementDetail.deleteConfirmMessage")}
				confirmLabel={t("common.delete")}
				cancelLabel={t("common.cancel")}
				onConfirm={() => {
					deleteMutation.mutate();
				}}
				onCancel={() => setShowDeleteConfirm(false)}
				variant="danger"
			/>
		</div>
	);
}

function PropertyRow({
	label,
	value,
}: {
	label: string;
	value?: string | null;
}) {
	return (
		<div>
			<p className="text-xs text-muted-foreground mb-0.5">{label}</p>
			<p className="text-sm text-white">{value ?? "—"}</p>
		</div>
	);
}

export default ElementDetail;
