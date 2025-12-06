#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="$REPO_DIR/setup/datalad_config.sh"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Missing $CONFIG_PATH" >&2
  exit 1
fi
source "$CONFIG_PATH"

if [[ -z "${GITHUB_REPO_URL:-}" ]]; then
  echo "GITHUB_REPO_URL is not set in $CONFIG_PATH" >&2
  exit 1
fi

DATASET_DIR="$REPO_DIR/tmp/badc-bogus-data"
rm -rf "$DATASET_DIR"
mkdir -p "$DATASET_DIR"
cd "$DATASET_DIR"

datalad create --force
mkdir -p audio
cp "$REPO_DIR/data/audio"/*.wav audio/ 2>/dev/null || true
datalad save -m "Add sample audio"

if ! git ls-remote "$GITHUB_REPO_URL" >/dev/null 2>&1; then
  echo "Remote $GITHUB_REPO_URL not reachable. Create the GitHub repo and rerun." >&2
  exit 1
fi
git remote remove origin >/dev/null 2>&1 || true
git remote add origin "$GITHUB_REPO_URL"

cat <<CFG > .gitmodules
[submodule "vendor/HawkEars"]
    path = vendor/HawkEars
    url = https://github.com/UBC-FRESH/HawkEars.git
CFG

annex_host=${S3_ENDPOINT_URL#https://}
git annex initremote arbutus-s3 \
  type=S3 \
  encryption=none \
  bucket="$S3_BUCKET_NAME" \
  public=yes \
  publicurl="$S3_ENDPOINT_URL/$S3_BUCKET_NAME" \
  host="$annex_host" \
  protocol=https \
  requeststyle=path \
  autoenable=true

echo "Dataset prepared at $DATASET_DIR (manual push required)."
