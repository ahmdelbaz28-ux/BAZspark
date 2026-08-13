"""
backend/services/connection_service.py — Unified Connection Business Service.
================================================================================
Consolidates connection retrieval, sorting, pagination, and device validation
shared between v1 project-scoped connections and v2 relationship connections.
"""

from __future__ import annotations

import math
from typing import Any

from backend.database import get_db


class ConnectionService:
    """Unified service layer for connection operations."""

    SORT_MAP: dict[str, str] = {
        "createdAt": "created_at",
        "cableSize": "cable_size",
        "length": "length",
        "type": "type",
    }

    @classmethod
    def normalize_sort_field(cls, sort: str) -> str:
        """Convert camelCase sort field names to database column names."""
        return cls.SORT_MAP.get(sort, "created_at")

    @classmethod
    def calculate_pagination(cls, total: int, page_size: int) -> int:
        """Calculate total pages from total count and page size."""
        if total <= 0 or page_size <= 0:
            return 0
        return math.ceil(total / page_size)

    @classmethod
    def verify_project_exists(cls, project_id: str) -> bool:
        """Check if project exists in database."""
        db = get_db()
        return db.get_project(project_id) is not None

    @classmethod
    def get_device(cls, project_id: str, device_id: str) -> Any | None:
        """Fetch device by project ID and device ID."""
        db = get_db()
        return db.get_device(project_id, device_id)


connection_service = ConnectionService()
