/**
 * ProjectContext.tsx — Canonical Project & Model Context Provider (Phase 8 Gate 5).
 *
 * Establishes a single, authoritative project context boundary for the workstation:
 * - Synchronizes active project with URL search param (?project=...), persisted storage, or authoritative backend query.
 * - Resolves active project metadata, revision, and device count from GET /api/v1/projects.
 * - Provides clean context propagation across AI Control Center, Engineering Workspace, Digital Twin, Reports, and Review.
 * - Graceful fallback when rendered in isolated test harnesses without a provider.
 */

import type React from "react";
import { createContext, useContext, useMemo, useState } from "react";
import { useSearchParams } from "react-router";
import { useProjects } from "@/hooks/useApiQuery";
import type { Project } from "@/services/digitalTwinApi";

export interface ProjectContextValue {
	activeProjectId: string;
	activeProject: Project | null;
	projects: Project[];
	loading: boolean;
	error: string | null;
	setActiveProjectId: (id: string) => void;
	refetchProjects: () => void;
}

const STORAGE_KEY = "bazspark_active_project_id";
const FALLBACK_PROJECT_ID = "default_project";

const ProjectContext = createContext<ProjectContextValue | null>(null);

export function ProjectProvider({ children }: { children: React.ReactNode }) {
	const [searchParams] = useSearchParams();
	const urlProject = searchParams.get("project");
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

	// Resolve active project ID: URL param -> user selected ID -> first available backend project -> fallback
	const activeProjectId = useMemo(() => {
		const candidateId = urlProject || userSelectedId;
		if (candidateId && projects.some((p) => p.id === candidateId)) {
			return candidateId;
		}
		if (projects.length > 0) {
			return projects[0].id;
		}
		return candidateId || FALLBACK_PROJECT_ID;
	}, [urlProject, userSelectedId, projects]);

	const activeProject = useMemo(() => {
		return projects.find((p) => p.id === activeProjectId) || null;
	}, [projects, activeProjectId]);

	const setActiveProjectId = (id: string) => {
		setUserSelectedId(id);
		try {
			localStorage.setItem(STORAGE_KEY, id);
		} catch {
			// ignore storage errors
		}
	};

	const value = useMemo(
		() => ({
			activeProjectId,
			activeProject,
			projects,
			loading,
			error,
			setActiveProjectId,
			refetchProjects: refetch,
		}),
		[activeProjectId, activeProject, projects, loading, error, refetch],
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
		// Graceful fallback for isolated test harnesses outside ProjectProvider
		return {
			activeProjectId: FALLBACK_PROJECT_ID,
			activeProject: null,
			projects: [],
			loading: false,
			error: null,
			setActiveProjectId: () => {},
			refetchProjects: () => {},
		};
	}
	return context;
}
