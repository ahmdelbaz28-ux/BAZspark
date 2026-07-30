/**
 * useApiQuery.ts — React Query hooks for the Digital Twin API
 *
 * Replaces the deprecated useState/useEffect pattern in useApi.ts with
 * @tanstack/react-query v5 for automatic deduplication, caching, and
 * revalidation.
 *
 * Migration guide (from useApi.ts):
 *   - Same hook names, same return shapes — drop-in replacement
 *   - mutations now return a promise from mutate() (via mutateAsync)
 *   - Queries are automatically deduplicated across component instances
 *   - Stale data is refetched on window focus by default (configurable)
 *
 * @see useApi.ts (DEPRECATED)
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/digitalTwinApi";
import type {
        ApiResponse,
        Connection,
        CreateDeviceInput,
        CreateProjectInput,
        Device,
        HealthStatus,
        PaginatedResponse,
        Project,
        Report,
} from "@/services/digitalTwinApi";

// ============================================================================
// Query key factory — centralised, type-safe keys for cache management
// ============================================================================

export const queryKeys = {
        health: ["health"] as const,
        projects: ["projects"] as const,
        project: (id: string) => ["project", id] as const,
        devices: (projectId: string) => ["devices", projectId] as const,
        connections: (projectId: string) => ["connections", projectId] as const,
        reports: (projectId: string) => ["reports", projectId] as const,
};

// ============================================================================
// Helpers
// ============================================================================

/** Unwrap the ApiResponse envelope — throws on success:false so React Query
 *  catches it as an error (populating error, not data). */
function unwrapData<T>(res: ApiResponse<T>): T {
        if (!res.success) {
                throw new Error(res.error ?? "Request failed");
        }
        return res.data as T;
}

/** Unwrap a paginated response and extract the items array. */
function unwrapPaginated<T>(res: ApiResponse<PaginatedResponse<T>>): T[] {
        const inner = unwrapData(res);
        return inner?.data ?? [];
}

// ============================================================================
// Query hooks
// ============================================================================

export function useHealth(): {
        data: HealthStatus | null;
        loading: boolean;
        error: string | null;
        refetch: () => void;
        connected: boolean;
} {
        const result = useQuery({
                queryKey: queryKeys.health,
                queryFn: () => api.healthCheck().then((r) => unwrapData(r)),
                staleTime: 30_000,
        });

        return {
                data: result.data ?? null,
                loading: result.isLoading,
                error: result.error?.message ?? null,
                refetch: () => void result.refetch(),
                connected: result.data?.status === "ok",
        };
}

export function useProjects(): {
        data: Project[] | null;
        loading: boolean;
        error: string | null;
        refetch: () => void;
} {
        const result = useQuery({
                queryKey: queryKeys.projects,
                queryFn: () =>
                        api.getProjects().then((r) => unwrapPaginated<Project>(r)),
                staleTime: 30_000,
        });

        return {
                data: result.data ?? null,
                loading: result.isLoading,
                error: result.error?.message ?? null,
                refetch: () => void result.refetch(),
        };
}

export function useProject(
        id: string | null,
): {
        data: Project | null;
        loading: boolean;
        error: string | null;
        refetch: () => void;
} {
        const result = useQuery({
                queryKey: id ? queryKeys.project(id) : ["project", "__skip__"],
                queryFn: () =>
                        api.getProject(id!).then((r) => unwrapData<Project>(r)),
                enabled: id !== null,
                staleTime: 30_000,
        });

        return {
                data: result.data ?? null,
                loading: result.isLoading,
                error: result.error?.message ?? null,
                refetch: () => void result.refetch(),
        };
}

export function useDevices(
        projectId: string | null,
): {
        data: Device[] | null;
        loading: boolean;
        error: string | null;
        refetch: () => void;
} {
        const result = useQuery({
                queryKey: projectId
                        ? queryKeys.devices(projectId)
                        : ["devices", "__skip__"],
                queryFn: () =>
                        api.getDevices(projectId!).then((r) => unwrapPaginated<Device>(r)),
                enabled: projectId !== null,
                staleTime: 30_000,
        });

        return {
                data: result.data ?? null,
                loading: result.isLoading,
                error: result.error?.message ?? null,
                refetch: () => void result.refetch(),
        };
}

export function useConnections(
        projectId: string | null,
): {
        data: Connection[] | null;
        loading: boolean;
        error: string | null;
        refetch: () => void;
} {
        const result = useQuery({
                queryKey: projectId
                        ? queryKeys.connections(projectId)
                        : ["connections", "__skip__"],
                queryFn: () =>
                        api
                                .getConnections(projectId!)
                                .then((r) => unwrapPaginated<Connection>(r)),
                enabled: projectId !== null,
                staleTime: 30_000,
        });

        return {
                data: result.data ?? null,
                loading: result.isLoading,
                error: result.error?.message ?? null,
                refetch: () => void result.refetch(),
        };
}

export function useReports(
        projectId: string | null,
): {
        data: Report[] | null;
        loading: boolean;
        error: string | null;
        refetch: () => void;
} {
        const result = useQuery({
                queryKey: projectId
                        ? queryKeys.reports(projectId)
                        : ["reports", "__skip__"],
                queryFn: () =>
                        api.getReports(projectId!).then((r) => unwrapPaginated<Report>(r)),
                enabled: projectId !== null,
                staleTime: 30_000,
        });

        return {
                data: result.data ?? null,
                loading: result.isLoading,
                error: result.error?.message ?? null,
                refetch: () => void result.refetch(),
        };
}

