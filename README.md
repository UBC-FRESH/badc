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
3. Initialise submodules (HawkEars fork) so the wrapper utilities can find the inference engine:
   ```bash
   git submodule update --init --recursive
   ```
4. Run `pre-commit install` so the Ruff hooks run automatically before each commit.
5. Run the standard command cadence (per `AGENTS.md`): `ruff format`, `ruff check`, `pytest`, and
   `sphinx-build` once docs grow.

GitHub Actions (`.github/workflows/ci.yml`) mirrors these commands on every push/PR.

## CLI preview

- `badc version` — display current package version.
- `badc data ...` — placeholder commands for future DataLad integration.
- `badc chunk probe|split` — scaffold commands for chunk-size experiments (currently stubs until
  HawkEars + GPU telemetry wiring lands).
- `badc chunk manifest` — generates a chunk manifest CSV, optionally writing chunk files + hashes
  via `--hash-chunks`.
- `badc chunk run` — splits audio into chunk WAVs and produces a manifest for inference.
- `badc infer run --manifest manifest.csv` — loads chunk jobs, detects GPUs, and runs the HawkEars
  runner (stubbed until the real CLI is wired).
- `badc data connect bogus` — placeholder for cloning the upcoming bogus DataLad dataset (smoke tests).
- `badc infer aggregate artifacts/infer` — reads detection JSON files and writes a summary CSV.
- `badc gpus` — lists detected GPUs via `nvidia-smi` so we can size the HawkEars worker pool.

The CLI entry point is `badc`. Use `badc --help` to inspect the available commands.
