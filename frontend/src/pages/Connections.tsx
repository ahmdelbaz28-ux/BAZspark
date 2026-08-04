
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import type { ConnectionCreate } from "@/types";

function Connections() {
        const { t } = useTranslation();
        const queryClient = useQueryClient();
        const [elementFilter, setElementFilter] = useState("");
        const [showCreateModal, setShowCreateModal] = useState(false);
        const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
        const [editTarget, setEditTarget] = useState<any | null>(null);

        const {
                data: connectionsData,
                isLoading,
                error,
        } = useQuery({
                queryKey: ["connections", elementFilter],
                queryFn: () =>
                        api.getConnections({ element_id: elementFilter || undefined }),
        });

        const connections = connectionsData?.items ?? [];

        const deleteMutation = useMutation({
                mutationFn: (id: string) => api.deleteConnection(id),
                onSuccess: () => {
                        queryClient.invalidateQueries({ queryKey: ["connections"] });
                        setDeleteTarget(null);
                },
        });

        const updateMutation = useMutation({
                mutationFn: async ({ id, data }: { id: string, data: any }) => {
                        const res = await fetch(`/api/v1/connections/${id}`, {
                                method: 'PUT',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(data),
                        });
                        if (!res.ok) throw new Error("Update failed");
                        return res.json();
                },
                onSuccess: () => {
                        queryClient.invalidateQueries({ queryKey: ["connections"] });
                        setEditTarget(null);
                },
        });

        return (
                <div className="space-y-6" aria-label={t("connectionsPage.title")}>
                        {/* Header */}
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                                <h1 className="text-2xl font-bold text-foreground">
                                        {t("connectionsPage.title")}
                                </h1>
                                <p className="text-muted-foreground text-sm mt-1">
                                        {connectionsData
                                                ? t("connectionsPage.totalConnections", {
                                                                count: connectionsData.total,
                                                        })
                                                : t("common.loading")}
                                </p>
                        </div>
                        <Button
                                onClick={() => setShowCreateModal(true)}
                                className="gap-2"
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
                                        <line x1="12" y1="5" x2="12" y2="19" />
                                        <line x1="5" y1="12" x2="19" y2="12" />
                                </svg>
                                {t("connectionsPage.createConnection")}
                        </Button>
                        </div>

                {/* Filter */}
                <div className="flex flex-wrap items-center gap-3">
                        <Input
                                type="text"
                                value={elementFilter}
                                onChange={(e) => setElementFilter(e.target.value)}
                                placeholder={t("connectionsPage.elementFilter")}
                                className="w-full sm:w-72"
                        />
                        {elementFilter && (
                                <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setElementFilter("")}
                                        className="text-muted-foreground hover:text-foreground"
                                >
                                        ✕ {t("common.clear")}
                                </Button>
                        )}
                </div>

                        {/* Error */}
                        {error && (
                                <div className="bg-slate-500/10 border border-slate-500/20 rounded-lg p-4">
                                        <p className="text-danger text-sm">
                                                {t("connectionsPage.failedToLoad")}
                                        </p>
                                </div>
                        )}

                        {/* Loading */}
                        {isLoading && (
                                <div className="flex items-center justify-center py-12">
                                        <div className="w-8 h-8 border-2 border-border border-t-primary rounded-full animate-spin" />
                                </div>
                        )}

                        {/* Table */}
                        {connectionsData && !isLoading && (
                                <div className="bg-card border border-border rounded-md overflow-hidden">
                                        <div className="overflow-x-auto">
                                                <table
                                                        className="w-full text-sm"
                                                        aria-label={t("connectionsPage.title")}
                                                >
                                                        <thead>
                                                                <tr className="border-b border-border bg-muted/50">
                                                                        <th
                                                                                scope="col"
                                                                                className="text-left text-muted-foreground font-medium px-4 py-3"
                                                                        >
                                                                                {t("connectionsPage.sourceElement")}
                                                                        </th>
                                                                        <th
                                                                                scope="col"
                                                                                className="text-left text-muted-foreground font-medium px-4 py-3"
                                                                        >
                                                                                {t("connectionsPage.targetElement")}
                                                                        </th>
                                                                        <th
                                                                                scope="col"
                                                                                className="text-left text-muted-foreground font-medium px-4 py-3"
                                                                        >
                                                                                {t("connectionsPage.relationshipType")}
                                                                        </th>
                                                                        <th
                                                                                scope="col"
                                                                                className="text-left text-muted-foreground font-medium px-4 py-3"
                                                                        >
                                                                                {t("common.active")}
                                                                        </th>
                                                                        <th
                                                                                scope="col"
                                                                                className="text-right text-muted-foreground font-medium px-4 py-3"
                                                                        >
                                                                                {t("connectionsPage.actions")}
                                                                        </th>
                                                                </tr>
                                                        </thead>
                                                        <tbody>
                                                                {connections.length === 0 ? (
                                                                        <tr>
                                                                                <td colSpan={5} className="py-8">
                                                                                        <EmptyState
                                                                                                icon={
                                                                                                        <svg
                                                                                                                width="48"
                                                                                                                height="48"
                                                                                                                viewBox="0 0 24 24"
                                                                                                                fill="none"
                                                                                                                stroke="currentColor"
                                                                                                                strokeWidth="1.5"
                                                                                                                className="h-12 w-12 text-muted-foreground/70"
                                                                                                        >
                                                                                                                <path d="M10 19h4m-2-17V4a2 2 0 00-2 2v3m6 12V7a4 4 0 00-8 0v12" />
                                                                                                        </svg>
                                                                                                }
                                                                                                title={t("connectionsPage.noConnections")}
                                                                                                description={t("connectionsPage.createFirst")}
                                                                                        />
                                                                                </td>
                                                                        </tr>
                                                                ) : (
                                                                        connections.map((conn) => (
                                                                                <tr
                                                                                        key={conn.connection_id}
                                                                                        className="border-b border-border/50 hover:bg-secondary/30 transition-colors"
                                                                                >
                                                                                        <td className="px-4 py-3">
                                                                                                <Link
                                                                                                        to={`/elements/${conn.from_element_id}`}
                                                                                                        className="text-primary hover:text-cyan-300 text-xs font-mono"
                                                                                                >
                                                                                                        {conn.from_element_id.slice(0, 12)}…
                                                                                                </Link>
                                                                                        </td>
                                                                                        <td className="px-4 py-3">
                                                                                                <Link
                                                                                                        to={`/elements/${conn.to_element_id}`}
                                                                                                        className="text-primary hover:text-cyan-300 text-xs font-mono"
                                                                                                >
                                                                                                        {conn.to_element_id.slice(0, 12)}…
                                                                                                </Link>
                                                                                        </td>
                                                                                        <td className="px-4 py-3">
                                                                                                <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-secondary text-foreground/90">
                                                                                                        {conn.relationship_type}
                                                                                                </span>
                                                                                        </td>
                                                                                        <td className="px-4 py-3">
                                                                                                {conn.is_parametric ? (
                                                                                                        <span className="text-success text-xs">Yes</span>
                                                                                                ) : (
                                                                                                        <span className="text-muted-foreground text-xs">No</span>
                                                                                                )}
                                                                                        </td>
                                                                                        <td className="px-4 py-3 text-right">
                                                                                                <div className="flex items-center justify-end gap-2">
                                                                                                        <button type="button"
                                                                                                                onClick={() => setEditTarget(conn)}
                                                                                                                className="text-muted-foreground hover:text-primary transition-colors"
                                                                                                                title="Edit"
                                                                                                        >
                                                                                                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                                                                                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                                                                                                                </svg>
                                                                                                        </button>
                                                                                                        <button type="button"
                                                                                                                onClick={() => setDeleteTarget(conn.connection_id)}
                                                                                                                className="text-muted-foreground hover:text-danger transition-colors"
                                                                                                                title="Delete"
                                                                                                        >
                                                                                                                <svg
                                                                                                                        width="14"
                                                                                                                        height="14"
                                                                                                                        viewBox="0 0 24 24"
                                                                                                                        fill="none"
                                                                                                                        stroke="currentColor"
                                                                                                                        strokeWidth="2"
                                                                                                                        strokeLinecap="round"
                                                                                                                        strokeLinejoin="round"
                                                                                                                >
                                                                                                                        <polyline points="3 6 5 6 21 6" />
                                                                                                                        <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
                                                                                                                </svg>
                                                                                                        </button>
                                                                                                </div>
                                                                                        </td>
                                                                                </tr>
                                                                        ))
                                                                )}
                                                        </tbody>
                                                </table>
                                        </div>
                                </div>
                        )}

                        {/* Create Modal */}
                        {showCreateModal && (
                                <CreateConnectionModal
                                        onClose={() => setShowCreateModal(false)}
                                        onSuccess={() => {
                                                setShowCreateModal(false);
                                                queryClient.invalidateQueries({ queryKey: ["connections"] });
                                        }}
                                />
                        )}

                {/* Delete Confirmation */}
                {deleteTarget && (
                        <dialog className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" open aria-modal="true" aria-label={t("connectionsPage.deleteConnection")}>
                                <div className="bg-card border border-border rounded-xl shadow-2xl max-w-md w-full p-6">
                                        <h3 className="text-lg font-semibold text-foreground mb-2">
                                                {t("connectionsPage.deleteConnection")}
                                        </h3>
                                        <p className="text-muted-foreground text-sm mb-4">
                                                {t("connectionsPage.deleteConfirmation")}
                                        </p>
                                        <div className="flex justify-end gap-3">
                                                <Button
                                                        variant="outline"
                                                        onClick={() => setDeleteTarget(null)}
                                                >
                                                        {t("common.cancel")}
                                                </Button>
                                                <Button
                                                        variant="destructive"
                                                        onClick={() => deleteMutation.mutate(deleteTarget)}
                                                        disabled={deleteMutation.isPending}
                                                >
                                                        {deleteMutation.isPending
                                                                ? t("common.deleting")
                                                                : t("common.delete")}
                                                </Button>
                                        </div>
                                </div>
                        </dialog>
                )}

                {/* Edit Modal */}
                {editTarget && (
                        <EditConnectionModal
                                connection={editTarget}
                                onClose={() => setEditTarget(null)}
                                onSuccess={(updatedData) => {
                                        updateMutation.mutate({ id: editTarget.connection_id, data: updatedData });
                                }}
                        />
                )}
                </div>
        );
}

