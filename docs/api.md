# Acosign API Documentation

This document describes the REST API endpoints provided by Acosign for audio fingerprinting, registration, identification, and catalog management.

- **Base URL**: `http://localhost:8000` (default)
- **Content-Type**:
  - `multipart/form-data` for audio upload endpoints (`/register`, `/identify`)
  - `application/json` for query and metadata endpoints
- **CORS Support**: Configurable via `CORS_ORIGINS` (defaults to `*`).

---

## Error Handling & Status Codes

All errors return a structured JSON response with a descriptive `detail` field:

```json
{
  "detail": "Error description or message"
}
```

The API uses standard HTTP response codes:
- **`200 OK`**: Request succeeded (metadata queries, identification matches).
- **`201 Created`**: Track successfully registered.
- **`204 No Content`**: Track successfully deleted; no response body returned.
- **`400 Bad Request`**: Audio could not be decoded, audio file is empty, or snippet duration is too short (< 3.0s for `/identify`).
- **`404 Not Found`**: The requested `content_id` does not exist.
- **`409 Conflict`**: Track is a duplicate (the audio strongly matches an already registered track).
- **`413 Payload Too Large`**: Uploaded audio exceeds `MAX_UPLOAD_MB` (default: 25 MB).
- **`422 Unprocessable Entity`**: Request validation error (e.g. missing form fields or invalid parameters).
- **`500 Internal Server Error`**: Unexpected server error. Returns `{"detail": "Internal error"}` with full diagnostics logged server-side (no stack traces leaked).

---

## Endpoints

### 1. Health Check

```http
GET /health
```

Checks API readiness and database connectivity. Always returns HTTP 200 without raising exceptions, indicating whether the database is currently reachable.

#### Request
- **Headers**: None
- **Body**: None

#### Response
- **Status**: `200 OK`
- **Body** (`application/json`):
```json
{
  "status": "ok",
  "database": "ok"
}
```
*(If database connection fails, `"database": "unreachable"` is returned with status 200).*

#### Curl Example
```bash
curl -X GET http://localhost:8000/health
```

---

### 2. Register Track

```http
POST /register
```

Processes an audio file through the STFT spectrogram and landmark peak pairing pipeline, generates 34-bit combinatorial hashes, verifies that the audio is not already registered under another track, and persists the track metadata and fingerprint hashes in the database.

#### Request Fields (`multipart/form-data`)
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | Binary File | Yes | Audio file (WAV, MP3, FLAC, OGG). Max size: 25 MB (`MAX_UPLOAD_MB`). |
| `title` | string | Yes | Track title (e.g. `"Midnight Groove"`). |
| `owner` | string | Yes | Rights holder or artist name (e.g. `"Studio Records"`). |

#### Responses
- **`201 Created`**: Track registered successfully.
  ```json
  {
    "content_id": "b3f090d81d2f447781f3d81b83dfaa90",
    "track_id": 1,
    "title": "Midnight Groove",
    "owner": "Studio Records",
    "duration_seconds": 182.4,
    "hashes_stored": 8420
  }
  ```
- **`400 Bad Request`**: Empty file or unreadable audio format.
  ```json
  {
    "detail": "Failed to decode audio file: format not recognized"
  }
  ```
- **`409 Conflict`**: Duplicate track detected.
  ```json
  {
    "detail": "Track already registered (matches content_id 'b3f090d81d2f447781f3d81b83dfaa90' with score 145)"
  }
  ```
- **`413 Payload Too Large`**: File exceeds upload limit.
  ```json
  {
    "detail": "File size 28.40 MB exceeds limit of 25 MB"
  }
  ```
- **`422 Unprocessable Entity`**: Missing form fields.

#### Curl Example
```bash
curl -X POST http://localhost:8000/register \
  -F "file=@/path/to/song.wav" \
  -F "title=Midnight Groove" \
  -F "owner=Studio Records"
```

---

### 3. Identify Audio Clip

```http
POST /identify
```

Takes a short query audio clip (minimum 3.0 seconds), computes fingerprint hashes, queries the inverted database index for matching hashes, and runs temporal offset alignment voting to identify the matching track.

