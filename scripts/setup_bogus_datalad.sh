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
if [[ -d "$DATASET_DIR" ]]; then
  chmod -R u+w "$DATASET_DIR" || true
  rm -rf "$DATASET_DIR"
fi
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
manual_uuid="${S3_EXISTING_REMOTE_UUID:-}"
if aws s3 ls "s3://$S3_BUCKET_NAME" >/dev/null 2>&1; then
  if aws s3 ls "s3://$S3_BUCKET_NAME/git-annex-uuid" >/dev/null 2>&1; then
    if uuid_contents=$(aws s3 cp "s3://$S3_BUCKET_NAME/git-annex-uuid" - 2>/dev/null); then
      existing_uuid="$(tr -d '\r\n' <<<"$uuid_contents")"
    elif [[ -n "$manual_uuid" ]]; then
      existing_uuid="$manual_uuid"
    elif [[ "${S3_RESET_CONFLICTING_BUCKET:-}" == "1" ]]; then
      echo "Bucket $S3_BUCKET_NAME has annex metadata but is unreadable; resetting bucket." >&2
      aws s3 rm --recursive "s3://$S3_BUCKET_NAME" >/dev/null 2>&1 || true
      aws s3 rb "s3://$S3_BUCKET_NAME" >/dev/null 2>&1 || true
      existing_uuid=""
    else
      cat >&2 <<EOF
Bucket $S3_BUCKET_NAME already exists but git-annex UUID cannot be read.
Set S3_EXISTING_REMOTE_UUID to the known UUID, or export S3_RESET_CONFLICTING_BUCKET=1 to allow the script to delete the bucket automatically.
EOF
      exit 1
    fi
  else
    if [[ "${S3_RESET_CONFLICTING_BUCKET:-}" == "1" ]]; then
      echo "Bucket $S3_BUCKET_NAME exists without git-annex metadata; resetting bucket." >&2
      aws s3 rm --recursive "s3://$S3_BUCKET_NAME" >/dev/null 2>&1 || true
      aws s3 rb "s3://$S3_BUCKET_NAME" >/dev/null 2>&1 || true
    else
      cat >&2 <<EOF
Bucket $S3_BUCKET_NAME exists but does not contain a git-annex-uuid file.
Export S3_RESET_CONFLICTING_BUCKET=1 to allow automatic cleanup, or point the script at a different bucket.
EOF
      exit 1
    fi
  fi
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
  init_params+=("sameas=$existing_uuid")
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
