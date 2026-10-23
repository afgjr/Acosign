"""Acosign Streamlit UI application.

HTTP-only client communicating with the Acosign FastAPI backend.
Never imports from app/ (AGENT.md rule 9).
"""

from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

# ─── Configuration ─────────────────────────────────────────────────────────────
DEFAULT_API_URL = "http://localhost:8000"
API_URL = os.getenv("API_URL", DEFAULT_API_URL).rstrip("/")
REQUEST_TIMEOUT = 180  # seconds

st.set_page_config(
    page_title="Acosign",
    page_icon="🎵",
    layout="wide",
)


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


# ─── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🎵 Acosign Control")

# Admin Key input (password field: never stored, never printed)
admin_key = st.sidebar.text_input(
    "Admin key",
    type="password",
    help="Required for registering new tracks and deleting existing tracks.",
    key="admin_key_input",
)
has_admin_key = bool(admin_key and admin_key.strip())

st.sidebar.markdown("---")
st.sidebar.markdown(f"**API URL:** `{API_URL}`")

# Health indicator
healthy, health_msg = check_api_health(API_URL)
if healthy:
    st.sidebar.success(health_msg)
else:
    st.sidebar.error(health_msg)

if st.sidebar.button("Refresh Status", key="refresh_health_btn"):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Acosign Acoustic Fingerprinting & Content ID Engine")


# ─── Main Header ───────────────────────────────────────────────────────────────
st.title("Acosign")
st.caption("Audio fingerprinting and Content ID")

tab_register, tab_identify, tab_tracks = st.tabs(["Register", "Identify", "Tracks"])


