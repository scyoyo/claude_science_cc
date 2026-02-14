"""Shared FastAPI dependencies (e.g. pagination)."""

from fastapi import Query

from app.schemas.pagination import PaginatedResponse


def pagination_params(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> tuple[int, int]:
    """Dependency for list endpoints (default limit 100)."""
    return (skip, limit)


def search_pagination_params(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> tuple[int, int]:
    """Dependency for search endpoints (default limit 20)."""
    return (skip, limit)


def build_paginated_response(query, skip: int, limit: int) -> PaginatedResponse:
    """Run count/offset/limit on query and return PaginatedResponse."""
    total = query.count()
    items = query.offset(skip).limit(limit).all()
    return PaginatedResponse(items=items, total=total, skip=skip, limit=limit)
