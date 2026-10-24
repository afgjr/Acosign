"""Developers page: API quickstart, interactive Try It tester, and reference tables."""

from __future__ import annotations

import streamlit as st

from ui.api_client import API_URL, identify_audio
from ui.styles import html


def render_developers_page() -> None:
    """Render the developer API documentation and tester."""
    st.markdown(
        html(
            """
            <div style="margin-bottom: 20px;">
                <h1 style="font-size: 2.2rem; font-weight: 800; margin-bottom: 4px;">Developer API</h1>
                <div style="color: #8a8a8f; font-size: 1rem;">Use the Acosign API to identify audio in your own app.</div>
            </div>
            """
        ),
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
with open("query_clip.wav", "rb") as f:
    response = requests.post(url, files={{"file": f}})

print(response.json())"""
    st.markdown("**Python (requests)**")
    st.code(python_snippet, language="python")

    st.caption(
        "Note: Mutating administrative endpoints (POST /register and DELETE /tracks/{content_id}) "
        "require the 'X-API-Key' header with a valid admin key."
    )

    st.markdown("---")

    # Interactive Try It Section
    st.markdown("### Try It")
    st.write("Upload an audio clip to test `POST /identify` and inspect the raw JSON response:")

    dev_try_file = st.file_uploader(
        "Choose an audio snippet",
        type=["mp3", "wav", "m4a"],
        key="uploader_developer_try",
    )
    if st.button("Send Request", type="primary", key="btn_dev_try"):
        if not dev_try_file:
            st.warning("Please upload an audio file first.")
        else:
            with st.spinner("Submitting to POST /identify..."):
                file_name = dev_try_file.name
                mime_type = dev_try_file.type or "application/octet-stream"
                audio_bytes = dev_try_file.getvalue()

                status_code, result = identify_audio(file_name, audio_bytes, mime_type)
                st.markdown(f"**HTTP Status:** `{status_code}`")
                if isinstance(result, dict):
                    st.json(result)
                else:
                    st.text(str(result))

    st.markdown("---")

    # Response fields reference table
    st.markdown("### Response Fields")
    st.markdown(
        """
| Field | Type | Description |
| :--- | :--- | :--- |
| `matched` | boolean | `true` if an acoustic match was identified above threshold |
| `content_id` | string \\| null | Unique Content ID assigned to the registered track |
| `title` | string \\| null | Registered track title |
| `owner` | string \\| null | Registered track rights holder or artist |
| `album` | string \\| null | Registered album or collection name |
| `genre` | string \\| null | Registered music or audio genre |
| `release_year` | integer \\| null | Track release year |
| `isrc` | string \\| null | International Standard Recording Code |
| `license_type` | string \\| null | Licensing terms or distribution model |
| `description` | string \\| null | Extended metadata or notes |
| `score` | integer | Number of matching fingerprint hash collisions |
| `match_strength` | string | Match confidence: `"strong"` or `"weak"` |
| `offset_seconds` | float | Temporal offset in seconds between clip and master track |
"""
    )

    # Status codes list
    st.markdown("### Status Codes")
    st.markdown(
        """
- `200 OK`: Query processed successfully. Inspect the `matched` boolean in the JSON payload.
- `400 Bad Request`: Audio file is corrupt, unreadable, or shorter than 3.0 seconds.
- `413 Payload Too Large`: Uploaded file exceeds server upload limits (25 MB default).
- `422 Unprocessable Entity`: Invalid request parameters or missing file payload.
"""
    )

    st.info(
        "Note: Identify is open for the demo; per-developer keys and rate limits would be added in production as future work."
    )
