"""API routes for track registration and audio identification (P2.3 / P2.4)."""

from __future__ import annotations

from datetime import datetime

import logging
import time

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.concurrency import run_in_threadpool
import numpy as np
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.api.schemas import IdentifyResponse, RegisterResponse, TrackOut
from app.core.config import settings
from app.db.repository import (
    add_fingerprints,
    create_track,
    delete_track,
    find_hits,
    get_track,
    get_track_by_content_id,
    list_tracks,
)
from app.db.session import get_db
from app.engine.fingerprint import (
    AudioDecodeError,
    compute_spectrogram,
    find_peaks,
    generate_hashes,
    load_audio,
)
from app.engine.matcher import find_best_match

logger = logging.getLogger(__name__)

router = APIRouter()


def trim_query_audio(y: np.ndarray) -> np.ndarray:
    """Trim query audio to settings.MAX_QUERY_SECONDS from the middle if longer."""
    max_samples = int(settings.MAX_QUERY_SECONDS * settings.SAMPLE_RATE)
    if len(y) > max_samples:
        start = (len(y) - max_samples) // 2
        return y[start : start + max_samples]
    return y


def _compute_spectrogram_and_peaks(
    y: np.ndarray,
) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Compute spectrogram and extract peaks."""
    spec = compute_spectrogram(y)
    peaks = find_peaks(spec)
    return spec, peaks


def _process_audio_bytes(
    data: bytes,
) -> tuple[np.ndarray, float, list[tuple[int, int]]]:
    """CPU-bound audio processing: load audio -> compute spectrogram -> find peaks -> generate hashes."""
    y = load_audio(data)
    duration = float(len(y) / settings.SAMPLE_RATE)
    spec = compute_spectrogram(y)
    peaks = find_peaks(spec)
    hashes = generate_hashes(peaks)
    return y, duration, hashes


@router.get(
    "/admin/verify",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_admin)],
    summary="Verify admin API key",
)
def verify_admin_key() -> Response:
    """Verify administrator API key.

    Returns 204 No Content on valid key, 401 on wrong/missing key, 503 if unconfigured.
    """
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_admin)],
    summary="Register audio track and store fingerprints",
)
async def register(
    file: UploadFile = File(...),
    title: str = Form(...),
    owner: str = Form(...),
    album: str | None = Form(None),
    genre: str | None = Form(None),
    release_year: int | None = Form(None),
    isrc: str | None = Form(None),
    license_type: str | None = Form(None),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
) -> RegisterResponse:
    """Upload and register a full audio track with Content ID."""
    # Validate optional metadata fields
    current_year = datetime.now().year
    if release_year is not None and (release_year < 1900 or release_year > current_year + 1):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"release_year must be between 1900 and {current_year + 1}",
        )

    for field_name, field_val in [
        ("album", album),
        ("genre", genre),
        ("isrc", isrc),
        ("license_type", license_type),
    ]:
        if field_val is not None and len(field_val) > 200:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field_name} must not exceed 200 characters",
            )

    if description is not None and len(description) > 2000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="description must not exceed 2000 characters",
        )

    content = await file.read()

    # Enforce maximum upload size limit
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum size limit of {settings.MAX_UPLOAD_MB} MB",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Stage 1: decode
    try:
        t0 = time.perf_counter()
        y = await run_in_threadpool(load_audio, content)
        duration = float(len(y) / settings.SAMPLE_RATE)
        logger.info("Register decode stage completed in %.3fs", time.perf_counter() - t0)
    except AudioDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio decoding failed: {exc}",
        ) from exc

    # Stage 2: spectrogram+peaks
    t0 = time.perf_counter()
    _, peaks = await run_in_threadpool(_compute_spectrogram_and_peaks, y)
    logger.info("Register spectrogram+peaks stage completed in %.3fs", time.perf_counter() - t0)

    # Stage 3: hashing
    t0 = time.perf_counter()
    hashes = await run_in_threadpool(generate_hashes, peaks)
    logger.info("Register hashing stage completed in %.3fs", time.perf_counter() - t0)

    # Stage 4: duplicate check
    t0 = time.perf_counter()
    query_hashes = [h for h, _ in hashes]
    db_hits = find_hits(db, query_hashes)
    if db_hits:
        dup_match = find_best_match(hashes, db_hits, min_score=settings.DUPLICATE_SCORE)
        if dup_match is not None and dup_match.score >= settings.DUPLICATE_SCORE:
            logger.info("Register duplicate check stage completed in %.3fs (duplicate detected)", time.perf_counter() - t0)
            existing_track = get_track(db, dup_match.track_id)
            existing_content_id = existing_track.content_id if existing_track else "unknown"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Track already registered",
                    "content_id": existing_content_id,
                },
            )
    logger.info("Register duplicate check stage completed in %.3fs", time.perf_counter() - t0)

    # Stage 5: insert
    t0 = time.perf_counter()
    track = create_track(
        db,
        title=title,
        owner=owner,
        duration_seconds=duration,
        album=album,
        genre=genre,
        release_year=release_year,
        isrc=isrc,
        license_type=license_type,
        description=description,
    )
    hashes_stored = add_fingerprints(db, track.id, hashes)
    logger.info("Register insert stage completed in %.3fs", time.perf_counter() - t0)

    return RegisterResponse(
        content_id=track.content_id,
        track_id=track.id,
        title=track.title,
        owner=track.owner,
        duration_seconds=track.duration_seconds,
        hashes_stored=hashes_stored,
        album=track.album,
        genre=track.genre,
        release_year=track.release_year,
        isrc=track.isrc,
        license_type=track.license_type,
        description=track.description,
    )


@router.post(
    "/identify",
    response_model=IdentifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Identify unknown audio clip",
)
async def identify(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> IdentifyResponse:
    """Identify an unknown audio clip using offset voting against database fingerprints."""
    content = await file.read()

    # Enforce maximum upload size limit
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded clip exceeds maximum size limit of {settings.MAX_UPLOAD_MB} MB",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Stage 1: decode (+ trim if longer than MAX_QUERY_SECONDS)
    try:
        t0 = time.perf_counter()
        y = await run_in_threadpool(load_audio, content)
        logger.info("Identify decode stage completed in %.3fs", time.perf_counter() - t0)
    except AudioDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio decoding failed: {exc}",
        ) from exc

    # Trim to middle window if audio exceeds MAX_QUERY_SECONDS
    y = trim_query_audio(y)
    duration = float(len(y) / settings.SAMPLE_RATE)

    # Reject query clips shorter than MIN_QUERY_SECONDS
    if duration < settings.MIN_QUERY_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Audio clip ({duration:.2f}s) is shorter than minimum required query duration "
                f"({settings.MIN_QUERY_SECONDS}s)"
            ),
        )

    # Stage 2: spectrogram+peaks
    t0 = time.perf_counter()
    _, peaks = await run_in_threadpool(_compute_spectrogram_and_peaks, y)
    logger.info("Identify spectrogram+peaks stage completed in %.3fs", time.perf_counter() - t0)

    # Stage 3: hashing
    t0 = time.perf_counter()
    hashes = await run_in_threadpool(generate_hashes, peaks)
    logger.info("Identify hashing stage completed in %.3fs", time.perf_counter() - t0)

    # Stage 4: db lookup and matching
    t0 = time.perf_counter()
    query_hashes = [h for h, _ in hashes]
    db_hits = find_hits(db, query_hashes)
    match = find_best_match(hashes, db_hits)
    logger.info("Identify db lookup and matching stage completed in %.3fs", time.perf_counter() - t0)
    if match is None:
        return IdentifyResponse(matched=False)

    track = get_track(db, match.track_id)
    if track is None:
        return IdentifyResponse(matched=False)

    match_strength = "strong" if match.score >= settings.STRONG_SCORE else "weak"
    offset_seconds = float(match.offset_frames * settings.HOP_LENGTH / settings.SAMPLE_RATE)

    return IdentifyResponse(
        matched=True,
        content_id=track.content_id,
        title=track.title,
        owner=track.owner,
        score=match.score,
        match_strength=match_strength,
        offset_seconds=offset_seconds,
        album=track.album,
        genre=track.genre,
        release_year=track.release_year,
        isrc=track.isrc,
        license_type=track.license_type,
        description=track.description,
    )


@router.get(
    "/tracks",
    response_model=list[TrackOut],
    status_code=status.HTTP_200_OK,
    summary="List registered tracks with pagination",
)
def list_registered_tracks(
    limit: int = Query(default=20, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[TrackOut]:
    """List registered tracks with offset-based pagination. Maximum limit is capped at 100."""
    effective_limit = min(limit, 100)
    tracks = list_tracks(db, limit=effective_limit, offset=offset)
    return [TrackOut.model_validate(t) for t in tracks]


@router.get(
    "/tracks/{content_id}",
    response_model=TrackOut,
    status_code=status.HTTP_200_OK,
    summary="Get track by Content ID",
)
def get_track_by_id(
    content_id: str,
    db: Session = Depends(get_db),
) -> TrackOut:
    """Retrieve metadata for a specific registered track by its unique Content ID."""
    track = get_track_by_content_id(db, content_id)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track with Content ID '{content_id}' not found",
        )
    return TrackOut.model_validate(track)


@router.delete(
    "/tracks/{content_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=[Depends(require_admin)],
    summary="Delete track by Content ID",
)
def delete_track_by_id(
    content_id: str,
    db: Session = Depends(get_db),
) -> Response:
    """Delete a registered track and all of its associated fingerprints."""
    track = get_track_by_content_id(db, content_id)
    if track is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track with Content ID '{content_id}' not found",
        )
    delete_track(db, track.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
