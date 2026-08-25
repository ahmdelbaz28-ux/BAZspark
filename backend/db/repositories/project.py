from __future__ import annotations

import uuid
try:
    from datetime import UTC, datetime
except ImportError:
    from datetime import datetime, timezone

    UTC = timezone.utc

from backend.db.repositories.base import BaseRepository


class ProjectRepository(BaseRepository):
    """Repository handling project CRUD and counts operations."""

    def create_project(self, project_data: dict) -> dict:
        """Insert a new project, seed initial OCC revision in project_revisions, and return it."""
        now = datetime.now(UTC).isoformat()
        project_data.setdefault("id", str(uuid.uuid4()))
        project_data["createdAt"] = now
        project_data["updatedAt"] = now
        project_data.setdefault("status", "draft")
        project_data.setdefault("description", "")
        project_data.setdefault("author", "")

        with self.db._transaction() as cur:
            cur.execute(
                f"""INSERT INTO projects (id, name, description, author, created_at, updated_at, status)
                   VALUES ({self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()}, {self.db._ph()})""",
                (
                    project_data["id"],
                    project_data["name"],
                    project_data["description"],
                    project_data["author"],
                    project_data["createdAt"],
                    project_data["updatedAt"],
                    project_data["status"],
                ),
            )
            cur.execute(
                f"""INSERT INTO project_revisions (project_id, revision, canonical_state, updated_at)
                   VALUES ({self.db._ph()}, 1, {self.db._ph()}, {self.db._ph()})""",
                (
                    project_data["id"],
                    "{}",
                    now,
                ),
            )

        return self.get_project(project_data["id"])

    def get_project(self, project_id: str) -> dict | None:
        """Get a project by ID, with device and connection counts and canonical OCC revision — single query."""
        with self.db._transaction() as cur:
            cur.execute(
                f"""
                SELECT
                    p.*,
                    COALESCE(d.device_count, 0) AS device_count,
                    COALESCE(c.connection_count, 0) AS connection_count,
                    COALESCE(r.revision, 1) AS revision
                FROM projects p
                LEFT JOIN (
                    SELECT project_id, COUNT(*) AS device_count
                    FROM devices
                    GROUP BY project_id
                ) d ON p.id = d.project_id
                LEFT JOIN (
                    SELECT project_id, COUNT(*) AS connection_count
                    FROM connections
                    GROUP BY project_id
                ) c ON p.id = c.project_id
                LEFT JOIN project_revisions r ON p.id = r.project_id
                WHERE p.id = {self.db._ph()}
                """,
                (project_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

        return self.db._row_to_project(
            row,
            row["device_count"],
            row["connection_count"],
            row["revision"],
        )

    def list_projects(
        self,
        page: int = 1,
        limit: int = 20,
        sort: str = "created_at",
        order: str = "desc",
        author: str | None = None,
    ) -> dict:
        """List projects with pagination, canonical revision, and server-authoritative tenant scoping."""
        _ALLOWED_PROJECT_SORTS = frozenset(
            {"id", "name", "created_at", "updated_at", "status", "author"}
        )
        if order.lower() not in ("asc", "desc"):
            order = "desc"

        page = page if isinstance(page, int) else 1
        limit = limit if isinstance(limit, int) else 20

        sort = sort if sort in _ALLOWED_PROJECT_SORTS else "created_at"
        order = "ASC" if order.upper() == "ASC" else "DESC"

        secondary_sort = "p.id" if self.db._is_postgres else "p.rowid"

        where_clause = ""
        where_params: list = []
        if author is not None:
            # Multi-tenant isolation: non-admin callers only see their own authored projects or legacy fixtures
            where_clause = f"WHERE (p.author = {self.db._ph()} OR p.author LIKE 'legacy%')"
            where_params.append(author)

        with self.db._transaction() as cur:
            # Get total count
            cur.execute(f"SELECT COUNT(*) FROM projects p {where_clause}", tuple(where_params))
            total = self.db._scalar(cur)

            # Get paginated results with device/connection counts and canonical revision in ONE query (no N+1)
            offset = (page - 1) * limit
            query_params = list(where_params) + [limit, offset]
            cur.execute(
                f"""
                SELECT
                    p.*,
                    COALESCE(d.device_count, 0) AS device_count,
                    COALESCE(c.connection_count, 0) AS connection_count,
                    COALESCE(r.revision, 1) AS revision
                FROM projects p
                LEFT JOIN (
                    SELECT project_id, COUNT(*) AS device_count
                    FROM devices
                    GROUP BY project_id
                ) d ON p.id = d.project_id
                LEFT JOIN (
                    SELECT project_id, COUNT(*) AS connection_count
                    FROM connections
                    GROUP BY project_id
                ) c ON p.id = c.project_id
                LEFT JOIN project_revisions r ON p.id = r.project_id
                {where_clause}
                ORDER BY p.{sort} {order}, {secondary_sort} {order}
                LIMIT {self.db._ph()} OFFSET {self.db._ph()}
                """,
                tuple(query_params),
            )
            rows = cur.fetchall()

            projects = [
                self.db._row_to_project(
                    row,
                    row["device_count"],
                    row["connection_count"],
                    row["revision"],
                )
                for row in rows
            ]

        total_pages = max(1, (total + limit - 1) // limit)
        return {
            "data": projects,
            "total": total,
            "page": page,
            "limit": limit,
            "totalPages": total_pages,
        }

    def update_project(self, project_id: str, updates: dict) -> dict | None:
        """Update a project. Returns updated project or None if not found."""
        existing = self.get_project(project_id)
        if not existing:
            return None

        now = datetime.now(UTC).isoformat()
        set_clauses = [f"updated_at = {self.db._ph()}"]
        values = [now]

        field_map = {
            "name": "name",
            "description": "description",
            "author": "author",
            "status": "status",
        }
        for api_field, db_field in field_map.items():
            if api_field in updates and updates[api_field] is not None:
                set_clauses.append(f"{db_field} = {self.db._ph()}")
                values.append(updates[api_field])

        values.append(project_id)

        with self.db._transaction() as cur:
            cur.execute(
                f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = {self.db._ph()}",
                values,
            )

        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its children (CASCADE)."""
        with self.db._transaction() as cur:
            cur.execute(
                f"DELETE FROM sync_status WHERE project_id = {self.db._ph()}", (project_id,)
            )
            cur.execute(f"DELETE FROM reports WHERE project_id = {self.db._ph()}", (project_id,))
            cur.execute(
                f"DELETE FROM connections WHERE project_id = {self.db._ph()}", (project_id,)
            )
            cur.execute(f"DELETE FROM devices WHERE project_id = {self.db._ph()}", (project_id,))
            cur.execute(
                f"DELETE FROM project_revisions WHERE project_id = {self.db._ph()}", (project_id,)
            )
            cur.execute(f"DELETE FROM projects WHERE id = {self.db._ph()}", (project_id,))
            return cur.rowcount > 0

    def get_global_counts(self) -> dict:
        """Get total counts of devices, connections, and active projects."""
        with self.db._transaction() as cur:
            cur.execute("SELECT COUNT(*) FROM devices")
            total_devices = self.db._scalar(cur)
            cur.execute("SELECT COUNT(*) FROM connections")
            total_connections = self.db._scalar(cur)
            cur.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")
            active_projects = self.db._scalar(cur)
        return {
            "total_devices": total_devices,
            "total_connections": total_connections,
            "active_projects": active_projects,
        }
