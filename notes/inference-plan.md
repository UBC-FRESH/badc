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
3. **HawkEars runner**:
   - Shell out to `vendor/HawkEars` CLI (initially) with arguments for input WAV and config.
   - Capture stdout/stderr, parse output to JSONL (chunk-level detections).
   - Return status + path to raw output.
4. **Telemetry**:
   - Log start/end timestamps, GPU index/name, VRAM usage, runtime, exit code.
   - Persist to `data/telemetry/infer/<manifest_id>.jsonl` and summarise per worker.
   - Record HawkEars command, chunk id, retry counter, and failure reason for post-mortems.
5. **Output storage**:
   - Store raw HawkEars CSV/JSON outputs in `artifacts/infer/<recording>/chunk_id.*`.
   - Convert to canonical detection schema (Parquet) for aggregation.

## CLI plan
- `badc infer run --manifest chunk_manifest.csv --output artifacts/infer --max-gpus 2 --worker-per-gpu 1`.
- `badc infer monitor` to tail telemetry / summarise in real time.
- Provide dry-run flag to simulate scheduling without invoking HawkEars.

## Testing strategy
- Mock HawkEars runner (fake script) to ensure scheduler distributes work across GPUs.
- Property tests verifying each chunk is processed exactly once.
- Telemetry tests checking JSONL entries include GPU metadata and runtimes.
