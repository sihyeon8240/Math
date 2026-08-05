#!/usr/bin/env bash
set -u

event_name="${1:?usage: check-image-tag.sh <event> <base> [head]}"
base_revision="${2:-}"
head_revision="${3:-HEAD}"
output_file="${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"
image_ref="${IMAGE_NAME:?IMAGE_NAME is required}:${RELEASE_TAG:?RELEASE_TAG is required}"
inputs=(.devcontainer/Dockerfile scripts/check-environment.sh)

inputs_changed=false
if [[ "$event_name" == push ]]; then
  if [[ -z "$base_revision" || "$base_revision" =~ ^0+$ ]] ||
     ! git cat-file -e "${base_revision}^{commit}" 2>/dev/null ||
     ! git diff --quiet "$base_revision" "$head_revision" -- "${inputs[@]}"; then
    inputs_changed=true
  fi
fi

if docker manifest inspect "$image_ref" >/dev/null 2>&1; then
  if [[ "$inputs_changed" == true ]]; then
    echo "error: immutable image tag already exists: $image_ref" >&2
    echo "error: bump RELEASE_TAG because image inputs changed" >&2
    exit 1
  fi
  echo "Immutable image tag already exists; it will not be overwritten." >&2
  echo "exists=true" >> "$output_file"
else
  echo "exists=false" >> "$output_file"
fi