// ============================================================================
// Mutation hooks
//
// CRITICAL: Each `mutate` wraps `mutateAsync` in try/catch so that errors
// are surfaced via the returned `error` property rather than as unhandled
// rejections. The old useApi.ts hooks caught all errors and returned null;
// consumers like ProjectsPage.tsx call `await mutate()` without try/catch.
// Using mutateAsync directly would break those callers.
// ============================================================================

export function useCreateProject(): {
        mutate: (input: CreateProjectInput) => Promise<Project | null>;
        loading: boolean;
        error: string | null;
        data: Project | null;
        reset: () => void;
        refetch: () => void;
} {
        const queryClient = useQueryClient();
        const mutation = useMutation({
                mutationFn: (input: CreateProjectInput) =>
                        api.createProject(input).then((r) => unwrapData<Project>(r)),
                onSuccess: () => {
                        queryClient.invalidateQueries({ queryKey: queryKeys.projects });
                },
        });

        return {
                mutate: async (input) => {
                        try {
                                return await mutation.mutateAsync(input);
                        } catch {
                                return null;
                        }
                },
                loading: mutation.isPending,
                error: mutation.error?.message ?? null,
                data: mutation.data ?? null,
                reset: mutation.reset,
                refetch: mutation.reset,
        };
}

export function useCreateDevice(): {
        mutate: (args: {
                projectId: string;
                data: CreateDeviceInput;
        }) => Promise<Device | null>;
        loading: boolean;
        error: string | null;
        data: Device | null;
        reset: () => void;
} {
        const queryClient = useQueryClient();
        const mutation = useMutation({
                mutationFn: (args: { projectId: string; data: CreateDeviceInput }) =>
                        api
                                .createDevice(args.projectId, args.data)
                                .then((r) => unwrapData<Device>(r)),
                onSuccess: (_data, variables) => {
                        queryClient.invalidateQueries({
                                queryKey: queryKeys.devices(variables.projectId),
                        });
                },
        });

        return {
                mutate: async (args) => {
                        try {
                                return await mutation.mutateAsync(args);
                        } catch {
                                return null;
                        }
                },
                loading: mutation.isPending,
                error: mutation.error?.message ?? null,
                data: mutation.data ?? null,
                reset: mutation.reset,
        };
}

export function useDeleteProject(): {
        mutate: (id: string) => Promise<void | null>;
        loading: boolean;
        error: string | null;
        data: null;
        reset: () => void;
        refetch: () => void;
} {
        const queryClient = useQueryClient();
        const mutation = useMutation({
                mutationFn: (id: string) =>
                        api.deleteProject(id).then((r) => {
                                if (!r.success)
                                        throw new Error(r.error ?? "Failed to delete project");
                        }),
                onSuccess: () => {
                        queryClient.invalidateQueries({ queryKey: queryKeys.projects });
                },
        });

        return {
                mutate: async (id) => {
                        try {
                                return await mutation.mutateAsync(id);
                        } catch {
                                return null;
                        }
                },
                loading: mutation.isPending,
                error: mutation.error?.message ?? null,
                data: null,
                reset: mutation.reset,
                refetch: mutation.reset,
        };
}

export function useSyncProject(): {
        mutate: (projectId: string) => Promise<unknown | null>;
        loading: boolean;
        error: string | null;
        data: Record<string, unknown> | null;
        reset: () => void;
} {
        const queryClient = useQueryClient();
        const mutation = useMutation({
                mutationFn: (projectId: string) =>
                        api.syncProject(projectId).then((r) => unwrapData(r)),
                onSuccess: () => {
                        queryClient.invalidateQueries({ queryKey: queryKeys.projects });
                },
        });

        return {
                mutate: async (projectId) => {
                        try {
                                return await mutation.mutateAsync(projectId);
                        } catch {
                                return null;
                        }
                },
                loading: mutation.isPending,
                error: mutation.error?.message ?? null,
                data: (mutation.data ?? null) as Record<string, unknown> | null,
                reset: mutation.reset,
        };
}

export function useGenerateReport(): {
        mutate: (args: {
                projectId: string;
                data: { type: string; execution_params: Record<string, unknown> };
        }) => Promise<Report | null>;
        loading: boolean;
        error: string | null;
        data: Report | null;
        reset: () => void;
} {
        const queryClient = useQueryClient();
        const mutation = useMutation({
                mutationFn: (args: {
                        projectId: string;
                        data: { type: string; execution_params: Record<string, unknown> };
                }) =>
                        api
                                .generateReport(args.projectId, args.data)
                                .then((r) => unwrapData<Report>(r)),
                onSuccess: (_data, variables) => {
                        queryClient.invalidateQueries({
                                queryKey: queryKeys.reports(variables.projectId),
                        });
                },
        });

        return {
                mutate: async (args) => {
                        try {
                                return await mutation.mutateAsync(args);
                        } catch {
                                return null;
                        }
                },
                loading: mutation.isPending,
                error: mutation.error?.message ?? null,
                data: mutation.data ?? null,
                reset: mutation.reset,
        };
}
