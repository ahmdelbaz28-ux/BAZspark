/**
 * RbacPage.tsx — RBAC Permission Matrix page.
 *
 * Displays a read-only permission matrix showing all 3 roles (Admin, Engineer, Viewer)
 * vs 28 permissions grouped by category. Fetches from the backend endpoint with
 * fallback to hardcoded data.
 *
 *   GET /api/v1/admin/rbac/permissions — List role-permission mapping
 */

import { Shield, Check, X } from "lucide-react";
import { useState, useEffect } from "react";
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
import {
        Table,
        TableBody,
        TableCell,
        TableHead,
        TableHeader,
        TableRow,
} from "@/components/ui/table";
import { rbacApi } from "@/services/fullApi";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PermissionEntry {
        name: string;
        label: string;
}

interface PermissionCategory {
        category: string;
        permissions: PermissionEntry[];
}

interface RolePermissionMap {
        admin: string[];
        engineer: string[];
        viewer: string[];
}

// ---------------------------------------------------------------------------
// Hardcoded fallback data (mirrors backend/rbac.py)
// ---------------------------------------------------------------------------

const FALLBACK_CATEGORIES: PermissionCategory[] = [
        {
                category: "Project",
                permissions: [
                        { name: "project:read", label: "project:read" },
                        { name: "project:create", label: "project:create" },
                        { name: "project:update", label: "project:update" },
                        { name: "project:delete", label: "project:delete" },
                ],
        },
        {
                category: "Device",
                permissions: [
                        { name: "device:read", label: "device:read" },
                        { name: "device:create", label: "device:create" },
                        { name: "device:update", label: "device:update" },
                        { name: "device:delete", label: "device:delete" },
                ],
        },
        {
                category: "Connection",
                permissions: [
                        { name: "connection:read", label: "connection:read" },
                        { name: "connection:create", label: "connection:create" },
                        { name: "connection:update", label: "connection:update" },
                        { name: "connection:delete", label: "connection:delete" },
                ],
        },
        {
                category: "Calculation",
                permissions: [
                        { name: "calculation:read", label: "calculation:read" },
                        { name: "calculation:execute", label: "calculation:execute" },
                ],
        },
        {
                category: "Report",
                permissions: [
                        { name: "report:read", label: "report:read" },
                        { name: "report:generate", label: "report:generate" },
                        { name: "report:delete", label: "report:delete" },
                ],
        },
        {
                category: "Export",
                permissions: [
                        { name: "export:read", label: "export:read" },
                        { name: "export:execute", label: "export:execute" },
                ],
        },
        {
                category: "Element",
                permissions: [
                        { name: "element:read", label: "element:read" },
                        { name: "element:create", label: "element:create" },
                        { name: "element:update", label: "element:update" },
                        { name: "element:delete", label: "element:delete" },
                ],
        },
        {
                category: "Conflict",
                permissions: [
                        { name: "conflict:read", label: "conflict:read" },
                        { name: "conflict:resolve", label: "conflict:resolve" },
                ],
        },
        {
                category: "System",
                permissions: [
                        { name: "system:config", label: "system:config" },
                        { name: "user:manage", label: "user:manage" },
                        { name: "monitor:read", label: "monitor:read" },
                        { name: "health:read", label: "health:read" },
                ],
        },
        {
                category: "QOMN",
                permissions: [
                        { name: "qomn:read", label: "qomn:read" },
                        { name: "qomn:execute", label: "qomn:execute" },
                ],
        },
        {
                category: "FACP",
                permissions: [
                        { name: "facp:read", label: "facp:read" },
                        { name: "facp:manage", label: "facp:manage" },
                ],
        },
        {
                category: "Workflow",
                permissions: [
                        { name: "workflow:read", label: "workflow:read" },
                        { name: "workflow:manage", label: "workflow:manage" },
                ],
        },
        {
                category: "Integration",
                permissions: [
                        { name: "integration:read", label: "integration:read" },
                        { name: "integration:manage", label: "integration:manage" },
                ],
        },
];

