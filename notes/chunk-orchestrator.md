# Chunk Orchestrator Notes

Phase 2 requires a reproducible way to walk an entire DataLad dataset, generate chunk manifests, and
queue HawkEars runs without hand-curating per-file commands. The new ``badc chunk orchestrate``
command + helpers in ``badc.chunk_orchestrator`` provide the first slice of that workflow.

## Goals
1. Scan ``<dataset>/audio/`` for recordings that match a glob (default ``*.wav``).
2. Produce a deterministic plan: manifest path, chunk output directory, chunk duration, overlap.
3. Emit ready-to-run ``datalad run`` commands so each recording can be chunked with provenance.
4. Support “print-only” dry runs (no audio touched) so we can discuss plans with Erin before
   writing GBs of intermediate data.

## Current implementation
- ``src/badc/chunk_orchestrator.py`` exposes the plan builder plus helpers to persist per-recording
  status metadata in ``artifacts/chunks/<recording>/.chunk_status.json``.
- ``badc chunk orchestrate`` CLI wraps those helpers:
  - Arguments: dataset root (default ``data/datalad/bogus``), glob, chunk duration, overlap,
    manifest/chunk directories, ``--include-existing`` (skip vs. reprocess), ``--workers``, ``--limit``.
  - Output: Rich table summarising recording, audio path, manifest destination, chunk directory.
  - ``--print-datalad-run`` prints a command like:

    .. code-block::

       datalad run -m "Chunk XXXX" --input audio/XXXX.wav \
         --output artifacts/chunks/XXXX --output manifests/XXXX.csv \
         -- badc chunk run audio/XXXX.wav --chunk-duration 60 \
         --overlap 0 --output-dir artifacts/chunks/XXXX --manifest manifests/XXXX.csv

  - ``--apply`` now records ``status`` (``in_progress``/``completed``/``failed``), timestamps,
    manifest row counts, and error messages in ``.chunk_status.json`` so reruns can resume
    automatically when a previous pass died mid-run. Recordings marked ``completed`` get skipped unless
    ``--include-existing`` is provided.
  - ``--workers`` fans out across recordings when ``datalad run`` is unavailable/disabled; provenance
    recording remains the default when `.datalad` + the CLI exist, with a graceful fallback to
    parallel direct writes via ``--no-record-datalad``.

## Next steps
- Feed the saved plan CSV/JSON into HPC submitters (Sockeye arrays, Chinook batches) so chunk +
  inference orchestration share a single scheduling surface.
- Detect chunk output corruption (e.g., missing WAVs vs. manifest rows) and mark statuses as
  ``failed`` when validation scripts detect discrepancies.
- Explore ffmpeg-based chunking for non-WAV formats and document the performance/VRAM trade-offs.
