"""HawkEars runner stub with retry logic."""

from __future__ import annotations

import json
import shlex
import subprocess
import time
from pathlib import Path

from badc.infer_scheduler import GPUWorker, InferenceJob, log_scheduler_event


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
        log_scheduler_event(job.chunk_id, worker, "start", {"attempt": attempts})
        start = time.time()
        try:
            if runner_cmd:
                cmd = shlex.split(runner_cmd) + [
                    "--input",
                    str(job.chunk_path),
                    "--output",
                    str(output_path),
                ]
                subprocess.run(cmd, check=True)
            else:
                # Stub output until HawkEars CLI wiring lands.
                output_path.write_text(
                    json.dumps({"chunk_id": job.chunk_id, "status": "stub", "attempt": attempts})
                )
            runtime = time.time() - start
            log_scheduler_event(
                job.chunk_id,
                worker,
                "success",
                {"attempt": attempts, "output": str(output_path)},
                runtime_s=runtime,
            )
            return output_path
        except subprocess.CalledProcessError as exc:
            runtime = time.time() - start
            log_scheduler_event(
                job.chunk_id,
                worker,
                "failure",
                {"attempt": attempts, "error": exc.stderr or str(exc)},
                runtime_s=runtime,
            )
            if attempts > max_retries:
                raise RuntimeError(f"HawkEars failed for {job.chunk_id}") from exc
            time.sleep(min(2**attempts, 5))
    return output_path