// ===== Create Connection Modal =====

function CreateConnectionModal({
        onClose,
        onSuccess,
}: {
        onClose: () => void;
        onSuccess: () => void;
}) {
        const { t } = useTranslation();
        const [fromId, setFromId] = useState("");
        const [toId, setToId] = useState("");
        const [relationshipType, setRelationshipType] = useState("");
        const [isParametric, setIsParametric] = useState(false);

        const createMutation = useMutation({
                mutationFn: () => {
                        const data: ConnectionCreate = {
                                from_element_id: fromId,
                                to_element_id: toId,
                                relationship_type: relationshipType,
                                is_parametric: isParametric,
                        };
                        return api.createConnection(data);
                },
                onSuccess,
        });

        return (
                <dialog className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" open aria-modal="true" aria-label={t("connectionsPage.createConnection")}>
                        <div className="bg-card border border-border rounded-xl shadow-2xl max-w-md w-full p-6">
                                <h3 className="text-lg font-semibold text-foreground mb-4">
                                        {t("connectionsPage.createConnection")}
                                </h3>

                                {createMutation.isError && (
                                        <div className="bg-slate-500/10 border border-slate-500/20 rounded-lg p-3 mb-4">
                                                <p className="text-danger text-sm">
                                                        {createMutation.error instanceof Error
                                                                ? createMutation.error.message
                                                                : t("connectionsPage.failedToLoad")}
                                                </p>
                                        </div>
                                )}

                                <div className="space-y-4">
                                        <div>
                                                <label className="block text-sm font-medium text-foreground/90 mb-1">
                                                        {t("connectionsPage.sourceElement")} *
                                                </label>
                                                <Input
                                                        type="text"
                                                        value={fromId}
                                                        onChange={(e) => setFromId(e.target.value)}
                                                        placeholder="Element UUID"
                                                />
                                        </div>
                                        <div>
                                                <label className="block text-sm font-medium text-foreground/90 mb-1">
                                                        {t("connectionsPage.targetElement")} *
                                                </label>
                                                <Input
                                                        type="text"
                                                        value={toId}
                                                        onChange={(e) => setToId(e.target.value)}
                                                        placeholder="Element UUID"
                                                />
                                        </div>
                                        <div>
                                                <label className="block text-sm font-medium text-foreground/90 mb-1">
                                                        {t("connectionsPage.relationshipType")} *
                                                </label>
                                                <Input
                                                        type="text"
                                                        value={relationshipType}
                                                        onChange={(e) => setRelationshipType(e.target.value)}
                                                        placeholder="e.g., adjacent, connected, contains"
                                                />
                                        </div>
                                        <label className="flex items-center gap-2 cursor-pointer">
                                                <input
                                                        type="checkbox"
                                                        checked={isParametric}
                                                        onChange={(e) => setIsParametric(e.target.checked)}
                                                        className="rounded bg-card border-border text-primary focus:ring-primary/30 focus:ring-2"
                                                />
                                                <span className="text-sm text-foreground/90">{t("common.active")}</span>
                                        </label>
                                </div>

                                <div className="flex justify-end gap-3 mt-6">
                                        <Button
                                                variant="outline"
                                                onClick={onClose}
                                        >
                                                {t("common.cancel")}
                                        </Button>
                                        <Button
                                                onClick={() => createMutation.mutate()}
                                                disabled={
                                                        !fromId || !toId || !relationshipType || createMutation.isPending
                                                }
                                        >
                                                {createMutation.isPending
                                                        ? t("common.creating")
                                                        : t("common.create")}
                                        </Button>
                                </div>
                        </div>
                        </dialog>
        );
}

