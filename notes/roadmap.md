# Bird Acoustic Data Compiler Roadmap

This roadmap coordinates the build-out of the Bird Acoustic Data Compiler (BADC) platform so it can
process ~60 TB of bird audio via a forked HawkEars pipeline, scale onto UBC ARC resources, and stay
aligned with Erin Tattersall’s PhD deliverables. Treat this document as the top-level plan; detailed
execution notes live alongside task-specific files under `notes/`.

## Phase 0 — Repository Foundations (in progress)
- [x] Capture problem statement and constraints in `notes/erin-notes.md`.
- [x] Add coding-agent contract (`AGENTS.md`, `CONTRIBUTING.md`) and changelog scaffolding.
- [x] Document DataLad repo strategy (bogus vs. production datasets + CLI expectations) in
      `notes/datalad-plan.md`.
- [x] Establish minimal Python package layout (`pyproject.toml`, `src/badc`, Typer CLI entry).
- [x] Stand up pre-commit config and CI workflow (ruff/pytest/Sphinx).
- [ ] Mirror FHOPS doc stack: Sphinx skeleton + GitHub Pages deployment workflow.

## Phase 1 — HawkEars Integration & Local Workflow
- [x] Embed the forked HawkEars repo as a git submodule plus wrapper package providing Typer CLI
      + Python API bindings.
- [x] Define configuration schema for HawkEars runs (GPU/CPU toggles, batch/chunk settings,
      telemetry output locations) and document defaults. *(Schema captured via
      `configs/hawkears-local.toml`, the updated `docs/howto/infer-local.rst` section, and the
      `notes/pipeline-plan.md` reference table.)*
- [x] Prototype chunk-size discovery routine that probes for the largest CUDA-safe window on the
      dev server (Quadro RTX 4000s) and records findings in `notes/chunking.md`. *(Binary-search
      probe lives in `badc chunk probe`; validation run on 2025-12-09 (see `notes/chunking.md` +
      telemetry log `XXXX-000_20251001_093000_20251208T215527Z.jsonl`) confirmed the recommended
      durations, so the heuristic is now considered Phase 1-complete.)*
- [x] Build local temp-dir workflow: chunk staging, HawkEars inference, raw-output collection,
      JSON/CSV/Parquet parsing into a canonical events table. *(Verified 2025-12-08 on the bogus
      dataset: `badc infer run --use-hawkears` now produces manifest-driven chunks, HawkEars JSON,
      telemetry, and canonical CSV/Parquet artifacts under `data/datalad/bogus/artifacts/`.)*
- [x] Provide smoke tests using the short audio sample plus CLI how-to docs. *(Unit tests cover the
      CLI plumbing; the gated smoke test now lives at `tests/smoke/test_hawkears_smoke.py` and runs
      when `BADC_RUN_HAWKEARS_SMOKE=1`, as documented in `docs/howto/infer-local.rst`.)*
- [x] Implement GPU utilization monitoring/profiling (see `notes/gpu-monitoring.md`) so we can
      verify HawkEars saturates available CUDA cores on 2-GPU dev boxes and 4-GPU Sockeye nodes.
      *(`badc infer monitor --follow` now renders per-GPU trends (utilization, VRAM, success/failure
      counts) and we captured the baseline telemetry/analysis for the dev Quadro RTX 4000 run in
      `notes/gpu-monitoring.md` on 2025-12-09. Sockeye profiling will piggyback on this flow during
      Phase 2 when multi-GPU jobs land.)*

## Phase 2 — Data Automation & Analysis Layer
- [ ] Implement chunker orchestrator that walks large datasets, schedules HawkEars jobs, and tracks
      provenance for each output segment. *(`badc chunk orchestrate --apply` now invokes `badc chunk run`
      directly and, when `.datalad` + the CLI are available, wraps each plan in `datalad run` by default.
      Future work: parallel execution + error-resume support.)*
- [ ] Implement HawkEars inference scheduler per `notes/inference-plan.md` (manifest loader, GPU
      worker pool, telemetry, output persistence). *(Manifest loader + telemetry exist; Phase 2 now
      includes `badc infer orchestrate` for planning, CSV/JSON plan exports, and `--apply` now runs
      each manifest automatically (wrapping in `datalad run` when available). ``--cpu-workers`` can
      supplement GPUs (with per-worker success/failure tables) so operators immediately see retry
      hotspots. Next steps: integrate with Sockeye arrays + multi-GPU scheduling/priority
      heuristics.)*
- [ ] Parse HawkEars JSON outputs into canonical detection schema and wire DuckDB aggregation
      (`notes/pipeline-plan.md`). *(Real HawkEars detections from the bogus dataset now serialize to
      canonical CSV/Parquet with model metadata + chunk hashes; next milestone is packaging DuckDB
      helpers/notebooks for Phase 2 analytics.)*
