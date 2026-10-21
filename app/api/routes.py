"""API routes for track registration and audio identification (P2.3 / P2.4)."""

from __future__ import annotations

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

router = APIRouter()


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


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register audio track and store fingerprints",
)
async def register(
    file: UploadFile = File(...),
    title: str = Form(...),
    owner: str = Form(...),
    db: Session = Depends(get_db),
) -> RegisterResponse:
    """Upload and register a full audio track with Content ID."""
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

    # Process audio in a threadpool to avoid blocking event loop
    try:
        _, duration, hashes = await run_in_threadpool(_process_audio_bytes, content)
    except AudioDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio decoding failed: {exc}",
        ) from exc

    # Duplicate check: check against existing fingerprints in the database
    query_hashes = [h for h, _ in hashes]
    db_hits = find_hits(db, query_hashes)
    if db_hits:
        dup_match = find_best_match(hashes, db_hits, min_score=settings.DUPLICATE_SCORE)
        if dup_match is not None and dup_match.score >= settings.DUPLICATE_SCORE:
            existing_track = get_track(db, dup_match.track_id)
            existing_content_id = existing_track.content_id if existing_track else "unknown"
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Track already registered",
                    "content_id": existing_content_id,
                },
            )

    # Persist track metadata and fingerprints
    track = create_track(
        db,
        title=title,
        owner=owner,
        duration_seconds=duration,
    )
    hashes_stored = add_fingerprints(db, track.id, hashes)

    return RegisterResponse(
        content_id=track.content_id,
        track_id=track.id,
        title=track.title,
        owner=track.owner,
        duration_seconds=track.duration_seconds,
        hashes_stored=hashes_stored,
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

    # Process clip in a threadpool to avoid blocking event loop
    try:
        _, duration, hashes = await run_in_threadpool(_process_audio_bytes, content)
    except AudioDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Audio decoding failed: {exc}",
        ) from exc

    # Reject query clips shorter than MIN_QUERY_SECONDS
    if duration < settings.MIN_QUERY_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Audio clip ({duration:.2f}s) is shorter than minimum required query duration "
                f"({settings.MIN_QUERY_SECONDS}s)"
            ),
        )

    # Query candidate database landmarks
    query_hashes = [h for h, _ in hashes]
    db_hits = find_hits(db, query_hashes)

    match = find_best_match(hashes, db_hits)
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
