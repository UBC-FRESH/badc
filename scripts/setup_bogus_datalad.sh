#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="$REPO_DIR/setup/datalad_config.sh"
if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "Missing $CONFIG_PATH" >&2
  exit 1
fi
source "$CONFIG_PATH"

if [[ -z "${GITHUB_ORG:-}" || -z "${GITHUB_REPO_NAME:-}" ]]; then
  echo "GITHUB_ORG and GITHUB_REPO_NAME must be set in $CONFIG_PATH" >&2
  exit 1
fi
if [[ -z "${DATALAD_GITHUB_TOKEN:-}" ]]; then
  echo "DATALAD_GITHUB_TOKEN must be set in $CONFIG_PATH" >&2
  exit 1
fi

export GITHUBTOKEN="$DATALAD_GITHUB_TOKEN"

DATASET_DIR="$REPO_DIR/tmp/badc-bogus-data"
rm -rf "$DATASET_DIR"
mkdir -p "$DATASET_DIR"
cd "$DATASET_DIR"

datalad create --force
mkdir -p audio
cp "$REPO_DIR/data/audio"/*.wav audio/ 2>/dev/null || true
datalad save -m "Add sample audio"

cat <<CFG > .gitmodules
[submodule "vendor/HawkEars"]
    path = vendor/HawkEars
    url = https://github.com/UBC-FRESH/HawkEars.git
CFG

annex_host=${S3_ENDPOINT_URL#https://}
existing_uuid=""
if aws s3 ls "s3://$S3_BUCKET_NAME/git-annex-uuid" >/dev/null 2>&1; then
  existing_uuid=$(aws s3 cp "s3://$S3_BUCKET_NAME/git-annex-uuid" - | tr -d '\r\n' || true)
fi

init_params=(
  arbutus-s3
  type=S3
  bucket="$S3_BUCKET_NAME"
  public=yes
  publicurl="$S3_ENDPOINT_URL/$S3_BUCKET_NAME"
  host="$annex_host"
  protocol=https
  requeststyle=path
  autoenable=true
)

if [[ -n "$existing_uuid" ]]; then
  init_params+=(--sameas="$existing_uuid")
else
  init_params+=(encryption=none)
fi

git annex initremote "${init_params[@]}"

datalad create-sibling-github \
  --github-organization "$GITHUB_ORG" \
  --name origin \
  --publish-depends arbutus-s3 \
  "$GITHUB_REPO_NAME"

git config remote.arbutus-s3.annex-multipartthreshold 50M

echo "Dataset prepared at $DATASET_DIR and GitHub repo created (push already executed by DataLad)."
