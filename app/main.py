"""FastAPI application entrypoint (P2.5)."""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import router as api_router
from app.core.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AudioSignature API",
    description="Acoustic fingerprinting and cryptographic provenance engine",
    version="0.1.0",
)

# ── CORS Middleware ────────────────────────────────────────────────────────────
raw_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
allow_all = "*" in raw_origins or not raw_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else raw_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handler ───────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch unexpected exceptions: return 500 without leaking stack traces."""
    # Let standard HTTP and validation errors pass through with their exact status codes
    if isinstance(exc, StarletteHTTPException):
        return await http_exception_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        return await request_validation_exception_handler(request, exc)

    logger.exception("Unhandled server exception on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal error"},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(api_router)


@app.get("/health", summary="Service health check")
def health(db: Session = Depends(get_db)):
    """Health check endpoint reporting service status and database connectivity."""
    db_status = "ok"
    try:
        db.execute(text("SELECT 1;"))
    except Exception as exc:
        logger.warning("Database connectivity check failed: %s", exc)
        db_status = "unreachable"

    return {
        "status": "ok",
        "database": db_status,
        "service": "AudioSignature Engine",
        "environment": "INSA Capstone Development",
    }
