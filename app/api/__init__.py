"""app.api package — routers and Pydantic schemas."""

from app.api.auth import require_admin
from app.api.routes import router
from app.api.schemas import IdentifyResponse, RegisterResponse, TrackOut

__all__ = [
    "require_admin",
    "router",
    "RegisterResponse",
    "IdentifyResponse",
    "TrackOut",
]
