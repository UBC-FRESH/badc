# End-to-End Pipeline Plan

## Overview
Stages:
1. Chunk: split large WAV/FLAC into GPU-safe windows; store metadata (start/end ms, hash, chunk file path).
2. Infer: run HawkEars on each chunk, emit raw detections (per-call time stamps, confidence).
3. Aggregate: merge detections, annotate with site metadata, and store in tabular backend (Parquet/DuckDB).
4. Report: generate CSV summaries, charts, and thesis-ready tables/figures.

## Chunk stage
- Inputs: DataLad-tracked audio, chunk-size hint from probe utility, optional overlap (e.g., 2 s) to avoid boundary misses.
- Temp layout: `artifacts/chunk/<recording>/<chunk_id>.wav` plus `chunk_manifest.csv`.
- CLI commands: `badc chunk probe`, `badc chunk split`, `badc chunk run` (future, orchestrates splitting + manifest writing).
- Telemetry: chunk durations, GPU assignments, disk usage.
- Manifest schema (CSV + JSON metadata):
  - `recording_id` (str)
  - `chunk_id` (str; `<recording>_<start_ms>_<end_ms>`)
  - `source_path` (relative path)
  - `start_ms` / `end_ms`
  - `overlap_ms`
  - `sha256` of chunk file
  - `notes` (optional)

## Infer stage
- Inputs: chunk manifest.
- Execution: schedule HawkEars jobs; capture stdout/stderr, GPU telemetry, and exit codes.
- Parallelism: auto-detect GPU count/type (NVML or `nvidia-smi`) and spin up one worker per GPU,
  respecting `CUDA_VISIBLE_DEVICES` on Sockeye; allow CLI overrides.
- Configuration surface (also documented in `docs/howto/infer-local.rst`):

  +-------------------------+-------------------------------+--------------------------------------------------+
  | Flag                    | Default                       | Purpose                                          |
  +=========================+===============================+==================================================+
  | ``--use-hawkears``      | ``False``                     | Switch from stub runner to vendor/HawkEars       |
  |                         |                               | ``analyze.py``.                                  |
  +-------------------------+-------------------------------+--------------------------------------------------+
  | ``--max-gpus``          | Auto-detect all GPUs          | Cap worker count when GPU inventory exceeds need.|
  +-------------------------+-------------------------------+--------------------------------------------------+
  | ``--cpu-workers``       | ``1``                         | Worker count when no GPUs are available.         |
  +-------------------------+-------------------------------+--------------------------------------------------+
  | ``--hawkears-arg``      | ``[]``                        | Extra CLI args forwarded to HawkEars.            |
  +-------------------------+-------------------------------+--------------------------------------------------+
  | ``--runner-cmd``        | ``None``                      | Custom command (mutually exclusive with          |
  |                         |                               | ``--use-hawkears``).                             |
  +-------------------------+-------------------------------+--------------------------------------------------+
  | ``--output-dir``        | ``artifacts/infer``           | Output root (auto-relocated inside DataLad       |
  |                         |                               | datasets).                                       |
  +-------------------------+-------------------------------+--------------------------------------------------+
  | ``--telemetry-log``     | Auto-generated (`data/telemetry/infer/...` or dataset-relative) | Control telemetry path.        |
  +-------------------------+-------------------------------+--------------------------------------------------+
  | ``--max-retries``       | ``2``                         | Retry budget per chunk.                          |
  +-------------------------+-------------------------------+--------------------------------------------------+
  | ``--print-datalad-run`` | ``False``                     | Print a ``datalad run`` command instead of       |
  |                         |                               | executing inference.                             |
  +-------------------------+-------------------------------+--------------------------------------------------+

- Output schema: JSON + Parquet with fields (chunk metadata, label, confidence, timestamps,
  `runner`, `model_version`, chunk SHA, dataset root). Aggregation helpers live in
  `badc.aggregate` and tests mirror the canonical structure.
- Telemetry: JSONL logs (one per run) with per-chunk/per-GPU metrics; analyzed via
  ``badc infer monitor`` / ``badc telemetry``.
- Config template: ``configs/hawkears-local.toml`` captures the shared runner/HawkEars settings so
  helper scripts can materialize ``badc infer run`` commands without repeating CLI flags.

## Aggregate stage
- Combine chunk-level detections, dedupe overlapping windows, and normalize timestamps relative to original recording.
- Store in DuckDB + export CSV for downstream stats; optionally push to DataLad dataset for provenance.
- CLI: `badc aggregate detections.parquet --out aggregated.db`.
- DuckDB schema sketch:
  - Table `detections_raw` (mirrors detection schema).
  - Table `detections_normalized` (timestamps corrected for chunk offsets).
  - Table `processing_log` (chunk status, runtimes, GPU info).
- Aggregation outputs:
  - Species/site summaries (CSV, Markdown).
  - QC metrics (chunks attempted, failures, runtime distributions).

## Report stage
- Produce summary tables (per species/per site), quality-control metrics (chunks processed, failures), and GPU utilization charts.
- CLI: `badc report summary --input aggregated.db`.
- Reporting artifacts:
  - Markdown/CSV for thesis tables.
  - Optional Plotly/Matplotlib PNGs showing detection counts vs. time.

## Implementation next steps
1. Finalize manifest format (CSV + JSON metadata) and chunk ID naming scheme.
2. Define detection schema (columns, types, units) informed by HawkEars output + reference paper (`reference/`).
3. Sketch DuckDB schema + API wrappers.
4. Hook CLI commands to orchestrator classes so automation can run locally or on Sockeye.
