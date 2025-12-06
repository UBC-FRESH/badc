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
