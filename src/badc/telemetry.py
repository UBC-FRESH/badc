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
    finished_at: str | None
    runtime_s: float | None
    details: dict[str, Any]


def log_telemetry(record: TelemetryRecord, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a") as fh:
        fh.write(json.dumps(asdict(record)) + "\n")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def load_telemetry(path: Path) -> list[TelemetryRecord]:
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
