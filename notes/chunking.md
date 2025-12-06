# Chunking & Chunk-Size Probe Plan

Goal: determine the maximum audio duration HawkEars can process per GPU without CUDA OOM errors,
then design automation that splits ~60 TB of recordings accordingly.

## Inputs
- Sample WAVs under `data/audio/` (1 min, 7 min, 60 min placeholders; more to follow).
  - `data/audio/GNWT-290_20230331_235938.wav`: ~60-minute recording (likely no grouse activity;
    useful for “no hit” validation runs).
  - `data/audio/XXXX-000_20251001_093000.wav`: ~7-minute clip with suspected ruffed grouse
    drumming (need to verify HawkEars actually detects these calls).
- HawkEars fork (`vendor/HawkEars`).
- GPU inventory:
  - Dev server: 2 × NVIDIA Quadro RTX 4000 (8 GB VRAM each).
  - Sockeye GPU nodes: up to 4 × GPUs per job (model varies; expect ≥16 GB VRAM).

## Desired outputs
1. Automated probe utility that:
   - Accepts a target file and an initial chunk duration.
   - Iteratively increases/decreases the window until HawkEars runs out of memory, logging the
     largest safe chunk.
   - Stores telemetry (GPU usage + chunk metadata) in `data/telemetry/chunk_probe/*.jsonl`.
2. Configurable chunking engine that:
   - Reads audio files (WAV/FLAC) and slices them into overlapping windows.
   - Names temp files deterministically (e.g., `<recording>_chunk_<start_ms>_<end_ms>.wav`).
   - Supports streaming to avoid writing intermediate files where possible.
3. CLI commands integrating the probe:
   - `badc chunk probe --file data/audio/foo.wav --max-duration 900 --gpu 0`
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

## Open questions
- Does HawkEars expose a Python API we can call directly, or do we shell out to its CLI?
- How do we incorporate overlapping windows (to avoid clipping detections near boundaries)?
- Should chunking happen lazily (streaming) or via temp files on SSD for better I/O throughput?
- What metadata do we need to persist for reproducibility (e.g., audio hash, GPU model, driver
  version)?