const FALLBACK_ROLE_PERMISSIONS: RolePermissionMap = {
        admin: [
                "project:read", "project:create", "project:update", "project:delete",
                "device:read", "device:create", "device:update", "device:delete",
                "connection:read", "connection:create", "connection:update", "connection:delete",
                "calculation:read", "calculation:execute",
                "report:read", "report:generate", "report:delete",
                "export:read", "export:execute",
                "element:read", "element:create", "element:update", "element:delete",
                "conflict:read", "conflict:resolve",
                "system:config", "user:manage", "monitor:read", "health:read",
                "qomn:read", "qomn:execute",
                "facp:read", "facp:manage",
                "workflow:read", "workflow:manage",
                "integration:read", "integration:manage",
        ],
        engineer: [
                "project:read", "project:create", "project:update", "project:delete",
                "device:read", "device:create", "device:update", "device:delete",
                "connection:read", "connection:create", "connection:update", "connection:delete",
                "calculation:read", "calculation:execute",
                "report:read", "report:generate", "report:delete",
                "export:read", "export:execute",
                "element:read", "element:create", "element:update", "element:delete",
                "conflict:read", "conflict:resolve",
                "health:read",
                "qomn:read", "qomn:execute",
                "facp:read", "facp:manage",
                "workflow:read", "workflow:manage",
                "monitor:read",
                "integration:read", "integration:manage",
        ],
        viewer: [
                "project:read",
                "device:read",
                "connection:read",
                "calculation:read",
                "report:read",
                "export:read",
                "element:read",
                "conflict:read",
                "health:read",
                "qomn:read",
                "facp:read",
                "workflow:read",
                "monitor:read",
                "integration:read",
        ],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const ROLES = ["admin", "engineer", "viewer"] as const;

const roleBadgeClass = (role: string): string => {
        if (role === "admin") return "bg-red-600";
        if (role === "engineer") return "bg-amber-500";
        return "bg-emerald-600";
};

const roleLabel = (role: string): string => {
        if (role === "admin") return "Admin";
        if (role === "engineer") return "Engineer";
        return "Viewer";
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RbacPage() {
        const { t } = useTranslation();
        const [categories, setCategories] = useState<PermissionCategory[]>(FALLBACK_CATEGORIES);
        const [rolePermissions, setRolePermissions] = useState<RolePermissionMap>(FALLBACK_ROLE_PERMISSIONS);
        const [loading, setLoading] = useState(true);
        const [usingFallback, setUsingFallback] = useState(false);

        const fetchPermissions = async () => {
                setLoading(true);
                setUsingFallback(false);
                try {
                        const data = await rbacApi.getPermissions();

                        // Backend may return { categories, role_permissions } or { data: { … } }
                        const payload = (data as Record<string, unknown>).data
                                ? (data as Record<string, unknown>).data as Record<string, unknown>
                                : data as Record<string, unknown>;
                        if (payload.categories) setCategories(payload.categories as PermissionCategory[]);
                        if (payload.role_permissions) setRolePermissions(payload.role_permissions as RolePermissionMap);
                } catch (err) {
                        setUsingFallback(true);
                        setCategories(FALLBACK_CATEGORIES);
                        setRolePermissions(FALLBACK_ROLE_PERMISSIONS);
                        toast.error(
                                `Failed to load RBAC data from backend: ${err instanceof Error ? err.message : "Unknown"}. Using local fallback.`,
                        );
                } finally {
                        setLoading(false);
                }
        };

        useEffect(() => {
                // Inline async IIFE — no synchronous setState in the effect body
                // (react-hooks/set-state-in-effect). `fetchPermissions` is still
                // defined above for use by event handlers (refresh button).
                let cancelled = false;
                (async () => {
                        try {
                                const data = await rbacApi.getPermissions();
                                if (cancelled) return;
                                const payload = (data as Record<string, unknown>).data
                                        ? (data as Record<string, unknown>).data as Record<string, unknown>
                                        : data as Record<string, unknown>;
                                if (payload.categories) setCategories(payload.categories as PermissionCategory[]);
                                if (payload.role_permissions) setRolePermissions(payload.role_permissions as RolePermissionMap);
                        } catch (err) {
                                if (cancelled) return;
                                setUsingFallback(true);
                                setCategories(FALLBACK_CATEGORIES);
                                setRolePermissions(FALLBACK_ROLE_PERMISSIONS);
                                toast.error(
                                        `Failed to load RBAC data from backend: ${err instanceof Error ? err.message : "Unknown"}. Using local fallback.`,
                                );
                        } finally {
                                if (!cancelled) setLoading(false);
                        }
                })();
                return () => {
                        cancelled = true;
                };
        }, []);

        const hasPermission = (role: string, permission: string): boolean => {
                const perms = rolePermissions[role as keyof RolePermissionMap];
                return perms ? perms.includes(permission) : false;
        };

        // Count total permissions per role
        const permissionCounts = ROLES.map((role) => {
                const perms = rolePermissions[role];
                return { role, count: perms ? perms.length : 0 };
        });

        const totalPermissions = categories.reduce(
                (sum, cat) => sum + cat.permissions.length,
                0,
        );

        return (
                <div className="flex-1 overflow-auto p-6 max-w-6xl mx-auto space-y-6">
                        {/* Header */}
                        <div>
                                <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
                                        <Shield aria-hidden="true" className="h-6 w-6 text-primary" />
                                        {t("rbac.title", "RBAC Permission Matrix")}
                                </h1>
                                <p className="text-sm text-muted-foreground mt-1">
                                        {t(
                                                "rbac.description",
                                                "View the role-permission mapping for the BAZspark platform",
                                        )}
                                </p>
                        </div>

                        {/* Role Summary Cards */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {permissionCounts.map(({ role, count }) => (
                                        <Card key={role} className="border-border bg-card">
                                                <CardHeader className="pb-2">
                                                        <div className="flex items-center justify-between">
                                                                <CardTitle className="text-base">{roleLabel(role)}</CardTitle>
                                                                <Badge className={roleBadgeClass(role)}>{role}</Badge>
                                                        </div>
                                                </CardHeader>
                                                <CardContent>
                                                        <div className="text-3xl font-bold">
                                                                {count}
                                                                <span className="text-sm font-normal text-muted-foreground">
                                                                        {" "}
                                                                        / {totalPermissions}
                                                                </span>
                                                        </div>
                                                        <p className="text-xs text-muted-foreground mt-1">
                                                                {t("rbac.permissionsGranted", "permissions granted")}
                                                        </p>
                                                </CardContent>
                                        </Card>
                                ))}
                        </div>

                        {/* Permission Matrix */}
                        <Card className="border-border bg-card">
                                <CardHeader>
                                        <div className="flex items-center justify-between">
                                                <div>
                                                        <CardTitle>
                                                                {t("rbac.matrixTitle", "Permission Matrix")}
                                                        </CardTitle>
                                                        <CardDescription>
                                                                {usingFallback
                                                                        ? t(
                                                                                        "rbac.fallbackNotice",
                                                                                        "Showing local fallback data — backend unreachable",
                                                                                )
                                                                        : t(
                                                                                        "rbac.matrixDescription",
                                                                                        "Current role-permission mapping from the backend",
                                                                                )}
                                                        </CardDescription>
                                                </div>
                                                <Button
                                                        onClick={fetchPermissions}
                                                        size="sm"
                                                        disabled={loading}
                                                        variant="outline"
                                                >
                                                        <Shield aria-hidden="true" className="h-4 w-4 mr-1" />
                                                        {t("rbac.refresh", "Refresh")}
                                                </Button>
                                        </div>
                                </CardHeader>
                                <CardContent>
                                        {loading ? (
                                                <div className="flex items-center justify-center py-8">
                                                        <Shield
                                                                aria-hidden="true"
                                                                className="h-6 w-6 animate-pulse text-muted-foreground"
                                                        />
                                                        <span className="ml-2 text-sm text-muted-foreground">
                                                                {t("rbac.loading", "Loading permissions…")}
                                                        </span>
                                                </div>
                                        ) : (
                                                <div className="overflow-x-auto">
                                                        <Table>
                                                                <TableHeader>
                                                                        <TableRow>
                                                                                <TableHead className="w-[180px]">
                                                                                        {t("rbac.category", "Category")}
                                                                                </TableHead>
                                                                                <TableHead className="w-[200px]">
                                                                                        {t("rbac.permission", "Permission")}
                                                                                </TableHead>
                                                                                {ROLES.map((role) => (
                                                                                        <TableHead key={role} className="text-center w-[120px]">
                                                                                                <div className="flex flex-col items-center gap-1">
                                                                                                        <Badge
                                                                                                                className={`${roleBadgeClass(role)} text-xs`}
                                                                                                        >
                                                                                                                {roleLabel(role)}
                                                                                                        </Badge>
                                                                                                </div>
                                                                                        </TableHead>
                                                                                ))}
                                                                        </TableRow>
                                                                </TableHeader>
                                                                <TableBody>
                                                                        {categories.map((cat) =>
                                                                                cat.permissions.map((perm, permIdx) => (
                                                                                        <TableRow key={perm.name}>
                                                                                                {permIdx === 0 ? (
                                                                                                        <TableCell
                                                                                                                rowSpan={cat.permissions.length}
                                                                                                                className="font-medium text-foreground align-top border-r border-border"
                                                                                                        >
                                                                                                                {cat.category}
                                                                                                        </TableCell>
                                                                                                ) : null}
                                                                                                <TableCell className="font-mono text-sm">
                                                                                                        {perm.label}
                                                                                                </TableCell>
                                                                                                {ROLES.map((role) => {
                                                                                                        const granted = hasPermission(role, perm.name);
                                                                                                        return (
                                                                                                                <TableCell
                                                                                                                        key={role}
                                                                                                                        className="text-center"
                                                                                                                >
                                                                                                                        {granted ? (
                                                                                                                                <Badge
                                                                                                                                        variant="outline"
                                                                                                                                        className="bg-emerald-600/10 text-emerald-600 border-emerald-600/30 gap-1"
                                                                                                                                >
                                                                                                                                        <Check
                                                                                                                                                aria-hidden="true"
                                                                                                                                                className="h-3 w-3"
                                                                                                                                        />
                                                                                                                                        {t("rbac.granted", "✓")}
                                                                                                                                </Badge>
                                                                                                                        ) : (
                                                                                                                                <Badge
                                                                                                                                        variant="outline"
                                                                                                                                        className="bg-red-600/10 text-red-600 border-red-600/30 gap-1"
                                                                                                                                >
                                                                                                                                        <X
                                                                                                                                                aria-hidden="true"
                                                                                                                                                className="h-3 w-3"
                                                                                                                                        />
                                                                                                                                        {t("rbac.denied", "—")}
                                                                                                                                </Badge>
                                                                                                                        )}
                                                                                                                </TableCell>
                                                                                                        );
                                                                                                })}
                                                                                        </TableRow>
                                                                                )),
                                                                        )}
                                                                </TableBody>
                                                        </Table>
                                                </div>
                                        )}
                                </CardContent>
                        </Card>
                </div>
        );
}