#### Request Fields (`multipart/form-data`)
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | Binary File | Yes | Audio snippet (minimum 3.0 seconds duration). |

#### Responses
- **`200 OK` (Match Found)**:
  ```json
  {
    "matched": true,
    "content_id": "b3f090d81d2f447781f3d81b83dfaa90",
    "title": "Midnight Groove",
    "owner": "Studio Records",
    "score": 84,
    "match_strength": "strong",
    "offset_seconds": 14.52
  }
  ```
- **`200 OK` (No Match Found)**:
  ```json
  {
    "matched": false,
    "content_id": null,
    "title": null,
    "owner": null,
    "score": null,
    "match_strength": null,
    "offset_seconds": null
  }
  ```
- **`400 Bad Request`**: Audio shorter than 3.0 seconds, empty, or unreadable format.
  ```json
  {
    "detail": "Audio clip too short (1.80s). Minimum duration for identification is 3.0 seconds."
  }
  ```
- **`413 Payload Too Large`**: File exceeds upload limit.
- **`422 Unprocessable Entity`**: Missing `file` form part.

> **Note on `match_strength` vs `confidence`**:
> The `match_strength` field is derived directly from the alignment peak `score` (`"strong"` if `score >= 30`, otherwise `"weak"` for partial candidate alignments). The internal engine `confidence` ratio (`score / clip_hashes`) is not exposed in the API to maintain a clean, resilient contract that decouples clients from raw fingerprint densities.

#### Curl Example
```bash
curl -X POST http://localhost:8000/identify \
  -F "file=@/path/to/recorded_clip.wav"
```

---

### 4. List Registered Tracks

```http
GET /tracks?limit=20&offset=0
```

Returns a paginated list of registered tracks in the database, ordered by creation time descending.

#### Query Parameters
| Parameter | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `limit` | integer | `20` | `1 <= limit`, capped at `100` | Maximum number of tracks to return. Values greater than 100 are automatically capped at 100. |
| `offset` | integer | `0` | `0 <= offset` | Number of tracks to skip for pagination. |

#### Responses
- **`200 OK`**:
  ```json
  [
    {
      "id": 1,
      "content_id": "b3f090d81d2f447781f3d81b83dfaa90",
      "title": "Midnight Groove",
      "owner": "Studio Records",
      "duration_seconds": 182.4,
      "created_at": "2026-10-21T12:00:00Z"
    }
  ]
  ```
- **`422 Unprocessable Entity`**: Invalid parameter types or negative offsets.

#### Curl Example
```bash
curl -X GET "http://localhost:8000/tracks?limit=10&offset=0"
```

---

### 5. Get Track by Content ID

```http
GET /tracks/{content_id}
```

Fetches track metadata for a single track identified by its unique Content ID.

#### Path Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `content_id` | string | Yes | Unique Content ID hex string of the track. |

#### Responses
- **`200 OK`**:
  ```json
  {
    "id": 1,
    "content_id": "b3f090d81d2f447781f3d81b83dfaa90",
    "title": "Midnight Groove",
    "owner": "Studio Records",
    "duration_seconds": 182.4,
    "created_at": "2026-10-21T12:00:00Z"
  }
  ```
- **`404 Not Found`**:
  ```json
  {
    "detail": "Track with Content ID 'b3f090d81d2f447781f3d81b83dfaa90' not found"
  }
  ```

#### Curl Example
```bash
curl -X GET http://localhost:8000/tracks/b3f090d81d2f447781f3d81b83dfaa90
```

---

### 6. Delete Track

```http
DELETE /tracks/{content_id}
```

Deletes the track metadata and all associated fingerprint hashes via cascading database delete. Subsequent calls to `/identify` using clips from this track will return `matched: false`.

#### Path Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `content_id` | string | Yes | Unique Content ID hex string of the track. |

#### Responses
- **`204 No Content`**: Track and its fingerprints successfully removed. Response has an empty body.
- **`404 Not Found`**:
  ```json
  {
    "detail": "Track with Content ID 'b3f090d81d2f447781f3d81b83dfaa90' not found"
  }
  ```

#### Curl Example
```bash
curl -i -X DELETE http://localhost:8000/tracks/b3f090d81d2f447781f3d81b83dfaa90
```
