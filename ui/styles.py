"""Styling definitions and visual helper functions for the Acosign UI."""

from __future__ import annotations

import io
import wave
import numpy as np

CUSTOM_CSS = """
<style>
/* Base Theme Colors & Font */
:root {
    --bg-color: #0b0b0c;
    --surface-color: #1a1a1c;
    --text-color: #f5f5f4;
    --muted-color: #8a8a8f;
    --accent-yellow: #f5f26b;
}

body, .stApp {
    background-color: #0b0b0c !important;
    color: #f5f5f4 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}

/* Centered layout, max width ~720px, generous spacing */
.block-container {
    max-width: 720px !important;
    padding-top: 2rem !important;
    padding-bottom: 5rem !important;
    margin: 0 auto !important;
}

/* Headings */
h1, h2, h3, h4, .stHeading {
    color: #f5f5f4 !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em !important;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: #121214 !important;
    border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
}

/* Sidebar Navigation Radio Buttons: styled as sleek pills */
[data-testid="stSidebar"] div[role="radiogroup"] {
    gap: 6px;
}
[data-testid="stSidebar"] div[role="radiogroup"] label {
    background-color: #1a1a1c !important;
    border-radius: 999px !important;
    padding: 8px 16px !important;
    margin-bottom: 4px !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
    border-color: rgba(245, 242, 107, 0.4) !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"],
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background-color: #f5f26b !important;
    border-color: #f5f26b !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] p,
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
    color: #0b0b0c !important;
    font-weight: 700 !important;
}

/* Cards: 24px radius, no hard borders */
.aco-card {
    background-color: #1a1a1c;
    border-radius: 24px;
    padding: 24px;
    margin-bottom: 20px;
    border: none;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
}

.aco-track-row {
    background-color: #1a1a1c;
    border-radius: 24px;
    padding: 20px 24px;
    margin-bottom: 14px;
    border: none;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.2);
}

/* Buttons: pill-shaped (999px) */
.stButton > button,
button[kind="primary"],
button[kind="secondary"],
button[data-testid="baseButton-primary"],
button[data-testid="baseButton-secondary"] {
    border-radius: 999px !important;
    padding: 0.55rem 1.4rem !important;
    font-weight: 600 !important;
    border: none !important;
    transition: all 0.15s ease-in-out !important;
}

/* Primary button: yellow with black text */
.stButton > button[kind="primary"],
button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background-color: #f5f26b !important;
    color: #0b0b0c !important;
}
.stButton > button[kind="primary"]:hover,
button[kind="primary"]:hover {
    background-color: #f3ef4f !important;
    color: #000000 !important;
    box-shadow: 0 0 16px rgba(245, 242, 107, 0.35) !important;
}

/* Secondary button */
.stButton > button[kind="secondary"],
button[kind="secondary"],
button[data-testid="baseButton-secondary"] {
    background-color: #1a1a1c !important;
    color: #f5f5f4 !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
}
.stButton > button[kind="secondary"]:hover,
button[kind="secondary"]:hover {
    background-color: #262629 !important;
    color: #ffffff !important;
}

/* Pill-shaped inputs */
div[data-baseweb="input"],
.stTextInput > div > div,
.stNumberInput > div > div,
.stSelectbox > div > div {
    border-radius: 999px !important;
    background-color: #1a1a1c !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    padding: 2px 12px !important;
}
div[data-baseweb="input"]:focus-within {
    border-color: #f5f26b !important;
}
input.stTextInput {
    color: #f5f5f4 !important;
}

/* Text area (for description): 20px radius */
.stTextArea textarea {
    border-radius: 20px !important;
    background-color: #1a1a1c !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    color: #f5f5f4 !important;
}
.stTextArea textarea:focus {
    border-color: #f5f26b !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background-color: #1a1a1c !important;
    border-radius: 24px !important;
    border: 1px dashed rgba(255, 255, 255, 0.12) !important;
    padding: 12px 18px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #f5f26b !important;
}
[data-testid="stFileUploader"] button {
    border-radius: 999px !important;
}

/* Audio input mic widget */
[data-testid="stAudioInput"] {
    background-color: #1a1a1c !important;
    border-radius: 24px !important;
    padding: 12px !important;
    border: none !important;
}
</style>
"""


def compute_waveform_envelope(audio_bytes: bytes, num_bars: int = 60) -> list[float] | None:
    """Compute amplitude envelope for ~60 vertical bars from WAV audio bytes.

    Uses only numpy and wave. If format cannot be parsed (e.g. non-WAV),
    returns None silently.
    """
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            n_frames = wf.getnframes()
            if n_frames <= 0:
                return None
            raw_frames = wf.readframes(n_frames)

            if sampwidth == 1:
                data = np.frombuffer(raw_frames, dtype=np.uint8).astype(np.float32) - 128.0
            elif sampwidth == 2:
                data = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32)
            elif sampwidth == 4:
                data = np.frombuffer(raw_frames, dtype=np.int32).astype(np.float32)
            else:
                return None

            if n_channels > 1:
                data = data.reshape(-1, n_channels).mean(axis=1)

            abs_data = np.abs(data)
            if len(abs_data) == 0:
                return None

            if len(abs_data) < num_bars:
                bars = np.pad(abs_data, (0, num_bars - len(abs_data)), mode="edge")
            else:
                chunk_size = len(abs_data) // num_bars
                trimmed = abs_data[: chunk_size * num_bars]
                bars = trimmed.reshape(num_bars, chunk_size).mean(axis=1)

            max_val = float(np.max(bars))
            if max_val > 0:
                normalized = (bars / max_val).tolist()
            else:
                normalized = [0.15] * num_bars
            return normalized
    except Exception:
        return None


def render_waveform_html(envelope: list[float], progress_pct: float = 0.58) -> str:
    """Render amplitude envelope as ~60 vertical bars with yellow played bars and gray rest."""
    num_bars = len(envelope)
    progress_point = int(num_bars * progress_pct)
    bars_html = []
    for i, val in enumerate(envelope):
        height_px = max(5, int(val * 40))
        color = "#f5f26b" if i <= progress_point else "#3a3a3e"
        bars_html.append(
            f'<div style="width: 4px; height: {height_px}px; background-color: {color}; '
            f'border-radius: 2px; flex-shrink: 0;"></div>'
        )
    return (
        '<div style="display: flex; align-items: center; justify-content: space-between; '
        'height: 48px; background: #121214; border-radius: 14px; padding: 0 14px; '
        'margin: 16px 0; gap: 3px; overflow: hidden;">'
        + "".join(bars_html)
        + "</div>"
    )
