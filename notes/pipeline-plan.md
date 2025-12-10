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
- Orchestrator: `badc chunk orchestrate` scans a dataset's `audio/` tree, skips recordings that
  already have manifests (unless `--include-existing`), prints a Rich summary, emits ready-to-run
  `datalad run` commands via `badc.chunk_orchestrator.render_datalad_run`, persists CSV/JSON plan
  files, and can apply the plan immediately (`--apply`) by invoking `badc chunk run` per recording.
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
| ``--cpu-workers``       | ``0``                         | Additional CPU worker threads (at least one CPU worker is added automatically when GPUs are absent). |
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
- CLI entry points:
  - `badc infer aggregate <infer_dir> --manifest <manifest.csv> --output <summary.csv> --parquet <detections.parquet>`
  - `badc report summary/quicklook/parquet/duckdb` for Phase 2-ready CSV/JSON/DuckDB bundles.
  - `badc report bundle --parquet <recording>.parquet` to run quicklook + parquet + DuckDB helpers in one pass (used by `badc infer orchestrate --bundle` and `--sockeye-bundle`).
- Canonical artifacts per recording (all under `artifacts/aggregate/<RUN_ID>*` inside the dataset):
  - `<RUN_ID>_summary.csv` — detection-level CSV (one row per DetectionRecord).
  - `<RUN_ID>.parquet` — canonical schema consumed by DuckDB.
  - `<RUN_ID>_quicklook/{labels,chunks,recordings}.csv` — lightweight summaries for notebooks.
  - `<RUN_ID>_parquet_report/{labels.csv,recordings.csv,timeline.csv,summary.json}` — outputs from `badc report parquet`.
  - `<RUN_ID>.duckdb` plus `<RUN_ID>_duckdb_exports/{label_summary.csv,recording_summary.csv,timeline.csv}` — DuckDB datastore + CSV exports from `badc report duckdb`.
- DuckDB bundle schema (materialized inside `badc report duckdb`):
  - Table `detections` (one row per detection/status, mirrors `badc.aggregate.DetectionRecord`).
  - View `label_summary(recording_id, label, label_name, detections, avg_confidence)`.
  - View `recording_summary(recording_id, detections, avg_confidence)`.
  - View `timeline_summary(recording_id, bucket_start_ms, bucket_end_ms, detections, avg_confidence)`.
- Notebook coverage: `docs/notebooks/aggregate_analysis.ipynb` now targets real GNWT runs, shows how to
  read the per-recording Parquet/DuckDB bundles, and renders both label bar charts and timeline plots sourced
  from `label_summary` / `timeline_summary`.
- Remaining checklist to consider this Phase 2 task complete:
  1. **Python API helper** — add a thin module (e.g., `badc.aggregate.duckdb_helpers`) that opens a bundle `.duckdb` file,
     returns pandas DataFrames for the three views, and documents column types/units.
  2. **Regression tests** — add fixtures covering `badc report bundle` output structure (ensure schema version + required columns)
     and unit tests for the helper so we catch schema regressions without running HawkEars.
  3. **Docs** — extend `docs/cli/report.rst` (schema table) and link from `docs/howto/aggregate-results.rst`
     plus `docs/notebooks/aggregate_analysis.ipynb` so reviewers see an end-to-end workflow (CLI → datastore → notebook plots).
  4. **Roadmap closure** — once helper/tests/docs land, mark the Phase 2 aggregation bullet `[x]` in `notes/roadmap.md`
     and summarize the closure in `CHANGE_LOG.md`.

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
