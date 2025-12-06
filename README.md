# Bird Acoustic Data Cruncher (BADC)

Early scaffold for the Bird Acoustic Data Cruncher project. The goal is to wrap the HawkEars audio
classifier with a Typer-based CLI + Python toolkit capable of chunking ~60 TB of bird audio,
running inference locally or on UBC ARC resources, and aggregating detections for Erin Tattersall's
PhD analyses.

## Development setup
1. Create a Python 3.12 virtual environment.
2. Install in editable mode with dev extras:
   ```bash
   pip install -e .[dev]
   ```
3. Run the standard command cadence (per `AGENTS.md`): `ruff format`, `ruff check`, `pytest`, and
   eventually `sphinx-build` once docs grow.

The CLI entry point is `badc`. Use `badc --help` to inspect the available commands.
