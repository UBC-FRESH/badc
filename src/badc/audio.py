"""Audio helper utilities for chunk manifests."""

from __future__ import annotations

import wave
from pathlib import Path


def get_wav_duration(path: Path) -> float:
    """Return WAV duration in seconds."""

    if not path.exists():
        raise FileNotFoundError(path)
    with wave.open(str(path), "rb") as fh:
        frames = fh.getnframes()
        rate = fh.getframerate()
    if rate == 0:
        raise ValueError("Invalid WAV file: frame rate is zero")
    return frames / float(rate)
