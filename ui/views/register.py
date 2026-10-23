"""Register page (admin only): two-step wizard for audio ingestion and metadata."""

from __future__ import annotations

from datetime import datetime
import streamlit as st

from ui.api_client import register_track


def render_register_page() -> None:
    """Render the two-step track registration wizard."""
    # Enforce admin authentication
    if not st.session_state.get("admin_authenticated", False):
        st.error("Access denied. Admin authentication required.")
        return

    admin_key = st.session_state.get("admin_key", "")

    st.markdown(
        """
        <div style="margin-bottom: 20px;">
            <h1 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 4px;">Register Audio Track</h1>
            <div style="color: #8a8a8f; font-size: 0.95rem;">Extract acoustic landmarks, index hashes, and assign a Content ID.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
            f'<div style="text-align: center; border-bottom: 3px solid {s1_color}; padding-bottom: 6px; font-weight: 700; color: {s1_color};">Step 1: Upload & Preview</div>',
            unsafe_allow_html=True,
        )
    with col_s2:
        s2_color = "#f5f26b" if current_step == 2 else "#8a8a8f"
        st.markdown(
            f'<div style="text-align: center; border-bottom: 3px solid {s2_color}; padding-bottom: 6px; font-weight: 700; color: {s2_color};">Step 2: Track Metadata</div>',
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
                with st.spinner("Fingerprinting, this takes about 30 seconds"):
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

                    status_code, result = register_track(
                        file_name=file_name,
                        file_bytes=audio_bytes,
                        mime_type=mime_type,
                        metadata=metadata,
                        admin_key=admin_key,
                    )

                    if status_code == 201 and isinstance(result, dict):
                        cid = result.get("content_id", "N/A")
                        stored = result.get("hashes_stored", 0)
                        st.markdown(
                            f"""
                            <div class="aco-card" style="border-left: 4px solid #f5f26b; margin-top: 16px;">
                                <div style="font-weight: 700; color: #f5f26b; font-size: 1.1rem; margin-bottom: 8px;">✓ Track Successfully Registered</div>
                                <div style="font-size: 0.95rem; color: #f5f5f4;">Content ID: <code>{cid}</code></div>
                                <div style="font-size: 0.9rem; color: #8a8a8f; margin-top: 4px;">Fingerprint hashes stored: {stored:,}</div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        # Reset wizard state for the next registration
                        st.session_state["reg_step"] = 1
                        st.session_state["reg_audio_bytes"] = None
                        st.session_state["reg_audio_name"] = None
                        st.session_state["reg_audio_type"] = None
                    elif status_code == 409:
                        st.warning(str(result))
                    elif status_code in (400, 401, 413, 422):
                        st.error(str(result))
                    else:
                        st.error(f"Registration failed ({status_code}): {result}")
