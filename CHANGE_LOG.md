# 2025-12-06 — Sample audio now lives in DataLad
- Removed the raw WAVs from `data/audio/`, added a README pointing users to
  `data/datalad/bogus/audio/`, refreshed docs/notes/tests to reference the submodule paths, and
  made the bogus bootstrap script look for audio in either `data/audio` or the submodule. This keeps
  large binaries out of the main Git repo.
- Commands executed:
  - `rm data/audio/*.wav`
  - `apply_patch data/audio/README.md AGENTS.md data/chunk_manifest_sample.csv`
  - `apply_patch docs/usage.rst notes/bogus-datalad.md notes/chunking.md notes/datalad-plan.md`
  - `apply_patch notes/erin-notes.md scripts/setup_bogus_datalad.sh tests/test_infer_cli.py`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — HawkEars runner integration
- Added `--use-hawkears` flag to `badc infer run`, implemented the HawkEars subprocess call
  (per-chunk `vendor/HawkEars/analyze.py` invocation) with telemetry logging, parsing of
  `HawkEars_labels.csv` into the JSON payload consumed by `badc infer aggregate`, and support for
  pass-through arguments via `--hawkears-arg`. Stub mode remains the default for CI/tests. Added unit
  tests for the CSV parser and documentation on how to use the new flag.
- Commands executed:
  - `apply_patch src/badc/hawkears_runner.py src/badc/cli/main.py README.md docs/usage.rst`
  - `apply_patch notes/inference-plan.md notes/roadmap.md`
  - `apply_patch tests/test_hawkears_runner.py`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Bogus dataset submodule
- Pushed the generated dataset in `tmp/badc-bogus-data` to GitHub (`datalad push --to origin`)
  and added `data/datalad/bogus` as a git submodule pointing at `UBC-FRESH/badc-bogus-data`.
  Updated notes/roadmap to mark the wiring complete.
- Commands executed:
  - `source setup/datalad_config.sh && cd tmp/badc-bogus-data && datalad create-sibling-github --existing=reconfigure`
  - `source setup/datalad_config.sh && cd tmp/badc-bogus-data && datalad push --to origin`
  - `git submodule add https://github.com/UBC-FRESH/badc-bogus-data.git data/datalad/bogus`
  - `apply_patch notes/datalad-plan.md notes/bogus-datalad.md notes/roadmap.md`
  - `apply_patch README.md docs/usage.rst`

# 2025-12-06 — Bogus submodule pending
- Tried to add `UBC-FRESH/badc-bogus-data` as `data/datalad/bogus`, but the GitHub repo currently
  has no commits so git refuses to create the submodule. Restored the placeholder README with
  instructions and documented the blocker in `notes/datalad-plan.md`, `notes/bogus-datalad.md`, and
  the roadmap.
- Commands executed:
  - `git rm data/datalad/bogus/README.md` (rolled back after failure)
  - `apply_patch data/datalad/bogus/README.md notes/datalad-plan.md notes/bogus-datalad.md notes/roadmap.md`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Data CLI connect/disconnect workflow
- Added `src/badc/data.py` plus Typer wiring so `badc data connect/disconnect/status` now clone
  datasets (preferring `datalad` with `git` fallback), record metadata in
  `~/.config/badc/data.toml`, and optionally remove content. Updated README, docs, roadmap, and
  bogus DataLad notes; added CLI regression tests.
- Commands executed:
  - `apply_patch src/badc/data.py src/badc/cli/main.py README.md docs/usage.rst notes/roadmap.md`
  - `apply_patch notes/bogus-datalad.md notes/datalad-plan.md`
  - `apply_patch tests/test_cli.py`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Bogus dataset caveat
- Updated `notes/datalad-plan.md` with the current limitation: if the bootstrap script fails after
  creating the Arbutus bucket, the reuse logic still can’t recover, so manual bucket/UUID deletion
  is required before rerunning.
- Commands executed:
  - `apply_patch notes/datalad-plan.md`

# 2025-12-06 — Bogus dataset bootstrap status
- Documented in `notes/datalad-plan.md` that the bogus dataset bootstrap succeeded (new Arbutus
  bucket + `UBC-FRESH/badc-bogus-data` GitHub repo) so we can focus on wiring `badc data connect`.
- Commands executed:
  - `apply_patch notes/datalad-plan.md`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Bogus DataLad bucket guardrails
- Hardened `scripts/setup_bogus_datalad.sh` to detect existing Arbutus buckets, reuse known
  `git-annex-uuid` values, and optionally reset unreadable/conflicting buckets via
  `S3_RESET_CONFLICTING_BUCKET`. Added `S3_EXISTING_REMOTE_UUID` hint + documented knobs in
  `setup/datalad_config.template.sh` and `notes/datalad-plan.md`. Ignored `tmp/` so local datasets
  don’t show up as untracked files.