- [ ] Wire `badc data connect` to the bogus dataset submodule once published (`notes/bogus-datalad.md`).
- [ ] Build `badc chunk run` per `notes/chunk-files.md` (real chunk WAV writer + manifest linking).
      *(Implemented dataset-aware defaults + manifest hashing; next steps include ffmpeg/FLAC
      support and performance tuning for multi-hour recordings.)*
- [ ] Design the aggregated “bird call events” datastore (likely DuckDB/Parquet) and expose query
      helpers for down-stream stats/figures. *(Canonical Parquet export + ``badc report summary``,
      ``badc report quicklook``, ``badc report parquet``, and the new ``badc report duckdb`` command
      now surface grouped counts, bucketed timelines, CSV/JSON artifacts, and a ready-to-query DuckDB
      database for Erin. Remaining work: richer notebook gallery + DuckDB views for cross-project
      comparisons.)*
- [ ] Wire Typer CLI commands for end-to-end runs (`badc chunk`, `badc infer`, `badc aggregate`,
      `badc report`). *(Scaffolded chunk/infer commands exist; `notes/pipeline-plan.md` now captures
      the full flow.)*
- [x] Add CLI plumbing for DataLad attachments (`badc data connect`, `badc data disconnect`,
      `badc data status`) so deployments can swap between bogus/test and production datasets at
      runtime. *(Implemented via `badc data connect/disconnect/status`, writing to
      `~/.config/badc/data.toml`; still need to wire real datasets/submodules.)*
- [ ] Author Python API wrappers so notebooks and downstream tooling can reuse the workflow.
- [ ] Extend docs with pipeline diagrams, config examples, and troubleshooting sections.

## Phase 3 — HPC & Containerisation
- [ ] Package the HawkEars runner + chunker into an Apptainer definition suitable for Sockeye GPU
      nodes; script build/push to Sylabs or Chinook object storage.
- [ ] Automate Datalad integration so large audio corpora sync against Chinook S3 while metadata
      stays in GitHub.
- [ ] Stand up the public bogus DataLad dataset (GitHub-hosted) and add it as a subdataset for
      smoke tests (`notes/datalad-plan.md`).
- [x] Implement `badc data connect/disconnect` wiring for the bogus dataset once the submodule
      exists (`notes/bogus-datalad.md`). *(Git submodule added at `data/datalad/bogus`; CLI now
      targets this path by default.)*
- [ ] Plan bogus dataset contents and workflow (`notes/bogus-datalad.md`).
- [ ] Stand up the restricted production DataLad dataset backed by Chinook object storage and
      document credential/bootstrap steps.
- [ ] Provide submission templates/scripts for Sockeye job arrays (per-chunk or per-batch) with
      telemetry collection.
- [ ] Stress-test the workflow on multi-hour recordings; capture performance, GPU usage, and
      failure-handling strategies in docs.

## Phase 4 — Documentation, QA, and Release Readiness
- [ ] Complete Sphinx docs (CLI reference, Python API, deployment guide, HPC operations playbook).
- [ ] Establish regression suites (unit tests, CLI smoke tests, long-run job harness) and ensure CI
      badges track them.
- [ ] Draft release checklist covering version bumps, container rebuilds, Datalad tagging, and
      GitHub Pages publication.
- [ ] Prep outreach materials (README story, example notebook, thesis-aligned figures).

## Detailed Next Steps
1. **Quicklook notebook wiring** — *(Completed 2025-12-08: `docs/notebooks/aggregate_analysis.ipynb`
   now loads the quicklook CSV exports and demonstrates pandas plots.)*
2. **Chunk-size probe utility** — script the automated GPU-memory probing routine, log results for
   the 1 min / 7 min / 60 min samples, and store telemetry in `notes/chunking.md`.
3. **Data management plan** — flesh out `notes/datalad-plan.md`, scaffold the bogus dataset, and
   draft the Chinook special-remote workflow ahead of the 60 TB ingest.
4. **HPC orchestration** — extend the inference scheduler with multi-node/Sockeye hooks and document
   the submission templates referenced in `docs/howto/infer-hpc.rst`.
5. **Regression scaffolding** — add smoke tests/notebooks that exercise Parquet exports end-to-end so
   CI can catch schema regressions without running HawkEars.

## Backlog & Ideas
- GPU-aware scheduling heuristics that prioritise short chunks when VRAM is scarce.
- Automated quality-control notebooks: confirm signal-to-noise, detect microphone glitches, flag
  low-confidence detections.
- Integration with UBC ARC telemetry dashboards for long-running Sockeye jobs.
- Optional web UI for browsing aggregated call events (post-MVP).
- Comparative benchmarking versus other open-source detectors to provide context in the thesis.
