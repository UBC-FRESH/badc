"""Telemetry logging utilities."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class TelemetryRecord:
    chunk_id: str
    gpu_index: int | None
    gpu_name: str | None
    status: str
    timestamp: str
    runtime_s: float | None
    details: dict[str, Any]


def log_telemetry(record: TelemetryRecord, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a") as fh:
        fh.write(json.dumps(asdict(record)) + "\n")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
