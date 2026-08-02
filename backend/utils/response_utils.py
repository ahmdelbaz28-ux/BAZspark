"""
backend/utils/response_utils.py — Unified API Response & Pagination Utilities.
================================================================================
Centralizes response formatting and pagination validation used across backend routers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypeVar

T = TypeVar("T")


def build_success_response(data: Any, message: str | None = None) -> Dict[str, Any]:
    """Build a standard success API response dictionary."""
    res: Dict[str, Any] = {"success": True, "data": data}
    if message:
        res["message"] = message
    return res


def build_error_response(error_code: str, detail: str, action: str | None = None) -> Dict[str, Any]:
    """Build a standard error API response dictionary."""
    res: Dict[str, Any] = {
        "success": False,
        "error": error_code,
        "detail": detail,
    }
    if action:
        res["action"] = action
    return res


def build_paginated_response(
    items: List[Any],
    total: int,
    page: int,
    page_size: int,
) -> Dict[str, Any]:
    """Build a standard paginated data structure."""
    import math

    total_pages = math.ceil(total / page_size) if total > 0 and page_size > 0 else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
