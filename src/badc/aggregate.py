"""Detection aggregation utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class DetectionRecord:
    """Normalized detection entry used for CSV summaries."""

    recording_id: str
    chunk_id: str
    timestamp_ms: int | None
    label: str
    confidence: float | None
    status: str
    source_path: Path


def _parse_detection_entries(
    data: dict, recording_id: str, chunk_id: str, source_path: Path
) -> list[DetectionRecord]:
    records: list[DetectionRecord] = []
    detections = data.get("detections")
    if isinstance(detections, list) and detections:
        for det in detections:
            records.append(
                DetectionRecord(
                    recording_id=recording_id,
                    chunk_id=chunk_id,
                    timestamp_ms=int(det.get("timestamp_ms", 0)),
                    label=str(det.get("label", "unknown")),
                    confidence=float(det.get("confidence", 0.0))
                    if det.get("confidence") is not None
                    else None,
                    status="ok",
                    source_path=source_path,
                )
            )
    else:
        records.append(
            DetectionRecord(
                recording_id=recording_id,
                chunk_id=chunk_id,
                timestamp_ms=None,
                label="none",
                confidence=None,
                status=data.get("status", "unknown"),
                source_path=source_path,
            )
        )
    return records


def load_detections(root: Path) -> List[DetectionRecord]:
    """Load detection JSON payloads under ``root``.

    Parameters
    ----------
    root
        Directory containing per-chunk JSON files (one per inference run).

    Returns
    -------
    list of DetectionRecord
        Parsed detections, one record per event or status placeholder.
    """

    records: List[DetectionRecord] = []
    for path in root.rglob("*.json"):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        chunk_id = data.get("chunk_id", path.stem)
        recording_id = path.parent.name
        records.extend(_parse_detection_entries(data, recording_id, chunk_id, path))
    return records


def write_summary_csv(records: Iterable[DetectionRecord], out_path: Path) -> Path:
    """Write detection records to ``out_path`` in CSV form.

    Parameters
    ----------
    records
        Iterable of :class:`DetectionRecord` objects.
    out_path
        Destination CSV path. Parent directories are created automatically.

    Returns
    -------
    Path
        The ``out_path`` provided (for chaining).
    """

    lines = ["recording_id,chunk_id,timestamp_ms,label,confidence,status,source_path"]
    for rec in records:
        ts = "" if rec.timestamp_ms is None else rec.timestamp_ms
        conf = "" if rec.confidence is None else rec.confidence
        lines.append(
            f"{rec.recording_id},{rec.chunk_id},{ts},{rec.label},{conf},{rec.status},{rec.source_path}"
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    return out_path
