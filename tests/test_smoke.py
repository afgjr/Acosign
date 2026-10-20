"""Smoke tests — verify that every sub-package is importable and that
Settings loads with its default values.

These tests have NO external dependencies (no database, no audio files).
They will fail fast if a package is missing or mis-named.
"""

import importlib

import pytest


# ────────────────────────────────────────────────────────────────────────────
# Import smoke tests
# ────────────────────────────────────────────────────────────────────────────


def test_import_app_main() -> None:
    """app.main must be importable and expose a FastAPI ``app`` object."""
    mod = importlib.import_module("app.main")
    assert hasattr(mod, "app"), "app.main must define a FastAPI 'app' instance"


def test_import_app_core_config() -> None:
    """app.core.config must be importable and expose Settings + settings."""
    mod = importlib.import_module("app.core.config")
    assert hasattr(mod, "Settings"), "app.core.config must define a Settings class"
    assert hasattr(mod, "settings"), "app.core.config must define a 'settings' singleton"


def test_import_app_engine() -> None:
    """app.engine package must be importable (Phase-1 stub acceptable)."""
    importlib.import_module("app.engine")


def test_import_app_db() -> None:
    """app.db package must be importable (Phase-2 stub acceptable)."""
    importlib.import_module("app.db")


def test_import_app_api() -> None:
    """app.api package must be importable (Phase-2 stub acceptable)."""
    importlib.import_module("app.api")


# ────────────────────────────────────────────────────────────────────────────
# Settings validation
# ────────────────────────────────────────────────────────────────────────────


def test_settings_loads() -> None:
    """Settings must instantiate successfully using default values."""
    from app.core.config import Settings

    s = Settings()
    assert isinstance(s, Settings)


def test_settings_sample_rate() -> None:
    """Default SAMPLE_RATE must be 22050 Hz."""
    from app.core.config import Settings

    assert Settings().SAMPLE_RATE == 22050


def test_settings_n_fft() -> None:
    """Default N_FFT must be 4096."""
    from app.core.config import Settings

    assert Settings().N_FFT == 4096


def test_settings_hop_length() -> None:
    """Default HOP_LENGTH must be 2048."""
    from app.core.config import Settings

    assert Settings().HOP_LENGTH == 2048


def test_settings_fan_out() -> None:
    """Default FAN_OUT must be 5."""
    from app.core.config import Settings

    assert Settings().FAN_OUT == 5


def test_settings_min_match_score() -> None:
    """Default MIN_MATCH_SCORE must be 5."""
    from app.core.config import Settings

    assert Settings().MIN_MATCH_SCORE == 5


def test_settings_database_url_not_empty() -> None:
    """DATABASE_URL must be a non-empty string."""
    from app.core.config import Settings

    url = Settings().DATABASE_URL
    assert isinstance(url, str) and url.strip(), "DATABASE_URL must not be empty"
