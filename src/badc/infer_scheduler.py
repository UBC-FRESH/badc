"""Inference scheduler scaffolding."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

from badc.gpu import detect_gpus
from badc.telemetry import TelemetryRecord, log_telemetry, now_iso


@dataclass
class InferenceJob:
    chunk_id: str
    chunk_path: Path
    recording_id: str


@dataclass
class GPUWorker:
    index: int
    name: str


def load_jobs(manifest: Path) -> List[InferenceJob]:
    with manifest.open() as fh:
        reader = csv.DictReader(fh)
        jobs: List[InferenceJob] = []
        for row in reader:
            jobs.append(
                InferenceJob(
                    chunk_id=row["chunk_id"],
                    chunk_path=Path(row["source_path"]),
                    recording_id=row["recording_id"],
                )
            )
    return jobs


def plan_workers(max_gpus: int | None = None) -> List[GPUWorker]:
    infos = detect_gpus()
    if not infos:
        return []
    workers = [GPUWorker(index=info.index, name=info.name) for info in infos]
    if max_gpus is not None:
        workers = workers[:max_gpus]
    return workers


def log_scheduler_event(
    chunk_id: str,
    worker: GPUWorker | None,
    status: str,
    details: dict,
    runtime_s: float | None = None,
) -> None:
    record = TelemetryRecord(
        chunk_id=chunk_id,
        gpu_index=worker.index if worker else None,
        gpu_name=worker.name if worker else None,
        status=status,
        started_at=now_iso(),
        finished_at=None,
        runtime_s=runtime_s,
        details=details,
    )
    log_telemetry(record, Path("data/telemetry/infer/log.jsonl"))
