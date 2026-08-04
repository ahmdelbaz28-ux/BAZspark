
/**
 * ProjectsPage.tsx - Project management with full CRUD + Device & Connection creation
 */

import {
        Clock,
        Eye,
        Folder,
        FolderPlus,
        Link as LinkIcon,
        Loader2,
        RefreshCw,
        Trash2,
        User,
        Download,
        FileCode2,
        Box,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
        Card,
        CardContent,
        CardDescription,
        CardHeader,
        CardTitle,
} from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
        Select,
        SelectContent,
        SelectItem,
        SelectTrigger,
        SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
        useCreateProject,
        useDeleteProject,
        useProjects,
        useSyncProject,
} from "@/hooks/useApiQuery";
import type { Project } from "@/services/digitalTwinApi";
import { DEVICE_CATEGORIES, getDevicesByCategory } from "@/types/deviceLibrary";
import { apiCall } from "@/services/fullApi";

// ============================================================================
// Connection types for the dropdown
// ============================================================================
const _CONNECTION_TYPES = [
        "power",
        "signal",
        "data",
        "fire_alarm_loop",
        "nac_circuit",
        "poe",
        "cable",
] as const;

const _CABLE_SIZES = [
        "1.5mm²",
        "2.5mm²",
        "4mm²",
        "6mm²",
        "10mm²",
        "16mm²",
        "25mm²",
        "35mm²",
        "50mm²",
        "70mm²",
        "95mm²",
        "120mm²",
] as const;

// ============================================================================
// ProjectsPage Component
// ============================================================================

