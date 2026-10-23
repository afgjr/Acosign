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

from ui.api_client import API_URL, check_api_health, verify_admin_key
from ui.styles import CUSTOM_CSS
from ui.views.developers import render_developers_page
from ui.views.identify import render_identify_page
from ui.views.manage_tracks import render_manage_tracks_page
from ui.views.register import render_register_page
from ui.views.tracks import render_tracks_page

st.set_page_config(
    page_title="Acosign",
    page_icon="🎵",
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


# ─── Sidebar Navigation & Health ───────────────────────────────────────────────
st.sidebar.markdown(
    """
    <div style="margin-bottom: 12px;">
        <h2 style="font-size: 1.5rem; font-weight: 800; margin: 0; color: #f5f5f4;">🎵 Acosign</h2>
        <div style="font-size: 0.82rem; color: #8a8a8f; margin-top: 2px;">Audio Fingerprinting & Content ID</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Health Indicator
healthy, health_msg = check_api_health(API_URL)
if healthy:
    st.sidebar.success(health_msg)
else:
    st.sidebar.error(health_msg)

if st.sidebar.button("Refresh Status", key="btn_refresh_status"):
    st.rerun()

st.sidebar.markdown("---")

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
    st.sidebar.markdown(
        """
        <div style="background: rgba(245, 242, 107, 0.1); border: 1px solid rgba(245, 242, 107, 0.2); border-radius: 16px; padding: 12px; margin-bottom: 12px;">
            <div style="color: #f5f26b; font-weight: 700; font-size: 0.9rem;">🔒 Admin Mode</div>
            <div style="color: #8a8a8f; font-size: 0.8rem; margin-top: 2px;">Register & catalog management unlocked</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.sidebar.button("Log out", key="btn_admin_logout", use_container_width=True):
        st.session_state["admin_authenticated"] = False
        st.session_state["admin_key"] = ""
        if st.session_state["selected_page"] in ("Register", "Manage tracks"):
            st.session_state["selected_page"] = "Identify"
        st.rerun()
else:
    st.sidebar.markdown("<div style='font-size: 0.9rem; font-weight: 700; color: #f5f5f4; margin-bottom: 6px;'>Admin Access</div>", unsafe_allow_html=True)
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

st.sidebar.markdown("---")
st.sidebar.caption(f"Backend API: `{API_URL}`")


# ─── Main Content Header & Page Dispatch ───────────────────────────────────────
st.markdown(
    """
    <div style="text-align: center; margin-top: 8px; margin-bottom: 24px;">
        <h1 style="font-size: 2.6rem; font-weight: 800; margin: 0 0 6px 0; letter-spacing: -0.03em;">Acosign</h1>
        <p style="color: #8a8a8f; font-size: 1.05rem; margin: 0;">Audio fingerprinting and Content ID</p>
    </div>
    """,
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
