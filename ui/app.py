"""Acosign Streamlit UI application.

HTTP-only multi-page client communicating with the Acosign FastAPI backend.
Never imports from app/ (AGENT.md rule 9).
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure repository root is on sys.path for `import ui...`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from ui.api_client import (
    API_URL,
    check_api_health,
    render_health_status_html,
    verify_admin_key,
)
from ui.styles import CUSTOM_CSS, html
from ui.views.developers import render_developers_page
from ui.views.identify import render_identify_page
from ui.views.manage_tracks import render_manage_tracks_page
from ui.views.register import render_register_page
from ui.views.tracks import render_tracks_page

st.set_page_config(
    page_title="Acosign",
    page_icon="ui/assets/favicon.png",
    layout="centered",
)

# Apply global styling
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ─── Session State Initialization ──────────────────────────────────────────────
if "admin_authenticated" not in st.session_state:
    st.session_state["admin_authenticated"] = False
if "admin_key" not in st.session_state:
    st.session_state["admin_key"] = ""
if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "Identify"


_FAVICON_SVG_PATH = Path(__file__).resolve().parent / "assets" / "favicon.svg"
if _FAVICON_SVG_PATH.exists():
    _svg_text = _FAVICON_SVG_PATH.read_text(encoding="utf-8").strip()
    LOGO_SVG_36 = _svg_text.replace(
        "<svg ",
        '<svg width="36" height="36" style="width:36px;height:36px;flex-shrink:0;" ',
        1,
    )
else:
    LOGO_SVG_36 = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="36" height="36" style="width:36px;height:36px;flex-shrink:0;">'
        '<rect width="64" height="64" rx="16" fill="#0b0b0c"/>'
        '<g transform="translate(0.0,0)">'
        '<rect x="0" y="22.0" width="8" height="20" rx="4.0" fill="#f5f26b"/>'
        '<rect x="14" y="14.0" width="8" height="36" rx="4.0" fill="#f5f26b"/>'
        '<rect x="28" y="4.0" width="8" height="56" rx="4.0" fill="#f5f26b"/>'
        '<rect x="42" y="14.0" width="8" height="36" rx="4.0" fill="#f5f26b"/>'
        '<rect x="56" y="22.0" width="8" height="20" rx="4.0" fill="#f5f26b"/>'
        "</g></svg>"
    )

# ─── Sidebar Navigation & Health ───────────────────────────────────────────────
st.sidebar.markdown(
    html(
        f"""
        <div class="aco-wordmark" style="margin-bottom: 16px; display: flex; align-items: center; gap: 10px;">
            {LOGO_SVG_36}
            <div>
                <h2 style="font-size: 1.4rem; font-weight: 700; margin: 0; color: #f5f5f4; letter-spacing: -0.02em;">Acosign</h2>
                <div style="font-size: 0.78rem; color: #8a8a8f; margin-top: 1px;">Audio Fingerprinting &amp; Content ID</div>
            </div>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

# Query cached health status (15s TTL)
health_status, health_detail = check_api_health(API_URL)
status_indicator_html = render_health_status_html(health_status)

# Navigation Menu
is_admin = st.session_state["admin_authenticated"]
public_pages = ["Identify", "Tracks", "Developers"]
admin_pages = ["Identify", "Tracks", "Developers", "Register", "Manage tracks"]
available_pages = admin_pages if is_admin else public_pages

# Ensure selected page is valid for current permissions
if st.session_state["selected_page"] not in available_pages:
    st.session_state["selected_page"] = "Identify"

selected = st.sidebar.radio(
    "Navigation",
    available_pages,
    index=available_pages.index(st.session_state["selected_page"]),
    label_visibility="collapsed",
    key="nav_radio_selection",
)
st.session_state["selected_page"] = selected

st.sidebar.markdown("---")

# ─── Admin Authentication Section ──────────────────────────────────────────────
if is_admin:
    col_adm_header, col_adm_ref = st.sidebar.columns([3, 1])
    with col_adm_header:
        st.markdown(
            html(
                f"""
                <div style="display: flex; align-items: center; gap: 8px; margin-top: 4px;">
                    <span style="color: #f5f26b; font-weight: 700; font-size: 0.95rem;">Admin mode</span>
                    {status_indicator_html}
                </div>
                """
            ),
            unsafe_allow_html=True,
        )
    with col_adm_ref:
        if st.button("Refresh", key="btn_admin_refresh_status"):
            check_api_health.clear()
            st.rerun()

    if st.sidebar.button("Log out", key="btn_admin_logout", use_container_width=True):
        st.session_state["admin_authenticated"] = False
        st.session_state["admin_key"] = ""
        if st.session_state["selected_page"] in ("Register", "Manage tracks"):
            st.session_state["selected_page"] = "Identify"
        st.rerun()
else:
    st.sidebar.markdown(html("<div style='font-size: 0.9rem; font-weight: 700; color: #f5f5f4; margin-bottom: 6px;'>Admin Access</div>"), unsafe_allow_html=True)
    admin_input = st.sidebar.text_input(
        "Admin Key",
        type="password",
        placeholder="Enter key...",
        label_visibility="collapsed",
        key="sidebar_admin_password",
    )
    if st.sidebar.button("Log in", type="primary", key="btn_admin_login", use_container_width=True):
        if not admin_input or not admin_input.strip():
            st.sidebar.warning("Please enter the admin key.")
        else:
            with st.sidebar.status("Verifying key...", expanded=False):
                code, msg = verify_admin_key(admin_input)
            if code == 204:
                st.session_state["admin_authenticated"] = True
                st.session_state["admin_key"] = admin_input.strip()
                st.rerun()
            elif code == 401:
                st.sidebar.error("Wrong admin key")
            elif code == 503:
                st.sidebar.error("Admin not configured")
            else:
                st.sidebar.error(f"Login failed: {msg}")

# ─── Sidebar Footer: Health Indicator ──────────────────────────────────────────
st.sidebar.markdown("---")
footer_html = f"""
<div style="margin-top: 4px;">
    <div>{status_indicator_html}</div>
"""
if health_status in ("offline", "degraded") and health_detail:
    footer_html += f'<div style="font-size: 0.78rem; color: #8a8a8f; margin-top: 4px; word-break: break-word;">{health_detail}</div>'

footer_html += "</div>"
st.sidebar.markdown(html(footer_html), unsafe_allow_html=True)


# ─── Main Content Header & Page Dispatch ───────────────────────────────────────
st.markdown(
    html(
        f"""
        <div class="aco-wordmark" style="text-align: center; margin-top: 8px; margin-bottom: 24px;">
            <div style="display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 6px;">
                {LOGO_SVG_36}
                <h1 style="font-size: 2.6rem; font-weight: 700; margin: 0; letter-spacing: -0.02em;">Acosign</h1>
            </div>
            <p style="color: #8a8a8f; font-size: 1.05rem; margin: 0;">Audio fingerprinting and Content ID</p>
        </div>
        """
    ),
    unsafe_allow_html=True,
)

# Route to active page
current_page = st.session_state["selected_page"]

if current_page == "Identify":
    render_identify_page()
elif current_page == "Tracks":
    render_tracks_page()
elif current_page == "Developers":
    render_developers_page()
elif current_page == "Register":
    if not is_admin:
        st.error("Admin authentication required.")
    else:
        render_register_page()
elif current_page == "Manage tracks":
    if not is_admin:
        st.error("Admin authentication required.")
    else:
        render_manage_tracks_page()
else:
    render_identify_page()
