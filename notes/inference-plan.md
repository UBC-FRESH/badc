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

## Sockeye script + bundle automation — 2025-12-10
- With the bogus dataset re-chunked (five GNWT recordings) and telemetry summaries recorded under
  `data/datalad/bogus/artifacts/telemetry/infer/*.jsonl.summary.json`, ran:

  ```
  badc infer orchestrate data/datalad/bogus \
      --manifest-dir manifests \
      --include-existing \
      --sockeye-script artifacts/sockeye/bogus_bundle.sh \
      --sockeye-job-name badc-bogus \
      --sockeye-account pi-fresh \
      --sockeye-partition gpu \
      --sockeye-gres gpu:4 \
      --sockeye-time 06:00:00 \
      --sockeye-cpus-per-task 8 \
      --sockeye-mem 64G \
      --sockeye-resume-completed \
      --sockeye-bundle \
      --sockeye-bundle-aggregate-dir artifacts/aggregate \
      --sockeye-bundle-bucket-minutes 30
  ```

- The emitted script lives at `artifacts/sockeye/bogus_bundle.sh` (ignored by Git); it now includes:

  * ``RESUMES=(...)`` pointing at each telemetry summary so reruns automatically append
    ``--resume-summary`` when the JSON exists.
  * ``AGG_CMD`` + ``BUNDLE_CMD`` blocks that run ``badc infer aggregate`` and
    ``badc report bundle`` right after inference so every Sockeye array task leaves behind the
    quicklook/parquet/DuckDB bundle under ``artifacts/aggregate``.
- Reminder for operators: ensure `cd "$DATASET"` appears before invoking any `datalad` commands so
  the annex-backed manifest paths resolve inside the job allocation (`datalad get` will populate the
  symlink targets automatically).

## Chunk orchestrator integration (2025-12-10)
- `badc infer orchestrate` now inspects `<dataset>/artifacts/chunks/<recording>/.chunk_status.json`
  before producing the plan (configurable via `--chunks-dir`). The planner refuses to run unless each
  recording reports `status="completed"` (override with `--allow-partial-chunks` when you
  intentionally want to proceed). This keeps Sockeye runs from burning GPU hours on manifests that
  were only partially chunked.
- Generated Sockeye scripts include a chunk-status sanity check before invoking HawkEars; array tasks
  exit early with a descriptive error if the status file is missing or still marked `failed` /
  `in_progress`.

## Phase 2 scheduler polish — detailed TODOs
1. **Enrich scheduler summaries**
   - Extend `_write_scheduler_summary` to include retry/backoff metadata per worker and per chunk
     (attempt count, final delay, last error message). Surfacing this data lets resume workflows flag
     flaky slices before Sockeye reruns them.
   - Tests: ensure the JSON contains the new fields and that ``badc infer run --resume-summary`` can
     consume them without breaking existing behavior.
2. **Persistent log/report hooks**
   - Have ``badc infer run`` emit an optional CSV (e.g., `artifacts/telemetry/infer/<manifest>_workers.csv`)
     summarising retries/failures so HPC operators can archive a single file alongside SLURM logs.
   - Update the CLI so it warns when a run finishes but several chunks exceeded the retry budget.
   - Document the workflow in this note + `docs/howto/infer-local.rst`.
3. **Sockeye integration**
   - Allow `badc infer orchestrate --sockeye-script` to accept a `--sockeye-log-dir` that redirects
     telemetry/summary paths into a SLURM-friendly directory (e.g., `$SCRATCH/logs/...`), ensuring
     multi-node submissions don't write to a read-only DataLad tree.
   - Inject a short resume report into the emitted script (log when a summary is missing / when
     bundle commands run) so cluster operators can eyeball array output quickly.
   - Expand `docs/hpc/sockeye.rst` with a “resume + bundle logging” subsection referencing the new
     flags/script snippets.

## Scheduler summary enrichment — 2025-12-10
- `_write_scheduler_summary` now writes `*.workers.csv` alongside the JSON so HPC operators can archive
  a single file containing per-worker success/failure/retry counts. The CLI prints the CSV path after
  each run.
- `_run_scheduler` records `last_backoff_s` + `last_error` for every chunk (success or failure). The
  CLI warns when any chunk retried or failed, listing the top offenders with their final error string.
- `JobExecutionError` carries the last backoff/error metadata, and the summary JSON now includes those
  fields so resume tooling can triage flaky chunks without scraping telemetry logs.

## Sockeye log-dir support — 2025-12-10
- Added ``--sockeye-log-dir`` to `badc infer orchestrate --sockeye-script` so generated SLURM arrays
  can redirect telemetry/summary logs into `$SCRATCH` (or any writable directory) before running
  inference. The script now emits `LOG_DIR=...`, creates the directory, and points both the
  ``TELEMETRY`` and ``RESUMES`` arrays at `${LOG_DIR}/<recording>.jsonl`.
- Generated scripts now echo whether the resume summary exists for each manifest and print the bundle
  artifact paths (summary/parquet/duckdb) after reporting completes so SLURM logs capture all relevant
  metadata.
- `docs/hpc/sockeye.rst` details the new flag/logging behavior and reminds operators to archive the log directory
  alongside SLURM output for multi-node runs.
