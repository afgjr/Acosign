"""Central configuration for all Acosign tunables.

All magic numbers live here (AGENT.md Rule 2).
Values are overridable via environment variables or a .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Acosign application settings.

    Audio fingerprinting parameters follow the Dejavu algorithm reference:
    spectrogram → peak detection → hash pairs → offset-vote matching.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Audio loading                                                        #
    # ------------------------------------------------------------------ #

    SAMPLE_RATE: int = 22050
    """Target sample rate (Hz) to which all audio is resampled on load.
    22 050 Hz covers the full musical range while keeping arrays compact."""

    MIN_AUDIO_DURATION: float = 1.0
    """Minimum audio duration in seconds. Audio shorter than this is rejected."""

    # ------------------------------------------------------------------ #
    # Spectrogram                                                          #
    # ------------------------------------------------------------------ #

    N_FFT: int = 4096
    """FFT window size in samples.
    Larger windows give finer frequency resolution at the cost of time
    resolution.  4096 ≈ 186 ms at 22 050 Hz — a good trade-off for music."""

    HOP_LENGTH: int = 2048
    """Number of samples between successive FFT frames (50 % overlap).
    Overlap ensures peaks near frame boundaries are captured."""

    TOP_DB: float = 80.0
    """Dynamic range in dB for spectrogram normalization relative to peak magnitude."""

    # ------------------------------------------------------------------ #
    # Peak detection                                                       #
    # ------------------------------------------------------------------ #

    PEAK_NEIGHBORHOOD_SIZE: int = 20
    """Radius (in time–frequency bins) of the local-max neighbourhood.
    A peak must be the maximum within a (2N+1)×(2N+1) box."""

    MIN_AMPLITUDE: float = 10.0
    """Minimum log-magnitude (dB above the noise floor) for a bin to be
    considered a peak.  Raise to suppress weak / noisy peaks."""

    # ------------------------------------------------------------------ #
    # Hash generation                                                      #
    # ------------------------------------------------------------------ #

    FAN_OUT: int = 5
    """Number of target peaks paired with each anchor peak.
    Higher fan-out → more hashes → more robust matching, more DB space."""

    MIN_DELTA_T: int = 1
    """Minimum time-frame gap between an anchor and its target peak.
    Prevents pairing peaks on the same frame."""

    MAX_DELTA_T: int = 200
    """Maximum time-frame gap between an anchor and its target peak (~18 s
    at hop=2048, sr=22050).  Caps the combinatorial explosion of hashes."""

    # ------------------------------------------------------------------ #
    # Matching                                                             #
    # ------------------------------------------------------------------ #

    MIN_MATCH_SCORE: int = 5
    """Minimum number of aligned hash-pair offsets required to declare a
    match.  Lower → more false positives; higher → misses short clips."""

    # ------------------------------------------------------------------ #
    # Database                                                             #
    # ------------------------------------------------------------------ #

    DATABASE_URL: str = (
        "postgresql://insa_user:secure_password@localhost:5432/audio_signature_db"
    )
    """SQLAlchemy connection string.  Override via DATABASE_URL env var or
    .env file.  Never hardcode credentials in source."""


# Module-level singleton — import this everywhere instead of instantiating
# Settings() repeatedly.
settings = Settings()
