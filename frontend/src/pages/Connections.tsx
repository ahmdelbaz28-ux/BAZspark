
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
                <div className="space-y-5" aria-label={t("connectionsPage.title")}>
                        {/* FACP Page Header */}
                        <div className="facp-page-header flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                        <div>
                                <h1 className="facp-page-title">
                                        {t("connectionsPage.title")}
                                </h1>
                                <p className="facp-page-count">
                                        {connectionsData
                                                ? t("connectionsPage.totalConnections", {
                                                                count: connectionsData.total,
                                                        })
                                                : t("common.loading")}
                                </p>
                        </div>
                        <button
                                type="button"
                                onClick={() => setShowCreateModal(true)}
                                className="facp-btn facp-btn--primary"
                                aria-label={t("connectionsPage.createConnection")}
                        >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                        <line x1="12" y1="5" x2="12" y2="19" />
                                        <line x1="5" y1="12" x2="19" y2="12" />
                                </svg>
                                {t("connectionsPage.createConnection")}
                        </button>
                        </div>

                {/* Filter Bar */}
                <div className="facp-filter-bar">
                        <input
                                type="text"
                                value={elementFilter}
                                onChange={(e) => setElementFilter(e.target.value)}
                                placeholder={t("connectionsPage.elementFilter")}
                                className="facp-filter-input"
                                aria-label={t("connectionsPage.elementFilter")}
                        />
                        {elementFilter && (
                                <button
                                        type="button"
                                        onClick={() => setElementFilter("")}
                                        className="facp-btn facp-btn--ghost"
                                        aria-label={t("common.clear")}
                                >
                                        ✕ {t("common.clear")}
                                </button>
                        )}
                </div>

                        {/* Error */}
                        {error && (
                                <div
                                        className="facp-panel"
                                        role="alert"
                                        style={{ borderLeft: "4px solid var(--color-signal-red)", padding: "1rem 1.25rem" }}
                                >
                                        <span className="facp-badge facp-badge--error">Error</span>
                                        <span style={{ fontFamily: "var(--font-body)", fontSize: "0.8125rem", color: "var(--color-bone)", marginLeft: "0.5rem" }}>
                                                {t("connectionsPage.failedToLoad")}
                                        </span>
                                </div>
                        )}

                        {/* Loading */}
                        {isLoading && (
                                <div className="flex items-center justify-center py-12">
                                        <div className="w-8 h-8 border-2 animate-spin" style={{ borderColor: "rgba(90,103,112,0.3)", borderTopColor: "var(--color-primary)", borderRadius: "9999px" }} />
                                </div>
                        )}

                        {/* Connection Table */}
                        {connectionsData && !isLoading && (
                                <div className="facp-table-wrap">
                                        <table className="facp-table" aria-label={t("connectionsPage.title")}>
                                                <thead>
                                                        <tr>
                                                                <th scope="col">{t("connectionsPage.sourceElement")}</th>
                                                                <th scope="col">{t("connectionsPage.targetElement")}</th>
                                                                <th scope="col">{t("connectionsPage.relationshipType")}</th>
                                                                <th scope="col">{t("common.active")}</th>
                                                                <th scope="col" style={{ textAlign: "right" }}>{t("connectionsPage.actions")}</th>
                                                        </tr>
                                                </thead>
                                                <tbody>
                                                        {connections.length === 0 ? (
                                                                <tr>
                                                                        <td colSpan={5} style={{ padding: 0 }}>
                                                                                <div className="facp-empty">
                                                                                        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true" className="facp-empty-icon">
                                                                                                <path d="M10 19h4m-2-17V4a2 2 0 00-2 2v3m6 12V7a4 4 0 00-8 0v12" />
                                                                                        </svg>
                                                                                        <p className="facp-empty-title">{t("connectionsPage.noConnections")}</p>
                                                                                        <p className="facp-empty-desc">{t("connectionsPage.createFirst")}</p>
                                                                                </div>
                                                                        </td>
                                                                </tr>
                                                        ) : (
                                                                connections.map((conn) => (
                                                                        <tr key={conn.connection_id}>
                                                                                <td>
                                                                                        <Link
                                                                                                to={`/elements/${conn.from_element_id}`}
                                                                                                className="facp-table-id hover:underline"
                                                                                                style={{ color: "var(--color-primary)" }}
                                                                                        >
                                                                                                {conn.from_element_id.slice(0, 12)}…
                                                                                        </Link>
                                                                                </td>
                                                                                <td>
                                                                                        <Link
                                                                                                to={`/elements/${conn.to_element_id}`}
                                                                                                className="facp-table-id hover:underline"
                                                                                                style={{ color: "var(--color-primary)" }}
                                                                                        >
                                                                                                {conn.to_element_id.slice(0, 12)}…
                                                                                        </Link>
                                                                                </td>
                                                                                <td>
                                                                                        <span className="facp-type-chip">
                                                                                                {conn.relationship_type}
                                                                                        </span>
                                                                                </td>
                                                                                <td>
                                                                                        {conn.is_parametric ? (
                                                                                                <span className="facp-badge facp-badge--active">Yes</span>
                                                                                        ) : (
                                                                                                <span className="facp-badge facp-badge--neutral">No</span>
                                                                                        )}
                                                                                </td>
                                                                                <td style={{ textAlign: "right" }}>
                                                                                        <div className="flex items-center justify-end gap-1">
                                                                                                        <button type="button"
                                                                                                                onClick={() => setEditTarget(conn)}
                                                                                                                className="facp-btn facp-btn--ghost facp-btn--icon"
                                                                                                                title="Edit"
                                                                                                                aria-label={`Edit connection`}
                                                                                                        >
                                                                                                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                                                                                                        <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path>
                                                                                                                </svg>
                                                                                                        </button>
                                                                                                        <button type="button"
                                                                                                                onClick={() => setDeleteTarget(conn.connection_id)}
                                                                                                                className="facp-btn facp-btn--danger facp-btn--icon"
                                                                                                                title="Delete"
                                                                                                                aria-label={`Delete connection`}
                                                                                                        >
                                                                                                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
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
                                <div className="bg-card border border-border rounded-xl shadow-2xl max-w-md w-full p-6 stagger-card">
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
                        <div className="bg-card border border-border rounded-xl shadow-2xl max-w-md w-full p-6 stagger-card">
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
                                                        className="rounded bg-card border-border text-primary focus:ring-primary/30 focus:ring-2 stagger-card"
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
                        <div className="bg-card border border-border rounded-xl shadow-2xl max-w-md w-full p-6 stagger-card">
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
