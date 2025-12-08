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
- ``src/badc/chunk_orchestrator.py`` exposes ``build_chunk_plan`` + ``render_datalad_run``.
- ``badc chunk orchestrate`` CLI wraps those helpers:
  - Arguments: dataset root (default ``data/datalad/bogus``), glob, chunk duration, overlap,
    manifest/chunk directories, ``--include-existing`` (skip vs. reprocess), ``--limit``.
  - Output: Rich table summarising recording, audio path, manifest destination, chunk directory.
  - ``--print-datalad-run`` prints a command like:

    .. code-block::

       datalad run -m "Chunk XXXX" --input audio/XXXX.wav \
         --output artifacts/chunks/XXXX --output manifests/XXXX.csv \
         -- badc chunk run audio/XXXX.wav --chunk-duration 60 \
         --overlap 0 --output-dir artifacts/chunks/XXXX --manifest manifests/XXXX.csv

## Next steps
- Persist plan metadata (CSV/JSON) so HPC submit scripts can chunk recordings in batches.
- Extend to emit ``badc infer run-config`` scaffolding once chunking completes (closing the loop
  from audio -> manifest -> inference plan).
- Sockeye mode: add template generation for SLURM job arrays (one recording per task).
- Plan persistence (Phase 2 follow-up): once the CSV/JSON plan is saved, we can feed it into HPC
  submit scripts or orchestrate partial re-runs by filtering rows.
