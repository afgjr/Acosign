import streamlit as st
import requests
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="AudioSignature", page_icon="í¾µ", layout="wide")

st.title("í¾µ AudioSignature Dashboard")
st.caption("Acoustic Fingerprinting & Cryptographic Provenance Platform")

tab1, tab2 = st.tabs(["Register Track", "Verify Audio Clip"])

with tab1:
    st.subheader("Register Original Track")
    artist = st.text_input("Artist / Label Name")
    title = st.text_input("Track Title")
    uploaded_file = st.file_uploader("Upload Audio (WAV/MP3)", type=["wav", "mp3"], key="register")
    if st.button("Generate Signature & Register", type="primary"):
        st.info("Registration endpoint will be connected once the DB schema is linked.")

with tab2:
    st.subheader("Verify & Match Clip")
    verify_file = st.file_uploader("Upload Query Sample", type=["wav", "mp3"], key="verify")
    if st.button("Audit / Check Copyright"):
        st.info("Acoustic lookup endpoint will be connected once the DB schema is linked.")
