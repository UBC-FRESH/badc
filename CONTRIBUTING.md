# Contributing

1. Create a Python 3.12+ virtual environment and install dev deps once the package scaffold is
   available: `pip install -e .[dev]`. Until then, pin tool versions in `requirements-dev.txt` or
   `pyproject.toml` as they land.
2. Enable pre-commit once `.pre-commit-config.yaml` exists: `pre-commit install`.
3. Run tests locally (`pytest`, `hatch run dev:suite`, or the equivalent) before every push.
4. Prefer feature branches; open PRs against `main` and link them to roadmap items / notes.
5. Document every change set:
   - Update Sphinx docs, README snippets, and CLI help when behaviour changes.
   - Add an entry to `CHANGE_LOG.md` describing what changed, why, and which commands you ran.
6. HawkEars + HPC specifics:
   - Keep audio fixtures small in Git. Large assets belong in the future DataLad remote backed by
     Chinook object storage.
   - Capture GPU/CPU requirements, chunk-size heuristics, and CUDA-related caveats in docs and
     notes so other contributors can reproduce your runs.
   - When containerising (Apptainer), commit the definition files and document build/push steps in
     the changelog/notes.
7. Docstrings follow NumPy style from the outset:
   1. One-sentence summary in sentence case.
   2. Explicit ``Parameters`` / ``Returns`` / ``Raises`` / ``Notes`` sections (omit unused ones).
   3. Document every argument with types, units, allowable ranges, defaults, and coupling to other
      arguments. Describe mapping/dataclass schemas explicitly.
   4. Explain return payloads (DataFrames, dicts, dataclasses) with column names/fields and units.
   5. Mention side-effects (file writes, telemetry, mutations) up front.
   6. Cite HawkEars docs, FPInnovations studies, or other provenance when referencing models or
      heuristics.
   7. Provide short ``Examples`` blocks when workflows span multiple steps (chunking → inference →
      aggregation) or when CLI usage is non-trivial.
8. Keep docstrings, CLI help, and Sphinx pages in sync. Run `sphinx-build -b html docs
   _build/html -W` when touching user-facing text.
9. Tests: add focused unit/CLI tests for every new feature. For GPU-only paths, include CPU
   fallbacks or mark tests with descriptive skips.
10. Releases (future): use Hatch for versioning/builds, mirror FHOPS release cadence (TestPyPI
    first, then PyPI/GitHub container registry), and ensure DataLad remotes + docs are refreshed
    before tagging.
