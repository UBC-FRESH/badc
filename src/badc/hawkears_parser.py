"""Helpers for parsing HawkEars CSV outputs into canonical detections."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

LABELS_FILENAME = "HawkEars_labels.csv"


def _seconds_to_ms(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value) * 1000)
    except ValueError:
        return None


def parse_hawkears_labels(
    csv_path: Path,
    *,
    chunk_names: Iterable[str],
) -> tuple[list[dict[str, object]], str]:
    """Return detections harvested from ``HawkEars_labels.csv``.

    Parameters
    ----------
    csv_path
        Path to the HawkEars CSV file written by ``analyze.py``.
    chunk_names
        Iterable of filenames that should be associated with the current chunk.
        HawkEars writes annex-resolved names when chunk WAVs live in git-annex;
        pass every acceptable stem so detections are not filtered out.

    Returns
    -------
    tuple
        Two-tuple of ``(detections, status)`` where detections is a list of
        dictionaries containing ``timestamp_ms``, ``end_ms``, ``label``,
        ``label_code``, ``label_name``, and ``confidence``. ``status`` is one of
        ``"ok"``, ``"no_detections"``, or ``"no_output"``.
    """

    normalized_names = {Path(name).name for name in chunk_names if name}
    if not csv_path.exists():
        return [], "no_output"

    detections: list[dict[str, object]] = []
    with csv_path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            filename = Path(row.get("filename", "")).name
            if normalized_names and filename and filename not in normalized_names:
                continue
            label_code = row.get("class_code") or None
            label_name = row.get("class_name") or None
            label = label_code or label_name or "unknown"
            detections.append(
                {
                    "timestamp_ms": _seconds_to_ms(row.get("start_time")),
                    "end_ms": _seconds_to_ms(row.get("end_time")),
                    "label_code": label_code,
                    "label_name": label_name,
                    "label": label,
                    "confidence": float(row["score"]) if row.get("score") else None,
                }
            )
    status = "ok" if detections else "no_detections"
    return detections, status
