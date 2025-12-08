# Chunking & Chunk-Size Probe Plan

Goal: determine the maximum audio duration HawkEars can process per GPU without CUDA OOM errors,
then design automation that splits ~60 TB of recordings accordingly.

## Inputs
- Sample WAVs under `data/datalad/bogus/audio/` (1 min, 7 min, 60 min placeholders; more to follow).
  - `data/datalad/bogus/audio/GNWT-290_20230331_235938.wav`: ~60-minute recording (likely no grouse activity;
    useful for “no hit” validation runs).
  - `data/datalad/bogus/audio/XXXX-000_20251001_093000.wav`: ~7-minute clip with suspected ruffed grouse
    drumming (need to verify HawkEars actually detects these calls).
- HawkEars fork (`vendor/HawkEars`).
- GPU inventory:
  - Dev server: 2 × NVIDIA Quadro RTX 4000 (8 GB VRAM each).
  - Sockeye GPU nodes: up to 4 × GPUs per job (model varies; expect ≥16 GB VRAM).

## Desired outputs
1. Automated probe utility that:
   - Accepts a target file and an initial chunk duration.
   - Iteratively increases/decreases the window until HawkEars runs out of memory, logging the
     largest safe chunk. *(Prototype in place: `badc chunk probe` estimates chunk sizes via WAV metadata +
     GPU VRAM heuristics, runs a binary search, and writes telemetry to
     `artifacts/telemetry/chunk_probe/*.jsonl`. Next step is validating the heuristic against real
     HawkEars runs so we can compare estimates vs. CUDA success/failure.)*
2. Configurable chunking engine that:
   - Reads audio files (WAV/FLAC) and slices them into overlapping windows.
   - Names temp files deterministically (e.g., `<recording>_chunk_<start_ms>_<end_ms>.wav`).
   - Supports streaming to avoid writing intermediate files where possible.
3. CLI commands integrating the probe:
  - `badc chunk probe --file data/datalad/bogus/audio/foo.wav --max-duration 900 --gpu 0`
   - `badc chunk split --file ... --chunk-duration <sec>`
   - `badc chunk manifest` (future) to emit a manifest CSV ingestible by `badc infer run`.
4. Documentation capturing the empirically determined safe durations per environment.

## Implementation notes
- Use `librosa` or `soundfile` for audio slicing (confirm licensing + performance).
- GPU probe flow:
  1. Start with a conservative duration (e.g., 60 seconds).
  2. Run HawkEars inference in a subprocess (Typer command or direct Python binding) with the
     chunk.
  3. Monitor GPU memory via NVML; if HawkEars crashes with CUDA OOM, reduce duration and retry.
  4. Record results (duration, outcome, GPU stats) in JSONL for later analysis.
- Consider binary search to converge quickly on the maximum safe chunk length.
- Allow per-GPU overrides; chunking may differ between dev server and Sockeye due to hardware.
- Reference: peer-reviewed HawkEars paper stored under `reference/` for grounding detection
  assumptions.
- Consider moving sample audio files into a tiny DataLad dataset (submodule) so the `badc data
  connect` workflow can fetch them cleanly before we scale to 60 TB.
- `badc chunk manifest` now emits placeholder CSVs; follow-ups: compute real SHA256 hashes for each
  chunk, include overlap offsets, and store chunk file locations within the temp directory
  structure defined in `notes/pipeline-plan.md`. SHA256 should cover the actual chunk file contents
  once chunking is implemented, not just the source path.

## Dev server probe runs — 2025-12-09

Performed heuristic probes on the bogus dataset recordings using the new CLI.

| Recording | Duration (s) | Recommended chunk (s) | GPU notes | Telemetry log |
| --- | --- | --- | --- | --- |
| `XXXX-000_20251001_093000.wav` | ~420 | 429.20 | GPU 0 (Quadro RTX 4000) limit 6554 MiB | `artifacts/telemetry/chunk_probe/MD5E-s38112038--1eca4ef56ef14b88f819437a5c12124e_20251208T212629Z.jsonl` |
| `GNWT-290_20230331_235938.wav` | ~3600 | 3591.20 | GPU 0 (Quadro RTX 4000) limit 6554 MiB | `artifacts/telemetry/chunk_probe/MD5E-s634689094--17d5cebd521ca376a362cf27f9f715f3_20251208T212634Z.jsonl` |

Observations:

- Both recordings fit comfortably under the 8 GB Quadro RTX 4000 limit; even a full 60‑minute chunk
  stays under ~3.3 GB according to the heuristic. We will still validate with real HawkEars runs,
  but for development purposes a 7‑minute chunk (420 s) is a safe default.
- Telemetry lives under `artifacts/telemetry/chunk_probe/…` at the repo root (not within the
  DataLad dataset). Copy or reference these logs when preparing chunk-size justification for future
  dev boxes.

## Open questions
- Does HawkEars expose a Python API we can call directly, or do we shell out to its CLI?
- How do we incorporate overlapping windows (to avoid clipping detections near boundaries)?
- Should chunking happen lazily (streaming) or via temp files on SSD for better I/O throughput?
- What metadata do we need to persist for reproducibility (e.g., audio hash, GPU model, driver
  version)?
