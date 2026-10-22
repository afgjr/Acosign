"""Authentication dependencies for administrative endpoints."""

from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_admin(x_api_key: str | None = Header(None)) -> str:
    """Validate administrator API key via X-API-Key request header.

    Fails closed:
    - If ADMIN_API_KEY is unset or empty, returns 503 Service Unavailable ("Admin key not configured").
    - If X-API-Key header is missing or incorrect, returns 401 Unauthorized ("Invalid or missing admin key")
      using timing-attack safe comparison (secrets.compare_digest).

    The key is never logged or included in any response payload.
    """
    if not settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin key not configured",
        )

    if not x_api_key or not secrets.compare_digest(x_api_key, settings.ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin key",
        )

    return x_api_key
