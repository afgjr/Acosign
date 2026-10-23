"""SQLAlchemy database models for Acosign (P2.1)."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""


class Track(Base):
    """Audio track metadata."""

    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content_id: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
        default=lambda: uuid.uuid4().hex,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Extended metadata (optional/nullable)
    album: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    genre: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    isrc: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    license_type: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    fingerprints: Mapped[list[Fingerprint]] = relationship(
        "Fingerprint",
        back_populates="track",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Fingerprint(Base):
    """Audio fingerprint hash entry for landmark constellation matching."""

    __tablename__ = "fingerprints"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    # 34-bit packed integer: (f1 << 22) | (f2 << 10) | dt
    hash: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    track_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tracks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    offset: Mapped[int] = mapped_column(Integer, nullable=False)

    track: Mapped[Track] = relationship("Track", back_populates="fingerprints")
