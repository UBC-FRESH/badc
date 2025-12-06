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
