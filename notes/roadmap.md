# Bird Acoustic Data Cruncher Roadmap

This roadmap coordinates the build-out of the Bird Acoustic Data Cruncher (BADC) platform so it can
process ~60 TB of bird audio via a forked HawkEars pipeline, scale onto UBC ARC resources, and stay
aligned with Erin Tattersall’s PhD deliverables. Treat this document as the top-level plan; detailed
execution notes live alongside task-specific files under `notes/`.

## Phase 0 — Repository Foundations (in progress)
- [x] Capture problem statement and constraints in `notes/erin-notes.md`.
- [x] Add coding-agent contract (`AGENTS.md`, `CONTRIBUTING.md`) and changelog scaffolding.
- [x] Document DataLad repo strategy (bogus vs. production datasets + CLI expectations) in
      `notes/datalad-plan.md`.
- [x] Establish minimal Python package layout (`pyproject.toml`, `src/badc`, Typer CLI entry).
- [ ] Stand up CI stubs (lint/test placeholders) and pre-commit config.
- [ ] Mirror FHOPS doc stack: Sphinx skeleton + GitHub Pages deployment workflow.

## Phase 1 — HawkEars Integration & Local Workflow
- [ ] Embed the forked HawkEars repo as a git submodule plus wrapper package providing Typer CLI
      + Python API bindings.
- [ ] Define configuration schema for HawkEars runs (GPU/CPU toggles, batch/chunk settings,
      telemetry output locations) and document defaults.
- [ ] Prototype chunk-size discovery routine that probes for the largest CUDA-safe window on the
      dev server (Quadro RTX 4000s) and records findings in `notes/chunking.md`.
- [ ] Build local temp-dir workflow: chunk staging, HawkEars inference, raw-output collection,
      JSON/CSV/Parquet parsing into a canonical events table.
- [ ] Provide smoke tests using the short audio sample plus CLI how-to docs.

## Phase 2 — Data Automation & Analysis Layer
- [ ] Implement chunker orchestrator that walks large datasets, schedules HawkEars jobs, and tracks
      provenance for each output segment.
- [ ] Design the aggregated “bird call events” datastore (likely DuckDB/Parquet) and expose query
      helpers for down-stream stats/figures.
- [ ] Wire Typer CLI commands for end-to-end runs (`badc chunk`, `badc infer`, `badc aggregate`,
      `badc report`).
- [ ] Add CLI plumbing for DataLad attachments (`badc data connect`, `badc data disconnect`,
      `badc data status`) so deployments can swap between bogus/test and production datasets at
      runtime.
- [ ] Author Python API wrappers so notebooks and downstream tooling can reuse the workflow.
- [ ] Extend docs with pipeline diagrams, config examples, and troubleshooting sections.

## Phase 3 — HPC & Containerisation
- [ ] Package the HawkEars runner + chunker into an Apptainer definition suitable for Sockeye GPU
      nodes; script build/push to Sylabs or Chinook object storage.
- [ ] Automate Datalad integration so large audio corpora sync against Chinook S3 while metadata
      stays in GitHub.
- [ ] Stand up the public bogus DataLad dataset (GitHub-hosted) and add it as a subdataset for
      smoke tests (`notes/datalad-plan.md`).
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
1. **CI + automation scaffold** — add `.pre-commit-config.yaml` plus GitHub Actions (or
   alternative) pipelines that run ruff, pytest, and Sphinx builds on every push/PR.
2. **HawkEars submodule onboarding** — add the fork as a submodule, document how to sync it, and
   draft the wrapper API that normalises configs/logging.
3. **Chunk-size probe utility** — script the automated GPU-memory probing routine, log results for
   the 1 min / 7 min / 60 min samples, and store telemetry in `notes/chunking.md`.
4. **Data pipeline sketch** — outline the chunking → inference → aggregation temp-dir structure and
   define the canonical events schema before coding.
5. **Data management plan** — flesh out `notes/datalad-plan.md`, scaffold the bogus dataset, and
   draft the Chinook special-remote workflow ahead of the 60 TB ingest.

## Backlog & Ideas
- GPU-aware scheduling heuristics that prioritise short chunks when VRAM is scarce.
- Automated quality-control notebooks: confirm signal-to-noise, detect microphone glitches, flag
  low-confidence detections.
- Integration with UBC ARC telemetry dashboards for long-running Sockeye jobs.
- Optional web UI for browsing aggregated call events (post-MVP).
- Comparative benchmarking versus other open-source detectors to provide context in the thesis.