export default Connections;

function EditConnectionModal({
        connection,
        onClose,
        onSuccess,
}: {
        connection: any;
        onClose: () => void;
        onSuccess: (data: any) => void;
}) {
        const { t } = useTranslation();
        const [relationshipType, setRelationshipType] = useState(connection.relationship_type || "");
        const [isParametric, setIsParametric] = useState(connection.is_parametric || false);

        const handleSave = (e: React.FormEvent) => {
                e.preventDefault();
                onSuccess({
                        relationship_type: relationshipType,
                        is_parametric: isParametric,
                });
        };

        return (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                        <div className="bg-card border border-border rounded-xl shadow-2xl max-w-md w-full p-6">
                                <h3 className="text-lg font-semibold text-foreground mb-4">
                                        Edit Connection
                                </h3>
                                <form onSubmit={handleSave} className="space-y-4">
                                        <div className="space-y-2">
                                                <label className="text-sm font-medium text-foreground">
                                                        Relationship Type
                                                </label>
                                                <Input
                                                        required
                                                        value={relationshipType}
                                                        onChange={(e) => setRelationshipType(e.target.value)}
                                                />
                                        </div>
                                        <div className="flex items-center gap-2">
                                                <input
                                                        type="checkbox"
                                                        id="edit-is-parametric"
                                                        checked={isParametric}
                                                        onChange={(e) => setIsParametric(e.target.checked)}
                                                        className="w-4 h-4 rounded border-border"
                                                />
                                                <label htmlFor="edit-is-parametric" className="text-sm font-medium text-foreground">
                                                        Parametric connection
                                                </label>
                                        </div>
                                        <div className="flex justify-end gap-3 pt-4 border-t border-border/50">
                                                <Button type="button" variant="outline" onClick={onClose}>
                                                        {t("common.cancel")}
                                                </Button>
                                                <Button type="submit">
                                                        {t("common.save")}
                                                </Button>
                                        </div>
                                </form>
                        </div>
                </div>
        );
}
