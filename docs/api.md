# Acosign API Documentation

This document describes the REST API endpoints provided by Acosign for audio fingerprinting, registration, identification, and catalog management.

- **Base URL**: `http://localhost:8000` (default)
- **Content-Type**:
  - `multipart/form-data` for audio upload endpoints (`/register`, `/identify`)
  - `application/json` for query and metadata endpoints
- **CORS Support**: Configurable via `CORS_ORIGINS` (defaults to `*`).

---

## Authentication

Acosign uses API key authentication to safeguard administrative operations.

- **Protected Endpoints**:
  - `POST /register` (catalog ingestion)
  - `DELETE /tracks/{content_id}` (catalog deletion)
  - `GET /admin/verify` (admin key validation)
- **Public Endpoints**:
  - `GET /health`
  - `POST /identify`
  - `GET /tracks`
  - `GET /tracks/{content_id}`

### How to Authenticate
Pass your secret admin key in the **`X-API-Key`** request header:

```http
X-API-Key: your_admin_api_key_here
```

### Security & Operational Behavior
- **Timing-Attack Protection**: Keys are validated in constant time using `secrets.compare_digest`.
- **Fail Closed**: If `ADMIN_API_KEY` is empty or unconfigured on the server, protected endpoints return **`503 Service Unavailable`** (`{"detail": "Admin key not configured"}`) instead of opening up.
- **Redaction**: Keys are never logged to console or logs, nor echoed in response bodies or errors.

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
- **`401 Unauthorized`**: Missing or invalid admin API key on protected endpoints.
- **`404 Not Found`**: The requested `content_id` does not exist.
- **`409 Conflict`**: Track is a duplicate (the audio strongly matches an already registered track).
- **`413 Payload Too Large`**: Uploaded audio exceeds `MAX_UPLOAD_MB` (default: 25 MB).
- **`422 Unprocessable Entity`**: Request validation error (e.g. missing form fields or invalid parameters).
- **`500 Internal Server Error`**: Unexpected server error. Returns `{"detail": "Internal error"}` with full diagnostics logged server-side (no stack traces leaked).
- **`503 Service Unavailable`**: Administrative endpoint called while `ADMIN_API_KEY` is unconfigured on the server.

---

## Endpoints

### 1. Health Check

```http
GET /health
```

Checks API readiness and database connectivity. Always returns HTTP 200 without raising exceptions, indicating whether the database is currently reachable. Public endpoint (no key required).

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

> **Protected Endpoint**: Requires valid `X-API-Key` header.

#### Request Headers
| Header | Type | Required | Description |
|---|---|---|---|
| `X-API-Key` | string | Yes | Administrator API key. |

#### Request Fields (`multipart/form-data`)
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | Binary File | Yes | Audio file (WAV, MP3, FLAC, OGG, M4A, AAC; FFmpeg fallback supported). Max size: 25 MB (`MAX_UPLOAD_MB`). Up to 600s decoded (`MAX_DECODE_SECONDS`). |
| `title` | string | Yes | Track title (e.g. `"Midnight Groove"`). |
| `owner` | string | Yes | Rights holder or artist name (e.g. `"Studio Records"`). |
| `album` | string | No | Album or collection name (max 200 chars). |
| `genre` | string | No | Musical genre (max 200 chars). |
| `release_year` | integer | No | Release year (1900 to current year + 1). |
| `isrc` | string | No | International Standard Recording Code (max 200 chars). |
| `license_type` | string | No | Licensing or usage terms (max 200 chars). |
| `description` | string | No | Description or contextual notes (max 2000 chars). |

#### Responses
- **`201 Created`**: Track registered successfully.
  ```json
  {
    "content_id": "b3f090d81d2f447781f3d81b83dfaa90",
    "track_id": 1,
    "title": "Midnight Groove",
    "owner": "Studio Records",
    "duration_seconds": 182.4,
    "hashes_stored": 8420,
    "album": "Night Sessions",
    "genre": "Lo-Fi Jazz",
    "release_year": 2024,
    "isrc": "USRC17607839",
    "license_type": "All Rights Reserved",
    "description": "Original studio master recording."
  }
  ```
- **`400 Bad Request`**: Empty file or unreadable audio format.
  ```json
  {
    "detail": "Failed to decode audio file: format not recognized"
  }
  ```
