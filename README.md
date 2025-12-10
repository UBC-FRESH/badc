# Bird Acoustic Data Compiler (BADC)

Early scaffold for the Bird Acoustic Data Compiler project. The goal is to wrap the HawkEars audio
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

> **GPU access tip:** if `badc gpus` prints “No GPUs detected via nvidia-smi” and a direct call to
> `nvidia-smi` returns “Failed to initialize NVML: Insufficient Permissions”, the driver is gating
> NVML to privileged users. Running `sudo nvidia-smi` should work, confirming the cards are present—
> ask the cluster admin to grant your user access (e.g., add you to the video group) so BADC can see
> the GPUs. Example session:
> ```bash
> gep@jupyterhub05:~/projects/badc$ badc gpus 
> No GPUs detected via nvidia-smi.
> gep@jupyterhub05:~/projects/badc$ nvidia-smi
> Failed to initialize NVML: Insufficient Permissions
> gep@jupyterhub05:~/projects/badc$ sudo nvidia-smi
> Sun Dec  7 07:50:48 2025       
> +-----------------------------------------------------------------------------------------+
> | NVIDIA-SMI 580.95.05              Driver Version: 580.95.05      CUDA Version: 13.0     |
> +-----------------------------------------+------------------------+----------------------+
> | GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
> | Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
> |                                         |                        |               MIG M. |
> |=========================================+========================+======================|
> |   0  Quadro RTX 4000                Off |   00000000:18:00.0 Off |                  N/A |
> | 30%   26C    P8              9W /  125W |    5743MiB /   8192MiB |      0%      Default |
> |                                         |                        |                  N/A |
> +-----------------------------------------+------------------------+----------------------+
> |   1  Quadro RTX 4000                Off |   00000000:3B:00.0 Off |                  N/A |
> | 30%   33C    P8             16W /  125W |    7548MiB /   8192MiB |      0%      Default |
> |                                         |                        |                  N/A |
> +-----------------------------------------+------------------------+----------------------+
> 
> +-----------------------------------------------------------------------------------------+
> | Processes:                                                                              |
> |  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
> |        ID   ID                                                               Usage      |
> |=========================================================================================|
> |  No running processes found                                                             |
> +-----------------------------------------------------------------------------------------+
> ```

## CLI preview

- `badc version` — display current package version.
- `badc data connect bogus --path data/datalad` — clones/updates the bogus DataLad dataset (uses
  `datalad clone` when installed, otherwise `git clone`) and records it in
  `~/.config/badc/data.toml`.
- `badc data disconnect bogus --drop-content` — marks the dataset as disconnected and optionally
  removes the files (useful for freeing disk space).
- `badc data status` — prints all recorded datasets and their local paths/status.
- `badc chunk probe` — inspects WAV metadata, estimates GPU VRAM needs, runs a binary search to
  find the largest chunk duration that fits in memory, and logs telemetry to
  `artifacts/telemetry/chunk_probe/…`.
- `badc chunk split` — scaffold command for chunk-size experiments (placeholder identifiers until
  the full chunk writer lands).
- `badc chunk manifest` — generates a chunk manifest CSV, optionally writing chunk files + hashes
  via `--hash-chunks`.
- `badc chunk run` — splits audio into chunk WAVs and produces a manifest for inference. When the
  source lives inside a DataLad dataset the command defaults to writing chunks under
  `<dataset>/artifacts/chunks/<recording>` and manifests under `<dataset>/manifests/<recording>.csv`.
- `badc chunk orchestrate` — scans a dataset’s `audio/` tree, lists recordings that still need
  manifests/chunk outputs, prints ready-to-run `datalad run` commands, persists CSV/JSON plans, and
  (with `--apply`) invokes `badc chunk run` for each recording. When the dataset contains `.datalad`
  and the `datalad` CLI is available, `--apply` wraps each job in `datalad run` automatically
  (disable with `--no-record-datalad`).
