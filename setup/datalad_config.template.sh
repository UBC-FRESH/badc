#!/usr/bin/env bash
# Copy to setup/datalad_config.sh and fill in secrets before sourcing.

export AWS_ACCESS_KEY_ID="CHANGE_ME"
export AWS_SECRET_ACCESS_KEY="CHANGE_ME"
export AWS_DEFAULT_REGION="ca-west-1"
export S3_ENDPOINT_URL="https://object-arbutus.cloud.computecanada.ca"
export S3_BUCKET_NAME="ubc-fresh-badc-bogus-data"
export GITHUB_REPO_URL="git@github.com:UBC-FRESH/badc-bogus-data.git"
export DATALAD_GITHUB_TOKEN="CHANGE_ME"

export AWS_EC2_METADATA_DISABLED=true
