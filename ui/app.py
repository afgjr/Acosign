"""Acosign Streamlit UI application.

HTTP-only client communicating with the Acosign FastAPI backend.
Never imports from app/ (AGENT.md rule 9).
"""

from __future__ import annotations

import io
import os
from typing import Any
import wave

import numpy as np
import requests
import streamlit as st

# ─── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_API_URL = "http://localhost:8000"
API_URL = os.getenv("API_URL", DEFAULT_API_URL).rstrip("/")
REQUEST_TIMEOUT = 180  # seconds

st.set_page_config(
    page_title="Acosign",
    page_icon="🎵",
    layout="centered",
)

# ─── Design CSS ────────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
/* Base theme colors & typography */
:root {
    --bg-color: #0b0b0c;
    --surface-color: #1a1a1c;
    --text-color: #f5f5f4;
    --muted-color: #8a8a8f;
    --accent-yellow: #f5f26b;
}

body, .stApp {
    background-color: #0b0b0c !important;
    color: #f5f5f4 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Centered layout, max width ~560px, generous spacing */
.block-container {
    max-width: 560px !important;
    padding-top: 2rem !important;
    padding-bottom: 5rem !important;
    margin: 0 auto !important;
}

/* Headings */
h1, h2, h3, h4, .stHeading {
    color: #f5f5f4 !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #121214 !important;
    border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
}

/* Cards: 24px radius, no hard borders */
.aco-card {
    background-color: #1a1a1c;
    border-radius: 24px;
    padding: 24px;
    margin-bottom: 20px;
    border: none;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
}

.aco-track-row {
    background-color: #1a1a1c;
    border-radius: 24px;
    padding: 18px 22px;
    margin-bottom: 12px;
    border: none;
}

/* Buttons: pill-shaped (999px) */
.stButton > button,
button[kind="primary"],
button[kind="secondary"],
button[data-testid="baseButton-primary"],
button[data-testid="baseButton-secondary"] {
    border-radius: 999px !important;
    padding: 0.55rem 1.4rem !important;
    font-weight: 600 !important;
    border: none !important;
    transition: all 0.15s ease-in-out !important;
}

/* Primary button: yellow with black text */
.stButton > button[kind="primary"],
button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background-color: #f5f26b !important;
    color: #0b0b0c !important;
}
.stButton > button[kind="primary"]:hover,
button[kind="primary"]:hover {
    background-color: #f3ef4f !important;
    color: #000000 !important;
    box-shadow: 0 0 16px rgba(245, 242, 107, 0.35) !important;
}

