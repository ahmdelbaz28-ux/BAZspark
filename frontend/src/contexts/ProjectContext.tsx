/**
 * ProjectContext.tsx — Canonical Project, Model & Entity Context Provider (Phase 8 Gate 5).
 *
 * Establishes the authoritative workstation context chain:
 * activeProjectId -> activeModelId -> activeRevision -> selectedEntityId -> capability execution
 *
 * Invariants:
 * 1. Project is the canonical aggregate root; Model ID is structurally bound to Project ID.
 * 2. Revision is the authoritative version token for OCC write-integrity checks.
 * 3. Selected Entity context is navigational/selection metadata (not frontend source-of-truth).
 * 4. Pure reactive resolution: URL search params (?project=, ?element=, ?device=) > persisted state > backend list > empty.
 * 5. Zero hardcoded project fallbacks.
 */

import type React from "react";
import { createContext, useContext, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { useProjects } from "@/hooks/useApiQuery";
import type { Project } from "@/services/digitalTwinApi";

export interface ProjectContextValue {
	activeProjectId: string;
	activeProject: Project | null;
	activeModelId: string;
	activeRevision: number;
	selectedEntityId: string | null;
	selectedEntityType: "device" | "element" | "circuit" | null;
	projects: Project[];
	loading: boolean;
	error: string | null;
	setActiveProjectId: (id: string) => void;
	setSelectedEntity: (id: string | null, type?: "device" | "element" | "circuit" | null) => void;
	refetchProjects: () => void;
}

const STORAGE_KEY = "bazspark_active_project_id";

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: React.ReactNode }) {
	const [searchParams] = useSearchParams();
	const urlProject = searchParams.get("project");
	const urlElement = searchParams.get("element");
	const urlDevice = searchParams.get("device");
	const urlEntity = urlElement || urlDevice || searchParams.get("entity");

	const { data: projectsData, loading, error, refetch } = useProjects();
	const projects = useMemo(() => projectsData || [], [projectsData]);

	const [userSelectedId, setUserSelectedId] = useState<string>(() => {
		try {
			const saved = localStorage.getItem(STORAGE_KEY);
			if (saved) return saved;
		} catch {
			// ignore storage errors
		}
		return "";
	});

	const [selectedEntityId, setSelectedEntityId] = useState<string | null>(urlEntity || null);
	const [selectedEntityType, setSelectedEntityType] = useState<"device" | "element" | "circuit" | null>(
		urlElement ? "element" : urlDevice ? "device" : null,
	);

	// Resolve active project ID: URL param -> user selected ID -> first available backend project -> empty string
	const activeProjectId = useMemo(() => {
		const candidateId = urlProject || userSelectedId;
		if (candidateId && projects.some((p) => p.id === candidateId)) {
			return candidateId;
		}
		if (projects.length > 0) {
			return projects[0].id;
		}
		return candidateId || "";
	}, [urlProject, userSelectedId, projects]);

	const activeProject = useMemo(() => {
		return projects.find((p) => p.id === activeProjectId) || null;
	}, [projects, activeProjectId]);

	// Canonical Model / Digital Twin Identity: Read directly from authoritative backend projection
	const activeModelId = useMemo(() => {
		if (activeProject) {
			if (activeProject.modelId) return activeProject.modelId;
			throw new Error(`Project '${activeProject.id}' is missing canonical modelId from backend`);
		}
		return "";
	}, [activeProject]);

	// Authoritative server-derived revision token (OCC tracking from backend project_revisions)
	const activeRevision = useMemo(() => {
		if (activeProject) {
			if (typeof activeProject.revision === "number") {
				return activeProject.revision;
			}
			throw new Error(`Project '${activeProject.id}' is missing canonical revision from backend`);
		}
		return 0;
	}, [activeProject]);

	const setActiveProjectId = (id: string) => {
		setUserSelectedId(id);
		try {
			localStorage.setItem(STORAGE_KEY, id);
		} catch {
			// ignore storage errors
		}
	};

	const setSelectedEntity = (id: string | null, type: "device" | "element" | "circuit" | null = null) => {
		setSelectedEntityId(id);
		setSelectedEntityType(type);
	};

	const value = useMemo<ProjectContextValue>(
		() => ({
			activeProjectId,
			activeProject,
			activeModelId,
			activeRevision,
			selectedEntityId: urlEntity || selectedEntityId,
			selectedEntityType: urlElement ? "element" : urlDevice ? "device" : selectedEntityType,
			projects,
			loading,
			error,
			setActiveProjectId,
			setSelectedEntity,
			refetchProjects: refetch,
		}),
		[
			activeProjectId,
			activeProject,
			activeModelId,
			activeRevision,
			urlEntity,
			urlElement,
			urlDevice,
			selectedEntityId,
			selectedEntityType,
			projects,
			loading,
			error,
			refetch,
		],
	);

	return (
		<ProjectContext.Provider value={value}>
			{children}
		</ProjectContext.Provider>
	);
}

export function useActiveProject(): ProjectContextValue {
	const context = useContext(ProjectContext);
	if (!context) {
		// Fallback for isolated test harnesses outside ProjectProvider
		return {
			activeProjectId: "",
			activeProject: null,
			activeModelId: "",
			activeRevision: 0,
			selectedEntityId: null,
			selectedEntityType: null,
			projects: [],
			loading: false,
			error: null,
			setActiveProjectId: () => {},
			setSelectedEntity: () => {},
			refetchProjects: () => {},
		};
	}
	return context;
}
