"""Lightweight scheduler helpers used by ``badc infer run``.

This module keeps queue management simple inside the Typer CLI while centralizing
how manifests become jobs, how GPU resources are described, and how telemetry is
recorded. Refer to ``notes/inference-plan.md`` for lifecycle details.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

from badc.gpu import detect_gpus
from badc.telemetry import TelemetryRecord, log_telemetry, now_iso


@dataclass
class InferenceJob:
    """Unit of work representing one chunk entry from a manifest."""

    chunk_id: str
    """Unique identifier for the chunk (matches manifest column)."""

    chunk_path: Path
    """Filesystem path to the chunk WAV that HawkEars should consume."""

    recording_id: str
    """Recording identifier used to group outputs and telemetry."""


@dataclass
class GPUWorker:
    """Description of a GPU slot available to the scheduler."""

    index: int
    """CUDA device index used in ``CUDA_VISIBLE_DEVICES``."""

    name: str
    """Human-readable GPU name from ``nvidia-smi``."""


def load_jobs(manifest: Path) -> List[InferenceJob]:
    """Parse a chunk manifest into ``InferenceJob`` objects.

    Parameters
    ----------
    manifest
        Path to a CSV containing ``chunk_id``, ``source_path``, ``recording_id``.

    Returns
    -------
    list of InferenceJob
        Ready-to-run jobs preserving the manifest order.
    """

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
    """Detect GPUs and return worker descriptors.

    Parameters
    ----------
    max_gpus
        Optional ceiling on the number of GPUs to schedule.

    Returns
    -------
    list of GPUWorker
        GPU indices/names suitable for binding to worker threads.
    """

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
    finished_at: str | None = None,
) -> None:
    """Persist a telemetry record to ``data/telemetry/infer/log.jsonl``.

    Parameters
    ----------
    chunk_id
        Identifier for the chunk whose status is being logged.
    worker
        GPU metadata (or ``None`` for CPU workers).
    status
        Event name such as ``start``, ``success``, or ``failure``.
    details
        Arbitrary JSON-serializable payload describing the event.
    runtime_s
        Optional runtime duration for completed events.
    finished_at
        ISO timestamp for completion when available.
    """

    record = TelemetryRecord(
        chunk_id=chunk_id,
        gpu_index=worker.index if worker else None,
        gpu_name=worker.name if worker else None,
        status=status,
        timestamp=now_iso(),
        finished_at=finished_at,
        runtime_s=runtime_s,
        details=details,
    )
    log_telemetry(record, Path("data/telemetry/infer/log.jsonl"))
