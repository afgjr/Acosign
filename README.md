<h1 align="center">Acosign</h1>

<p align="center">
  <b>Audio Digital Signature & Content ID Platform</b><br>
  <i>An API platform that converts audio into unique digital signatures for copyright protection and ownership verification.</i>
</p>

---

## Developer

| Name | ID | GitHub | Role |
|------|----|--------|------|
| **Abel Fekede** | CTC-5298-26 | [@afgjr](https://github.com/afgjr) | Full Stack Developer |

---

## 💡 What is This Project?

This project is a platform that takes an audio file, generates a unique **digital signature (acoustic fingerprint)** from it, stores that signature in a database, and assigns it a unique **Content ID**.

Once registered, the platform provides an **API** so that users, apps, or platforms can upload an unknown audio clip to check if it matches any registered sound in the database.

---

## ⚙️ How It Works (Simple Flow)

1. **Upload Audio:** An artist or owner uploads an audio track (MP3/WAV).
2. **Generate Signature:** The system analyzes the audio frequencies and converts the sound into a unique digital signature.
3. **Store & Assign Content ID:** The signature is saved in the database with a unique Content ID and owner details.
4. **Search / Verification API:** 
   - A user sends any audio snippet to the API.
   - The platform extracts its signature and searches the database.
   - If a match is found, the API returns the Content ID, track title, and owner.

---

## 🚀 Quick Start

> **Note:** Full containerized deployment via Docker Compose will be detailed here once the Docker service stack setup is finalized.

```bash
# Clone the repository
git clone https://github.com/afgjr/Acosign.git
cd Acosign

# Copy environment file
cp .env.example .env

# Run services with Docker Compose (coming in Phase 3)
# docker compose up -d
```

---

## 📡 API Overview

Acosign provides a REST API built with FastAPI for track registration, query identification, catalog management, and system health checks.

- **`GET /health`**: Health check reporting service status and database connectivity.
- **`POST /register`**: Upload an audio file, extract fingerprints, store them in the database, and return a unique `content_id`.
- **`POST /identify`**: Upload an unknown audio clip (minimum 3.0s) to identify matching registered tracks via peak offset alignment voting.
- **`GET /tracks`**: List registered tracks with pagination (`limit` capped at 100, `offset`).
- **`GET /tracks/{content_id}`**: Retrieve metadata for a specific registered track.
- **`DELETE /tracks/{content_id}`**: Delete a track and cascade-remove all associated fingerprint hashes.

---

## 🖥️ Demo UI

Acosign provides a Streamlit web interface for interactive fingerprint registration, audio query identification, and catalog exploration.

### Running the UI

Ensure your API backend is running (by default at `http://localhost:8000`), then start Streamlit:

```bash
# Optional: set custom backend URL (defaults to http://localhost:8000)
# export API_URL=http://localhost:8000

streamlit run ui/app.py
```

### UI Features & Tabs

- **Identify Tab (Default):**
  Hero section with one-tap recording via microphone (`st.audio_input`) or file snippet upload. Submits query audio to `POST /identify` and displays an inspection card with track title, owner, strength badge (`STRONG MATCH` / `WEAK MATCH`), score, temporal alignment offset, and an inline amplitude envelope waveform visualizer (for WAV clips). Displays a muted "No match found" card if unrecognized.
- **Register Tab:**
  Upload full audio tracks (`.mp3`, `.wav`, `.m4a`) and supply required metadata (Track Title and Owner). Extracts landmark peak pairs, stores hashes in PostgreSQL, and generates a unique Content ID. Protected by the Admin key.
- **Tracks Tab:**
  Catalog browser displaying all registered tracks formatted as row cards (`Title`, `Owner`, `Duration` in `mm:ss`, and short Content ID). Features catalog refresh and per-track deletion with confirmation, protected by the Admin key.
- **Developers Tab:**
  Developer portal and API quickstart. Displays the base URL, direct link to interactive FastAPI `/docs`, copyable `curl` and Python `requests` code snippets for `POST /identify`, an interactive "Try it" test box with raw JSON output, response field reference table, HTTP status code guide, and production notes.
- **Sidebar & Health Indicator:**
  Displays the active API base URL, real-time service and database health status (`GET /health`), and a password input for the Admin key.

---

## 🔐 Administrative Protection (`ADMIN_API_KEY`)

Acosign secures mutating administrative endpoints (`POST /register` and `DELETE /tracks/{content_id}`) with an API key dependency (`X-API-Key`).

### Setting the Admin Key

Set `ADMIN_API_KEY` in your `.env` file or environment:

```env
ADMIN_API_KEY=change_me_admin_key
```

- When accessing the Streamlit UI, enter your admin key in the **Admin key** field in the sidebar. When left empty, register and delete actions remain locked.
- **Demo Pre-registration:** Demo audio tracks are pre-registered by the administrator. Normal users can immediately identify audio snippets in the **Identify** tab without needing administrative privileges.

---


## 🎵 Supported Audio Formats

- **Officially Supported:** `MP3` and `WAV` (native decoding via SoundFile/librosa).
- **Conditional Support:** `M4A` (works only when `ffmpeg` is installed on the host system or container).

---

## ⚠️ Known Limits

- **Acoustic Noise Degradation:** Under heavy background noise (SNR 10 dB), short 5-second clips achieve ~77% identification accuracy.
- **Minimum Query Length:** Query clips require at least 3.0 seconds of audio to extract sufficient landmark pairs for reliable identification.
- **Single-Track Baseline:** Robustness benchmarks to date were evaluated on single-track baselines; see [docs/testing.md](docs/testing.md) for full benchmark tables and parameter evaluations.

---

## 🧪 Testing

The test suite contains pure unit tests and integration tests using synthetic, deterministically generated multi-tone audio (using an in-memory SQLite database override).

To run the full test suite:

```bash
python -m pytest -q
```

---

## 🎯 Use Cases

- **Royalty Tracking:** Check when and where registered audio is being played.
- **Copyright Check:** Allow music platforms or streaming apps to check if uploaded audio already belongs to someone else.
- **Audio Identification:** A Shazam-style search API for apps to identify music tracks from short audio clips.

---

## 🛠 Tech Stack

- **Backend / API:** FastAPI (Python)
- **Audio Processing:** Librosa / NumPy / SciPy
- **Database:** PostgreSQL (SQLAlchemy 2.0)
- **Frontend / Demo:** Streamlit
- **Deployment:** Docker & Docker Compose
