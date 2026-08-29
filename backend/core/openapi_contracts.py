"""
backend/core/openapi_contracts.py — Standardized OpenAPI Error Contracts.
========================================================================
Provides automated OpenAPI response documentation for FastAPI routers,
eliminating repetitive per-endpoint boilerplate while maintaining strict
OpenAPI schema contracts (resolves SonarCloud python:S8415).
"""

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi.routing import APIRoute

# Standard RFC 7807 / FastAPI HTTP error responses
STANDARD_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": "Bad Request — Client validation or input parameter failure."},
    401: {"description": "Unauthorized — Missing or invalid authentication token."},
    403: {"description": "Forbidden — Insufficient permissions to access this resource."},
    404: {"description": "Not Found — Requested resource does not exist."},
    422: {"description": "Unprocessable Entity — Schema validation error."},
    500: {"description": "Internal Server Error — Unhandled server exception."},
}

F = TypeVar("F", bound=Callable[..., Any])


class StandardizedAPIRoute(APIRoute):
    """
    Custom APIRoute that automatically merges standard HTTP error responses
    into every route definition if not already explicitly defined.
    """

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        responses = kwargs.get("responses") or {}
        # Merge standard error responses without overriding user-defined ones
        for status_code, doc in STANDARD_ERROR_RESPONSES.items():
            if status_code not in responses:
                responses[status_code] = doc
        kwargs["responses"] = responses
        super().__init__(path, endpoint, **kwargs)


def standardized_error_responses(
    *status_codes: int,
) -> Callable[[F], F]:
    """
    Decorator to attach standard error response documentation to an endpoint.
    If no status codes are supplied, attaches 400, 404, and 500.
    """
    selected_codes = status_codes or (400, 404, 500)

    def decorator(func: F) -> F:
        existing_responses = getattr(func, "__openapi_responses__", {})
        for code in selected_codes:
            if code in STANDARD_ERROR_RESPONSES and code not in existing_responses:
                existing_responses[code] = STANDARD_ERROR_RESPONSES[code]
        func.__dict__["__openapi_responses__"] = existing_responses
        return func

    return decorator
