"""Tracks page (public, read-only): search and browse registered track catalog."""

from __future__ import annotations

import streamlit as st

from ui.api_client import get_tracks


def render_tracks_page() -> None:
    """Render the public tracks catalog browser."""
    st.markdown(
        """
        <div style="margin-bottom: 20px;">
            <h1 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 4px;">Registered Tracks</h1>
            <div style="color: #8a8a8f; font-size: 0.95rem;">Browse public acoustic signatures stored in the platform.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_query = st.text_input(
        "Search tracks",
        placeholder="Filter by title or owner...",
        label_visibility="collapsed",
        key="search_tracks_input",
    )

    status_code, result = get_tracks(limit=100)

    if status_code == 200 and isinstance(result, list):
        tracks = result
        if search_query and search_query.strip():
            q = search_query.strip().lower()
            tracks = [
                t
                for t in tracks
                if q in str(t.get("title", "")).lower() or q in str(t.get("owner", "")).lower()
            ]

        if not tracks:
            st.markdown(
                """
                <div class="aco-card" style="text-align: center; padding: 36px 20px;">
                    <div style="color: #8a8a8f; font-size: 0.95rem;">No matching tracks found.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        st.caption(f"Showing {len(tracks)} track{'s' if len(tracks) != 1 else ''}")

        for track in tracks:
            t_title = str(track.get("title", "Untitled"))
            t_owner = str(track.get("owner", "Unknown"))
            t_genre = track.get("genre") or "—"
            t_year = track.get("release_year") or "—"

            dur_val = track.get("duration_seconds")
            if dur_val is not None:
                mins = int(dur_val // 60)
                secs = int(dur_val % 60)
                dur_str = f"{mins:02d}:{secs:02d}"
            else:
                dur_str = "--:--"

            st.markdown(
                f"""
                <div class="aco-track-row">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 700; font-size: 1.1rem; color: #f5f5f4;">{t_title}</div>
                            <div style="font-size: 0.88rem; color: #8a8a8f; margin-top: 4px;">
                                {t_owner} &bull; Genre: {t_genre} &bull; Year: {t_year}
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <span style="background: rgba(245, 242, 107, 0.12); color: #f5f26b; padding: 4px 12px; border-radius: 999px; font-size: 0.85rem; font-weight: 600;">
                                {dur_str}
                            </span>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    elif status_code == 0:
        st.error(f"Connection error: {result}")
    else:
        st.error(f"Unable to fetch catalog ({status_code}): {result}")
