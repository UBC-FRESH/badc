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
- Output schema: JSONL/Parquet with fields (chunk_id, species_label, confidence, timestamp, model_version).
- Detection schema (Parquet):
  - `recording_id`
  - `chunk_id`
  - `call_timestamp_ms`
  - `species_label`
  - `confidence`
  - `probabilities` (JSON/dict)
  - `model_version`
  - `runtime_s`
- CLI: `badc infer run` (per manifest), `badc infer monitor` (watch GPU usage using NVML hooks).

## Aggregate stage
- Combine chunk-level detections, dedupe overlapping windows, and normalize timestamps relative to original recording.
- Store in DuckDB + export CSV for downstream stats; optionally push to DataLad dataset for provenance.
- CLI: `badc aggregate detections.parquet --out aggregated.db`.

## Report stage
- Produce summary tables (per species/per site), quality-control metrics (chunks processed, failures), and GPU utilization charts.
- CLI: `badc report summary --input aggregated.db`.

## Implementation next steps
1. Finalize manifest format (CSV + JSON metadata) and chunk ID naming scheme.
2. Define detection schema (columns, types, units) informed by HawkEars output + reference paper (`reference/`).
3. Sketch DuckDB schema + API wrappers.
4. Hook CLI commands to orchestrator classes so automation can run locally or on Sockeye.