/* Secondary button */
.stButton > button[kind="secondary"],
button[kind="secondary"],
button[data-testid="baseButton-secondary"] {
    background-color: #1a1a1c !important;
    color: #f5f5f4 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}
.stButton > button[kind="secondary"]:hover,
button[kind="secondary"]:hover {
    background-color: #262629 !important;
    color: #ffffff !important;
}

/* Pill-shaped inputs */
div[data-baseweb="input"],
.stTextInput > div > div {
    border-radius: 999px !important;
    background-color: #1a1a1c !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    padding: 2px 12px !important;
}
div[data-baseweb="input"]:focus-within {
    border-color: #f5f26b !important;
}
input.stTextInput {
    color: #f5f5f4 !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background-color: #1a1a1c !important;
    border-radius: 24px !important;
    border: 1px dashed rgba(255, 255, 255, 0.12) !important;
    padding: 10px 16px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #f5f26b !important;
}
[data-testid="stFileUploader"] button {
    border-radius: 999px !important;
}

/* Audio input mic widget */
[data-testid="stAudioInput"] {
    background-color: #1a1a1c !important;
    border-radius: 24px !important;
    padding: 10px !important;
    border: none !important;
}

/* Pill-shaped navigation tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: transparent;
    padding: 4px 0 16px 0;
    margin-bottom: 20px;
    border-bottom: none;
    justify-content: center;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 999px !important;
    padding: 8px 18px !important;
    background-color: #1a1a1c !important;
    color: #8a8a8f !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    border: none !important;
    height: auto !important;
}
.stTabs [aria-selected="true"] {
    background-color: #f5f26b !important;
    color: #0b0b0c !important;
    font-weight: 700 !important;
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}

/* Expanders */
.streamlit-expanderHeader {
    background-color: #1a1a1c !important;
    border-radius: 16px !important;
    color: #f5f5f4 !important;
    border: none !important;
}
.streamlit-expanderContent {
    background-color: #1a1a1c !important;
    border-bottom-left-radius: 16px !important;
    border-bottom-right-radius: 16px !important;
    border: none !important;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ─── Helper Functions ──────────────────────────────────────────────────────────
def extract_error_detail(response: requests.Response) -> str:
    """Extract clean, readable error detail message from FastAPI HTTP error response."""
    try:
        data = response.json()
        detail = data.get("detail", response.text)
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            messages = []
            for item in detail:
                if isinstance(item, dict):
                    loc = " -> ".join(str(x) for x in item.get("loc", []))
                    msg = item.get("msg", "")
                    messages.append(f"{loc}: {msg}" if loc else msg)
                else:
                    messages.append(str(item))
            return "; ".join(messages)
        if isinstance(detail, dict):
            return str(detail.get("message", detail))
        return str(detail)
    except Exception:
        return response.text or f"HTTP status {response.status_code}"


def check_api_health(base_url: str) -> tuple[bool, str]:
    """Call GET /health and return (is_healthy, status_message)."""
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            api_status = data.get("status")
            db_status = data.get("database")
            if api_status == "ok" and db_status == "ok":
                return True, "API and database ok"
            return False, f"API ok, but database is {db_status}"
        return False, f"Health check failed (HTTP {resp.status_code})"
    except requests.exceptions.RequestException:
        return False, "API unreachable"


def compute_waveform_envelope(audio_bytes: bytes, num_bars: int = 60) -> list[float] | None:
    """Compute amplitude envelope for ~60 vertical bars from WAV audio bytes.

    Uses only numpy and wave. If format cannot be parsed (e.g. non-WAV),
    returns None silently.
    """
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            if n_frames <= 0:
                return None
            raw_frames = wf.readframes(n_frames)

            if sampwidth == 1:
                data = np.frombuffer(raw_frames, dtype=np.uint8).astype(np.float32) - 128.0
            elif sampwidth == 2:
                data = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32)
            elif sampwidth == 4:
                data = np.frombuffer(raw_frames, dtype=np.int32).astype(np.float32)
            else:
                return None

            if n_channels > 1:
                data = data.reshape(-1, n_channels).mean(axis=1)

            abs_data = np.abs(data)
            if len(abs_data) == 0:
                return None

            if len(abs_data) < num_bars:
                bars = np.pad(abs_data, (0, num_bars - len(abs_data)), mode="edge")
            else:
                chunk_size = len(abs_data) // num_bars
                trimmed = abs_data[: chunk_size * num_bars]
                bars = trimmed.reshape(num_bars, chunk_size).mean(axis=1)

            max_val = float(np.max(bars))
            if max_val > 0:
                normalized = (bars / max_val).tolist()
            else:
                normalized = [0.15] * num_bars
            return normalized
    except Exception:
        return None


def render_waveform_html(envelope: list[float], progress_pct: float = 0.58) -> str:
    """Render amplitude envelope as ~60 vertical bars with yellow played bars and gray rest."""
    num_bars = len(envelope)
    progress_point = int(num_bars * progress_pct)
    bars_html = []
    for i, val in enumerate(envelope):
        height_px = max(5, int(val * 40))
        color = "#f5f26b" if i <= progress_point else "#3a3a3e"
        bars_html.append(
            f'<div style="width: 4px; height: {height_px}px; background-color: {color}; '
            f'border-radius: 2px; flex-shrink: 0;"></div>'
        )
    return (
        '<div style="display: flex; align-items: center; justify-content: space-between; '
        'height: 48px; background: #121214; border-radius: 14px; padding: 0 14px; '
        'margin: 16px 0; gap: 3px; overflow: hidden;">'
        + "".join(bars_html)
        + "</div>"
    )


# ─── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🎵 Acosign")

admin_key = st.sidebar.text_input(
    "Admin key",
    type="password",
    help="Required for registering new tracks and deleting existing tracks.",
    key="admin_key_input",
)
has_admin_key = bool(admin_key and admin_key.strip())

st.sidebar.markdown("---")
st.sidebar.markdown(f"**API URL:** `{API_URL}`")

healthy, health_msg = check_api_health(API_URL)
if healthy:
    st.sidebar.success(health_msg)
else:
    st.sidebar.error(health_msg)

if st.sidebar.button("Refresh Status", key="refresh_health_btn"):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Acosign Acoustic Fingerprinting & Content ID Platform")


# ─── App Header ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="text-align: center; margin-top: 10px; margin-bottom: 24px;">
        <h1 style="font-size: 2.5rem; font-weight: 800; margin: 0 0 6px 0; letter-spacing: -0.03em;">Acosign</h1>
        <p style="color: #8a8a8f; font-size: 1.05rem; margin: 0;">Audio fingerprinting and Content ID</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_identify, tab_register, tab_tracks, tab_developers = st.tabs(
    ["Identify", "Register", "Tracks", "Developers"]
)


# ─── Tab 1: Identify (Default) ─────────────────────────────────────────────────
with tab_identify:
    st.markdown(
        """
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="font-size: 1.9rem; font-weight: 800; margin-bottom: 4px;">Tap to listen</h2>
            <div style="color: #8a8a8f; font-size: 0.95rem;">Record a live clip or upload an audio snippet</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # st.audio_input mic widget directly beneath the heading
    mic_recording = None
    if hasattr(st, "audio_input"):
        mic_recording = st.audio_input(
            "Record audio clip",
            label_visibility="collapsed",
            key="mic_identify",
        )

    st.markdown(
        '<div style="text-align: center; color: #8a8a8f; font-size: 0.9rem; margin: 16px 0 10px 0;">or upload a file</div>',
        unsafe_allow_html=True,
    )

    ident_file = st.file_uploader(
        "Upload audio clip",
        type=["mp3", "wav", "m4a"],
        label_visibility="collapsed",
        key="uploader_identify",
        help="Upload a query snippet (minimum 3 seconds)",
    )

    ident_btn = st.button("Identify Audio", type="primary", key="ident_btn", use_container_width=True)

    if ident_btn:
        active_audio = mic_recording if mic_recording is not None else ident_file
        if active_audio is None:
            st.warning("Please record audio or upload a file to identify.")
        else:
            with st.spinner("Analyzing acoustic landmarks..."):
                try:
                    filename = getattr(active_audio, "name", "recording.wav")
                    mime_type = getattr(active_audio, "type", "audio/wav") or "application/octet-stream"
                    audio_bytes = active_audio.getvalue()
                    files = {
                        "file": (
                            filename,
                            audio_bytes,
                            mime_type,
                        )
                    }
                    resp = requests.post(
                        f"{API_URL}/identify",
                        files=files,
                        timeout=REQUEST_TIMEOUT,
                    )

                    if resp.status_code == 200:
                        res = resp.json()
                        if res.get("matched"):
                            title = res.get("title", "Unknown")
                            owner = res.get("owner", "Unknown")
                            cid = res.get("content_id", "Unknown")
                            score = res.get("score", 0)
                            raw_strength = str(res.get("match_strength", "weak")).lower()
                            is_strong = raw_strength == "strong"
                            strength_badge = "STRONG MATCH" if is_strong else "WEAK MATCH"
                            offset = float(res.get("offset_seconds", 0.0))

                            # Envelope computation: WAV input only via numpy and wave, silently skipped if cannot parse
                            envelope = compute_waveform_envelope(audio_bytes, num_bars=60)
                            waveform_html = render_waveform_html(envelope) if envelope is not None else ""

                            badge_style = (
                                "background: #f5f26b; color: #0b0b0c;"
                                if is_strong
                                else "background: rgba(245, 242, 107, 0.15); color: #f5f26b; border: 1px solid #f5f26b;"
                            )

                            st.markdown(
                                f"""
                                <div class="aco-card">
                                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
                                        <div>
                                            <div style="font-size: 1.6rem; font-weight: 800; color: #f5f5f4; line-height: 1.2;">{title}</div>
                                            <div style="color: #8a8a8f; font-size: 0.95rem; margin-top: 4px;">{owner}</div>
                                        </div>
                                        <span style="{badge_style} font-size: 0.75rem; font-weight: 700; padding: 4px 12px; border-radius: 999px; letter-spacing: 0.05em;">{strength_badge}</span>
                                    </div>
                                    {waveform_html}
                                    <div style="display: flex; justify-content: space-between; margin-top: 14px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.06); color: #8a8a8f; font-size: 0.88rem;">
                                        <div>Score: <strong style="color: #f5f5f4;">{score}</strong></div>
                                        <div>Offset: <strong style="color: #f5f5f4;">{offset:.2f}s</strong></div>
                                        <div>ID: <code style="color: #f5f26b; font-size: 0.8rem;">{cid[:8]}...</code></div>
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        else:
                            st.markdown(
                                """
                                <div class="aco-card" style="text-align: center; padding: 36px 20px;">
                                    <div style="font-size: 2.2rem; margin-bottom: 8px;">🔍</div>
                                    <div style="font-size: 1.2rem; font-weight: 700; color: #f5f5f4;">No match found</div>
                                    <div style="color: #8a8a8f; font-size: 0.9rem; margin-top: 6px;">
                                        This clip does not match any registered tracks in the catalog.
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                    elif resp.status_code in (400, 413, 422):
                        st.error(extract_error_detail(resp))
                    else:
                        st.error(f"Unexpected error (HTTP {resp.status_code}): {extract_error_detail(resp)}")
                except requests.exceptions.RequestException:
                    st.error(f"Unable to connect to the API at {API_URL}. Please check the server connection.")


# ─── Tab 2: Register ───────────────────────────────────────────────────────────
with tab_register:
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 4px;">Register Track</h2>
            <div style="color: #8a8a8f; font-size: 0.95rem;">Upload an audio master to extract acoustic landmarks and assign a Content ID.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    reg_file = st.file_uploader(
        "Audio file *",
        type=["mp3", "wav", "m4a"],
        key="uploader_register",
        help="Supported formats: MP3, WAV, M4A",
    )
    reg_title = st.text_input("Track Title *", placeholder="e.g. Bohemian Rhapsody", key="input_title")
    reg_owner = st.text_input("Track Owner *", placeholder="e.g. Queen / EMI", key="input_owner")

    if not has_admin_key:
        st.info("Admin key required to register tracks.")
        reg_btn = st.button("Register Track", type="primary", disabled=True, key="reg_btn_disabled", use_container_width=True)
    else:
        reg_btn = st.button("Register Track", type="primary", key="reg_btn_enabled", use_container_width=True)

    if reg_btn:
        if not reg_file or not reg_title.strip() or not reg_owner.strip():
            st.warning("Please provide an audio file, Title, and Owner.")
        else:
            with st.spinner("Fingerprinting, this takes about 30 seconds"):
                try:
                    files = {
                        "file": (
                            reg_file.name,
                            reg_file.getvalue(),
                            reg_file.type or "application/octet-stream",
                        )
                    }
                    data = {
                        "title": reg_title.strip(),
                        "owner": reg_owner.strip(),
                    }
                    headers = {"X-API-Key": admin_key.strip()}
                    resp = requests.post(
                        f"{API_URL}/register",
                        files=files,
                        data=data,
                        headers=headers,
                        timeout=REQUEST_TIMEOUT,
                    )

                    if resp.status_code == 201:
                        result = resp.json()
                        cid = result.get("content_id", "N/A")
                        stored = result.get("hashes_stored", 0)
                        st.markdown(
                            f"""
                            <div class="aco-card" style="border-left: 4px solid #f5f26b;">
                                <div style="font-weight: 700; color: #f5f26b; margin-bottom: 8px;">✓ Track Successfully Registered</div>
                                <div style="font-size: 0.95rem; color: #f5f5f4;">Content ID: <code>{cid}</code></div>
                                <div style="font-size: 0.9rem; color: #8a8a8f; margin-top: 4px;">Hashes stored: {stored:,}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                    elif resp.status_code == 401:
                        st.error("Wrong admin key")
                    elif resp.status_code == 409:
                        try:
                            err_json = resp.json()
                            detail = err_json.get("detail", {})
                            if isinstance(detail, dict):
                                existing_cid = detail.get("content_id", "Unknown")
                            else:
                                existing_cid = str(detail)
                        except Exception:
                            existing_cid = "Unknown"
                        st.warning(f"Track already registered with Content ID: {existing_cid}")
                    elif resp.status_code in (400, 413, 422):
                        st.error(extract_error_detail(resp))
                    else:
                        st.error(f"Unexpected error (HTTP {resp.status_code}): {extract_error_detail(resp)}")
                except requests.exceptions.RequestException:
                    st.error(f"Unable to connect to the API at {API_URL}. Please check the server connection.")


# ─── Tab 3: Tracks ─────────────────────────────────────────────────────────────
with tab_tracks:
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 4px;">Registered Tracks</h2>
            <div style="color: #8a8a8f; font-size: 0.95rem;">Catalog of all acoustic signatures stored in the platform.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🔄 Refresh Catalog", key="refresh_tracks_catalog"):
        st.rerun()

    try:
        resp = requests.get(f"{API_URL}/tracks?limit=100", timeout=15)
        if resp.status_code == 200:
            tracks: list[dict[str, Any]] = resp.json()
            if not tracks:
                st.markdown(
                    """
                    <div class="aco-card" style="text-align: center; padding: 32px;">
                        <div style="color: #8a8a8f; font-size: 0.95rem;">No tracks registered yet.</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                if not has_admin_key:
                    st.caption("Admin key required in the sidebar to delete tracks.")

                for track in tracks:
                    cid = str(track.get("content_id", ""))
                    t_title = str(track.get("title", "Untitled"))
                    t_owner = str(track.get("owner", "Unknown"))
                    dur_val = track.get("duration_seconds")
                    if dur_val is not None:
                        mins = int(dur_val // 60)
                        secs = int(dur_val % 60)
                        dur_str = f"{mins:02d}:{secs:02d}"
                    else:
                        dur_str = "--:--"
                    short_cid = f"{cid[:8]}..." if len(cid) > 8 else cid

                    st.markdown(
                        f"""
                        <div class="aco-track-row">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <div style="font-weight: 700; font-size: 1.05rem; color: #f5f5f4;">{t_title}</div>
                                    <div style="font-size: 0.85rem; color: #8a8a8f; margin-top: 3px;">
                                        {t_owner} &bull; {dur_str}
                                    </div>
                                </div>
                                <div>
                                    <code style="background: rgba(245, 242, 107, 0.12); color: #f5f26b; padding: 4px 10px; border-radius: 999px; font-size: 0.8rem;">{short_cid}</code>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Delete action behind existing admin-key confirmation
                    if has_admin_key:
                        confirm_key = f"confirm_delete_{cid}"
                        if st.session_state.get(confirm_key, False):
                            st.warning(f"Permanently delete '{t_title}' (`{short_cid}`)?")
                            col_c1, col_c2 = st.columns(2)
                            with col_c1:
                                if st.button("Confirm Delete", key=f"btn_confirm_{cid}", type="primary"):
                                    try:
                                        del_resp = requests.delete(
                                            f"{API_URL}/tracks/{cid}",
                                            headers={"X-API-Key": admin_key.strip()},
                                            timeout=30,
                                        )
                                        if del_resp.status_code == 204:
                                            st.success(f"Track '{t_title}' deleted.")
                                            st.session_state[confirm_key] = False
                                            st.rerun()
                                        elif del_resp.status_code == 401:
                                            st.error("Wrong admin key")
                                        elif del_resp.status_code == 404:
                                            st.error(f"Track with Content ID '{cid}' not found")
                                        else:
                                            st.error(
                                                f"Delete failed (HTTP {del_resp.status_code}): "
                                                f"{extract_error_detail(del_resp)}"
                                            )
                                    except requests.exceptions.RequestException:
                                        st.error(f"Unable to connect to the API at {API_URL}.")
                            with col_c2:
                                if st.button("Cancel", key=f"btn_cancel_{cid}"):
                                    st.session_state[confirm_key] = False
                                    st.rerun()
                        else:
                            if st.button("Delete", key=f"btn_del_req_{cid}"):
                                st.session_state[confirm_key] = True
                                st.rerun()
        else:
            st.error(f"Failed to fetch tracks (HTTP {resp.status_code}): {extract_error_detail(resp)}")
    except requests.exceptions.RequestException:
        st.error(f"Unable to connect to the API at {API_URL}. Please check the server connection.")


# ─── Tab 4: Developers ─────────────────────────────────────────────────────────
with tab_developers:
    st.markdown(
        """
        <div style="margin-bottom: 16px;">
            <h2 style="font-size: 1.6rem; font-weight: 800; margin-bottom: 4px;">Developer API</h2>
            <div style="color: #8a8a8f; font-size: 0.95rem;">Use the Acosign API to identify audio in your own app.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f"**Base URL:** `{API_URL}` &nbsp;|&nbsp; [Interactive API Documentation]({API_URL}/docs)")

    st.markdown("### Quickstart: Identify Audio")
    st.caption("Submit an audio snippet (minimum 3.0s) to POST /identify for instant signature matching.")

    # cURL snippet
    curl_snippet = f"""curl -X POST "{API_URL}/identify" \\
  -F "file=@query_clip.wav\""""
    st.markdown("**cURL**")
    st.code(curl_snippet, language="bash")

    # Python requests snippet
    python_snippet = f"""import requests

url = "{API_URL}/identify"
files = {{"file": open("query_clip.wav", "rb")}}

response = requests.post(url, files=files)
print(response.json())"""
    st.markdown("**Python (requests)**")
    st.code(python_snippet, language="python")

    st.caption(
        "Note: Mutating administrative endpoints (POST /register and DELETE /tracks/{content_id}) "
        "require the 'X-API-Key' header with a valid admin key."
    )

    st.markdown("---")

    # Try it section
    st.markdown("### Try It")
    st.write("Upload an audio clip to test `POST /identify` and inspect the raw JSON response:")

    dev_try_file = st.file_uploader(
        "Choose an audio file",
        type=["mp3", "wav", "m4a"],
        key="uploader_developer_try",
    )
    if st.button("Send Request", type="primary", key="btn_dev_try"):
        if not dev_try_file:
            st.warning("Please select an audio file first.")
        else:
            with st.spinner("Submitting to POST /identify..."):
                try:
                    files = {
                        "file": (
                            dev_try_file.name,
                            dev_try_file.getvalue(),
                            dev_try_file.type or "application/octet-stream",
                        )
                    }
                    resp = requests.post(f"{API_URL}/identify", files=files, timeout=REQUEST_TIMEOUT)
                    st.markdown(f"**HTTP Status:** `{resp.status_code}`")
                    try:
                        st.json(resp.json())
                    except Exception:
                        st.text(resp.text)
                except requests.exceptions.RequestException as e:
                    st.error(f"Request failed: {e}")

    st.markdown("---")

    # Response fields table
    st.markdown("### Response Fields")
    st.markdown(
        """
| Field | Type | Description |
| :--- | :--- | :--- |
| `matched` | boolean | `true` if an acoustic match was identified above the score threshold |
| `content_id` | string \\| null | Unique Content ID assigned to the registered track |
| `title` | string \\| null | Registered track title |
| `owner` | string \\| null | Registered track rights holder or artist |
| `score` | integer | Number of matching fingerprint hash collisions |
| `match_strength` | string | Match confidence: `"strong"` or `"weak"` |
| `offset_seconds` | float | Temporal offset in seconds between clip and registered track |
"""
    )

    # Status codes list
    st.markdown("### Status Codes")
    st.markdown(
        """
- `200 OK`: Query processed successfully. Inspect the `matched` boolean in the JSON payload.
- `400 Bad Request`: Audio file is corrupt, unreadable, or shorter than the 3.0-second minimum.
- `413 Payload Too Large`: Uploaded file exceeds server upload limits.
- `422 Unprocessable Entity`: Invalid request parameters or missing file payload.
"""
    )

    # Production note
    st.info(
        "Note: Identify is open for the demo; per-developer keys and rate limits would be added in production."
    )
