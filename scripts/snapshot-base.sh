#!/usr/bin/env bash
set -u

head_revision="${1:-HEAD}"
output_file="${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"
base=""

if git fetch --no-tags origin generated-pdfs >/dev/null 2>&1; then
  source_sha="$(git show origin/generated-pdfs:.source-sha 2>/dev/null || true)"
  if [[ "$source_sha" =~ ^[0-9a-f]{40}$ ]] &&
     git cat-file -e "${source_sha}^{commit}" 2>/dev/null &&
     git merge-base --is-ancestor "$source_sha" "$head_revision" 2>/dev/null; then
    base="$source_sha"
  fi
fi

printf 'base=%s\n' "$base" >> "$output_file"
