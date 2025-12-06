# Coding Agent Operating Notes

These notes govern day-to-day execution for Codex (and collaborators) working on Bird Acoustic
Data Cruncher (BADC). Follow them for every milestone, feature branch, or pull request. Treat
this file as the root contract: its guidance applies everywhere unless a subdirectory ships a
more specific `AGENTS.md`.

## Command cadence (run before handing work back)
Until the tooling stack is fully wired, keep this checklist short but strict. Expand it as soon
as the corresponding configs land in the repo.

1. `ruff format src tests` *(add `pyproject.toml`/`ruff.toml` once the Python package scaffold
   exists)*
2. `ruff check src tests`
3. `pytest` *(or the project-specific Hatch/UV runner once defined)*
4. `sphinx-build -b html docs _build/html -W` *(after docs scaffolding lands)*
5. `pre-commit run --all-files` *(after `pre-commit` is configured)*
6. Record every executed command in the current `CHANGE_LOG.md` entry. If a command is skipped,
   write down why (e.g., feature branch lacks docs yet).

Address warnings instead of suppressing them; escalate only after confirming the warning is not a
regression.

## Planning hygiene
- Keep `notes/roadmap.md` authoritative. Update phase checkboxes and "Detailed Next Steps"
  whenever work starts/pauses/completes.
- Maintain topical notes under `notes/` (e.g., `notes/erin-notes.md`, CLI plans, HPC ops). These
  notes should always reflect the latest assumptions, blockers, and design options.
- **Every change set must append to `CHANGE_LOG.md` immediately after implementation.** Restate
  the status update you intend to share with maintainers.
- Before proposing new work, read `notes/erin-notes.md`, `notes/roadmap.md`, and the latest
  changelog entry so priorities stay aligned with the PhD deliverables.

## Data & infrastructure handling
- Large raw audio lives in the DataLad-managed paths under `data/datalad/` (e.g.,
  `data/datalad/bogus/audio/`). The legacy `data/audio/` directory should remain empty and only
  contain documentation. Never commit large binaries outside the DataLad-managed paths once that
  setup lands. Until then, keep audio fixtures lightweight (<10 MB) and document provenance.
- When scripting HawkEars runs, provide switches for CPU/GPU selection and document the expected
  NVIDIA memory requirements. Capture crash logs that relate to CUDA OOMs in `notes/`.
- For HPC workflows (Sockeye, Chinook), prefer containerised (Apptainer) entry points. Record the
  exact container build/push/pull commands in the changelog and, when relevant, in dedicated
  notes.
- Treat any credentials (Sylabs tokens, Chinook access keys) as secrets—use environment variables
  or config files ignored by Git.

## Code & documentation expectations
- Ship small, reviewable commits tied to roadmap tasks.
- When behaviour changes, update docs immediately: README snippets, Sphinx how-tos, CLI `--help`
  text, and relevant notes.
- Guard new functionality with focused tests (unit, CLI smoke, or notebook harness as
  appropriate). For GPU-only logic, provide CPU fallbacks or descriptive skips so CI can still
  pass.
- Docstrings follow the NumPy style from day one: summary line, explicit ``Parameters`` /
  ``Returns`` /
  ``Raises`` /
  ``Notes`` sections (omit unused ones). Document units, ranges, defaults, and side-effects.
  Describe return payloads (DataFrames, dicts, dataclasses) explicitly. Cite HawkEars docs or
  supporting literature when referencing models or heuristics.
- Module docstrings must explain why the module exists (e.g., CLI chunker, Apptainer builder,
  Datalad helper) and reference the authoritative note/roadmap section.
- Keep docstrings, docs, and CLI help in lockstep—run `sphinx-build -b html docs _build/html -W`
  whenever you touch user-facing text.

## Release workflow (future-ready)
- Packaging will follow Hatch once the Python package skeleton lands; mirror FHOPS by using
  ``hatch build`` for validation and versioning via `src/badc/__init__.__version__` (or similar).
- Maintain a release checklist note (e.g., `notes/release_prep.md`) capturing Apptainer build
  steps, DataLad tagging, and GitHub Pages deployment for docs.
- Before tagging any release, ensure the containers, docs, and CLI help reference the same
  feature set and that sample datasets are synchronised with the DataLad remote.

## Collaboration guidelines
- Log blockers or scope shifts in the relevant note and cross-link from `CHANGE_LOG.md`.
- Use feature branches; name them after roadmap tasks (e.g., `feature/cli-split-chunker`).
- Use draft PRs/issues to capture design discussions. Summarise the resolution back into
  `notes/roadmap.md` or topical notes so readers can catch up without trawling Git history.

## Starting a new Codex chat
- Open this repository as the workspace and read `AGENTS.md`, `notes/roadmap.md`, and the note
  tied to your task (usually `notes/erin-notes.md`). These are the authoritative context sources.
- Keep each chat focused on a single roadmap item or closely related set of tasks. When a block
  finishes, add a short summary to `CHANGE_LOG.md` and update any affected notes.
