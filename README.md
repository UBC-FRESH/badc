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
3. Initialise submodules (HawkEars fork + bogus DataLad dataset) so the wrapper utilities and sample
   data are available, then connect the bogus dataset so DataLad metadata is recorded locally:
   ```bash
   git submodule update --init --recursive
   badc data connect bogus --pull
   ```
4. Run `pre-commit install` so the Ruff hooks run automatically before each commit.
5. Run the standard command cadence (per `AGENTS.md`): `ruff format`, `ruff check`, `pytest`, and
   `sphinx-build` once docs grow.

GitHub Actions (`.github/workflows/ci.yml`) mirrors these commands on every push/PR.

## CLI preview

- `badc version` — display current package version.
- `badc data connect bogus --path data/datalad` — clones/updates the bogus DataLad dataset (uses
  `datalad clone` when installed, otherwise `git clone`) and records it in
  `~/.config/badc/data.toml`.
- `badc data disconnect bogus --drop-content` — marks the dataset as disconnected and optionally
  removes the files (useful for freeing disk space).
- `badc data status` — prints all recorded datasets and their local paths/status.
- `badc chunk probe|split` — scaffold commands for chunk-size experiments (currently stubs until
  HawkEars + GPU telemetry wiring lands).
- `badc chunk manifest` — generates a chunk manifest CSV, optionally writing chunk files + hashes
  via `--hash-chunks`.
- `badc chunk run` — splits audio into chunk WAVs and produces a manifest for inference.
- `badc infer run --manifest manifest.csv` — loads chunk jobs, detects GPUs, and runs the HawkEars
  runner (stubbed until the real CLI is wired).
- `badc infer aggregate artifacts/infer` — reads detection JSON files and writes a summary CSV.
- `badc telemetry --log data/telemetry/infer/log.jsonl` — tail recent telemetry entries.
- `badc gpus` — lists detected GPUs via `nvidia-smi` so we can size the HawkEars worker pool.

### Attaching the sample dataset

The bogus DataLad dataset is now a git submodule at `data/datalad/bogus`. After cloning the repo:

```bash
git submodule update --init --recursive
badc data connect bogus --pull
```

The `badc data connect` command prefers `datalad clone` (falls back to git) and records the dataset
in `~/.config/badc/data.toml` so subsequent `badc data status` calls show where the audio lives.

The CLI entry point is `badc`. Use `badc --help` to inspect the available commands.
