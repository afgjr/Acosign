"""Integration tests for FastAPI endpoints POST /register and POST /identify (P2.4).

Uses TestClient with an in-memory SQLite database override (no PostgreSQL).
All audio test data is generated synthetically using numpy and soundfile.
"""

from __future__ import annotations

import io
from fastapi.testclient import TestClient
import numpy as np
import pytest
from sqlalchemy.orm import Session
import soundfile as sf

from app.api.routes import trim_query_audio
from app.core.config import settings
from app.db.models import Track


def _generate_wav(duration: float = 8.0, freqs: list[list[float]] | None = None) -> bytes:
    """Generate a multi-tone harmonic WAV in memory."""
    sr = settings.SAMPLE_RATE
    total_samples = int(sr * duration)
    t = np.linspace(0, duration, total_samples, endpoint=False, dtype=np.float32)
    audio = np.zeros_like(t)

    chord_list = freqs or [
        [261, 329, 392, 523, 659],
        [293, 369, 440, 587, 739],
        [329, 415, 493, 659, 830],
        [349, 440, 523, 698, 880],
        [392, 493, 587, 783, 987],
        [440, 554, 659, 880, 1108],
        [493, 622, 739, 987, 1244],
        [523, 659, 783, 1046, 1318],
        [587, 739, 880, 1174, 1479],
        [659, 830, 987, 1318, 1661],
    ]

    for sec_i, chord in enumerate(chord_list):
        s_idx = int(sec_i * sr)
        e_idx = min(int((sec_i + 1) * sr), total_samples)
        if s_idx >= total_samples:
            break
        t_sec = t[s_idx:e_idx]
        sig = np.zeros_like(t_sec)
        for k, f in enumerate(chord):
            mod = 1.0 + 0.05 * np.sin(2.0 * np.pi * 5.0 * t_sec)
            sig += (1.0 / (k + 1)) * np.sin(2.0 * np.pi * f * mod * t_sec)
        audio[s_idx:e_idx] = sig

    max_val = float(np.max(np.abs(audio)))
    if max_val > 0:
        audio = audio / max_val

    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def _slice_wav(full_wav_bytes: bytes, start_sec: float, duration_sec: float) -> bytes:
    """Slice a portion of WAV audio bytes."""
    data, sr = sf.read(io.BytesIO(full_wav_bytes), dtype="float32")
    s_idx = int(round(start_sec * sr))
    e_idx = s_idx + int(round(duration_sec * sr))
    sliced = data[s_idx:e_idx]

    buf = io.BytesIO()
    sf.write(buf, sliced, sr, format="WAV")
    return buf.getvalue()


ADMIN_HEADERS = {"X-API-Key": "test-admin-key"}


def test_register_track_success_and_stored_in_db(
    client: TestClient, db_session: Session
) -> None:
    """POST /register returns 201 and a content_id; track appears in the database."""
    wav_bytes = _generate_wav(duration=6.0)

    res = client.post(
        "/register",
        data={"title": "Test Symphony", "owner": "Alice"},
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )

    assert res.status_code == 201
    payload = res.json()
    assert "content_id" in payload
    assert payload["title"] == "Test Symphony"
    assert payload["owner"] == "Alice"
    assert payload["duration_seconds"] > 5.0
    assert payload["hashes_stored"] > 0

    # Verify track exists in database
    track = db_session.get(Track, payload["track_id"])
    assert track is not None
    assert track.content_id == payload["content_id"]
    assert track.title == "Test Symphony"


