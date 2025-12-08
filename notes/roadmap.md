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
- [ ] Define configuration schema for HawkEars runs (GPU/CPU toggles, batch/chunk settings,
      telemetry output locations) and document defaults.
- [ ] Prototype chunk-size discovery routine that probes for the largest CUDA-safe window on the
      dev server (Quadro RTX 4000s) and records findings in `notes/chunking.md`.
- [x] Build local temp-dir workflow: chunk staging, HawkEars inference, raw-output collection,
      JSON/CSV/Parquet parsing into a canonical events table. *(Verified 2025-12-08 on the bogus
      dataset: `badc infer run --use-hawkears` now produces manifest-driven chunks, HawkEars JSON,
      telemetry, and canonical CSV/Parquet artifacts under `data/datalad/bogus/artifacts/`.)*
- [ ] Provide smoke tests using the short audio sample plus CLI how-to docs.
- [ ] Implement GPU utilization monitoring/profiling (see `notes/gpu-monitoring.md`) so we can
      verify HawkEars saturates available CUDA cores on 2-GPU dev boxes and 4-GPU Sockeye nodes.

## Phase 2 — Data Automation & Analysis Layer
- [ ] Implement chunker orchestrator that walks large datasets, schedules HawkEars jobs, and tracks
      provenance for each output segment.
- [ ] Implement HawkEars inference scheduler per `notes/inference-plan.md` (manifest loader, GPU
      worker pool, telemetry, output persistence). *(Manifest loader + telemetry exist; the bogus
      dataset run exercised the GPU worker path with per-chunk utilization snapshots. Still need
      multi-process/HPC orchestration and configurable chunk sizing per host.)*
- [ ] Parse HawkEars JSON outputs into canonical detection schema and wire DuckDB aggregation
      (`notes/pipeline-plan.md`). *(Real HawkEars detections from the bogus dataset now serialize to
      canonical CSV/Parquet with model metadata + chunk hashes; next milestone is packaging DuckDB
      helpers/notebooks for Phase 2 analytics.)*
- [ ] Wire `badc data connect` to the bogus dataset submodule once published (`notes/bogus-datalad.md`).
- [ ] Build `badc chunk run` per `notes/chunk-files.md` (real chunk WAV writer + manifest linking).
- [ ] Design the aggregated “bird call events” datastore (likely DuckDB/Parquet) and expose query
      helpers for down-stream stats/figures. *(Canonical Parquet export +
      ``badc report summary`` now provide grouped counts/avg confidence; next up is richer
      aggregation notebooks.)*
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
1. **Telemetry monitor uplift** — feed the recorded per-GPU utilization/memory snapshots into
   `badc infer monitor` so long HawkEars runs surface live GPU usage trends (`notes/gpu-monitoring.md`).
2. **Canonical detection serialization** — finish the HawkEars parsing story by locking down the
   manifest-aware Parquet schema (chunk offsets, model metadata) and exposing helpers that pipe the
   outputs straight into DuckDB for Phase 2 aggregation tooling (`notes/pipeline-plan.md`).
3. **DuckDB aggregation helper** — automate Parquet consumption via a `badc aggregate parquet`/report
   helper or notebook that loads the bogus detections and produces summary tables/plots for Erin to
   review (`docs/howto/aggregate-results.rst` + notebook gallery).
4. **Chunk-size probe utility** — script the automated GPU-memory probing routine, log results for
   the 1 min / 7 min / 60 min samples, and store telemetry in `notes/chunking.md`.
5. **Data management plan** — flesh out `notes/datalad-plan.md`, scaffold the bogus dataset, and
   draft the Chinook special-remote workflow ahead of the 60 TB ingest.

## Backlog & Ideas
- GPU-aware scheduling heuristics that prioritise short chunks when VRAM is scarce.
- Automated quality-control notebooks: confirm signal-to-noise, detect microphone glitches, flag
  low-confidence detections.
- Integration with UBC ARC telemetry dashboards for long-running Sockeye jobs.
- Optional web UI for browsing aggregated call events (post-MVP).
- Comparative benchmarking versus other open-source detectors to provide context in the thesis.
