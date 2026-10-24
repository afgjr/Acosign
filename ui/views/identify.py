"""Identify page: microphone recording, file snippet upload, and waveform visualizer."""

from __future__ import annotations

import streamlit as st

from ui.api_client import identify_audio
from ui.styles import compute_waveform_envelope, html, render_waveform_html


def render_identify_page() -> None:
    """Render the audio identification interface."""
    st.markdown(
        html(
            """
            <div style="text-align: center; margin-top: 6px; margin-bottom: 22px;">
                <h1 style="font-size: 2.4rem; font-weight: 800; margin-bottom: 4px;">Tap to listen</h1>
                <div style="color: #8a8a8f; font-size: 1rem;">Record live audio or drop a snippet to search the database</div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    # Microphone input directly beneath the heading
    mic_recording = None
    if hasattr(st, "audio_input"):
        mic_recording = st.audio_input(
            "Record audio clip",
            label_visibility="collapsed",
            key="mic_identify",
        )
    else:
        st.info("Microphone recording widget is not available in this environment. Please upload an audio file below.")

    with st.expander("Upload an audio file instead", expanded=False):
        ident_file = st.file_uploader(
            "Upload audio clip",
            type=["mp3", "wav", "m4a"],
            label_visibility="collapsed",
            key="uploader_identify",
            help="Supported formats: WAV, MP3, M4A (minimum 3 seconds)",
        )

    ident_btn = st.button("Identify", type="primary", key="ident_btn", use_container_width=True)

    if ident_btn:
        active_audio = mic_recording if mic_recording is not None else ident_file
        if active_audio is None:
            st.warning("Please record audio or upload a file first.")
            return

        with st.spinner("Analyzing acoustic landmarks..."):
            file_name = getattr(active_audio, "name", "recording.wav")
            mime_type = getattr(active_audio, "type", "audio/wav") or "application/octet-stream"
            audio_bytes = active_audio.getvalue()

            status_code, result = identify_audio(file_name, audio_bytes, mime_type)

            if status_code == 200 and isinstance(result, dict):
                if result.get("matched"):
                    title = result.get("title", "Unknown")
                    owner = result.get("owner", "Unknown")
                    album = result.get("album")
                    genre = result.get("genre")
                    year = result.get("release_year")
                    score = result.get("score", 0)
                    offset = float(result.get("offset_seconds", 0.0))
                    raw_strength = str(result.get("match_strength", "weak")).lower()
                    is_strong = raw_strength == "strong"

                    # Optional metadata line
                    meta_parts = []
                    if album:
                        meta_parts.append(f"Album: {album}")
                    if genre:
                        meta_parts.append(f"Genre: {genre}")
                    if year:
                        meta_parts.append(f"Year: {year}")
                    meta_str = " &bull; ".join(meta_parts)
                    meta_html = (
                        f'<div style="color: #a1a1aa; font-size: 0.88rem; margin-top: 4px;">{meta_str}</div>'
                        if meta_str
                        else ""
                    )

                    # Strength badge: strong green, weak orange
                    badge_color = "#10b981" if is_strong else "#f59e0b"
                    badge_bg = "rgba(16, 185, 129, 0.15)" if is_strong else "rgba(245, 158, 11, 0.15)"
                    badge_label = "STRONG MATCH" if is_strong else "WEAK MATCH"

                    # Waveform graphic: amplitude envelope as ~60 vertical bars for WAV, silently skipped if cannot parse
                    envelope = compute_waveform_envelope(audio_bytes, num_bars=60)
                    waveform_html = render_waveform_html(envelope) if envelope is not None else ""

                    st.markdown(
                        html(
                            f"""
                            <div class="aco-card">
                                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                                    <div>
                                        <div style="font-size: 1.65rem; font-weight: 800; color: #f5f5f4; line-height: 1.2;">{title}</div>
                                        <div style="color: #8a8a8f; font-size: 0.95rem; margin-top: 4px;">{owner}</div>
                                        {meta_html}
                                    </div>
                                    <span style="background: {badge_bg}; color: {badge_color}; border: 1px solid {badge_color}; font-size: 0.75rem; font-weight: 700; padding: 4px 12px; border-radius: 999px; letter-spacing: 0.05em; white-space: nowrap;">
                                        {badge_label}
                                    </span>
                                </div>
                                {waveform_html}
                                <div style="display: flex; justify-content: space-between; margin-top: 14px; padding-top: 14px; border-top: 1px solid rgba(255,255,255,0.06); color: #8a8a8f; font-size: 0.88rem;">
                                    <div>Score: <strong style="color: #f5f5f4;">{score}</strong></div>
                                    <div>Offset: <strong style="color: #f5f5f4;">{offset:.2f}s</strong></div>
                                    <div>Content ID: <code style="color: #f5f26b; font-size: 0.8rem;">{str(result.get('content_id', ''))[:8]}...</code></div>
                                </div>
                            </div>
                            """
                        ),
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        html(
                            """
                            <div class="aco-card" style="text-align: center; padding: 36px 20px;">
                                <div style="font-size: 2.2rem; margin-bottom: 8px;">🔍</div>
                                <div style="font-size: 1.2rem; font-weight: 700; color: #f5f5f4;">No match found</div>
                                <div style="color: #8a8a8f; font-size: 0.9rem; margin-top: 6px;">
                                    This clip did not match any registered tracks in the catalog.
                                </div>
                            </div>
                            """
                        ),
                        unsafe_allow_html=True,
                    )
            elif status_code in (400, 413, 422):
                st.error(str(result))
            else:
                st.error(f"Error ({status_code}): {result}")
