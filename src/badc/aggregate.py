"""Detection aggregation utilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class DetectionRecord:
    chunk_id: str
    recording_id: str
    status: str
    raw: dict


def load_detections(root: Path) -> List[DetectionRecord]:
    records: List[DetectionRecord] = []
    for path in root.rglob("*.json"):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        chunk_id = data.get("chunk_id", path.stem)
        recording_id = path.parent.name
        records.append(
            DetectionRecord(
                chunk_id=chunk_id,
                recording_id=recording_id,
                status=data.get("status", "unknown"),
                raw=data,
            )
        )
    return records


def write_summary_csv(records: Iterable[DetectionRecord], out_path: Path) -> Path:
    lines = ["recording_id,chunk_id,status"]
    for rec in records:
        lines.append(f"{rec.recording_id},{rec.chunk_id},{rec.status}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")
    return out_path
