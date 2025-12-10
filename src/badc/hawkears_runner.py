"""Interface between BADC chunk manifests and HawkEars inference.

`badc infer run` calls this module to execute either the vendored HawkEars
`analyze.py` script or a custom runner, collect outputs, and record telemetry as
outlined in ``notes/inference-plan.md``.
"""

from __future__ import annotations

import csv
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from badc import hawkears
from badc.data import find_dataset_root
from badc.gpu import GPUMetrics, query_gpu_metrics
from badc.infer_scheduler import GPUWorker, InferenceJob, log_scheduler_event
from badc.telemetry import now_iso

RAW_OUTPUT_SUFFIX = "_hawkears"
LABELS_FILENAME = "HawkEars_labels.csv"


@dataclass(slots=True)
class JobResult:
    """Metadata describing the outcome of a ``run_job`` invocation."""

    output_path: Path
    attempts: int
    retries: int


class JobExecutionError(RuntimeError):
    """Raised when a job exhausts its retry budget without succeeding."""

    def __init__(self, chunk_id: str, attempts: int, original: Exception | None = None):
        message = f"Inference failed for {chunk_id} after {attempts} attempt(s)"
        super().__init__(message)
        self.chunk_id = chunk_id
        self.attempts = attempts
        self.original = original


def _metrics_payload(metrics: GPUMetrics | None) -> dict[str, int | None] | None:
    if not metrics:
        return None
    return {
        "index": metrics.index,
        "utilization": metrics.utilization,
        "memory_used_mb": metrics.memory_used_mb,
        "memory_total_mb": metrics.memory_total_mb,
    }


def _chunk_metadata(job: InferenceJob) -> dict[str, int | str | None]:
    return {
        "start_ms": job.start_ms,
        "end_ms": job.end_ms,
        "overlap_ms": job.overlap_ms,
        "sha256": job.sha256,
        "notes": job.notes,
    }


def _build_command(
    runner_cmd: str, job: InferenceJob, output_path: Path
) -> tuple[list[str], Path | None]:
    base = shlex.split(runner_cmd)
    return base + ["--input", str(job.chunk_path), "--output", str(output_path)], None


def _build_hawkears_command(
    job: InferenceJob,
    output_dir: Path,
    extra_args: Sequence[str] | None,
) -> tuple[list[str], Path]:
    root = hawkears.get_hawkears_root()
    script = root / "analyze.py"
    cmd = [
        sys.executable,
        str(script),
        "-i",
        str(job.chunk_path.resolve()),
        "-o",
        str(output_dir.resolve()),
        "--rtype",
        "csv",
        "--merge",
        "0",
    ]
    if extra_args:
        cmd.extend(extra_args)
    return cmd, root


def _write_stub_output(
    job: InferenceJob, output_path: Path, attempt: int, dataset_root: Path | None
) -> None:
    payload = {
        "chunk_id": job.chunk_id,
        "recording_id": job.recording_id,
        "source_path": str(job.chunk_path),
        "status": "stub",
        "detections": [],
        "meta": {"attempt": attempt},
        "chunk": _chunk_metadata(job),
        "runner": "stub",
    }
    if dataset_root:
        payload["dataset_root"] = str(dataset_root)
    output_path.write_text(json.dumps(payload))


def _seconds_to_ms(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value) * 1000)
    except ValueError:
        return None


def _parse_hawkears_labels(
    csv_path: Path,
    job: InferenceJob,
    *,
    dataset_root: Path | None,
    runner: str,
    model_version: str | None = None,
) -> dict:
    detections: list[dict[str, object]] = []
    if csv_path.exists():
        expected_names = {job.chunk_path.name}
        try:
            resolved_name = job.chunk_path.resolve().name
        except FileNotFoundError:
            resolved_name = None
        if resolved_name:
            expected_names.add(resolved_name)
        with csv_path.open() as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                filename = Path(row.get("filename", "")).name
                if filename and filename not in expected_names:
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
    status = "ok" if detections else "no_detections" if csv_path.exists() else "no_output"
    payload = {
        "chunk_id": job.chunk_id,
        "recording_id": job.recording_id,
        "source_path": str(job.chunk_path),
        "status": status,
        "detections": detections,
        "chunk": _chunk_metadata(job),
        "runner": runner,
    }
    if dataset_root:
        payload["dataset_root"] = str(dataset_root)
    if model_version:
        payload["model_version"] = model_version
    return payload