- Fixed the special-remote reuse call so we now pass `sameas=<uuid>` (per git-annex docs) instead of
  the invalid `--sameas` flag.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs _build/html -W`
  - `pre-commit run --all-files`

# 2025-12-06 — Bogus DataLad scaffolding
- Updated `data/datalad/bogus/README.md`, README/docs, and notest to document the upcoming `badc data connect` wiring to `UBC-FRESH/badc-bogus-audio`.
- Commands executed:
  - `echo ... > data/datalad/bogus/README.md`
  - `apply_patch README.md docs/usage.rst`

# 2025-12-06 — Datalad bootstrap script
- Added `setup/datalad_config.template.sh` and `scripts/setup_bogus_datalad.sh` to automate dataset
  creation (`datalad create`, audio copy, GitHub remote, and `git annex initremote` to spawn the S3
  bucket). Documentation updated in `notes/datalad-plan.md`.
- 2025-12-06: Script now shells out to `datalad create-sibling-github` so the GitHub repo is
  auto-created (per lab docs) and uses `GITHUB_ORG`/`GITHUB_REPO_NAME` env vars.
- 2025-12-06: Added S3 bucket reuse detection (reads `git-annex-uuid` and passes `--sameas=UUID` to
  `git annex initremote`) so reruns don’t fail if the bucket already exists.

# 2025-12-06 — HawkEars runner + telemetry hooks
- Added `hawkears_runner.py`, wired `badc infer run --manifest` to process chunk jobs (with retries,
  telemetry, and output dir handling), and documented README/docs/tests updates.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Telemetry record timestamp fix
- Simplified telemetry records to log a single timestamp + runtime (no deprecated UTC warning) and
  updated scheduler logging accordingly.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — Bogus DataLad workflow note
- Updated `notes/bogus-datalad.md` + roadmap to capture the upcoming `badc data connect` wiring for
  the bogus dataset (clone, connect, disconnect flow).
- Commands executed:
  - `apply_patch notes/bogus-datalad.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Bogus dataset skeleton
- Created `data/datalad/bogus/README.md` (placeholder) to reserve the submodule mount point for the
  forthcoming bogus DataLad repository.
- Commands executed: `mkdir -p data/datalad/bogus && touch data/datalad/bogus/README.md`

# 2025-12-06 — Data connect/disconnect stubs
- Added CLI stubs for `badc data connect/disconnect` (points to `data/datalad/<name>`), plus README/docs notes ahead of wiring the bogus DataLad repo.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — HawkEars runner subprocess wiring
- `badc infer run` now shells out to the HawkEars CLI (when `--runner-cmd` is provided), sets
  `CUDA_VISIBLE_DEVICES`, captures stdout/stderr, and logs telemetry per attempt; stub mode remains
  for local testing.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — HawkEars CLI integration plan
- Noted in `notes/inference-plan.md` that the runner passes GPU index info to the HawkEars CLI
  along with input/config args.
- Commands executed: `apply_patch notes/inference-plan.md`

# 2025-12-06 — HawkEars inference plan
- Added `notes/inference-plan.md` detailing the manifest loader, GPU scheduler, telemetry, and CLI
  requirements for `badc infer run`; roadmap updated accordingly.
- Commands executed:
  - `cat > notes/inference-plan.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Telemetry utilities
# 2025-12-06 — HawkEars runner plan
- Added retry/backoff details to `notes/inference-plan.md` (up to 2 retries per chunk, telemetry\n+  annotation).\n+- Commands executed: `apply_patch notes/inference-plan.md`\n+\n # 2025-12-06 — Telemetry utilities
- Added `telemetry.py` and hooked it into `infer_scheduler` to log JSONL events per chunk/worker.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Inference telemetry plan
- Expanded `notes/inference-plan.md` with telemetry logging details (JSONL storage, command
  metadata, retry info).
- Commands executed: `apply_patch notes/inference-plan.md`

# 2025-12-06 — Inference scheduler scaffolding
- Added `src/badc/infer_scheduler.py` + CLI hooks so `badc infer run --manifest ...` loads chunk jobs
  and reports detected GPU workers; updated tests to reflect manifest-based invocation.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk manifest path integration
- `badc chunk run` now passes real chunk metadata to the manifest writer so path/hash entries
  reference generated files; tests updated.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk run CLI test
- Added regression test for `badc chunk run` ensuring chunk files + manifest are created.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk run CLI scaffold
- Added `badc chunk run` command (dry-run + chunk writing), chunk writer overlap handling, and docs.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk writer scaffolding
- Introduced `chunk_writer.py` plus updated `badc chunk manifest --hash-chunks` to generate chunk
  files with hashes (still stubbed for real overlap handling and temp layout).
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk file plan
- Added `notes/chunk-files.md` outlining the implementation strategy for `badc chunk run`
  (chunk writer + manifest integration) and updated the roadmap accordingly.
- Commands executed:
  - `cat > notes/chunk-files.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Manifest hashing improvement