export function ProjectsPage() {
        const { t } = useTranslation();
        const {
                data: projects,
                loading: projectsLoading,
                error: projectsError,
                refetch,
        } = useProjects();
        const { mutate: deleteProject, loading: deleting } = useDeleteProject();
        const { mutate: syncProject, loading: syncing } = useSyncProject();
        const { mutate: createProject } = useCreateProject();
        const [newProject, setNewProject] = useState({ name: "", description: "" });
        const [creating, setCreating] = useState(false);
        const [showCreateForm, setShowCreateForm] = useState(false);
        const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
        const [syncTarget, setSyncTarget] = useState<Project | null>(null);
        const [statusFilter, setStatusFilter] = useState("all");

        const filteredProjects = useMemo(() => {
                if (!projects) return [];
                return projects.filter(
                        (project) => statusFilter === "all" || project.status === statusFilter,
                );
        }, [projects, statusFilter]);

        const handleCreate = async () => {
                if (!newProject.name.trim()) return;

                setCreating(true);
                const result = await createProject(newProject);
                if (result) {
                        setNewProject({ name: "", description: "" });
                        setShowCreateForm(false);
                        refetch();
                        toast.success("Project created successfully.");
                } else {
                        // V250 FIX: Show error toast on failure (was silent)
                        toast.error("Failed to create project. Please try again.");
                }
                setCreating(false);
        };

        const handleDelete = async () => {
                if (!deleteTarget) return;

                const result = await deleteProject(deleteTarget.id);
                if (result) {
                        setDeleteTarget(null);
                        refetch();
                        toast.success("Project deleted.");
                } else {
                        // V250 FIX: Show error toast on failure (was silent)
                        toast.error("Failed to delete project. Please try again.");
                        setDeleteTarget(null);
                }
        };

        const handleSync = async () => {
                if (!syncTarget) return;

                const result = await syncProject(syncTarget.id);
                if (result) {
                        setSyncTarget(null);
                        refetch();
                        toast.success("Project synced successfully.");
                } else {
                        // V250 FIX: Show error toast on failure (was silent)
                        toast.error("Failed to sync project. Please try again.");
                        setSyncTarget(null);
                }
        };

        return (
                <div className="flex-1 overflow-auto" aria-label={t("projects.title")}>
                        <div className="p-6 max-w-4xl mx-auto space-y-5">
                                {/* FACP Page Header */}
                                <div className="facp-page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                                        <div>
                                                <h1 className="facp-page-title">{t("projects.title")}</h1>
                                                <p className="facp-page-subtitle">{t("projects.subtitle")}</p>
                                        </div>
                                        <button
                                                type="button"
                                                className="facp-btn facp-btn--primary"
                                                data-testid="create-project-btn"
                                                onClick={() => setShowCreateForm(true)}
                                        >
                                                <FolderPlus aria-hidden="true" className="h-4 w-4" />
                                                {t("projects.newProject")}
                                        </button>
                                </div>

                                {/* Create Project Form */}
                                {showCreateForm && (
                                        <Card className="border-border bg-card stagger-card">
                                                <CardHeader>
                                                        <CardTitle className="text-lg text-foreground">
                                                                {t("projects.createProject")}
                                                        </CardTitle>
                                                </CardHeader>
                                                <CardContent className="space-y-4">
                                                        <div className="space-y-2">
                                                                <Label className="text-foreground/90">
                                                                        {t("projects.projectName")}
                                                                </Label>
                                                                <Input
                                                                        value={newProject.name}
                                                                        onChange={(e) =>
                                                                                setNewProject((p) => ({ ...p, name: e.target.value }))
                                                                        }
                                                                        placeholder={t("projects.projectName")}
                                                                        className="bg-card border-border text-foreground stagger-card"
                                                                />
                                                        </div>
                                                        <div className="space-y-2">
                                                                <Label className="text-foreground/90">
                                                                        {t("projects.description")}
                                                                </Label>
                                                                <Input
                                                                        value={newProject.description}
                                                                        onChange={(e) =>
                                                                                setNewProject((p) => ({
                                                                                        ...p,
                                                                                        description: e.target.value,
                                                                                }))
                                                                        }
                                                                        placeholder={t("projects.description")}
                                                                        className="bg-card border-border text-foreground stagger-card"
                                                                />
                                                        </div>
                                                        <div className="flex justify-end gap-3 pt-2">
                                                                <Button
                                                                        variant="outline"
                                                                        className="border-border text-foreground/90"
                                                                        onClick={() => {
                                                                                setShowCreateForm(false);
                                                                                setNewProject({ name: "", description: "" });
                                                                        }}
                                                                >
                                                                        {t("common.cancel")}
                                                                </Button>
                                                                                <Button
                                                                                        className="bg-primary hover:bg-primary/90 text-primary-foreground border-none"
                                                                                        onClick={handleCreate}
                                                                                        disabled={creating || !newProject.name.trim()}
                                                                                >
                                                                        {creating ? (
                                                                                <>
                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 mr-1 animate-spin" />
                                                                                        {t("common.creating")}
                                                                                </>
                                                                        ) : (
                                                                                t("projects.createProject")
                                                                        )}
                                                                </Button>
                                                        </div>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Filter Bar */}
                                <div className="facp-filter-bar">
                                        <select
                                                value={statusFilter}
                                                onChange={(e) => setStatusFilter(e.target.value)}
                                                className="facp-select"
                                                style={{ minWidth: "160px", flex: "0 0 auto" }}
                                                aria-label={t("projects.allStatuses", "Filter by status")}
                                        >
                                                <option value="all">{t("projects.allStatuses")}</option>
                                                <option value="active">{t("projects.active")}</option>
                                                <option value="inactive">{t("projects.inactive")}</option>
                                                <option value="draft">{t("projects.draft")}</option>
                                                <option value="archived">{t("projects.archived")}</option>
                                        </select>
                                        <button
                                                type="button"
                                                className="facp-btn facp-btn--ghost"
                                                onClick={() => refetch()}
                                                aria-label={t("projects.refresh")}
                                        >
                                                <RefreshCw aria-hidden="true" className="h-4 w-4" />
                                                {t("projects.refresh")}
                                        </button>
                                </div>

                                {/* Error */}
                                {projectsError && (
                                        <Card className="border-danger/30 bg-slate-500/5">
                                                <CardContent className="p-4">
                                                        <p className="text-danger">
                                                                {t("projects.errorLoading")}: {projectsError}
                                                        </p>
                                                </CardContent>
                                        </Card>
                                )}

                                {/* Loading State with Skeletons */}
                                {projectsLoading && (
                                        <div className="space-y-4">
                                                {["skeleton-0", "skeleton-1", "skeleton-2"].map((id) => (
                                                        <Card key={id} className="border-border bg-card stagger-card">
                                                                <CardHeader className="pb-3">
                                                                        <div className="flex items-center justify-between">
                                                                                <div>
                                                                                        <Skeleton className="h-5 w-48 bg-secondary" />
                                                                                        <Skeleton className="h-4 w-32 bg-secondary mt-2" />
                                                                                </div>
                                                                                <Skeleton className="h-9 w-24 rounded" />
                                                                        </div>
                                                                </CardHeader>
                                                                <CardContent>
                                                                        <div className="flex items-center justify-between">
                                                                                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                                                                                        <Skeleton className="h-4 w-24" />
                                                                                        <Skeleton className="h-4 w-20" />
                                                                                        <Skeleton className="h-4 w-16" />
                                                                                </div>
                                                                                <div className="flex gap-2">
                                                                                        <Skeleton className="h-8 w-8 rounded" />
                                                                                        <Skeleton className="h-8 w-8 rounded" />
                                                                                        <Skeleton className="h-8 w-8 rounded" />
                                                                                </div>
                                                                        </div>
                                                                </CardContent>
                                                        </Card>
                                                ))}
                                        </div>
                                )}

                                {/* Empty State */}
                                {!projectsLoading &&
                                        (!filteredProjects || filteredProjects.length === 0) && (
                                                <div className="py-12">
                                                        <EmptyState
                                                                icon={<Folder aria-hidden="true" className="h-12 w-12" />}
                                                                title={t("projects.noProjects")}
                                                                description={t("projects.createFirst")}
                                                                action={{
                                                                        label: t("projects.newProject"),
                                                                        onClick: () => setShowCreateForm(true),
                                                                }}
                                                        />
                                                </div>
                                        )}

                                {/* Projects List */}
                                {!projectsLoading &&
                                        filteredProjects &&
                                        filteredProjects.length > 0 && (
                                                <div className="space-y-3">
                                                        {filteredProjects.map((project: Project) => {
                                                                const cardMod =
                                                                        project.status === "active" ? "facp-card--active"
                                                                        : project.status === "draft" ? "facp-card--warning"
                                                                        : project.status === "archived" ? "facp-card--neutral"
                                                                        : "";
                                                                const badgeMod =
                                                                        project.status === "active" ? "facp-badge--active"
                                                                        : project.status === "draft" ? "facp-badge--pending"
                                                                        : project.status === "archived" ? "facp-badge--neutral"
                                                                        : "facp-badge--inactive";
                                                                return (
                                                                <div key={project.id} className={`facp-card ${cardMod}`}>
                                                                        {/* Card Header */}
                                                                        <div className="flex items-start justify-between gap-3">
                                                                                <div className="flex-1 min-w-0">
                                                                                        <div className="facp-card-id">
                                                                                                PRJ-{project.id.slice(0, 8).toUpperCase()}
                                                                                        </div>
                                                                                        <h2 className="facp-card-title truncate">{project.name}</h2>
                                                                                        <p className="facp-card-meta">
                                                                                                {project.description || t("common.noData")}
                                                                                        </p>
                                                                                </div>
                                                                                <span className={`facp-badge ${badgeMod} flex-shrink-0`}>
                                                                                        {project.status === "active" ? t("projects.active")
                                                                                                : project.status === "draft" ? t("projects.draft") // NOSONAR: typescript:S3358
                                                                                                : project.status === "archived" ? t("projects.archived") // NOSONAR: typescript:S3358
                                                                                                : t("projects.inactive")}
                                                                                </span>
                                                                        </div>

                                                                        {/* Meta row */}
                                                                        <div className="facp-card-actions" style={{ flexWrap: "wrap" }}>
                                                                                <div className="flex flex-wrap items-center gap-4 flex-1" style={{ fontFamily: "var(--font-data)", fontSize: "0.7rem", color: "var(--color-steel)", letterSpacing: "0.04em" }}>
                                                                                        <span className="flex items-center gap-1">
                                                                                                <User aria-hidden="true" className="h-3.5 w-3.5" />
                                                                                                {project.author}
                                                                                        </span>
                                                                                        <span className="flex items-center gap-1">
                                                                                                <Clock aria-hidden="true" className="h-3.5 w-3.5" />
                                                                                                {new Date(project.createdAt).toLocaleDateString()}
                                                                                        </span>
                                                                                        <span style={{ color: "var(--color-bone)" }}>
                                                                                                {project.deviceCount} devices
                                                                                        </span>
                                                                                        <span>
                                                                                                {project.connectionCount} connections
                                                                                        </span>
                                                                                </div>
                                                                                <div className="flex items-center gap-1.5 flex-shrink-0">
                                                                                        <button
                                                                                                type="button"
                                                                                                className="facp-btn facp-btn--ghost facp-btn--icon"
                                                                                                onClick={() => setSyncTarget(project)}
                                                                                                title={t("projects.sync")}
                                                                                                aria-label={`Sync ${project.name}`}
                                                                                        >
                                                                                                {syncing && syncTarget?.id === project.id ? (
                                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                                                                                                ) : (
                                                                                                        <RefreshCw aria-hidden="true" className="h-4 w-4" />
                                                                                                )}
                                                                                        </button>
                                                                                        <button
                                                                                                type="button"
                                                                                                className="facp-btn facp-btn--ghost facp-btn--icon"
                                                                                                onClick={() => { window.location.hash = `/projects/${project.id}`; }}
                                                                                                title={t("common.view")}
                                                                                                aria-label={`View ${project.name}`}
                                                                                        >
                                                                                                <Eye aria-hidden="true" className="h-4 w-4" />
                                                                                        </button>
                                                                                        <button
                                                                                                type="button"
                                                                                                className="facp-btn facp-btn--danger facp-btn--icon"
                                                                                                onClick={() => setDeleteTarget(project)}
                                                                                                title={t("common.delete")}
                                                                                                aria-label={`Delete ${project.name}`}
                                                                                        >
                                                                                                <Trash2 aria-hidden="true" className="h-4 w-4" />
                                                                                        </button>
                                                                                </div>
                                                                        </div>

                                                                        {/* Export row */}
                                                                        <div className="flex flex-wrap gap-1.5" style={{ borderTop: "1px solid rgba(90,103,112,0.2)", paddingTop: "0.75rem", marginTop: "0.5rem" }}>
                                                                                <button
                                                                                        type="button"
                                                                                        className="facp-btn facp-btn--ghost"
                                                                                        style={{ fontSize: "0.65rem" }}
                                                                                        onClick={async () => {
                                                                                                try {
                                                                                                        await apiCall(`/projects/${project.id}/export/dxf`);
                                                                                                        toast.success("DXF exported");
                                                                                                } catch (err) {
                                                                                                        toast.error(`DXF export failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                                                }
                                                                                        }}
                                                                                >
                                                                                        <FileCode2 aria-hidden="true" className="h-3.5 w-3.5" />
                                                                                        DXF
                                                                                </button>
                                                                                <button
                                                                                        type="button"
                                                                                        className="facp-btn facp-btn--ghost"
                                                                                        style={{ fontSize: "0.65rem" }}
                                                                                        onClick={async () => {
                                                                                                try {
                                                                                                        await apiCall(`/projects/${project.id}/export/revit`);
                                                                                                        toast.success("Revit exported");
                                                                                                } catch (err) {
                                                                                                        toast.error(`Revit export failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                                                }
                                                                                        }}
                                                                                >
                                                                                        <Download aria-hidden="true" className="h-3.5 w-3.5" />
                                                                                        Revit
                                                                                </button>
                                                                                <button
                                                                                        type="button"
                                                                                        className="facp-btn facp-btn--ghost"
                                                                                        style={{ fontSize: "0.65rem" }}
                                                                                        onClick={async () => {
                                                                                                try {
                                                                                                        await apiCall(`/projects/${project.id}/export/ifc`);
                                                                                                        toast.success("IFC exported");
                                                                                                } catch (err) {
                                                                                                        toast.error(`IFC export failed: ${err instanceof Error ? err.message : "Unknown"}`);
                                                                                                }
                                                                                        }}
                                                                                >
                                                                                        <Box aria-hidden="true" className="h-3.5 w-3.5" />
                                                                                        IFC
                                                                                </button>
                                                                        </div>
                                                                </div>
                                                                );
                                                        })}

                                                </div>
                                        )}


                                {/* Sync Confirmation Modal */}
                                {syncTarget && (
                                        <dialog className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" open aria-modal="true" aria-label={t("projects.sync")}>
                                                <div className="bg-card border border-border rounded-xl max-w-md w-full p-6 shadow-2xl stagger-card">
                                                        <h3 className="text-lg font-semibold text-foreground">
                                                                {t("projects.sync")}
                                                        </h3>
                                                        <p className="text-muted-foreground mt-2">
                                                                {t("projects.syncConfirm", { name: syncTarget.name })}
                                                        </p>
                                                        <div className="flex justify-end gap-3 mt-6">
                                                                <Button
                                                                        variant="outline"
                                                                        className="border-border text-foreground/90"
                                                                        onClick={() => setSyncTarget(null)}
                                                                >
                                                                        {t("common.cancel")}
                                                                </Button>
                                                                <Button
                                                                        className="bg-primary hover:bg-primary/90 text-primary-foreground border-none"
                                                                        onClick={handleSync}
                                                                        disabled={syncing}
                                                                >
                                                                        {syncing ? (
                                                                                <>
                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 mr-1 animate-spin" />
                                                                                        {t("projects.syncing")}
                                                                                </>
                                                                        ) : (
                                                                                t("projects.sync")
                                                                        )}
                                                                </Button>
                                                        </div>
                                                </div>
                                        </dialog>
                                )}

                                {/* Delete Confirmation Modal */}
                                {deleteTarget && (
                                        <dialog className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" open aria-modal="true" aria-label={t("projects.deleteProject")}>
                                                <div className="bg-card border border-border rounded-xl max-w-md w-full p-6 shadow-2xl stagger-card">
                                                        <h3 className="text-lg font-semibold text-foreground">
                                                                {t("projects.deleteProject")}
                                                        </h3>
                                                        <p className="text-muted-foreground mt-2">
                                                                {t("projects.deleteConfirmMessage", {
                                                                        name: deleteTarget.name,
                                                                })}
                                                        </p>
                                                        <div className="flex justify-end gap-3 mt-6">
                                                                <Button
                                                                        variant="outline"
                                                                        className="border-border text-foreground/90"
                                                                        onClick={() => setDeleteTarget(null)}
                                                                >
                                                                        {t("common.cancel")}
                                                                </Button>
                                                                <Button
                                                                        className="bg-destructive hover:bg-destructive/90 text-destructive-foreground border-none"
                                                                        onClick={handleDelete}
                                                                        disabled={deleting}
                                                                >
                                                                        {deleting ? (
                                                                                <>
                                                                                        <Loader2 aria-hidden="true" className="h-4 w-4 mr-1 animate-spin" />
                                                                                        {t("common.deleting")}
                                                                                </>
                                                                        ) : (
                                                                                t("projects.deleteProject")
                                                                        )}
                                                                </Button>
                                                        </div>
                                                </div>
                                        </dialog>
                                )}
                        </div>
                </div>
        );
}

// ============================================================================
// Form state types & defaults
// ============================================================================

interface DeviceFormState {
        category: string;
        type: string;
        name: string;
        x: number;
        y: number;
        z: number;
        voltage: number;
        current: number;
        load: number;
        loadUnit: "A" | "mA" | "W"; // BUG-30 FIX: Track load unit
}

function _getDefaultDeviceForm(): DeviceFormState {
        const firstCat = DEVICE_CATEGORIES[0];
        const firstDevice = getDevicesByCategory(firstCat.id)[0];
        return {
                category: firstCat.id,
                type: firstDevice?.id || "",
                name: firstDevice?.name || "",
                x: 0,
                y: 0,
                z: 0,
                voltage: firstDevice?.defaultVoltage || 24,
                current: firstDevice?.defaultCurrent || 0,
                load: firstDevice?.defaultLoad || 0,
                loadUnit: "A", // BUG-30 FIX: Default to Amperes
        };
}

interface ConnectionFormState {
        fromDeviceId: string;
        toDeviceId: string;
        type: string;
        cableSize: string;
        length: number;
}

function _getDefaultConnectionForm(): ConnectionFormState {
        return {
                fromDeviceId: "",
                toDeviceId: "",
                type: "",
                cableSize: "",
                length: 0,
        };
}
