<p align="center"><img src="ui/assets/favicon.png" width="64" alt="Acosign logo"/></p>
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

1. **Clone and enter the repository:**
   ```bash
   git clone https://github.com/afgjr/Acosign.git
   cd Acosign
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and configure your `ADMIN_API_KEY` (required for registering tracks and catalog administration).

   > [!IMPORTANT]
   > Change the default database credentials (`POSTGRES_PASSWORD` and `POSTGRES_USER`) in `.env` before any real or production deployment.

3. **Build and launch with Docker Compose:**
   ```bash
   docker compose up --build
   ```
   This builds and starts the PostgreSQL database (`db`), FastAPI backend (`api`), and Streamlit UI (`ui`).

4. **Access the services:**
   - **Web Application:** [http://localhost:8501](http://localhost:8501)
   - **Interactive API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **API Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

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

### UI Pages & Access Control

Acosign UI is built as a multi-page app with sidebar navigation and session-based admin authorization.

#### Public Pages (Visible to All Visitors)
- **Identify (Default):**
  Hero section with one-tap recording via microphone (`st.audio_input`) or file snippet upload (`.mp3`, `.wav`, `.m4a`). Submits query audio to `POST /identify` and displays an inspection card with track title, owner, metadata (album, genre, release year), strength badge (`STRONG MATCH` in green vs. `WEAK MATCH` in orange), score, temporal alignment offset, and an inline amplitude envelope waveform visualizer (for WAV clips). Displays a muted "No match found" card if unrecognized.
- **Tracks (Read-Only):**
  Public catalog browser with a search box filtering tracks by title or owner. Renders clean row cards showing track title, owner, genre, year, and duration (`mm:ss`). Does not permit catalog modifications.
- **Developers:**
  API documentation and interactive testing portal. Features copyable `curl` and Python `requests` quickstart code snippets, direct link to FastAPI `/docs`, an interactive "Try it" test box with raw JSON output, status code definitions, and response field specifications.

#### Admin-Only Pages (Unlocked via Admin Login)
- **Register (2-Step Ingestion Wizard):**
  - **Step 1:** Upload master audio file (`.mp3`, `.wav`, `.m4a`) and verify via inline audio player preview (`st.audio`).
  - **Step 2:** Form input for required metadata (Title, Owner) and optional metadata (Album, Genre, Release Year, ISRC, License Type, Description). Submits to `POST /register` with administrative credentials.
- **Manage Tracks:**
  Catalog administration interface showing registered tracks with a per-track **Delete** button guarded by a two-step confirmation prompt calling `DELETE /tracks/{content_id}`.

#### Admin Login Flow
1. At the bottom of the sidebar, enter the secret admin key into the password field and click **Log in**.
2. The UI validates the key against `GET /admin/verify`:
   - `204 No Content`: The key is saved securely in `st.session_state` (never logged or printed), unlocking the **Register** and **Manage tracks** pages.
   - `401 Unauthorized`: Displays "Wrong admin key".
   - `503 Service Unavailable`: Displays "Admin not configured".
3. An active admin session can click **Log out** in the sidebar at any time to clear credentials and return to public mode.

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