- `badc chunk manifest --hash-chunks` now hashes the source file per chunk row (still placeholder
  until actual chunk files exist).
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — GPU CLI knobs planned
- Noted in `notes/pipeline-plan.md` that `badc infer run` should expose `--max-gpus` and worker
  pool overrides, defaulting to auto-detected GPU counts.
- Commands executed: `apply_patch notes/pipeline-plan.md`

# 2025-12-06 — GPU detection CLI
- Added `badc gpus` command and `src/badc/gpu.py` helper to enumerate GPUs via `nvidia-smi` so we
  can size the HawkEars worker pool per environment.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — GPU parallelism planning
- Updated `notes/gpu-monitoring.md` and `notes/pipeline-plan.md` to capture automatic GPU
  detection and multi-process HawkEars scheduling (one worker per GPU with NVML telemetry).
- Commands executed:
  - `apply_patch notes/gpu-monitoring.md`
  - `apply_patch notes/pipeline-plan.md`

# 2025-12-06 — Chunk manifest hashing option
- Added SHA256 utility + `--hash-chunks` option so `badc chunk manifest` can embed real hashes (per
  file for now) and documented the behavior in README/docs + tests.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Manifest hashing note
- Clarified in `notes/chunking.md` that SHA256 hashes must cover the chunk file bytes (not just
  placeholders) when the chunking engine lands.
- Commands executed: `apply_patch notes/chunking.md`

# 2025-12-06 — Chunk manifest follow-ups noted
- Documented in `notes/chunking.md` that `badc chunk manifest` currently writes placeholder hashes
  and needs SHA256 + overlap metadata in the upcoming implementation.
- Commands executed: `apply_patch notes/chunking.md`

# 2025-12-06 — Chunk manifest CLI scaffold
- Added `badc chunk manifest` command, WAV duration helper, sample tests/assets, and documentation
  so manifests can be generated ahead of the full HawkEars wiring.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunk manifest sample
- Added a sample chunk manifest CSV (`data/chunk_manifest_sample.csv`) and noted the future
  `badc chunk manifest` command in `notes/chunking.md` to clarify the metadata contract.
- Commands executed:
  - `cat > data/chunk_manifest_sample.csv`
  - `apply_patch notes/chunking.md`

# 2025-12-06 — Aggregation/reporting plan details
- Enriched `notes/pipeline-plan.md` with DuckDB table sketches, QC/report artifact expectations,
  and CLI implications for `badc aggregate/report`.
- Commands executed: `apply_patch notes/pipeline-plan.md`

# 2025-12-06 — Pipeline schema details
- Expanded `notes/pipeline-plan.md` with manifest and detection schema definitions (chunk IDs,
  timestamps, model metadata) so downstream automation has concrete targets.
- Commands executed: `apply_patch notes/pipeline-plan.md`

# 2025-12-06 — Pipeline planning note
- Added `notes/pipeline-plan.md` describing the chunk → infer → aggregate → report stages,
  including manifests, telemetry expectations, and CLI hooks.
- Updated the roadmap to reference the plan in the CLI orchestration task.
- Commands executed:
  - `cat > notes/pipeline-plan.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Inference CLI scaffolding
- Added `badc infer run|aggregate` placeholder commands plus utility helpers so the full
  chunk→infer→aggregate pipeline shape is represented in the CLI/tests/docs.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Bogus DataLad planning note
- Added `notes/bogus-datalad.md` outlining the lightweight audio dataset we will expose as a test
  submodule for the `badc data connect` workflow.
- Roadmap now references the new note under Phase 3.
- Commands executed:
  - `cat > notes/bogus-datalad.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Chunk CLI scaffolding
- Added `badc.chunk` subcommands (`probe`, `split`) plus `badc/chunking.py` utilities and tests to
  prepare for the real HawkEars/GPU integration.
- Documented the commands in README/docs and kept CI green via ruff/pytest/Sphinx builds.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — Chunking note audio details
- Updated `notes/chunking.md` to document the 60 min (`GNWT-290_20230331_235938.wav`) and 7 min
  (`XXXX-000_20251001_093000.wav`) test clips, highlight the HawkEars reference paper in
  `reference/`, and capture the plan to move these samples into a mini DataLad dataset.
- Commands executed:
  - `apply_patch notes/chunking.md`