- `badc infer run --manifest manifest.csv` — loads chunk jobs, detects GPUs, and runs the HawkEars
  runner (pass `--use-hawkears` to invoke the embedded `vendor/HawkEars/analyze.py`, or `--runner-cmd`
  to supply a custom command; stub mode remains the default for local tests). Use `--cpu-workers N`
  to append CPU worker threads (at least one CPU worker is used automatically when no GPUs are
  detected). When chunks come from a DataLad dataset the command drops a telemetry log plus a
  `*.summary.json` file so you can resume interrupted runs without reprocessing completed chunks, and
  (e.g., `data/datalad/bogus`), outputs automatically land under `artifacts/infer/` inside that same
  dataset so you can `datalad save` immediately.
- `badc infer orchestrate` — scans a dataset’s manifests (or a saved chunk plan), prints an inference
  plan table, emits ready-to-run `datalad run` commands, saves CSV/JSON plans, and (with `--apply`)
  executes each recording immediately. When `.datalad` plus the CLI are available the applied runs
  are wrapped in `datalad run` automatically (toggle with `--no-record-datalad`).
- `badc infer aggregate artifacts/infer --manifest chunk_manifest.csv --parquet artifacts/aggregate/detections.parquet`
  — reads detection JSON files, pulls in chunk metadata from the manifest when available (start/end
  offsets, hashes), ingests the real HawkEars label output (label code/name, detection end offset,
  model version), writes a summary CSV, and (optionally) persists the canonical Parquet export for
  DuckDB tooling.
- `badc report summary --parquet artifacts/aggregate/detections.parquet --group-by label` — loads the
  Parquet detections export via DuckDB, prints grouped counts/average confidence, and optionally
  writes another CSV for downstream notebooks.
- `badc report quicklook --parquet artifacts/aggregate/detections.parquet` — runs a suite of DuckDB
  queries (top labels, top recordings, per-chunk timeline) and prints ASCII sparklines while saving
  optional CSV snapshots for notebooks/Phase 2 analytics.
- `badc report parquet --parquet artifacts/aggregate/detections.parquet` — produces Phase 2-ready
  CSV/JSON artifacts (labels, recordings, timeline buckets, summary stats) using DuckDB; perfect for
  Erin’s aggregation workflows.
- `badc report duckdb --parquet artifacts/aggregate/detections.parquet` — materializes the Parquet
  detections into a DuckDB database, prints top labels/recordings/timeline buckets, and writes
  optional CSV exports so Erin can open the `.duckdb` file and run custom SQL immediately.
- `badc infer monitor --log data/telemetry/infer/<manifest>_<timestamp>.jsonl` — stream per-GPU
  telemetry tables with events/success/failure counts, trending utilization (min/avg/max), peak VRAM
  usage, rolling ASCII sparklines (utilization + VRAM), and a live tail of recent chunk status
  updates.
- `badc telemetry --log data/telemetry/infer/<manifest>_<timestamp>.jsonl` — plain tail of telemetry
  events (the run command prints the exact log path).
- `badc gpus` — lists detected GPUs via `nvidia-smi` so we can size the HawkEars worker pool.

### Attaching the sample dataset

The bogus DataLad dataset is now a git submodule at `data/datalad/bogus`. After cloning the repo:

```bash
git submodule update --init --recursive
badc data connect bogus --pull

# Example HawkEars invocation once CUDA deps are installed:
badc infer run --manifest chunk_manifest.csv --use-hawkears --hawkears-arg --fast

# Preview the equivalent datalad run command (no jobs executed):
badc infer run --manifest chunk_manifest.csv --print-datalad-run
```

The `badc data connect` command prefers `datalad clone` (falls back to git) and records the dataset
in `~/.config/badc/data.toml` so subsequent `badc data status` calls show where the audio lives.

The CLI entry point is `badc`. Use `badc --help` to inspect the available commands.

## Documentation

Rendered Sphinx docs are published automatically from `main` at  
https://ubc-fresh.github.io/badc/
