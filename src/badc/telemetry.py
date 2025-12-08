"""Telemetry logging utilities."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class TelemetryRecord:
    """Serializable telemetry payload for scheduler events."""

    chunk_id: str
    gpu_index: int | None
    gpu_name: str | None
    status: str
    timestamp: str
    finished_at: str | None
    runtime_s: float | None
    details: dict[str, Any]


def log_telemetry(record: TelemetryRecord, out_path: Path) -> None:
    """Append ``record`` to ``out_path`` as a JSON line.

    Parameters
    ----------
    record
        Telemetry payload to serialize.
    out_path
        Log file path (created if missing).
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a") as fh:
        fh.write(json.dumps(asdict(record)) + "\n")


def now_iso() -> str:
    """Return the current UTC timestamp in ISO-8601 form.

    Returns
    -------
    str
        Timestamp including timezone offset (``+00:00``).
    """

    return datetime.now(UTC).isoformat()


def default_log_path(
    manifest: Path,
    *,
    base_dir: Path | None = None,
    timestamp: str | None = None,
) -> Path:
    """Return a run-specific telemetry log path derived from ``manifest``.

    Parameters
    ----------
    manifest
        Manifest driving the inference run.
    base_dir
        Override for the telemetry directory (defaults to ``data/telemetry/infer``).
    timestamp
        Optional timestamp slug for deterministic tests.
    """

    slug = manifest.stem.replace(" ", "_")
    stamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    directory = base_dir or Path("data/telemetry/infer")
    return directory / f"{slug}_{stamp}.jsonl"


def load_telemetry(path: Path) -> list[TelemetryRecord]:
    """Load telemetry records from ``path`` (if it exists).

    Parameters
    ----------
    path
        JSONL log file produced by :func:`log_telemetry`.

    Returns
    -------
    list of TelemetryRecord
        Parsed records ordered as they appear in the file.
    """

    if not path.exists():
        return []
    records: list[TelemetryRecord] = []
    for line in path.read_text().splitlines():
        if not line:
            continue
        data = json.loads(line)
        records.append(
            TelemetryRecord(
                chunk_id=data["chunk_id"],
                gpu_index=data.get("gpu_index"),
                gpu_name=data.get("gpu_name"),
                status=data.get("status", "unknown"),
                timestamp=data.get("timestamp", ""),
                finished_at=data.get("finished_at"),
                runtime_s=data.get("runtime_s"),
                details=data.get("details", {}),
            )
        )
    return records
