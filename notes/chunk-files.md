# Chunk File Creation Plan

Goal: implement `badc chunk run` that reads source audio, produces chunk WAV files with optional overlap,
and writes a manifest referencing the chunk file paths + hashes.

## Requirements
- Support WAV inputs initially; keep hooks for future FLAC/MP3 decoding via ffmpeg or soundfile.
- Accept options: `--chunk-duration`, `--overlap`, `--output-dir` (default `artifacts/chunks/<recording>`),
  `--manifest`. Overlap applied symmetrically (previous chunk end overlaps next chunk start).
- Ensure filenames are stable: `<recording>_chunk_<start_ms>_<end_ms>.wav`.
- Compute SHA256 hash over each chunk file and store in manifest.
- Record chunk start/end timestamps, overlap_ms, hash, chunk path (relative) in manifest.
- Auto-detect DataLad dataset roots (``.datalad``) so default chunk + manifest paths land inside
  the dataset (``<dataset>/artifacts/chunks/<recording>`` and ``<dataset>/manifests/<recording>.csv``);
  outside datasets, place outputs alongside the source audio.

## Implementation sketch
1. Use Python's `wave` module or `soundfile` to read frames streaming.
2. Determine samples per chunk: `chunk_duration_s * sample_rate`. Overlap samples = `overlap_s * sample_rate`.
3. For each chunk window, seek to frame offset and read frames (account for overlap), writing to new WAV via `wave` module.
4. Maintain `ChunkWriter` helper returning chunk metadata entries; pass to manifest writer.
5. Add CLI command `badc chunk run ...` that orchestrates chunk writing + manifest generation (calls `write_manifest`).
6. Ensure temporary directories are created using `pathlib.Path.mkdir(parents=True, exist_ok=True)`.
7. Provide dry-run mode for testing (no actual chunk files; just manifest entries).

## Testing
- Use the tiny `tests/data/minimal.wav` to verify chunk splitting logic and manifest output.
- Add property tests ensuring chunk coverage matches source duration +/- overlap.

## Follow-ups
- Explore ffmpeg-backed splitter for FLAC/MP3.
- Integrate DataLad so chunk artifacts can be tracked or dropped easily.
