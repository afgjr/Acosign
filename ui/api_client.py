"""HTTP client functions for communicating with the Acosign backend API."""

from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_API_URL = "http://localhost:8000"
API_URL = os.getenv("API_URL", DEFAULT_API_URL).rstrip("/")
REQUEST_TIMEOUT = 180  # seconds


def extract_error_detail(response: requests.Response) -> str:
    """Extract clean, readable error detail message from FastAPI HTTP error response."""
    try:
        data = response.json()
        detail = data.get("detail", response.text)
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            messages = []
            for item in detail:
                if isinstance(item, dict):
                    loc = " -> ".join(str(x) for x in item.get("loc", []))
                    msg = item.get("msg", "")
                    messages.append(f"{loc}: {msg}" if loc else msg)
                else:
                    messages.append(str(item))
            return "; ".join(messages)
        if isinstance(detail, dict):
            return str(detail.get("message", detail))
        return str(detail)
    except Exception:
        return response.text or f"HTTP status {response.status_code}"


def check_api_health(base_url: str = API_URL) -> tuple[bool, str]:
    """Call GET /health and return (is_healthy, status_message)."""
    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            api_status = data.get("status")
            db_status = data.get("database")
            if api_status == "ok" and db_status == "ok":
                return True, "API and database ok"
            return False, f"API ok, but database is {db_status}"
        return False, f"Health check failed (HTTP {resp.status_code})"
    except requests.exceptions.RequestException:
        return False, "API unreachable"


def verify_admin_key(admin_key: str, base_url: str = API_URL) -> tuple[int, str]:
    """Verify administrator key via GET /admin/verify.

    Returns:
        (status_code, message)
        204 -> Authorized
        401 -> Wrong admin key
        503 -> Admin not configured
    """
    if not admin_key or not admin_key.strip():
        return 401, "Admin key cannot be empty"
    try:
        headers = {"X-API-Key": admin_key.strip()}
        resp = requests.get(f"{base_url}/admin/verify", headers=headers, timeout=10)
        if resp.status_code == 204:
            return 204, "Authorized"
        if resp.status_code == 401:
            return 401, "Wrong admin key"
        if resp.status_code == 503:
            return 503, "Admin not configured"
        return resp.status_code, extract_error_detail(resp)
    except requests.exceptions.RequestException:
        return 0, "API unreachable"


def identify_audio(
    file_name: str,
    file_bytes: bytes,
    mime_type: str,
    base_url: str = API_URL,
) -> tuple[int, dict[str, Any] | str]:
    """Submit audio clip to POST /identify."""
    try:
        files = {"file": (file_name, file_bytes, mime_type)}
        resp = requests.post(f"{base_url}/identify", files=files, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            return 200, resp.json()
        return resp.status_code, extract_error_detail(resp)
    except requests.exceptions.RequestException:
        return 0, "Unable to connect to the API server."


def register_track(
    file_name: str,
    file_bytes: bytes,
    mime_type: str,
    metadata: dict[str, Any],
    admin_key: str,
    base_url: str = API_URL,
) -> tuple[int, dict[str, Any] | str]:
    """Upload and register a track via POST /register."""
    try:
        files = {"file": (file_name, file_bytes, mime_type)}
        # Filter out None values from form data
        data = {k: v for k, v in metadata.items() if v is not None and v != ""}
        headers = {"X-API-Key": admin_key.strip()}
        resp = requests.post(
            f"{base_url}/register",
            files=files,
            data=data,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 201:
            return 201, resp.json()
        if resp.status_code == 401:
            return 401, "Wrong admin key"
        if resp.status_code == 409:
            try:
                err_json = resp.json()
                detail = err_json.get("detail", {})
                cid = detail.get("content_id") if isinstance(detail, dict) else str(detail)
                return 409, f"Track already registered with Content ID: {cid}"
            except Exception:
                return 409, "Track already registered"
        return resp.status_code, extract_error_detail(resp)
    except requests.exceptions.RequestException:
        return 0, "Unable to connect to the API server."


def get_tracks(
    limit: int = 100,
    offset: int = 0,
    base_url: str = API_URL,
) -> tuple[int, list[dict[str, Any]] | str]:
    """Retrieve catalog list from GET /tracks."""
    try:
        resp = requests.get(f"{base_url}/tracks?limit={limit}&offset={offset}", timeout=15)
        if resp.status_code == 200:
            return 200, resp.json()
        return resp.status_code, extract_error_detail(resp)
    except requests.exceptions.RequestException:
        return 0, "Unable to connect to the API server."


def delete_track(
    content_id: str,
    admin_key: str,
    base_url: str = API_URL,
) -> tuple[int, str]:
    """Delete a track via DELETE /tracks/{content_id}."""
    try:
        headers = {"X-API-Key": admin_key.strip()}
        resp = requests.delete(
            f"{base_url}/tracks/{content_id}",
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 204:
            return 204, "Deleted"
        if resp.status_code == 401:
            return 401, "Wrong admin key"
        if resp.status_code == 404:
            return 404, f"Track with Content ID '{content_id}' not found"
        return resp.status_code, extract_error_detail(resp)
    except requests.exceptions.RequestException:
        return 0, "Unable to connect to the API server."