# 2025-12-06 — Chunking probe planning note
- Added `notes/chunking.md` detailing the chunk-size probing workflow (binary search, telemetry
  capture, CLI surface) and documenting the GPU inventories we must account for.
- Roadmap now references the note for the chunk-size discovery task.
- Commands executed:
  - `cat > notes/chunking.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — HawkEars submodule onboarding
- Added the HawkEars fork as a git submodule under `vendor/HawkEars` and exposed
  `badc.hawkears.get_hawkears_root()` so CLI/tools can locate it.
- Updated README instructions to remind contributors to run `git submodule update --init --recursive`
  and marked the roadmap task complete.
- Commands executed:
  - `git submodule add https://github.com/UBC-FRESH/HawkEars vendor/HawkEars`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — GPU monitoring plan note
- Added `notes/gpu-monitoring.md` outlining tooling (nvidia-smi, NVML, Nsight) and documenting the
  2-GPU dev vs. 4-GPU Sockeye environments so we can verify HawkEars utilizes available CUDA
  capacity.
- Updated `notes/roadmap.md` Detailed Next Steps with a dedicated GPU telemetry task.
- Commands executed:
  - `cat > notes/gpu-monitoring.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Pre-commit + CI automation
- Added `.pre-commit-config.yaml` with Ruff hooks and documented the setup in `README.md` so local
  workflows stay aligned with the agent contract.
- Introduced `.github/workflows/ci.yml` to run Ruff format/lint, `pytest`, and the Sphinx build on
  every push/PR; marked the roadmap task complete.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — DataLad installation guidance
- Expanded `notes/datalad-plan.md` with git-annex + DataLad install instructions (pip extras,
  NeuroDebian/Homebrew, and the `datalad-installer` shortcut) so future setup scripts have a
  canonical reference.
- Commands executed:
  - `apply_patch notes/datalad-plan.md`

# 2025-12-06 — Python/CLI/docs scaffolding
- Added initial project scaffold: `pyproject.toml`, `src/badc` package with Typer CLI stubs,
  editable install via Hatch, and README instructions.
- Introduced tooling + docs baselines: ruff/pytest config, `.gitignore`, `tests/test_cli.py`, and a
  minimal Sphinx tree (`docs/conf.py`, `docs/index.rst`, `docs/usage.rst`) that builds with the
  Furo theme.
- Ran the standard command cadence to prove the scaffold works locally.
- Commands executed:
  - `python -m pip install -e .[dev]`
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
  - `sphinx-build -b html docs docs/_build/html -W`

# 2025-12-06 — DataLad planning note + roadmap update
- Added `notes/datalad-plan.md` describing the bogus/test vs. production DataLad repositories and
  the required `badc data connect|disconnect|status` CLI surface.
- Extended `notes/roadmap.md` with tasks for the new DataLad workflow (Phase 0/2/3) and refreshed
  the "Detailed Next Steps" data-management item.
- Commands executed:
  - `cat > notes/datalad-plan.md`
  - `apply_patch notes/roadmap.md`

# 2025-12-06 — Governance scaffold + roadmap draft
- Added `AGENTS.md` and `CONTRIBUTING.md`, adapted from the FHOPS templates, to codify the coding-agent contract, doc/test expectations, and GPU/HPC data-handling rules for the new project.
- Created `CHANGE_LOG.md` (this file) and `notes/roadmap.md` so future work items, status, and command cadences stay traceable from the outset.
- Commands executed:
  - `cat > AGENTS.md`
  - `cat > CONTRIBUTING.md`
  - `cat > CHANGE_LOG.md`
  - `cat > notes/roadmap.md`
# 2025-12-06 — Detection aggregation CLI
- Implemented `badc infer aggregate` to scan detection JSON outputs, added `aggregate.py`, README/docs updates, and regression tests.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`

# 2025-12-06 — Telemetry finish timestamps
- Telemetry records now capture a single timestamp plus `finished_at`, and the HawkEars runner populates success/failure entries (with stdout/stderr snippets).
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
# 2025-12-06 — Telemetry monitor command
- Added `badc telemetry --log ...` to read the JSONL log and show the latest entries; documented in README/docs.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
# 2025-12-06 — Roadmap next steps
- Added roadmap bullets for HawkEars JSON parsing + DuckDB work and the upcoming bogus DataLad connect wiring.
- Commands executed: `apply_patch notes/roadmap.md`
- # 2025-12-06 — Detection schema parsing
- Aggregator now reads HawkEars JSON detections (`aggregate.py`) and emits canonical CSV rows
  (recording/chunk/timestamp/label/confidence); tests updated.
- Commands executed:
  - `ruff format src tests`
  - `ruff check src tests`
  - `pytest`