def run_job(
    job: InferenceJob,
    worker: GPUWorker | None,
    output_dir: Path,
    runner_cmd: str | None = None,
    max_retries: int = 2,
    use_hawkears: bool = False,
    hawkears_args: Sequence[str] | None = None,
    dataset_root: Path | None = None,
    telemetry_path: Path | None = None,
) -> JobResult:
    """Execute a single inference job and return the JSON output path.

    Parameters
    ----------
    job
        Chunk metadata describing the recording id, chunk path, and manifest row.
    worker
        GPU affinity information (index + UUID) or ``None`` for CPU runs.
    output_dir
        Root directory that will receive per-recording JSON + HawkEars artifacts.
    runner_cmd
        External command to invoke instead of the built-in HawkEars/stub logic.
    max_retries
        Maximum number of retries for a failing chunk (default ``2``).
    use_hawkears
        When ``True``, run the vendored ``analyze.py`` script and parse its CSV.
    hawkears_args
        Extra arguments forwarded to HawkEars (e.g., ``--config`` flags).
    dataset_root
        Optional DataLad dataset root used to embed provenance in the JSON.

    Returns
    -------
    JobResult
        Information about the completed job (output path, attempts, retries).

    Raises
    ------
    JobExecutionError
        If HawkEars continues to fail after ``max_retries`` attempts.
    subprocess.CalledProcessError
        Propagated when ``runner_cmd`` fails and retries are exhausted.

    Notes
    -----
    This function logs scheduler events via ``log_scheduler_event`` for every
    start/success/failure, including runtime seconds and recent stdout/stderr.
    When ``use_hawkears`` is false and ``runner_cmd`` is ``None``, the stub writer
    emits deterministic JSON for CI coverage.
    """
    recording_dir = output_dir / job.recording_id
    recording_dir.mkdir(parents=True, exist_ok=True)
    output_path = recording_dir / f"{job.chunk_id}.json"
    hawkears_output_dir = recording_dir / f"{job.chunk_id}{RAW_OUTPUT_SUFFIX}"
    dataset_root = dataset_root or find_dataset_root(job.chunk_path)
    runner_label = "hawkears" if use_hawkears else ("custom" if runner_cmd else "stub")

    model_version = hawkears.get_hawkears_version() if use_hawkears else None
    attempts = 0
    while attempts <= max_retries:
        attempts += 1
        start = time.time()
        log_scheduler_event(
            job.chunk_id,
            worker,
            "start",
            {"attempt": attempts},
            telemetry_path=telemetry_path,
        )
        try:
            cmd: list[str] | None = None
            cwd: Path | None = None
            env = os.environ.copy()
            if worker is not None:
                env["CUDA_VISIBLE_DEVICES"] = str(worker.index)

            if runner_cmd:
                cmd, cwd = _build_command(runner_cmd, job, output_path)
            elif use_hawkears:
                if hawkears_output_dir.exists():
                    shutil.rmtree(hawkears_output_dir)
                hawkears_output_dir.mkdir(parents=True, exist_ok=True)
                cmd, cwd = _build_hawkears_command(job, hawkears_output_dir, hawkears_args)
            else:
                _write_stub_output(job, output_path, attempts, dataset_root)
                runtime = time.time() - start
                log_scheduler_event(
                    job.chunk_id,
                    worker,
                    "success",
                    {
                        "attempt": attempts,
                        "output": str(output_path),
                        "runner": "stub",
                    },
                    runtime_s=runtime,
                    finished_at=now_iso(),
                    telemetry_path=telemetry_path,
                )
                return JobResult(
                    output_path=output_path,
                    attempts=attempts,
                    retries=max(attempts - 1, 0),
                )

            gpu_before = query_gpu_metrics(worker.index) if worker else None
            result = subprocess.run(
                cmd,
                env=env,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                check=True,
            )
            gpu_after = query_gpu_metrics(worker.index) if worker else None

            if use_hawkears:
                labels_path = hawkears_output_dir / LABELS_FILENAME
                payload = _parse_hawkears_labels(
                    labels_path,
                    job,
                    dataset_root=dataset_root,
                    runner=runner_label,
                    model_version=model_version,
                )
                payload["hawkears_output"] = str(hawkears_output_dir)
                output_path.write_text(json.dumps(payload))
            elif runner_cmd:
                payload = {
                    "chunk_id": job.chunk_id,
                    "recording_id": job.recording_id,
                    "source_path": str(job.chunk_path),
                    "status": "ok",
                    "detections": [],
                    "chunk": _chunk_metadata(job),
                    "runner": runner_label,
                }
                if dataset_root:
                    payload["dataset_root"] = str(dataset_root)
                if model_version:
                    payload["model_version"] = model_version
                output_path.write_text(json.dumps(payload))
            details = {
                "attempt": attempts,
                "output": str(output_path),
                "runner": runner_label,
                "stdout": (result.stdout or "")[-500:],
            }
            metrics_summary = {
                "before": _metrics_payload(gpu_before),
                "after": _metrics_payload(gpu_after),
            }
            if metrics_summary["before"] or metrics_summary["after"]:
                details["gpu_metrics"] = metrics_summary
            runtime = time.time() - start
            log_scheduler_event(
                job.chunk_id,
                worker,
                "success",
                details,
                runtime_s=runtime,
                finished_at=now_iso(),
                telemetry_path=telemetry_path,
            )
            return JobResult(
                output_path=output_path,
                attempts=attempts,
                retries=max(attempts - 1, 0),
            )
        except subprocess.CalledProcessError as exc:
            runtime = time.time() - start
            gpu_after = query_gpu_metrics(worker.index) if worker else None
            metrics_summary = {
                "before": _metrics_payload(gpu_before),
                "after": _metrics_payload(gpu_after),
            }
            log_scheduler_event(
                job.chunk_id,
                worker,
                "failure",
                {
                    "attempt": attempts,
                    "returncode": exc.returncode,
                    "stderr": (exc.stderr or "")[-500:],
                    "gpu_metrics": metrics_summary,
                },
                runtime_s=runtime,
                finished_at=now_iso(),
                telemetry_path=telemetry_path,
            )
            if attempts > max_retries:
                raise JobExecutionError(job.chunk_id, attempts, exc) from exc
            time.sleep(min(2**attempts, 5))