# ─── Tab 1: Register ───────────────────────────────────────────────────────────
with tab_register:
    st.subheader("Register Audio Track")
    st.write(
        "Upload a full audio track to extract acoustic landmarks, store its fingerprint "
        "hashes, and assign a unique Content ID."
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
        reg_btn = st.button("Register Track", type="primary", disabled=True, key="reg_btn_disabled")
    else:
        reg_btn = st.button("Register Track", type="primary", key="reg_btn_enabled")

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
                        st.success("Track successfully registered!")
                        col_m1, col_m2 = st.columns(2)
                        col_m1.metric("Content ID", cid)
                        col_m2.metric("Hashes Stored", f"{stored:,}")
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


# ─── Tab 2: Identify ───────────────────────────────────────────────────────────
with tab_identify:
    st.subheader("Identify Audio Clip")
    st.write(
        "Upload a short audio snippet or record directly via microphone (minimum 3 seconds) "
        "to search against registered database fingerprints."
    )

    ident_file = st.file_uploader(
        "Upload audio clip",
        type=["mp3", "wav", "m4a"],
        key="uploader_identify",
        help="Upload a query snippet (minimum 3 seconds)",
    )

    mic_recording = None
    if hasattr(st, "audio_input"):
        mic_recording = st.audio_input("Or record clip from microphone", key="mic_identify")

    ident_btn = st.button("Identify", type="primary", key="ident_btn")

    if ident_btn:
        active_audio = ident_file if ident_file is not None else mic_recording
        if active_audio is None:
            st.warning("Please upload an audio file or record from the microphone to identify.")
        else:
            with st.spinner("Analyzing and identifying audio clip..."):
                try:
                    filename = getattr(active_audio, "name", "query_recording.wav")
                    mime_type = getattr(active_audio, "type", "audio/wav") or "application/octet-stream"
                    files = {
                        "file": (
                            filename,
                            active_audio.getvalue(),
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
                            strength = str(res.get("match_strength", "weak")).lower()
                            offset = float(res.get("offset_seconds", 0.0))

                            is_strong = strength == "strong"
                            badge_color = "#10b981" if is_strong else "#f59e0b"
                            badge_bg = "rgba(16, 185, 129, 0.15)" if is_strong else "rgba(245, 158, 11, 0.15)"
                            badge_label = "STRONG MATCH" if is_strong else "WEAK MATCH"

                            st.success("Match found!")
                            st.markdown(
                                f"""
                                <div style="background-color: #1f2937; border-radius: 8px; padding: 20px; margin-top: 10px; margin-bottom: 16px; border-left: 5px solid {badge_color};">
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                        <h3 style="margin: 0; color: #f9fafb; font-size: 1.3rem;">{title}</h3>
                                        <span style="background-color: {badge_bg}; color: {badge_color}; border: 1px solid {badge_color}; padding: 4px 12px; border-radius: 9999px; font-size: 0.8rem; font-weight: 700; letter-spacing: 0.05em;">{badge_label}</span>
                                    </div>
                                    <p style="margin: 6px 0; color: #d1d5db; font-size: 0.95rem;"><strong>Owner:</strong> {owner}</p>
                                    <p style="margin: 6px 0; color: #d1d5db; font-size: 0.95rem;"><strong>Content ID:</strong> <code>{cid}</code></p>
                                    <p style="margin: 6px 0; color: #d1d5db; font-size: 0.95rem;"><strong>Offset:</strong> {offset:.2f} seconds</p>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                            col_s1, col_s2 = st.columns(2)
                            col_s1.metric("Match Score", score)
                            col_s2.metric("Temporal Offset", f"{offset:.2f} s")
                        else:
                            st.info("No match found")
                    elif resp.status_code in (400, 413, 422):
                        st.error(extract_error_detail(resp))
                    else:
                        st.error(f"Unexpected error (HTTP {resp.status_code}): {extract_error_detail(resp)}")
                except requests.exceptions.RequestException:
                    st.error(f"Unable to connect to the API at {API_URL}. Please check the server connection.")


# ─── Tab 3: Tracks ─────────────────────────────────────────────────────────────
with tab_tracks:
    st.subheader("Registered Tracks Catalog")
    col_t_desc, col_t_btn = st.columns([4, 1])
    with col_t_desc:
        st.write("Browse all registered audio tracks in the database or manage catalog items.")
    with col_t_btn:
        refresh_clicked = st.button("🔄 Refresh Tracks", key="refresh_tracks_catalog")

    try:
        resp = requests.get(f"{API_URL}/tracks?limit=100", timeout=15)
        if resp.status_code == 200:
            tracks: list[dict[str, Any]] = resp.json()
            if not tracks:
                st.info("No tracks registered yet.")
            else:
                # Display catalog table
                display_rows = []
                for t in tracks:
                    dur_val = t.get("duration_seconds", 0.0)
                    dur_str = f"{dur_val:.1f}s" if dur_val is not None else "N/A"
                    created_raw = str(t.get("created_at", ""))
                    created_str = created_raw[:19].replace("T", " ") if created_raw else "N/A"
                    display_rows.append(
                        {
                            "Title": t.get("title", ""),
                            "Owner": t.get("owner", ""),
                            "Duration": dur_str,
                            "Content ID": t.get("content_id", ""),
                            "Created At": created_str,
                        }
                    )
                st.dataframe(display_rows, use_container_width=True)

                st.markdown("### Manage Tracks")
                if not has_admin_key:
                    st.info("Admin key required to delete tracks.")

                for track in tracks:
                    cid = str(track.get("content_id", ""))
                    t_title = str(track.get("title", "Untitled"))
                    t_owner = str(track.get("owner", "Unknown"))

                    with st.expander(f"🎵 {t_title} (ID: `{cid}`)"):
                        st.write(f"**Owner:** {t_owner} | **Content ID:** `{cid}`")

                        if not has_admin_key:
                            st.caption("Admin key required")
                            st.button(
                                "Delete Track",
                                key=f"del_disabled_{cid}",
                                disabled=True,
                            )
                        else:
                            confirm_key = f"confirm_delete_{cid}"
                            if st.session_state.get(confirm_key, False):
                                st.warning(f"Are you sure you want to permanently delete '{t_title}' (`{cid}`)?")
                                col_c1, col_c2 = st.columns([1, 1])
                                with col_c1:
                                    if st.button("Confirm Delete", key=f"btn_confirm_{cid}", type="primary"):
                                        try:
                                            del_resp = requests.delete(
                                                f"{API_URL}/tracks/{cid}",
                                                headers={"X-API-Key": admin_key.strip()},
                                                timeout=30,
                                            )
                                            if del_resp.status_code == 204:
                                                st.success(f"Track '{t_title}' deleted successfully.")
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
                                if st.button("Delete Track", key=f"btn_delete_req_{cid}"):
                                    st.session_state[confirm_key] = True
                                    st.rerun()
        else:
            st.error(f"Failed to fetch tracks (HTTP {resp.status_code}): {extract_error_detail(resp)}")
    except requests.exceptions.RequestException:
        st.error(f"Unable to connect to the API at {API_URL}. Please check the server connection.")