- **`401 Unauthorized`**: Missing or incorrect `X-API-Key` header.
  ```json
  {
    "detail": "Invalid or missing admin key"
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
- **`503 Service Unavailable`**: `ADMIN_API_KEY` is not configured on the server.
  ```json
  {
    "detail": "Admin key not configured"
  }
  ```

#### Curl Example
```bash
curl -X POST http://localhost:8000/register \
  -H "X-API-Key: YOUR_ADMIN_KEY" \
  -F "file=@/path/to/song.wav" \
  -F "title=Midnight Groove" \
  -F "owner=Studio Records"
```

---

### 3. Identify Audio Clip

```http
POST /identify
```

Takes a short query audio clip (minimum 3.0 seconds), computes fingerprint hashes, queries the inverted database index for matching hashes, and runs temporal offset alignment voting to identify the matching track. Public endpoint (no key required).

> **Trimming Rule**: If query audio exceeds `MAX_QUERY_SECONDS` (default: 20.0 seconds), the audio is automatically trimmed after decoding to a window of that exact duration from the middle of the audio (`MAX_QUERY_SECONDS * SAMPLE_RATE` samples). This provides optimal recognition performance on long uploads. Trimming applies exclusively to `/identify` and is never applied to `/register`.

#### Request Fields (`multipart/form-data`)
| Field | Type | Required | Description |
|---|---|---|---|
| `file` | Binary File | Yes | Audio snippet (minimum 3.0 seconds duration; WAV, MP3, M4A, FLAC, OGG, AAC; FFmpeg fallback supported). Clips longer than 20s are trimmed to the middle window. |

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
    "offset_seconds": 14.52,
    "album": "Night Sessions",
    "genre": "Lo-Fi Jazz",
    "release_year": 2024,
    "isrc": "USRC17607839",
    "license_type": "All Rights Reserved",
    "description": "Original studio master recording."
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
    "offset_seconds": null,
    "album": null,
    "genre": null,
    "release_year": null,
    "isrc": null,
    "license_type": null,
    "description": null
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

Returns a paginated list of registered tracks in the database, ordered by creation time descending. Public endpoint (no key required).

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

Fetches track metadata for a single track identified by its unique Content ID. Public endpoint (no key required).

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

> **Protected Endpoint**: Requires valid `X-API-Key` header.

#### Request Headers
| Header | Type | Required | Description |
|---|---|---|---|
| `X-API-Key` | string | Yes | Administrator API key. |

#### Path Parameters
| Parameter | Type | Required | Description |
|---|---|---|---|
| `content_id` | string | Yes | Unique Content ID hex string of the track. |

#### Responses
- **`204 No Content`**: Track and its fingerprints successfully removed. Response has an empty body.
- **`401 Unauthorized`**: Missing or incorrect `X-API-Key` header.
  ```json
  {
    "detail": "Invalid or missing admin key"
  }
  ```
- **`404 Not Found`**:
  ```json
  {
    "detail": "Track with Content ID 'b3f090d81d2f447781f3d81b83dfaa90' not found"
  }
  ```
- **`503 Service Unavailable`**: `ADMIN_API_KEY` is not configured on the server.
  ```json
  {
    "detail": "Admin key not configured"
  }
  ```

#### Curl Example
```bash
curl -i -X DELETE http://localhost:8000/tracks/b3f090d81d2f447781f3d81b83dfaa90 \
  -H "X-API-Key: YOUR_ADMIN_KEY"
```

---

### 7. Verify Admin Key

```http
GET /admin/verify
```

Verifies that the supplied administrative key is valid without performing any mutations. Returns HTTP 204 No Content when the key is authorized.

> **Protected Endpoint**: Requires valid `X-API-Key` header.

#### Request Headers
| Header | Type | Required | Description |
|---|---|---|---|
| `X-API-Key` | string | Yes | Administrator API key. |

#### Responses
- **`204 No Content`**: Admin key is valid. Response body is empty.
- **`401 Unauthorized`**: Missing or incorrect `X-API-Key` header.
  ```json
  {
    "detail": "Invalid or missing admin key"
  }
  ```
- **`503 Service Unavailable`**: `ADMIN_API_KEY` is not configured on the server.
  ```json
  {
    "detail": "Admin key not configured"
  }
  ```

#### Curl Example
```bash
curl -i -X GET http://localhost:8000/admin/verify \
  -H "X-API-Key: YOUR_ADMIN_KEY"
```
