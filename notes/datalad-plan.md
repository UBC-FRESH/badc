# DataLad Repository Plan

This note tracks how BADC will manage large bird-audio assets using DataLad + UBC ARC storage. It
covers the two-tier repository approach (bogus/test vs. production) and the user-facing commands
required for connecting/disconnecting datasets at runtime.

## Goals
- Keep the Git repo lightweight while still providing representative audio samples.
- Provide an always-public "bogus" DataLad dataset (synthetic or short clips) for local dev/tests.
- Provide a production dataset that mirrors the 60 TB archive, hosted on Chinook object storage and
  gated behind UBC ARC credentials.
- Allow users to attach/detach either dataset via CLI commands so deployments can swap data sources
  without editing code.

## Repository tiers
### 1. Bogus/test dataset (public)
- **Purpose**: smoke-test chunking/inference flows, demo CLI usage, and run CI-friendly pipelines.
- **Contents**: curated short clips (≤10 MB each) plus metadata manifest. May include downsampled
  HawkEars outputs for deterministic tests.
- **Location**: GitHub repo under UBC-FRESH (e.g., `bird-audio-bogus`) initialised as a DataLad
  dataset. Storage can be plain Git (no special remotes) so contributors can clone without
  credentials.
- **Tasks**:
  - Create dataset skeleton with README describing limitations.
  - Add it as a subdataset under `data/datalad/bogus` in this repo.
  - Provide automation (`scripts/datalad/setup_bogus.sh`) to clone/update it.
  - Keep file sizes below GitHub’s 100 MB limit; rely on Datalad/Git LFS only if necessary.

### 2. Production dataset (restricted)
- **Purpose**: house the 60 TB archive and authoritative HawkEars outputs for Erin’s project.
- **Contents**: raw WAV/FLAC shards, chunk manifests, intermediate outputs, and QA notebooks.
- **Location**: DataLad dataset backed by Chinook object storage (S3-compatible special remote).
- **Access**: restricted to PI accounts; requires UBC ARC credentials + possibly VPN.
- **Tasks**:
  - Set up the DataLad dataset on Chinook VM with `datalad create` + `datalad siblings add-s3` to
    register the special remote.
  - Document credential bootstrap (ARC tokens, environment variables, or AWS-style config files) in
    a secure note.
  - Publish dataset metadata to a GitHub repo (without annexed files) so collaborators can clone the
    structure and then `datalad get` from Chinook.
  - Define naming convention for study areas / recordings (e.g., `GNWT-290/2023/…`).
  - Determine versioning cadence (per ingest vs. per processing milestone) and record it here.

## CLI integration (`badc data connect/disconnect`)
- Implement Typer commands under the main CLI namespace:
  - `badc data connect --name bogus --path <local-path>`
    - Clones (or updates) the specified DataLad dataset into `data/datalad/<name>`.
    - Records the active dataset in a config file (e.g., `~/.config/badc/data.toml`).
  - `badc data disconnect --name bogus`
    - Drops annexed content (`datalad drop --reckless auto`) and removes the config entry.
  - `badc data status` to list attached datasets and whether their content is present locally.
- Commands should emit clear guidance when credentials are missing (production repo) or when
  detaching would remove in-use files.
- Provide optional `--special-remote` argument so advanced users can point at alternate Chinook
  buckets.
- Surface these commands in docs + README as part of environment bootstrap.

## Open questions / follow-ups
1. How much bogus data do we need to exercise CUDA chunking without tripping GPU VRAM limits?
2. Should the production dataset include HawkEars intermediate outputs, or should those live in a
   sibling dataset to keep annex sizes manageable?
3. What is the preferred secret-management mechanism for Chinook credentials (ARC Vault, Pass,
   environment module)?
4. Do we need per-user quotas/logging when `badc data connect` pulls tens of GB onto dev servers?
5. Can we automate dataset integrity checks (e.g., `datalad fsck`) inside CI for the bogus repo?

## Installation notes
- **git-annex** is mandatory. Install via NeuroDebian/apt on Ubuntu, Homebrew on macOS, or the
  cross-platform `datalad-installer git-annex` tool (recommended when system packages lag).
- After `git-annex` is on `PATH`, install DataLad plus extras: `python -m pip install
  "datalad[full]"`. Use `--user` or `pip3` variants as needed.
- The `datalad-installer` Python package can bootstrap both `git-annex` and DataLad in a portable
  fashion, which may be easier on HPC nodes where we lack root.
