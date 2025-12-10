# HawkEars Inference Integration Plan

## Goals
- Consume chunk manifests and run HawkEars on each chunk, in parallel across GPUs.
- Capture telemetry (GPU usage, runtime, exit codes) and store detection outputs (JSONL/Parquet).
- Provide CLI + Python interfaces for scheduling runs locally or on Sockeye.

## Architecture
1. **Manifest loader**: read chunk manifest CSV and produce job specs (chunk path, recording id,
   chunk id, metadata).
2. **GPU scheduler**:
   - Detect GPUs via `badc.gpu.detect_gpus()`.
   - Allow CLI overrides (`--max-gpus`, `--workers`).
   - For each GPU, run a worker process that pops chunk jobs and invokes HawkEars.
     *(Implemented via thread-per-worker; `--cpu-workers` can now supplement GPU workers or take over
     when none exist, and worker labels surface in the CLI summary so hotspots are easy to spot.
     Future work: true async queue feeding HPC jobs).*
3. **HawkEars runner**:
   - Shell out to `vendor/HawkEars` CLI (initially) with arguments for input WAV, config, and
     optional GPU index (via env var or CLI flag).
   - Capture stdout/stderr, parse output to JSONL (chunk-level detections) and stash outputs back
     into the originating DataLad dataset (`<dataset>/artifacts/infer/...`) so `datalad save` can run
     immediately.
   - Return status + path to raw output.
   - Retry policy: up to 2 automatic retries per chunk with exponential backoff; mark failures in
     telemetry and manifest.
4. **Telemetry**:
   - Log start/end timestamps, GPU index/name, VRAM usage, runtime, exit code.
   - Persist to `data/telemetry/infer/<manifest_id>.jsonl` and summarise per worker.
   - Record HawkEars command, chunk id, retry counter, and failure reason for post-mortems.
   - `badc infer run` prints a final worker summary (GPU/CPU label, successes, failures, retry
     counts) using the stats gathered during scheduling so flare-ups are visible without opening the
     telemetry log, ``badc infer monitor`` surfaces live retry/failed-attempt totals plus a retry
     sparkline, and every run writes a ``*.summary.json`` file (next to the telemetry log) that maps
     chunk IDs to success/failure metadata for resumable workflows.
5. **Output storage**:
   - Store raw HawkEars CSV/JSON outputs in `artifacts/infer/<recording>/chunk_id.*`.
   - Convert to canonical detection schema (Parquet) for aggregation.
   - Surface `--print-datalad-run` helper so the entire transform can be wrapped in `datalad run`.

## CLI plan
- `badc infer run --manifest chunk_manifest.csv --output artifacts/infer --max-gpus 2 --worker-per-gpu 1`.
- `badc infer monitor` to tail telemetry / summarise in real time.
- Provide dry-run flag to simulate scheduling without invoking HawkEars. *(Implemented via stub
  mode; passing `--use-hawkears` now shells out to `vendor/HawkEars/analyze.py` and parses the
  generated `HawkEars_labels.csv` into the JSON payload used by `badc infer aggregate`.)*
- `badc infer orchestrate` scans manifests or chunk-plan files, prints an inference plan, emits
  ready-to-run `datalad run` commands, persists CSV/JSON for HPC submission, and now executes the full
  run list via `--apply` (auto-wrapping each recording in `datalad run` when available; disable with
  `--no-record-datalad`). `--sockeye-script` writes a SLURM array script (one manifest per array
  index) so Sockeye submissions no longer require hand-editing sbatch snippets.

## Testing strategy
- Mock HawkEars runner (fake script) to ensure scheduler distributes work across GPUs.
- Property tests verifying each chunk is processed exactly once.
- Telemetry tests checking JSONL entries include GPU metadata and runtimes.

## Resume workflow validation — 2025-12-10
- Ran `badc infer run data/datalad/bogus/manifests/XXXX-000_20251001_093000.csv --cpu-workers 1`
  (stub runner) to generate a fresh telemetry pair at
  `data/datalad/bogus/artifacts/telemetry/XXXX-000_20251001_093000_20251210T025842Z.jsonl`
  + `.summary.json` (15 chunks completed across gpu-0/gpu-1/cpu-0).
- Re-ran the same command with
  `--resume-summary data/datalad/bogus/artifacts/telemetry/XXXX-000_20251001_093000_20251210T025842Z.jsonl.summary.json`
  and confirmed the CLI skipped all 15 chunks and printed the orphan/skip diagnostics.
- Exercised the orchestrator path with
  `badc infer orchestrate data/datalad/bogus --manifest-dir manifests --include-existing --apply --stub-runner --no-record-datalad`
  to create the deterministic telemetry log
  `data/datalad/bogus/artifacts/telemetry/infer/XXXX-000_20251001_093000.jsonl` (plus summary).
  A follow-up invocation adding `--resume-completed` reused that summary automatically and skipped
  every chunk, validating the dataset-scale resume flag without requiring manual `--resume-summary`
  plumbing per manifest.
