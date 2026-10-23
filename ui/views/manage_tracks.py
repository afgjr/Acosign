"""Manage tracks page (admin only): catalog administration and track deletion."""

from __future__ import annotations

import streamlit as st

from ui.api_client import delete_track, get_tracks


def render_manage_tracks_page() -> None:
    """Render the catalog management and track deletion interface."""
    # Enforce admin authentication
    if not st.session_state.get("admin_authenticated", False):
        st.error("Access denied. Admin authentication required.")
        return

    admin_key = st.session_state.get("admin_key", "")

    st.markdown(
        """
        <div style="margin-bottom: 20px;">
            <h1 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 4px;">Manage Tracks</h1>
            <div style="color: #8a8a8f; font-size: 0.95rem;">Administrative catalog controls and track removal.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🔄 Refresh Catalog", key="btn_refresh_manage_catalog"):
        st.rerun()

    status_code, result = get_tracks(limit=100)

    if status_code == 200 and isinstance(result, list):
        tracks = result
        if not tracks:
            st.markdown(
                """
                <div class="aco-card" style="text-align: center; padding: 36px 20px;">
                    <div style="color: #8a8a8f; font-size: 0.95rem;">No tracks registered in the database.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        st.caption(f"Total tracks in catalog: {len(tracks)}")

        for track in tracks:
            cid = str(track.get("content_id", ""))
            t_title = str(track.get("title", "Untitled"))
            t_owner = str(track.get("owner", "Unknown"))
            t_genre = track.get("genre") or "—"

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
                <div class="aco-track-row" style="margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 700; font-size: 1.05rem; color: #f5f5f4;">{t_title}</div>
                            <div style="font-size: 0.85rem; color: #8a8a8f; margin-top: 2px;">
                                {t_owner} &bull; {dur_str} &bull; {t_genre}
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

            # Two-step delete confirmation
            confirm_key = f"confirm_del_{cid}"
            if st.session_state.get(confirm_key, False):
                st.warning(f"Are you sure you want to permanently delete '{t_title}' (`{short_cid}`)?")
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    if st.button("Confirm Delete", key=f"btn_confirm_del_{cid}", type="primary", use_container_width=True):
                        del_code, del_msg = delete_track(cid, admin_key=admin_key)
                        if del_code == 204:
                            st.success(f"Track '{t_title}' deleted.")
                            st.session_state[confirm_key] = False
                            st.rerun()
                        elif del_code == 401:
                            st.error("Wrong admin key")
                        elif del_code == 404:
                            st.error(f"Track with Content ID '{cid}' not found")
                        else:
                            st.error(f"Delete failed ({del_code}): {del_msg}")
                with col_c2:
                    if st.button("Cancel", key=f"btn_cancel_del_{cid}", use_container_width=True):
                        st.session_state[confirm_key] = False
                        st.rerun()
            else:
                if st.button("Delete Track", key=f"btn_request_del_{cid}"):
                    st.session_state[confirm_key] = True
                    st.rerun()

            st.write("")
    elif status_code == 0:
        st.error(f"Connection error: {result}")
    else:
        st.error(f"Unable to load catalog ({status_code}): {result}")
