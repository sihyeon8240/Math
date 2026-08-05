#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "usage: $0 <tag>" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
tag="$1"

mapfile -t releasable_books < <(
  "$PYTHON" "$repo_root/scripts/books.py" list --for release
)

version_pattern='[0-9]+\.[0-9]+\.[0-9]+'
version_pattern+='(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?'
single_book_pattern='^([a-z0-9]+(-[a-z0-9]+)*)-v'
single_book_pattern+="($version_pattern)\$"

if [[ "$tag" =~ $single_book_pattern ]]; then
  requested_book="${BASH_REMATCH[1]}"
  version="${BASH_REMATCH[3]}"
  if [[ ! " ${releasable_books[*]} " =~ " ${requested_book} " ]]; then
    echo "error: book is not enabled for release in books.yml: $requested_book" >&2
    exit 2
  fi
  targets=("$requested_book")
else
  echo "error: invalid release tag '$tag'" >&2
  echo "expected <book>-v<version>" >&2
  exit 2
fi
for book in "${targets[@]}"; do
  metadata_version="$("$PYTHON" "$repo_root/scripts/books.py" version "$book")"
  if [[ "$metadata_version" != "$version" ]]; then
    echo "error: tag version $version does not match" \
      "books/$book/metadata.tex (bookversion=$metadata_version)" >&2
    exit 1
  fi
  printf '%s_version=%s\n' "${book//-/_}" "$metadata_version"
done
printf 'version=%s\n' "$version"
printf 'matrix={"book":["%s"]}\n' "${targets[0]}"
