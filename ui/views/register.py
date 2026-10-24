"""Register page (admin only): two-step wizard for audio ingestion and metadata."""

from __future__ import annotations

from datetime import datetime, timezone
import requests
import streamlit as st

from ui.api_client import get_tracks, register_track
from ui.styles import html


def render_register_page() -> None:
    """Render the two-step track registration wizard."""
    # Enforce admin authentication
    if not st.session_state.get("admin_authenticated", False):
        st.error("Access denied. Admin authentication required.")
        return

    admin_key = st.session_state.get("admin_key", "")

    st.markdown(
        html(
            """
            <div style="margin-bottom: 20px;">
                <h1 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 4px;">Register Audio Track</h1>
                <div style="color: #8a8a8f; font-size: 0.95rem;">Extract acoustic landmarks, index hashes, and assign a Content ID.</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    # ─── Top: Registration Outcome (persisted across reruns) ───────────────────
    reg_result = st.session_state.get("register_result")
    if reg_result is not None:
        if reg_result.get("success"):
            cid = reg_result.get("content_id", "N/A")
            title = reg_result.get("title", "")
            stored = reg_result.get("hashes_stored", 0)
            confirmed = reg_result.get("confirmed_from_tracks", False)

            header_text = (
                "✓ Registered successfully (confirmed from the tracks list)"
                if confirmed
                else "✓ Track Successfully Registered"
            )
            title_html = (
                f'<div style="font-size: 1.15rem; font-weight: 700; color: #f5f5f4; margin-bottom: 6px;">{title}</div>'
                if title
                else ""
            )
            hashes_html = (
                f'<div style="font-size: 0.9rem; color: #8a8a8f; margin-top: 4px;">Fingerprint hashes stored: {stored:,}</div>'
                if stored
                else ""
            )

            st.markdown(
                html(
                    f"""
                    <div class="aco-card" style="border-left: 4px solid #10b981; margin-bottom: 16px;">
                        <div style="font-weight: 700; color: #10b981; font-size: 1.15rem; margin-bottom: 8px;">{header_text}</div>
                        {title_html}
                        <div style="font-size: 0.95rem; color: #f5f5f4;">Content ID: <code>{cid}</code></div>
                        {hashes_html}
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )
        else:
            err_text = reg_result.get("error", "Registration failed.")
            st.markdown(
                html(
                    f"""
                    <div class="aco-card" style="border-left: 4px solid #ef4444; margin-bottom: 16px;">
                        <div style="font-weight: 700; color: #ef4444; font-size: 1.1rem; margin-bottom: 6px;">Registration Failed</div>
                        <div style="font-size: 0.95rem; color: #f5f5f4;">{err_text}</div>
                    </div>
                    """
                ),
                unsafe_allow_html=True,
            )

        if st.button("Register another song", key="btn_clear_reg_result", type="primary"):
            st.session_state.pop("register_result", None)
            st.session_state["reg_step"] = 1
            st.session_state["reg_audio_bytes"] = None
            st.session_state["reg_audio_name"] = None
            st.session_state["reg_audio_type"] = None
            st.rerun()

        st.write("")

    # Initialize wizard session state
    if "reg_step" not in st.session_state:
        st.session_state["reg_step"] = 1
    if "reg_audio_bytes" not in st.session_state:
        st.session_state["reg_audio_bytes"] = None
    if "reg_audio_name" not in st.session_state:
        st.session_state["reg_audio_name"] = None
    if "reg_audio_type" not in st.session_state:
        st.session_state["reg_audio_type"] = None

    # Step indicators
    current_step = st.session_state["reg_step"]
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        s1_color = "#f5f26b" if current_step == 1 else "#8a8a8f"
        st.markdown(
            html(f'<div style="text-align: center; border-bottom: 3px solid {s1_color}; padding-bottom: 6px; font-weight: 700; color: {s1_color};">Step 1: Upload & Preview</div>'),
            unsafe_allow_html=True,
        )
    with col_s2:
        s2_color = "#f5f26b" if current_step == 2 else "#8a8a8f"
        st.markdown(
            html(f'<div style="text-align: center; border-bottom: 3px solid {s2_color}; padding-bottom: 6px; font-weight: 700; color: {s2_color};">Step 2: Track Metadata</div>'),
            unsafe_allow_html=True,
        )

    st.write("")

    # ─── Step 1: Upload & Preview ──────────────────────────────────────────────
    if current_step == 1:
        st.markdown("### Step 1: Select Master Audio File")
        uploaded_file = st.file_uploader(
            "Choose audio file",
            type=["mp3", "wav", "m4a"],
            key="wizard_file_uploader",
            help="Supported formats: WAV, MP3, M4A",
        )

        if uploaded_file is not None:
            st.session_state["reg_audio_bytes"] = uploaded_file.getvalue()
            st.session_state["reg_audio_name"] = uploaded_file.name
            st.session_state["reg_audio_type"] = uploaded_file.type or "application/octet-stream"

            st.markdown(f"**Previewing:** `{uploaded_file.name}`")
            st.audio(uploaded_file)

            if st.button("Next: Track Details →", type="primary", key="btn_wizard_next", use_container_width=True):
                st.session_state["reg_step"] = 2
                st.rerun()
        else:
            st.button("Next: Track Details →", type="primary", disabled=True, key="btn_wizard_next_disabled", use_container_width=True)

    # ─── Step 2: Track Metadata ────────────────────────────────────────────────
    elif current_step == 2:
        file_name = st.session_state.get("reg_audio_name", "Audio Track")
        audio_bytes = st.session_state.get("reg_audio_bytes")
        mime_type = st.session_state.get("reg_audio_type", "application/octet-stream")

        st.markdown(f"### Step 2: Metadata for `{file_name}`")

        with st.form("register_metadata_form"):
            reg_title = st.text_input("Track Title *", placeholder="e.g. Bohemian Rhapsody")
            reg_owner = st.text_input("Track Owner *", placeholder="e.g. Queen / EMI")

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                reg_album = st.text_input("Album (optional)", placeholder="e.g. A Night at the Opera")
                current_year = datetime.now().year
                reg_year_raw = st.number_input(
                    "Release Year (optional)",
                    min_value=1900,
                    max_value=current_year + 1,
                    value=None,
                    step=1,
                    help="Release year between 1900 and next year",
                )
            with col_m2:
                reg_genre = st.text_input("Genre (optional)", placeholder="e.g. Classic Rock")
                reg_isrc = st.text_input("ISRC (optional)", placeholder="e.g. GBAYE0601477")

            license_options = [
                "Original",
                "CC-BY",
                "CC-BY-SA",
                "CC0",
                "All rights reserved",
                "Other",
            ]
            reg_license = st.selectbox("License Type (optional)", license_options, index=0)
            reg_desc = st.text_area("Description (optional)", placeholder="Notes or context about this recording...", max_chars=2000)

            col_b1, col_b2 = st.columns(2)
            with col_b1:
                submitted = st.form_submit_button("Register Track", type="primary", use_container_width=True)
            with col_b2:
                back_clicked = st.form_submit_button("← Back to Step 1", use_container_width=True)

        if back_clicked:
            st.session_state["reg_step"] = 1
            st.rerun()

        if submitted:
            if not reg_title.strip() or not reg_owner.strip():
                st.warning("Please provide both Title and Owner.")
            elif not audio_bytes:
                st.error("Audio data is missing. Please go back to Step 1.")
            else:
                metadata = {
                    "title": reg_title.strip(),
                    "owner": reg_owner.strip(),
                    "album": reg_album.strip() if reg_album else None,
                    "genre": reg_genre.strip() if reg_genre else None,
                    "release_year": int(reg_year_raw) if reg_year_raw is not None else None,
                    "isrc": reg_isrc.strip() if reg_isrc else None,
                    "license_type": reg_license,
                    "description": reg_desc.strip() if reg_desc else None,
                }

                outcome_result = None
                with st.status("Fingerprinting and saving, this can take about a minute", expanded=True) as status_box:
                    try:
                        status_code, result = register_track(
                            file_name=file_name,
                            file_bytes=audio_bytes,
                            mime_type=mime_type,
                            metadata=metadata,
                            admin_key=admin_key,
                        )
                    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, ConnectionError) as exc:
                        # Call GET /tracks and check if track was created in last 5 minutes
                        recovered_track = None
                        try:
                            t_code, tracks = get_tracks(limit=100)
                            if t_code == 200 and isinstance(tracks, list):
                                now = datetime.now(timezone.utc)
                                for t in tracks:
                                    if t.get("title") == metadata["title"] and t.get("owner") == metadata["owner"]:
                                        created_str = t.get("created_at")
                                        if created_str:
                                            try:
                                                dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                                                if dt.tzinfo is None:
                                                    dt = dt.replace(tzinfo=timezone.utc)
                                                if abs((now - dt).total_seconds()) <= 300:
                                                    recovered_track = t
                                                    break
                                            except Exception:
                                                recovered_track = t
                                                break
                                        else:
                                            recovered_track = t
                                            break
                        except Exception:
                            pass

                        if recovered_track is not None:
                            status_code = 201
                            result = {
                                "content_id": recovered_track.get("content_id", "N/A"),
                                "title": recovered_track.get("title", metadata["title"]),
                                "hashes_stored": recovered_track.get("hashes_stored", 0),
                                "confirmed_from_tracks": True,
                            }
                        else:
                            status_code = 0
                            result = (
                                f"Registration timed out or connection error ({type(exc).__name__}). "
                                "Hint: please check the Tracks page to see if your track was saved."
                            )

                    if status_code == 201 and isinstance(result, dict):
                        cid = result.get("content_id", "N/A")
                        stored = result.get("hashes_stored", 0)
                        confirmed = result.get("confirmed_from_tracks", False)
                        if confirmed:
                            status_box.update(
                                label="Registered successfully (confirmed from the tracks list)",
                                state="complete",
                                expanded=False,
                            )
                        else:
                            status_box.update(
                                label="Registration complete",
                                state="complete",
                                expanded=False,
                            )

                        outcome_result = {
                            "success": True,
                            "content_id": cid,
                            "title": result.get("title", metadata["title"]),
                            "hashes_stored": stored,
                            "confirmed_from_tracks": confirmed,
                        }
                    else:
                        status_box.update(
                            label="Registration failed",
                            state="error",
                            expanded=False,
                        )
                        if status_code == 409:
                            err_msg = str(result)
                        elif status_code == 401:
                            err_msg = "Wrong admin key. Access denied."
                        elif status_code in (400, 413, 422):
                            err_msg = str(result)
                        elif status_code == 0:
                            err_msg = str(result)
                        else:
                            err_msg = f"Registration failed ({status_code}): {result}"

                        outcome_result = {
                            "success": False,
                            "error": err_msg,
                            "status_code": status_code,
                        }

                # Store outcome in st.session_state["register_result"] BEFORE resetting wizard or calling st.rerun()
                st.session_state["register_result"] = outcome_result
                st.session_state["reg_step"] = 1
                st.session_state["reg_audio_bytes"] = None
                st.session_state["reg_audio_name"] = None
                st.session_state["reg_audio_type"] = None
                st.rerun()
