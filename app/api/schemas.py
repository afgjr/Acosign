"""Pydantic schemas for the AudioSignature API (P2.3 / P2.4)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class RegisterResponse(BaseModel):
    """Response payload returned upon successfully registering a track."""

    content_id: str
    track_id: int
    title: str
    owner: str
    duration_seconds: float
    hashes_stored: int


class IdentifyResponse(BaseModel):
    """Response payload returned when querying an unknown audio clip."""

    matched: bool
    content_id: str | None = None
    title: str | None = None
    owner: str | None = None
    score: int | None = None
    match_strength: Literal["strong", "weak"] | None = None
    offset_seconds: float | None = None


class TrackOut(BaseModel):
    """Track metadata representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content_id: str
    title: str
    owner: str
    duration_seconds: float
    created_at: datetime
