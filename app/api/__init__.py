"""app.api package — routers and Pydantic schemas."""

from app.api.auth import require_admin
from app.api.routes import router, trim_query_audio
from app.api.schemas import IdentifyResponse, RegisterResponse, TrackOut

__all__ = [
    "require_admin",
    "router",
    "trim_query_audio",
    "RegisterResponse",
    "IdentifyResponse",
    "TrackOut",
]
