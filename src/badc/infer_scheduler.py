"""Inference scheduler scaffolding."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List

from badc.gpu import detect_gpus


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
