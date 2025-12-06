"""HawkEars runner stub with retry logic."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from badc.infer_scheduler import GPUWorker, InferenceJob, log_scheduler_event
from badc.telemetry import now_iso


def _build_command(runner_cmd: str, job: InferenceJob, output_path: Path) -> list[str]:
    base = shlex.split(runner_cmd)
    return base + ["--input", str(job.chunk_path), "--output", str(output_path)]


def _write_stub_output(job: InferenceJob, output_path: Path, attempt: int) -> None:
    output_path.write_text(
        json.dumps({"chunk_id": job.chunk_id, "status": "stub", "attempt": attempt})
    )


def run_job(
    job: InferenceJob,
    worker: GPUWorker | None,
    output_dir: Path,
    runner_cmd: str | None = None,
    max_retries: int = 2,
) -> Path:
    output_dir = output_dir / job.recording_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{job.chunk_id}.json"

    attempts = 0
    while attempts <= max_retries:
        attempts += 1
        start = time.time()
        log_scheduler_event(
            job.chunk_id,
            worker,
            "start",
            {"attempt": attempts},
        )
        try:
            if runner_cmd:
                cmd = _build_command(runner_cmd, job, output_path)
                env = os.environ.copy()
                if worker is not None:
                    env["CUDA_VISIBLE_DEVICES"] = str(worker.index)
                result = subprocess.run(
                    cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                details = {
                    "attempt": attempts,
                    "output": str(output_path),
                    "stdout": (result.stdout or "")[-500:],
                }
            else:
                _write_stub_output(job, output_path, attempts)
                details = {
                    "attempt": attempts,
                    "output": str(output_path),
                    "note": "stub runner",
                }
            runtime = time.time() - start
            log_scheduler_event(
                job.chunk_id,
                worker,
                "success",
                details,
                runtime_s=runtime,
                finished_at=now_iso(),
            )
            return output_path
        except subprocess.CalledProcessError as exc:
            runtime = time.time() - start
            log_scheduler_event(
                job.chunk_id,
                worker,
                "failure",
                {
                    "attempt": attempts,
                    "returncode": exc.returncode,
                    "stderr": (exc.stderr or "")[-500:],
                },
                runtime_s=runtime,
                finished_at=now_iso(),
            )
            if attempts > max_retries:
                raise RuntimeError(f"HawkEars failed for {job.chunk_id}") from exc
            time.sleep(min(2**attempts, 5))
    return output_path