def test_identify_middle_clip_matched_true_with_metadata(
    client: TestClient,
) -> None:
    """POST /identify with a middle clip returns matched=true with correct title/owner."""
    full_wav = _generate_wav(duration=10.0)

    # Register track first
    reg_res = client.post(
        "/register",
        data={"title": "Master Track", "owner": "Producer X"},
        files={"file": ("master.wav", full_wav, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert reg_res.status_code == 201
    content_id = reg_res.json()["content_id"]

    # Extract a 4-second middle clip from 3.0s to 7.0s
    clip_wav = _slice_wav(full_wav, start_sec=3.0, duration_sec=4.0)

    id_res = client.post(
        "/identify",
        files={"file": ("clip.wav", clip_wav, "audio/wav")},
    )

    assert id_res.status_code == 200
    payload = id_res.json()
    assert payload["matched"] is True
    assert payload["content_id"] == content_id
    assert payload["title"] == "Master Track"
    assert payload["owner"] == "Producer X"
    assert payload["score"] >= settings.MIN_MATCH_SCORE
    assert payload["match_strength"] in ("strong", "weak")
    assert abs(payload["offset_seconds"] - 3.0) < 0.5


def test_identify_unrelated_audio_returns_matched_false(
    client: TestClient,
) -> None:
    """POST /identify on unrelated audio returns matched=false with 200 OK (never 404)."""
    full_wav = _generate_wav(duration=8.0)
    client.post(
        "/register",
        data={"title": "Known Song", "owner": "Known Artist"},
        files={"file": ("known.wav", full_wav, "audio/wav")},
        headers=ADMIN_HEADERS,
    )

    # Generate completely unrelated audio (different frequencies)
    unrelated_chords = [
        [150, 225, 337],
        [160, 240, 360],
        [170, 255, 382],
        [180, 270, 405],
    ]
    unrelated_wav = _generate_wav(duration=4.0, freqs=unrelated_chords)

    res = client.post(
        "/identify",
        files={"file": ("unrelated.wav", unrelated_wav, "audio/wav")},
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload["matched"] is False
    assert payload["content_id"] is None
    assert payload["title"] is None
    assert payload["owner"] is None


def test_bad_inputs_empty_garbage_and_short_clip_return_400(
    client: TestClient,
) -> None:
    """Empty file, garbage bytes, and a clip < 3s all return 400 with a clear message."""
    # 1. Empty file
    res_empty_reg = client.post(
        "/register",
        data={"title": "Empty", "owner": "Tester"},
        files={"file": ("empty.wav", b"", "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_empty_reg.status_code == 400
    assert "empty" in res_empty_reg.text.lower()

    res_empty_id = client.post(
        "/identify",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert res_empty_id.status_code == 400
    assert "empty" in res_empty_id.text.lower()

    # 2. Garbage non-audio bytes
    garbage = b"THIS_IS_NOT_AN_AUDIO_FILE_JUST_RANDOM_GARBAGE"
    res_garbage_reg = client.post(
        "/register",
        data={"title": "Garbage", "owner": "Tester"},
        files={"file": ("garbage.wav", garbage, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_garbage_reg.status_code == 400
    assert "decoding failed" in res_garbage_reg.text.lower()

    res_garbage_id = client.post(
        "/identify",
        files={"file": ("garbage.wav", garbage, "audio/wav")},
    )
    assert res_garbage_id.status_code == 400

    # 3. Clip shorter than MIN_QUERY_SECONDS (2.0s < 3.0s)
    short_wav = _generate_wav(duration=2.0)
    res_short = client.post(
        "/identify",
        files={"file": ("short.wav", short_wav, "audio/wav")},
    )
    assert res_short.status_code == 400
    assert "shorter than minimum" in res_short.text.lower()


def test_oversized_upload_returns_413(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upload exceeding MAX_UPLOAD_MB returns 413 Payload Too Large."""
    # Set MAX_UPLOAD_MB to 1 MB for fast test execution
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)

    oversized_data = b"0" * (1024 * 1024 + 1024)  # 1 MB + 1 KB

    res = client.post(
        "/register",
        data={"title": "Too Big", "owner": "Tester"},
        files={"file": ("big.wav", oversized_data, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res.status_code == 413
    assert "exceeds maximum size" in res.text.lower()


def test_register_same_audio_twice_returns_409(
    client: TestClient,
) -> None:
    """Registering the same audio twice returns 409 Conflict with the existing content_id."""
    wav_bytes = _generate_wav(duration=8.0)

    # First registration
    res1 = client.post(
        "/register",
        data={"title": "Original Track", "owner": "Artist 1"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res1.status_code == 201
    existing_content_id = res1.json()["content_id"]

    # Second registration with the exact same audio
    res2 = client.post(
        "/register",
        data={"title": "Duplicate Upload", "owner": "Artist 2"},
        files={"file": ("duplicate.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res2.status_code == 409
    assert existing_content_id in res2.text


def test_missing_required_fields_returns_422(
    client: TestClient,
) -> None:
    """Missing required multipart form fields returns 422 Unprocessable Entity."""
    wav_bytes = _generate_wav(duration=4.0)

    # Missing title
    res_no_title = client.post(
        "/register",
        data={"owner": "Artist"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_no_title.status_code == 422

    # Missing file
    res_no_file = client.post(
        "/register",
        data={"title": "Song", "owner": "Artist"},
        headers=ADMIN_HEADERS,
    )
    assert res_no_file.status_code == 422


def test_health_endpoint_reports_database_ok_and_unreachable(
    client: TestClient, db_session: Session
) -> None:
    """GET /health reports status 'ok' and database 'ok' (or 'unreachable') without raising."""
    # 1. Normal state with working database
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"

    # 2. Database connectivity failure (simulated)
    # Monkeypatch execute on db_session to raise an exception
    def _failing_execute(*args, **kwargs):
        raise RuntimeError("Simulated DB connection failure")

    orig_execute = db_session.execute
    try:
        db_session.execute = _failing_execute
        res_fail = client.get("/health")
        assert res_fail.status_code == 200
        fail_data = res_fail.json()
        assert fail_data["status"] == "ok"
        assert fail_data["database"] == "unreachable"
    finally:
        db_session.execute = orig_execute


def test_list_tracks_pagination_and_limit_capped(
    client: TestClient,
) -> None:
    """GET /tracks supports pagination and caps limit at 100."""
    # Register 3 tracks with distinct audio frequencies so deduplication does not trigger
    for i in range(3):
        base_f = 200 + i * 350
        chords = [[base_f, base_f * 1.25, base_f * 1.5, base_f * 2.0]] * 4
        wav_bytes = _generate_wav(duration=4.0, freqs=chords)
        reg_res = client.post(
            "/register",
            data={"title": f"Pagination Track {i}", "owner": "Artist"},
            files={"file": (f"track_{i}.wav", wav_bytes, "audio/wav")},
            headers=ADMIN_HEADERS,
        )
        assert reg_res.status_code == 201

    # Page 1: limit 2, offset 0 -> 2 tracks
    res1 = client.get("/tracks?limit=2&offset=0")
    assert res1.status_code == 200
    tracks1 = res1.json()
    assert len(tracks1) == 2

    # Page 2: limit 2, offset 2 -> 1 track
    res2 = client.get("/tracks?limit=2&offset=2")
    assert res2.status_code == 200
    tracks2 = res2.json()
    assert len(tracks2) == 1
    assert tracks2[0]["content_id"] not in [t["content_id"] for t in tracks1]

    # Limit capped at 100: passing limit=500 does not error and returns tracks
    res_capped = client.get("/tracks?limit=500&offset=0")
    assert res_capped.status_code == 200
    assert len(res_capped.json()) == 3


def test_get_track_by_content_id_success_and_not_found(
    client: TestClient,
) -> None:
    """GET /tracks/{content_id} returns track details or 404 for unknown content_id."""
    wav_bytes = _generate_wav(duration=4.0)
    reg_res = client.post(
        "/register",
        data={"title": "Single Track", "owner": "Solo Artist"},
        files={"file": ("single.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    content_id = reg_res.json()["content_id"]

    # Found
    res = client.get(f"/tracks/{content_id}")
    assert res.status_code == 200
    payload = res.json()
    assert payload["content_id"] == content_id
    assert payload["title"] == "Single Track"
    assert payload["owner"] == "Solo Artist"

    # Unknown content_id -> 404
    res_404 = client.get("/tracks/nonexistent_content_id_123")
    assert res_404.status_code == 404
    assert "not found" in res_404.text.lower()


def test_delete_track_then_identify_returns_matched_false(
    client: TestClient,
) -> None:
    """DELETE /tracks/{content_id} deletes track and cascading fingerprints; clip now fails to match."""
    full_wav = _generate_wav(duration=8.0)
    reg_res = client.post(
        "/register",
        data={"title": "To Be Deleted", "owner": "Ephemeral"},
        files={"file": ("to_delete.wav", full_wav, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    content_id = reg_res.json()["content_id"]

    # Verify query clip matches before deletion
    clip_wav = _slice_wav(full_wav, start_sec=2.0, duration_sec=4.0)
    id_before = client.post("/identify", files={"file": ("clip.wav", clip_wav, "audio/wav")})
    assert id_before.status_code == 200
    assert id_before.json()["matched"] is True

    # Delete track -> 204 No Content
    del_res = client.delete(f"/tracks/{content_id}", headers=ADMIN_HEADERS)
    assert del_res.status_code == 204
    assert del_res.text == ""

    # GET /tracks/{content_id} now returns 404
    get_after = client.get(f"/tracks/{content_id}")
    assert get_after.status_code == 404

    # Identify of the same clip now returns matched=False
    id_after = client.post("/identify", files={"file": ("clip.wav", clip_wav, "audio/wav")})
    assert id_after.status_code == 200
    assert id_after.json()["matched"] is False


def test_delete_unknown_track_returns_404(
    client: TestClient,
) -> None:
    """DELETE /tracks/{content_id} with unknown content_id returns 404."""
    res = client.delete("/tracks/unknown_content_id_999", headers=ADMIN_HEADERS)
    assert res.status_code == 404
    assert "not found" in res.text.lower()


def test_global_exception_handler_returns_500_without_stacktrace(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unexpected internal server errors return 500 JSON without leaking stack traces."""
    # Force an unhandled RuntimeError inside an endpoint
    from app.api import routes

    def _crash(*args, **kwargs):
        raise RuntimeError("Sensitive internal database connection failure with credentials")

    monkeypatch.setattr(routes, "list_tracks", _crash)

    test_client = TestClient(client.app, raise_server_exceptions=False)
    res = test_client.get("/tracks")
    assert res.status_code == 500
    assert res.json() == {"detail": "Internal error"}
    # Ensure raw exception text/stack trace was not leaked to client
    assert "Sensitive" not in res.text
    assert "RuntimeError" not in res.text
    assert "credentials" not in res.text


def test_register_without_key_returns_401(client: TestClient) -> None:
    """POST /register without X-API-Key header returns 401 Unauthorized."""
    wav_bytes = _generate_wav(duration=4.0)
    res = client.post(
        "/register",
        data={"title": "No Key Track", "owner": "Artist"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
    )
    assert res.status_code == 401
    assert res.json() == {"detail": "Invalid or missing admin key"}


def test_register_with_wrong_key_returns_401(client: TestClient) -> None:
    """POST /register with invalid X-API-Key returns 401 Unauthorized."""
    wav_bytes = _generate_wav(duration=4.0)
    res = client.post(
        "/register",
        data={"title": "Wrong Key Track", "owner": "Artist"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers={"X-API-Key": "incorrect-secret-key"},
    )
    assert res.status_code == 401
    assert res.json() == {"detail": "Invalid or missing admin key"}


def test_register_with_right_key_returns_201(client: TestClient) -> None:
    """POST /register with valid X-API-Key returns 201 Created."""
    wav_bytes = _generate_wav(duration=4.0)
    res = client.post(
        "/register",
        data={"title": "Auth Track", "owner": "Artist"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res.status_code == 201
    assert "content_id" in res.json()


def test_delete_without_key_returns_401(client: TestClient) -> None:
    """DELETE /tracks/{content_id} without X-API-Key returns 401 Unauthorized."""
    res = client.delete("/tracks/some-content-id")
    assert res.status_code == 401
    assert res.json() == {"detail": "Invalid or missing admin key"}


def test_empty_admin_api_key_returns_503_for_register_and_delete(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ADMIN_API_KEY is empty/unset, admin endpoints fail closed with 503."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")

    wav_bytes = _generate_wav(duration=4.0)
    # 1. Register with header -> 503
    res_reg = client.post(
        "/register",
        data={"title": "Track", "owner": "Artist"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_reg.status_code == 503
    assert res_reg.json() == {"detail": "Admin key not configured"}

    # 2. Register without header -> 503 (fails closed before checking header)
    res_reg_no_hdr = client.post(
        "/register",
        data={"title": "Track", "owner": "Artist"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
    )
    assert res_reg_no_hdr.status_code == 503
    assert res_reg_no_hdr.json() == {"detail": "Admin key not configured"}

    # 3. Delete with header -> 503
    res_del = client.delete("/tracks/some-id", headers=ADMIN_HEADERS)
    assert res_del.status_code == 503
    assert res_del.json() == {"detail": "Admin key not configured"}

    # 4. Delete without header -> 503
    res_del_no_hdr = client.delete("/tracks/some-id")
    assert res_del_no_hdr.status_code == 503
    assert res_del_no_hdr.json() == {"detail": "Admin key not configured"}


def test_public_endpoints_identify_and_get_tracks_work_without_key(
    client: TestClient,
) -> None:
    """POST /identify and GET /tracks remain public and require no admin key."""
    # Register a track using admin key so we have data
    wav_bytes = _generate_wav(duration=6.0)
    reg_res = client.post(
        "/register",
        data={"title": "Public Check Track", "owner": "Artist"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert reg_res.status_code == 201
    cid = reg_res.json()["content_id"]

    # GET /tracks without any header -> 200
    res_list = client.get("/tracks")
    assert res_list.status_code == 200
    assert any(t["content_id"] == cid for t in res_list.json())

    # GET /tracks/{content_id} without any header -> 200
    res_get = client.get(f"/tracks/{cid}")
    assert res_get.status_code == 200
    assert res_get.json()["content_id"] == cid

    # POST /identify without any header -> 200
    clip_bytes = _slice_wav(wav_bytes, start_sec=1.0, duration_sec=4.0)
    res_id = client.post(
        "/identify",
        files={"file": ("clip.wav", clip_bytes, "audio/wav")},
    )
    assert res_id.status_code == 200
    assert res_id.json()["matched"] is True


def test_register_with_all_metadata_and_read_back(client: TestClient) -> None:
    """Register a track with all optional metadata fields and read back via GET /tracks/{content_id}."""
    wav_bytes = _generate_wav(duration=6.0)
    reg_data = {
        "title": "Extended Track",
        "owner": "Sound Studio",
        "album": "Masterpieces",
        "genre": "Classical",
        "release_year": "2021",
        "isrc": "USRC17607839",
        "license_type": "Creative Commons BY-NC",
        "description": "A high fidelity test piece with multi-harmonic chords.",
    }

    res_reg = client.post(
        "/register",
        data=reg_data,
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_reg.status_code == 201
    payload = res_reg.json()
    cid = payload["content_id"]
    assert payload["album"] == "Masterpieces"
    assert payload["genre"] == "Classical"
    assert payload["release_year"] == 2021
    assert payload["isrc"] == "USRC17607839"
    assert payload["license_type"] == "Creative Commons BY-NC"
    assert payload["description"] == "A high fidelity test piece with multi-harmonic chords."

    # Read back via GET /tracks/{content_id}
    res_get = client.get(f"/tracks/{cid}")
    assert res_get.status_code == 200
    get_payload = res_get.json()
    assert get_payload["content_id"] == cid
    assert get_payload["album"] == "Masterpieces"
    assert get_payload["genre"] == "Classical"
    assert get_payload["release_year"] == 2021
    assert get_payload["isrc"] == "USRC17607839"
    assert get_payload["license_type"] == "Creative Commons BY-NC"
    assert get_payload["description"] == "A high fidelity test piece with multi-harmonic chords."


def test_register_with_no_optional_metadata_defaults_to_none(client: TestClient) -> None:
    """Registering with no optional metadata succeeds and fields default to None."""
    wav_bytes = _generate_wav(duration=6.0)
    res_reg = client.post(
        "/register",
        data={"title": "Minimal Track", "owner": "Bob"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_reg.status_code == 201
    payload = res_reg.json()
    cid = payload["content_id"]
    assert payload["album"] is None
    assert payload["genre"] is None
    assert payload["release_year"] is None
    assert payload["isrc"] is None
    assert payload["license_type"] is None
    assert payload["description"] is None

    # Read back via GET /tracks/{content_id}
    res_get = client.get(f"/tracks/{cid}")
    assert res_get.status_code == 200
    get_payload = res_get.json()
    assert get_payload["album"] is None
    assert get_payload["genre"] is None
    assert get_payload["release_year"] is None


def test_register_invalid_release_year_returns_422(client: TestClient) -> None:
    """Out-of-range release_year returns 422 Unprocessable Entity."""
    wav_bytes = _generate_wav(duration=4.0)

    # Year before 1900
    res_old = client.post(
        "/register",
        data={"title": "Too Old", "owner": "Historian", "release_year": "1899"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_old.status_code == 422

    # Year far in future
    res_future = client.post(
        "/register",
        data={"title": "Too Future", "owner": "SciFi", "release_year": "2099"},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_future.status_code == 422


def test_register_string_fields_exceeding_max_length_returns_422(client: TestClient) -> None:
    """String metadata fields exceeding length limits return 422."""
    wav_bytes = _generate_wav(duration=4.0)

    # album exceeding 200 chars
    res_album = client.post(
        "/register",
        data={"title": "Track", "owner": "Artist", "album": "A" * 201},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_album.status_code == 422

    # description exceeding 2000 chars
    res_desc = client.post(
        "/register",
        data={"title": "Track", "owner": "Artist", "description": "D" * 2001},
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert res_desc.status_code == 422


def test_identify_returns_new_metadata_fields(client: TestClient) -> None:
    """POST /identify returns extended metadata fields for matched track."""
    wav_bytes = _generate_wav(duration=8.0)
    reg_data = {
        "title": "Identifiable Track",
        "owner": "Producer",
        "album": "Synth Wave 80s",
        "genre": "Synthwave",
        "release_year": "1984",
        "isrc": "USABC8400001",
        "license_type": "Standard Commercial",
        "description": "Retro wave synth recording.",
    }
    reg_res = client.post(
        "/register",
        data=reg_data,
        files={"file": ("track.wav", wav_bytes, "audio/wav")},
        headers=ADMIN_HEADERS,
    )
    assert reg_res.status_code == 201
    cid = reg_res.json()["content_id"]

    # Query with a 4.0s slice
    clip_bytes = _slice_wav(wav_bytes, start_sec=2.0, duration_sec=4.0)
    ident_res = client.post(
        "/identify",
        files={"file": ("clip.wav", clip_bytes, "audio/wav")},
    )
    assert ident_res.status_code == 200
    payload = ident_res.json()
    assert payload["matched"] is True
    assert payload["content_id"] == cid
    assert payload["title"] == "Identifiable Track"
    assert payload["owner"] == "Producer"
    assert payload["album"] == "Synth Wave 80s"
    assert payload["genre"] == "Synthwave"
    assert payload["release_year"] == 1984
    assert payload["isrc"] == "USABC8400001"
    assert payload["license_type"] == "Standard Commercial"
    assert payload["description"] == "Retro wave synth recording."


def test_admin_verify_success_204(client: TestClient) -> None:
    """GET /admin/verify with valid X-API-Key returns 204 No Content."""
    res = client.get("/admin/verify", headers=ADMIN_HEADERS)
    assert res.status_code == 204
    assert res.text == ""


def test_admin_verify_missing_or_wrong_key_401(client: TestClient) -> None:
    """GET /admin/verify with missing or wrong key returns 401 Unauthorized."""
    # Missing key
    res_no_key = client.get("/admin/verify")
    assert res_no_key.status_code == 401
    assert res_no_key.json() == {"detail": "Invalid or missing admin key"}

    # Wrong key
    res_wrong_key = client.get("/admin/verify", headers={"X-API-Key": "wrong-key"})
    assert res_wrong_key.status_code == 401
    assert res_wrong_key.json() == {"detail": "Invalid or missing admin key"}


def test_admin_verify_key_unset_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GET /admin/verify when ADMIN_API_KEY is unconfigured returns 503."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "")
    res = client.get("/admin/verify", headers=ADMIN_HEADERS)
    assert res.status_code == 503
    assert res.json() == {"detail": "Admin key not configured"}


def _generate_long_wav(duration: float = 60.0) -> bytes:
    """Generate a multi-second harmonic WAV cycling through chords."""
    sr = settings.SAMPLE_RATE
    total_samples = int(sr * duration)
    t = np.linspace(0, duration, total_samples, endpoint=False, dtype=np.float32)
    base_chords = [
        [261, 329, 392, 523, 659],
        [293, 369, 440, 587, 739],
        [329, 415, 493, 659, 830],
        [349, 440, 523, 698, 880],
        [392, 493, 587, 783, 987],
        [440, 554, 659, 880, 1108],
        [493, 622, 739, 987, 1244],
        [523, 659, 783, 1046, 1318],
        [587, 739, 880, 1174, 1479],
        [659, 830, 987, 1318, 1661],
    ]
    audio = np.zeros_like(t)
    num_seconds = int(np.ceil(duration))
    for sec_i in range(num_seconds):
        chord = base_chords[sec_i % len(base_chords)]
        s_idx = int(sec_i * sr)
        e_idx = min(int((sec_i + 1) * sr), total_samples)
        if s_idx >= total_samples:
            break
        t_sec = t[s_idx:e_idx]
        sig = np.zeros_like(t_sec)
        for k, f in enumerate(chord):
            mod = 1.0 + 0.05 * np.sin(2.0 * np.pi * 5.0 * t_sec)
            sig += (1.0 / (k + 1)) * np.sin(2.0 * np.pi * f * mod * t_sec)
        audio[s_idx:e_idx] = sig

    max_val = float(np.max(np.abs(audio)))
    if max_val > 0:
        audio = audio / max_val

    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV")
    return buf.getvalue()


def test_trim_query_audio_exact_sample_count() -> None:
    """trim_query_audio returns exactly MAX_QUERY_SECONDS * SAMPLE_RATE samples from middle."""
    sr = settings.SAMPLE_RATE
    max_seconds = settings.MAX_QUERY_SECONDS
    expected_samples = int(max_seconds * sr)

    # 1. 60-second array is trimmed to exact sample count
    duration_60 = 60.0
    arr_60 = np.arange(int(duration_60 * sr), dtype=np.float32)
    trimmed_60 = trim_query_audio(arr_60)
    assert len(trimmed_60) == expected_samples

    # Verify that the middle window was sliced
    start_60 = (len(arr_60) - expected_samples) // 2
    np.testing.assert_array_equal(trimmed_60, arr_60[start_60 : start_60 + expected_samples])

    # 2. 25-second array is also trimmed to exact sample count
    duration_25 = 25.0
    arr_25 = np.arange(int(duration_25 * sr), dtype=np.float32)
    trimmed_25 = trim_query_audio(arr_25)
    assert len(trimmed_25) == expected_samples
    start_25 = (len(arr_25) - expected_samples) // 2
    np.testing.assert_array_equal(trimmed_25, arr_25[start_25 : start_25 + expected_samples])

    # 3. Audio shorter than or equal to MAX_QUERY_SECONDS is not trimmed
    duration_10 = 10.0
    arr_10 = np.arange(int(duration_10 * sr), dtype=np.float32)
    trimmed_10 = trim_query_audio(arr_10)
    assert len(trimmed_10) == len(arr_10)
    np.testing.assert_array_equal(trimmed_10, arr_10)


def test_identify_long_upload_trimmed_matches_track(
    client: TestClient,
    db_session: Session,
) -> None:
    """A 60-second synthetic upload is trimmed during identify and still matches registered track."""
    wav_60s = _generate_long_wav(duration=60.0)

    # Register full 60-second track
    reg_res = client.post(
        "/register",
        headers=ADMIN_HEADERS,
        data={"title": "Symphony No. 60", "owner": "Philharmonic Studio"},
        files={"file": ("symphony.wav", wav_60s, "audio/wav")},
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert reg_data["content_id"] is not None

    # Identify with the same 60-second file (which will be trimmed to MAX_QUERY_SECONDS)
    ident_res = client.post(
        "/identify",
        files={"file": ("query_clip.wav", wav_60s, "audio/wav")},
    )
    assert ident_res.status_code == 200
    ident_data = ident_res.json()

    assert ident_data["matched"] is True
    assert ident_data["content_id"] == reg_data["content_id"]
    assert ident_data["title"] == "Symphony No. 60"
    assert ident_data["owner"] == "Philharmonic Studio"
    assert ident_data["score"] > 0



