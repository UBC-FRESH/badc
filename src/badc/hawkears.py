"""Helpers for interacting with the embedded HawkEars submodule."""

from __future__ import annotations

from pathlib import Path

HAWKEARS_ROOT = Path(__file__).resolve().parents[2] / "vendor" / "HawkEars"


def get_hawkears_root() -> Path:
    """Return the absolute path to the HawkEars submodule.

    Returns
    -------
    Path
        Root of ``vendor/HawkEars`` within the repository.

    Raises
    ------
    FileNotFoundError
        If the HawkEars directory cannot be located (e.g., submodule not initialised).
    """

    if not HAWKEARS_ROOT.exists():
        raise FileNotFoundError(
            "HawkEars submodule not found. Run 'git submodule update --init --recursive'."
        )
    return HAWKEARS_ROOT
