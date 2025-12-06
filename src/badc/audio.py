"""Audio helper utilities for chunk manifests."""

from __future__ import annotations

import hashlib
import wave
from pathlib import Path


def get_wav_duration(path: Path) -> float:
    """Return WAV duration in seconds.

    Parameters
    ----------
    path
        Path to a local WAV file.

    Returns
    -------
    float
        Duration in seconds.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the WAV header reports a zero frame rate.
    """

    if not path.exists():
        raise FileNotFoundError(path)
    with wave.open(str(path), "rb") as fh:
        frames = fh.getnframes()
        rate = fh.getframerate()
    if rate == 0:
        raise ValueError("Invalid WAV file: frame rate is zero")
    return frames / float(rate)


def compute_sha256(path: Path) -> str:
    """Return SHA256 hash of the file contents.

    Parameters
    ----------
    path
        File whose contents should be hashed.

    Returns
    -------
    str
        Hex-encoded SHA256 digest.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    """

    if not path.exists():
        raise FileNotFoundError(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
